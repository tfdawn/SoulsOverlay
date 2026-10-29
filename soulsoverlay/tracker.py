"""Turns a stream of FrameReadings into game events.

The tracker is pure logic with an injected clock, so it can be driven by
recorded readings in tests. It never writes to the database itself; it
returns events and the service applies them.

Event types it emits:
    engage      {boss, phase}
    phase       {boss, phase}
    live        {boss, phase, pct}           smoothed health, for the overlay
    death       {boss|None, phase, pct}      pct is health just before death
    defeated    {boss, phase}                the bar hit 0%: show DEFEATED now
    defeated_cancel {boss}                   ...but YOU DIED came while the boss
                                             was still on screen (a sliver left)
    kill        {boss, phase, shown}         shown: DEFEATED is already up
    disengage   {boss}
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field

from .detect.analyzer import FrameReading
from .profiles import Profile


@dataclass
class Encounter:
    boss: str
    phase: int = 1
    bars: int = 1
    started: float = 0.0
    last_seen: float = 0.0
    readings: deque = field(default_factory=lambda: deque(maxlen=120))  # (t, phase, pct)
    max_visible_bars: int = 0
    refill_count: int = 0
    # Set when the bar hits 0%. The kill is only saved once the boss's bar
    # and name have left the screen; until then a YOU DIED means a sliver of
    # health was left that the bar couldn't show.
    defeated_at: float | None = None
    still_there: float = 0.0  # last time its bar or name was on screen

    def recent(self, n: int = 3) -> float | None:
        vals = [p for _, ph, p in list(self.readings)[-n:] if ph == self.phase]
        return statistics.median(vals) if vals else None


class Tracker:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.encounter: Encounter | None = None
        self.last_boss: str | None = None  # stays on the overlay after a fight
        self.pinned_boss: str | None = None  # manual override
        self._candidate: tuple[str, int] | None = None  # (boss, consecutive reads)
        self._death_streak = 0
        self._death_latched = False
        self._last_death_t = -1e9
        self._victory_streak = 0
        self.bar_up = False  # the boss bar is on screen right now
        self.bar_boss: str | None = None  # whose bar that is
        self._bar_misses = 0
        self._bar_miss_t = -1e9  # when the bar first went missing
        # Dark Souls Remastered keeps the bar of the boss that killed us up
        # after "YOU DIED" fades, until the loading screen. That's still the
        # fight that just ended, so the boss can't be engaged again until its
        # bar has gone away once.
        self._killed_by: str | None = None
        # Bosses that share a bar name (see Profile.shown_as). `beaten` says
        # whether a boss has been killed on this character; `variant_choice`
        # holds the user's pick when the guess was wrong.
        self.beaten = lambda boss: False
        self.variant_choice: dict[str, str] = {}

    @property
    def cfg(self) -> dict:
        return self.profile.data["tracking"]

    @property
    def defeat_pending(self) -> bool:
        """DEFEATED is up but not confirmed: the analyzer should keep reading
        the name strip after the bar goes."""
        return self.encounter is not None and self.encounter.defeated_at is not None

    @property
    def display_boss(self) -> str | None:
        if self.encounter:
            return self.encounter.boss
        return self.pinned_boss or self.last_boss

    # -- bosses that share a bar name ------------------------------------
    def _names(self, s, boss: str) -> bool:
        """The slot's name strip reads as this boss (or the name it goes by)."""
        return bool(s.match) and s.match.boss in (boss, self.profile.shown_as(boss))

    def _resolve(self, matched: list) -> str:
        """Which boss the name on screen means. Dark Souls II gives two pairs
        of bosses one name: the Twin Dragonriders show two "Dragonrider" bars
        from the start, and the blue Smelter Demon is taken to be the one met
        once the Iron Keep one is beaten (experimental). The user's own pick
        wins, and a fight keeps its boss when one of the twins falls."""
        name = matched[0].match.boss
        alikes = self.profile.look_alikes(name)
        if not alikes:
            return name
        enc = self.encounter
        if enc is not None and enc.boss in alikes:
            return enc.boss
        same = sum(1 for s in matched if s.match.boss == name)
        for alike in alikes:
            if self.profile.bar_count(alike) > 1 and same > 1:
                return alike
        if name in self.variant_choice:
            return self.variant_choice[name]
        for alike in alikes:
            if self.profile.bar_count(alike) == 1 and self.beaten(name):
                return alike
        return name

    def choose_variant(self, boss: str):
        """The user says the boss on screen is `boss`, one of a same-name pair."""
        base = self.profile.shown_as(boss)
        self.variant_choice[base] = boss
        enc = self.encounter
        if enc is not None and self.profile.shown_as(enc.boss) == base:
            enc.boss = boss
        if self.pinned_boss and self.profile.shown_as(self.pinned_boss) == base:
            self.pinned_boss = boss
        if self.last_boss and self.profile.shown_as(self.last_boss) == base:
            self.last_boss = boss
        if self._killed_by and self.profile.shown_as(self._killed_by) == base:
            self._killed_by = boss

    # -- manual controls -------------------------------------------------
    def pin_boss(self, boss: str | None):
        self.pinned_boss = boss
        if boss:
            self.last_boss = boss

    def manual_death_context(self, now: float) -> tuple[str | None, int, float | None]:
        """Boss/phase/pct to attach to a death added by hotkey."""
        enc = self.encounter
        if enc and now - enc.last_seen <= self.cfg["attribution_window_s"]:
            return enc.boss, enc.phase, self._pre_death_pct(enc, now)
        boss = self.pinned_boss or self.last_boss
        return boss, 1, None

    # -- main loop -------------------------------------------------------
    def update(self, r: FrameReading) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        cfg = self.cfg
        now = r.t

        # 1. who is on screen?
        matched = [s for s in r.slots if s.match is not None]
        boss_now = None
        if matched:
            boss_now = self._resolve(matched)
            if self._candidate and self._candidate[0] == boss_now:
                self._candidate = (boss_now, self._candidate[1] + 1)
            else:
                self._candidate = (boss_now, 1)
        sure = bool(matched) and matched[0].match.score >= cfg["instant_score"]
        # The bar can stay up under "YOU DIED"; that is the fight that just
        # ended, not a new one.
        dying = r.death or self._death_latched
        if (boss_now and not dying and (sure or self._candidate[1] >= cfg["confirm_reads"])
                and (self.encounter is None or self.encounter.boss != boss_now)
                and boss_now != self._killed_by):
            if self.encounter:
                events.append(("disengage", {"boss": self.encounter.boss}))
            bars = min(self.profile.bar_count(boss_now), max(1, len(self.profile.boss_slots)))
            self.encounter = Encounter(boss_now, bars=bars,
                                       started=now, last_seen=now)
            self.last_boss = boss_now
            events.append(("engage", {"boss": boss_now, "phase": 1}))

        enc = self.encounter
        if enc is not None:
            self._update_health(enc, r, now, events)
            if enc.defeated_at is not None and (
                    enc.last_seen == now or any(self._names(s, enc.boss) for s in r.slots)):
                enc.still_there = now
        self._update_bar_up(enc, r, now, events)

        # 2. death banner
        dcfg = self.profile.data["death"]
        if r.death and not self._death_latched:
            self._death_streak += 1
        elif not r.death:
            self._death_streak = 0
            self._death_latched = False
        # The fight's bar has just vanished and the banner is starting to show.
        quick = (self.encounter is not None and self._bar_misses >= 1 and not self._death_latched
                 and now - self._bar_miss_t <= dcfg["bar_window_s"]
                 and r.death_score >= dcfg["with_bar_score"])
        if self._death_streak >= dcfg["confirm_frames"] or (
                self._death_streak and r.death_sure) or quick:
            # One banner is one death, however long it stays up. A second
            # banner inside the cooldown is treated as the same death.
            self._death_latched = True
            self._death_streak = 0
            fire = now - self._last_death_t >= self.profile.data["death"]["cooldown_s"]
        else:
            fire = False
        if fire:
            self._last_death_t = now
            enc = self.encounter
            if enc is not None and enc.defeated_at is not None:
                if now - enc.still_there > cfg["defeat_alive_s"]:
                    # The boss had already gone when we died: it still counts.
                    events.append(("kill", {"boss": enc.boss, "phase": enc.phase, "shown": True}))
                    self.encounter = None
                else:
                    events.append(("defeated_cancel", {"boss": enc.boss}))
            events.append(("death", self._death_payload(now)))
            if self.encounter:
                self._killed_by = self.encounter.boss
                self.encounter = None
            return events

        # 3. the bar hitting 0%, a victory banner, or the bar vanishing low
        if enc is not None and self._defeat(enc, r, now, events):
            return events
        if enc is not None:
            if r.victory:
                self._victory_streak += 1
            else:
                self._victory_streak = 0
            if self._victory_streak >= 2:
                events.append(("kill", {"boss": enc.boss, "phase": enc.phase}))
                self.encounter = None
                self._victory_streak = 0
            elif now - enc.last_seen >= cfg["disengage_s"]:
                last = enc.recent(3)
                max_ph = self.profile.max_phases(enc.boss)
                final_phase = max_ph is None or enc.phase >= max_ph
                if (last is not None and last <= cfg["kill_threshold_pct"] and final_phase
                        and self.profile.data.get("victory") is None):
                    events.append(("kill", {"boss": enc.boss, "phase": enc.phase}))
                    self.encounter = None
                elif last is not None and last <= cfg["kill_threshold_pct"] and not final_phase:
                    # Mid-fight transition (e.g. a cutscene between phases):
                    # keep waiting a while longer for the next bar.
                    if now - enc.last_seen >= cfg["phase_wait_s"]:
                        events.append(("disengage", {"boss": enc.boss}))
                        self.encounter = None
                else:
                    events.append(("disengage", {"boss": enc.boss}))
                    self.encounter = None
        return events

    # -- helpers ---------------------------------------------------------
    def _defeat(self, enc: Encounter, r: FrameReading, now: float, events) -> bool:
        """DEFEATED as soon as the bar reads 0%, or vanishes while nearly empty
        (Elden Ring can drop the bar before an empty one is ever read), saved
        as a kill once the boss has left the screen. True while that is in hand."""
        cfg = self.cfg
        max_ph = self.profile.max_phases(enc.boss)
        if max_ph is not None and enc.phase < max_ph:
            return False
        last = [p for _, ph, p in list(enc.readings)[-2:] if ph == enc.phase]
        if enc.defeated_at is None:
            zero = len(last) == 2 and max(last) <= cfg["defeat_pct"] and enc.last_seen == now
            # Not while YOU DIED is coming in: that's the bar going because we died.
            vanished = (enc.last_seen < now and self._bar_misses >= cfg["bar_hide_frames"]
                        and last and last[-1] <= cfg["kill_threshold_pct"]
                        and not r.death and r.death_score < self.profile.data["death"]["with_bar_score"])
            if zero or vanished:
                enc.defeated_at, enc.still_there = now, enc.last_seen
                events.append(("defeated", {"boss": enc.boss, "phase": enc.phase}))
                return True
            return False
        if enc.last_seen == now and last and min(last) > cfg["kill_threshold_pct"]:
            # Health showing again (a heal, or a bad read): not dead after all.
            enc.defeated_at = None
            events.append(("defeated_cancel", {"boss": enc.boss}))
            return False
        if enc.still_there != now and now - enc.still_there >= cfg["defeat_confirm_s"]:
            events.append(("kill", {"boss": enc.boss, "phase": enc.phase, "shown": True}))
            self.encounter = None
        return True

    def _update_bar_up(self, enc: Encounter | None, r: FrameReading, now: float, events):
        """Follow the game's bar closely so the HUD can come and go with it.
        After a death the bar may linger under "YOU DIED" or vanish at once;
        either way the HUD stays exactly as long as the bar. A couple of
        missed frames (not one, which can be a bad read) hides it."""
        if enc is not None:
            seen = enc.last_seen == now
            self.bar_boss = enc.boss
        else:
            # No fight, so only the bar of the boss that just killed us counts.
            seen = self.bar_boss is not None and self.bar_up and any(
                s.pct is not None for s in r.slots[:1])
        if seen:
            self._bar_misses = 0
            self._set_bar_up(True, events)
        else:
            self._bar_misses += 1
            if self._bar_misses == 1:
                self._bar_miss_t = now
            # One missed frame could be a bad read, unless the banner is coming in.
            if (self._bar_misses >= self.cfg["bar_hide_frames"]
                    or r.death_score >= self.profile.data["death"]["with_bar_score"]):
                self._set_bar_up(False, events)

    def _set_bar_up(self, up: bool, events):
        if not up and self.encounter is None:
            self.bar_boss = None
            self._killed_by = None
        if up != self.bar_up:
            self.bar_up = up
            events.append(("bar", {"up": up}))

    def _update_health(self, enc: Encounter, r: FrameReading, now: float, events):
        cfg = self.cfg
        slots = r.slots[: max(enc.bars, 1)]
        visible = [s for s in slots if s.pct is not None]
        if not visible:
            return
        # Only trust bars when the name strip belongs to this encounter (or
        # could not be read this frame, which happens on busy backgrounds).
        if any(s.match and not self._names(s, enc.boss) for s in visible):
            return
        # Back from a long gap (a cutscene between phases): cutscenes are full
        # of fire and blood that can pass for a bar, so wait for the name.
        if now - enc.last_seen > cfg["disengage_s"] and not any(
                self._names(s, enc.boss) for s in visible):
            return
        enc.last_seen = now
        for s in visible:
            if s.match and s.match.phase_hint and s.match.phase_hint > enc.phase:
                enc.phase = s.match.phase_hint
                events.append(("phase", {"boss": enc.boss, "phase": enc.phase}))

        if enc.bars > 1:
            # Duos: phase 1 is the average of both bars; when one partner
            # falls and its bar goes away, phase 2 tracks the survivor.
            # Groups without phases (Ruin Sentinels) stay one average: a bar
            # that hasn't shown up yet counts as full, a fallen one as empty.
            enc.max_visible_bars = max(enc.max_visible_bars, len(visible))
            duo = self.profile.max_phases(enc.boss) is not None
            if duo and enc.max_visible_bars == enc.bars and len(visible) < enc.bars:
                enc.refill_count += 1
                if enc.refill_count >= cfg["confirm_reads"] and enc.phase == 1:
                    enc.phase = 2
                    events.append(("phase", {"boss": enc.boss, "phase": 2}))
            else:
                enc.refill_count = 0
            if not duo:
                pct = (sum(s.pct for s in visible) + 100.0 * (enc.bars - enc.max_visible_bars)) / enc.bars
            elif enc.phase == 1:
                pct = sum(s.pct for s in slots if s.pct is not None) / enc.bars
            else:
                pct = min(s.pct for s in visible)
        else:
            pct = visible[0].pct
            prev = enc.recent(3)
            max_ph = self.profile.max_phases(enc.boss)
            can_advance = max_ph is None or enc.phase < max_ph
            if prev is not None and prev <= cfg["phase_low_pct"] and pct >= cfg["phase_refill_pct"]:
                enc.refill_count += 1
                if enc.refill_count >= cfg["confirm_reads"] and can_advance:
                    enc.phase += 1
                    enc.refill_count = 0
                    events.append(("phase", {"boss": enc.boss, "phase": enc.phase}))
                else:
                    return  # don't let one odd frame pollute the buffer
            else:
                enc.refill_count = 0

        enc.readings.append((now, enc.phase, round(pct, 1)))
        events.append(("live", {"boss": enc.boss, "phase": enc.phase, "pct": enc.recent(3)}))

    def _pre_death_pct(self, enc: Encounter, now: float) -> float | None:
        window = self.cfg["pre_death_window_s"]
        same_phase = [(t, p) for t, ph, p in enc.readings if ph == enc.phase]
        if not same_phase:
            return None
        recent = [p for t, p in same_phase if now - t <= window + 2.0]
        vals = recent[-3:] if recent else [same_phase[-1][1]]
        return round(statistics.median(vals), 1)

    def _death_payload(self, now: float) -> dict:
        enc = self.encounter
        if enc and now - enc.last_seen <= self.cfg["attribution_window_s"]:
            return {"boss": enc.boss, "phase": enc.phase, "pct": self._pre_death_pct(enc, now),
                    "source": "auto"}
        if self.pinned_boss:
            return {"boss": self.pinned_boss, "phase": 1, "pct": None, "source": "auto"}
        return {"boss": None, "phase": 1, "pct": None, "source": "auto"}
