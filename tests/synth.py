"""Synthetic souls-style frames for tests: noisy background, boss bar, name, death banner."""

from __future__ import annotations

import cv2
import numpy as np

RED = (27, 25, 160)  # BGR, close to the souls boss-bar red
TRAIL = (60, 170, 205)  # yellow/orange delayed-damage trail
DEATH_RED = (30, 30, 150)


def _px(region, w, h):
    x, y, rw, rh = region
    return int(round(x * w)), int(round(y * h)), int(round(rw * w)), int(round(rh * h))


def make_frame(profile=None, *, w=1280, h=720, bosses=(), death=False, seed=0):
    """bosses: list of (name or None, pct or None, trail_pct) per slot."""
    rng = np.random.default_rng(seed)
    frame = rng.integers(20, 110, size=(h, w, 3), dtype=np.uint8)
    frame = cv2.GaussianBlur(frame, (9, 9), 0)
    # some greenish/blueish scenery blobs
    for _ in range(6):
        c = tuple(int(v) for v in rng.integers(40, 160, 3))
        cv2.circle(frame, (int(rng.integers(0, w)), int(rng.integers(0, h // 2))), int(rng.integers(30, 120)), c, -1)

    if profile is not None:
        for slot, spec in zip(profile.boss_slots, bosses):
            name, pct, trail = (list(spec) + [0])[:3]
            if pct is not None and slot.get("bar"):
                x, y, bw, bh = _px(slot["bar"], w, h)
                cv2.rectangle(frame, (x - 3, y - 3), (x + bw + 3, y + bh + 3), (70, 90, 110), 1)
                frame[y:y + bh, x:x + bw] = (18, 16, 16)
                fill = int(round(bw * pct / 100))
                frame[y:y + bh, x:x + fill] = RED
                # texture on the fill
                frame[y:y + bh, x:x + fill] = np.clip(
                    frame[y:y + bh, x:x + fill].astype(int) + rng.integers(-12, 12, (bh, fill, 1)), 0, 255)
                t = int(round(bw * trail / 100))
                frame[y:y + bh, x + fill:x + fill + t] = TRAIL
            if name and slot.get("name"):
                x, y, nw, nh = _px(slot["name"], w, h)
                scale = nh / 34
                cv2.putText(frame, name, (x + 4, y + int(nh * 0.75)), cv2.FONT_HERSHEY_DUPLEX,
                            scale, (225, 235, 240), 1, cv2.LINE_AA)

    if death:
        band = frame[int(h * 0.40):int(h * 0.60)]
        frame[int(h * 0.40):int(h * 0.60)] = (band * 0.25).astype(np.uint8)
        text = "YOU DIED"
        scale = h / 220
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_TRIPLEX, scale, 3)
        cv2.putText(frame, text, ((w - tw) // 2, int(h * 0.5 + th / 2)), cv2.FONT_HERSHEY_TRIPLEX,
                    scale, DEATH_RED, 3, cv2.LINE_AA)
    return frame
