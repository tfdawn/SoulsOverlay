"""Boss health from the fill of the boss bar.

The bar fills left to right. After a hit, souls games leave a yellow/orange
"delayed damage" trail to the right of the red fill that drains a moment
later; we only count red. Health is the position of the rightmost red column,
after a small median filter so a stray dark pixel or the bar's texture can't
cut the reading short.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import crop, hsv_mask


@dataclass
class BarReading:
    pct: float | None  # 0..100, None when no bar is visible
    trail_pct: float  # how much of the bar is delayed-damage trail
    fill_columns: float  # share of columns that are red (diagnostics)


def _median_filter_1d(mask: np.ndarray, width: int) -> np.ndarray:
    if width <= 1 or mask.size < width:
        return mask
    pad = width // 2
    padded = np.pad(mask.astype(np.uint8), pad, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, width)
    return windows.sum(axis=1) > (width // 2)


def _rest_is_empty(bar: np.ndarray, rest: np.ndarray, colors: dict, threshold: float) -> bool:
    """The part of a real bar past the fill and trail is the empty bar's
    colour. Brown or gold scenery (sunlit floors, torches) behind an unused
    slot can pass for a sliver of fill or trail, but not with an empty bar
    beside it. Half the rest is enough, so a boss or player standing in front
    of the bar doesn't hide it. Profiles without an "empty" colour skip this."""
    spec = colors.get("empty")
    if spec is None or rest.sum() < max(3, rest.size // 20):
        return True
    empty = hsv_mask(bar, spec).mean(axis=0) >= threshold
    return float(empty[rest].mean()) >= 0.5


def read_bar(frame: np.ndarray, region, colors: dict) -> BarReading:
    bar = crop(frame, region)
    if bar is None:
        return BarReading(None, 0.0, 0.0)
    threshold = colors.get("column_threshold", 0.35)
    fill = hsv_mask(bar, colors["fill"]).mean(axis=0) >= threshold
    trail = hsv_mask(bar, colors["trail"]).mean(axis=0) >= threshold
    width = fill.size
    filt = max(3, (width // 100) | 1)
    fill = _median_filter_1d(fill, filt)
    trail = _median_filter_1d(trail, filt) & ~fill

    red_cols = np.flatnonzero(fill)
    trail_share = float(trail.mean()) * 100
    # A real bar always starts at the left edge of its box. Scenery that
    # happens to be red or gold (fire, blood, autumn leaves) rarely does,
    # and without this check it reads as a phantom bar.
    anchor = max(2, width // 40)
    if red_cols.size == 0:
        # A bar with only trail left is a boss at ~0% (the killing blow);
        # otherwise there is no bar on screen.
        if trail_share > 2.0 and trail[:anchor].any() and _rest_is_empty(bar, ~trail, colors, threshold):
            return BarReading(0.0, trail_share, 0.0)
        return BarReading(None, 0.0, 0.0)
    if red_cols[0] >= anchor:
        return BarReading(None, 0.0, float(fill.mean()))

    # Ignore isolated red specks far to the right of the main fill (sparks,
    # blood, red UI from other elements bleeding into the box): keep the
    # rightmost red column such that most columns to its left are red/trail.
    covered = np.cumsum(fill | trail)
    good = covered[red_cols] >= 0.8 * (red_cols + 1)
    if not good.any():
        return BarReading(None, trail_share, float(fill.mean()))
    last = int(red_cols[good][-1])
    rest = ~(fill | trail)
    rest[: last + 1] = False
    if not _rest_is_empty(bar, rest, colors, threshold):
        return BarReading(None, trail_share, float(fill.mean()))
    pct = 100.0 * (last + 1) / width
    return BarReading(round(min(pct, 100.0), 1), round(trail_share, 1), float(fill.mean()))
