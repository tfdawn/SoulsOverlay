// Settings page: change the overlays' look, with the default and your version
// playing side by side. Opened by `soulsoverlay settings`, which passes the
// control token in the URL fragment, like the calibration page. Saved
// settings go to data/style.json and reach the overlays in OBS straight away.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const m = location.hash.match(/token=([^&]+)/);
  if (m) {
    sessionStorage.setItem("dc_token", decodeURIComponent(m[1]));
    history.replaceState(null, "", location.pathname);
  }
  const token = sessionStorage.getItem("dc_token");

  const DEMO_LAYOUT = { bar: [0.2422, 0.8035, 0.5184, 0.0076], name: [0.2383, 0.7722, 0.33, 0.0257] };
  const SCENARIOS = {
    hud: [["live", "NEW PB"], ["death", "Death"], ["kill", "Defeated"], ["first", "First attempt"], ["idle", "Still"]],
  };
  // Seven colours each: flare centre, flare, flare edge, flare fade-out, aura centre, aura, aura edge.
  const GLOW_KEYS = ["hud.shine_core", "hud.shine", "hud.shine_edge", "hud.shine_tail", "hud.aura_core", "hud.aura", "hud.aura_edge"];
  const GLOWS = [
    ["Gold", null],
    ["Ice", ["rgba(235, 250, 255, 0.95)", "rgba(140, 210, 255, 0.8)", "rgba(60, 130, 240, 0.5)", "rgba(40, 90, 200, 0.2)",
             "rgba(200, 235, 255, 0.95)", "rgba(90, 170, 255, 0.75)", "rgba(60, 120, 230, 0.35)"], ["#e4eef6", "#9fb2c4"]],
    ["Crimson", ["rgba(255, 225, 215, 0.95)", "rgba(255, 110, 90, 0.8)", "rgba(200, 30, 30, 0.5)", "rgba(150, 20, 20, 0.2)",
                 "rgba(255, 190, 170, 0.95)", "rgba(230, 60, 50, 0.75)", "rgba(180, 30, 30, 0.35)"], ["#f0e2de", "#bea6a0"]],
    ["Emerald", ["rgba(230, 255, 225, 0.95)", "rgba(120, 235, 140, 0.8)", "rgba(30, 160, 80, 0.5)", "rgba(20, 110, 50, 0.2)",
                 "rgba(190, 255, 200, 0.95)", "rgba(60, 200, 110, 0.75)", "rgba(40, 150, 80, 0.35)"], ["#e2efe3", "#a2baa6"]],
    ["Violet", ["rgba(245, 230, 255, 0.95)", "rgba(190, 140, 255, 0.8)", "rgba(120, 60, 220, 0.5)", "rgba(90, 40, 170, 0.2)",
                "rgba(225, 200, 255, 0.95)", "rgba(160, 100, 255, 0.75)", "rgba(120, 70, 210, 0.35)"], ["#ece3f4", "#b4a6c4"]],
    ["Pink", ["rgba(255, 235, 245, 0.95)", "rgba(255, 140, 200, 0.8)", "rgba(230, 60, 150, 0.5)", "rgba(180, 30, 110, 0.2)",
              "rgba(255, 210, 235, 0.95)", "rgba(250, 110, 185, 0.75)", "rgba(210, 60, 140, 0.35)"], ["#f4e2ec", "#c4a6b6"]],
    ["White", ["rgba(255, 255, 255, 0.95)", "rgba(225, 230, 240, 0.8)", "rgba(160, 170, 190, 0.5)", "rgba(130, 140, 160, 0.2)",
               "rgba(240, 244, 255, 0.9)", "rgba(200, 210, 230, 0.6)", "rgba(170, 180, 200, 0.3)"], ["#f0f0f0", "#b2b6bc"]],
  ];

  // The Simplified tab (the "hud" tab): colour themes, colours and the words
  // on screen. Everything else about the HUD is on The Lab tab.
  const FX_COLORS = [["pale", "Flash"], ["warm", "Body"], ["coreColor", "Core and sheen"], ["glowColor", "Glow"], ["partColor", "Sparks"]];
  const COLOR_KEYS = ["hud.deaths_label_color", "hud.deaths_color", "hud.danger", "hud.pb_label_color", "hud.pb_color",
    "hud.mark_color", "hud.phase_color", "hud.new_pb_color", "hud.defeated_color", "hud.callout_sub_color"];
  const SIMPLE = [
    { title: "Colour theme", help: "One click recolours the whole overlay: the text, the PB marker and the NEW PB light.", themes: true },
    { title: "Text", help: "The words and numbers under the game's boss health bar.", keys: ["hud.font", "hud.size", "hud.shadow"] },
    { title: "Text colours", help: "Each part of the HUD on its own. A colour theme sets them all at once; change any of them after.", keys: COLOR_KEYS },
    { title: "NEW PB effect colours", help: "The light that plays on the boss's health bar when you beat your PB. Its speeds and timings are on The Lab tab.", fx: FX_COLORS },
    { title: "Words on screen", help: "Leave a box empty to show no word, just the number.", keys: ["hud.label_deaths", "hud.label_pb", "hud.label_new_pb", "hud.label_defeated"] },
    { title: "Show", help: "Which parts of the HUD appear.", keys: ["hud.show_deaths", "hud.show_pb", "hud.show_phase", "hud.show_mark", "hud.callouts", "hud.always"] },
    { title: "Bar", help: "Where things sit around the boss bar.", keys: ["hud.gap", "hud.mark_width"] },
    { title: "Timing", help: "How long the HUD stays after the game hides its boss bar (when you die or the boss does).", keys: ["hud.linger", "hud.death_hold"] },
  ];
  const SIMPLE_KEYS = new Set(SIMPLE.flatMap((g) => g.keys || []));

  // What each section is, in game terms.
  const GROUP_HELP = {
    "hud.Text": "How the HUD's text looks under the game's boss health bar.",
    "hud.Layout": "Where things sit around the boss bar.",
    "hud.Labels": "The words the HUD shows. Leave a box empty to show no word, just the number.",
    "hud.Show": "Which parts of the HUD appear.",
    "hud.Timing": "How long the HUD stays after the game hides its boss bar (when you die or the boss does).",
  };
  let schema = [], byKey = {};
  let saved = {};   // what's in data/style.json
  let draft = {};   // what's on screen; only settings that differ from the default
  let tab = "hud";
  let layout = DEMO_LAYOUT;
  const scenario = { hud: "live" };
  const view = { hud: "close" };
  const compare = { hud: "stack" };
  const rows = {};  // key -> {el, set(value)}
  const frames = {};  // tab -> {def, mine} iframes
  let loopTimer = null;

  // -- helpers --------------------------------------------------------------
  function say(text, cls) { $("msg").textContent = text; $("msg").className = cls || ""; }
  const value = (key) => (key in draft ? draft[key] : byKey[key].default);
  const same = (a, b) => JSON.stringify(sortKeys(a)) === JSON.stringify(sortKeys(b));
  function sortKeys(o) { const out = {}; for (const k of Object.keys(o).sort()) out[k] = o[k]; return out; }
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) e.append(kid);
    return e;
  }

  function parseColor(s) {
    s = String(s).trim();
    let m = s.match(/^#([0-9a-f]{3,8})$/i);
    if (m) {
      let h = m[1];
      if (h.length === 3) h = [...h].map((c) => c + c).join("");
      const n = (i) => parseInt(h.slice(i, i + 2), 16);
      return { r: n(0), g: n(2), b: n(4), a: h.length === 8 ? n(6) / 255 : 1 };
    }
    m = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
    if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4] };
    return { r: 0, g: 0, b: 0, a: 1 };
  }
  const hex2 = (n) => Math.round(Math.min(255, Math.max(0, n))).toString(16).padStart(2, "0");
  const toHex = (c) => "#" + hex2(c.r) + hex2(c.g) + hex2(c.b);
  function colorString(c) {
    if (c.a >= 1) return toHex(c);
    return `rgba(${Math.round(c.r)}, ${Math.round(c.g)}, ${Math.round(c.b)}, ${Math.round(c.a * 100) / 100})`;
  }

  // -- changing a setting ---------------------------------------------------
  function setValue(key, v, fromControl) {
    if (same({ v }, { v: byKey[key].default })) delete draft[key]; else draft[key] = v;
    if (!fromControl && rows[key]) rows[key].set(value(key));
    changed();
  }

  function changed() {
    for (const [key, r] of Object.entries(rows)) r.el.classList.toggle("changed", key in draft);
    for (const d of document.querySelectorAll("details[data-group]")) {
      const n = d.querySelectorAll(".row.changed").length;
      d.querySelector(".count").textContent = n ? `${n} changed` : "";
    }
    const n = Object.keys(draft).filter((k) => byKey[k].target === tab || (tab === "hud" && byKey[k].target === "adv")).length;
    $("changes").textContent = n ? `· ${n} change${n === 1 ? "" : "s"} from default` : "· same as default";
    const dirty = !same(draft, saved);
    $("save").disabled = !dirty || !token;
    $("revert").disabled = !dirty;
    $("reset-all").disabled = !Object.keys(draft).length;
    if (dirty) say(token ? "Unsaved changes" : "Preview only: open this page with `soulsoverlay settings` to save.", "unsaved");
    else if ($("msg").classList.contains("unsaved")) say("");
    for (const b of document.querySelectorAll(".themes [data-theme]")) {
      const t = themeValues(...GLOWS.find(([n]) => n === b.dataset.theme).slice(1));
      b.classList.toggle("on", Object.entries(t).every(([k, v]) => same({ v }, { v: value(k) })));
    }
    send("mine", { type: "values", values: draft });
    for (const w of ["def", "mine"]) send(w, { type: "scene", bg: value("hud.fx").bg });
    sizeFrames();
  }

  // -- building the controls ----------------------------------------------
  // A number box with its own up/down arrows, as on The Lab tab.
  function numBox(min, max, step, label, onSet) {
    const num = el("input", { type: "number", min, max, step, "aria-label": label });
    const dec = String(step).split(".")[1];
    const fix = (v) => +(+v).toFixed(dec ? dec.length : 0);
    const put = (v) => { v = fix(Math.min(max, Math.max(min, v))); num.value = v; onSet(v); };
    num.addEventListener("change", () => put(+num.value || 0));
    const btn = (dir, name) => el("button", { type: "button", tabindex: "-1", "aria-label": name,
      onclick: (e) => { e.preventDefault(); put((+num.value || 0) + dir * step); } }, dir > 0 ? "▲" : "▼");
    return { el: el("span", { class: "numbox" }, num, el("span", { class: "arrows" }, btn(1, "Up"), btn(-1, "Down"))),
             show: (v) => { num.value = fix(v); } };
  }

  function control(f) {
    const key = f.key;
    let set, ctl;
    const commit = (v) => setValue(key, v, true);
    if (f.type === "color") {
      const pick = el("input", { type: "color", "aria-label": f.label });
      const alpha = el("input", { type: "range", min: 0, max: 100, step: 1, class: "alpha", title: "Opacity", "aria-label": f.label + " opacity" });
      const update = () => commit(colorString({ ...parseColor(pick.value), a: alpha.value / 100 }));
      const pct = numBox(0, 100, 1, f.label + " opacity %", (v) => { alpha.value = v; update(); });
      pick.addEventListener("input", update);
      alpha.addEventListener("input", () => { pct.show(alpha.value); update(); });
      set = (v) => { const c = parseColor(v); pick.value = toHex(c); alpha.value = Math.round(c.a * 100); pct.show(alpha.value); };
      ctl = [pick, alpha, pct.el, el("span", { class: "unit" }, "%")];
    } else if (f.type === "number") {
      const range = el("input", { type: "range", min: f.min, max: f.max, step: f.step, "aria-label": f.label });
      const num = numBox(f.min, f.max, f.step, f.label, (v) => { range.value = v; commit(v); });
      range.addEventListener("input", () => { num.show(range.value); commit(+range.value); });
      set = (v) => { range.value = v; num.show(v); };
      ctl = [range, num.el, el("span", { class: "unit" }, f.unit || "")];
    } else if (f.type === "bool") {
      const box = el("input", { type: "checkbox", role: "switch", "aria-label": f.label });
      box.addEventListener("change", () => commit(box.checked));
      set = (v) => { box.checked = !!v; };
      ctl = [el("label", { class: "switch" }, box, el("span"))];
    } else if (f.type === "enum") {
      const seg = el("div", { class: "seg" });
      for (const o of f.options) {
        seg.append(el("button", { type: "button", "data-v": o.value, onclick: () => { set(o.value); commit(o.value); } }, o.label));
      }
      set = (v) => { for (const b of seg.children) b.classList.toggle("on", b.dataset.v === v); };
      ctl = [seg];
    } else if (f.type === "font") {
      // One box: type any installed font's name, or pick from the list that
      // opens under it (each name shown in its own font).
      const input = el("input", { type: "text", role: "combobox", "aria-label": f.label, "aria-expanded": "false",
                                   "aria-autocomplete": "list", placeholder: "Pick or type a font name", autocomplete: "off" });
      const list = el("ul", { class: "font-list", role: "listbox", hidden: "" });
      const wrap = el("div", { class: "font-combo" }, input,
        el("button", { type: "button", class: "font-open", tabindex: "-1", "aria-label": "Show fonts",
                       onclick: () => { if (list.hidden) open(true); else close(); input.focus(); } }, "▾"), list);
      const labelOf = (v) => (f.options.find((o) => o.value === v) || {}).label;
      const nameOf = (v) => labelOf(v) || String(v).replace(/^"([^"]*)",.*$/, "$1");
      const toValue = (text) => {
        const o = f.options.find((x) => x.label.toLowerCase() === text.trim().toLowerCase());
        if (o) return o.value;
        const name = text.replace(/[^A-Za-z0-9 ,'"\-]/g, "").trim();
        return name ? (/[,"']/.test(name) ? name : `"${name}", ${f.default}`) : null;
      };
      let active = -1;
      const items = () => [...list.children];
      const mark = (i) => { active = i; items().forEach((li, j) => li.classList.toggle("on", j === i)); if (i >= 0) items()[i].scrollIntoView({ block: "nearest" }); };
      function open(all) {
        const q = all ? "" : input.value.trim().toLowerCase();
        list.replaceChildren(...f.options.filter((o) => !q || o.label.toLowerCase().includes(q)).map((o) =>
          el("li", { role: "option", style: `font-family: ${o.value}`,
                     onmousedown: (e) => { e.preventDefault(); input.value = o.label; commit(o.value); close(); } }, o.label)));
        list.hidden = !list.children.length;
        input.setAttribute("aria-expanded", String(!list.hidden));
        mark(-1);
      }
      function close() { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
      input.addEventListener("focus", () => { input.select(); open(true); });
      input.addEventListener("blur", () => { close(); input.value = nameOf(value(key)); });
      input.addEventListener("input", () => { open(false); const v = toValue(input.value); if (v) commit(v); });
      input.addEventListener("keydown", (e) => {
        const n = items().length;
        if (e.key === "ArrowDown") { e.preventDefault(); if (list.hidden) open(true); else if (n) mark((active + 1) % n); }
        else if (e.key === "ArrowUp") { e.preventDefault(); if (n) mark((active - 1 + n) % n); }
        else if (e.key === "Enter") { if (active >= 0) items()[active].dispatchEvent(new MouseEvent("mousedown")); else close(); e.preventDefault(); }
        else if (e.key === "Escape") close();
      });
      set = (v) => { if (document.activeElement !== input) input.value = nameOf(v); };
      ctl = [wrap];
    } else {
      const input = el("input", { type: "text", maxlength: f.maxlength || 40, placeholder: f.default, "aria-label": f.label });
      input.addEventListener("input", () => commit(input.value));
      set = (v) => { input.value = v; };
      ctl = [input];
    }
    const reset = el("button", { type: "button", class: "reset", title: "Back to the default",
                                 "aria-label": `Reset ${f.label}`, onclick: () => setValue(key, f.default) }, "↺");
    const wide = f.type === "font" || f.type === "text" || (f.type === "enum" && f.options.length > 3);
    const row = el("div", { class: "row" + (wide ? " wide" : "")  },
      el("div", { class: "name" }, f.label, f.help ? el("span", { class: "help" }, f.help) : null));
    if (wide) row.append(reset, el("div", { class: "ctl" }, ...ctl));
    else row.append(el("div", { class: "ctl" }, ...ctl), reset);
    rows[key] = { el: row, set };
    set(value(key));
    return row;
  }

  // A theme recolours everything the same way: the theme colour goes on all
  // things PB (the marker, the PB %, NEW PB / DEFEATED and the line under it),
  // the numbers and labels get a pale and a dim tint of it, and the NEW PB
  // light uses its shades. The death flash stays red.
  function themeValues(colors, tints) {
    const fxDef = byKey["hud.fx"].default;
    const list = colors || GLOW_KEYS.map((k) => byKey[k].default);
    const hex = (i) => toHex(parseColor(list[i]));
    const out = {};
    GLOW_KEYS.forEach((k, i) => { out[k] = list[i]; });
    const pick = { accent: colors && hex(1), text: tints && tints[0], muted: tints && tints[1] };
    const role = { "hud.deaths_color": "text", "hud.deaths_label_color": "muted", "hud.pb_label_color": "muted",
                   "hud.phase_color": "muted" };
    for (const k of COLOR_KEYS) {
      if (k === "hud.danger") continue;  // the death flash stays red
      out[k] = pick[role[k] || "accent"] || byKey[k].default;
    }
    const fxc = colors ? { pale: hex(0), warm: hex(2), coreColor: hex(4), glowColor: hex(5), partColor: hex(1) }
                       : Object.fromEntries(FX_COLORS.map(([k]) => [k, fxDef[k]]));
    out["hud.fx"] = { ...value("hud.fx"), ...fxc };
    return out;
  }
  function themes() {
    const wrap = el("div", { class: "presets themes", "aria-label": "Colour themes" });
    for (const [name, colors, tints] of GLOWS) {
      const list = colors || GLOW_KEYS.map((k) => byKey[k].default);
      const dot = el("i");
      dot.style.background = `radial-gradient(circle, ${list[0]} 0%, ${list[1]} 40%, ${list[2]} 75%, ${list[3]} 100%)`;
      const b = el("button", { type: "button", class: "preset", title: `${name} theme`,
        onclick: () => { for (const [k, v] of Object.entries(themeValues(colors, tints))) setValue(k, v); } },
        dot, colors ? name : "Default");
      b.dataset.theme = name;
      wrap.append(b);
    }
    return wrap;
  }
  // The custom effect's colours and the preview background live inside hud.fx;
  // one row object keeps all their controls in step.
  let fxShows = [];
  function fxRow(show) {
    fxShows.push(show);
    rows["hud.fx"] = { el: el("div"), set: (v) => fxShows.forEach((f) => f(v)) };
    show(value("hud.fx"));
  }
  const SCENES = [["dark", "Dark (default)"], ["warm", "Warm gameplay"], ["stone", "Stone"], ["light", "Light"], ["black", "Pure black"], ["checker", "Checkerboard"]];
  // The preview background, in the preview toolbar; shared with The Lab.
  const sceneSel = $("scene");
  for (const [v, t] of SCENES) sceneSel.append(el("option", { value: v }, t));
  sceneSel.addEventListener("change", () => setValue("hud.fx", { ...value("hud.fx"), bg: sceneSel.value }, true));
  function fxColorRows(list) {
    const pickers = {};
    const out = list.map(([k, label]) => {
      const pick = el("input", { type: "color", "aria-label": label });
      pick.addEventListener("input", () => setValue("hud.fx", { ...value("hud.fx"), [k]: pick.value }, true));
      pickers[k] = pick;
      const reset = el("button", { type: "button", class: "reset", title: "Back to the default", "aria-label": `Reset ${label}`,
        onclick: () => setValue("hud.fx", { ...value("hud.fx"), [k]: byKey["hud.fx"].default[k] }) }, "↺");
      return el("div", { class: "row" }, el("div", { class: "name" }, label), el("div", { class: "ctl" }, pick), reset);
    });
    fxRow((v) => { for (const [k, p] of Object.entries(pickers)) p.value = toHex(parseColor(v[k])); });
    return out;
  }
  function buildSimple(box) {
    fxShows = [];
    fxRow((v) => { sceneSel.value = v.bg; });
    for (const g of SIMPLE) {
      const d = el("details", { "data-group": g.title, open: "" }, el("summary", {}, g.title, el("span", { class: "count" })));
      if (g.help) d.append(el("p", { class: "group-help" }, g.help));
      if (g.themes) d.append(themes());
      for (const k of g.keys || []) d.append(control(byKey[k]));
      if (g.fx) d.append(...fxColorRows(g.fx));
      box.append(d);
    }
  }

  function buildControls() {
    const box = $("controls");
    box.innerHTML = "";
    buildSimple(box);
  }

  // -- previews -------------------------------------------------------------
  function send(which, msg) {
    const f = frames[tab] && frames[tab][which === "mine" ? "mine" : "def"];
    if (f && f.ready) f.contentWindow.postMessage(msg, location.origin);
  }
  let rate = 1;  // slow-mo, for the previews only; never saved
  const play = () => {
    for (const w of ["def", "mine"]) {
      send(w, { type: "rate", rate });
      send(w, { type: "play", scenario: scenario[tab], layout });
    }
  };
  $("rate").addEventListener("input", () => {
    rate = +$("rate").value;
    $("rate-out").textContent = rate + "×";
  });
  $("rate").addEventListener("change", () => { play(); restartLoop(); });

  function makeFrames() {
    for (const t of Object.keys(frames)) for (const f of Object.values(frames[t])) f.remove();
    const src = "/overlay/hud?preview=1";
    const def = el("iframe", { src, title: "Default look", tabindex: "-1" });
    const mine = el("iframe", { src, title: "Your look", tabindex: "-1" });
    frames[tab] = { def, mine };
    $("frame-default").replaceChildren(def);
    $("frame-mine").replaceChildren(mine);
    sizeFrames();
  }

  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || !e.data || e.data.type !== "ready") return;
    const fr = frames[tab];
    if (!fr) return;
    for (const [w, f] of Object.entries(fr)) {
      if (f.contentWindow !== e.source) continue;
      f.ready = true;
      f.contentWindow.postMessage({ type: "values", values: w === "mine" ? draft : {} }, location.origin);
      f.contentWindow.postMessage({ type: "scene", bg: value("hud.fx").bg }, location.origin);
    }
    if (fr.def.ready && fr.mine.ready) play();
  });

  function sizeFrames() {
    const fr = frames[tab];
    if (!fr) return;
    $("panes").className = "panes" + (compare[tab] === "side" ? " side" : "");
    for (const f of Object.values(fr)) {
      const holder = f.parentElement;
      const cw = holder.clientWidth;
      if (!cw) continue;
      // Render a full 1080p screen and show either all of it or the strip
      // around the bar, scaled to fit.
      const W = 1920, H = 1080;
      let crop = [0, 0, 1, 1];
      if (view.hud === "close") {
        const [x, y, bw, bh] = layout.bar;
        const top = Math.max(0, (layout.name ? layout.name[1] : y) - 0.02);
        // Room under the bar for the stats and the two-line callout, at the
        // larger of the two text sizes so both panes crop the same.
        const big = (k) => Math.max(byKey[k].default, value(k)) / 100;
        const bottom = y + bh + big("hud.gap") + 6.2 * big("hud.size") + 0.012;
        crop = [Math.max(0, x - 0.05), top, Math.min(1, bw + 0.1), Math.min(1, bottom) - top];
      }
      const s = cw / (crop[2] * W);
      Object.assign(f.style, { width: W + "px", height: H + "px",
        transform: `translate(${-crop[0] * W * s}px, ${-crop[1] * H * s}px) scale(${s})` });
      holder.style.height = Math.round(crop[3] * H * s) + "px";
    }
  }
  new ResizeObserver(() => sizeFrames()).observe($("panes"));

  function setScenario(id) {
    scenario[tab] = id;
    const i = SCENARIOS[tab].findIndex(([s]) => s === id);
    [...$("scenarios").children].forEach((b, j) => b.classList.toggle("on", j === i));
  }

  function buildToolbar() {
    const seg = $("scenarios");
    seg.innerHTML = "";
    for (const [id, label] of SCENARIOS[tab]) {
      seg.append(el("button", { type: "button", class: id === scenario[tab] ? "on" : "",
        onclick: (e) => {
          scenario[tab] = id;
          for (const b of seg.children) b.classList.toggle("on", b === e.currentTarget);
          play();
          restartLoop();
        } }, label));
    }
        for (const b of $("view").children) b.classList.toggle("on", b.dataset.view === view.hud);
    for (const b of $("compare").children) b.classList.toggle("on", b.dataset.compare === compare[tab]);
    $("hint").innerHTML = "The HUD overlays on the game's own boss bar.<br>In OBS, add a Browser Source and input <code>http://127.0.0.1:8765/overlay/hud</code> as the URL, set it to your canvas size and then Fit to Screen.";
  }
  $("view").addEventListener("click", (e) => {
    const v = e.target.dataset.view;
    if (!v) return;
    view.hud = v;
    for (const b of $("view").children) b.classList.toggle("on", b === e.target);
    sizeFrames();
  });
  $("compare").addEventListener("click", (e) => {
    const v = e.target.dataset.compare;
    if (!v) return;
    compare[tab] = v;
    for (const b of $("compare").children) b.classList.toggle("on", b === e.target);
    sizeFrames();
  });

  function restartLoop() {
    clearInterval(loopTimer);
    if (tab !== "adv" && $("loop").checked && scenario[tab] !== "idle") loopTimer = setInterval(play, 6500 / rate);
  }
  $("loop").addEventListener("change", restartLoop);

  // The Advanced tab is the HP Bar Lab (lab.js), built once.
  let lab = null;
  function showLab() {
    const fxKey = "hud.fx";
    if (!lab) {
      lab = DCLab.build({
        root: $("lab"), defaults: byKey[fxKey].default,
        get: () => value(fxKey), set: (v) => setValue(fxKey, v, true),
        getVal: (k) => value(k),
        setVal: (k, v) => setValue(k, v, true),
        toHex: (v) => toHex(parseColor(v)),
        alpha: (v) => parseColor(v).a,
        colorString: (hex, a) => colorString({ ...parseColor(hex), a }),
      });
    }
    const dummy = document.createElement("div");
    rows[fxKey] = { el: dummy, set: (v) => lab.set(v) };
    for (const f of schema) {
      if (f.target !== "hud") continue;
      rows[f.key] = { el: dummy, set: (v) => lab.setVal(f.key, v) };
      lab.setVal(f.key, value(f.key));
    }
    lab.set(value(fxKey));
    lab.shown();
  }

  function showTab(t) {
    if (tab === "adv" && lab && t !== "adv") lab.hidden();
    tab = t;
    for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("on", b.dataset.tab === t);
    for (const k of Object.keys(rows)) delete rows[k];
    $("main").hidden = t === "adv";
    $("lab").hidden = t !== "adv";
    if (t === "adv") {
      clearInterval(loopTimer);
      showLab();
      changed();
      return;
    }
    buildControls();
    buildToolbar();
    makeFrames();
    changed();
    restartLoop();
  }
  for (const b of document.querySelectorAll(".tabs button")) b.addEventListener("click", () => showTab(b.dataset.tab));

  // -- saving, resetting, sharing -------------------------------------------
  async function api(path, body) {
    const res = await fetch(path, { method: "POST", body: JSON.stringify(body),
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" } });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  $("save").addEventListener("click", async () => {
    try {
      const data = await api("/api/settings", { values: draft });
      saved = { ...data.values };
      draft = { ...data.values };
      changed();
      say("Saved. The overlays in OBS have updated.");
    } catch (e) { say("Could not save: " + e.message, "bad"); }
  });
  $("revert").addEventListener("click", () => { draft = { ...saved }; refreshRows(); changed(); say("Back to your saved settings."); });
  $("reset-all").addEventListener("click", () => {
    if (!confirm("Set every setting, on both tabs, back to the default look? Nothing is saved until you click Save.")) return;
    draft = {};
    refreshRows();
    changed();
    say("Everything is back to the default. Click Save to keep it.", "unsaved");
  });
  function refreshRows() { for (const [k, r] of Object.entries(rows)) r.set(value(k)); }

  $("export").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ souls_overlay_style: 1, values: sortKeys(draft) }, null, 2) + "\n"], { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: "souls-overlay-style.json" });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $("import").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const vals = data && typeof data.values === "object" ? data.values : data;
      const known = Object.entries(vals || {}).filter(([k]) => byKey[k]);
      if (!known.length) throw new Error("no settings in that file");
      draft = {};
      for (const [k, v] of known) if (typeof v === typeof byKey[k].default) draft[k] = v;
      refreshRows();
      changed();
      const skipped = Object.keys(vals).length - known.length;
      say(`Loaded ${known.length} setting${known.length === 1 ? "" : "s"}${skipped ? ` (${skipped} unknown skipped)` : ""}. Click Save to keep them.`, "unsaved");
    } catch (err) { say("Could not read that file: " + err.message, "bad"); }
  });
  window.addEventListener("beforeunload", (e) => { if (!same(draft, saved)) e.preventDefault(); });

  // -- start ----------------------------------------------------------------
  (async function start() {
    try {
      const data = await (await fetch("/overlay/settings.json", { cache: "no-store" })).json();
      schema = data.schema;
      for (const f of schema) byKey[f.key] = f;
      saved = { ...(data.values || {}) };
      draft = { ...saved };
    } catch (e) { say("Could not load the settings: is `soulsoverlay run` running?", "bad"); return; }
    try {
      const st = await (await fetch("/api/state", { cache: "no-store" })).json();
      if (st.layout && st.layout.bar) layout = st.layout;
    } catch (_) {}
    showTab("hud");
    if (!token) say("Preview only: open this page with `soulsoverlay settings` to save.", "unsaved");
  })();
})();
