// The custom NEW PB effect, from the "HP Bar Lab" (an advanced option on the
// settings page). Origin flashes, a lens streak, light spreading along the
// bar (from the centre, either end or both ends) on an editable speed curve,
// an outer glow, shockwave fronts, a landing flash, a sheen, sparks, grain,
// jolt and shake. It's driven frame by frame from JavaScript rather than CSS, so the
// spread can follow any curve.
//
// Sizes in the lab are in pixels for a bar 10px tall; here they're scaled by
// the real bar's height, so it looks the same on any screen.
window.DCFx = (function () {
  "use strict";
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const rgb = (h) => { const n = parseInt(String(h).slice(1), 16) || 0; return `${n >> 16 & 255}, ${n >> 8 & 255}, ${n & 255}`; };

  // -- speed curves (shared with the settings page's curve editor) ------------
  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    const solve = (x) => {
      let t = x;
      for (let i = 0; i < 8; i++) {
        const e = sx(t) - x, d = dx(t);
        if (Math.abs(e) < 1e-6) return t;
        if (Math.abs(d) < 1e-6) break;
        t -= e / d;
      }
      let lo = 0, hi = 1; t = x;
      for (let i = 0; i < 40; i++) { const v = sx(t); if (Math.abs(v - x) < 1e-6) break; if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; }
      return t;
    };
    return (x) => (x <= 0 ? 0 : x >= 1 ? 1 : sy(solve(x)));
  }

  // Through points: straight lines, monotone (no overshoot) or a spline.
  function pointsEase(pts, mode) {
    const P = pts.map((p) => [...p]).sort((a, b) => a[0] - b[0]);
    const n = P.length, xs = P.map((p) => p[0]), ys = P.map((p) => p[1]);
    const sec = [];
    for (let i = 0; i < n - 1; i++) sec.push((ys[i + 1] - ys[i]) / Math.max(1e-6, xs[i + 1] - xs[i]));
    const m = [];
    if (mode === "spline") {
      for (let i = 0; i < n; i++) m.push(i === 0 ? sec[0] : i === n - 1 ? sec[n - 2] : (ys[i + 1] - ys[i - 1]) / Math.max(1e-6, xs[i + 1] - xs[i - 1]));
    } else if (mode === "smooth") {  // Fritsch-Carlson monotone cubic
      m.push(sec[0]);
      for (let i = 1; i < n - 1; i++) m.push(sec[i - 1] * sec[i] <= 0 ? 0 : (sec[i - 1] + sec[i]) / 2);
      m.push(sec[n - 2]);
      for (let i = 0; i < n - 1; i++) {
        if (sec[i] === 0) { m[i] = m[i + 1] = 0; continue; }
        const a = m[i] / sec[i], b = m[i + 1] / sec[i], h = a * a + b * b;
        if (h > 9) { const t = 3 / Math.sqrt(h); m[i] = t * a * sec[i]; m[i + 1] = t * b * sec[i]; }
      }
    }
    return (x) => {
      if (x <= xs[0]) return ys[0];
      if (x >= xs[n - 1]) return ys[n - 1];
      let i = 0; while (i < n - 2 && x > xs[i + 1]) i++;
      const h = xs[i + 1] - xs[i], t = (x - xs[i]) / Math.max(1e-6, h);
      if (mode === "linear") return ys[i] + (ys[i + 1] - ys[i]) * t;
      const t2 = t * t, t3 = t2 * t;
      return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1];
    };
  }

  function buildEase(S) {
    switch (S.curveType) {
      case "linear": return (x) => clamp(x);
      case "points": return pointsEase(S.points, S.interp);
      case "power": {
        const e = S.power.exp;
        if (S.power.dir === "in") return (x) => Math.pow(clamp(x), e);
        if (S.power.dir === "inout") return (x) => ((x = clamp(x)) < 0.5 ? Math.pow(2 * x, e) / 2 : 1 - Math.pow(2 - 2 * x, e) / 2);
        return (x) => 1 - Math.pow(1 - clamp(x), e);
      }
      case "spring": {
        const w0 = Math.sqrt(S.spring.stiffness), z = S.spring.damping / (2 * w0);
        const T = Math.min(-Math.log(0.001) / Math.max(1e-3, z * w0), 30);
        if (z < 1) {
          const wd = w0 * Math.sqrt(1 - z * z);
          return (x) => (x >= 1 ? 1 : x <= 0 ? 0 : ((t) => 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + z * w0 / wd * Math.sin(wd * t)))(x * T));
        }
        return (x) => (x >= 1 ? 1 : x <= 0 ? 0 : ((t) => 1 - Math.exp(-w0 * t) * (1 + w0 * t))(x * T));
      }
      case "steps": {
        const n = S.steps.n;
        return S.steps.pos === "start" ? (x) => (x <= 0 ? 0 : Math.min(1, Math.ceil(x * n) / n)) : (x) => (x >= 1 ? 1 : Math.floor(clamp(x) * n) / n);
      }
      default: return bezier(...S.curve);
    }
  }

  const hexArr = (h) => { const n = parseInt(String(h).slice(1), 16) || 0; return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  const mixRgb = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(", ");
  // Shifts a colour's hue (degrees) and lightness (-1..1).
  function shiftColor([r, g, b], dh, dl) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    let h = 0; let l = (mx + mn) / 2;
    const sat = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
    if (d) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h = (h * 60 + dh + 360) % 360; l = clamp(l + dl * 0.5 * (dl > 0 ? 1 - l : l), 0, 1);
    const c = (1 - Math.abs(2 * l - 1)) * sat, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = l - c / 2;
    const [a, b2, c2] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
    return [a, b2, c2].map((v) => Math.round((v + m) * 255));
  }
  const FLASH_DECAY = {
    fast: (d) => Math.pow(1 - d, 3), quad: (d) => (1 - d) * (1 - d), linear: (d) => 1 - d,
    slow: (d) => 1 - d * d, smooth: (d) => 1 - d * d * (3 - 2 * d),
  };
  const FADES = { in: (f) => 1 - f * f, linear: (f) => 1 - f, out: (f) => (1 - f) * (1 - f), smooth: (f) => 1 - f * f * (3 - 2 * f) };

  // Where the light is at spread progress p, in % of the lit part: lit
  // ranges, moving edges [pos, dir] and start points [pos, dir].
  function geom(S, p) {
    const q = clamp(p, 0, 1.2) * S.reach / 100;
    switch (S.direction) {
      case "ltr": return { spans: [[0, 100 * q]], fronts: [[100 * q, 1]], origins: [[0, 1]] };
      case "rtl": return { spans: [[100 - 100 * q, 100]], fronts: [[100 - 100 * q, -1]], origins: [[100, -1]] };
      case "edges": {
        const h = Math.min(50 * q, 50);  // the two halves meet in the middle and stop there
        return { spans: [[0, h], [100 - h, 100]], fronts: h < 50 ? [[h, 1], [100 - h, -1]] : [], origins: [[0, 1], [100, -1]] };
      }
      default: return { spans: [[50 - 50 * q, 50 + 50 * q]], fronts: [[50 - 50 * q, -1], [50 + 50 * q, 1]], origins: [[50, 0]] };
    }
  }
  function mergeSpans(spans) {
    const out = [];
    for (const s of spans.filter(([a, b]) => b - a > 0.01).sort((x, y) => x[0] - y[0])) {
      const last = out[out.length - 1];
      if (last && s[0] <= last[1] + 0.01) last[1] = Math.max(last[1], s[1]);
      else out.push([...s]);
    }
    return out;
  }
  // 1 inside the lit spans, a soft ramp at moving edges, crisp at the bar's
  // ends. Ramps add up, so two edges closing in leave no dim seam.
  function maskFor(spans, s) {
    spans = spans.filter(([a, b]) => b - a > 0.01);
    if (!spans.length) return "linear-gradient(transparent, transparent)";
    const alpha = (x) => {
      let m = 0;
      for (const [a, b] of spans) {
        if (x >= a && x <= b) m += 1;
        else if (x < a) m += a > 0 && s > 0 ? clamp(1 - (a - x) / s) : 0;
        else m += b < 100 && s > 0 ? clamp(1 - (x - b) / s) : 0;
      }
      return clamp(m);
    };
    const xs = new Set([0, 100]);
    for (const [a, b] of spans) for (const v of [a, b, a - s, b + s, a - 0.01, b + 0.01]) xs.add(clamp(v, 0, 100));
    for (let i = 0; i <= 40; i++) xs.add(i * 2.5);
    const arr = [...xs].sort((p, q) => p - q);
    return `linear-gradient(90deg, ${arr.map((x) => `rgba(0,0,0,${alpha(x).toFixed(3)}) ${x.toFixed(3)}%`).join(", ")})`;
  }

  // Film grain (triangular noise, like a debander's dither), a few frames, made once.
  const GRAIN_SIZE = 192, GRAIN_FRAMES = 8;
  const grainCache = {};
  function grainFrames(mono) {
    if (grainCache[mono]) return grainCache[mono];
    const out = [];
    const c = document.createElement("canvas"); c.width = c.height = GRAIN_SIZE;
    const g = c.getContext("2d"), img = g.createImageData(GRAIN_SIZE, GRAIN_SIZE), d = img.data;
    const tpdf = () => (Math.random() + Math.random()) * 127.5;
    for (let f = 0; f < GRAIN_FRAMES; f++) {
      for (let i = 0; i < d.length; i += 4) {
        const v = tpdf();
        d[i] = v; d[i + 1] = mono ? v : tpdf(); d[i + 2] = mono ? v : tpdf(); d[i + 3] = 255;
      }
      g.putImageData(img, 0, 0);
      out.push(`url(${c.toDataURL()})`);
    }
    return (grainCache[mono] = out);
  }

  // -- the effect on a bar ----------------------------------------------------
  const runs = new WeakMap();  // bar element -> its layers and the running animation

  function layers(bar) {
    let L = runs.get(bar);
    if (L) return L;
    const root = document.createElement("div");
    root.className = "fx-root";
    const flash = '<div class="fx fx-flashc"><div class="fx-bloom"></div></div>';
    const wave = '<div class="fx fx-wave"><div class="fx-tail"></div><div class="fx-head"></div></div>';
    root.innerHTML =
      '<div class="fx-frame"><div class="fx-fill"><div class="fx-light"><div class="fx-warm"></div><div class="fx-pale"></div><div class="fx-shim"></div></div>' +
      '<div class="fx-sheen"></div></div></div>' +
      '<div class="fx-box"><div class="fx fx-aura"></div><div class="fx fx-aura"></div>' +
      '<div class="fx fx-ana"><div class="fx-ana-soft"></div><div class="fx-ana-line"></div></div>' +
      flash + flash + wave + wave + '</div>' +
      '<canvas class="fx-parts"></canvas><div class="fx-grain"></div>';
    bar.appendChild(root);
    const q = (s) => root.querySelector(s), qa = (s) => [...root.querySelectorAll(s)];
    L = { root, frame: q(".fx-frame"), fill: q(".fx-fill"), light: q(".fx-light"), warm: q(".fx-warm"), pale: q(".fx-pale"),
          shim: q(".fx-shim"), sheen: q(".fx-sheen"), box: q(".fx-box"), auras: qa(".fx-aura"), ana: q(".fx-ana"),
          anaSoft: q(".fx-ana-soft"), anaLine: q(".fx-ana-line"), flashes: qa(".fx-flashc"), waves: qa(".fx-wave"),
          canvas: q(".fx-parts"), grain: q(".fx-grain"), raf: 0 };
    runs.set(bar, L);
    return L;
  }

  // Sparks are generated from a seed and placed by age, like in the lab, so
  // scrubbing the timeline shows the same sparks as playback.
  function genParticles(S, ease) {
    const P = S.particles;
    let s = (P.seed * 2654435761) >>> 0 || 1;
    const rnd = () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const pick = (list) => list[Math.min(list.length - 1, Math.floor(rnd() * list.length))];
    const parts = []; let end = 0;
    const baseCol = hexArr(S.partColor);
    for (let i = 0; i < P.count; i++) {
      let spawn, xf, vx, vy;
      if (P.mode === "burst") {
        spawn = rnd() * 60;
        const [pos, dir] = pick(geom(S, 0).origins);
        const d = dir || (rnd() < 0.5 ? -1 : 1);
        xf = pos / 100 + d * rnd() * 0.015;
        vx = d * P.speed * (0.4 + rnd() * 1.6);
        vy = -P.speed * P.jitter * (rnd() * 1.2 - 0.2);
      } else if (P.mode === "bar") {
        spawn = rnd() * (S.spread + S.hold);
        const spans = mergeSpans(geom(S, ease(clamp(spawn / S.spread))).spans);
        const [a, b] = spans.length ? pick(spans) : [50, 50];
        xf = (a + rnd() * (b - a)) / 100;
        vx = (rnd() - 0.5) * P.speed * P.jitter;
        vy = -P.speed * (0.3 + rnd() * 0.7);
      } else {  // the spreading front
        spawn = rnd() * S.spread * 0.9;
        const g = geom(S, ease(clamp(spawn / S.spread)));
        const [pos, dir] = g.fronts.length ? pick(g.fronts) : [50, rnd() < 0.5 ? -1 : 1];
        xf = pos / 100;
        vx = dir * P.speed * (0.3 + rnd() * 0.7);
        vy = (rnd() - 0.7) * P.speed * P.jitter * 2;
      }
      spawn += P.delay;
      const life = P.life * (0.6 + rnd() * 0.8);
      // Colour variation: each spark gets its own hue and lightness, and its core takes on the tint.
      const tint = shiftColor(baseCol, (rnd() * 2 - 1) * 70 * P.colorVar, (rnd() * 2 - 1) * P.colorVar);
      const halo = tint.join(", "), core = mixRgb([255, 248, 230], tint, 0.65 * P.colorVar);
      parts.push({ spawn, xf, vx, vy, life, size: P.size * (0.6 + rnd() * 0.8), flick: rnd() * 6.28, yOff: (rnd() - 0.5) * 8, halo, core });
      end = Math.max(end, spawn + life);
    }
    return { parts, end: P.on ? end : 0 };
  }

  function setup(L, S, k, lit, grainHost) {
    const P = rgb(S.pale), W = rgb(S.warm), G = rgb(S.glowColor), C = rgb(S.coreColor);
    const px = (v) => v * k + "px";
    L.fill.style.width = L.box.style.width = lit * 100 + "%";
    const e = S.fill.endFade, cw = S.fill.coreWidth / 2;
    L.pale.style.background =
      `linear-gradient(90deg, rgba(${P},${e > 0 ? 0 : .75}) 0%, rgba(${P},.75) ${e}%, rgba(${P},.95) 50%, rgba(${P},.75) ${100 - e}%, rgba(${P},${e > 0 ? 0 : .75}) 100%)`;
    L.warm.style.background =
      `linear-gradient(transparent ${50 - cw}%, rgba(${C},${S.coreLine}) 50%, transparent ${50 + cw}%),` +
      `linear-gradient(90deg, rgba(${W},${e > 0 ? 0 : .5}) 0%, rgba(${W},.5) ${e}%, rgba(${W},.85) 50%, rgba(${W},.5) ${100 - e}%, rgba(${W},${e > 0 ? 0 : .5}) 100%)`;
    L.shim.style.background = `repeating-linear-gradient(105deg, transparent 0px, transparent ${px(26)}, rgba(${C},.55) ${px(40)}, transparent ${px(54)}, transparent ${px(84)})`;
    Object.assign(L.sheen.style, { width: S.sheen.width + "%", top: px(-10), bottom: px(-10),
      background: `linear-gradient(90deg, transparent, rgba(${C},.95) 50%, transparent)` });
    for (const a of L.auras) Object.assign(a.style, { height: px(S.glow.height), top: `calc(50% + ${px(S.glow.offsetY)})`,
      filter: `blur(${px(S.glow.blur)})`,
      background: `radial-gradient(ellipse closest-side, rgba(${G},.65) 0%, rgba(${G},.3) 30%, rgba(${G},.08) 60%, transparent 85%)` });
    const anchor = { ltr: ["0%", "0%", "0% 50%"], rtl: ["100%", "-100%", "100% 50%"] }[S.direction] || ["50%", "-50%", "50% 50%"];
    Object.assign(L.ana.style, { width: S.streak.length + "%", height: px(60), left: anchor[0], transformOrigin: anchor[2],
      filter: S.streak.blur > 0 ? `blur(${px(S.streak.blur)})` : "" });
    L.ana.dataset.tx = anchor[1];
    Object.assign(L.anaLine.style, { width: "100%", height: px(S.streak.thickness),
      background: `radial-gradient(ellipse closest-side, #fff 0%, rgba(${P},1) 25%, rgba(${G},.7) 60%, transparent 100%)` });
    Object.assign(L.anaSoft.style, { width: "100%", height: px(S.streak.thickness * 3.5), filter: `blur(${px(3)})`,
      background: `radial-gradient(ellipse closest-side, rgba(${P},.8) 0%, rgba(${G},.35) 45%, transparent 100%)` });
    const F = S.flash;
    for (const f of L.flashes) Object.assign(f.firstChild.style, { width: px(F.size), height: px(F.height), filter: `blur(${px(F.blur)})`,
      background: `radial-gradient(ellipse closest-side, rgba(${C},1) 0%, rgba(${P},.75) 20%, rgba(${G},.32) 48%, rgba(${G},.08) 75%, transparent 100%)` });
    for (const w of L.waves) {
      Object.assign(w.querySelector(".fx-head").style, { width: px(S.waves.size), height: px(S.waves.size * 0.65), filter: `blur(${px(2)})`,
        background: `radial-gradient(ellipse closest-side, rgba(255,252,235,1) 0%, rgba(${P},.75) 30%, rgba(${G},.25) 65%, transparent 100%)` });
      Object.assign(w.querySelector(".fx-tail").style, { width: px(S.waves.trail), height: px(Math.max(3, S.waves.size * 0.28)),
        filter: `blur(${px(2)})`, background: `linear-gradient(90deg, transparent, rgba(${P},.65))`, display: S.waves.trail > 0 ? "" : "none" });
    }
    // The spark canvas reaches 10 bar-heights past each end and above and below.
    Object.assign(L.canvas.style, { left: px(-100), top: px(-100), width: `calc(100% + ${px(200)})`, height: px(210) });
    const Gr = S.grain;
    const host = Gr.area === "full" && grainHost ? grainHost : L.root;
    if (L.grain.parentElement !== host) host.append(L.grain);
    L.grain.classList.toggle("fx-grain-full", host !== L.root);
    L.grainFrames = Gr.on ? grainFrames(Gr.mono) : [];
    Object.assign(L.grain.style, { mixBlendMode: Gr.blend, backgroundSize: `${GRAIN_SIZE * Gr.size}px`,
      imageRendering: Gr.size > 1 ? "pixelated" : "auto", opacity: Gr.on ? Gr.amount : 0,
      backgroundImage: Gr.on ? L.grainFrames[0] : "none" });
    if (host === L.root) Object.assign(L.grain.style, { left: px(-100), top: px(-100), width: `calc(100% + ${px(200)})`, height: px(210) });
    else Object.assign(L.grain.style, { left: "0", top: "0", width: "100%", height: "100%" });
  }

  function frame(L, S, ease, sparks, k, t, shakeEl) {
    const playing = t >= 0;
    const x = clamp(t / S.spread);
    const p = playing ? ease(x) : 0;
    const G = geom(S, p);
    const px = (v) => v * k + "px";

    // Full during spread and hold, then fades on its curve; an optional pulse while held.
    const fadeT = clamp((t - S.spread - S.hold) / S.fade);
    let I = playing ? (FADES[S.fadeCurve] || FADES.in)(fadeT) : 0;
    if (S.fill.pulse > 0 && t > S.spread) I *= 1 - S.fill.pulse * 0.5 * (1 - Math.cos(2 * Math.PI * (t - S.spread) / 1000 * S.fill.pulseRate));
    // The landing flash when the spread completes.
    const Ld = S.landing.on && playing && t >= S.spread ? clamp(1 - (t - S.spread) / S.landing.dur) * S.landing.intensity : 0;

    L.light.style.maskImage = L.light.style.webkitMaskImage = playing ? maskFor(G.spans, S.soft) : "linear-gradient(transparent, transparent)";
    L.light.style.filter = `brightness(${S.fill.brightness * (1 + Ld)})`;
    L.warm.style.opacity = I;
    L.pale.style.opacity = I * (S.colorShift > 0 ? 1 - clamp(t / S.colorShift) : 0);
    L.shim.style.opacity = S.fill.shimmer * I;
    L.shim.style.backgroundPosition = `${(t * 0.12 * S.fill.shimmerSpeed * k) % (84 * k)}px 0`;

    if (S.sheen.on && playing) {
      const u = (t - S.spread - S.sheen.delay) / S.sheen.dur;
      const w = S.sheen.width, back = S.direction === "rtl";
      L.sheen.style.left = -w + (100 + 2 * w) * clamp(back ? 1 - u : u) + "%";
      L.sheen.style.transform = `translateX(-50%) skewX(${-S.sheen.angle}deg)`;
      L.sheen.style.opacity = u > 0 && u < 1 ? S.sheen.intensity * Math.sin(Math.PI * u) : 0;
    } else L.sheen.style.opacity = 0;

    // The outer glow over each lit span, kept per half so it never jumps when the halves meet.
    L.auras.forEach((au, i) => {
      const sp = G.spans[i];
      if (!sp || !S.glow.on || !playing) { au.style.opacity = 0; return; }
      const w = Math.max(sp[1] - sp[0], S.direction === "center" ? 6 : 0);
      au.style.left = (sp[0] + sp[1]) / 2 + "%";
      au.style.width = `calc(${w}% + ${px(2 * S.glow.overscan)})`;
      au.style.transform = "translate(-50%, -50%)";
      au.style.opacity = clamp(I * S.glow.intensity * (1 + Ld * 0.6));
    });

    const ts = t - S.streak.delay;
    const st = clamp(1 - ts / S.streak.dur);
    const open = 1 - Math.pow(1 - clamp(ts / Math.max(1, S.streak.open)), 3);
    L.ana.style.opacity = S.streak.on && playing && ts >= 0 ? Math.pow(st, 1.5) * S.streak.intensity : 0;
    L.ana.style.transform = `translate(${L.ana.dataset.tx || "-50%"}, -50%) scaleX(${0.3 + 0.7 * open})`;

    const F = S.flash, tf = t - F.delay;
    const fEnv = tf < 0 ? 0 : tf < F.attack ? tf / Math.max(1, F.attack) : (FLASH_DECAY[F.decay] || FLASH_DECAY.quad)(clamp((tf - F.attack) / Math.max(1, F.dur)));
    const flick = F.flicker > 0 ? 1 - F.flicker * (0.5 + 0.5 * Math.sin(tf * 0.083) * Math.sin(tf * 0.231 + 1.3)) : 1;
    const grow = F.growFrom + (F.growTo - F.growFrom) * (1 - Math.pow(1 - clamp(tf / Math.max(1, F.attack + F.dur)), 3));
    L.flashes.forEach((f, i) => {
      const o = G.origins[i];
      if (!o || !F.on || !playing || tf < 0) { f.style.opacity = 0; return; }
      f.style.opacity = 1;
      f.style.left = `calc(${o[0]}% + ${px(o[1] * F.inset)})`;
      const b = f.firstChild.style;
      b.opacity = clamp(fEnv * flick * F.intensity);
      b.transform = `translate(-50%, -50%) scale(${grow})`;
    });

    const wo = S.waves.on && playing ? S.waves.intensity * Math.pow(1 - x, 0.8) * I : 0;
    L.waves.forEach((w, i) => {
      const fr = G.fronts[i];
      if (!fr) { w.style.opacity = 0; return; }
      w.style.left = fr[0] + "%";
      w.style.transform = `scaleX(${fr[1]})`;
      w.style.opacity = wo;
    });

    const j = playing ? clamp(1 - t / S.joltDur) : 0;
    L.frame.style.transform = `scaleY(${1 + S.jolt * j * j})`;
    if (shakeEl) {
      const sk = playing && S.shake > 0 ? clamp(1 - t / S.shakeDur) : 0;
      const a = S.shake * k * sk * sk;
      shakeEl.style.transform = sk > 0 ? `translate(${(a * Math.sin(t * 0.11)).toFixed(2)}px, ${(a * 0.5 * Math.cos(t * 0.137)).toFixed(2)}px)` : "";
    }

    drawSparks(L, S, sparks, k, t);

    if (S.grain.on && L.grainFrames.length && playing && S.grain.fps > 0) {
      const fi = Math.floor(t / 1000 * S.grain.fps);
      L.grain.style.backgroundImage = L.grainFrames[fi % GRAIN_FRAMES];
      L.grain.style.backgroundPosition = `${(fi * 37) % GRAIN_SIZE}px ${(fi * 71) % GRAIN_SIZE}px`;
    }
  }

  function drawSparks(L, S, sparks, k, t) {
    const c = L.canvas, r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    if (c.width !== Math.round(r.width * d) || c.height !== Math.round(r.height * d)) { c.width = Math.round(r.width * d); c.height = Math.round(r.height * d); }
    const g = c.getContext("2d");
    g.setTransform(d, 0, 0, d, 0, 0);
    g.clearRect(0, 0, r.width, r.height);
    const P = S.particles;
    if (!P.on || t < 0) return;
    const fb = L.box.getBoundingClientRect();
    const x0 = fb.left - r.left, cy = fb.top - r.top + fb.height / 2;
    g.globalCompositeOperation = "lighter";
    g.lineCap = "round";
    for (const p of sparks) {
      const ageMs = t - p.spawn;
      if (ageMs < 0 || ageMs > p.life) continue;
      const a = ageMs / 1000, q = ageMs / p.life, dr = P.drag;
      const f = dr > 0 ? (1 - Math.exp(-dr * a)) / dr : a, decay = Math.exp(-dr * a);
      const x = x0 + p.xf * fb.width + p.vx * k * f;
      const y = cy + p.yOff * k + p.vy * k * f - 0.5 * P.rise * k * a * a;
      const tw = 1 - P.twinkle + P.twinkle * (0.5 + 0.5 * Math.sin(p.flick + t * 0.03));
      const alpha = P.intensity * Math.pow(1 - q, 1.3) * tw;
      const rad = Math.max(0.1, p.size * k * (1 - (1 - P.sizeEnd) * q));
      if (P.shape === "spark") {
        const vx = p.vx * decay, vy = p.vy * decay - P.rise * a, sp = Math.hypot(vx, vy) || 1;
        const len = sp * k * 0.03 * P.stretch + rad;
        const x2 = x - vx / sp * len, y2 = y - vy / sp * len;
        g.strokeStyle = `rgba(${p.halo},${alpha * 0.3})`; g.lineWidth = rad * 3;
        g.beginPath(); g.moveTo(x, y); g.lineTo(x2, y2); g.stroke();
        g.strokeStyle = `rgba(${p.core},${alpha})`; g.lineWidth = rad * 1.1;
        g.beginPath(); g.moveTo(x, y); g.lineTo(x2, y2); g.stroke();
      } else {
        g.fillStyle = `rgba(${p.halo},${alpha * 0.25})`;
        g.beginPath(); g.arc(x, y, rad * 3, 0, 7); g.fill();
        g.fillStyle = `rgba(${p.core},${alpha})`;
        g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill();
      }
    }
  }

  // The settings page's slow-mo (preview only): 1 = real speed.
  let rate = 1;
  const setRate = (r) => { rate = r; };

  // Gets the effect ready on `bar` and returns its length and a way to draw
  // any moment of it (the Advanced tab's timeline scrubs with this). `lit` is
  // how much of the bar, from the left, the light spreads over (1 = all).
  // opts: shakeEl (what the screen shake moves), grainHost (what "whole
  // preview" grain covers; without it grain stays around the bar).
  function prepare(bar, S, lit, opts = {}) {
    const L = layers(bar);
    cancelAnimationFrame(L.raf);
    const k = Math.max(0.2, bar.getBoundingClientRect().height / 10);
    const ease = buildEase(S);
    const sp = genParticles(S, ease);
    const total = Math.ceil(Math.max(S.spread + S.hold + S.fade,
      S.streak.on ? S.streak.delay + S.streak.dur : 0,
      S.flash.on ? S.flash.delay + S.flash.attack + S.flash.dur : 0,
      S.sheen.on ? S.spread + S.sheen.delay + S.sheen.dur : 0,
      sp.end, S.joltDur, S.shake > 0 ? S.shakeDur : 0));
    setup(L, S, k, clamp(lit == null ? 1 : lit, 0.02, 1), opts.grainHost);
    L.root.style.display = "";
    L.shakeEl = opts.shakeEl;
    return { total, ease, draw: (t) => frame(L, S, ease, sp.parts, k, t, opts.shakeEl) };
  }

  // Plays the effect once on `bar`.
  function play(bar, S, lit, opts) {
    const fx = prepare(bar, S, lit, opts);
    const L = runs.get(bar);
    let t = 0, last = performance.now();
    const tick = (now) => {
      t += (now - last) * rate;
      last = now;
      if (t >= fx.total) { stop(bar); return; }
      fx.draw(t);
      L.raf = requestAnimationFrame(tick);
    };
    L.raf = requestAnimationFrame(tick);
    return fx.total;
  }

  function stop(bar) {
    const L = runs.get(bar);
    if (!L) return;
    cancelAnimationFrame(L.raf);
    L.root.style.display = "none";
    if (L.shakeEl) L.shakeEl.style.transform = "";
  }

  return { play, stop, prepare, buildEase, setRate };
})();
