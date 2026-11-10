"""Pomme crystal apple scene.

Builds a glass apple (gold stem, glass leaf), carves human-style bites with
boolean cutters, and renders a turntable for each bite stage.

Usage:
  blender -b -P apple.py -- --color red --stages 0,1,2,3,4,5 --frames 48 \
      --res 640 --samples 96 --out ../renders
  blender -b -P apple.py -- --mode icon --out ../renders
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--color", default="red")
ap.add_argument("--stages", default="0")
ap.add_argument("--frames", type=int, default=1)
ap.add_argument("--res", type=int, default=640)
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--out", default="renders")
ap.add_argument("--mode", default="turntable")  # turntable | icon | export
ap.add_argument("--save-blend", default="")
ap.add_argument("--scallop", type=int, default=0)
ap.add_argument("--flesh", default="crystal")
args = ap.parse_args(argv)
OUT = os.path.abspath(args.out)

COLORS = {
    "red": dict(flesh=(1.0, 0.90, 0.74), glass=(1.0, 0.30, 0.30),
                absorb=(1.0, 0.22, 0.20), density=1.9),
    "green": dict(flesh=(0.98, 0.95, 0.74), glass=(0.55, 1.0, 0.45),
                  absorb=(0.40, 1.0, 0.28), density=1.8),
}

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials


def principled(name, base, rough=0.0, metal=0.0, transmission=0.0, ior=1.5,
               coat=0.0, absorb=None, density=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Coat Weight"].default_value = coat
    if absorb is not None:
        vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
        vol.inputs["Color"].default_value = (*absorb, 1)
        vol.inputs["Density"].default_value = density
        out = nt.nodes["Material Output"]
        nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


c = COLORS[args.color]


def add_flesh_bump(m):
    nt = m.node_tree
    tc2 = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.18)
    nt.links.new(tc2.outputs["Object"], mp.inputs["Vector"])
    tex = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(mp.outputs[0], tex.inputs["Vector"])
    tex.inputs["Scale"].default_value = 22
    tex.inputs["Detail"].default_value = 6
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.02
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
mat_glass = principled("Glass", c["glass"], rough=0.0, transmission=1.0,
                       ior=1.62, absorb=c["absorb"], density=c["density"])
# bitten flesh: milky white frosted crystal, like the inside of an apple
mat_cut = principled("GlassCut", (0.97, 0.95, 0.92), rough=0.45, transmission=0.35,
                     ior=1.5)
add_flesh_bump(mat_cut)
mat_gold = principled("Gold", (1.0, 0.74, 0.38), rough=0.16, metal=1.0)
mat_leaf = principled("Leaf", (0.42, 0.9, 0.3), rough=0.02, transmission=1.0,
                      ior=1.5, absorb=(0.35, 0.9, 0.2), density=2.5)

# ---------------------------------------------------------------- apple body
# Half silhouette (radius, height), from the top dimple to the bottom dimple.
PROFILE = [
    (0.00, 0.52), (0.10, 0.58), (0.24, 0.74), (0.44, 0.85), (0.64, 0.84),
    (0.81, 0.74), (0.93, 0.56), (1.00, 0.32), (1.02, 0.08), (0.98, -0.17),
    (0.89, -0.41), (0.76, -0.62), (0.59, -0.79), (0.41, -0.90), (0.24, -0.94),
    (0.12, -0.91), (0.00, -0.86),
]


def catmull(points, per_seg=8):
    pts = [points[0]] + points + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (Vector(p) for p in pts[i - 1:i + 3])
        for s in range(per_seg):
            t = s / per_seg
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t +
                              (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(Vector(points[-1]))
    return out


def build_apple():
    prof = catmull(PROFILE, 10)
    seg = 160
    verts, faces = [], []
    top = len(verts)
    verts.append((0, 0, prof[0].y))
    rings = []
    for p in prof[1:-1]:
        ring = []
        for j in range(seg):
            th = 2 * math.pi * j / seg
            r = p.x
            # soft lobes toward the base, and a slight asymmetry
            lobe = 0.022 * math.cos(5 * th) * max(0.0, min(1.0, (0.2 - p.y) * 1.4))
            r *= 1 + lobe + 0.015 * math.cos(th - 0.6)
            ring.append(len(verts))
            verts.append((r * math.cos(th), r * math.sin(th), p.y))
        rings.append(ring)
    bot = len(verts)
    verts.append((0, 0, prof[-1].y))
    for j in range(seg):
        faces.append((top, rings[0][(j + 1) % seg], rings[0][j]))
    for a, b in zip(rings, rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            faces.append((a[j], a[k], b[k], b[j]))
    for j in range(seg):
        faces.append((bot, rings[-1][j], rings[-1][(j + 1) % seg]))
    me = bpy.data.meshes.new("Apple")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new("Apple", me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat_glass)
    ob.data.materials.append(mat_cut)
    for poly in me.polygons:
        poly.use_smooth = True
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier="sub")
    return ob


apple = build_apple()

# ---------------------------------------------------------------- stem + leaf
def build_stem():
    cu = bpy.data.curves.new("Stem", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.034
    cu.bevel_resolution = 6
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(2)
    pts = [(0, 0, 0.46), (0.03, 0.0, 0.92), (0.16, 0.0, 1.20)]
    for bp, co in zip(sp.bezier_points, pts):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.bezier_points[0].radius = 1.15
    sp.bezier_points[1].radius = 0.9
    sp.bezier_points[2].radius = 0.75
    cu.use_fill_caps = True
    ob = bpy.data.objects.new("Stem", cu)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat_gold)
    return ob


def build_leaf():
    nu, nv = 40, 14
    L = 0.78
    verts, faces = [], []
    for i in range(nu + 1):
        u = i / nu
        w = 0.27 * math.sin(math.pi * u ** 0.75) * (1 - 0.15 * u)
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            x = u * L
            y = v * w
            # fold along the midrib and curl down toward the tip
            z = 0.10 * abs(v) * w * 4 - 0.12 * u * u
            verts.append((x, y, z))
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    me = bpy.data.meshes.new("Leaf")
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new("Leaf", me)
    scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    sol = ob.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.03
    sol.offset = 0
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    ob.data.materials.append(mat_leaf)
    ob.location = (0.04, -0.02, 0.84)
    ob.rotation_euler = (math.radians(-15), math.radians(-32), math.radians(-40))
    return ob


stem = build_stem()
leaf = build_leaf()

# ---------------------------------------------------------------- bites
# Eaten the way people eat an apple: a ring of bites all the way round,
# then a deeper ring between them, down to the core. Each bite lands on what
# is left (surface_frame ray-casts the current mesh), so the second ring
# goes deeper. Every stage is cut fresh from the whole apple in one boolean. (azimuth deg, height, tilt deg, depth, half-height)
BITES = [
    (-8, 0.08, 6, 0.42, 0.47), (52, -0.04, -6, 0.42, 0.47),        # stage 1
    (112, 0.06, 5, 0.42, 0.47), (172, -0.02, -4, 0.42, 0.47),      # stage 2
    (232, 0.05, 6, 0.42, 0.47), (292, -0.03, -5, 0.42, 0.47),      # stage 3
    (22, 0.02, 3, 0.82, 0.56), (142, 0.0, -3, 0.82, 0.56), (262, 0.02, 4, 0.82, 0.56),   # stage 4
    (82, 0.0, -4, 0.82, 0.56), (202, 0.02, 3, 0.82, 0.56), (322, 0.0, -3, 0.82, 0.56),   # stage 5
]
# how many bites have been taken at each stage
STAGE_BITES = [0, 2, 4, 6, 9, 12]


def surface_frame(az, h):
    """Ray-cast toward the apple axis to find the surface point + normal."""
    d = Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0))
    origin = d * 3 + Vector((0, 0, h))
    hit, loc, nrm, _ = apple.ray_cast(origin, -d)
    assert hit, f"bite ray missed at {az},{h}"
    z = nrm.normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    y = z.cross(x)
    return loc, Matrix((x, y, z)).transposed()


# --- human bite -----------------------------------------------------------
# Scale: 1 unit = ~4 cm (apple is ~8 cm wide). Real front-teeth widths:
# central incisor 8.5 mm, lateral 6.5 mm, canine 7.5 mm; upper arch is ~35 mm
# wide at the canines. Lower teeth are narrower and sit behind the uppers.
UPPER = [(0.212, 0.30), (0.162, 0.27), (0.188, 0.30)]   # (width, crown height)
LOWER = [(0.135, 0.26), (0.148, 0.26), (0.170, 0.28)]


def arch_points(teeth, depth, k):
    """Place teeth along a parabolic arch z = -depth + k x^2 (local frame:
    x across the mouth, y up, z out of the apple). Returns (x, z, angle, w)."""
    out = []
    for side in (1, -1):
        s_along = 0.0
        x = 0.0
        for w, _ in teeth:
            # walk along the arch by half a tooth, place it, walk the other half
            for _ in range(2):
                step = w / 2
                while step > 1e-4:
                    dx = min(step, 0.01)
                    slope = 2 * k * x
                    ds = dx * math.sqrt(1 + slope * slope)
                    x += dx * (step / max(step, ds)) if ds > step else dx
                    step -= ds
                if _ == 0:
                    ang = math.atan(2 * k * x)
                    out.append((side * x, -depth + k * x * x, side * ang, w))
    return out


def add_ellipsoid(col, mat_world, loc, scale, rot_y=0.0, name="tooth"):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1)
    p = bpy.context.object
    p.data.materials.append(mat_cut)
    for poly in p.data.polygons:
        poly.use_smooth = True
    for c2 in list(p.users_collection):
        c2.objects.unlink(p)
    col.objects.link(p)
    local = Matrix.LocRotScale(Vector(loc), Matrix.Rotation(rot_y, 3, "Y"),
                               Vector(scale))
    p.matrix_world = mat_world @ local
    p.hide_render = True
    p.name = name
    return p


def add_mouth_volume(col, mat_world, depth, k, half_h, name):
    """Everything in front of the arch (inside the mouth) is removed."""
    pts = []
    for i in range(41):
        x = -0.62 + 1.24 * i / 40
        pts.append((x, -depth + k * x * x + 0.035))
    pts += [(0.62, 1.2), (-0.62, 1.2)]
    verts = [(x, -half_h, z) for x, z in pts] + [(x, half_h, z) for x, z in pts]
    n = len(pts)
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.data.materials.append(mat_cut)
    ob.matrix_world = mat_world
    ob.hide_render = True
    return ob


def tooth_centres(teeth):
    out, x = [], 0.0
    for w, _ in teeth:
        out.append((x + w / 2, w))
        x += w
    return [(side * c, w) for c, w in out for side in (1, -1)]


def bump(x, centres):
    """1 at a tooth's middle, 0 at its edges: the ridge pattern teeth leave."""
    best = 0.0
    for c, w in centres:
        t = (x - c) / (w / 2)
        if abs(t) < 1:
            best = max(best, math.sqrt(1 - t * t))
    return best


def smoothstep(e0, e1, v):
    t = max(0.0, min(1.0, (v - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def make_bite(idx, az, h, tilt, depth=0.42, H=0.47, k=0.85, ridge=0.0):
    """Bite cutter lofted from a dental arch.

    Seen from above the cut follows the arch (z = -depth + k x^2). Seen from
    the side the jaws close in an arc, so the cut is deepest at the seam and
    meets the skin at the tooth tips. Each tooth presses a faint vertical
    ridge; the lower teeth sit a little behind the uppers (overbite)."""
    loc, rot = surface_frame(az, h)
    rot = rot @ Matrix.Rotation(math.radians(tilt), 3, "Z")
    M = Matrix.Translation(loc) @ rot.to_4x4()
    up, lo = tooth_centres(UPPER), tooth_centres(LOWER)
    nx, ny = 121, 49
    X0 = 0.72
    Hmax = H * 1.08
    front = []
    for j in range(ny):
        y = -Hmax + 2 * Hmax * j / (ny - 1)
        wu = smoothstep(-0.05, 0.05, y)          # 1 on the upper jaw
        row = []
        for i in range(nx):
            x = -X0 + 2 * X0 * i / (nx - 1)
            bu, bl = bump(x, up), bump(x, lo)
            b = wu * bu + (1 - wu) * bl
            Hx = H * (0.985 + 0.02 * b)           # tooth tips make a wavy rim
            f = math.sqrt(max(0.0, 1 - (y / Hx) ** 2))
            d = depth - (1 - wu) * 0.035         # lower jaw sits behind
            z = -(d + ridge * b) * f + k * x * x + 0.02 * (1 - f)
            row.append((x, y, z))
        front.append(row)
    verts, faces = [], []
    idxF = [[0] * nx for _ in range(ny)]
    idxB = [[0] * nx for _ in range(ny)]
    for j in range(ny):
        for i in range(nx):
            idxF[j][i] = len(verts)
            verts.append(front[j][i])
    for j in range(ny):
        for i in range(nx):
            idxB[j][i] = len(verts)
            x, y, _ = front[j][i]
            verts.append((x, y, 1.4))
    for j in range(ny - 1):
        for i in range(nx - 1):
            faces.append((idxF[j][i], idxF[j][i + 1], idxF[j + 1][i + 1], idxF[j + 1][i]))
            faces.append((idxB[j][i], idxB[j + 1][i], idxB[j + 1][i + 1], idxB[j][i + 1]))
    border = ([(0, i) for i in range(nx)] + [(j, nx - 1) for j in range(1, ny)] +
              [(ny - 1, i) for i in range(nx - 2, -1, -1)] +
              [(j, 0) for j in range(ny - 2, 0, -1)])
    for a_, b_ in zip(border, border[1:] + border[:1]):
        faces.append((idxF[a_[0]][a_[1]], idxB[a_[0]][a_[1]],
                      idxB[b_[0]][b_[1]], idxF[b_[0]][b_[1]]))
    me = bpy.data.meshes.new(f"bite{idx}")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(f"bite{idx}", me)
    bpy.data.collections["Cutters"].objects.link(ob)
    ob.data.materials.append(mat_cut)
    ob.matrix_world = M
    ob.hide_render = True


APPLE_WHOLE = None


def apply_bites(n):
    # start from the whole apple each time; chained booleans go hollow
    global APPLE_WHOLE
    if APPLE_WHOLE is None:
        APPLE_WHOLE = apple.data.copy()
    old = apple.data
    apple.data = APPLE_WHOLE.copy()
    if old is not APPLE_WHOLE and old.users == 0:
        bpy.data.meshes.remove(old)
    if n == 0:
        return
    col = bpy.data.collections.new("Cutters")
    scene.collection.children.link(col)
    for i, b in enumerate(BITES[:n]):
        az, h, tilt, depth, H = b
        make_bite(i, az, h, tilt, depth=depth, H=H)
    mod = apple.modifiers.new("bite", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.operand_type = "COLLECTION"
    mod.collection = col
    mod.solver = "EXACT"
    mod.use_self = True
    mod.use_hole_tolerant = True
    mod.material_mode = "TRANSFER"
    with bpy.context.temp_override(object=apple, active_object=apple):
        bpy.ops.object.modifier_apply(modifier="bite")
    with bpy.context.temp_override(selected_editable_objects=[apple],
                                   object=apple, active_object=apple):
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    for ob in list(col.objects):
        bpy.data.objects.remove(ob)
    bpy.data.collections.remove(col)


# ---------------------------------------------------------------- rig
pivot = bpy.data.objects.new("Pivot", None)
scene.collection.objects.link(pivot)
for ob in (apple, stem, leaf):
    ob.parent = pivot

ground_z = min((apple.matrix_world @ v.co).z for v in apple.data.vertices)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, ground_z))
ground = bpy.context.object
ground.is_shadow_catcher = True

# ---------------------------------------------------------------- lights/world
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree
tc = wn.nodes.new("ShaderNodeTexCoord")
sep = wn.nodes.new("ShaderNodeSeparateXYZ")
ramp = wn.nodes.new("ShaderNodeValToRGB")
wn.links.new(tc.outputs["Normal"], sep.inputs[0])
wn.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
cr = ramp.color_ramp
cr.elements[0].position = 0.35
cr.elements[0].color = (0.40, 0.37, 0.39, 1)
cr.elements[1].position = 0.62
cr.elements[1].color = (1.0, 0.98, 0.97, 1)
mid = cr.elements.new(0.5)
mid.color = (0.80, 0.76, 0.77, 1)
bg = wn.nodes["Background"]
bg.inputs["Strength"].default_value = 1.0
wn.links.new(ramp.outputs[0], bg.inputs["Color"])


def area(name, loc, size, energy, color=(1, 1, 1), shape="RECTANGLE",
         size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    ld.shape = shape
    ld.size = size
    if size_y:
        ld.size_y = size_y
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    direction = Vector((0, 0, 0.1)) - Vector(loc)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return ob


# window-like softbox reflections (the bright rectangles on crystal)
area("Key", (-3.2, -3.6, 3.8), 1.2, 900, (1, 0.97, 0.93), size_y=2.4)
area("Fill", (4.0, -2.5, 1.2), 2.5, 160, (0.92, 0.95, 1.0))
area("Rim", (2.0, 4.5, 3.0), 1.0, 700, (1, 0.95, 0.9), size_y=2.0)
area("Top", (0, 0, 5), 2.0, 250)
area("Glow", (0.4, 3.2, 0.1), 1.6, 900, (1.0, 0.78, 0.55))
for sx in (-1, 1):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(sx * 2.4, 0.9, 0.4))
    flag = bpy.context.object
    flag.scale = (3.0, 1.0, 1.0)
    flag.rotation_euler = (0, math.radians(90), 0)
    flag.visible_camera = False
    flag.visible_shadow = False
    flag.data.materials.append(principled("Flag", (0.02, 0.02, 0.02), rough=1.0))

# ---------------------------------------------------------------- render setup
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = "GPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 16
scene.cycles.transmission_bounces = 16
scene.cycles.glossy_bounces = 8
scene.cycles.volume_bounces = 2
scene.cycles.caustics_refractive = True
scene.cycles.caustics_reflective = True
scene.cycles.blur_glossy = 0.5
scene.render.film_transparent = True
scene.cycles.film_transparent_glass = False
scene.cycles.film_transparent_roughness = 0.2
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Punchy"
scene.render.resolution_x = scene.render.resolution_y = args.res
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 70
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, -6.8, 0.95)
target = Vector((0, 0, 0.05))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- render
os.makedirs(OUT, exist_ok=True)
done = 0
if args.mode == "icon":
    # macOS-style tile: a true squircle (|x|^5 + |y|^5 = 1) behind the apple
    ground.hide_render = True
    n = 256
    R = 1.62
    ring = []
    for i in range(n):
        t = 2 * math.pi * i / n
        cx, cy = math.cos(t), math.sin(t)
        x = R * math.copysign(abs(cx) ** 0.4, cx)
        z = R * math.copysign(abs(cy) ** 0.4, cy)
        ring.append((x, 0, z))
    me = bpy.data.meshes.new("Tile")
    me.from_pydata(ring, [], [tuple(range(n))])
    tile = bpy.data.objects.new("Tile", me)
    scene.collection.objects.link(tile)
    sol = tile.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.12
    bev = tile.modifiers.new("bev", "BEVEL")
    bev.width = 0.04
    bev.segments = 6
    bev.limit_method = "ANGLE"
    tile.location = (0, 1.3, 0.17)
    tint = (0.97, 0.86, 0.83) if args.color == "red" else (0.93, 0.94, 0.84)
    tile.data.materials.append(principled("TileMat", tint, rough=0.55))
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2 * R * 1024 / 824
    cam.location = (0, -9, 0.17)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.render.resolution_x = scene.render.resolution_y = 1024
    pivot.rotation_euler = (0, 0, math.radians(12))
    pivot.scale = (0.92, 0.92, 0.92)
    pivot.location = (0, 0, 0.12)
    scene.render.filepath = os.path.join(OUT, f"icon_{args.color}.png")
    bpy.ops.render.render(write_still=True)
elif args.mode == "backdrop":
    # The set behind the apple: a seamless sweep, a round plinth the apple
    # stands on, and late sun through leaves just out of frame. The apple
    # itself is hidden (the app draws it live); this renders a 4x-wide
    # plate from the same camera so the app can line it up exactly.
    import random
    random.seed(7)
    for ob in (apple, stem, leaf, ground):
        ob.hide_render = True
    for ob in scene.objects:
        if ob.type == "LIGHT" or ob.name.startswith("Plane"):
            ob.hide_render = True
    base_z = ground_z
    tones = {
        "red": dict(wall=(0.98, 0.80, 0.75), plinth=(1.0, 0.91, 0.88)),
        "green": dict(wall=(0.88, 0.90, 0.72), plinth=(0.97, 0.97, 0.90)),
    }[args.color]
    # sweep: floor running back into a curved wall
    plinth_h = 0.24
    floor_z = base_z - plinth_h
    prof = []
    for i in range(24):
        y = -12 + 15 * i / 23
        prof.append((y, floor_z))
    R = 2.2
    for i in range(1, 25):
        a_ = (math.pi / 2) * i / 24
        prof.append((3 + R * math.sin(a_), floor_z + R * (1 - math.cos(a_))))
    prof.append((3 + R, floor_z + 14))
    verts, faces = [], []
    for x in (-20, 20):
        for (y, z) in prof:
            verts.append((x, y, z))
    n = len(prof)
    for i in range(n - 1):
        faces.append((i, i + 1, n + i + 1, n + i))
    me = bpy.data.meshes.new("Sweep")
    me.from_pydata(verts, [], faces)
    sweep = bpy.data.objects.new("Sweep", me)
    scene.collection.objects.link(sweep)
    for p_ in me.polygons:
        p_.use_smooth = True
    sweep.data.materials.append(principled("Wall", tones["wall"], rough=0.92))
    # plinth
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=1.55, depth=plinth_h,
                                        location=(0, 0, base_z - plinth_h / 2))
    plinth = bpy.context.object
    bev = plinth.modifiers.new("bev", "BEVEL")
    bev.width = 0.05
    bev.segments = 8
    bpy.ops.object.shade_smooth()
    plinth.data.materials.append(principled("Plinth", tones["plinth"], rough=0.55))
    # warm late sun, a little soft
    sun_d = bpy.data.lights.new("Sun", "SUN")
    sun_d.energy = 6.5
    sun_d.angle = math.radians(3.5)
    sun_d.color = (1.0, 0.86, 0.70)
    sun = bpy.data.objects.new("Sun", sun_d)
    scene.collection.objects.link(sun)
    sun_dir = Vector((-0.75, -1.0, 0.95)).normalized()   # toward the sun
    sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    # soft sky fill so shadows stay airy
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    fill_d = bpy.data.lights.new("SoftFill", "AREA")
    fill_d.energy = 380
    fill_d.size = 8
    fill = bpy.data.objects.new("SoftFill", fill_d)
    scene.collection.objects.link(fill)
    fill.location = (3, -7, 4)
    fill.rotation_euler = (Vector((0, 2, 0)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    # a window out of frame: the sun comes through it, with leaves outside,
    # so a warm window-shaped patch with leaf shadows lands on the wall
    target = Vector((-0.5, 4.95, 1.9))
    perp_x = sun_dir.cross(Vector((0, 0, 1))).normalized()
    perp_y = perp_x.cross(sun_dir).normalized()
    win_c = target + sun_dir * 5.0
    W2, H2, BIG = 1.8, 2.3, 30.0

    def slab(name, x0, x1, y0, y1, mat):
        vs = [win_c + perp_x * x + perp_y * y for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        m = bpy.data.meshes.new(name)
        m.from_pydata([tuple(v) for v in vs], [], [(0, 1, 2, 3)])
        o = bpy.data.objects.new(name, m)
        scene.collection.objects.link(o)
        o.data.materials.append(mat)
        o.visible_camera = False
        o.visible_glossy = False
        return o

    shade = principled("Shade", (0.05, 0.05, 0.05), rough=1.0)
    blockers = [
        slab("wallL", -BIG, -W2, -BIG, BIG, shade), slab("wallR", W2, BIG, -BIG, BIG, shade),
        slab("wallT", -W2, W2, H2, BIG, shade), slab("wallB", -W2, W2, -BIG, -H2, shade),
        slab("mullV", -0.05, 0.05, -H2, H2, shade), slab("mullH", -W2, W2, 0.15, 0.25, shade),
    ]
    leaf_mat = principled("LeafShade", (0.1, 0.1, 0.1), rough=1.0)
    branches = [((-2.4, 2.6), (1.2, 0.4)), ((2.2, 2.4), (-0.6, -0.8)), ((-1.8, -2.6), (0.9, -0.2))]
    k = 0
    for (sx, sy), (ex, ey) in branches:
        for t in [i / 26 for i in range(27)]:
            bx = sx + (ex - sx) * t + 0.25 * math.sin(t * 7)
            by = sy + (ey - sy) * t + 0.2 * math.cos(t * 5)
            for side in (-1, 1):
                if random.random() < 0.25:
                    continue
                L = random.uniform(0.35, 0.6)
                lv, lf = [], []
                nu = 14
                for i in range(nu + 1):
                    u = i / nu
                    w = 0.34 * L * math.sin(math.pi * u ** 0.8)
                    lv += [(u * L, -w, 0), (u * L, w, 0)]
                for i in range(nu):
                    lf.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
                lme = bpy.data.meshes.new(f"gobo{k}")
                lme.from_pydata(lv, [], lf)
                lob = bpy.data.objects.new(f"gobo{k}", lme)
                scene.collection.objects.link(lob)
                lob.data.materials.append(leaf_mat)
                base = win_c + sun_dir * random.uniform(1.2, 2.2) + perp_x * bx + perp_y * by
                lob.location = base
                ang = math.atan2(ey - sy, ex - sx) + side * random.uniform(0.6, 1.1)
                rot = Matrix.Rotation(ang, 3, sun_dir) @ Vector(perp_x).to_track_quat("X", "Z").to_matrix()
                lob.rotation_euler = rot.to_euler()
                lob.rotation_euler.x += random.uniform(-0.4, 0.4)
                lob.visible_camera = False
                lob.visible_glossy = False
                k += 1
        # the twig itself
        cu = bpy.data.curves.new(f"twig{k}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.025
        sp = cu.splines.new("POLY")
        pts = []
        for t in [i / 12 for i in range(13)]:
            bx = sx + (ex - sx) * t + 0.25 * math.sin(t * 7)
            by = sy + (ey - sy) * t + 0.2 * math.cos(t * 5)
            pts.append(win_c + sun_dir * 1.7 + perp_x * bx + perp_y * by)
        sp.points.add(len(pts) - 1)
        for pt, v in zip(sp.points, pts):
            pt.co = (*v, 1)
        tw = bpy.data.objects.new(f"twig{k}", cu)
        scene.collection.objects.link(tw)
        tw.visible_camera = False
        tw.visible_glossy = False
    # the window wall and leaves only shade the sun, not the soft room light
    sun_block = bpy.data.collections.new("SunBlockers")
    for o in scene.objects:
        if o.name.startswith(("wall", "mull", "gobo", "twig")) or o in (plinth, sweep):
            sun_block.objects.link(o)
    sun.light_linking.blocker_collection = sun_block
    fill_block = bpy.data.collections.new("FillBlockers")
    fill_block.objects.link(plinth)
    fill_block.objects.link(sweep)
    fill.light_linking.blocker_collection = fill_block
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    fill_d.energy = 900
    # thin twigs tie the leaves into branches
    # camera: same eye, 4x the frame
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36 * 4
    scene.render.resolution_x = scene.render.resolution_y = args.res
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"
    scene.view_settings.exposure = 0.55
    scene.cycles.caustics_refractive = False
    scene.cycles.caustics_reflective = False
    scene.render.filepath = os.path.join(OUT, f"backdrop_{args.color}.png")
    bpy.ops.render.render(write_still=True)
elif args.mode == "export":
    # Real-time assets: one GLB per bite stage, the studio as an HDR, the shadow.
    for ob in (apple, stem, leaf):
        mw = ob.matrix_world.copy()
        ob.parent = None
        ob.matrix_world = mw
    for ob in (stem, leaf):
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob,
                                       selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.convert(target="MESH")
    stem = bpy.data.objects["Stem"]
    leaf = bpy.data.objects["Leaf"]
    # shadow: top-down shadow catcher only
    scene.render.resolution_x = scene.render.resolution_y = 512
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 4.0
    cam.location = (0, 0, 10)
    cam.rotation_euler = (0, 0, 0)
    for ob in (apple, stem, leaf):
        ob.visible_camera = False
    scene.render.filepath = os.path.join(OUT, "shadow.png")
    bpy.ops.render.render(write_still=True)
    for ob in (apple, stem, leaf):
        ob.visible_camera = True
    # environment: what the glass sees, as an equirect panorama. No black
    # flags (they read as black rectangles); the key is a four-pane window
    # and the other lights are round, so reflections look like a sunny room.
    ground.hide_render = True
    for ob in scene.objects:
        if ob.name.startswith("Plane") and ob is not ground:
            ob.hide_render = True
    glow = bpy.data.materials.new("WindowGlow")
    glow.use_nodes = True
    gn = glow.node_tree.nodes
    gn.remove(gn["Principled BSDF"])
    em = gn.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 6.0
    em.inputs["Color"].default_value = (1.0, 0.95, 0.88, 1)
    glow.node_tree.links.new(em.outputs[0], gn["Material Output"].inputs["Surface"])
    key = scene.objects["Key"]
    kd = (Vector((0, 0, 0.1)) - key.location).normalized()
    px = kd.cross(Vector((0, 0, 1))).normalized()
    py = px.cross(kd).normalized()
    for i, (cx, cy) in enumerate(((-0.34, 0.62), (0.34, 0.62), (-0.34, -0.62), (0.34, -0.62))):
        vs = [key.location + px * (cx + dx) + py * (cy + dy)
              for dx, dy in ((-0.31, -0.58), (0.31, -0.58), (0.31, 0.58), (-0.31, 0.58))]
        m = bpy.data.meshes.new(f"pane{i}")
        m.from_pydata([tuple(v) for v in vs], [], [(0, 1, 2, 3)])
        o = bpy.data.objects.new(f"pane{i}", m)
        scene.collection.objects.link(o)
        o.data.materials.append(glow)
    for name, r in (("Top", 1.0), ("Rim", 0.55), ("Fill", 0.9)):
        L_ = scene.objects[name]
        bpy.ops.mesh.primitive_circle_add(vertices=64, radius=r, fill_type="NGON", location=L_.location)
        d = bpy.context.object
        d.rotation_euler = (Vector((0, 0, 0.1)) - L_.location).to_track_quat("-Z", "Y").to_euler()
        d.data.materials.append(glow)
    scene.objects["Glow"].visible_camera = True
    # a deeper room tone where the flags were, so the glass keeps its edges
    cr.elements[0].color = (0.22, 0.19, 0.21, 1)
    mid.color = (0.62, 0.57, 0.58, 1)
    for ob in (apple, stem, leaf):
        ob.hide_render = True
    cam_data.type = "PANO"
    cam_data.panorama_type = "EQUIRECTANGULAR"
    cam.location = (0, 0, 0.1)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.resolution_x, scene.render.resolution_y = 2048, 1024
    scene.render.image_settings.file_format = "HDR"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = os.path.join(OUT, "studio.hdr")
    bpy.ops.render.render(write_still=True)
    for ob in (apple, stem, leaf):
        ob.hide_render = False
    print("[pomme] material names:", [m.name for m in bpy.data.materials], flush=True)

    def export(name):
        bpy.ops.object.select_all(action="DESELECT")
        for ob in (apple, stem, leaf):
            ob.select_set(True)
        bpy.context.view_layer.objects.active = apple
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name), export_format="GLB",
                                  use_selection=True, export_apply=True, export_yup=True,
                                  export_cameras=False, export_lights=False)
    export("s0.glb")
    for st in range(1, 6):
        apply_bites(STAGE_BITES[st])
        export(f"s{st}.glb")
        print(f"[pomme] exported stage {st}", flush=True)
else:
    stages = [int(s) for s in args.stages.split(",")]
    for st in sorted(stages):
        # bites accumulate: rebuild cutters for the delta only
        if st != done:
            apply_bites(STAGE_BITES[st])
            done = st
        d = os.path.join(OUT, args.color, f"s{st}")
        os.makedirs(d, exist_ok=True)
        for f in range(args.frames):
            pivot.rotation_euler = (0, 0, 2 * math.pi * f / args.frames)
            scene.render.filepath = os.path.join(d, f"{f:03d}.png")
            bpy.ops.render.render(write_still=True)
        print(f"[pomme] {args.color} stage {st} done", flush=True)

if args.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save_blend))
