// HUD overlay: lines up with the game's own boss bar, using the bar region
// from the game profile. Read-only, like the box overlay.
// URL options: ?always=1 (stay visible between fights)  ?hide=deaths,pb,phase,mark
//              ?banner=0 (no NEW PB / DEFEATED callouts)  ?demo=pb|live|first|kill|death (preview)
// The look and most of these options can also be set on the settings page
// (`soulsoverlay settings`), which applies here live through style.js.
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const $ = (id) => document.getElementById(id);
  const hud = $("hud");
  const urlHides = (params.get("hide") || "").split(",").filter(Boolean).map((h) => h.replace(/[^a-z-]/g, ""));
  for (const h of urlHides) hud.classList.add("hide-" + h);
  const preview = params.get("preview") === "1";  // inside the settings page
  const always = () => params.get("always") === "1" || DCStyle.value("hud.always") === true;
  const bannersOn = () => params.get("banner") !== "0" && DCStyle.value("hud.callouts") !== false;
  const cssVar = (n) => parseFloat(getComputedStyle(document.documentElement).getPropertyValue(n));
  const lingerMs = () => 1000 * (cssVar("--linger") || 0);
  const deathHoldMs = () => 1000 * (cssVar("--death-hold") || 0);

  let state = null;
  let lastEngaged = 0;
  let holdUntil = 0;  // a callout keeps the HUD up until it has played
  let barUp = false;
  // Live PB: Elden Ring hides the boss bar the moment you die, before "YOU
  // DIED", so waiting for the death to show a new PB means showing it on an
  // empty screen. Instead, as soon as the boss's live health drops past the
  // PB in this attempt, celebrate on the bar and let the marker ride the
  // health down. The death then just confirms it.
  let attempt = { celebrated: false, below: 0, wasEngaged: false };
  let lastAttemptCelebrated = false;  // the death's own new_pb event comes after it
  let hideTimer = null;
  let rate = 1;  // the settings page's slow-mo; always 1 in OBS
  const slow = (ms) => ms / rate;
  let calloutKind = "";

  const pct = (v) => (v * 100).toFixed(3) + "%";
  const fmtPct = (p) => (p == null ? "?" : (p < 10 ? p.toFixed(1) : Math.round(p)) + "%");

  function place(layout) {
    const b = layout && layout.bar;
    if (!b) return false;
    const [x, y, w, h] = b;
    Object.assign($("bar").style, { left: pct(x), top: pct(y), width: pct(w), height: pct(h) });
    const under = $("under");
    Object.assign(under.style, { left: pct(x), width: pct(w), top: `calc(${pct(y + h)} + var(--gap))` });
    const callout = $("callout");
    Object.assign(callout.style, { left: pct(x), width: pct(w), top: `calc(${pct(y + h)} + var(--gap) + 1.9em)` });
    return true;
  }

  function setVisible(on) {
    clearTimeout(hideTimer);
    if (on) hud.classList.add("visible");
    else {
      const wait = Math.max(slow(lingerMs()) - (Date.now() - lastEngaged), holdUntil - Date.now(), 0);
      if (wait) hideTimer = setTimeout(() => hud.classList.remove("visible"), wait);
      else hud.classList.remove("visible");
    }
  }

  function render() {
    if (!state) return;
    const ok = place(state.layout);
    const boss = state.boss;
    if (!ok || !boss) { setVisible(false); return; }

    $("deaths").textContent = boss.deaths;
    const pb = boss.pb;
    const multi = (boss.max_phases || (pb && pb.phase) || 1) > 1;
    $("pb").textContent = !pb ? "–" : pb.killed ? "Defeated" : fmtPct(pb.pct) + (multi ? ` · P${pb.phase}` : "");
    $("phase").textContent = boss.engaged && boss.max_phases > 1 && boss.phase ? `Phase ${boss.phase}/${boss.max_phases}` : "";

    if (boss.engaged && !attempt.wasEngaged) {
      attempt = { celebrated: false, below: 0, wasEngaged: true };
      lastAttemptCelebrated = false;
    }
    if (!boss.engaged) attempt.wasEngaged = false;

    // Beating the PB right now? A later phase than the PB counts outright.
    const live = boss.engaged ? boss.live_pct : null;
    const beating = !!(pb && !pb.killed && pb.pct != null && live != null && boss.phase &&
      (boss.phase > pb.phase || (boss.phase === pb.phase && live < pb.pct - 0.5)));
    attempt.below = beating ? attempt.below + 1 : 0;
    if (attempt.below >= 2 && !attempt.celebrated) {  // two readings in a row, not one odd frame
      attempt.celebrated = true;
      celebrate(live, boss.phase);
    }

    // The HUD comes and goes with the game's own bar. Older agents don't
    // send bar_up, so fall back to the fight being on.
    barUp = boss.bar_up !== undefined ? !!boss.bar_up : !!boss.engaged;

    // The marker sits on the game's bar, so it only shows while that bar is up,
    // and only on the bar of the phase the PB is in.
    const mark = $("pb-mark");
    // First attempt at a boss: no PB yet, so the marker rides the health
    // down to show where the first PB will land.
    const firstTry = !pb && live != null;
    const liveMark = (attempt.celebrated || firstTry) && live != null;
    const showMark = barUp && (liveMark ||
      (pb && !pb.killed && pb.pct != null && (!boss.phase || boss.phase === pb.phase)));
    mark.classList.toggle("on", !!showMark);
    mark.classList.toggle("live", !!liveMark);
    if (showMark) mark.style.left = `calc(${liveMark ? live : pb.pct}% - var(--mark-width) / 2)`;
    if (liveMark) {
      $("pb").textContent = fmtPct(live) + (multi ? ` · P${boss.phase}` : "");
      if (calloutKind === "pb") $("callout-sub").textContent = pbSub(live, boss.phase);
    }

    if (barUp) lastEngaged = Date.now();
    if (scene) scene.update(state, barUp);
    setVisible(always() || barUp);
  }

  function bump(el) {
    el.classList.remove("bump");
    void el.offsetWidth;
    el.classList.add("bump");
  }

  function callout(kind, sub, hold) {
    if (!bannersOn()) return;
    // DEFEATED can outlast the bar, so it holds the HUD up while it
    // plays. NEW PB sits on the bar and leaves with it.
    if (hold) {
      holdUntil = Date.now() + slow(4500);  // the length of the callout animation
      setVisible(true);
    }
    calloutKind = kind;
    $("callout-title").textContent = DCStyle.text(kind === "pb" ? "hud.label_new_pb" : "hud.label_defeated");
    $("callout-sub").textContent = sub || "";
    const c = $("callout");
    c.classList.toggle("defeated", kind !== "pb");
    c.classList.remove("show");
    void c.offsetWidth;
    c.classList.add("show");
    setVisible(always() || barUp);
  }

  // Under NEW PB: the new best, which keeps counting down with the boss's
  // health for as long as the callout is up.
  function pbSub(pctValue, phase) {
    const multi = state && state.boss && state.boss.max_phases > 1;
    return (pctValue != null ? fmtPct(pctValue) : "") + (multi ? ` · Phase ${phase}` : "");
  }

  function celebrate(pctValue, phase) {
    const fx = DCStyle.value("hud.fx");
    if (fx && window.DCFx) {
      // The custom effect, over the whole bar or just the health that's left.
      DCFx.play($("bar"), fx, fx.area === "health" && pctValue != null ? pctValue / 100 : 1, { shakeEl: $("hud") });
    } else {
      const s = $("shine");
      s.classList.remove("go");
      void s.offsetWidth;
      s.classList.add("go");
    }
    callout("pb", pbSub(pctValue, phase));
  }

  function onEvent(ev) {
    if (ev.type === "death") {
      // The game hides its bar as YOU DIED fades in, so the marker is already
      // gone; keep the text up just long enough to see the count go up.
      lastAttemptCelebrated = attempt.celebrated;
      attempt = { celebrated: false, below: 0, wasEngaged: false };
      holdUntil = Math.max(holdUntil, Date.now() + slow(deathHoldMs()));
      setVisible(true);
      bump($("deaths"));
      setVisible(always() || barUp);
    }
    if (ev.type === "new_pb" && !attempt.celebrated && !lastAttemptCelebrated && barUp) {
      // Only if the live check missed it (no health readings this attempt),
      // and only while there is still a bar to put it on.
      lastAttemptCelebrated = true;
      celebrate(ev.pct, ev.phase);
    }
    // DEFEATED goes up the moment the bar hits 0% ("defeated"); the kill
    // itself is only saved a moment later, once the boss has left the screen.
    if ((ev.type === "defeated" || (ev.type === "kill" && !ev.shown)) && ev.first_kill) {
      const d = ev.boss_deaths != null ? ev.boss_deaths : state && state.boss ? state.boss.deaths : null;
      callout("kill", d != null ? `after ${d} death${d === 1 ? "" : "s"}` : "", true);
    }
    if (ev.type === "defeated_cancel" && calloutKind === "kill") {
      // YOU DIED with the boss still on screen: it had a sliver left.
      $("callout").classList.remove("show");
      calloutKind = "";
      holdUntil = 0;
      setVisible(always() || barUp);
    }
  }

  let delay = 500;
  function connect() {
    const ws = new WebSocket(`ws://${location.host}/overlay/ws`);
    ws.onopen = () => { delay = 500; };
    ws.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.kind === "state") { state = msg.state; render(); }
      else if (msg.kind === "event") onEvent(msg.event);
      else if (msg.kind === "settings") { DCStyle.apply(msg.values); render(); }
    };
    ws.onclose = () => { setTimeout(connect, delay); delay = Math.min(delay * 2, 10000); };
  }

  // -- demo and the settings page's preview ---------------------------------
  const DEMO_LAYOUT = { bar: [0.2422, 0.8035, 0.5184, 0.0076], name: [0.2383, 0.7722, 0.33, 0.0257] };
  let demoTimers = [];
  let scene = null;

  function runDemo(demo, layout) {
    demoTimers.forEach((t) => { clearTimeout(t); clearInterval(t); });
    demoTimers = [];
    const later = (ms, fn) => demoTimers.push(setTimeout(fn, slow(ms)));
    attempt = { celebrated: false, below: 0, wasEngaged: true };
    lastAttemptCelebrated = false;
    holdUntil = 0;
    for (const id of ["shine", "callout"]) $(id).classList.remove("go", "show");
    if (window.DCFx) DCFx.stop($("bar"));
    $("deaths").classList.remove("bump");
    state = {
      layout: layout || DEMO_LAYOUT,
      boss: { name: "Morgott, the Omen King", engaged: true, bar_up: true, phase: 1, max_phases: null,
              deaths: 37, pb: { phase: 1, pct: 23.4, killed: false }, live_pct: demo === "idle" ? 61 : 40 },
    };
    if (demo === "first") Object.assign(state.boss, { deaths: 0, pb: null });
    if (!scene || demo === "pb") delete state.boss.live_pct;
    render();
    if (demo === "pb") later(400, () => onEvent({ type: "new_pb", pct: 21.8, phase: 1 }));
    if (demo === "live" || demo === "first") {
      // Health drains past the PB at 23.4% and keeps going (or, on a first
      // attempt, the marker just follows it).
      let hp = 40;
      const tick = setInterval(() => {
        hp -= 1.2;
        state.boss.live_pct = hp;
        render();
        if (hp < 12) clearInterval(tick);
      }, slow(120));
      demoTimers.push(tick);
    }
    if (demo === "kill") {
      if (scene) Object.assign(state.boss, { live_pct: 9, pb: { phase: 1, pct: 6.2, killed: false } });
      later(300, () => { state.boss.live_pct = 0; render(); onEvent({ type: "defeated", first_kill: true }); });
      later(900, () => { state.boss.bar_up = false; state.boss.engaged = false; render(); });
      later(1800, () => onEvent({ type: "kill", first_kill: true, shown: true }));
    }
    if (demo === "death") {
      // As in game: the counter spots YOU DIED as it fades in, and the bar
      // goes most of a second later.
      if (scene) later(300, () => { state.boss.live_pct = 52; render(); });
      later(1500, () => { onEvent({ type: "death" }); Object.assign(state.boss, { deaths: state.boss.deaths + 1, engaged: false }); render(); });
      later(2200, () => { state.boss.bar_up = false; render(); });
    }
  }

  // A stand-in for the game's own boss bar and name, under the HUD.
  function makeScene() {
    const el = document.createElement("div");
    el.className = "preview-scene";
    el.innerHTML = '<div class="pv-name"></div><div class="pv-bar"><div class="pv-trail"></div><div class="pv-fill"></div></div>';
    document.body.prepend(el);
    const box = (node, r) => Object.assign(node.style, { left: pct(r[0]), top: pct(r[1]), width: pct(r[2]), height: pct(r[3]) });
    return {
      update(st, up) {
        const b = st.boss, l = st.layout || {};
        if (l.bar) box(el.querySelector(".pv-bar"), l.bar);
        if (l.name) {
          const n = el.querySelector(".pv-name");
          box(n, l.name);
          n.style.fontSize = `${l.name[3] * 70}vh`;
          n.textContent = b ? b.name : "";
        }
        const hp = b && b.live_pct != null ? b.live_pct : 100;
        el.querySelector(".pv-fill").style.width = hp + "%";
        el.querySelector(".pv-trail").style.width = hp + "%";
        el.classList.toggle("bar-down", !up);
      },
    };
  }

  function startPreview() {
    scene = makeScene();
    DCStyle.apply({});
    let layout = null;
    // Only the settings page on this same server may drive the preview.
    window.addEventListener("message", (e) => {
      if (e.origin !== location.origin || e.source !== window.parent || !e.data) return;
      const msg = e.data;
      if (msg.type === "values") { DCStyle.apply(msg.values); render(); }
      if (msg.type === "play") { layout = msg.layout || layout; runDemo(msg.scenario, layout); }
      if (msg.type === "scene") document.querySelector(".preview-scene").dataset.bg = msg.bg || "dark";
      if (msg.type === "rate") { rate = Math.min(1, Math.max(0.05, +msg.rate || 1)); if (window.DCFx) DCFx.setRate(rate); }
    });
    // Slow-mo: every CSS animation and transition plays at the chosen rate.
    const slowAll = () => {
      for (const a of document.getAnimations()) if (a.playbackRate !== rate) a.playbackRate = rate;
      requestAnimationFrame(slowAll);
    };
    slowAll();
    runDemo("idle");
    window.parent.postMessage({ type: "ready", target: "hud" }, location.origin);
  }

  DCStyle.load("hud", hud, urlHides).then(() => {
    if (preview) startPreview();
    else if (params.get("demo")) runDemo(params.get("demo"));
    else connect();
  });
})();
