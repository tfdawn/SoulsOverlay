"""Auto-find: locating the boss bar and fitting the profile's boxes to it,
on real screenshots and on copies scaled the way a game's HUD-scale setting does."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from soulsoverlay.detect.autofind import ShortBar, auto_find
from soulsoverlay.detect.healthbar import read_bar
from soulsoverlay.profiles import load_profile

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"


def frame(name):
    return cv2.imread(str(FIX / f"{name}_1080p.jpg"))


def hud_scale(img, s):
    """The whole frame shrunk or grown about its bottom centre, which is what
    a HUD-scale setting does to the boss bar and name."""
    H, W = img.shape[:2]
    m = np.float32([[s, 0, W / 2 * (1 - s)], [0, s, H * (1 - s)]])
    return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_AREA, borderValue=(15, 15, 15))


def scaled(region, s):
    x, y, w, h = region
    return [0.5 + (x - 0.5) * s, 1 + (y - 1) * s, w * s, h * s]


@pytest.mark.parametrize("game,shot,pct", [
    ("dark_souls_remastered", "dsr_asylum_full", 100),
    ("dark_souls_remastered", "dsr_asylum_trail", 64.6),
    ("elden_ring", "er_morgott_full", 100),
    ("elden_ring", "er_sentinel_fight", 100),
])
@pytest.mark.parametrize("s", [0.8, 1.0, 1.15])
def test_fits_boxes_at_any_hud_scale(game, shot, pct, s):
    profile = load_profile(ROOT / "profiles", game)
    img = frame(shot) if s == 1 else hud_scale(frame(shot), s)
    found = auto_find(img, profile.data)
    assert found.scale == pytest.approx(s, abs=0.015)
    slot = found.boss_slots[0]
    want = scaled(profile.boss_slots[0]["bar"], s)
    assert slot["bar"][0] == pytest.approx(want[0], abs=0.003)
    assert slot["bar"][1] == pytest.approx(want[1], abs=0.003)
    assert slot["bar"][2] == pytest.approx(want[2], abs=0.004)
    want_name = scaled(profile.boss_slots[0]["name"], s)
    assert slot["name"] == pytest.approx(want_name, abs=0.004)
    assert read_bar(img, slot["bar"], profile.data["bar_colors"]).pct == pytest.approx(pct, abs=1.0)


def test_second_slot_follows_the_layout():
    profile = load_profile(ROOT / "profiles", "dark_souls_remastered")
    found = auto_find(hud_scale(frame("dsr_asylum_full"), 0.8), profile.data)
    assert len(found.boss_slots) == len(profile.boss_slots)
    assert found.boss_slots[1]["bar"] == pytest.approx(scaled(profile.boss_slots[1]["bar"], 0.8), abs=0.004)


def test_boss_that_lost_health_is_refused():
    profile = load_profile(ROOT / "profiles", "dark_souls_remastered")
    with pytest.raises(ShortBar):
        auto_find(frame("dsr_asylum_lost"), profile.data)


def test_no_bar_on_screen():
    profile = load_profile(ROOT / "profiles", "elden_ring")
    assert auto_find(np.zeros((720, 1280, 3), np.uint8), profile.data) is None


def test_generic_profile_measures_the_colour_and_places_a_name():
    """No boxes and no colours to go on: the bar is found as broad red, and its
    fill colour is measured from it so the dark DSR red still reads."""
    profile = load_profile(ROOT / "profiles", "generic")
    data = {k: v for k, v in profile.data.items() if k != "bar_colors"}
    found = auto_find(frame("dsr_asylum_full"), data)
    assert found.bar_colors is not None
    slot = found.boss_slots[0]
    assert slot["bar"][0] == pytest.approx(0.348, abs=0.003)
    assert slot["name"][1] < slot["bar"][1]
    reading = read_bar(frame("dsr_asylum_lost"), slot["bar"], {**found.bar_colors,
                                                                "trail": {"h": [[18, 35]], "s": [140, 255], "v": [30, 255]}})
    assert reading.pct == pytest.approx(41.2, abs=1.0)
