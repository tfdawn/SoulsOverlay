"""The shipped Elden Ring profile against real screenshots (2560x1440 originals,
stored at 1080p) and rescaled to the resolutions OBS might hand us."""

import shutil
from pathlib import Path

import cv2
import numpy as np
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


@needs_tesseract
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_dsr_duo_at_hud_scale_one(dsr, width):
    """Ornstein and Smough at HUD scale 1.00: the boxes typed in for 1.00 and the
    ones Auto-find places both read the two bars and both names."""
    from soulsoverlay.detect.autofind import auto_find
    from soulsoverlay.profiles import Profile

    img = cv2.imread(str(FIX / "dsr_ons_hud100_1080p.jpg"))
    img = cv2.resize(img, (width, width * 9 // 16), interpolation=cv2.INTER_AREA)
    k = 1.0 / dsr.data["hud_scale"]["value"]
    ax, ay = dsr.data["hud_scale"]["anchor"]
    typed = [{key: [ax + (r[0] - ax) * k, ay + (r[1] - ay) * k, r[2] * k, r[3] * k] for key, r in s.items()}
             for s in dsr.boss_slots]
    found = auto_find(img, dsr.data).boss_slots
    for slots in (typed, found):
        reading = Analyzer(Profile({**dsr.raw, "boss_slots": slots})).analyze(img, force_ocr=True)
        assert [s.pct for s in reading.slots] == [pytest.approx(100, abs=1)] * 2
        assert [s.text for s in reading.slots] == ["Executioner Smough", "Dragon Slayer Ornstein"]
        assert all(s.match.boss == "Ornstein and Smough" for s in reading.slots)


# -- Dark Souls II: Scholar of the First Sin, Dragonrider (60 fps 1080p clips)
# and Ruin Sentinels (1080p screenshot). DSII has no HUD scale setting. -------

@pytest.fixture(scope="module")
def ds2():
    return load_profile(ROOT / "profiles", "dark_souls_2")


@pytest.mark.parametrize("width", [2560, 1920, 1280])
@pytest.mark.parametrize("name,pct,trail", [
    ("ds2_dragonrider_full", 100, 0), ("ds2_dragonrider_trail", 96.2, 3.7),
    ("ds2_dragonrider_low", 16.0, 0)])
def test_ds2_bar(ds2, width, name, pct, trail):
    r = read_bar(frame(name, width), ds2.boss_slots[0]["bar"], ds2.data["bar_colors"])
    assert r.pct == pytest.approx(pct, abs=1.0)
    assert r.trail_pct == pytest.approx(trail, abs=1.5)


@pytest.mark.parametrize("width", [2560, 1920, 1280])
@pytest.mark.parametrize("name", ["ds2_dragonrider_full", "ds2_dragonrider_trail",
                                  "ds2_dragonrider_low", "ds2_no_boss_floor"])
def test_ds2_sunlit_floor_is_not_a_bar(ds2, width, name):
    """Heide's Tower's floor is brown and gold, close enough to a sliver of fill
    and trail to read as a bar in the empty slots without the empty-bar check."""
    img = frame(name, width)
    slots = ds2.boss_slots if name == "ds2_no_boss_floor" else ds2.boss_slots[1:]
    for slot in slots:
        assert read_bar(img, slot["bar"], ds2.data["bar_colors"]).pct is None


def test_ds2_trail_only_bar_is_the_killing_blow(ds2):
    """A bar holding only trail, with the empty bar after it, still reads as 0%."""
    img = cv2.imread(str(FIX / "ds2_dragonrider_low_1080p.jpg"))
    x0 = 557  # left end of the fill at 1080p
    img[919:933, x0:x0 + 200] = img[919:933, x0 + 600:x0 + 800]  # empty bar over the 16% fill
    img[920:932, x0:x0 + 38] = (70, 131, 171)  # measured from a real trail
    r = read_bar(img, ds2.boss_slots[0]["bar"], ds2.data["bar_colors"])
    assert r.pct == 0.0 and r.trail_pct == pytest.approx(3.8, abs=1)


@needs_tesseract
@pytest.mark.parametrize("name", ["ds2_dragonrider_full", "ds2_dragonrider_trail", "ds2_dragonrider_low"])
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds2_boss_name(ds2, name, width):
    slot = Analyzer(ds2).analyze(frame(name, width), force_ocr=True).slots[0]
    assert slot.match is not None and slot.match.boss == "Dragonrider", slot.text


def test_ds2_noise_after_the_name_is_not_another_boss(ds2):
    # Read off the bright floor at 1280 wide; WRatio matched it to Demon of Song.
    assert ds2.match_boss("Deragcon whi” oF ee ort a") is None
    assert ds2.match_boss("Dragonrtder -_, . ° a gen").boss == "Dragonrider"
    assert ds2.match_boss("RuinSentinel Ricce 146").boss == "Ruin Sentinels"


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds2_death(ds2, width):
    a = Analyzer(ds2)
    assert a.death.mode == "template"
    hit, score = a.death.detect(frame("ds2_dragonrider_died", width))
    assert hit and score > 0.9
    # 0.4s into the fade-in, the first frame over the threshold
    hit, score = a.death.detect(frame("ds2_dragonrider_died_fadein", width))
    assert hit
    for name in ("ds2_dragonrider_full", "ds2_dragonrider_trail", "ds2_dragonrider_low",
                 "ds2_no_boss_floor", "ds2_ruin_sentinels"):
        hit, score = a.death.detect(frame(name, width))
        assert not hit and score < 0.2, name


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds2_three_bars(ds2, width):
    """Ruin Sentinels: three bars stacked upwards, Yahim's at the bottom."""
    img = frame("ds2_ruin_sentinels", width)
    pcts = [read_bar(img, s["bar"], ds2.data["bar_colors"]).pct for s in ds2.boss_slots]
    assert pcts == [pytest.approx(51.9, abs=1), pytest.approx(100, abs=1), pytest.approx(100, abs=1)]
    assert ds2.bar_count("Ruin Sentinels") == 3


# -- Dark Souls III: Iudex Gundyr, from the user's 1080p 60 fps clips. DS3 has no
# HUD scale setting. -----------------------------------------------------------

@pytest.fixture(scope="module")
def ds3():
    return load_profile(ROOT / "profiles", "dark_souls_3")


@pytest.mark.parametrize("width", [2560, 1920, 1280])
@pytest.mark.parametrize("name,pct,trail", [
    ("ds3_gundyr_full", 100, 0), ("ds3_gundyr_trail", 94.4, 5.6), ("ds3_gundyr_low", 3.7, 0),
    ("ds3_gundyr_died", 94.2, 0)])
def test_ds3_bar(ds3, width, name, pct, trail):
    r = read_bar(frame(name, width), ds3.boss_slots[0]["bar"], ds3.data["bar_colors"])
    assert r.pct == pytest.approx(pct, abs=1.0)
    assert r.trail_pct == pytest.approx(trail, abs=1.5)
    assert read_bar(frame(name, width), ds3.boss_slots[1]["bar"], ds3.data["bar_colors"]).pct is None


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds3_killing_blow_and_empty_bar(ds3, width):
    """The real killing blow: only trail left (0%), then the emptied bar, which
    DS3 keeps on screen through the boss's death animation."""
    r = read_bar(frame("ds3_gundyr_zero", width), ds3.boss_slots[0]["bar"], ds3.data["bar_colors"])
    assert r.pct == 0.0 and r.trail_pct == pytest.approx(3.6, abs=1.5)
    assert read_bar(frame("ds3_gundyr_empty", width), ds3.boss_slots[0]["bar"], ds3.data["bar_colors"]).pct is None


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds3_bar_in_a_dark_arena(ds3, width):
    """The empty part of the bar lets the scene through: in the Abyss Watchers'
    dark arena it's nearly black, and the fill must still read."""
    r = read_bar(frame("ds3_abyss_dark", width), ds3.boss_slots[0]["bar"], ds3.data["bar_colors"])
    assert r.pct == pytest.approx(18.0, abs=1.0)


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds3_bar_against_a_bright_sky(ds3, width):
    """Looking up at the sky, the see-through empty part turns pale grey; the
    bar used to drop out there and the HUD flickered on and off."""
    r = read_bar(frame("ds3_gundyr_sky", width), ds3.boss_slots[0]["bar"], ds3.data["bar_colors"])
    assert r.pct == pytest.approx(65.7, abs=1.0)


@needs_tesseract
@pytest.mark.parametrize("name", ["ds3_gundyr_full", "ds3_gundyr_trail", "ds3_gundyr_low", "ds3_gundyr_zero"])
@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds3_boss_name(ds3, name, width):
    slot = Analyzer(ds3).analyze(frame(name, width), force_ocr=True).slots[0]
    assert slot.match is not None and slot.match.boss == "Iudex Gundyr", slot.text


@pytest.mark.parametrize("width", [2560, 1920, 1280])
def test_ds3_death(ds3, width):
    a = Analyzer(ds3)
    assert a.death.mode == "template"
    hit, score = a.death.detect(frame("ds3_gundyr_died", width))
    assert hit and score > 0.9
    # 0.5s into the fade-in
    hit, score = a.death.detect(frame("ds3_gundyr_died_fadein", width))
    assert hit
    for name in ("ds3_gundyr_full", "ds3_gundyr_trail", "ds3_gundyr_low", "ds3_gundyr_zero",
                 "ds3_gundyr_empty"):
        hit, score = a.death.detect(frame(name, width))
        assert not hit and score < 0.15, name


@needs_tesseract
def test_ds3_real_kill_and_death():
    """Frame by frame as in the clips: DEFEATED on the second 0% read, saved as
    a kill once the name goes; a death under a bar that stays up."""
    from soulsoverlay.tracker import Tracker

    p = load_profile(ROOT / "profiles", "dark_souls_3")

    def play(frames):
        tr, a, ev = Tracker(p), Analyzer(p), []
        for i, img in enumerate(frames):
            r = a.analyze(img, now=i * 0.1, watch_names=tr.defeat_pending)
            ev += [(round(r.t, 1), k) for k, _ in tr.update(r)]
        return ev, tr

    low, zero, empty = (frame(n, 1920) for n in ("ds3_gundyr_low", "ds3_gundyr_zero", "ds3_gundyr_empty"))
    ev, _ = play([low] * 5 + [zero] * 5 + [empty] * 10 + [_without_boss(p, empty)] * 20)
    assert [(t, k) for t, k in ev if k in ("defeated", "kill", "death")] == [(0.6, "defeated"), (3.7, "kill")]

    full, died = frame("ds3_gundyr_trail", 1920), frame("ds3_gundyr_died", 1920)
    ev, tr = play([full] * 5 + [frame("ds3_gundyr_died_fadein", 1920)] + [died] * 10 + [full] * 10)
    assert [k for _, k in ev if k in ("engage", "death", "defeated", "kill")] == ["engage", "death"]
    assert tr.encounter is None and tr.bar_up  # the HUD stays with the game's bar


@needs_tesseract
def test_watch_names_reads_the_name_after_the_bar_empties(er_real):
    """A boss left on a sliver: the bar looks empty, but its name is still up."""
    img = damage(er_real, frame("er_morgott_full", 1920), 0, 0)
    a = Analyzer(er_real)
    r = a.analyze(img, now=0.0)
    assert r.slots[0].pct is None and r.slots[0].match is None
    r = a.analyze(img, now=0.5, watch_names=True)
    assert r.slots[0].pct is None
    assert r.slots[0].match and r.slots[0].match.boss == "Morgott, the Omen King"


# -- DEFEATED at 0%, on each game's real frames -------------------------------
# From each game's low-health shot: the red repainted in the colour of the
# damage trail from its trail shot (the killing blow: 0%, trail draining), the
# whole bar in its empty colour (a sliver too small to show, name still up),
# and the bar and name strip blanked (the boss gone).

GAMES = [("elden_ring", "er_sentinel_low", "er_morgott_trail", "Tree Sentinel", "er_sentinel_died_fadein"),
         ("dark_souls_remastered", "dsr_asylum_fight", "dsr_asylum_trail", "Asylum Demon", "dsr_asylum_died"),
         ("dark_souls_2", "ds2_dragonrider_low", "ds2_dragonrider_trail", "Dragonrider", "ds2_dragonrider_died"),
         ("dark_souls_3", "ds3_gundyr_low", "ds3_gundyr_trail", "Iudex Gundyr", "ds3_gundyr_died")]


def _box(img, region):
    H, W = img.shape[:2]
    x, y, w, h = region
    return int(x * W), int(y * H), int(round(w * W)), max(1, int(round(h * H)))


def _killing_blow_frames(profile, img, trail_img):
    from soulsoverlay.detect import hsv_mask

    x, y, w, h = _box(img, profile.boss_slots[0]["bar"])
    colors = profile.data["bar_colors"]
    cols = lambda bar, spec: hsv_mask(bar, spec).mean(axis=0) >= colors.get("column_threshold", 0.35)
    tbar = trail_img[y:y + h, x:x + w]
    trail_px = tbar[:, cols(tbar, colors["trail"]) & ~cols(tbar, colors["fill"])].reshape(-1, 3)
    bar = img[y:y + h, x:x + w]
    fill = cols(bar, colors["fill"])
    empty_x = int(np.flatnonzero(fill).max()) + 8
    zero = img.copy()
    zbar = zero[y:y + h, x:x + w]
    zbar[:, fill] = np.median(trail_px, axis=0).astype(np.uint8)  # all of it trail now
    empty = img.copy()
    empty[y:y + h, x:x + w] = bar[:, empty_x:empty_x + 1]  # the empty bar's colour
    return zero, empty, _without_boss(profile, empty)


def _without_boss(profile, img):
    img = img.copy()
    for key in ("bar", "name"):
        bx, by, bw, bh = _box(img, profile.boss_slots[0][key])
        img[by - 3:by + bh + 3, bx - 3:bx + bw + 3] = img[by - 40:by - 10, bx:bx + bw].mean(axis=(0, 1))
    return img


@needs_tesseract
@pytest.mark.parametrize("game,low_shot,trail_shot,boss,died", GAMES)
def test_defeated_on_real_frames(game, low_shot, trail_shot, boss, died):
    from soulsoverlay.tracker import Tracker

    profile = load_profile(ROOT / "profiles", game)
    src = frame(low_shot, 1920)
    zero, empty, gone = _killing_blow_frames(profile, src, frame(trail_shot, 1920))
    a = Analyzer(profile)
    assert read_bar(zero, profile.boss_slots[0]["bar"], profile.data["bar_colors"]).pct == 0.0
    assert read_bar(empty, profile.boss_slots[0]["bar"], profile.data["bar_colors"]).pct is None

    def play(frames, t0=0.0):
        tr, ev, a = Tracker(profile), [], Analyzer(profile)
        for i, img in enumerate(frames):
            r = a.analyze(img, now=t0 + i * 0.1, watch_names=tr.defeat_pending)
            ev += [(round(r.t, 1), k, d) for k, d in tr.update(r)]
        return ev

    # Killed: DEFEATED on the second 0% frame, the kill 1.5s after the boss goes.
    ev = play([src] * 3 + [zero] * 3 + [gone] * 20)
    assert [(t, k) for t, k, _ in ev if k in ("defeated", "kill", "defeated_cancel")] == [
        (0.4, "defeated"), (2.0, "kill")]
    assert [d["boss"] for _, k, d in ev if k == "kill"] == [boss]

    # A sliver left: the bar looks empty but the name stays, then YOU DIED.
    ev = play([src] * 3 + [zero] * 3 + [empty] * 20 + [frame(died, 1920)] * 3)
    kinds = [k for _, k, _ in ev if k in ("defeated", "kill", "defeated_cancel", "death")]
    assert kinds == ["defeated", "defeated_cancel", "death"]
    assert [d["boss"] for _, k, d in ev if k == "death"] == [boss]

    # Boss gone, then we die: the kill stands.
    ev = play([src] * 3 + [zero] * 3 + [gone] * 8 + [_without_boss(profile, frame(died, 1920))] * 3)
    kinds = [k for _, k, _ in ev if k in ("defeated", "kill", "defeated_cancel", "death")]
    assert kinds == ["defeated", "kill", "death"]
