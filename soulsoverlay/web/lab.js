// The Lab tab: the "HP Bar Lab" (made by a friend of the project) built
// into the settings page, with its layout kept as it was. It edits the
// NEW PB effect that the HUD plays. The lab's stage
// plays the effect on its own bar, with a timeline to scrub; the other tabs'
// previews show it on the game's bar. The lab's own settings files load and
// save as they are.
window.DCLab = (function () {
  "use strict";
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const clone = (o) => JSON.parse(JSON.stringify(o));

  const PRESETS = {
    "Ease out expo (snap, long crawl)": [0.16, 1, 0.3, 1],
    "Ease out quart": [0.25, 1, 0.5, 1],
    "Ease out cubic": [0.33, 1, 0.68, 1],
    "Ease out quad (like the gif)": [0.5, 1, 0.89, 1],
    "Instant snap": [0.05, 0.9, 0.1, 1],
    "Overshoot": [0.34, 1.56, 0.64, 1],
    "Anticipate (pull back first)": [0.6, -0.28, 0.735, 0.045],
    "Ease in-out (bell)": [0.65, 0, 0.35, 1],
    "Tight in-out (sharp bell)": [0.83, 0, 0.17, 1],
    "Ease": [0.25, 0.1, 0.25, 1],
    "Linear": [0, 0, 1, 1],
  };
  const OTHER_PRESETS = {
    "Spring (bouncy)": { curveType: "spring", spring: { stiffness: 220, damping: 9 } },
    "Spring (tight)": { curveType: "spring", spring: { stiffness: 320, damping: 30 } },
    "Power out ^3": { curveType: "power", power: { dir: "out", exp: 3 } },
    "Power out ^8 (whip)": { curveType: "power", power: { dir: "out", exp: 8 } },
    "Power in-out ^4 (bell)": { curveType: "power", power: { dir: "inout", exp: 4 } },
    "Steps (6)": { curveType: "steps", steps: { n: 6, pos: "end" } },
    "Points: snap then crawl": { curveType: "points", interp: "smooth", points: [[0, 0], [0.08, 0.6], [0.3, 0.88], [1, 1]] },
    "Points: two-stage burst": { curveType: "points", interp: "smooth", points: [[0, 0], [0.1, 0.45], [0.35, 0.5], [0.5, 0.92], [1, 1]] },
  };
  const CAPS = {
    bezier: "Drag the two handles. Steep = fast, flat = slow. Above 1 overshoots, below 0 pulls back.",
    points: "Click to add a point, drag to move, double-click or right-click to remove.",
    power: "Higher exponent = sharper start (out) or end (in).",
    spring: "Low damping bounces past full and settles; high damping glides in.",
    steps: "Jumps in fixed chunks instead of moving smoothly.",
    linear: "Constant speed the whole way.",
  };
  // Effect presets: changes on top of the default effect (the lab's own list).
  const FX_PRESETS = {
    "Souls heal (original)": {},
    "Radiant burst": {curve: [0.05, 0.9, 0.1, 1], spread: 700, hold: 300, fade: 800, streak: {thickness: 3, dur: 500}, flash: {decay: "fast", attack: 15, dur: 420, size: 200, height: 90, blur: 6, growFrom: 0.5, growTo: 1.4}, particles: {mode: "burst", shape: "spark", count: 70, speed: 220, drag: 4, rise: -80, life: 650}},
    "Gif match (soft sweep)": {curve: [0.5, 1, 0.89, 1], spread: 1000, hold: 1300, fade: 750, colorShift: 700, streak: {on: false}, flash: {intensity: 0.7, dur: 400}, particles: {on: false}, jolt: 0},
    "Shockwave blast": {curve: [0.05, 0.9, 0.1, 1], spread: 600, hold: 250, fade: 600, streak: {thickness: 5, dur: 350}, flash: {size: 160, dur: 260}, waves: {on: true, intensity: 0.9, size: 50, trail: 120}, particles: {mode: "front", shape: "spark", count: 90, speed: 160, rise: -120, drag: 2, jitter: 0.8, life: 600}, jolt: 0.6, shake: 3},
    "Critical hit": {curve: [0.05, 0.9, 0.1, 1], spread: 350, hold: 150, fade: 550, jolt: 0.8, shake: 6, shakeDur: 320, flash: {size: 230, dur: 300, decay: "fast"}, streak: {thickness: 6, dur: 300}, waves: {on: true, trail: 160, size: 40}, landing: {on: true, intensity: 0.8, dur: 220}, particles: {mode: "burst", shape: "spark", count: 130, speed: 280, drag: 4, rise: -220, life: 700, stretch: 1.6}},
    "Holy light": {pale: "#fffbea", warm: "#ffcf5e", coreColor: "#ffffff", glowColor: "#fff0b0", partColor: "#fff3c4", curveType: "power", power: {dir: "out", exp: 3}, spread: 900, hold: 1000, fade: 900, flash: {attack: 120, dur: 700, decay: "slow", size: 180}, fill: {pulse: 0.25, pulseRate: 1.4}, sheen: {on: true, delay: 100, dur: 600, width: 10}, landing: {on: true, intensity: 0.5, dur: 400}, glow: {intensity: 0.8, height: 110}, particles: {mode: "bar", count: 70, speed: 20, rise: 40, life: 1600, size: 1.6, twinkle: 0.7}},
    "Electric surge": {pale: "#eaf7ff", warm: "#3a9cff", coreColor: "#ffffff", glowColor: "#7fd4ff", partColor: "#c4ecff", direction: "ltr", curveType: "power", power: {dir: "out", exp: 2}, spread: 650, hold: 600, fill: {shimmer: 0.8, shimmerSpeed: 4, pulse: 0.15, pulseRate: 9}, flash: {blur: 2, size: 80, flicker: 0.7, decay: "fast"}, streak: {on: false}, waves: {on: true, size: 34, trail: 90}, particles: {mode: "front", shape: "spark", count: 90, speed: 220, drag: 6, jitter: 1, rise: 0, life: 450, stretch: 2}},
    "Left → right charge": {direction: "ltr", curveType: "power", power: {dir: "out", exp: 3}, spread: 900, hold: 400, streak: {on: false}, flash: {size: 70}, waves: {on: true, intensity: 0.7, size: 40, trail: 80}, particles: {mode: "front", count: 60, speed: 50, rise: 80}, jolt: 0.15},
    "Right → left drain": {direction: "rtl", curveType: "power", power: {dir: "inout", exp: 3}, spread: 1100, hold: 300, fade: 900, streak: {on: false}, flash: {on: false}, particles: {mode: "front", count: 50, speed: 30, rise: -60}, jolt: 0},
    "Closing in (edges)": {direction: "edges", curve: [0.65, 0, 0.35, 1], spread: 900, hold: 500, streak: {on: false}, flash: {size: 80}, waves: {on: true, trail: 60}, landing: {on: true, intensity: 0.7, dur: 350}, particles: {mode: "front", count: 60}},
    "Bouncy spring pop": {curveType: "spring", spring: {stiffness: 260, damping: 10}, spread: 1100, reach: 85, jolt: 0.4},
    "Stepped charge-up": {direction: "ltr", curveType: "steps", steps: {n: 8, pos: "end"}, spread: 1200, hold: 400, streak: {on: false}, particles: {mode: "bar", count: 40}, jolt: 0, landing: {on: true}},
    "Gentle embers": {curveType: "power", power: {dir: "out", exp: 2}, spread: 1400, hold: 900, fade: 1200, fadeCurve: "smooth", streak: {on: false}, flash: {intensity: 0.4, dur: 600, size: 90}, glow: {intensity: 0.45}, particles: {mode: "bar", count: 120, speed: 25, rise: 30, life: 1600, size: 1.6, intensity: 0.7, twinkle: 0.6}, jolt: 0},
    "Frost": {pale: "#e2f4ff", warm: "#3f8fe0", coreColor: "#f4fbff", glowColor: "#8fd0ff", partColor: "#cdeeff", sheen: {on: true, angle: 35}, particles: {mode: "bar", count: 70, speed: 20, rise: -20, life: 1400}},
    "Poison": {pale: "#e6ffc2", warm: "#5fae2a", coreColor: "#f2ffe0", glowColor: "#a8f070", partColor: "#c8ff8a", direction: "ltr", curveType: "power", power: {dir: "out", exp: 4}, fill: {pulse: 0.3, pulseRate: 3}, particles: {mode: "bar", count: 80, rise: 50, colorVar: 0.6}},
    "Friend's saved look": {reach: 80, curveType: "points", curve: [0.12, 1, 0.3, 1], points: [[0, 0], [0.08, 0.6], [0.3, 0.88], [1, 1]], power: {dir: "inout", exp: 4}, spring: {stiffness: 320, damping: 30}, spread: 1000, hold: 2000, fade: 1250, colorShift: 200, soft: 10, fill: {brightness: 0.9, coreWidth: 85, endFade: 12, pulseRate: 5.5, shimmerSpeed: 2}, streak: {intensity: 0.8, open: 225, dur: 1500, thickness: 14, length: 90, blur: 2.5}, flash: {attack: 50, dur: 500, decay: "fast", size: 500, blur: 30, growFrom: 1.25, growTo: 1, height: 125}, glow: {intensity: 0.6, height: 125, blur: 10, overscan: 150}, waves: {intensity: 1}, particles: {mode: "bar", count: 125, delay: 50, life: 1000, speed: 100, rise: -130, size: 2.5, stretch: 0, intensity: 0.8, seed: 1}, jolt: 1.25, shake: 2.5, shakeDur: 500, coreLine: 0.25, partColor: "#ffd78a"},
  };
  // Settings that belong to this preview or to the game, kept when a preset loads.
  const KEEP = ["hp", "barWidth", "bg", "showText", "speed", "area"];
  const PANELS = [
    { title: "Timing",
      selects: [
        ["direction", "Fill direction", [["center", "From center outward"], ["ltr", "Left → right"], ["rtl", "Right → left"], ["edges", "Edges → center"]]],
        ["fadeCurve", "Fade shape", [["in", "Ease in (holds, then drops)"], ["linear", "Linear"], ["out", "Ease out (drops, then lingers)"], ["smooth", "Smooth"]]]],
      items: [
        ["spread", "Spread duration", 50, 3000, 10, "ms"],
        ["reach", "Glow reach", 5, 100, 1, "%"],
        ["hold", "Hold at full", 0, 3000, 10, "ms"],
        ["fade", "Fade out", 50, 3000, 10, "ms"],
        ["colorShift", "Flash color → body color", 0, 3000, 10, "ms"],
        ["soft", "Leading-edge softness", 0, 25, 0.5, "%"]] },
    { title: "Fill light",
      items: [
        ["fill.brightness", "Brightness", 0, 2, 0.01],
        ["coreLine", "Core line brightness", 0, 1, 0.01],
        ["fill.coreWidth", "Core line thickness", 5, 100, 1, "%"],
        ["fill.endFade", "Fade toward bar ends", 0, 40, 0.5, "%"],
        ["fill.pulse", "Pulse while held", 0, 1, 0.01],
        ["fill.pulseRate", "Pulse rate", 0.2, 12, 0.1, "Hz"],
        ["fill.shimmer", "Shimmer", 0, 1, 0.01],
        ["fill.shimmerSpeed", "Shimmer speed", 0, 8, 0.1]] },
    { title: "Lens streak", toggle: "streak.on",
      items: [
        ["streak.intensity", "Brightness", 0, 1, 0.01],
        ["streak.delay", "Delay", 0, 1500, 10, "ms"],
        ["streak.open", "Open time", 0, 500, 5, "ms"],
        ["streak.dur", "Duration", 50, 2000, 10, "ms"],
        ["streak.thickness", "Thickness", 1, 14, 0.5, "px"],
        ["streak.length", "Length", 10, 100, 1, "%"],
        ["streak.blur", "Blur", 0, 10, 0.5, "px"]] },
    { title: "Origin flash", toggle: "flash.on",
      selects: [["flash.decay", "Decay shape", [["fast", "Fast (snappy)"], ["quad", "Quadratic"], ["linear", "Linear"], ["slow", "Slow (lingers)"], ["smooth", "Smooth"]]]],
      items: [
        ["flash.intensity", "Brightness", 0, 1.5, 0.01],
        ["flash.delay", "Delay", 0, 1500, 10, "ms"],
        ["flash.attack", "Attack (ramp in)", 0, 500, 5, "ms"],
        ["flash.dur", "Decay time", 30, 2000, 10, "ms"],
        ["flash.flicker", "Flicker", 0, 1, 0.01],
        ["flash.inset", "Inset from bar ends", 0, 200, 1, "px"],
        ["flash.size", "Width", 10, 600, 1, "px"],
        ["flash.height", "Height", 5, 400, 1, "px"],
        ["flash.blur", "Blur", 0, 30, 0.5, "px"],
        ["flash.growFrom", "Start scale", 0, 3, 0.05, "×"],
        ["flash.growTo", "End scale", 0, 4, 0.05, "×"]] },
    { title: "Outer glow", toggle: "glow.on",
      items: [
        ["glow.intensity", "Brightness", 0, 1, 0.01],
        ["glow.height", "Height", 10, 220, 1, "px"],
        ["glow.blur", "Blur", 0, 30, 0.5, "px"],
        ["glow.overscan", "Spill past the ends", 0, 200, 1, "px"],
        ["glow.offsetY", "Vertical offset", -40, 40, 1, "px"]] },
    { title: "Shockwave fronts", toggle: "waves.on",
      items: [
        ["waves.intensity", "Brightness", 0, 1, 0.01],
        ["waves.size", "Size", 10, 160, 1, "px"],
        ["waves.trail", "Trail length", 0, 400, 1, "px"]] },
    { title: "Landing flash", toggle: "landing.on",
      items: [
        ["landing.intensity", "Brightness boost", 0, 1.5, 0.01],
        ["landing.dur", "Duration", 50, 1500, 10, "ms"]] },
    { title: "Sheen sweep", toggle: "sheen.on",
      items: [
        ["sheen.intensity", "Brightness", 0, 1, 0.01],
        ["sheen.delay", "Delay after spread", -2000, 2000, 10, "ms"],
        ["sheen.dur", "Sweep time", 100, 3000, 10, "ms"],
        ["sheen.width", "Width", 2, 40, 0.5, "%"],
        ["sheen.angle", "Angle", -60, 60, 1, "°"]] },
    { title: "Particles", toggle: "particles.on",
      selects: [
        ["particles.mode", "Emit from", [["front", "Spreading front"], ["burst", "Origin burst"], ["bar", "Along the lit bar"]]],
        ["particles.shape", "Shape", [["dot", "Glowing dots"], ["spark", "Streaking sparks"]]]],
      items: [
        ["particles.count", "Count", 0, 400, 1],
        ["particles.delay", "Delay", 0, 1500, 10, "ms"],
        ["particles.life", "Lifetime", 100, 3000, 10, "ms"],
        ["particles.speed", "Speed", 0, 500, 1, "px/s"],
        ["particles.rise", "Rise (negative falls)", -500, 500, 1, "px/s²"],
        ["particles.drag", "Drag", 0, 12, 0.1],
        ["particles.jitter", "Randomness", 0, 1, 0.01],
        ["particles.size", "Size", 0.5, 6, 0.1, "px"],
        ["particles.sizeEnd", "Size at end of life", 0, 2, 0.05, "×"],
        ["particles.stretch", "Spark length", 0, 5, 0.05, "×"],
        ["particles.twinkle", "Twinkle", 0, 1, 0.01],
        ["particles.intensity", "Brightness", 0, 1, 0.01],
        ["particles.colorVar", "Color variation", 0, 1, 0.01],
        ["particles.seed", "Random seed", 1, 100, 1]] },
    { title: "Grain / deband", toggle: "grain.on",
      selects: [
        ["grain.blend", "Blend", [["overlay", "Overlay (natural)"], ["soft-light", "Soft light (subtle)"], ["screen", "Screen (lightens)"], ["normal", "Normal (raw noise)"]]],
        ["grain.area", "Covers", [["effect", "Effect area only"], ["full", "Whole preview (in game: the effect area)"]]]],
      items: [
        ["grain.amount", "Amount", 0, 1, 0.01],
        ["grain.size", "Grain size", 1, 4, 0.5, "px"],
        ["grain.fps", "Animation rate (0 = still)", 0, 60, 1, "fps"]],
      checks: [["grain.mono", "Monochrome grain"]] },
    { title: "Bar & camera",
      items: [
        ["jolt", "Jolt (bar swell)", 0, 1.5, 0.01],
        ["joltDur", "Jolt duration", 20, 600, 5, "ms"],
        ["shake", "Screen shake", 0, 12, 0.1, "px"],
        ["shakeDur", "Shake duration", 50, 1000, 10, "ms"]],
      // Ours: in the game, how much of the bar the light covers.
      selects: [["area", "In game, the light covers", [["bar", "The whole bar"], ["health", "Only the health that's left"]]]] },
    { title: "Scene",
      items: [
        ["hp", "Health fill", 1, 100, 1, "%"],
        ["barWidth", "Bar width", 200, 1600, 10, "px"]],
      selects: [["bg", "Background", [["dark", "Dark (default)"], ["warm", "Warm gameplay"], ["stone", "Stone"], ["light", "Light"], ["black", "Pure black"], ["checker", "Checkerboard"]]]],
      checks: [["showText", "Boss name and stats"]] },
  ];

  const getP = (S, p) => p.split(".").reduce((o, k) => o[k], S);
  const setP = (S, p, v) => { const ks = p.split("."); const last = ks.pop(); ks.reduce((o, k) => o[k], S)[last] = v; };

  // Copy only known keys with matching types from src onto base.
  function merge(base, src) {
    if (!src || typeof src !== "object") return base;
    for (const k of Object.keys(base)) {
      const b = base[k], v = src[k];
      if (v === undefined) continue;
      if (Array.isArray(b)) {
        if (!Array.isArray(v)) continue;
        if (Array.isArray(b[0])) {
          if (v.length >= 2 && v.length <= 32 && v.every((p) => Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === "number"))) base[k] = v.map((p) => [...p]);
        } else if (v.length === b.length && v.every((n) => typeof n === "number")) base[k] = [...v];
      } else if (b && typeof b === "object") merge(b, v);
      else if (typeof v === typeof b) base[k] = v;
    }
    return base;
  }

  const HTML = `
<div class="stage">
  <nav class="jump" aria-label="Jump to"><a href="#" data-jump="effect">The Lab</a><a href="#" data-jump="json">Settings JSON</a></nav>
  <div class="lab-hud">
    <div class="lab-row top"><span class="name">Morgott, the Omen King</span><span class="num" data-id="hpNum">252</span></div>
    <div class="lab-bar" data-id="bar"><div class="pb" data-id="pb"></div></div>
    <div class="lab-row bottom"><span class="meta">Deaths<b>37</b></span><span class="meta">PB<b class="gold">23%</b></span></div>
  </div>
  <div class="transport">
    <button class="primary" data-id="play">Play</button>
    <label class="chk"><input type="checkbox" data-id="loop"> Loop</label>
    <label class="chk speed" title="Plays the bar above slower or faster. Preview only.">Speed <input type="range" data-id="speed" min="0.05" max="2" step="0.05" aria-label="Preview speed"><output data-id="speedOut"></output></label>
    <input type="range" data-id="scrub" min="0" max="2000" step="1" value="0" aria-label="Timeline">
    <span class="time" data-id="time">0 / 0 ms</span>
    <button type="button" data-id="undo" title="Undo (Ctrl+Z)">Undo</button>
    <button type="button" data-id="redo" title="Redo (Ctrl+Y)">Redo</button>
  </div>
  <div class="transport">
    <select data-id="fxPreset" aria-label="Effect preset"></select>
    <input type="text" data-id="presetName" placeholder="Name for your preset" aria-label="Preset name" maxlength="40">
    <button type="button" data-id="savePreset">Save preset</button>
    <button type="button" data-id="delPreset">Delete</button>
    <button type="button" data-id="randomize">Randomize</button>
  </div>
</div>
<div class="lab-wrap">
<h2 class="lab-sep first" data-anchor="effect">The Lab</h2>
<div class="cap lab-sep-cap">Intended for advanced users to customize the effects.</div>
<div class="lab-cols" data-id="panels">
  <section class="panel curve-wrap">
    <h3>Spread speed curve</h3>
    <canvas data-id="curve" class="curve"></canvas>
    <div class="cap" data-id="curveCap"></div>
    <canvas data-id="speedc" class="speedc"></canvas>
    <div class="cap">Speed over time (height = how fast the light is spreading)</div>
    <div class="curve-row">
      <select data-id="ctype" aria-label="Curve type">
        <option value="bezier">Cubic bezier</option>
        <option value="points">Custom points</option>
        <option value="power">Power (in / out / in-out)</option>
        <option value="spring">Spring</option>
        <option value="steps">Steps</option>
        <option value="linear">Linear</option>
      </select>
      <select data-id="preset" aria-label="Curve preset"></select>
    </div>
    <div class="curve-row" data-id="bezRow"><input type="text" data-id="bez" aria-label="cubic-bezier values" spellcheck="false"></div>
    <div data-id="cparams" style="margin-top:10px"></div>
  </section>
</div>
<h2 class="lab-sep" data-anchor="json">Settings JSON</h2>
  <section class="panel">
    <h3>Settings (JSON)</h3>
    <div class="actions">
      <button data-id="copy">Copy settings</button>
      <button data-id="apply">Apply JSON below</button>
      <button data-id="importBtn">Import .json file</button>
      <button data-id="exportBtn">Save .json file</button>
      <button data-id="reset">Reset to defaults</button>
      <input type="file" data-id="importFile" accept=".json,application/json,text/plain" hidden>
    </div>
    <div class="cap" data-id="jsonMsg">Edit or paste settings here, then press Apply. Missing keys keep their current value. Click Save at the top to keep your changes.
      Shortcuts: <kbd>Space</kbd> play, <kbd>Ctrl+Z</kbd> undo, <kbd>Ctrl+Y</kbd> redo. Number boxes take values past the slider's range.</div>
    <textarea data-id="dump" spellcheck="false" aria-label="Settings JSON"></textarea>
  </section>
</div>`;

  const fmt = (v) => +(+v).toFixed(3);
  // A number box with its own up/down arrows beside it (the browser's own
  // arrows sit on top of the number). It takes values past the slider's range.
  function numBox(step, put, get) {
    const wrap = document.createElement("span"); wrap.className = "numbox";
    const num = document.createElement("input"); Object.assign(num, { type: "number", step });
    const arrows = document.createElement("span"); arrows.className = "arrows";
    const btn = (dir, label) => {
      const b = document.createElement("button"); b.type = "button"; b.tabIndex = -1;
      b.textContent = dir > 0 ? "▲" : "▼"; b.setAttribute("aria-label", label);
      b.onclick = (e) => { e.preventDefault(); const v = fmt(+get() + dir * step); put(v); num.value = fmt(v); };
      return b;
    };
    arrows.append(btn(1, "Up"), btn(-1, "Down"));
    num.onchange = () => {
      const v = +num.value;
      if (num.value !== "" && Number.isFinite(v)) put(v); else num.value = fmt(get());
    };
    wrap.append(num, arrows);
    return { el: wrap, show: (v) => { num.value = fmt(v); } };
  }
  function ctlName(label, unit) {
    const name = document.createElement("span"); name.textContent = label;
    if (unit) { const u = document.createElement("span"); u.className = "unit"; u.textContent = " " + unit; name.append(u); }
    return name;
  }
  // A panel's heading: click the title to fold it, ↺ puts its settings back.
  function panelHead(sec, title, reset) {
    const h = document.createElement("h3");
    const t = document.createElement("span"); t.className = "title"; t.textContent = title;
    t.onclick = () => sec.classList.toggle("collapsed");
    const rs = document.createElement("button"); rs.type = "button"; rs.className = "panel-reset"; rs.textContent = "↺";
    rs.title = "Reset this section"; rs.onclick = reset;
    h.append(t, rs);
    let body = sec.querySelector(".body");
    if (!body) { body = document.createElement("div"); body.className = "body"; sec.append(body); }
    sec.insertBefore(h, body);
    return h;
  }

  // opts: { root, defaults, get(): fx, set(fx), getUse(), setUse(bool) }
  // Panels flow down columns, so short ones stack under each other. This
  // order puts each tall panel in a column of its own and the short ones together.
  // Lay panels out in fixed columns (one list of titles per column) so short
  // panels stack under each other and the tall ones get a column to themselves.
  function packColumns(box, cols) {
    const title = (sec) => sec.querySelector("h3").firstChild.textContent.trim();
    const secs = [...box.children];
    const made = cols.map((names) => {
      const col = document.createElement("div");
      col.className = "lab-col";
      for (const n of names) {
        const sec = secs.find((x) => title(x) === n);
        if (sec) col.append(sec);
      }
      return col;
    });
    // Anything not named goes at the end of the last column.
    const rest = secs.filter((x) => x.parentNode === box);
    made[made.length - 1].append(...rest);
    box.replaceChildren(...made);
  }

  function build(opts) {
    const host = opts.root;
    host.innerHTML = HTML;
    const el = (id) => host.querySelector(`[data-id="${id}"]`);
    let S = merge(clone(opts.defaults), opts.get());
    const bar = el("bar"), scrub = el("scrub"), timeEl = el("time"), dump = el("dump");
    let fx = null, ease = (x) => x;

    // -- the effect on the stage -----------------------------------------------
    let pushTimer = 0;
    const labHud = host.querySelector(".lab-hud"), stageEl = host.querySelector(".stage");
    function applyStatic(push = true) {
      labHud.style.width = `min(${S.barWidth}px, 100%)`;
      labHud.classList.toggle("notext", !S.showText);
      stageEl.dataset.bg = S.bg;
      el("hpNum").textContent = Math.round(252 * S.hp / 100);
      fx = DCFx.prepare(bar, S, S.hp / 100, { shakeEl: labHud, grainHost: stageEl });
      ease = fx.ease;
      scrub.max = fx.total;
      if (document.activeElement !== dump) dump.value = JSON.stringify(S, null, 2);
      scheduleSnap();
      // Hand the change to the page (Save, the other tabs), a little debounced
      // while a slider is being dragged.
      if (push) { clearTimeout(pushTimer); pushTimer = setTimeout(() => opts.set(clone(S)), 120); }
    }
    function render(t) {
      fx.draw(t);
      scrub.value = Math.max(0, t);
      timeEl.textContent = `${Math.round(Math.max(0, t))} / ${fx.total} ms`;
      drawCurve(t >= 0 ? clamp(t / S.spread) : null);
    }

    // -- playback --------------------------------------------------------------
    let raf = 0, start = 0, offset = 0, loopTimer = 0;
    function play(from = 0) {
      cancelAnimationFrame(raf); clearTimeout(loopTimer);
      offset = from; start = performance.now();
      el("play").textContent = "Replay";
      const tick = (now) => {
        const t = offset + (now - start) * S.speed;
        render(Math.min(t, fx.total));
        if (t < fx.total) raf = requestAnimationFrame(tick);
        else if (el("loop").checked) loopTimer = setTimeout(() => play(0), 500);
      };
      raf = requestAnimationFrame(tick);
    }
    const stop = () => { cancelAnimationFrame(raf); clearTimeout(loopTimer); };
    el("play").onclick = () => play(0);
    scrub.oninput = () => { stop(); render(+scrub.value); };
    // Space plays; Ctrl+Z / Ctrl+Y step through this tab's changes.
    document.addEventListener("keydown", (e) => {
      if (host.hidden) return;
      const a = document.activeElement;
      if (a && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && /text|number/.test(a.type)))) return;
      const mod = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
      if (mod && k === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
      else if (mod && (k === "y" || (k === "z" && e.shiftKey))) { e.preventDefault(); redo(); }
      else if (e.code === "Space" && !/SELECT|BUTTON/.test(a.tagName)) { e.preventDefault(); play(0); }
    });

    // -- undo / redo: snapshots taken shortly after each change settles --------
    let hist = [], fut = [], lastSnap = null, snapTimer = 0;
    function scheduleSnap() { clearTimeout(snapTimer); snapTimer = setTimeout(snap, 350); }
    function snap() {
      clearTimeout(snapTimer);
      const j = JSON.stringify(S);
      if (j === lastSnap) return;
      if (lastSnap !== null) { hist.push(lastSnap); if (hist.length > 150) hist.shift(); fut = []; }
      lastSnap = j; updUndo();
    }
    function restore(j) { S = merge(clone(opts.defaults), JSON.parse(j)); fxSel.value = ""; reload(); }
    function undo() { snap(); if (!hist.length) return; fut.push(lastSnap); lastSnap = hist.pop(); restore(lastSnap); updUndo(); }
    function redo() { snap(); if (!fut.length) return; hist.push(lastSnap); lastSnap = fut.pop(); restore(lastSnap); updUndo(); }
    function updUndo() { el("undo").disabled = !hist.length; el("redo").disabled = !fut.length; }
    el("undo").onclick = undo;
    el("redo").onclick = redo;
    function reload() { builtType = null; refreshers.forEach((f) => f()); curveChanged(); play(0); }
    const speed = el("speed");
    const showSpeed = () => { speed.value = S.speed; el("speedOut").textContent = S.speed + "×"; };
    speed.oninput = () => { S.speed = +speed.value; showSpeed(); applyStatic(); };
    speed.onchange = () => play(0);

    // -- curve editor ----------------------------------------------------------
    const cv = el("curve"), sp = el("speedc");
    const YMIN = -0.5, YMAX = 1.5, PAD = 14;
    let dpr = 1;
    function sizeCanvas(c) { dpr = window.devicePixelRatio || 1; const r = c.getBoundingClientRect(); c.width = r.width * dpr; c.height = r.height * dpr; }
    const toPx = (x, y) => { const w = cv.width / dpr, h = cv.height / dpr; return [PAD + x * (w - 2 * PAD), PAD + (YMAX - y) / (YMAX - YMIN) * (h - 2 * PAD)]; };
    const fromPx = (px, py) => { const w = cv.width / dpr, h = cv.height / dpr; return [clamp((px - PAD) / (w - 2 * PAD)), clamp(YMAX - (py - PAD) / (h - 2 * PAD) * (YMAX - YMIN), YMIN, YMAX)]; };

    function drawCurve(dotX) {
      const c = cv.getContext("2d"), w = cv.width / dpr, h = cv.height / dpr;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, w, h);
      const [x1, y1, x2, y2] = S.curve;
      c.strokeStyle = "#2a211b"; c.lineWidth = 1;
      for (const y of [0, 0.5, 1]) { const [, py] = toPx(0, y); c.beginPath(); c.moveTo(PAD, py); c.lineTo(w - PAD, py); c.stroke(); }
      for (const x of [0, 0.5, 1]) { const [px] = toPx(x, 0); c.beginPath(); c.moveTo(px, PAD); c.lineTo(px, h - PAD); c.stroke(); }
      c.fillStyle = "#5e5246"; c.font = "10px system-ui";
      c.fillText("time →", w - PAD - 36, toPx(0, 0)[1] + 12);
      c.save(); c.translate(PAD - 4, toPx(0, 1)[1] + 34); c.rotate(-Math.PI / 2); c.fillText("filled →", 0, 0); c.restore();
      const p0 = toPx(0, 0), p3 = toPx(1, 1), h1 = toPx(x1, y1), h2 = toPx(x2, y2);
      if (S.curveType === "bezier") { c.strokeStyle = "#6d5a45"; c.beginPath(); c.moveTo(...p0); c.lineTo(...h1); c.moveTo(...p3); c.lineTo(...h2); c.stroke(); }
      c.strokeStyle = "#e0a85a"; c.lineWidth = 2; c.beginPath();
      for (let i = 0; i <= 400; i++) { const x = i / 400; const [px, py] = toPx(x, ease(x)); if (i) c.lineTo(px, py); else c.moveTo(px, py); }
      c.stroke();
      c.fillStyle = "#f3dfc0";
      if (S.curveType === "bezier") for (const hp of [h1, h2]) { c.beginPath(); c.arc(...hp, 6, 0, 7); c.fill(); }
      if (S.curveType === "points") S.points.forEach(([px, py], i) => {
        const fixed = i === 0 || i === S.points.length - 1;
        c.fillStyle = fixed ? "#7a6a58" : "#f3dfc0";
        c.beginPath(); c.arc(...toPx(px, py), fixed ? 4 : 6, 0, 7); c.fill();
      });
      if (dotX != null) { const [px, py] = toPx(dotX, ease(dotX)); c.fillStyle = "#fff"; c.beginPath(); c.arc(px, py, 4, 0, 7); c.fill(); }
      drawSpeed(dotX);
    }
    function drawSpeed(dotX) {
      const c = sp.getContext("2d"), w = sp.width / dpr, h = sp.height / dpr;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, w, h);
      const N = 120, v = [];
      for (let i = 0; i <= N; i++) { const x = i / N, d = 0.004; v.push((ease(Math.min(1, x + d)) - ease(Math.max(0, x - d))) / (Math.min(1, x + d) - Math.max(0, x - d))); }
      const max = Math.max(...v.map(Math.abs), 1e-6), base = h - 6;
      c.fillStyle = "rgba(224,168,90,.18)"; c.strokeStyle = "#e0a85a"; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(PAD, base);
      v.forEach((s, i) => c.lineTo(PAD + i / N * (w - 2 * PAD), base - Math.max(0, s) / max * (h - 12)));
      c.lineTo(w - PAD, base); c.closePath(); c.fill(); c.stroke();
      if (dotX != null) { const px = PAD + dotX * (w - 2 * PAD); c.strokeStyle = "#fff"; c.beginPath(); c.moveTo(px, 4); c.lineTo(px, base); c.stroke(); }
    }

    let drag = -1;
    const mouse = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    const nearest = (list, mx, my) => { let best = -1, bd = 14; list.forEach(([x, y], i) => { const d = Math.hypot(x - mx, y - my); if (d < bd) { bd = d; best = i; } }); return best; };
    cv.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      const [mx, my] = mouse(e);
      if (S.curveType === "bezier") {
        const hs = [toPx(S.curve[0], S.curve[1]), toPx(S.curve[2], S.curve[3])];
        const d = hs.map(([x, y]) => Math.hypot(x - mx, y - my));
        drag = d[0] < d[1] ? 0 : 1;
      } else if (S.curveType === "points") {
        drag = nearest(S.points.map((p) => toPx(...p)), mx, my);
        if (drag === 0 || drag === S.points.length - 1) drag = -1;
        else if (drag < 0) {
          const [x, y] = fromPx(mx, my);
          if (x <= 0.001 || x >= 0.999 || S.points.length >= 32) return;
          S.points.push([+x.toFixed(3), +y.toFixed(3)]);
          S.points.sort((a, b) => a[0] - b[0]);
          drag = S.points.findIndex((p) => p[0] === +x.toFixed(3));
          curveChanged();
        }
      } else return;
      if (drag >= 0) { cv.setPointerCapture(e.pointerId); moveHandle(e); }
    });
    cv.addEventListener("pointermove", (e) => { if (drag >= 0) moveHandle(e); });
    cv.addEventListener("pointerup", () => { if (drag >= 0) { drag = -1; play(0); } });
    function removePointAt(e) {
      if (S.curveType !== "points") return;
      const [mx, my] = mouse(e);
      const i = nearest(S.points.map((p) => toPx(...p)), mx, my);
      if (i > 0 && i < S.points.length - 1) { S.points.splice(i, 1); curveChanged(); play(0); }
    }
    cv.addEventListener("dblclick", removePointAt);
    cv.addEventListener("contextmenu", (e) => { if (S.curveType === "points") { e.preventDefault(); removePointAt(e); } });
    function moveHandle(e) {
      const [x, y] = fromPx(...mouse(e));
      if (S.curveType === "bezier") { S.curve[drag * 2] = +x.toFixed(3); S.curve[drag * 2 + 1] = +y.toFixed(3); }
      else {
        const lo = S.points[drag - 1][0] + 0.005, hi = S.points[drag + 1][0] - 0.005;
        S.points[drag] = [+clamp(x, lo, hi).toFixed(3), +y.toFixed(3)];
      }
      curveChanged();
    }

    let builtType = null;
    function curveParam(label, get_, set_, min, max, step) {
      const row = document.createElement("label"); row.className = "ctl";
      const r = document.createElement("input"); Object.assign(r, { type: "range", min, max, step, value: get_() });
      const nb = numBox(step, (v) => { set_(v); r.value = get_(); nb.show(get_()); curveChanged(); play(0); }, get_);
      nb.show(get_());
      r.oninput = () => { set_(+r.value); nb.show(+r.value); curveChanged(); };
      r.onchange = () => play(0);
      row.append(ctlName(label), nb.el, r); return row;
    }
    function curveSelect(label, list, get_, set_) {
      const row = document.createElement("label"); row.className = "ctl";
      const name = document.createElement("span"); name.textContent = label;
      const sel = document.createElement("select"); sel.style.gridColumn = "1 / -1";
      for (const [v, t] of list) { const o = document.createElement("option"); o.value = v; o.textContent = t; sel.append(o); }
      sel.value = get_();
      sel.onchange = () => { set_(sel.value); curveChanged(); play(0); };
      row.append(name, sel); return row;
    }
    function buildCurveParams() {
      const box = el("cparams"); box.innerHTML = "";
      const t = S.curveType;
      if (t === "points") {
        box.append(curveSelect("Interpolation", [["smooth", "Smooth (no overshoot)"], ["spline", "Spline (can overshoot)"], ["linear", "Straight lines"]], () => S.interp, (v) => { S.interp = v; }));
        const b = document.createElement("button"); b.textContent = "Reset points";
        b.onclick = () => { S.points = clone(opts.defaults.points); curveChanged(); play(0); };
        box.append(b);
      } else if (t === "power") {
        box.append(curveSelect("Direction", [["out", "Out (fast start, slow end)"], ["in", "In (slow start, fast end)"], ["inout", "In-out (bell)"]], () => S.power.dir, (v) => { S.power.dir = v; }));
        box.append(curveParam("Exponent", () => S.power.exp, (v) => { S.power.exp = v; }, 1, 12, 0.1));
      } else if (t === "spring") {
        box.append(curveParam("Stiffness", () => S.spring.stiffness, (v) => { S.spring.stiffness = v; }, 20, 800, 1));
        box.append(curveParam("Damping", () => S.spring.damping, (v) => { S.spring.damping = v; }, 1, 80, 0.5));
      } else if (t === "steps") {
        box.append(curveParam("Number of steps", () => S.steps.n, (v) => { S.steps.n = Math.max(1, Math.round(v)); }, 1, 30, 1));
        box.append(curveSelect("Jump at", [["end", "End of each step"], ["start", "Start of each step"]], () => S.steps.pos, (v) => { S.steps.pos = v; }));
      }
      builtType = t;
    }

    const presetSel = el("preset"), bezIn = el("bez"), ctypeSel = el("ctype");
    function curveChanged(push = true) {
      ctypeSel.value = S.curveType;
      el("bezRow").hidden = S.curveType !== "bezier";
      el("curveCap").textContent = CAPS[S.curveType];
      cv.style.cursor = S.curveType === "bezier" || S.curveType === "points" ? "crosshair" : "default";
      if (builtType !== S.curveType) buildCurveParams();
      bezIn.value = `cubic-bezier(${S.curve.join(", ")})`;
      let match;
      if (S.curveType === "bezier") match = Object.entries(PRESETS).find(([, v]) => v.every((n, i) => Math.abs(n - S.curve[i]) < 1e-3));
      else match = Object.entries(OTHER_PRESETS).find(([, v]) => v.curveType === S.curveType && Object.keys(v).every((k) => JSON.stringify(v[k]) === JSON.stringify(S[k])));
      presetSel.value = match ? match[0] : "custom";
      applyStatic(push); render(+scrub.value || -1);
    }
    presetSel.innerHTML = '<option value="custom">Preset…</option>' +
      '<optgroup label="Bezier">' + Object.keys(PRESETS).map((k) => `<option>${k}</option>`).join("") + "</optgroup>" +
      '<optgroup label="Other">' + Object.keys(OTHER_PRESETS).map((k) => `<option>${k}</option>`).join("") + "</optgroup>";
    presetSel.onchange = () => {
      const v = presetSel.value;
      if (PRESETS[v]) { S.curveType = "bezier"; S.curve = [...PRESETS[v]]; }
      else if (OTHER_PRESETS[v]) merge(S, clone(OTHER_PRESETS[v]));
      else return;
      builtType = null;
      curveChanged(); play(0);
    };
    ctypeSel.onchange = () => { S.curveType = ctypeSel.value; curveChanged(); play(0); };
    bezIn.onchange = () => {
      const n = (bezIn.value.match(/-?\d*\.?\d+/g) || []).map(Number);
      if (n.length === 4) { S.curveType = "bezier"; S.curve = [clamp(n[0]), clamp(n[1], YMIN, YMAX), clamp(n[2]), clamp(n[3], YMIN, YMAX)]; curveChanged(); play(0); }
    };

    // -- control panels --------------------------------------------------------
    const panelsEl = el("panels");
    const refreshers = [];
    function fxSlider([path, label, min, max, step, unit = ""]) {
      const row = document.createElement("label"); row.className = "ctl";
      const r = document.createElement("input"); Object.assign(r, { type: "range", min, max, step });
      const nb = numBox(step, (v) => { setP(S, path, v); r.value = v; applyStatic(); play(0); }, () => getP(S, path));
      const sync = () => { r.value = getP(S, path); nb.show(getP(S, path)); };
      r.oninput = () => { setP(S, path, +r.value); nb.show(+r.value); applyStatic(); render(+scrub.value || 0); };
      r.onchange = () => play(0);
      row.append(ctlName(label, unit), nb.el, r); refreshers.push(sync);
      return row;
    }
    for (const P of PANELS) {
      const sec = document.createElement("section");
      sec.className = "panel";
      const paths = [];
      const h = panelHead(sec, P.title, () => {
        for (const p of paths) setP(S, p, clone(getP(opts.defaults, p)));
        refreshers.forEach((f) => f()); applyStatic(); play(0);
      });
      if (P.toggle) {
        paths.push(P.toggle);
        const lab = document.createElement("label"); lab.className = "chk";
        const cb = document.createElement("input"); cb.type = "checkbox";
        lab.append(cb, "On"); h.insertBefore(lab, h.lastChild);
        const sync = () => { cb.checked = getP(S, P.toggle); sec.classList.toggle("off", !cb.checked); };
        cb.onchange = () => { setP(S, P.toggle, cb.checked); sync(); applyStatic(); play(0); };
        refreshers.push(sync);
      }
      const body = sec.querySelector(".body");
      const selects = (P.selects || []).map(([path, label, list]) => {
        paths.push(path);
        const row = document.createElement("label"); row.className = "ctl";
        const name = document.createElement("span"); name.textContent = label;
        const sel = document.createElement("select"); sel.style.gridColumn = "1 / -1";
        for (const [v, t] of list) { const o = document.createElement("option"); o.value = v; o.textContent = t; sel.append(o); }
        sel.onchange = () => { setP(S, path, sel.value); applyStatic(); play(0); };
        row.append(name, sel); refreshers.push(() => { sel.value = getP(S, path); });
        return row;
      });
      // The Bar & camera panel's in-game option goes last; the lab's own selects go first.
      const ours = P.title === "Bar & camera";
      if (!ours) body.append(...selects);
      for (const item of P.items || []) { paths.push(item[0]); body.append(fxSlider(item)); }
      for (const [path, label] of P.checks || []) {
        paths.push(path);
        const lab = document.createElement("label"); lab.className = "chk";
        const cb = document.createElement("input"); cb.type = "checkbox";
        cb.onchange = () => { setP(S, path, cb.checked); applyStatic(); render(+scrub.value || 0); };
        lab.append(cb, label); body.append(lab); refreshers.push(() => { cb.checked = getP(S, path); });
      }
      if (ours) { body.append(...selects); selects.forEach((x) => x.classList.add("ours")); }
      if (P.title === "Scene") {
        // The preview's own settings sit on the stage, under the presets.
        const row = document.createElement("div");
        row.className = "transport scene-row";
        row.setAttribute("aria-label", "Scene");
        const t = document.createElement("span"); t.className = "scene-label"; t.textContent = "Scene";
        row.append(t, ...body.children);
        [...host.querySelectorAll(".stage .transport")].pop().after(row);
        continue;
      }
      panelsEl.append(sec);
    }
    // The curve panel was written in the HTML; it folds up like the rest.
    const curvePanel = host.querySelector(".curve-wrap");
    const curveH = curvePanel.querySelector("h3");
    const curveBody = document.createElement("div"); curveBody.className = "body";
    curveBody.append(...[...curvePanel.children].filter((c) => c !== curveH));
    curvePanel.append(curveBody);
    curveH.remove();
    panelHead(curvePanel, "Spread speed curve", () => {
      for (const k of ["curveType", "curve", "points", "interp", "power", "spring", "steps"]) S[k] = clone(opts.defaults[k]);
      builtType = null; curveChanged(); play(0);
    });

    // -- effect presets ------------------------------------------------------------
    const userKey = "dc-lab-presets";
    const loadUser = () => { try { return JSON.parse(localStorage.getItem(userKey) || "{}") || {}; } catch (_) { return {}; } };
    const saveUser = (u) => { try { localStorage.setItem(userKey, JSON.stringify(u)); } catch (_) {} };
    const fxSel = el("fxPreset");
    const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    function fillPresets(selected) {
      const user = loadUser();
      fxSel.innerHTML = '<option value="">Effect presets…</option>' +
        '<optgroup label="Built-in">' + Object.keys(FX_PRESETS).map((k) => `<option value="b:${esc(k)}">${esc(k)}</option>`).join("") + "</optgroup>" +
        (Object.keys(user).length ? '<optgroup label="Your presets">' + Object.keys(user).map((k) => `<option value="u:${esc(k)}">${esc(k)}</option>`).join("") + "</optgroup>" : "");
      fxSel.value = selected || "";
      el("delPreset").disabled = !fxSel.value.startsWith("u:");
    }
    // A preset replaces the effect but keeps the preview's and the game's own settings.
    function loadEffect(obj, base) {
      const keep = Object.fromEntries(KEEP.map((k) => [k, S[k]]));
      S = merge(clone(opts.defaults), merge(clone(base), clone(obj)));
      Object.assign(S, keep);
      reload();
    }
    fxSel.onchange = () => {
      const v = fxSel.value;
      el("delPreset").disabled = !v.startsWith("u:");
      if (!v) return;
      const name = v.slice(2);
      if (v[0] === "b") loadEffect(FX_PRESETS[name], opts.defaults);
      else { loadEffect(loadUser()[name] || {}, opts.defaults); el("presetName").value = name; }
    };
    el("savePreset").onclick = () => {
      const name = el("presetName").value.trim();
      if (!name) { el("presetName").focus(); el("presetName").placeholder = "Type a name first"; return; }
      const user = loadUser(); user[name] = clone(S); saveUser(user);
      fillPresets("u:" + name);
    };
    el("delPreset").onclick = () => {
      const v = fxSel.value;
      if (!v.startsWith("u:")) return;
      const user = loadUser(); delete user[v.slice(2)]; saveUser(user);
      fillPresets("");
    };
    el("randomize").onclick = () => {
      const r = (a, b) => a + Math.random() * (b - a), coin = (p) => Math.random() < p, any = (a) => a[Math.floor(Math.random() * a.length)];
      loadEffect({
        curveType: "bezier", curve: any(Object.values(PRESETS)),
        direction: any(["center", "center", "ltr", "rtl", "edges"]), fadeCurve: any(["in", "linear", "out", "smooth"]),
        spread: Math.round(r(350, 1500)), hold: Math.round(r(100, 900)), fade: Math.round(r(400, 1400)),
        fill: { pulse: coin(0.3) ? +r(0.1, 0.4).toFixed(2) : 0, shimmer: coin(0.3) ? +r(0.3, 0.9).toFixed(2) : 0, shimmerSpeed: +r(0.5, 5).toFixed(1) },
        streak: { on: coin(0.6), intensity: +r(0.6, 1).toFixed(2), dur: Math.round(r(200, 600)) },
        flash: { on: coin(0.7), size: Math.round(r(60, 220)), height: Math.round(r(25, 120)) },
        waves: { on: coin(0.35), trail: coin(0.5) ? Math.round(r(40, 200)) : 0 },
        landing: { on: coin(0.4) }, sheen: { on: coin(0.3), angle: Math.round(r(-40, 40)) },
        particles: { on: coin(0.7), mode: any(["front", "burst", "bar"]), shape: any(["dot", "spark"]), count: Math.round(r(20, 160)),
                     speed: Math.round(r(20, 250)), rise: Math.round(r(-150, 150)), drag: +r(0, 5).toFixed(1), seed: Math.ceil(r(0, 100)) },
        jolt: +r(0, 0.6).toFixed(2), shake: coin(0.25) ? +r(1, 6).toFixed(1) : 0,
      }, S);
      fxSel.value = "";
    };
    fillPresets("");

    // -- the Boss bar HUD's settings on the stage ----------------------------------
    // They're edited on the Simplified tab; the stage's text follows the
    // colours, font, labels and show switches.
    const stage = {
      "hud.deaths_color": (v) => host.style.setProperty("--hud-text", v),
      "hud.deaths_label_color": (v) => host.style.setProperty("--hud-muted", v),
      "hud.pb_color": (v) => host.style.setProperty("--hud-accent", v),
      "hud.font": (v) => { host.querySelector(".lab-row.bottom").style.fontFamily = v; },
      "hud.label_deaths": (v) => { host.querySelectorAll(".meta")[0].firstChild.textContent = v; },
      "hud.label_pb": (v) => { host.querySelectorAll(".meta")[1].firstChild.textContent = v; },
      "hud.show_deaths": (v) => { host.querySelectorAll(".meta")[0].style.visibility = v ? "" : "hidden"; },
      "hud.show_pb": (v) => { host.querySelectorAll(".meta")[1].style.visibility = v ? "" : "hidden"; },
      "hud.show_mark": (v) => { el("pb").style.opacity = v ? "" : "0"; },
    };
    packColumns(panelsEl, [["Spread speed curve", "Timing", "Sheen sweep", "Bar & camera"],
      ["Particles", "Fill light", "Landing flash", "Grain / deband"], ["Origin flash", "Lens streak", "Outer glow", "Shockwave fronts"]]);

    // The jump menu: scroll the section to just under the sticky stage.
    const scroller = host;
    host.querySelector(".jump").addEventListener("click", (e) => {
      const a = e.target.closest("[data-jump]");
      if (!a) return;
      e.preventDefault();
      const target = host.querySelector(`[data-anchor="${a.dataset.jump}"]`);
      const stageH = host.querySelector(".stage").offsetHeight;
      scroller.scrollTo({ top: target.offsetTop - stageH - 8, behavior: "smooth" });
    });

    // -- settings JSON -----------------------------------------------------------
    const msg = (t) => { el("jsonMsg").textContent = t; };
    el("copy").onclick = async () => {
      try { await navigator.clipboard.writeText(dump.value); el("copy").textContent = "Copied"; }
      catch (_) { dump.select(); el("copy").textContent = "Press Ctrl+C"; }
      setTimeout(() => { el("copy").textContent = "Copy settings"; }, 1500);
    };
    el("reset").onclick = () => { S = clone(opts.defaults); reload(); };
    function importJSON(text) {
      let data;
      try { data = JSON.parse(text); } catch (e) { msg("Couldn't read that JSON: " + e.message); return; }
      S = merge(clone(opts.defaults), merge(clone(S), data));
      builtType = null;
      refreshers.forEach((f) => f()); curveChanged(); play(0);
      msg("Settings applied. Click Save at the top to keep them.");
    }
    el("apply").onclick = () => importJSON(dump.value);
    el("importBtn").onclick = () => el("importFile").click();
    el("importFile").onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      importJSON(await f.text()); e.target.value = "";
    };
    el("exportBtn").onclick = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(S, null, 2)], { type: "application/json" }));
      a.download = "hpbar-settings.json";
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };

    function resize() { if (!cv.getBoundingClientRect().width) return; sizeCanvas(cv); sizeCanvas(sp); drawCurve(null); }
    new ResizeObserver(resize).observe(cv);

    refreshers.push(showSpeed);
    refreshers.forEach((f) => f());
    curveChanged(false);

    return {
      // From the page: a revert, a reset or an import.
      set(v) { stop(); S = merge(clone(opts.defaults), v); builtType = null; refreshers.forEach((f) => f()); curveChanged(false); render(-1); },
      setVal(key, v) { if (stage[key]) stage[key](v); },
      shown() { resize(); curveChanged(false); render(-1); },
      hidden() { stop(); },
    };
  }

  return { build, merge };
})();
