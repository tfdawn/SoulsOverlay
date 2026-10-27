"""Frame sources.

ObsCapture asks OBS for a screenshot of the game source through
obs-websocket (built into OBS 28+). It only reads what OBS already renders:
no hooks into the game, no memory reads, no input, so anti-cheat has nothing
to see.

FolderCapture replays a folder of images, for testing profiles offline.
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


def decode_data_uri(data: str) -> np.ndarray:
    if "," in data:
        data = data.split(",", 1)[1]
    buf = np.frombuffer(base64.b64decode(data), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode screenshot")
    return img


class ObsCapture:
    # How often to re-check the source's native size (resolution changes,
    # switching between windowed and fullscreen).
    PROBE_INTERVAL_S = 60.0

    def __init__(self, host: str, port: int, password: str, source: str, width: int = 1280):
        self.host, self.port, self.password = host, port, password
        self.source = source
        self.width = width
        self._client = None
        self._size: tuple[int, int] | None = None  # source's native (w, h)
        self._probed_at = 0.0
        self._warned_missing = False

    def _connect(self):
        import obsws_python as obs

        self._client = obs.ReqClient(host=self.host, port=self.port,
                                     password=self.password, timeout=5)
        log.info("connected to OBS at %s:%s", self.host, self.port)

    def _screenshot(self, width: int, height: int) -> np.ndarray:
        resp = self._req("GetSourceScreenshot", {
            "sourceName": self.source, "imageFormat": "jpg", "imageCompressionQuality": 92,
            "imageWidth": width, "imageHeight": height})
        return decode_data_uri(resp["imageData"])

    def _req(self, request: str, data: dict | None = None) -> dict:
        return self._client.send(request, data, raw=True) or {}

    def _source_size(self) -> tuple[int, int] | None:
        """The game source's native size, from its scene item in OBS.

        OBS stretches a screenshot to exactly the width and height asked for,
        so we need the source's own aspect ratio. (Asking for a screenshot with
        no size fails with "Failed to render screenshot" on some setups.)
        """
        scenes = [s["sceneName"] for s in self._req("GetSceneList").get("scenes", [])]
        for scene in scenes:
            items = self._req("GetSceneItemList", {"sceneName": scene}).get("sceneItems", [])
            for item in items:
                if item.get("sourceName") != self.source:
                    continue
                t = self._req("GetSceneItemTransform", {
                    "sceneName": scene, "sceneItemId": item["sceneItemId"]}).get("sceneItemTransform", {})
                w, h = int(t.get("sourceWidth") or 0), int(t.get("sourceHeight") or 0)
                if w >= 8 and h >= 8:
                    return w, h
        # Not in any scene, nested in a group, or the game isn't hooked yet
        # (size 0): fall back to the canvas, which a fullscreen game fills.
        if not self._warned_missing:
            self._warned_missing = True
            names = [i.get("inputName") for i in self._req("GetInputList").get("inputs", [])]
            if self.source not in names:
                log.warning("OBS has no source called '%s'. Set obs.source in config.toml to one of: %s",
                            self.source, ", ".join(f"'{n}'" for n in names) or "(none)")
            else:
                log.warning("source '%s' isn't in any scene, or isn't showing the game yet;"
                            " frames may come back black", self.source)
        v = self._req("GetVideoSettings")
        w, h = int(v.get("baseWidth") or 0), int(v.get("baseHeight") or 0)
        return (w, h) if w and h else None

    def _probe(self):
        size = self._source_size()
        if size is None:
            raise RuntimeError(f"could not find the size of OBS source '{self.source}'")
        if size != self._size:
            log.info("game source is %dx%d", *size)
        self._size = size
        self._probed_at = time.monotonic()

    def grab(self) -> np.ndarray:
        if self._client is None:
            self._connect()
        try:
            if self._size is None or time.monotonic() - self._probed_at >= self.PROBE_INTERVAL_S:
                self._probe()
            w, h = self._size
            if w <= self.width:
                return self._screenshot(w, h)
            # JPEG is several times faster to encode than PNG on the OBS side,
            # and the detectors are tested against JPEG at this quality.
            return self._screenshot(self.width, max(8, round(self.width * h / w)))
        except Exception:
            self.close()
            raise

    def close(self):
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._size = None


class FolderCapture:
    """Cycles through images in a folder (sorted by name)."""

    def __init__(self, folder: Path, loop: bool = True):
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        self.files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in exts)
        if not self.files:
            raise FileNotFoundError(f"no images in {folder}")
        self.i = 0
        self.loop = loop

    def grab(self) -> np.ndarray:
        if self.i >= len(self.files):
            if not self.loop:
                raise StopIteration
            self.i = 0
        img = cv2.imread(str(self.files[self.i]), cv2.IMREAD_COLOR)
        self.i += 1
        return img

    def close(self):
        pass


class Backoff:
    def __init__(self, start: float = 1.0, cap: float = 30.0):
        self.start, self.cap, self.delay, self.next_try = start, cap, start, 0.0

    def ready(self) -> bool:
        return time.monotonic() >= self.next_try

    def fail(self):
        self.next_try = time.monotonic() + self.delay
        self.delay = min(self.cap, self.delay * 2)

    def reset(self):
        """Try again now (new OBS details, or Start pressed)."""
        self.ok()
        self.next_try = 0.0

    def ok(self):
        self.delay = self.start
