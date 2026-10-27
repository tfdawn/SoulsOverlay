"""The shipped Elden Ring profile against real screenshots (2560x1440 originals,
stored at 1080p) and rescaled to the resolutions OBS might hand us."""

import shutil
from pathlib import Path

import cv2
import pytest

from soulsoverlay.detect.analyzer import Analyzer
from soulsoverlay.detect.healthbar import read_bar
from soulsoverlay.profiles import load_profile

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")


@pytest.fixture(scope="module")
def er_real():
    return load_profile(ROOT / "profiles", "elden_ring")


def frame(name, width):
    img = cv2.imread(str(FIX / f"{name}_1080p.jpg"))
    return cv2.resize(img, (width, width * 9 // 16), interpolation=cv2.INTER_AREA)


def damage(profile, img, pct, trail):
    """Paint a damaged bar onto a real full-health frame."""
    img = img.copy()
    H, W = img.shape[:2]
    x, y, w, h = profile.boss_slots[0]["bar"]
    x0, y0, ww, hh = int(x * W), int(y * H), int(w * W), int(round(h * H)) + 2
    f = x0 + int(ww * pct / 100)
    t = f + int(ww * trail / 100)
    img[y0 - 1:y0 + hh, f:x0 + ww] = (22, 20, 24)
    img[y0 - 1:y0 + hh, f:t] = (24, 118, 143)  # measured from a real trail
    return img


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_death_template(er_real, width):
    a = Analyzer(er_real)
    assert a.death.mode == "template"
    hit, score = a.death.detect(frame("er_morgott_died", width))
    assert hit and score > 0.9
    hit, score = a.death.detect(frame("er_morgott_full", width))
    assert not hit and score < 0.2


@pytest.mark.parametrize("width", [2560, 1920, 1280])
@pytest.mark.parametrize("pct,trail", [(100, 0), (73, 0), (41, 9), (12, 20), (2, 5)])
def test_bar_on_real_frame(er_real, width, pct, trail):
    img = frame("er_morgott_full", width)
    if pct < 100:
        img = damage(er_real, img, pct, trail)
    r = read_bar(img, er_real.boss_slots[0]["bar"], er_real.data["bar_colors"])
    assert r.pct == pytest.approx(pct, abs=1.0)


@needs_tesseract
@pytest.mark.parametrize("name", ["er_morgott_full", "er_morgott_died"])
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_boss_name_on_real_frame(er_real, name, width):
    slot = Analyzer(er_real).analyze(frame(name, width), force_ocr=True).slots[0]
    assert slot.match is not None, slot.text
    assert slot.match.boss == "Morgott, the Omen King"


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_real_yellow_trail(er_real, width):
    """Morgott just after a hit: about 97.7% red with a 2% yellow trail after it."""
    r = read_bar(frame("er_morgott_trail", width), er_real.boss_slots[0]["bar"], er_real.data["bar_colors"])
    assert r.pct == pytest.approx(97.7, abs=0.6)
    assert r.trail_pct == pytest.approx(2.2, abs=0.8)


@needs_tesseract
def test_trail_frame_is_not_a_death_and_reads_name(er_real):
    reading = Analyzer(er_real).analyze(frame("er_morgott_trail", 1920), force_ocr=True)
    assert not reading.death
    assert reading.slots[0].match.boss == "Morgott, the Omen King"


@needs_tesseract
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_low_health_real_frame(er_real, width):
    """Tree Sentinel at about 20%, with the see-through empty part of the bar over grass."""
    reading = Analyzer(er_real).analyze(frame("er_sentinel_low", width), force_ocr=True)
    slot = reading.slots[0]
    assert slot.pct == pytest.approx(19.6, abs=0.8)
    assert slot.trail_pct < 1.0
    assert slot.match and slot.match.boss == "Tree Sentinel"
    assert not reading.death


@needs_tesseract
def test_name_fading_in_is_retried_on_the_next_frame(er_real):
    img = frame("er_morgott_full", 1920)
    blank = img.copy()
    x, y, w, h = er_real.boss_slots[0]["name"]
    blank[int(y * 1080):int((y + h) * 1080) + 1, int(x * 1920):int((x + w) * 1920)] = (20, 18, 16)
    a = Analyzer(er_real)
    assert a.analyze(blank, now=0.0).slots[0].match is None  # bar up, name not legible yet
    assert a.analyze(img, now=0.25).slots[0].match.boss == "Morgott, the Omen King"


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_death_counts_while_the_bar_is_still_up(er_real, width):
    # From a 60 fps recording: YOU DIED 0.17s into its fade-in, about 0.65s
    # before the game drops the boss bar.
    a = Analyzer(er_real)
    img = frame("er_sentinel_died_fadein", width)
    hit, _ = a.death.detect(img)
    assert hit
    assert read_bar(img, er_real.boss_slots[0]["bar"], er_real.data["bar_colors"]).pct is not None
    hit, score = a.death.detect(frame("er_sentinel_fight", width))
    assert not hit and score < 0.25


# -- Dark Souls Remastered: Asylum Demon at HUD scale 0.80 (2560x1440 shots
# and a 60 fps 1080p death clip, stored at 1080p) ----------------------------

@pytest.fixture(scope="module")
def dsr():
    return load_profile(ROOT / "profiles", "dark_souls_remastered")


@pytest.mark.parametrize("width", [2560, 1920, 1280])
@pytest.mark.parametrize("name,pct,trail", [
    ("dsr_asylum_full", 100, 0), ("dsr_asylum_trail", 64.6, 35.0), ("dsr_asylum_lost", 41.2, 0),
    ("dsr_asylum_fight", 36.4, 0)])
def test_dsr_bar(dsr, width, name, pct, trail):
    r = read_bar(frame(name, width), dsr.boss_slots[0]["bar"], dsr.data["bar_colors"])
    assert r.pct == pytest.approx(pct, abs=1.0)
    assert r.trail_pct == pytest.approx(trail, abs=1.5)


@needs_tesseract
@pytest.mark.parametrize("name", ["dsr_asylum_full", "dsr_asylum_trail", "dsr_asylum_lost"])
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_dsr_boss_name(dsr, name, width):
    slot = Analyzer(dsr).analyze(frame(name, width), force_ocr=True).slots[0]
    assert slot.match is not None and slot.match.boss == "Asylum Demon", slot.text


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_dsr_death(dsr, width):
    a = Analyzer(dsr)
    assert a.death.mode == "template"
    hit, score = a.death.detect(frame("dsr_asylum_died", width))
    assert hit and score > 0.9
    # 0.6s into the fade-in, the first frame over the threshold
    hit, score = a.death.detect(frame("dsr_asylum_died_fadein", width))
    assert hit
    for name in ("dsr_asylum_fight", "dsr_asylum_full", "dsr_asylum_trail"):
        hit, score = a.death.detect(frame(name, width))
        assert not hit and score < 0.2, name


def test_ocr_dropping_the_space_still_matches(dsr):
    assert dsr.match_boss("AsylumDemon : ok Ne _").boss == "Asylum Demon"


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_dsr_death_follows_the_hud_scale(dsr, width):
    """YOU DIED at HUD scale 1.00 is 1.25x the 0.80 one, about the screen centre."""
    img = cv2.imread(str(FIX / "dsr_died_hud100_1080p.jpg"))
    img = cv2.resize(img, (width, width * 9 // 16), interpolation=cv2.INTER_AREA)
    assert not Analyzer(dsr).death.detect(img)[0]
    k = 1.0 / dsr.data["hud_scale"]["value"]
    ax, ay = dsr.data["hud_scale"]["death_anchor"]
    x, y, w, h = dsr.regions["death"]
    moved = load_profile(ROOT / "profiles", "dark_souls_remastered")
    moved.update({"regions": {"death": [ax + (x - ax) * k, ay + (y - ay) * k, w * k, h * k]}})
    hit, score = Analyzer(moved).death.detect(img)
    assert hit and score > 0.6
