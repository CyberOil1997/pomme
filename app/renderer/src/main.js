/* Pomme: a crystal apple pomodoro.
 * The apple is the real Blender model, rendered live so it spins smoothly.
 * Each 20% of a focus session takes a bite. */
import { Apple3D } from './apple3d.js';
import { SoundKit } from './sound.js';

// Azimuth of each bite in the Blender scene (degrees), in eating order.
// (first new bite of each stage; the last stage is the core)
const BITE_AZ = [-8, 112, 232, 22, 82];
// Turn the newest bite to a three-quarter view so you can see it.
const VIEW_AZ = -35;
const RAD = Math.PI / 180;

const $ = (s) => document.querySelector(s);
const body = document.body;

/* ---------------- settings ---------------- */
const DEFAULTS = {
  focus: 25, short: 5, long: 15, rounds: 4,
  autoBreak: true, autoFocus: false,
  sound: true, volume: 0.7, apple: 'red',
};
let settings = { ...DEFAULTS };
try {
  const saved = localStorage.getItem('pomme.settings') || '{}';
  settings = { ...DEFAULTS, ...JSON.parse(saved) };
} catch {}
const save = () => { try { localStorage.setItem('pomme.settings', JSON.stringify(settings)); } catch {} };

/* ---------------- sound ---------------- */
const sound = new SoundKit();
const syncSound = () => { sound.enabled = settings.sound; sound.volume = settings.volume; };
syncSound();

/* ---------------- the apple ---------------- */
const canvas = $('#apple');
const apple = new Apple3D(canvas);
const wrap = $('#appleWrap');

const view = {
  angle: 0,          // radians
  velocity: 0,       // radians per ms
  dragging: false,
  stage: 0,
  squash: 0,         // little "chomp" pulse
  target: null,      // spring target angle when turning to show a bite
};

function layoutApple() {
  const r = wrap.getBoundingClientRect();
  apple.layout({ x: r.left, y: r.top, size: r.width });
}
window.addEventListener('resize', layoutApple);

function paperColor() {
  return getComputedStyle(body).getPropertyValue('--paper').trim();
}

/* ---------------- spinning ---------------- */
let last = { x: 0, t: 0 };
let downAt = { x: 0, t: 0 };
const RAD_PER_PX = 0.0125;

wrap.addEventListener('pointerdown', (e) => {
  if (view.dragging) return; // ignore a second finger
  wrap.setPointerCapture(e.pointerId);
  view.dragging = true;
  view.velocity = 0;
  view.target = null;
  last = { x: e.clientX, t: performance.now() };
  downAt = { ...last };
});
wrap.addEventListener('pointermove', (e) => {
  if (!view.dragging) return;
  const now = performance.now();
  const dx = e.clientX - last.x;
  const dt = Math.max(1, now - last.t);
  view.angle += dx * RAD_PER_PX;
  view.velocity = 0.8 * (dx * RAD_PER_PX / dt) + 0.2 * view.velocity;
  last = { x: e.clientX, t: now };
});
function endDrag(e) {
  if (!view.dragging) return;
  view.dragging = false;
  const moved = Math.abs(e.clientX - downAt.x);
  if (performance.now() - last.t > 80) view.velocity = 0; // held still before letting go
  if (moved < 4 && performance.now() - downAt.t < 300) {
    sound.clink(); // a tap rings the glass
    view.squash = 0.6;
  } else if (Math.abs(view.velocity) > 0.004) {
    sound.spin(Math.min(1, Math.abs(view.velocity) * 120));
  }
}
wrap.addEventListener('pointerup', endDrag);
wrap.addEventListener('pointercancel', endDrag);

function turnToBite(stage) {
  if (stage < 1) return;
  let want = (VIEW_AZ - BITE_AZ[stage - 1]) * RAD;
  // shortest way round from where we are
  const cur = view.angle, TAU = Math.PI * 2;
  want = cur + ((((want - cur) % TAU) + TAU * 1.5) % TAU) - Math.PI;
  view.target = want;
  view.velocity = 0;
}

function setStage(stage, { chomp = false } = {}) {
  if (stage === view.stage) return;
  view.stage = stage;
  apple.setStage(stage);
  if (chomp && stage > 0) {
    view.squash = 1;
    sound.bite(stage);
  }
  renderBites();
}

/* ---------------- animation loop ---------------- */
let prevT = performance.now();
function frame(now) {
  const dt = Math.min(48, now - prevT);
  prevT = now;
  if (!view.dragging) {
    if (view.target !== null) {
      // critically damped spring toward the bite
      const k = 0.00004, d = 2 * Math.sqrt(k);
      const x = view.angle - view.target;
      view.velocity += (-k * x - d * view.velocity) * dt;
      view.angle += view.velocity * dt;
      if (Math.abs(x) < 0.001 && Math.abs(view.velocity) < 0.00002) {
        view.angle = view.target; view.target = null; view.velocity = 0;
      }
    } else {
      view.angle += view.velocity * dt;
      view.velocity *= Math.pow(0.996, dt); // glassy, long glide
      if (Math.abs(view.velocity) < 0.00004) view.velocity = 0;
      // a slow idle drift while on a break
      if (state.mode !== 'focus' && state.running && view.velocity === 0) view.angle += dt * 0.00012;
    }
  }
  if (view.squash > 0) view.squash = Math.max(0, view.squash - dt / 260);
  apple.angle = view.angle;
  apple.squash = view.squash;
  tick(now);
  apple.render();
  requestAnimationFrame(frame);
}

/* ---------------- timer ---------------- */
const state = {
  mode: 'focus',
  running: false,
  endAt: 0,
  remaining: settings.focus * 60000,
  round: 1,
};
const durationOf = (m) => settings[m] * 60000;

function fmt(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(total / 60), s = total % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function currentRemaining() {
  return state.running ? Math.max(0, state.endAt - Date.now()) : state.remaining;
}

function progress() {
  return 1 - currentRemaining() / durationOf(state.mode);
}

function stageForProgress(p) {
  return Math.max(0, Math.min(5, Math.floor(p * 5 + 1e-6)));
}

let lastShown = '';
let lastTray = '';
function tick() {
  const rem = currentRemaining();
  const txt = fmt(rem);
  if (txt !== lastShown) {
    $('#time').textContent = txt;
    lastShown = txt;
    document.title = state.running ? `${txt} · Pomme` : 'Pomme';
  }
  const tray = state.running ? `🍎 ${txt}` : (state.remaining < durationOf(state.mode) ? `⏸ ${txt}` : '🍎');
  if (tray !== lastTray && window.pomme) { window.pomme.setTrayTitle(tray); lastTray = tray; }

  if (state.mode === 'focus') {
    const want = stageForProgress(progress());
    if (want > view.stage && want < 5) {
      setStage(want, { chomp: true });
      turnToBite(want);
      setCaption(captionFor());
    }
    renderBites();
  }
  if (state.running && rem <= 0) complete();
}

function renderBites() {
  const p = state.mode === 'focus' ? progress() : 0;
  document.querySelectorAll('#bites i').forEach((el, i) => {
    const fill = Math.max(0, Math.min(1, p * 5 - i));
    el.style.setProperty('--fill', fill.toFixed(3));
  });
}

function setCaption(text) {
  const el = $('#caption');
  if (el.textContent === text) return;
  el.classList.add('swap');
  setTimeout(() => { el.textContent = text; el.classList.remove('swap'); }, 160);
}

function captionFor() {
  const fresh = !state.running && state.remaining === durationOf(state.mode);
  if (state.mode === 'focus') {
    if (fresh) return 'work time. eat it down to the core';
    if (!state.running) return 'paused';
    const left = 5 - view.stage;
    if (view.stage === 0) return 'first bite soon';
    return left === 1 ? 'one more bite to the core' : `${left} bites to the core`;
  }
  if (fresh) return state.mode === 'short' ? `short break. ${settings.short} min off, no work` : `long break. ${settings.long} min off, no work`;
  return state.running ? 'on a break. step away' : 'paused';
}

function updateUI() {
  $('#startLabel').textContent = state.running ? 'Pause' : (state.remaining < durationOf(state.mode) ? 'Resume' : 'Start');
  $('#round').textContent = `round ${state.round} of ${settings.rounds}`;
  setCaption(captionFor());
  document.querySelectorAll('#modes button').forEach((b, i) => {
    const on = b.dataset.mode === state.mode;
    b.setAttribute('aria-selected', on);
    if (on) $('#segIndicator').style.transform = `translateX(${i * 100}%)`;
  });
  body.dataset.mode = state.mode;
}

function start() {
  if (state.running || state.remaining <= 0) return;
  state.endAt = Date.now() + state.remaining;
  state.running = true;
  updateUI();
}
function pause() {
  if (!state.running) return;
  state.remaining = Math.max(0, state.endAt - Date.now());
  state.running = false;
  updateUI();
}
function setMode(mode, { autoStart = false } = {}) {
  state.mode = mode;
  state.running = false;
  state.remaining = durationOf(mode);
  // focus starts with a whole apple; breaks show a fresh one too
  setStage(0);
  view.target = null;
  updateUI();
  if (autoStart) start();
}
function reset() {
  state.running = false;
  state.remaining = durationOf(state.mode);
  setStage(0);
  updateUI();
}

function complete() {
  state.running = false;
  state.remaining = 0;
  $('#startLabel').textContent = 'Start';
  if (state.mode === 'focus') {
    setStage(5, { chomp: true });
    turnToBite(5);
    setTimeout(() => sound.finish(), 420);
    window.pomme?.notify('Apple finished 🍎', 'Nice focus. Time for a break.');
    const longNext = state.round % settings.rounds === 0;
    setCaption('down to the core. nice work');
    // let the last bite land before the new apple appears
    setTimeout(() => {
      setMode(longNext ? 'long' : 'short', { autoStart: settings.autoBreak });
    }, 2600);
  } else {
    sound.ready();
    window.pomme?.notify('Break over', 'A fresh apple is ready.');
    state.round = state.mode === 'long' ? 1 : state.round + 1;
    setMode('focus', { autoStart: settings.autoFocus });
  }
}

function skip() {
  if (state.mode === 'focus') {
    const longNext = state.round % settings.rounds === 0;
    setMode(longNext ? 'long' : 'short');
  } else {
    state.round = state.mode === 'long' ? 1 : state.round + 1;
    setMode('focus');
  }
}

/* ---------------- controls ---------------- */
function swapLabel() {
  const l = $('#startLabel');
  l.classList.add('swap');
  requestAnimationFrame(() => requestAnimationFrame(() => l.classList.remove('swap')));
}
$('#startBtn').addEventListener('click', () => {
  state.running ? sound.pause() : sound.start();
  swapLabel();
  state.running ? pause() : start();
});
$('#resetBtn').addEventListener('click', () => { sound.tap(); reset(); });
$('#skipBtn').addEventListener('click', () => { sound.tap(); skip(); });
document.querySelectorAll('#modes button').forEach((b) =>
  b.addEventListener('click', () => {
    if (b.dataset.mode === state.mode) return;
    sound.tab(['focus', 'short', 'long'].indexOf(b.dataset.mode));
    setMode(b.dataset.mode);
  }));

// keyboard: no animation, just do it
window.addEventListener('keydown', (e) => {
  if (body.classList.contains('sheet-open')) { if (e.key === 'Escape') closeSheet(); return; }
  if (e.code === 'Space') { e.preventDefault(); state.running ? pause() : start(); }
  else if (e.key === 'r') reset();
  else if (e.key === 's') skip();
  else if (e.key === '1') setMode('focus');
  else if (e.key === '2') setMode('short');
  else if (e.key === '3') setMode('long');
});
window.pomme?.onToggle(() => (state.running ? pause() : start()));

/* apple colour */
function applyApple(color) {
  settings.apple = color;
  save();
  body.dataset.apple = color;
  document.querySelectorAll('.swatch').forEach((s) => s.setAttribute('aria-checked', s.dataset.apple === color));
  apple.tint(color);
  apple.setBackground(paperColor());
  apple.setBackdrop(color);
}
document.querySelectorAll('.swatch').forEach((s) =>
  s.addEventListener('click', () => {
    if (s.dataset.apple === settings.apple) return;
    sound.clink();
    applyApple(s.dataset.apple);
  }));

/* sound toggle */
function applySound() { body.classList.toggle('muted', !settings.sound); }
$('#soundBtn').addEventListener('click', () => {
  settings.sound = !settings.sound;
  save();
  applySound();
  syncSound();
  sound.toggle(settings.sound);
});

/* settings sheet */
function fillAbout() {
  document.querySelectorAll('[data-about]').forEach((el) => { el.textContent = settings[el.dataset.about]; });
}
function openSheet() { body.classList.add('sheet-open'); $('#sheet').setAttribute('aria-hidden', 'false'); }
function closeSheet() { body.classList.remove('sheet-open'); $('#sheet').setAttribute('aria-hidden', 'true'); }
$('#settingsBtn').addEventListener('click', () => { sound.sheet(true); openSheet(); });
$('#doneBtn').addEventListener('click', () => { sound.sheet(false); closeSheet(); });
$('#scrim').addEventListener('click', () => { sound.sheet(false); closeSheet(); });

document.querySelectorAll('.stepper').forEach((el) => {
  const key = el.dataset.key;
  const min = +el.dataset.min, max = +el.dataset.max, unit = el.dataset.unit;
  el.innerHTML = `<button aria-label="less">−</button><output></output><button aria-label="more">+</button>`;
  const out = el.querySelector('output');
  const show = () => { fillAbout(); out.innerHTML = `${settings[key]}${unit ? `<small>${unit}</small>` : ''}`; };
  const change = (d) => {
    const v = Math.max(min, Math.min(max, settings[key] + d));
    if (v === settings[key]) return;
    settings[key] = v;
    save();
    show();
    sound.step(d);
    // update an idle timer right away
    if (!state.running && key === state.mode) state.remaining = durationOf(state.mode);
    updateUI();
  };
  const [less, more] = el.querySelectorAll('button');
  less.addEventListener('click', () => change(-1));
  more.addEventListener('click', () => change(1));
  show();
});
document.querySelectorAll('.switch').forEach((sw) => {
  const key = sw.dataset.key;
  sw.setAttribute('aria-checked', settings[key]);
  sw.addEventListener('click', () => {
    settings[key] = !settings[key];
    sw.setAttribute('aria-checked', settings[key]);
    save();
    sound.toggle(settings[key]);
  });
});
const vol = $('#volume');
vol.value = settings.volume;
vol.addEventListener('input', () => { settings.volume = +vol.value; save(); syncSound(); });
vol.addEventListener('change', () => sound.clink());

/* ---------------- boot ---------------- */
applyApple(settings.apple);
applySound();
layoutApple();
updateUI();
apple.load(() => $('#loading').classList.add('hidden'));
requestAnimationFrame(frame);
window.__pomme = { state };
