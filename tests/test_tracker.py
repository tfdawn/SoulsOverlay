import pytest

from dataclasses import replace

from soulsoverlay.detect.analyzer import FrameReading, SlotReading
from soulsoverlay.tracker import Tracker


def slot(profile, name, pct, trail=0.0):
    return SlotReading(pct, trail, name or "", profile.match_boss(name) if name else None)


def reading(profile, t, *slots, death=False, victory=False):
    s = list(slots) + [SlotReading(None, 0, "", None)] * (2 - len(slots))
    return FrameReading(t, death, 1.0 if death else 0.0, victory, 0.0, s)


def run(tracker, readings):
    events = []
    for r in readings:
        events.extend(tracker.update(r))
    return events


def kinds(events, kind):
    return [d for k, d in events if k == kind]


def test_death_attributed_with_pre_death_pct(er):
    tr = Tracker(er)
    seq = [reading(er, t * 0.5, slot(er, "Margit, the Fell Omen", 100 - t * 2)) for t in range(30)]
    t0 = 15.0
    # Death screen: bar is still visible for a beat, then the HUD goes.
    seq += [reading(er, t0, slot(er, "Margit, the Fell Omen", 42.0), death=True),
            reading(er, t0 + 0.5, death=True), reading(er, t0 + 1.0, death=True)]
    ev = run(tr, seq)
    assert len(kinds(ev, "engage")) == 1
    deaths = kinds(ev, "death")
    assert len(deaths) == 1
    assert deaths[0]["boss"] == "Margit, the Fell Omen"
    assert 40 <= deaths[0]["pct"] <= 46


def test_one_banner_is_one_death_even_after_cooldown(er):
    tr = Tracker(er)
    ev = run(tr, [reading(er, t * 0.5, death=True) for t in range(60)])
    assert len(kinds(ev, "death")) == 1
    ev = run(tr, [reading(er, 31), reading(er, 32, death=True), reading(er, 32.5, death=True)])
    assert len(kinds(ev, "death")) == 1


def test_death_without_boss(er):
    ev = run(Tracker(er), [reading(er, 0, death=True), reading(er, 0.5, death=True)])
    assert kinds(ev, "death")[0]["boss"] is None


def test_unclear_name_needs_confirming_before_engaging(er):
    tr = Tracker(er)
    weak = slot(er, "Margit, the Fell Omen", 100)
    weak.match = replace(weak.match, score=80.0)
    ev = run(tr, [reading(er, 0, weak), reading(er, 0.5)])
    assert not kinds(ev, "engage")
    ev = run(tr, [reading(er, 1.0, weak)])
    assert kinds(ev, "engage")


def test_clear_name_engages_on_first_read(er):
    tr = Tracker(er)
    ev = run(tr, [reading(er, 0, slot(er, "Margit, the Fell Omen", 100))])
    assert kinds(ev, "engage")[0]["boss"] == "Margit, the Fell Omen"


def test_phase_by_refill_and_by_name(er):
    tr = Tracker(er)
    m1, m2 = "Malenia, Blade of Miquella", "Malenia, Goddess of Rot"
    seq = [reading(er, i * 0.5, slot(er, m1, max(0, 100 - i * 5))) for i in range(22)]
    seq += [reading(er, 11 + i * 0.5) for i in range(6)]  # transition: no bar
    seq += [reading(er, 14 + i * 0.5, slot(er, m2, 100 - i)) for i in range(10)]
    seq += [reading(er, 19, slot(er, m2, 90), death=True), reading(er, 19.5, death=True)]
    ev = run(tr, seq)
    assert not kinds(ev, "kill"), "phase 1 reaching 0% is not a kill for a 2-phase boss"
    assert [p["phase"] for p in kinds(ev, "phase")] == [2]
    d = kinds(ev, "death")[0]
    assert d["phase"] == 2 and d["boss"] == m1


def test_refill_without_name_change(er):
    tr = Tracker(er)
    boss = "Rennala, Queen of the Full Moon"
    seq = [reading(er, i * 0.5, slot(er, boss, max(2, 100 - i * 10))) for i in range(12)]
    seq += [reading(er, 6 + i * 0.5, slot(er, boss, 100)) for i in range(4)]
    ev = run(tr, seq)
    assert [p["phase"] for p in kinds(ev, "phase")] == [2]


def test_kill_when_bar_drains_and_vanishes(er):
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    seq = [reading(er, i * 0.5, slot(er, boss, max(0.0, 30 - i * 3))) for i in range(12)]
    seq += [reading(er, 6 + i * 0.5) for i in range(20)]
    ev = run(tr, seq)
    assert kinds(ev, "kill") == [{"boss": boss, "phase": 1, "shown": True}]


def drained(er, boss, until):
    """Health draining to 0% (trail only) by `until`, two reads a second."""
    n = int(until * 2)
    return [reading(er, i * 0.5, slot(er, boss, max(0.0, 30 - 30 * i / (n - 2)))) for i in range(n + 1)]


def test_defeated_shows_at_zero_and_kill_follows_when_boss_leaves(er):
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    seq = drained(er, boss, 6.0)
    ev, shown_at = [], None
    for r in seq:
        new = tr.update(r)
        if kinds(new, "defeated"):
            shown_at = r.t
        ev += new
    first_zero = next(r.t for r in seq if r.slots[0].pct == 0.0)
    assert kinds(ev, "defeated") == [{"boss": boss, "phase": 1}]
    assert shown_at == first_zero + 0.5  # the second 0% read
    assert not kinds(ev, "kill")
    # The bar and name go: saved 1.5s later.
    ev = run(tr, [reading(er, 6.5), reading(er, 7.0)])
    assert not kinds(ev, "kill")
    ev = run(tr, [reading(er, 7.5)])
    assert kinds(ev, "kill") == [{"boss": boss, "phase": 1, "shown": True}]


def test_sliver_left_and_you_died_takes_defeated_back(er):
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    run(tr, drained(er, boss, 6.0))
    # The bar looks empty but the name stays up: the boss is still there.
    name_only = SlotReading(None, 0.0, boss, er.match_boss(boss))
    ev = run(tr, [reading(er, 6.5 + i * 0.5, name_only) for i in range(10)])
    assert not kinds(ev, "kill")
    ev = run(tr, [reading(er, 11.5, name_only, death=True), reading(er, 12.0, death=True)])
    assert kinds(ev, "defeated_cancel") == [{"boss": boss}]
    assert not kinds(ev, "kill")
    d = kinds(ev, "death")
    assert len(d) == 1 and d[0]["boss"] == boss and d[0]["pct"] == 0.0


def test_dying_after_the_boss_keeps_the_kill(er):
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    run(tr, drained(er, boss, 6.0))
    # Boss gone, and we die a second later (before the kill was saved).
    ev = run(tr, [reading(er, 6.5), reading(er, 7.0, death=True), reading(er, 7.5, death=True)])
    assert kinds(ev, "kill") == [{"boss": boss, "phase": 1, "shown": True}]
    assert not kinds(ev, "defeated_cancel")
    assert len(kinds(ev, "death")) == 1 and kinds(ev, "death")[0]["boss"] is None


def test_health_coming_back_takes_defeated_back(er):
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    run(tr, drained(er, boss, 6.0))
    ev = run(tr, [reading(er, 6.5, slot(er, boss, 12.0)), reading(er, 7.0, slot(er, boss, 12.0))])
    assert kinds(ev, "defeated_cancel") == [{"boss": boss}]


def test_zero_in_an_early_phase_is_not_defeated(er):
    tr = Tracker(er)
    ev = run(tr, drained(er, "Malenia, Blade of Miquella", 6.0))
    assert not kinds(ev, "defeated")


def test_walking_away_is_not_a_kill(er):
    tr = Tracker(er)
    seq = [reading(er, i * 0.5, slot(er, "Margit, the Fell Omen", 70)) for i in range(5)]
    seq += [reading(er, 3 + i * 0.5) for i in range(20)]
    ev = run(tr, seq)
    assert not kinds(ev, "kill") and kinds(ev, "disengage")


def test_duo_phase_two_tracks_survivor(profiles_dir):
    from soulsoverlay.profiles import load_profile

    dsr = load_profile(profiles_dir, "dark_souls_remastered")
    tr = Tracker(dsr)
    o, s = "Dragon Slayer Ornstein", "Executioner Smough"
    seq = [reading(dsr, i * 0.5, slot(dsr, o, 80 - i * 4), slot(dsr, s, 90)) for i in range(10)]
    seq += [reading(dsr, 5 + i * 0.5, slot(dsr, s, 100 - i)) for i in range(6)]
    seq += [reading(dsr, 9, slot(dsr, s, 93), death=True), reading(dsr, 9.5, death=True)]
    ev = run(tr, seq)
    assert len(kinds(ev, "engage")) == 1
    assert kinds(ev, "engage")[0]["boss"] == "Ornstein and Smough"
    assert [p["phase"] for p in kinds(ev, "phase")] == [2]
    d = kinds(ev, "death")[0]
    assert d["phase"] == 2 and 93 <= d["pct"] <= 97


def test_pinned_boss_used_when_ocr_fails(er):
    tr = Tracker(er)
    tr.pin_boss("Godrick the Grafted")
    ev = run(tr, [reading(er, 0, death=True), reading(er, 0.5, death=True)])
    assert kinds(ev, "death")[0]["boss"] == "Godrick the Grafted"


def test_bar_up_follows_the_game_bar(er):
    tr = Tracker(er)
    m = "Margit, the Fell Omen"
    ev = run(tr, [reading(er, 0, slot(er, m, 80)), reading(er, 0.25, slot(er, m, 79))])
    assert [d["up"] for d in kinds(ev, "bar")] == [True]
    # One missed read keeps it up; two in a row (the bar is gone) hide it,
    # long before the fight itself times out.
    assert not kinds(run(tr, [reading(er, 0.5)]), "bar")
    assert tr.bar_up
    ev = run(tr, [reading(er, 0.75)])
    assert [d["up"] for d in kinds(ev, "bar")] == [False]
    assert tr.encounter is not None
    ev = run(tr, [reading(er, 1.0, slot(er, m, 79))])
    assert [d["up"] for d in kinds(ev, "bar")] == [True]


def test_bar_up_lasts_as_long_as_the_bar_after_a_death(er):
    tr = Tracker(er)
    m = "Margit, the Fell Omen"
    run(tr, [reading(er, 0, slot(er, m, 80))])
    ev = run(tr, [reading(er, 0.25, slot(er, m, 50), death=True), reading(er, 0.5, slot(er, m, 50), death=True)])
    assert kinds(ev, "death") and tr.bar_up
    # The name is still cached under YOU DIED; that must not start a new fight.
    assert not kinds(ev, "engage") and tr.encounter is None
    ev = run(tr, [reading(er, 0.75, death=True), reading(er, 1.0, death=True)])
    assert [d["up"] for d in kinds(ev, "bar")] == [False]
    # Any bar after that needs a fresh engage to count.
    run(tr, [reading(er, 30, SlotReading(60.0, 0, "", None))])
    assert not tr.bar_up


def test_clear_death_counts_on_one_frame(er):
    tr = Tracker(er)
    r = reading(er, 0, death=True)
    r.death_sure = True
    assert kinds(run(tr, [r]), "death")
    assert not kinds(run(Tracker(er), [reading(er, 0, death=True)]), "death")


def test_faint_banner_right_after_the_bar_vanishes_counts(er):
    tr = Tracker(er)
    m = "Margit, the Fell Omen"
    run(tr, [reading(er, t * 0.1, slot(er, m, 70)) for t in range(5)])
    faint = reading(er, 0.6)
    faint.death_score = 0.3  # below the normal threshold
    ev = run(tr, [reading(er, 0.5), faint])
    assert len(kinds(ev, "death")) == 1 and not tr.bar_up
    # The banner growing clearer afterwards is the same death.
    ev = run(tr, [reading(er, t, death=True) for t in (0.7, 0.8, 0.9)])
    assert not kinds(ev, "death")


def test_faint_red_without_the_bar_vanishing_is_not_a_death(er):
    tr = Tracker(er)
    m = "Margit, the Fell Omen"
    r = reading(er, 0.1, slot(er, m, 70))
    r.death_score = 0.3
    assert not kinds(run(tr, [reading(er, 0, slot(er, m, 70)), r]), "death")
    late = reading(er, 5.0)
    late.death_score = 0.3
    assert not kinds(run(tr, [reading(er, t * 0.5) for t in range(1, 10)] + [late]), "death")


def test_bar_left_up_after_the_banner_is_not_a_new_fight(er):
    # Dark Souls Remastered: the bar of the boss that killed us stays up after
    # YOU DIED fades, until the loading screen. Only the next fight engages.
    tr = Tracker(er)
    boss = "Margit, the Fell Omen"
    seq = [reading(er, t * 0.5, slot(er, boss, 40)) for t in range(4)]
    seq += [reading(er, 2 + t * 0.5, slot(er, boss, 40), death=True) for t in range(4)]
    seq += [reading(er, 4 + t * 0.5, slot(er, boss, 40)) for t in range(8)]  # banner gone, bar still up
    seq += [reading(er, 8 + t * 0.5) for t in range(6)]  # loading screen
    seq += [reading(er, 11 + t * 0.5, slot(er, boss, 100)) for t in range(4)]  # back in the fog
    ev = run(tr, seq)
    assert len(kinds(ev, "death")) == 1
    assert [e["boss"] for e in kinds(ev, "engage")] == [boss, boss]
    assert tr.encounter and tr.encounter.started == 11


def test_group_without_phases_averages_with_late_and_fallen_bars():
    """Ruin Sentinels: Yahim fights alone at first, the other two drop in later,
    and a fallen sentinel's bar goes away. Bars yet to appear count as full,
    fallen ones as empty, so the reading only ever goes down."""
    from pathlib import Path
    from soulsoverlay.profiles import load_profile

    ds2 = load_profile(Path(__file__).resolve().parents[1] / "profiles", "dark_souls_2")
    tr = Tracker(ds2)

    def at(t, *pcts):
        names = ["Ruin Sentinel Yahim", "Ruin Sentinel Ricce", "Ruin Sentinel Alessia"]
        s = [slot(ds2, names[i], p) for i, p in enumerate(pcts)]
        return FrameReading(t, False, 0.0, False, 0.0, s + [SlotReading(None, 0, "", None)] * (3 - len(s)))

    ev = run(tr, [at(0, 100), at(0.5, 100), at(1.0, 40), at(1.5, 40), at(2.0, 40)])
    assert kinds(ev, "engage")[0]["boss"] == "Ruin Sentinels"
    assert kinds(ev, "live")[-1]["pct"] == 80.0
    ev = run(tr, [at(t, 40, 100, 100) for t in (2.5, 3.0, 3.5)])
    assert kinds(ev, "live")[-1]["pct"] == 80.0
    ev = run(tr, [at(t, 100, 100) for t in (4.0, 4.5, 5.0)])  # Yahim falls
    assert kinds(ev, "live")[-1]["pct"] == pytest.approx(66.7, abs=0.1)
    assert not kinds(ev, "phase")


@pytest.mark.parametrize("game,boss", [("elden_ring", "Margit, the Fell Omen"),
                                       ("dark_souls_remastered", "Asylum Demon"),
                                       ("dark_souls_2", "Dragonrider"),
                                       ("dark_souls_3", "Iudex Gundyr")])
def test_defeated_in_every_game(game, boss):
    from pathlib import Path

    from soulsoverlay.profiles import load_profile

    p = load_profile(Path(__file__).resolve().parents[1] / "profiles", game)
    tr = Tracker(p)
    ev = run(tr, drained(p, boss, 6.0))
    assert kinds(ev, "defeated") == [{"boss": boss, "phase": 1}]
    ev = run(tr, [reading(p, 6.5), reading(p, 7.0), reading(p, 7.5)])
    assert kinds(ev, "kill") == [{"boss": boss, "phase": 1, "shown": True}]
