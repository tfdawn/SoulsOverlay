// Calibration page. Opened by `soulsoverlay calibrate`, which passes the
// control token in the URL fragment; fragments never reach the server or the
// Referer, and we move it into sessionStorage and strip it from the address bar.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const m = location.hash.match(/token=([^&]+)/);
  if (m) {
    sessionStorage.setItem("dc_token", decodeURIComponent(m[1]));
    history.replaceState(null, "", location.pathname);
  }
  const token = sessionStorage.getItem("dc_token");

  const COLORS = ["#e5484d", "#3e9bff", "#30a46c", "#f5a524", "#a855f7", "#14b8a6", "#ec4899", "#84cc16"];
  const canvas = $("canvas"), ctx = canvas.getContext("2d");
  const zoom = $("zoom"), zctx = zoom.getContext("2d");
  let img = null;
  let regions = {};     // death, victory
  let slots = [];       // [{name, bar}]
  let active = "slot0.bar";
  let drag = null;
  let barColors = null; // from Auto-find, when the game's own colours didn't match
  let hud = null;       // {value, min, max, anchor}: the HUD scale the boss boxes are drawn for

  function say(text, bad) { $("msg").textContent = text; $("msg").style.color = bad ? "#e5484d" : ""; }

  async function api(path, opts = {}) {
    const headers = { Authorization: "Bearer " + token, ...(opts.headers || {}) };
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    const res = await fetch(path, { ...opts, headers });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error || msg; } catch (_) {}
      throw new Error(msg);
    }
    return res;
  }

  // -- region model --------------------------------------------------------
  function keys() {
    const out = ["death", "victory"];
    slots.forEach((_, i) => out.push(`slot${i}.name`, `slot${i}.bar`));
    return out;
  }
  function label(k) {
    if (k === "death") return "Death text";
    if (k === "victory") return "Victory text (optional)";
    const [s, f] = k.split(".");
    const n = +s.slice(4) + 1;
    return `Boss ${n} ${f === "bar" ? "health bar" : "name"}`;
  }
  function get(k) {
    if (!k.startsWith("slot")) return regions[k];
    const [s, f] = k.split(".");
    return (slots[+s.slice(4)] || {})[f];
  }
  function set(k, r) {
    if (!k.startsWith("slot")) { regions[k] = r; return; }
    const [s, f] = k.split(".");
    slots[+s.slice(4)][f] = r;
  }

  function renderList() {
    const ul = $("regions");
    ul.innerHTML = "";
    keys().forEach((k, i) => {
      const li = document.createElement("li");
      if (k === active) li.className = "active";
      const sw = document.createElement("span");
      sw.className = "swatch"; sw.style.background = COLORS[i % COLORS.length];
      const name = document.createElement("span"); name.textContent = label(k);
      const c = document.createElement("span"); c.className = "coords";
      const r = get(k);
      c.textContent = r ? r.map((v) => v.toFixed(3)).join(" ") : "not set";
      li.append(sw, name, c);
      li.onclick = () => { active = k; renderList(); draw(); };
      ul.appendChild(li);
    });
  }

  function draw() {
    if (img) {
      canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
    } else {
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#888"; ctx.font = "28px system-ui";
      ctx.fillText("Grab a frame from OBS or load a screenshot", 40, 60);
    }
    const W = canvas.width, H = canvas.height;
    ctx.lineWidth = Math.max(2, W / 640);
    ctx.font = `${Math.round(W / 80)}px system-ui`;
    keys().forEach((k, i) => {
      const r = get(k);
      if (!r) return;
      ctx.strokeStyle = COLORS[i % COLORS.length];
      ctx.setLineDash(k === active ? [] : [8, 6]);
      ctx.strokeRect(r[0] * W, r[1] * H, r[2] * W, r[3] * H);
      if (k === active) {  // only the active box is labelled; stacked slots get crowded
        ctx.fillStyle = COLORS[i % COLORS.length];
        ctx.fillText(label(k), r[0] * W, r[1] * H - 6);
      }
    });
    ctx.setLineDash([]);
    drawZoom();
  }

  function drawZoom() {
    zctx.fillStyle = "#000"; zctx.fillRect(0, 0, zoom.width, zoom.height);
    const r = get(active);
    if (!img || !r) return;
    const W = img.naturalWidth, H = img.naturalHeight;
    const x = r[0] * W, y = r[1] * H, w = r[2] * W, h = r[3] * H;
    zctx.imageSmoothingEnabled = false;
    // Long thin boxes (health bars): show both ends magnified side by side,
    // since that's where a pixel off matters. Anything else: the whole box.
    const views = w / h > 6
      ? [[x, y + h / 2], [x + w, y + h / 2]]
      : [[x + w / 2, y + h / 2]];
    const vw = zoom.width / views.length, vh = zoom.height;
    const span = views.length > 1 ? Math.max(24, h * 4) : Math.max(w, h * vw / vh) * 1.2;
    const s = vw / span;
    views.forEach(([cx, cy], i) => {
      const sx = cx - span / 2, sy = cy - (vh / s) / 2;
      zctx.save();
      zctx.beginPath(); zctx.rect(i * vw, 0, vw, vh); zctx.clip();
      zctx.drawImage(img, sx, sy, span, vh / s, i * vw, 0, vw, vh);
      zctx.strokeStyle = "#fff"; zctx.lineWidth = 1;
      zctx.strokeRect(i * vw + (x - sx) * s, (y - sy) * s, w * s, h * s);
      zctx.restore();
    });
    if (views.length > 1) { zctx.fillStyle = "#666"; zctx.fillRect(vw - 1, 0, 2, vh); }
  }

  // -- dragging ------------------------------------------------------------
  function pos(ev) {
    const b = canvas.getBoundingClientRect();
    return [Math.min(1, Math.max(0, (ev.clientX - b.left) / b.width)),
            Math.min(1, Math.max(0, (ev.clientY - b.top) / b.height))];
  }
  canvas.addEventListener("pointerdown", (ev) => {
    if (!img) return;
    drag = pos(ev);
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const p = pos(ev);
    const r = [Math.min(drag[0], p[0]), Math.min(drag[1], p[1]), Math.abs(p[0] - drag[0]), Math.abs(p[1] - drag[1])];
    set(active, r.map((v) => +v.toFixed(4)));
    draw();
  });
  canvas.addEventListener("pointerup", () => {
    if (!drag) return;
    drag = null;
    const r = get(active);
    if (r && (r[2] < 0.002 || r[3] < 0.002)) set(active, null);
    renderList(); draw();
  });
  // Arrow keys nudge the active box (Shift = resize), for pixel-exact bars.
  document.addEventListener("keydown", (ev) => {
    const r = get(active);
    if (!r || !img || ev.target.tagName === "SELECT") return;
    const dx = 1 / img.naturalWidth, dy = 1 / img.naturalHeight;
    const d = { ArrowLeft: [-dx, 0], ArrowRight: [dx, 0], ArrowUp: [0, -dy], ArrowDown: [0, dy] }[ev.key];
    if (!d) return;
    ev.preventDefault();
    const n = r.slice();
    if (ev.shiftKey) { n[2] = Math.max(dx, n[2] + d[0]); n[3] = Math.max(dy, n[3] + d[1]); }
    else { n[0] += d[0]; n[1] += d[1]; }
    set(active, n.map((v) => +Math.min(1, Math.max(0, v)).toFixed(4)));
    renderList(); draw();
  });

  // -- server calls --------------------------------------------------------
  async function loadFrame() {
    const res = await api("/api/calibrate/frame");
    const url = URL.createObjectURL(await res.blob());
    img = new Image();
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = url; });
    draw();
  }

  async function loadProfile() {
    const data = await (await api("/api/calibrate/profile")).json();
    regions = { death: data.effective.regions.death || null, victory: data.effective.regions.victory || null };
    slots = (data.effective.boss_slots || []).map((s) => ({ name: s.name || null, bar: s.bar || null }));
    if (!slots.length) slots = [{ name: null, bar: null }];
    hud = data.effective.hud_scale ? { ...data.effective.hud_scale } : null;
    $("hud-box").hidden = !hud;
    if (hud) {
      Object.assign($("hud-scale"), { min: hud.min, max: hud.max, value: hud.value.toFixed(2) });
    }
    renderList(); draw();
  }

  async function loadGames() {
    const data = await (await api("/api/games")).json();
    const sel = $("game");
    sel.innerHTML = "";
    for (const g of data.games) {
      const o = document.createElement("option");
      o.value = g.id; o.textContent = g.name; o.selected = g.id === data.current;
      sel.appendChild(o);
    }
  }

  const run = (fn) => async () => { try { await fn(); } catch (e) { say(e.message, true); } };

  $("game").onchange = run(async () => {
    await api("/api/control", { method: "POST", json: { command: "game_set", args: { game: $("game").value } } });
    await loadProfile(); say("Switched game");
  });
  $("grab").onclick = run(async () => {
    say("Grabbing…");
    await api("/api/calibrate/grab", { method: "POST", json: {} });
    await loadFrame(); say("Frame grabbed. Live detection is paused while you calibrate.");
  });
  $("file").onchange = run(async () => {
    const f = $("file").files[0];
    if (!f) return;
    await api("/api/calibrate/upload", { method: "POST", body: f, headers: { "Content-Type": f.type || "application/octet-stream" } });
    await loadFrame(); say(`Loaded ${f.name}. Live detection is paused while you calibrate.`);
    $("file").value = "";
  });
  $("save").onclick = run(async () => {
    const regs = {};
    for (const k of ["death", "victory"]) if (regions[k]) regs[k] = regions[k];
    await api("/api/calibrate/profile", { method: "POST", json: {
      regions: regs, boss_slots: slots.filter((s) => s.name || s.bar),
      ...(barColors ? { bar_colors: barColors } : {}),
      ...(hud ? { hud_scale: { value: hud.value } } : {}) } });
    barColors = null;
    say("Saved");
  });
  $("autofind").onclick = run(async () => {
    say("Looking for the boss bar…");
    const d = await (await api("/api/calibrate/autofind", { method: "POST", json: {} })).json();
    slots = d.boss_slots.map((s) => ({ name: s.name || null, bar: s.bar || null }));
    barColors = d.bar_colors || null;
    if (d.regions) Object.assign(regions, d.regions);
    active = "slot0.bar";
    let size = d.scale === 1 ? "" : ` at ${Math.round(d.scale * 100)}% of the preset's size`;
    if (hud && d.hud_scale) {
      hud.value = d.hud_scale;
      $("hud-scale").value = d.hud_scale.toFixed(2);
      size = ` for a HUD scale of about ${d.hud_scale.toFixed(2)}`;
    }
    renderList(); draw();
    say(`Found the boss bar${size}. Check the boxes, then Save profile.`);
  });
  // The HUD grows and shrinks about a fixed point (the bottom centre in DSR),
  // so a new scale moves every boss box the same way. YOU DIED scales too,
  // about its own point (the centre of the screen).
  $("hud-apply").onclick = () => {
    const want = parseFloat($("hud-scale").value);
    if (!hud || !(want >= hud.min && want <= hud.max)) {
      say(`The HUD scale goes from ${hud.min.toFixed(2)} to ${hud.max.toFixed(2)}`, true);
      return;
    }
    const k = want / hud.value;
    const mover = ([ax, ay]) => (r) => r && [ax + (r[0] - ax) * k, ay + (r[1] - ay) * k, r[2] * k, r[3] * k]
      .map((v) => +v.toFixed(4));
    const move = mover(hud.anchor);
    slots = slots.map((s) => ({ name: move(s.name), bar: move(s.bar) }));
    if (hud.death_anchor) regions.death = mover(hud.death_anchor)(regions.death);
    hud.value = want;
    renderList(); draw();
    say(`Boxes moved for a HUD scale of ${want.toFixed(2)}. Check them, then Save profile.`);
  };
  $("test").onclick = run(async () => {
    const d = await (await api("/api/calibrate/diagnose", { method: "POST", json: {} })).json();
    const lines = [
      `frame ${d.frame.w}x${d.frame.h}`,
      `death: ${d.death ? "YES" : "no"}  score ${d.death_score}  (${d.detector})`,
      `victory: ${d.victory ? "YES" : "no"}  score ${d.victory_score}`,
    ];
    d.slots.forEach((s, i) => {
      lines.push("", `boss slot ${i + 1}`,
        `  health: ${s.pct == null ? "no bar" : s.pct + "%"}   trail: ${s.trail_pct}%`,
        `  OCR: "${s.text}"`,
        `  match: ${s.boss ? `${s.boss} (score ${s.score}${s.phase_hint ? ", phase " + s.phase_hint : ""})` : "none"}`);
    });
    $("diag").textContent = lines.join("\n");
    say("Tested on the current frame (saved profile)");
  });
  $("resume").onclick = run(async () => {
    await api("/api/calibrate/resume", { method: "POST", json: {} });
    say("Live capture resumed");
  });
  $("add-slot").onclick = () => { slots.push({ name: null, bar: null }); active = `slot${slots.length - 1}.bar`; renderList(); draw(); };
  $("remove-slot").onclick = () => { if (slots.length > 1) { slots.pop(); active = "slot0.bar"; renderList(); draw(); } };
  for (const kind of ["death", "victory"]) {
    $("tpl-" + kind).onclick = run(async () => {
      const d = await (await api("/api/calibrate/template", { method: "POST", json: { kind } })).json();
      say(`Saved ${d.template}`);
    });
  }

  if (!token) {
    say("No token. Open this page with `soulsoverlay calibrate`.", true);
    draw();
    return;
  }
  run(async () => {
    await loadGames(); await loadProfile();
    try { await loadFrame(); } catch (_) { say("No frame yet: grab one from OBS or load a screenshot."); }
  })();
})();
