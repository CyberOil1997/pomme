// Pomme's sound kit, synthesized with WebAudio so every cue shares one key
// (C major pentatonic) and one soft, rounded timbre. Principles:
//  - short: controls are 40-150 ms, only celebrations ring longer
//  - rising pitch means "go / good", falling means "stop / undo"
//  - tiny pitch jitter so repeated presses never sound canned
//  - quiet by default, one compressor so nothing pokes out
// The apple crunch is the one recorded sound (assets/sounds/bite.mp3).

const NOTE = (n) => 440 * Math.pow(2, (n - 69) / 12); // midi -> Hz
const C5 = 72;
const PENTA = [0, 2, 4, 7, 9, 12, 14, 16];

export class SoundKit {
  constructor() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.volume = 0.7;
    this.enabled = true;
    const c = this.ctx;
    this.comp = c.createDynamicsCompressor();
    this.comp.threshold.value = -16;
    this.comp.ratio.value = 3;
    this.comp.attack.value = 0.002;
    this.comp.release.value = 0.12;
    this.master = c.createGain();
    this.master.connect(this.comp).connect(c.destination);
    // a small, bright room so tones have a little air around them
    this.verb = c.createConvolver();
    this.verb.buffer = this.makeRoom(0.9);
    this.verbSend = c.createGain();
    this.verbSend.gain.value = 0.16;
    this.verbSend.connect(this.verb).connect(this.master);
    this.buffers = {};
    this.loadSample('bite', '../assets/sounds/bite.mp3');
  }

  makeRoom(seconds) {
    const c = this.ctx, len = Math.floor(c.sampleRate * seconds);
    const buf = c.createBuffer(2, len, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.2);
    }
    return buf;
  }

  async loadSample(name, url) {
    try {
      const res = await fetch(url);
      this.buffers[name] = await this.ctx.decodeAudioData(await res.arrayBuffer());
    } catch (e) { console.warn('sound', name, e); }
  }

  get ok() {
    if (!this.enabled || this.volume <= 0) return false;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return true;
  }

  out(gain, wet = true) {
    const g = this.ctx.createGain();
    g.gain.value = gain * this.volume;
    g.connect(this.master);
    if (wet) g.connect(this.verbSend);
    return g;
  }

  jitter(amount = 0.015) { return 1 + (Math.random() * 2 - 1) * amount; }

  // a single voice: oscillator with a fast attack and exponential decay
  voice(dest, { freq, type = 'sine', t = 0, attack = 0.004, decay = 0.2, gain = 1, glide = 0 }) {
    const c = this.ctx, at = c.currentTime + t;
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, at);
    if (glide) o.frequency.exponentialRampToValueAtTime(freq * glide, at + Math.min(0.08, decay));
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(gain, at + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
    o.connect(g).connect(dest);
    o.start(at);
    o.stop(at + attack + decay + 0.05);
  }

  // marimba-ish: fundamental plus the bar's 4x and ~10x partials, which die fast
  mallet(dest, freq, t = 0, gain = 1, decay = 0.45) {
    this.voice(dest, { freq, t, decay, gain });
    this.voice(dest, { freq: freq * 3.99, t, decay: decay * 0.22, gain: gain * 0.22 });
    this.voice(dest, { freq: freq * 9.9, t, decay: decay * 0.06, gain: gain * 0.08 });
  }

  // glass/bell: inharmonic partials with a long shimmer
  bell(dest, freq, t = 0, gain = 1, decay = 1.1) {
    this.voice(dest, { freq, t, decay, gain });
    this.voice(dest, { freq: freq * 2.76, t, decay: decay * 0.5, gain: gain * 0.3 });
    this.voice(dest, { freq: freq * 5.4, t, decay: decay * 0.25, gain: gain * 0.12 });
    this.voice(dest, { freq: freq * 1.003, t, decay, gain: gain * 0.5 }); // slow beating
  }

  /* ---- the cues ---- */

  // Start: a round "bloop" that slides up. Pause: the same, sliding down.
  start() {
    if (!this.ok) return;
    const d = this.out(0.5);
    const f = NOTE(C5 + 7) * this.jitter();
    this.voice(d, { freq: f * 0.75, decay: 0.12, gain: 0.9, glide: 1.34 });
    this.mallet(d, f * 1.5, 0.05, 0.35, 0.25);
  }
  pause() {
    if (!this.ok) return;
    const d = this.out(0.45);
    const f = NOTE(C5 + 7) * this.jitter();
    this.voice(d, { freq: f, decay: 0.12, gain: 0.9, glide: 0.75 });
  }

  // small controls: a soft wooden tap, barely there
  tap(gain = 1) {
    if (!this.ok) return;
    const d = this.out(0.28 * gain, false);
    const f = NOTE(C5 + 19) * this.jitter(0.03);
    this.voice(d, { freq: f, type: 'triangle', attack: 0.002, decay: 0.045, gain: 1 });
    this.voice(d, { freq: f * 0.5, attack: 0.002, decay: 0.03, gain: 0.5 });
  }

  // a stepper / slider tick that follows the value up and down
  step(dir = 1) {
    if (!this.ok) return;
    const d = this.out(0.22, false);
    this.voice(d, { freq: NOTE(C5 + (dir > 0 ? 16 : 12)) * this.jitter(0.01), type: 'triangle', decay: 0.05 });
  }

  // switches: up a fifth for on, down for off
  toggle(on) {
    if (!this.ok) return;
    const d = this.out(0.32);
    const base = NOTE(C5 + 12);
    this.mallet(d, on ? base : base * 1.5, 0, 0.7, 0.18);
    this.mallet(d, on ? base * 1.5 : base, 0.06, 0.7, 0.22);
  }

  // mode tabs: one clean mallet note per tab
  tab(i) {
    if (!this.ok) return;
    this.mallet(this.out(0.32), NOTE(C5 + [7, 4, 0][i] + 12), 0, 0.8, 0.3);
  }

  // a sheet opening/closing: a soft two-note sweep
  sheet(open) {
    if (!this.ok) return;
    const d = this.out(0.25);
    const a = NOTE(C5 + 7), b = NOTE(C5 + 12);
    this.mallet(d, open ? a : b, 0, 0.6, 0.22);
    this.mallet(d, open ? b : a, 0.07, 0.6, 0.3);
  }

  // tapping the crystal
  clink() {
    if (!this.ok) return;
    const d = this.out(0.32);
    const f = NOTE(C5 + 24 + [0, 4, 7][Math.floor(Math.random() * 3)]);
    this.bell(d, f, 0, 0.8, 0.9);
  }

  // a flick: filtered air that sweeps with the spin
  spin(speed = 0.5) {
    if (!this.ok) return;
    const c = this.ctx, at = c.currentTime;
    const len = 0.35;
    const buf = c.createBuffer(1, Math.floor(c.sampleRate * len), c.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    const src = c.createBufferSource();
    src.buffer = buf;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass';
    bp.Q.value = 1.4;
    bp.frequency.setValueAtTime(900, at);
    bp.frequency.exponentialRampToValueAtTime(2600, at + len);
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(0.12 * speed * this.volume, at + 0.05);
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    src.connect(bp).connect(g).connect(this.master);
    src.start(at);
  }

  // a bite: the real crunch, then a note that climbs with every bite
  bite(stage) {
    if (!this.ok) return;
    const b = this.buffers.bite;
    if (b) {
      const src = this.ctx.createBufferSource();
      src.buffer = b;
      src.playbackRate.value = this.jitter(0.05);
      src.connect(this.out(0.85, false));
      src.start();
    }
    const n = PENTA[Math.max(0, stage - 1)];
    this.mallet(this.out(0.42), NOTE(C5 + n), 0.07, 1, 0.55);
  }

  // the apple is gone: a quick rising arpeggio that lands on a bell
  finish() {
    if (!this.ok) return;
    const d = this.out(0.5);
    [0, 4, 7, 12].forEach((n, i) => this.mallet(d, NOTE(C5 + n), i * 0.085, 0.8, 0.5));
    this.bell(d, NOTE(C5 + 24), 0.34, 0.55, 1.6);
    this.bell(d, NOTE(C5 + 28), 0.36, 0.3, 1.4);
  }

  // break over: a gentle two-note "ready"
  ready() {
    if (!this.ok) return;
    const d = this.out(0.45);
    this.mallet(d, NOTE(C5 + 7), 0, 0.8, 0.4);
    this.bell(d, NOTE(C5 + 12), 0.12, 0.6, 1.2);
  }
}
