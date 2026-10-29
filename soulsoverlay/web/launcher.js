// Launcher window: what SoulsOverlay.exe shows instead of a terminal. It runs
// inside the exe's own window (pywebview), which adds `window.pywebview.api`
// for things a page can't do (open the data folder, hide the window to the tray); in a
// normal browser those links stay hidden. Opened with the control token in
// the URL fragment, like the settings and calibration pages.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const m = location.hash.match(/token=([^&]+)/);
  if (m) {
    sessionStorage.setItem("dc_token", decodeURIComponent(m[1]));
    history.replaceState(null, "", location.pathname);
  }
  const token = sessionStorage.getItem("dc_token");

  let info = null;   // GET /api/launcher
  let state = null;  // live state from the overlay WebSocket
  let connectOpen = false;
  let native = null; // pywebview's bridge, once it's ready

  async function api(path, body) {
    const opts = { headers: { Authorization: "Bearer " + token } };
    if (body !== undefined) {
      opts.method = "POST";
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `error ${r.status}`);
    return data;
  }

  // -- status in plain words ----------------------------------------------
  function explain(error, source) {
    const e = (error || "").toLowerCase();
    if (e.includes("auth") || e.includes("password") || e.includes("4009") || e.includes("identif"))
      return ["OBS refused the password", "Copy it again from Show Connect Info in OBS's WebSocket Server Settings."];
    if (e.includes("source") || e.includes("600") || e.includes("not found") || e.includes("size of obs"))
      return [`OBS has no source called "${source}"`, "Use the exact name from OBS's Sources list, under OBS connection."];
    if (e.includes("refused") || e.includes("timed out") || e.includes("timeout") || e.includes("errno") || e.includes("connect"))
      return ["Can't reach OBS", "Open OBS, and check Tools ▸ WebSocket Server Settings has the server enabled."];
    return ["Can't get the picture from OBS", error || ""];
  }

  function renderStatus() {
    const st = (state && state.status) || {};
    const source = info ? info.obs.source : "";
    let dot = "", title, detail, bad = false;
    if (info && info.setup_needed) {
      dot = "warn"; title = "Connect SoulsOverlay to OBS"; detail = "First time here: fill in the two boxes below.";
    } else if (info && info.stopped || st.capture === "stopped") {
      title = "Stopped"; detail = "Press Start, then play. OBS needs to be open.";
    } else if (st.capture === "ok") {
      dot = "ok"; title = "Running";
      detail = `Watching OBS source "${source}"` + (st.fps ? ` · ${st.fps} checks a second` : "");
      if (st.picture === "black") { dot = "warn"; title = "Running, but the picture is black"; detail = "Is the game minimised, or is that the wrong source?"; }
      else if (st.ocr && st.ocr !== "ok") { dot = "warn"; detail = "Boss names can't be read: " + st.ocr; }
    } else if (st.capture === "error") {
      dot = "bad"; bad = true;
      [title, detail] = explain(st.capture_error, source);
    } else {
      dot = "warn"; title = "Connecting to OBS…"; detail = `Looking for source "${source}"`;
    }
    $("dot").className = "dot " + dot;
    $("status-card").classList.toggle("bad", bad);
    $("status-title").textContent = title;
    $("status-detail").textContent = detail;

    const stopped = !!(info && info.stopped);
    $("startstop").hidden = !!(info && info.setup_needed);
    const btn = $("startstop");
    btn.innerHTML = stopped ? "▶&nbsp; Start" : "■&nbsp; Stop";
    btn.className = stopped ? "primary" : "stop";

    const boss = state && state.boss;
    $("boss").hidden = !boss;
    if (boss) {
      $("boss-name").textContent = boss.name;
      $("boss-deaths").textContent = boss.deaths;
      const pb = boss.pb;
      $("boss-pb").textContent = !pb ? "–" : pb.killed ? "defeated" : `${pb.pct}%`;
    }
    // Show the OBS form by itself on the first start and when the details look wrong.
    const wrongDetails = bad && !/Can't reach OBS/.test(title);
    $("connect").hidden = !(connectOpen || (info && info.setup_needed) || wrongDetails);
  }

  // -- OBS connection form ----------------------------------------------
  function fillConnect() {
    $("source").value = info.obs.source;
    $("password").value = "";
    $("password").placeholder = info.obs.password_set ? "Saved (leave empty to keep it)" : "Leave empty if OBS has no password";
    $("connect-cancel").hidden = !!info.setup_needed;
    $("open-hotkeys").hidden = !!info.setup_needed;  // saving would skip the first-start OBS form
  }

  $("connect").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = $("connect-msg");
    msg.className = "msg"; msg.textContent = "Connecting…";
    try {
      await api("/api/launcher/obs", { password: $("password").value, source: $("source").value });
      connectOpen = false;
      msg.textContent = "";
      await loadInfo();
    } catch (err) {
      msg.className = "msg bad"; msg.textContent = err.message;
    }
  });
  $("connect-cancel").addEventListener("click", () => { connectOpen = false; renderStatus(); });
  $("edit-obs").addEventListener("click", (e) => {
    e.preventDefault();
    connectOpen = true; fillConnect(); renderStatus(); $("password").focus();
  });

  // -- buttons ----------------------------------------------------------
  $("startstop").addEventListener("click", async () => {
    $("startstop").disabled = true;
    try {
      await api("/api/control", { command: info.stopped ? "start" : "stop" });
      await loadInfo();
    } finally { $("startstop").disabled = false; }
  });

  function openPage(page) {
    const url = `${location.origin}/${page}#token=${encodeURIComponent(token)}`;
    if (native) native.open_url(url);
    else window.open(url, "_blank", "noopener");
  }
  // Settings is a small hub: the overlay's look (a page in the browser) and hotkeys.
  const closeSettings = () => { $("settings").hidden = true; };
  $("open-settings").addEventListener("click", () => {
    $("st-autogame").checked = !state || !state.game_detect || state.game_detect.auto_switch;
    $("settings").hidden = false;
    $("st-look").focus();
  });
  $("st-look").addEventListener("click", () => { closeSettings(); $("editor").hidden = false; $("ed-open").focus(); });
  const closeEditor = () => { $("editor").hidden = true; };
  $("ed-open").addEventListener("click", () => { closeEditor(); openPage("settings"); });
  $("ed-cancel").addEventListener("click", closeEditor);
  $("editor").addEventListener("keydown", (e) => { if (e.key === "Escape") closeEditor(); });
  $("st-close").addEventListener("click", closeSettings);
  $("st-autogame").addEventListener("change", async () => {
    $("st-autogame").checked = (await api("/api/game_detect", { auto_switch: $("st-autogame").checked })).auto_switch;
  });
  $("st-tray").addEventListener("change", async () => {
    $("st-tray").checked = (await native.set_pref("close_to_tray", $("st-tray").checked)).close_to_tray;
  });

  // Closing the window (with the tray on) shows this first; the app calls it.
  window.trayNotice = () => {
    $("tn-off").checked = false;
    $("traynote").hidden = false;
    $("tn-ok").focus();
  };
  const closeNotice = async () => {
    $("traynote").hidden = true;
    if ($("tn-off").checked) await native.set_pref("tray_notice", false);
  };
  $("tn-ok").addEventListener("click", async () => { await closeNotice(); native.hide_window(); });
  $("tn-settings").addEventListener("click", async () => {
    await closeNotice();
    $("settings").hidden = false;
    $("st-tray").focus();
  });
  $("traynote").addEventListener("keydown", (e) => { if (e.key === "Escape") $("tn-ok").click(); });
  $("settings").addEventListener("keydown", (e) => { if (e.key === "Escape") closeSettings(); });
  $("open-calibrate").addEventListener("click", () => openPage("calibrate"));

  $("copy").addEventListener("click", async () => {
    const url = $("hud-url").value;
    try { await navigator.clipboard.writeText(url); }
    catch { if (native) await native.copy(url); else { $("hud-url").select(); document.execCommand("copy"); } }
    $("copy").textContent = "Copied ✓";
    setTimeout(() => { $("copy").textContent = "Copy"; }, 1500);
  });

  // Switching to a preset that hasn't been tested in game asks first.
  let games = [];
  let currentGame = null;
  $("game").addEventListener("change", async () => {
    const sel = $("game");
    const game = games.find((g) => g.id === sel.value);
    if (game && game.wip) {
      const from = games.find((g) => g.id === currentGame);
      $("wip-title").textContent = `${game.game} is a work in progress`;
      $("wip-keep").textContent = from ? `Keep ${from.game}` : "Cancel";
      $("wip").hidden = false;
      $("wip-switch").focus();
      const ok = await new Promise((resolve) => {
        $("wip-switch").onclick = () => resolve(true);
        $("wip-keep").onclick = () => resolve(false);
        $("wip").onkeydown = (e) => { if (e.key === "Escape") resolve(false); };
      });
      $("wip").hidden = true;
      if (!ok) { sel.value = currentGame; return; }
    }
    await api("/api/control", { command: "game_set", args: { game: sel.value } });
    currentGame = sel.value;
  });

  // -- characters: each has its own deaths and PBs, per game ---------------
  let characters = [];
  const activeChar = () => characters.find((c) => c.active) || {};
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  function renderCharacters(list) {
    if (JSON.stringify(list) === JSON.stringify(characters)) return;
    characters = list || [];
    $("char-card").hidden = !characters.length || !!(info && info.setup_needed);
    $("character").replaceChildren(...characters.map((c) =>
      new Option(`${c.name}  ·  ${plural(c.deaths, "death")}`, c.id, false, c.active)));
    $("char-delete").classList.toggle("off", characters.length < 2);
    $("char-delete").title = characters.length < 2 ? "You need at least one character" : "";
  }

  async function charCommand(command, args) {
    const r = await api("/api/control", { command, args });
    return r;
  }

  $("character").addEventListener("change", () => charCommand("character_set", { id: Number($("character").value) }));

  function askName(title, text, ok, value) {
    $("cn-title").textContent = title;
    $("cn-text").textContent = text;
    $("cn-ok").textContent = ok;
    $("cn-name").value = value || "";
    $("cn-msg").textContent = "";
    $("charname").hidden = false;
    $("cn-name").focus();
    $("cn-name").select();
    return new Promise((resolve) => {
      const done = (v) => { $("charname").hidden = true; resolve(v); };
      $("charname").onsubmit = (e) => { e.preventDefault(); done($("cn-name").value.trim()); };
      $("cn-cancel").onclick = () => done(null);
      $("charname").onkeydown = (e) => { if (e.key === "Escape") done(null); };
    });
  }

  $("char-new").addEventListener("click", async (e) => {
    e.preventDefault();
    const name = await askName("New character",
      "Starts from zero deaths and no PBs. You can switch back to your other characters any time.", "Create");
    if (name) await charCommand("character_add", { name });
  });
  $("char-rename").addEventListener("click", async (e) => {
    e.preventDefault();
    const c = activeChar();
    const name = await askName(`Rename ${c.name}`, "Only the name changes; deaths and PBs stay.", "Rename", c.name);
    if (name && name !== c.name) await charCommand("character_rename", { id: c.id, name });
  });
  $("char-delete").addEventListener("click", async (e) => {
    e.preventDefault();
    const c = activeChar();
    $("cd-title").textContent = `Delete ${c.name}?`;
    $("chardel").hidden = false;
    $("cd-cancel").focus();
    const ok = await new Promise((resolve) => {
      $("cd-ok").onclick = () => resolve(true);
      $("cd-cancel").onclick = () => resolve(false);
      $("chardel").onkeydown = (ev) => { if (ev.key === "Escape") resolve(false); };
    });
    $("chardel").hidden = true;
    if (ok) await charCommand("character_delete", { id: c.id });
  });

  // -- hotkeys --------------------------------------------------------------
  // Stored in pynput's format ("<ctrl>+<alt>+="), shown as "Ctrl + Alt + =".
  const HK = [
    ["death_add", "Add a death the counter missed", "<ctrl>+<alt>+=",
     "For when you died but the count didn't go up, for example because something covered the YOU DIED screen. Adds one death to the boss you're fighting."],
    ["death_undo", "Remove the last death", "<ctrl>+<alt>+-",
     "For when a death was counted that shouldn't have been, or you added one by mistake. Takes the most recent death off the count."],
    ["boss_reset", "Reset this boss's deaths and PB", "<ctrl>+<alt>+r",
     "Starts the boss on screen over from zero: its deaths and PB are wiped. It can't be undone, so untick it if you don't need it."],
    ["boss_clear", "Clear the boss on screen", "<ctrl>+<alt>+c",
     "Takes the boss off the overlay until the next boss health bar appears. Useful when an old boss is still showing after you've left the fight. Nothing is deleted."],
    ["snapshot", "Save what it sees, for calibrating", "<ctrl>+<alt>+s",
     "Saves a picture of what SoulsOverlay sees into the data folder, without leaving the game. Only needed if deaths or bosses aren't being picked up and you want to fix or report it."],
  ];
  const CODE_KEYS = { Minus: "-", Equal: "=", BracketLeft: "[", BracketRight: "]", Semicolon: ";", Quote: "'",
    Backquote: "`", Backslash: "\\", Comma: ",", Period: ".", Slash: "/", Space: "<space>", ArrowUp: "<up>",
    ArrowDown: "<down>", ArrowLeft: "<left>", ArrowRight: "<right>", Home: "<home>", End: "<end>",
    PageUp: "<page_up>", PageDown: "<page_down>", Insert: "<insert>", Delete: "<delete>", Pause: "<pause>",
    ScrollLock: "<scroll_lock>" };
  let hkKeys = {};
  let hkOff = new Set();
  let listening = null;

  function keyFromEvent(e) {
    const c = e.code;
    if (/^Key[A-Z]$/.test(c)) return c.slice(3).toLowerCase();
    if (/^Digit\d$/.test(c)) return c.slice(5);
    if (/^F\d{1,2}$/.test(c)) return `<${c.toLowerCase()}>`;
    return CODE_KEYS[c] || null;
  }

  function pretty(combo) {
    if (!combo) return "Not set";
    return combo.split("+").map((k) => {
      const m = k.match(/^<(.+)>$/);
      if (!m) return k.toUpperCase();
      const n = m[1];
      return { ctrl: "Ctrl", alt: "Alt", shift: "Shift", cmd: "Win", page_up: "Page Up", page_down: "Page Down",
               scroll_lock: "Scroll Lock" }[n] || n.charAt(0).toUpperCase() + n.slice(1);
    }).join(" + ");
  }

  function renderHotkeys() {
    $("hotkeys").classList.toggle("off", !$("hk-enabled").checked);
    hideTip();
    $("hk-rows").replaceChildren(...HK.map(([id, what, , why]) => {
      const row = document.createElement("div");
      row.className = "hk-row" + (hkOff.has(id) ? " row-off" : "");
      const label = document.createElement("label");
      label.className = "what";
      const tick = document.createElement("input");
      tick.type = "checkbox"; tick.checked = !hkOff.has(id);
      tick.title = "Use this hotkey";
      tick.addEventListener("change", () => { tick.checked ? hkOff.delete(id) : hkOff.add(id); renderHotkeys(); });
      label.append(tick, " " + what);
      const box = document.createElement("button");
      box.className = "keys" + (listening === id ? " listening" : hkKeys[id] ? "" : " none");
      box.textContent = listening === id ? "Press keys…" : pretty(hkKeys[id]);
      box.addEventListener("click", () => { listening = listening === id ? null : id; $("hk-msg").textContent = ""; renderHotkeys(); });
      row.append(label, box);
      label.addEventListener("mouseenter", () => showTip(row, why));
      label.addEventListener("mouseleave", hideTip);
      tick.addEventListener("focus", () => showTip(row, why));
      tick.addEventListener("blur", hideTip);
      return row;
    }));
  }

  // Hover help for each hotkey, in a fixed spot under the list so it never covers anything.
  const TIP_IDLE = "Hover over a hotkey to see what it's for.";
  function showTip(_row, text) { $("hk-tip").textContent = text; $("hk-tip").classList.add("on"); }
  function hideTip() { $("hk-tip").textContent = TIP_IDLE; $("hk-tip").classList.remove("on"); }

  document.addEventListener("keydown", (e) => {
    if (!listening || $("hotkeys").hidden) return;
    e.preventDefault();
    if (e.code === "Escape") { listening = null; renderHotkeys(); return; }
    const key = keyFromEvent(e);
    if (!key) return;  // a modifier on its own, or a key hotkeys can't use
    const mods = [e.ctrlKey && "<ctrl>", e.altKey && "<alt>", e.shiftKey && "<shift>", e.metaKey && "<cmd>"].filter(Boolean);
    if (!mods.length && !key.startsWith("<f")) {
      $("hk-msg").textContent = "Add Ctrl, Alt or Shift, or it would go off while you type.";
      return;
    }
    hkKeys[listening] = [...mods, key].join("+");
    $("hk-msg").textContent = "";
    listening = null;
    renderHotkeys();
  });

  async function openHotkeys() {
    const data = await api("/api/hotkeys");
    hkKeys = { ...data.keys };
    hkOff = new Set(data.off || []);
    $("hk-enabled").checked = data.enabled;
    listening = null;
    $("hk-msg").textContent = data.available ? "" : "Hotkeys need the pynput package (included in SoulsOverlay.exe).";
    renderHotkeys();
    $("hotkeys").hidden = false;
  }
  $("open-hotkeys").addEventListener("click", () => { closeSettings(); openHotkeys(); });
  $("hk-enabled").addEventListener("change", renderHotkeys);
  $("hk-cancel").addEventListener("click", () => { listening = null; hideTip(); $("hotkeys").hidden = true; });
  $("hk-defaults").addEventListener("click", () => {
    for (const [id, , def] of HK) hkKeys[id] = def;
    hkOff = new Set();
    $("hk-enabled").checked = true; listening = null; renderHotkeys();
  });
  $("hk-save").addEventListener("click", async () => {
    try {
      await api("/api/hotkeys", { enabled: $("hk-enabled").checked, keys: hkKeys, off: [...hkOff] });
      $("hotkeys").hidden = true;
    } catch (err) { $("hk-msg").textContent = err.message; }
  });

  // -- the game that's running (Steam says which) ---------------------------
  async function control(command, args) {
    await api("/api/control", { command, args: args || {} });
  }

  function renderGameDetect() {
    const gd = state && state.game_detect;
    const card = $("gamedetect");
    let title = "", detail = "", buttons = [], auto = null;
    if (gd && gd.offer) {
      const run = gd.running, cur = state.game.name;
      title = `You're playing ${run.name}`;
      detail = `SoulsOverlay is set to ${cur}. Switch, so deaths count for your ${run.name} characters?`;
      buttons = [button(`Switch to ${run.name}`, "primary", () => setGame(run.id)),
                 button(`Keep ${cur}`, "", () => control("game_keep"))];
      if (!gd.auto_switch) auto = ["Always switch by itself", true];
    } else if (gd && gd.switched_from) {
      title = `Switched to ${state.game.name}`;
      detail = "Also switched your character profile to match the game currently running.";
      buttons = [button("OK", "primary", () => control("game_notice_ok")),
                 button(`Back to ${gd.switched_from.name}`, "", () => setGame(gd.switched_from.id))];
      auto = ["Don't switch by itself, ask first", false];
    }
    card.hidden = !title;
    $("gd-title").textContent = title;
    $("gd-detail").textContent = detail;
    $("gd-actions").replaceChildren(...buttons);
    $("gd-auto").hidden = !auto;
    if (auto) {
      $("gd-auto").textContent = auto[0];
      $("gd-auto").onclick = async (e) => {
        e.preventDefault();
        await api("/api/game_detect", { auto_switch: auto[1] });
      };
    }
  }

  async function setGame(id) {
    await control("game_set", { game: id });
  }

  // -- updates (SoulsOverlay.exe asks GitHub; nothing downloads until confirmed)
  let update = null;
  let confirming = false;
  let pollTimer = null;

  function button(label, cls, onClick) {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    b.addEventListener("click", onClick);
    return b;
  }

  function renderUpdate() {
    const card = $("update"), actions = $("update-actions");
    const u = update || {};
    const v = u.latest ? u.latest.version : "";
    let show = true, title = "", detail = "", buttons = [], bar = false, bad = false;
    if (u.state === "available" && confirming) {
      title = `Install SoulsOverlay ${v} now?`;
      detail = "It downloads from GitHub, closes and reopens by itself. Your settings, stats and OBS details are kept.";
      buttons = [button("Yes, update", "primary", install), button("Not now", "", () => { confirming = false; renderUpdate(); })];
    } else if (u.state === "available") {
      title = `SoulsOverlay ${v} is available`;
      detail = `You have ${u.current}.`;
      buttons = [u.can_install ? button("Update…", "primary", () => { confirming = true; renderUpdate(); })
                               : button("Download", "primary", () => openExternal(u.latest.url)),
                 button("What's new", "", () => openExternal(u.latest.url))];
    } else if (u.state === "downloading") {
      title = `Downloading SoulsOverlay ${v}…`;
      detail = "SoulsOverlay restarts by itself when it's done.";
      bar = true;
    } else if (u.state === "restarting") {
      title = "Restarting into the new version…"; detail = "This window closes and opens again in a moment.";
    } else if (u.state === "error") {
      bad = true; title = "The update didn't install";
      const why = (u.error || "").replace(/^./, (c) => c.toUpperCase()).replace(/\.?$/, ".");
      detail = why + " Nothing was changed.";
      buttons = [button("Try again", "", async () => { await checkUpdates(); })];
    } else {
      show = false;
    }
    card.hidden = !show;
    card.classList.toggle("bad", bad);
    $("update-title").textContent = title;
    $("update-detail").textContent = detail;
    $("update-bar").hidden = !bar;
    $("update-fill").style.width = `${Math.round((u.progress || 0) * 100)}%`;
    actions.replaceChildren(...buttons);
    clearTimeout(pollTimer);
    if (u.state === "downloading" || u.state === "checking") pollTimer = setTimeout(loadUpdate, 700);
  }

  async function loadUpdate() {
    try { update = await api("/api/update"); } catch { return; }
    renderUpdate();
  }

  async function checkUpdates() {
    const link = $("check-updates");
    link.textContent = "Checking…";
    try {
      update = await api("/api/update/check", {});
      link.textContent = update.state === "latest" ? "Up to date ✓" : update.state === "available" ? "Update found" : "Couldn't check";
    } catch { link.textContent = "Couldn't check"; }
    setTimeout(() => { link.textContent = "Check for updates"; }, 3000);
    confirming = false;
    renderUpdate();
  }

  async function install() {
    confirming = false;
    try { update = await api("/api/update/install", {}); }
    catch (e) { update = { ...update, state: "error", error: e.message }; }
    update.state = update.state === "available" ? "downloading" : update.state;
    renderUpdate();
  }

  function openExternal(url) {
    if (!/^https:\/\/github\.com\//.test(url)) return;
    if (native && native.open_external) native.open_external(url);
    else window.open(url, "_blank", "noopener");
  }

  $("check-updates").addEventListener("click", (e) => { e.preventDefault(); checkUpdates(); });

  // -- native extras (only inside the exe's window) ----------------------
  async function setupNative() {
    native = window.pywebview.api;
    document.querySelectorAll(".native").forEach((el) => { el.hidden = false; });
    $("st-tray").checked = (await native.get_prefs()).close_to_tray;
    $("open-data").addEventListener("click", (e) => { e.preventDefault(); native.open_data_folder(); });
  }
  if (window.pywebview && window.pywebview.api) setupNative();
  else window.addEventListener("pywebviewready", setupNative);

  // -- data -------------------------------------------------------------
  async function loadInfo() {
    info = await api("/api/launcher");
    $("version").textContent = "v" + info.version;
    $("hud-url").value = info.hud_url;
    if (!connectOpen) fillConnect();
    renderStatus();
  }

  async function loadGames() {
    const data = await api("/api/games");
    const sel = $("game");
    games = data.games;
    currentGame = data.current;
    sel.replaceChildren(...data.games.map((g) => new Option(g.name, g.id, false, g.id === data.current)));
  }

  function connectWs() {
    const ws = new WebSocket(`ws://${location.host}/overlay/ws`);
    ws.onopen = () => ws.send(JSON.stringify({ kind: "hello", role: "launcher" }));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.kind === "hud_status") $("refresh").hidden = !msg.stale;
      if (msg.kind === "state") {
        const gameChanged = state && state.game.id !== msg.state.game.id;
        state = msg.state;
        renderCharacters(state.characters);
        renderGameDetect();
        if (gameChanged) { $("game").value = state.game.id; currentGame = state.game.id; }
        renderStatus();
      }
    };
    ws.onclose = () => setTimeout(connectWs, 1000);
  }

  if (!token) {
    $("status-title").textContent = "Open this window from SoulsOverlay";
    $("status-detail").textContent = "It needs the private link the app opens it with.";
    return;
  }
  loadUpdate();
  setTimeout(loadUpdate, 4000);  // the start-up check runs in the background
  loadInfo().then(loadGames).catch((e) => { $("status-title").textContent = "Something went wrong"; $("status-detail").textContent = e.message; });
  connectWs();
})();
