"""Frame analysis. Every detector works on a BGR numpy frame plus a profile."""

from __future__ import annotations

import cv2
import numpy as np


def crop(frame: np.ndarray, region) -> np.ndarray | None:
    """Crop a fractional [x, y, w, h] region out of a frame."""
    if not region:
        return None
    h, w = frame.shape[:2]
    x0 = int(round(region[0] * w))
    y0 = int(round(region[1] * h))
    x1 = int(round((region[0] + region[2]) * w))
    y1 = int(round((region[1] + region[3]) * h))
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return frame[y0:y1, x0:x1]


def hsv_mask(bgr: np.ndarray, spec: dict) -> np.ndarray:
    """Boolean mask of pixels inside an HSV colour spec.

    spec = {"h": [[lo, hi], ...], "s": [lo, hi], "v": [lo, hi]}
    Several hue ranges are OR-ed, which handles red wrapping around 0/180.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hue_ok = np.zeros(hue.shape, dtype=bool)
    for lo, hi in spec["h"]:
        hue_ok |= (hue >= lo) & (hue <= hi)
    s_lo, s_hi = spec["s"]
    v_lo, v_hi = spec["v"]
    return hue_ok & (sat >= s_lo) & (sat <= s_hi) & (val >= v_lo) & (val <= v_hi)
