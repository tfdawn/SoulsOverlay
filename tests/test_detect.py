import shutil

import cv2
import pytest

from soulsoverlay.detect.analyzer import Analyzer
from soulsoverlay.detect.healthbar import read_bar
from soulsoverlay.detect.screen import ScreenDetector, save_template
from synth import make_frame

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")


@pytest.mark.parametrize("pct,trail", [(100, 0), (73.5, 0), (41, 12), (8.2, 30), (1.5, 5)])
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (854, 480)])
def test_health_bar_ignores_trail(er, pct, trail, size):
    frame = make_frame(er, w=size[0], h=size[1], bosses=[("x", pct, trail)])
    r = read_bar(frame, er.boss_slots[0]["bar"], er.data["bar_colors"])
    tolerance = 100 / (er.boss_slots[0]["bar"][2] * size[0]) + 0.6  # one column + rounding
    assert r.pct == pytest.approx(pct, abs=tolerance)
    if trail:
        assert r.trail_pct == pytest.approx(trail, abs=2)


def test_no_bar_means_none(er):
    frame = make_frame(er)
    assert read_bar(frame, er.boss_slots[0]["bar"], er.data["bar_colors"]).pct is None


def test_only_trail_left_is_zero(er):
    frame = make_frame(er, bosses=[("x", 0, 6)])
    assert read_bar(frame, er.boss_slots[0]["bar"], er.data["bar_colors"]).pct == 0.0


def test_death_heuristic(er):
    det = ScreenDetector(er.regions["death"], er.data["death"], None)
    assert det.mode == "heuristic"
    for seed in range(5):
        assert det.detect(make_frame(er, death=True, seed=seed))[0]
        assert not det.detect(make_frame(er, seed=seed))[0]
        assert not det.detect(make_frame(er, bosses=[("Margit", 80)], seed=seed))[0]


def test_death_template_across_resolutions(er, tmp_path):
    tpl = save_template(make_frame(er, death=True, w=1920, h=1080), er.regions["death"], tmp_path / "t.png")
    det = ScreenDetector(er.regions["death"], er.data["death"], tpl)
    assert det.mode == "template"
    for w, h in [(1280, 720), (1920, 1080), (2560, 1440)]:
        hit, score = det.detect(make_frame(er, death=True, w=w, h=h, seed=3))
        assert hit, (w, h, score)
        miss, score = det.detect(make_frame(er, w=w, h=h, seed=3))
        assert not miss, (w, h, score)


@needs_tesseract
@pytest.mark.parametrize("name,expected,phase", [
    ("Margit, the Fell Omen", "Margit, the Fell Omen", None),
    ("Malenia, Goddess of Rot", "Malenia, Blade of Miquella", 2),
    ("Elden Beast", "Radagon of the Golden Order", 2),
    ("Godrick the Grafted", "Godrick the Grafted", None),
])
def test_boss_name_ocr_and_matching(er, name, expected, phase):
    frame = make_frame(er, bosses=[(name, 50)])
    slot = Analyzer(er).analyze(frame, force_ocr=True).slots[0]
    assert slot.match is not None, slot.text
    assert slot.match.boss == expected
    assert slot.match.phase_hint == phase


def test_fuzzy_match_tolerates_ocr_noise(er):
    assert er.match_boss("Margit, the Fel 0men").boss == "Margit, the Fell Omen"
    assert er.match_boss("Malenia Goddess of Rat").phase_hint == 2
    assert er.match_boss("the") is None
    assert er.match_boss("Patches") is None


def test_regions_scale_with_resolution(er):
    small = make_frame(er, w=1280, h=720, bosses=[("Margit", 55)])
    big = cv2.resize(small, (2560, 1440), interpolation=cv2.INTER_NEAREST)
    a = read_bar(small, er.boss_slots[0]["bar"], er.data["bar_colors"]).pct
    b = read_bar(big, er.boss_slots[0]["bar"], er.data["bar_colors"]).pct
    assert a == pytest.approx(b, abs=0.5)
