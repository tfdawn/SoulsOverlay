"""Full-screen banners: "YOU DIED", and optionally a victory banner.

Two ways to score a frame:

* Template: the region is resized to the size of a template captured with the
  calibration page and compared with normalised cross-correlation. Because the
  template is cut from the same fractional region, scale is already right and
  a plain correlation is enough (and cheap at a few frames per second).
* Heuristic: before a template exists, count saturated red pixels in the
  region against a darkened background, which is what every souls death
  screen looks like.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from . import crop, hsv_mask


def _prep(img: np.ndarray) -> np.ndarray:
    # Correlate on the red channel minus the others: keeps the red lettering,
    # drops whatever the background is doing behind the dimmed band.
    b, g, r = cv2.split(img.astype(np.int16))
    redness = np.clip(r - (g + b) // 2, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(redness, (3, 3), 0)


class ScreenDetector:
    def __init__(self, region, spec: dict, template_path: Path | None):
        self.region = region
        self.spec = spec
        self.template = None
        if template_path is not None and Path(template_path).exists():
            img = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
            if img is not None:
                self.template = _prep(img)

    @property
    def mode(self) -> str:
        return "template" if self.template is not None else "heuristic"

    def score(self, frame: np.ndarray) -> float:
        """0..1, higher means more confident the banner is on screen."""
        roi = crop(frame, self.region)
        if roi is None:
            return 0.0
        if self.template is not None:
            th, tw = self.template.shape[:2]
            probe = _prep(cv2.resize(roi, (tw, th), interpolation=cv2.INTER_AREA))
            if probe.std() < 1e-3 or self.template.std() < 1e-3:
                return 0.0
            res = cv2.matchTemplate(probe, self.template, cv2.TM_CCOEFF_NORMED)
            return float(max(0.0, res.max()))
        h = self.spec["heuristic"]
        frac = float(hsv_mask(roi, h).mean())
        mean_v = float(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[..., 2].mean())
        if frac < h["min_fraction"] or frac > h["max_fraction"] or mean_v > h["max_mean_v"]:
            return 0.0
        # Map the plausible band onto 0.6..1 so the same threshold works.
        return min(1.0, 0.6 + frac * 4)

    def threshold(self) -> float:
        return self.spec["threshold"] if self.template is not None else 0.6

    def detect(self, frame: np.ndarray) -> tuple[bool, float]:
        s = self.score(frame)
        return s >= self.threshold(), s


def save_template(frame: np.ndarray, region, path: Path) -> Path:
    roi = crop(frame, region)
    if roi is None:
        raise ValueError("region is empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), roi)
    return path
