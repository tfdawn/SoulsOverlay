"""Local HTTP/WebSocket server: the overlay, the calibration page, the control API.

Security model
* Binds to loopback only (config refuses anything else).
* Every request must carry a Host header naming this server, which defeats
  DNS-rebinding pages that try to talk to 127.0.0.1 from a public site.
* The HUD (/overlay/hud, /overlay/ws, GET /api/state) is read-only and needs
  no secret, so the URL you paste into OBS reveals nothing if it leaks on
  stream.
* The HUD page may be framed by this server's own settings page (for its
  preview) and by nothing else; the token-holding pages can't be framed.
* Everything that changes state or exposes frames lives under /api/ and
  needs `Authorization: Bearer <token>` plus, when a browser sends one, an
  allowed Origin. No CORS headers are ever sent, so other sites can't even
  get past the preflight.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import weakref
from pathlib import Path

import cv2
import numpy as np
from aiohttp import WSMsgType, web

from . import __version__, hotkeys, style
from .config import save_obs, save_section
from .events import Event
from .service import Service

log = logging.getLogger(__name__)
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 25 * 1024 * 1024


def _json_error(status: int, message: str) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


class OverlayServer:
    def __init__(self, service: Service, token: str):
        self.service = service
        self.token = token
        cfg = service.config.server
        self.port = cfg.port
        self.allowed_hosts = {f"{h}:{cfg.port}" for h in ("127.0.0.1", "localhost", "[::1]")}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts} | set(cfg.allowed_origins)
        self.sockets: weakref.WeakSet = weakref.WeakSet()
        # Set by the launcher (the exe): one-click updates and how to quit for one.
        self.updater = None
        self.on_update_ready = None
        self.hotkeys = None  # the running pynput listener, restarted when hotkeys change
        service.on_state_change(self._broadcast_state)
        service.bus.subscribe(self._broadcast_event)

    # -- app -------------------------------------------------------------
    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._guard], client_max_size=MAX_UPLOAD)
        app.on_shutdown.append(self._close_sockets)
        r = app.router
        r.add_get("/", self.index)
        r.add_get("/overlay/hud", self._static("hud.html"))
        r.add_get("/overlay/hud.js", self._static("hud.js"))
        r.add_get("/overlay/hud.css", self._static("hud.css"))
        r.add_get("/overlay/custom.css", self.custom_css)
        r.add_get("/overlay/style.js", self._static("style.js"))
        r.add_get("/overlay/fx.js", self._static("fx.js"))
        r.add_get("/settings/lab.js", self._static("lab.js"))
        r.add_get("/overlay/settings.json", self.get_settings)
        r.add_get("/overlay/ws", self.overlay_ws)
        r.add_get("/api/state", self.get_state)
        r.add_get("/calibrate", self._static("calibrate.html"))
        r.add_get("/calibrate/calibrate.js", self._static("calibrate.js"))
        r.add_get("/calibrate/calibrate.css", self._static("calibrate.css"))
        r.add_get("/settings", self._static("settings.html"))
        r.add_get("/settings/settings.js", self._static("settings.js"))
        r.add_get("/settings/settings.css", self._static("settings.css"))
        r.add_get("/launcher", self._static("launcher.html"))
        r.add_get("/launcher/launcher.js", self._static("launcher.js"))
        r.add_get("/launcher/launcher.css", self._static("launcher.css"))
        # Authenticated below this line (see _guard).
        r.add_post("/api/control", self.control)
        r.add_get("/api/games", self.games)
        r.add_get("/api/calibrate/frame", self.cal_frame)
        r.add_post("/api/calibrate/grab", self.cal_grab)
        r.add_post("/api/calibrate/upload", self.cal_upload)
        r.add_post("/api/calibrate/resume", self.cal_resume)
        r.add_get("/api/calibrate/profile", self.cal_profile)
        r.add_post("/api/calibrate/profile", self.cal_save_profile)
        r.add_post("/api/calibrate/diagnose", self.cal_diagnose)
        r.add_post("/api/calibrate/template", self.cal_template)
        r.add_post("/api/calibrate/autofind", self.cal_autofind)
        r.add_post("/api/settings", self.save_settings)
        r.add_get("/api/launcher", self.launcher_info)
        r.add_post("/api/launcher/obs", self.launcher_obs)
        r.add_get("/api/hotkeys", self.get_hotkeys)
        r.add_post("/api/hotkeys", self.save_hotkeys)
        r.add_get("/api/update", self.update_status)
        r.add_post("/api/update/check", self.update_check)
        r.add_post("/api/update/install", self.update_install)
        return app

    async def index(self, _request):
        raise web.HTTPFound("/overlay/hud")

    PUBLIC_API = {("GET", "/api/state")}

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        if request.host not in self.allowed_hosts:
            return _json_error(421, "bad host")
        if request.path.startswith("/api/") and (request.method, request.path) not in self.PUBLIC_API:
            origin = request.headers.get("Origin")
            if origin is not None and origin not in self.allowed_origins:
                return _json_error(403, "origin not allowed")
            auth = request.headers.get("Authorization", "")
            given = auth[7:] if auth.startswith("Bearer ") else ""
            if not given or not hmac.compare_digest(given.encode(), self.token.encode()):
                return _json_error(401, "missing or bad token")
            if request.method == "POST" and request.path != "/api/calibrate/upload":
                if request.content_type != "application/json":
                    return _json_error(415, "expected application/json")
        resp = await handler(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    def _static(self, name: str):
        path = WEB / name
        # The HUD shows in the settings page's preview; nothing else may frame a page.
        framers = "'self'" if name == "hud.html" else "'none'"

        async def handler(_request):
            resp = web.FileResponse(path)
            if name.endswith(".html"):
                resp.headers["Content-Security-Policy"] = (
                    "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline';"
                    f" connect-src 'self' ws://127.0.0.1:* ws://localhost:*; frame-ancestors {framers}")
            return resp

        return handler

    # -- overlay ---------------------------------------------------------
    async def custom_css(self, _request):
        path = self.service.config.custom_css_path
        text = path.read_text(encoding="utf-8") if path.exists() else "/* data/overlay.css */\n"
        return web.Response(text=text, content_type="text/css")

    async def get_settings(self, _request):
        # Read-only and secret-free, like the overlay itself.
        return web.json_response({"schema": style.SCHEMA,
                                  "values": style.load(self.service.config.style_path)})

    async def save_settings(self, request):
        try:
            body = await request.json()
            values = style.save(self.service.config.style_path, body.get("values", {}))
        except (ValueError, json.JSONDecodeError, AttributeError) as e:
            return _json_error(400, str(e))
        await self._send_all({"kind": "settings", "values": values})
        return web.json_response({"ok": True, "values": values})

    async def get_state(self, _request):
        return web.json_response(self.service.state())

    async def overlay_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        self.sockets.add(ws)
        await ws.send_json({"kind": "state", "state": self.service.state()})
        async for msg in ws:  # read-only: incoming messages are ignored
            if msg.type == WSMsgType.ERROR:
                break
        self.sockets.discard(ws)
        return ws

    async def _close_sockets(self, _app):
        # Close overlay connections cleanly on Ctrl+C, instead of leaving
        # aiohttp to cancel them mid-read (which prints a scary traceback).
        for ws in list(self.sockets):
            await ws.close(code=1001, message=b"server shutting down")

    async def _send_all(self, payload: dict):
        data = json.dumps(payload)
        for ws in list(self.sockets):
            if ws.closed:
                continue
            try:
                await ws.send_str(data)
            except (ConnectionError, RuntimeError):
                pass

    async def _broadcast_state(self, state: dict):
        await self._send_all({"kind": "state", "state": state})

    async def _broadcast_event(self, event: Event):
        await self._send_all({"kind": "event", "event": event.to_json()})

    # -- control ---------------------------------------------------------
    async def control(self, request):
        try:
            body = await request.json()
            result = await self.service.control(body.get("command", ""), body.get("args") or {})
        except (ValueError, json.JSONDecodeError, FileNotFoundError) as e:
            return _json_error(400, str(e))
        return web.json_response(result)

    # -- launcher ----------------------------------------------------------
    async def launcher_info(self, _request):
        cfg = self.service.config
        return web.json_response({
            "version": __version__,
            "hud_url": f"http://127.0.0.1:{self.port}/overlay/hud",
            "setup_needed": cfg.path is None or not cfg.path.exists(),
            "obs": {"host": cfg.obs.host, "port": cfg.obs.port, "source": cfg.obs.source,
                    "password_set": bool(cfg.obs.password)},
            "stopped": self.service.stopped,
        })

    async def launcher_obs(self, request):
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return _json_error(400, str(e))
        cfg = self.service.config
        source = str(body.get("source", "")).strip()[:200]
        if not source:
            return _json_error(400, "Type the name of your game source in OBS.")
        # A blank password field keeps the saved one, unless asked to clear it.
        password = body.get("password")
        if password is None or (password == "" and not body.get("clear_password")):
            password = cfg.obs.password
        password = str(password)[:500]
        if cfg.path is not None:
            await asyncio.to_thread(save_obs, cfg.path, password, source)
        await self.service.set_obs(password, source)
        return web.json_response({"ok": True})

    # -- hotkeys ---------------------------------------------------------------
    def _hotkeys_json(self):
        hk = self.service.config.hotkeys
        try:
            import pynput  # noqa: F401
            available = True
        except ImportError:
            available = False
        return {"enabled": hk.enabled, "available": available, "running": self.hotkeys is not None,
                "keys": {a: getattr(hk, a) for a in hotkeys.ACTIONS},
                "off": [a for a in hk.off if a in hotkeys.ACTIONS]}

    async def get_hotkeys(self, _request):
        return web.json_response(self._hotkeys_json())

    async def save_hotkeys(self, request):
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return _json_error(400, str(e))
        keys = body.get("keys") or {}
        new = {}
        for action in hotkeys.ACTIONS:
            combo = str(keys.get(action, "")).strip()[:60]
            if combo and (why := hotkeys.check(combo)):
                return _json_error(400, f"{action}: {why}")
            new[action] = combo
        off = [a for a in hotkeys.ACTIONS if a in (body.get("off") or [])]
        used = [c for a, c in new.items() if c and a not in off]
        if len(used) != len(set(used)):
            return _json_error(400, "Two actions have the same keys.")
        cfg = self.service.config
        cfg.hotkeys.enabled = bool(body.get("enabled", True))
        cfg.hotkeys.off = off
        for action, combo in new.items():
            setattr(cfg.hotkeys, action, combo)
        if cfg.path is not None:
            await asyncio.to_thread(save_section, cfg.path, "hotkeys",
                                    {"enabled": cfg.hotkeys.enabled, **new, "off": off})
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self.hotkeys = hotkeys.start_hotkeys(cfg.hotkeys, self.service, asyncio.get_running_loop())
        return web.json_response(self._hotkeys_json())

    # -- updates (launcher only) ----------------------------------------------
    async def update_status(self, _request):
        if self.updater is None:
            return web.json_response({"state": "unsupported"})
        return web.json_response(self.updater.status())

    async def update_check(self, _request):
        if self.updater is None:
            return _json_error(404, "updates are only available in SoulsOverlay.exe")
        await asyncio.to_thread(self.updater.check)
        return web.json_response(self.updater.status())

    async def update_install(self, _request):
        up = self.updater
        if up is None or not up.can_install or up.state != "available":
            return _json_error(409, "no update to install")

        async def install():
            try:
                new = await asyncio.to_thread(up.download)
                await asyncio.to_thread(up.swap_and_restart, new)
            except Exception as e:
                log.exception("update failed")
                up._set(state="error", error=str(e))
                return
            if self.on_update_ready:
                self.on_update_ready()

        asyncio.get_running_loop().create_task(install())
        return web.json_response(up.status())

    async def games(self, _request):
        return web.json_response({"games": self.service.games(), "current": self.service.profile.id})

    # -- calibration -----------------------------------------------------
    async def cal_frame(self, _request):
        data = self.service.frame_jpeg()
        if data is None:
            return _json_error(404, "no frame yet: grab one from OBS or load a screenshot")
        return web.Response(body=data, content_type="image/jpeg")

    async def cal_grab(self, _request):
        try:
            frame = await asyncio.to_thread(self.service.capture.grab)
        except Exception as e:
            return _json_error(502, f"could not grab from OBS: {e}")
        self.service.set_paused_frame(frame)
        return web.json_response({"ok": True, "w": frame.shape[1], "h": frame.shape[0]})

    async def cal_upload(self, request):
        body = await request.read()
        img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return _json_error(400, "not an image")
        self.service.set_paused_frame(img)
        return web.json_response({"ok": True, "w": img.shape[1], "h": img.shape[0]})

    async def cal_resume(self, _request):
        self.service.paused = False
        return web.json_response({"ok": True})

    async def cal_profile(self, _request):
        p = self.service.profile
        return web.json_response({"id": p.id, "profile": p.to_json(), "effective": p.data})

    async def cal_save_profile(self, request):
        body = await request.json()
        allowed = {"regions", "boss_slots", "bar_colors", "death", "victory", "ocr", "tracking", "hud_scale"}
        changes = {k: v for k, v in body.items() if k in allowed}
        if not changes:
            return _json_error(400, "nothing to save")
        for slot in changes.get("boss_slots", []):
            for key in ("name", "bar"):
                _check_region(slot.get(key))
        for region in changes.get("regions", {}).values():
            _check_region(region)
        p = self.service.profile
        # Lists replace wholesale; dicts merge.
        if "boss_slots" in changes:
            p.raw["boss_slots"] = changes.pop("boss_slots")
        p.update(changes)
        p.save()
        self.service.reload_profile()
        return web.json_response({"ok": True})

    async def cal_diagnose(self, _request):
        result = await asyncio.to_thread(self.service.diagnose)
        if result is None:
            return _json_error(404, "no frame yet")
        return web.json_response(result)

    async def cal_template(self, request):
        body = await request.json()
        try:
            rel = self.service.save_template(body.get("kind", "death"))
        except ValueError as e:
            return _json_error(400, str(e))
        return web.json_response({"ok": True, "template": rel})

    async def cal_autofind(self, _request):
        try:
            result = await asyncio.to_thread(self.service.auto_find)
        except ValueError as e:
            return _json_error(422, str(e))
        return web.json_response(result)


def _check_region(r):
    if r is None:
        return
    if (not isinstance(r, list) or len(r) != 4
            or not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in r)):
        raise web.HTTPBadRequest(text="regions are [x, y, w, h] fractions between 0 and 1")
