"""Find the boss bar on a frame and fit the profile's boxes to it.

Games like Dark Souls Remastered let players change the HUD scale, which
moves and resizes the boss bar and name. The HUD scales as one piece, so
once we know where the bar really is, every other box (the name, a second
boss slot) follows from the profile's layout: same offsets from the bar's
left end, multiplied by how much bigger or smaller the bar is.

The bar is found as a long, straight, horizontal strip of fill (or trail)
colour in the lower half of the frame. It has to be at full health or close
to it, because the empty part of a bar is see-through and can't be measured.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import hsv_mask

# Used when the profile has no boss slot to copy the layout from: the name
# sits just above the left end of the bar (measured on Elden Ring).
DEFAULT_NAME = (-0.0075, -0.06, 0.64, 0.05)  # x, y, w, h as multiples of bar width

# Broad red, for profiles whose own fill colour doesn't find anything.
FALLBACK_FILL = {"h": [[0, 12], [165, 180]], "s": [110, 255], "v": [20, 255]}


class ShortBar(ValueError):
    """A bar was found but it's too short to measure: the boss has lost health."""


@dataclass
class Bar:
    x: int
    y: int
    w: int
    h: int


@dataclass
class AutoFind:
    boss_slots: list[dict]
    scale: float  # found bar width / the profile's bar width
    bars: list[Bar]
    bar_colors: dict | None = None  # only set when the profile's colours didn't work


def _row_runs(mask: np.ndarray, min_len: int, gap: int):
    """Longest run of True per row, after closing gaps up to `gap` pixels."""
    if gap > 1:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (gap, 1))
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool)
    out = []
    for y, row in enumerate(mask):
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        if starts.size == 0:
            out.append(None)
            continue
        i = int(np.argmax(ends - starts))
        out.append((int(starts[i]), int(ends[i])) if ends[i] - starts[i] >= min_len else None)
    return out


def find_bars(frame: np.ndarray, colors: dict, top: float = 0.5) -> list[Bar]:
    """Boss-bar-like strips in the lower part of the frame, best one first.

    A strip is a group of consecutive rows whose longest run of fill colour
    starts and ends in the same place on every row: scenery that happens to
    be red (fire, blood, gold leaves) is never that straight for that long.
    A delayed-damage trail to the right of the fill is added on afterwards.
    """
    H, W = frame.shape[:2]
    y0 = int(H * top)
    region = frame[y0:]
    fill = hsv_mask(region, colors["fill"])
    trail = hsv_mask(region, colors["trail"]) if "trail" in colors else np.zeros_like(fill)
    runs = _row_runs(fill, min_len=int(W * 0.12), gap=max(3, W // 200))
    tol = max(2, W * 0.004)

    groups, cur = [], []
    for y, run in enumerate(runs):
        if run and cur and abs(run[0] - cur[-1][1][0]) <= tol:
            cur.append((y, run))
            continue
        if len(cur) >= 2:
            groups.append(cur)
        cur = [(y, run)] if run else []
    if len(cur) >= 2:
        groups.append(cur)

    bars = []
    for g in groups:
        if len(g) > H * 0.03:  # far too thick: a red wall, not a bar
            continue
        x0 = int(np.median([r[0] for _, r in g]))
        x1 = int(np.median([r[1] for _, r in g]))
        # Keep the rows where the strip runs the full length: the soft top
        # and bottom edges of the bar texture are left out, like a hand-drawn box.
        rows = [y for y, (s, e) in g if abs(s - x0) <= tol and abs(e - x1) <= tol]
        if len(rows) < 2:
            continue
        top_y, bot_y = min(rows), max(rows)
        if bot_y - top_y >= 4:
            top_y, bot_y = top_y + 1, bot_y - 1
        band = slice(top_y, bot_y + 1)
        if fill[band, x0:x1].mean() < 0.85:
            continue
        # Carry on to the right through any trail.
        # The bar's segment notches leave gaps of a pixel or two.
        cols = (fill[band] | trail[band]).mean(axis=0) >= 0.6
        gap = max(3, W // 150)
        while x1 < W and cols[x1:x1 + gap].any():
            x1 += int(np.flatnonzero(cols[x1:x1 + gap])[-1]) + 1
        bars.append(Bar(x0, y0 + top_y, x1 - x0, bot_y - top_y + 1))
    if not bars:
        return []
    # The widest strip is the boss bar. Other strips of about the same size
    # lined up with it are the bars of a duo fight; anything else is scenery.
    best = max(bars, key=lambda b: b.w)
    same = [b for b in bars if b.w >= 0.8 * best.w and abs(b.x - best.x) <= W * 0.02]
    same.sort(key=lambda b: -b.y)
    return same


def _fit_colors(frame: np.ndarray, bar: Bar) -> dict:
    """A fill colour spec measured from the bar itself."""
    px = cv2.cvtColor(frame[bar.y:bar.y + bar.h, bar.x:bar.x + bar.w], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = (px[:, i].astype(int) for i in range(3))
    red = (h <= 20) | (h >= 160)
    if red.mean() > 0.5:  # red wraps around 0/180
        hh = np.where(h >= 160, h - 180, h)
        lo, hi = np.percentile(hh[red], [2, 98]).astype(int)
        hue = [[max(0, lo - 3), max(0, hi + 3)]]
        if lo - 3 < 0:
            hue.append([180 + lo - 3, 180])
    else:
        lo, hi = np.percentile(h, [2, 98]).astype(int)
        hue = [[max(0, lo - 3), min(180, hi + 3)]]
    s_lo = max(60, int(np.percentile(s, 5)) - 30)
    v_lo = max(12, int(np.percentile(v, 5) * 0.6))
    return {"h": hue, "s": [s_lo, 255], "v": [v_lo, 255]}


def auto_find(frame: np.ndarray, profile_data: dict) -> AutoFind | None:
    """Boss slots fitted to the bar on this frame, or None if there's no bar.

    Raises ShortBar when the boss has lost too much health to measure the bar.
    """
    H, W = frame.shape[:2]
    colors = profile_data.get("bar_colors") or {}
    fitted = None
    bars = find_bars(frame, colors) if "fill" in colors else []
    if not bars:
        fallback = {"fill": FALLBACK_FILL}
        bars = find_bars(frame, fallback)
        if not bars:
            return None
        fitted = dict(colors, fill=_fit_colors(frame, bars[0]))
    bar = bars[0]

    def px(r):
        return (r[0] * W, r[1] * H, r[2] * W, r[3] * H)

    def frac(x, y, w, h):
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(W), x + w), min(float(H), y + h)
        return [round(x0 / W, 4), round(y0 / H, 4), round((x1 - x0) / W, 4), round((y1 - y0) / H, 4)]

    ref_slots = [s for s in profile_data.get("boss_slots") or [] if s.get("bar")]
    if ref_slots:
        rx, ry, rw, rh = px(ref_slots[0]["bar"])
        scale = bar.w / rw
        thick = bar.h / rh if rh else scale
        if scale < 0.7 * thick:
            raise ShortBar("The boss bar isn't full. Grab a frame where the boss is at full health, "
                           "or just after its first hit.")

        def move(r):
            x, y, w, h = px(r)
            return frac(bar.x + (x - rx) * scale, bar.y + (y - ry) * scale, w * scale, h * scale)

        slots = []
        for i, s in enumerate(ref_slots):
            new = {k: move(s[k]) for k in ("name", "bar") if s.get(k)}
            if i < len(bars):
                # A bar we can see beats one placed from the layout; its name
                # keeps the same offset from it.
                b = bars[i]
                bx, by, _, _ = px(s["bar"])
                if "name" in s:
                    nx, ny, nw, nh = px(s["name"])
                    new["name"] = frac(b.x + (nx - bx) * scale, b.y + (ny - by) * scale, nw * scale, nh * scale)
                new["bar"] = frac(b.x, b.y, b.w, b.h)
            slots.append(new)
    else:
        scale = 1.0
        nx, ny, nw, nh = DEFAULT_NAME
        slots = [{"name": frac(b.x + nx * b.w, b.y + ny * b.w, nw * b.w, nh * b.w),
                  "bar": frac(b.x, b.y, b.w, b.h)} for b in bars]
    return AutoFind(slots, round(scale, 3), bars, fitted)
