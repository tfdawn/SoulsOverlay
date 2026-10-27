"""Ties capture, detection, tracking, storage and events together."""

from __future__ import annotations

import asyncio
import logging
import time

import cv2
import numpy as np

from .capture import Backoff, ObsCapture
from .config import Config
from .detect import bossname
from .detect.analyzer import Analyzer, FrameReading
from .detect.screen import save_template
from .events import Event, EventBus
from .profiles import Profile, list_profiles, load_profile
from .store import Store
from .tracker import Tracker

log = logging.getLogger(__name__)

CONTROL_COMMANDS = ("death_add", "death_undo", "boss_reset", "boss_set", "boss_clear", "game_set",
                    "character_set", "character_add", "character_rename", "character_delete",
                    "snapshot", "start", "stop")


class Service:
    def __init__(self, config: Config, capture=None, store: Store | None = None):
        self.config = config
        self.bus = EventBus()
        self.store = store or Store(config.db_path)
        self.capture = capture or ObsCapture(config.obs.host, config.obs.port, config.obs.password,
                                             config.obs.source, config.obs.capture_width)
        self._state_listeners = []
        self.live: dict | None = None
        self.last_frame: np.ndarray | None = None
        self.last_reading: FrameReading | None = None
        self.status = {"capture": "starting", "capture_error": None, "ocr": "unknown",
                       "detector": None, "fps": 0.0}
        self.paused = False   # calibration has a frame up
        self.stopped = False  # Stop in the launcher: no OBS connection, no detection
        self._backoff = Backoff()
        self._black = False
        try:
            bossname.configure(config.tesseract_cmd)
            self.status["ocr"] = "ok"
        except bossname.OcrUnavailable as e:
            self.status["ocr"] = f"unavailable: {e}"
        self.set_game(config.game)

    # -- game / profile --------------------------------------------------
    def set_game(self, game_id: str):
        self.profile: Profile = load_profile(self.config.profiles_dir, game_id)
        self.analyzer = Analyzer(self.profile)
        self.tracker = Tracker(self.profile)
        self.live = None
        self.store.ensure_game(self.profile.id, self.profile.name)
        self.status["detector"] = self.analyzer.death.mode

    def reload_profile(self):
        """Pick up a saved calibration without losing the current fight."""
        self.profile = load_profile(self.config.profiles_dir, self.profile.id)
        self.analyzer = Analyzer(self.profile)
        self.tracker.profile = self.profile
        self.status["detector"] = self.analyzer.death.mode

    def games(self) -> list[dict]:
        return list_profiles(self.config.profiles_dir)

    # -- state -----------------------------------------------------------
    def on_state_change(self, callback):
        self._state_listeners.append(callback)

    async def _notify(self):
        state = self.state()
        for cb in list(self._state_listeners):
            try:
                await cb(state)
            except Exception:
                log.exception("state listener failed")

    def state(self) -> dict:
        game = self.profile.id
        boss_name = self.tracker.display_boss
        boss = self.store.boss_stats(game, boss_name)
        if boss is not None:
            enc = self.tracker.encounter
            engaged = enc is not None and enc.boss == boss_name
            boss.update({
                "engaged": engaged,
                "phase": enc.phase if engaged else None,
                "max_phases": self.profile.max_phases(boss_name),
                "live_pct": self.live["pct"] if engaged and self.live else None,
                "bar_up": engaged and self.tracker.bar_up,
                "pinned": self.tracker.pinned_boss == boss_name,
            })
        return {
            "game": {"id": game, "name": self.profile.name, **self.store.game_stats(game)},
            "characters": self.store.characters(game),
            "boss": boss,
            "status": dict(self.status),
            # Where the game draws its boss bar, as fractions of the frame, so
            # the HUD overlay can sit on top of it.
            "layout": {k: (self.profile.boss_slots[0].get(k) if self.profile.boss_slots else None)
                       for k in ("bar", "name")},
        }

    # -- tracker events -> storage/bus -----------------------------------
    async def apply(self, events: list[tuple[str, dict]]):
        game = self.profile.id
        changed = False
        for kind, data in events:
            if kind not in ("live", "bar"):
                # One line per detection, so the terminal shows what the
                # counter is seeing without opening the calibration page.
                log.info("%s: %s", kind, ", ".join(f"{k}={v}" for k, v in data.items()))
            if kind == "live":
                if self.live != data:
                    self.live = data
                    changed = True
            elif kind == "engage":
                self.live = None
                await self.bus.publish(Event("boss_engaged", {"game": game, "boss": data["boss"]}))
                changed = True
            elif kind == "phase":
                await self.bus.publish(Event("phase", {"game": game, **data}))
                changed = True
            elif kind == "death":
                await self._death(data["boss"], data["phase"], data["pct"], data.get("source", "auto"))
                changed = True
            elif kind == "kill":
                result = self.store.record_kill(game, data["boss"], data["phase"])
                await self.bus.publish(Event("kill", {"game": game, **result}))
                self.live = None
                changed = True
            elif kind == "disengage":
                self.live = None
                changed = True
            elif kind == "bar":
                changed = True
        if changed:
            await self._notify()

    async def _death(self, boss, phase, pct, source):
        game = self.profile.id
        result = self.store.record_death(game, boss, phase, pct, source)
        stats = self.store.boss_stats(game, boss)
        payload = {"game": game, "boss": boss, "phase": phase, "pct": pct, "source": source,
                   "boss_deaths": stats["deaths"] if stats else None,
                   "game_deaths": self.store.game_stats(game)["deaths"]}
        await self.bus.publish(Event("death", payload))
        if result["new_pb"]:
            await self.bus.publish(Event("new_pb", {
                "game": game, "boss": boss, "phase": phase, "pct": pct,
                "previous": result["previous_pb"]}))
        self.live = None

    # -- manual control --------------------------------------------------
    async def control(self, command: str, args: dict | None = None) -> dict:
        args = args or {}
        game = self.profile.id
        if command not in CONTROL_COMMANDS:
            raise ValueError(f"unknown command {command}")
        result: dict = {"ok": True}
        if command == "death_add":
            boss, phase, pct = self.tracker.manual_death_context(time.monotonic())
            await self._death(boss, phase, pct, "manual")
            self.tracker.encounter = None
        elif command == "death_undo":
            row = self.store.undo_last_death(game)
            result["undone"] = row
            if row:
                await self.bus.publish(Event("death_undone", {"game": game, **row}))
        elif command == "boss_reset":
            boss = args.get("boss") or self.tracker.display_boss
            if boss:
                result["voided"] = self.store.reset_boss(game, boss)
                await self.bus.publish(Event("boss_reset", {"game": game, "boss": boss}))
        elif command == "boss_set":
            name = str(args.get("boss", "")).strip()[:120]
            if not name:
                raise ValueError("boss name required")
            match = self.profile.match_boss(name)
            boss = match.boss if match else name
            self.tracker.pin_boss(boss)
            result["boss"] = boss
            await self.bus.publish(Event("boss_changed", {"game": game, "boss": boss, "manual": True}))
        elif command == "boss_clear":
            self.tracker.pin_boss(None)
            self.tracker.last_boss = None
            await self.bus.publish(Event("boss_changed", {"game": game, "boss": None, "manual": True}))
        elif command == "character_set":
            self.store.select_character(game, args.get("id"))
        elif command == "character_add":
            result["id"] = self.store.add_character(game, args.get("name"))
        elif command == "character_rename":
            self.store.rename_character(game, args.get("id"), args.get("name"))
        elif command == "character_delete":
            self.store.delete_character(game, args.get("id"))
        elif command == "game_set":
            gid = str(args.get("game", ""))
            if gid not in {g["id"] for g in self.games()}:
                raise ValueError(f"unknown game {gid}")
            self.set_game(gid)
            await self.bus.publish(Event("game_changed", {"game": gid}))
        elif command == "stop":
            self.stopped = True
            self.live = None
            await asyncio.to_thread(self.capture.close)
            self.status.update(capture="stopped", capture_error=None, fps=0.0)
        elif command == "start":
            self.stopped = False
            self._backoff.reset()
            self.status.update(capture="starting", capture_error=None)
        elif command == "snapshot":
            result.update(await asyncio.to_thread(self.snapshot))
            return result
        await self._notify()
        return result

    async def set_obs(self, password: str, source: str):
        """Reconnect with new OBS details (the launcher's Connect to OBS form)."""
        obs = self.config.obs
        obs.password, obs.source = password, source
        old = self.capture
        if isinstance(old, ObsCapture):
            self.capture = ObsCapture(obs.host, obs.port, password, source, obs.capture_width)
            await asyncio.to_thread(old.close)
        self.stopped = False
        self._backoff.reset()
        self.status.update(capture="starting", capture_error=None)
        await self._notify()

    # -- calibration helpers ---------------------------------------------
    def set_paused_frame(self, frame: np.ndarray):
        self.last_frame = frame
        self.paused = True

    def diagnose(self) -> dict | None:
        if self.last_frame is None:
            return None
        reading = Analyzer(self.profile).analyze(self.last_frame, force_ocr=True)
        return {**reading.to_json(), "detector": self.analyzer.death.mode,
                "frame": {"w": int(self.last_frame.shape[1]), "h": int(self.last_frame.shape[0])}}

    def snapshot(self) -> dict:
        """Save the latest live frame and log what detection makes of it.

        Bound to a hotkey so it can be taken from inside the game: alt-tabbing
        to the calibration page makes Game Capture go black.
        """
        if self.last_frame is None:
            raise ValueError("no frame from OBS yet")
        frame = self.last_frame
        folder = self.config.data_dir / "snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / time.strftime("snapshot-%Y%m%d-%H%M%S.png")
        cv2.imwrite(str(path), frame)
        r = Analyzer(self.profile).analyze(frame, force_ocr=True)
        log.info("snapshot saved to %s (%dx%d)", path, frame.shape[1], frame.shape[0])
        log.info("  death screen: %s (score %.2f)", "yes" if r.death else "no", r.death_score)
        for i, s in enumerate(r.slots, 1):
            log.info("  boss %d: health %s, name read as %r, matched %s", i,
                     "no bar" if s.pct is None else f"{s.pct}%", s.text,
                     s.match.boss if s.match else "nothing")
        return {"path": str(path), **r.to_json()}

    def save_template(self, kind: str) -> str:
        if kind not in ("death", "victory"):
            raise ValueError("kind must be death or victory")
        region = self.profile.regions.get(kind)
        if self.last_frame is None or not region:
            raise ValueError(f"need a frame and a '{kind}' region first")
        rel = f"templates/{self.profile.id}_{kind}.png"
        save_template(self.last_frame, region, self.profile.asset_path(rel))
        section = {"template": rel}
        if kind == "victory" and not self.profile.raw.get("victory"):
            section["threshold"] = 0.55
        self.profile.update({kind: section})
        self.profile.save()
        self.reload_profile()
        return rel

    def frame_jpeg(self) -> bytes | None:
        if self.last_frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes() if ok else None

    # -- capture loop ----------------------------------------------------
    async def run(self):
        backoff = self._backoff
        frames, fps_t = 0, time.monotonic()
        while True:
            start = time.monotonic()
            # Faster during a fight: frames are cheap once the name is known,
            # and every frame shaves time off spotting a death.
            fighting = self.tracker.encounter is not None or self.tracker.bar_up
            period = 1.0 / max(0.2, self.config.obs.fight_fps if fighting else self.config.obs.fps)
            if self.paused or self.stopped or not backoff.ready():
                await asyncio.sleep(period)
                continue
            try:
                t_grab = time.monotonic()
                frame = await asyncio.to_thread(self.capture.grab)
                t_grab = time.monotonic() - t_grab
                if self.stopped:  # Stop pressed while that frame was on its way
                    await asyncio.to_thread(self.capture.close)
                    continue
                backoff.ok()
                if self.status["capture"] != "ok":
                    self.status.update(capture="ok", capture_error=None)
                    await self._notify()
            except Exception as e:  # OBS closed, wrong password, source renamed...
                if self.stopped:
                    continue
                backoff.fail()
                msg = f"{type(e).__name__}: {e}"
                if self.status["capture_error"] != msg:
                    log.warning("capture failed: %s", msg)
                    self.status.update(capture="error", capture_error=msg)
                    await self._notify()
                continue
            self.last_frame = frame
            black = frame.max() < 20
            if black != self._black:
                self._black = black
                if black:
                    log.warning("OBS is sending a black picture of '%s'. Is the game minimised or "
                                "alt-tabbed, or is that the wrong source?", self.config.obs.source)
                else:
                    log.info("picture from OBS is back")
                self.status["picture"] = "black" if black else "ok"
                await self._notify()
            try:
                t_an = time.monotonic()
                reading = await asyncio.to_thread(self.analyzer.analyze, frame)
                t_an = time.monotonic() - t_an
            except bossname.OcrUnavailable as e:
                self.status["ocr"] = f"unavailable: {e}"
                continue
            self.last_reading = reading
            events = self.tracker.update(reading)
            if any(k == "death" for k, _ in events):
                # How long this frame took, to see where any delay comes from.
                log.info("death frame: grab %.0f ms, analyse %.0f ms, checking %.0f times a second",
                         t_grab * 1000, t_an * 1000, 1.0 / period)
            await self.apply(events)
            frames += 1
            if time.monotonic() - fps_t >= 10:
                self.status["fps"] = round(frames / (time.monotonic() - fps_t), 2)
                frames, fps_t = 0, time.monotonic()
            await asyncio.sleep(max(0.0, period - (time.monotonic() - start)))
