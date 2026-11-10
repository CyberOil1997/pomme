// The real Blender apple, rendered live with three.js so it spins smoothly.
// Geometry, the studio lighting (studio.hdr) and the soft shadow all come
// from blender/apple.py --mode export. Nothing here draws art; it only
// lights and shows the model.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';

const ASSETS = '../assets/3d/';

const TINTS = {
  red: { body: 0xe3150c, cut: 0xd8463a, attenuation: 0xd8231c, leaf: 0x55c22e },
  green: { body: 0x62c72a, cut: 0x7cc04a, attenuation: 0x4f9e1f, leaf: 0x55c22e },
};

export class Apple3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.toneMapping = THREE.AgXToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.scene = new THREE.Scene();
    // camera matches the Blender camera: 70mm lens on a 36mm sensor, (0,-6.8,0.95)
    this.camera = new THREE.PerspectiveCamera(2 * Math.atan(18 / 70) * 180 / Math.PI, 1, 0.1, 100);
    this.camera.position.set(0, 0.95, 6.8);
    this.camera.lookAt(0, 0.05, 0);

    this.pivot = new THREE.Group();
    this.scene.add(this.pivot);
    this.stages = [];
    this.stage = 0;
    this.color = 'red';
    this.mats = this.makeMaterials();
    this.dirty = true;
    this.squash = 0;
    this.rect = { x: 0, y: 0, size: 264 };
  }

  makeMaterials() {
    // Crystal in two layers, like the Cycles render:
    //  body:  the studio seen *through* the glass (refraction), tinted
    //  shell: the studio reflected *off* the glass, added on top
    const glass = new THREE.MeshBasicMaterial({ color: 0xffffff, refractionRatio: 1 / 1.55, reflectivity: 1 });
    const shell = new THREE.MeshPhysicalMaterial({
      color: 0x000000, metalness: 0, roughness: 0.03, specularIntensity: 1, ior: 1.55,
      envMapIntensity: 1.0,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const leafBody = new THREE.MeshBasicMaterial({ color: 0xffffff, refractionRatio: 1 / 1.4, reflectivity: 1 });
    // bitten faces: frosted, like sandblasted crystal
    const cut = new THREE.MeshPhysicalMaterial({
      color: 0xf7f3ec, roughness: 0.42, metalness: 0, specularIntensity: 0.7,
      sheen: 0.4, sheenRoughness: 0.5, envMapIntensity: 0.9,
      emissive: 0xfff8f0, emissiveIntensity: 0.12,
    });
    const gold = new THREE.MeshPhysicalMaterial({ color: 0xffbd61, metalness: 1, roughness: 0.16, envMapIntensity: 1.3 });
    this.shellMat = shell;
    return { Glass: glass, GlassCut: cut, Gold: gold, Leaf: leafBody };
  }

  tint(color) {
    const t = TINTS[color];
    const { Glass, GlassCut, Leaf } = this.mats;
    Glass.color.set(t.body);
    // the flesh is white on both apples; only a whisper of the skin colour
    GlassCut.sheenColor.set(t.body).lerp(new THREE.Color(0xffffff), 0.7);
    Leaf.color.set(t.leaf);
    this.dirty = true;
  }

  async load(onFirst) {
    const hdr = await new HDRLoader().loadAsync(ASSETS + 'studio.hdr');
    hdr.mapping = THREE.EquirectangularReflectionMapping;
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromEquirectangular(hdr).texture;
    pmrem.dispose();
    const refr = hdr.clone();
    refr.mapping = THREE.EquirectangularRefractionMapping;
    refr.needsUpdate = true;
    this.mats.Glass.envMap = refr;
    this.mats.Leaf.envMap = refr;

    const shadowTex = await new THREE.TextureLoader().loadAsync(ASSETS + 'shadow.png');
    shadowTex.colorSpace = THREE.SRGBColorSpace;
    this.shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(3, 3),
      new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, opacity: 0.55, depthWrite: false, toneMapped: false }),
    );
    this.shadow.rotation.x = -Math.PI / 2;
    this.scene.add(this.shadow);

    const loader = new GLTFLoader();
    const loadStage = async (i) => {
      const gltf = await loader.loadAsync(`${ASSETS}s${i}.glb`);
      const root = gltf.scene;
      const shells = [];
      root.traverse((o) => {
        if (!o.isMesh) return;
        const name = o.material.name;
        o.material = this.mats[name] || this.mats.Glass;
        if (name === 'Glass' || name === 'Leaf') shells.push(o);
      });
      for (const o of shells) {
        const s = new THREE.Mesh(o.geometry, this.shellMat);
        s.renderOrder = 2;
        o.add(s);
      }
      root.visible = i === this.stage;
      this.pivot.add(root);
      this.stages[i] = root;
      if (i === 0) {
        const box = new THREE.Box3().setFromObject(root);
        this.ground = box.min.y;
        this.shadow.position.y = this.ground + 0.002;
      }
      this.dirty = true;
    };
    await loadStage(0);
    onFirst?.();
    for (let i = 1; i < 6; i++) await loadStage(i);
  }

  setStage(i) {
    this.stage = i;
    this.stages.forEach((r, k) => { if (r) r.visible = k === i; });
    this.dirty = true;
  }

  setBackground(hex) {
    if (!this.backdrop) this.scene.background = new THREE.Color(hex);
    this.dirty = true;
  }

  // The set behind the apple (sweep, plinth, window light) is a Blender
  // render from this same camera, 4x wider than the apple's square, so it
  // can be cropped to whatever the window shows and still line up.
  async setBackdrop(color) {
    const tex = await new THREE.TextureLoader().loadAsync(`${ASSETS}backdrop_${color}.webp`);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.generateMipmaps = false;
    tex.minFilter = THREE.LinearFilter;
    if (this.backdrop) this.backdrop.dispose();
    this.backdrop = tex;
    this.scene.background = tex;
    this.fitBackdrop();
  }

  fitBackdrop() {
    const t = this.backdrop;
    if (!t) return;
    const { x, y, size } = this.rect;
    const w = window.innerWidth, h = window.innerHeight;
    const SPAN = 4; // the plate covers [-1.5, 2.5] apple squares each way
    const u0 = -x / size, u1 = (w - x) / size;
    const v0 = -y / size, v1 = (h - y) / size;
    t.repeat.set((u1 - u0) / SPAN, (v1 - v0) / SPAN);
    t.offset.set((u0 + 1.5) / SPAN, 1 - (v1 + 1.5) / SPAN);
    t.needsUpdate = true;
    this.dirty = true;
  }

  // Where the apple should sit on the page (CSS px). The canvas fills the
  // window; the camera's view is offset so the apple lands in that square.
  layout(rect) {
    this.rect = rect;
    const w = window.innerWidth, h = window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = 1;
    this.camera.setViewOffset(rect.size, rect.size, -rect.x, -rect.y, w, h);
    this.camera.updateProjectionMatrix();
    this.fitBackdrop();
    this.dirty = true;
  }

  set angle(rad) {
    if (this.pivot.rotation.y !== rad) { this.pivot.rotation.y = rad; this.dirty = true; }
  }

  render() {
    const q = this.squash;
    const sx = 1 + 0.03 * q, sy = 1 - 0.035 * q;
    const g = this.ground ?? -0.86;
    if (this.pivot.scale.y !== sy) {
      this.pivot.scale.set(sx, sy, sx);
      this.pivot.position.y = g - g * sy; // squash toward the base
      this.dirty = true;
    }
    if (!this.dirty) return;
    this.renderer.render(this.scene, this.camera);
    this.dirty = false;
  }
}
