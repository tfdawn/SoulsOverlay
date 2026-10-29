"""The launcher window: SoulsOverlay without a terminal.

Runs the capture service and overlay server on a background thread and shows
web/launcher.html in a small native window (pywebview, which uses the Edge
WebView2 that ships with Windows 10 and 11). Closing the window keeps the app
running in the system tray (pystray), unless that's turned off in Settings;
Quit in the tray menu stops it. If either
library is missing, the page opens in the normal browser instead and the
terminal keeps the app alive.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__, app, updater

log = logging.getLogger(__name__)

# The window's own preferences, kept in data/launcher.json.
PREFS = {"close_to_tray": False,  # closing the window hides it to the tray instead of quitting
         "tray_notice": True}    # say so when it does


class Backend:
    """The service and server on their own thread and event loop."""

    def __init__(self, cfg, after_update: bool = False):
        self.cfg = cfg
        self.after_update = after_update
        self.on_update_ready = None  # set by run(): quit so the new exe can take over
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.error: BaseException | None = None
        self.service = None
        self.thread = threading.Thread(target=self._run, name="backend", daemon=True)

    def start(self):
        self.thread.start()
        self.ready.wait(30)
        if self.error:
            raise self.error

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except BaseException as e:  # reported by start(), or logged if it dies later
            self.error = e
            log.exception("SoulsOverlay stopped with an error")
            self.ready.set()

    async def _main(self):
        from aiohttp import web

        from .events import load_plugins
        from .hotkeys import start_hotkeys
        from .server import OverlayServer
        from .service import Service

        cfg = self.cfg
        self.service = Service(cfg)
        # The window always opens stopped: counting starts when you click Start
        # (on the first start, after the OBS details are saved).
        self.service.stopped = True
        self.service.status["capture"] = "stopped"
        server = OverlayServer(self.service, cfg.control_token())
        server.updater = updater.Updater()
        server.on_update_ready = lambda: self.on_update_ready and self.on_update_ready()
        if cfg.check_updates:
            threading.Thread(target=server.updater.check, name="update-check", daemon=True).start()
        load_plugins(cfg.plugins, self.service.bus, self.service.store, cfg)
        runner = web.AppRunner(server.app(), access_log=None)
        await runner.setup()
        # Right after an update the old exe may still be letting go of the port.
        for attempt in range(40 if self.after_update else 1):
            try:
                await web.TCPSite(runner, cfg.server.host, cfg.server.port).start()
                break
            except OSError as e:
                if attempt == (39 if self.after_update else 0):
                    raise RuntimeError(f"Port {cfg.server.port} is in use. Is SoulsOverlay already running?") from e
                await asyncio.sleep(0.25)
        server.hotkeys = start_hotkeys(cfg.hotkeys, self.service, asyncio.get_running_loop())
        log.info("SoulsOverlay %s: HUD at %s", __version__, self.url("overlay/hud", token=False))
        self.ready.set()
        try:
            await self.service.run()
        finally:
            await runner.cleanup()

    def url(self, page: str, token: bool = True) -> str:
        base = f"http://127.0.0.1:{self.cfg.server.port}/{page}"
        return f"{base}#token={self.cfg.control_token()}" if token else base

    def control(self, command: str):
        fut = asyncio.run_coroutine_threadsafe(self.service.control(command), self.loop)
        return fut.result(10)


class Api:
    """Called from launcher.js as window.pywebview.api.*"""

    def __init__(self, cfg):
        self._cfg = cfg
        self._path = cfg.data_dir / "launcher.json"
        self._window = None  # private: pywebview walks public attributes of js_api

    def _saved(self) -> dict:
        try:
            saved = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        return saved if isinstance(saved, dict) else {}

    def get_prefs(self) -> dict:
        saved = self._saved()
        return {k: saved[k] if isinstance(saved.get(k), bool) else v for k, v in PREFS.items()}

    def set_pref(self, name: str, on: bool) -> dict:
        # Only what the user changed is saved, so the others follow the defaults.
        if name in PREFS:
            saved = {k: v for k, v in self._saved().items() if k in PREFS}
            saved[name] = bool(on)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        return self.get_prefs()

    def hide_window(self):
        if self._window:
            self._window.hide()

    def open_url(self, url: str):
        if url.startswith("http://127.0.0.1:"):
            webbrowser.open(url)

    def open_external(self, url: str):
        if url.startswith("https://github.com/"):
            webbrowser.open(url)

    def copy(self, text: str):
        _copy(text)

    def open_data_folder(self):
        folder = self._cfg.data_dir.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)  # noqa: S606 - our own folder


def _copy(text: str):
    if os.name == "nt":
        subprocess.run(["clip"], input=text.encode("utf-16-le"), check=False,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _log_to_file(cfg):
    """No terminal in the exe, so the log goes to data/soulsoverlay.log."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(cfg.data_dir / "soulsoverlay.log", maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)


def _tray(backend: Backend, show, quit_app):
    try:
        import pystray
        from PIL import Image
    except ImportError:
        log.info("no tray icon: pystray is not installed")
        return None
    icon_path = app.bundle_dir() / "packaging" / "soulsoverlay.ico"
    if not icon_path.exists():
        icon_path = Path(__file__).resolve().parents[1] / "packaging" / "soulsoverlay.ico"
    image = Image.open(icon_path) if icon_path.exists() else Image.new("RGB", (64, 64), (224, 168, 90))

    def toggle(_icon, _item):
        backend.control("start" if backend.service.stopped else "stop")

    menu = pystray.Menu(
        pystray.MenuItem("Show window", lambda: show(), default=True),
        pystray.MenuItem("Open settings", lambda: webbrowser.open(backend.url("settings"))),
        pystray.MenuItem("Copy OBS URL", lambda: _copy(backend.url("overlay/hud", token=False))),
        pystray.MenuItem("Calibrate", lambda: webbrowser.open(backend.url("calibrate"))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda _item: "Start" if backend.service.stopped else "Stop", toggle),
        pystray.MenuItem("Quit", lambda: quit_app()),
    )
    icon = pystray.Icon("SoulsOverlay", image, "SoulsOverlay", menu)
    icon.run_detached()
    return icon


def run(cfg, after_update: bool = False):
    if app.FROZEN:
        _log_to_file(cfg)
    updater.cleanup_old()
    backend = Backend(cfg, after_update=after_update)
    try:
        backend.start()
    except BaseException as e:
        app.error_box(f"SoulsOverlay couldn't start:\n\n{e}")
        raise SystemExit(1)

    # An installed update starts the new exe itself; this one just has to go.
    backend.on_update_ready = lambda: os._exit(0)
    try:
        import webview
    except ImportError:
        _in_browser(backend)
        return

    api = Api(cfg)
    window = webview.create_window(
        "SoulsOverlay", backend.url("launcher"), js_api=api, width=480, height=760,
        min_size=(420, 520), background_color="#0b0908")
    api._window = window
    quitting = False

    def quit_app():
        nonlocal quitting
        quitting = True
        if tray:
            tray.stop()
        window.destroy()

    try:
        tray = _tray(backend, window.show, quit_app)
    except Exception:  # no tray on this desktop: closing the window quits
        log.exception("no tray icon")
        tray = None

    def on_closing():
        # With a tray icon, closing the window only hides it (unless that's
        # turned off in Settings). The page first says so, and where to change it.
        if not tray or quitting:
            return True
        prefs = api.get_prefs()
        if not prefs["close_to_tray"]:
            return True
        if prefs["tray_notice"]:
            # Not from inside this handler: it runs on the window's own thread.
            def notice():
                try:
                    shown = window.evaluate_js("window.trayNotice ? (trayNotice(), true) : false")
                except Exception:
                    shown = False
                if not shown:
                    window.hide()
            threading.Thread(target=notice, daemon=True).start()
        else:
            window.hide()
        return False

    window.events.closing += on_closing
    backend.on_update_ready = quit_app
    try:
        webview.start(private_mode=False, storage_path=str(cfg.data_dir / "webview"))
    except Exception:  # no WebView2 (or no GUI toolkit off Windows)
        log.exception("couldn't open the launcher window")
        _in_browser(backend)
    if tray:
        tray.stop()
    os._exit(0)  # don't wait on the backend thread or the tray


def _in_browser(backend: Backend):
    """Fallback: the same page in the normal browser; the app runs until closed."""
    print(f"Opening the launcher in your browser: {backend.url('launcher', token=False)}")
    webbrowser.open(backend.url("launcher"))
    backend.thread.join()
