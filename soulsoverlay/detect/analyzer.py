"""Runs every detector on a frame and returns one FrameReading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..profiles import BossMatch, Profile
from . import bossname
from .healthbar import read_bar
from .screen import ScreenDetector


@dataclass
class SlotReading:
    pct: float | None
    trail_pct: float
    text: str
    match: BossMatch | None


@dataclass
class FrameReading:
    t: float
    death: bool
    death_score: float
    victory: bool = False
    victory_score: float = 0.0
    slots: list[SlotReading] = field(default_factory=list)
    death_sure: bool = False  # clear enough to count on this one frame

    def to_json(self) -> dict:
        return {
            "t": self.t,
            "death": self.death,
            "death_score": round(self.death_score, 3),
            "victory": self.victory,
            "victory_score": round(self.victory_score, 3),
            "slots": [
                {
                    "pct": s.pct,
                    "trail_pct": s.trail_pct,
                    "text": s.text,
                    "boss": s.match.boss if s.match else None,
                    "phase_hint": s.match.phase_hint if s.match else None,
                    "score": round(s.match.score, 1) if s.match else None,
                }
                for s in self.slots
            ],
        }


class Analyzer:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.reload()

    def reload(self):
        p = self.profile
        death = p.data["death"]
        self.death = ScreenDetector(p.regions.get("death"), death,
                                    p.asset_path(death.get("template")))
        self.victory = None
        if p.data.get("victory") and p.regions.get("victory"):
            v = {**p.data["death"], **p.data["victory"]}
            self.victory = ScreenDetector(p.regions["victory"], v, p.asset_path(v.get("template")))
        # OCR is the expensive part, so each slot caches its last text and
        # only re-reads every `interval_s`, or straight away when its bar
        # appears or disappears.
        self._ocr_cache: list[tuple[float, bool, str]] = [(0.0, False, "")] * len(p.boss_slots)
        self._appeared: list[float | None] = [None] * len(p.boss_slots)

    def analyze(self, frame: np.ndarray, now: float | None = None, force_ocr: bool = False) -> FrameReading:
        now = time.monotonic() if now is None else now
        p = self.profile
        is_death, death_score = self.death.detect(frame)
        reading = FrameReading(now, is_death, death_score)
        # Elden Ring hides the boss bar as YOU DIED fades in, so every frame of
        # waiting is time the HUD has nothing to sit on. A clear template match
        # counts straight away; a borderline one still needs a second frame.
        reading.death_sure = (is_death and self.death.mode == "template"
                              and death_score >= p.data["death"]["instant_score"])
        if self.victory is not None:
            reading.victory, reading.victory_score = self.victory.detect(frame)

        for i, slot in enumerate(p.boss_slots):
            bar = read_bar(frame, slot.get("bar"), p.data["bar_colors"])
            visible = bar.pct is not None
            last_t, last_visible, last_text = self._ocr_cache[i]
            text = last_text
            # OCR is by far the slowest step (a Tesseract process per call), and
            # every frame it holds up is a frame the death check waits for. Once
            # the name has matched a boss, re-read it only now and then; never
            # spend the time on a frame that already shows the death screen.
            known = bool(last_text) and p.match_boss(last_text) is not None
            ocr = p.data["ocr"]
            if visible and self._appeared[i] is None:
                self._appeared[i] = now
            # The name fades in with the bar, so the first read often misses.
            # Retry on every frame for a few seconds, so the overlay appears as
            # soon as the name is legible, then back off for unknown names.
            fresh = visible and now - self._appeared[i] <= ocr["fast_retry_s"]
            interval = ocr["interval_matched_s"] if known else (0.0 if fresh else ocr["interval_s"])
            due = not last_visible or now - last_t >= interval
            if visible and (force_ocr or (due and not is_death)):
                text = bossname.read_name(frame, slot.get("name"), p.data["ocr"])
                self._ocr_cache[i] = (now, True, text)
            elif not visible:
                text = ""
                self._ocr_cache[i] = (now, False, "")
                self._appeared[i] = None
            match = p.match_boss(text) if text else None
            reading.slots.append(SlotReading(bar.pct, bar.trail_pct, text, match))
        return reading
