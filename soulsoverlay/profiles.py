"""Per-game profiles: screen regions, colours, thresholds and boss lists.

Regions are stored as fractions of the frame ([x, y, w, h], all 0..1) so a
profile calibrated at 1080p keeps working when OBS hands us a 720p frame.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

DEFAULTS: dict = {
    "regions": {},
    "boss_slots": [],
    "bar_colors": {
        # OpenCV HSV: H 0..180, S/V 0..255. Hue ranges may wrap via two ranges.
        "fill": {"h": [[0, 10], [165, 180]], "s": [90, 255], "v": [45, 255]},
        "trail": {"h": [[12, 40]], "s": [70, 255], "v": [90, 255]},
        "column_threshold": 0.35,
    },
    "death": {
        "template": None,
        "threshold": 0.55,
        # Used when no template has been captured yet: the share of
        # saturated red pixels inside the death region.
        "heuristic": {"h": [[0, 10], [165, 180]], "s": [80, 255], "v": [60, 255],
                      "min_fraction": 0.015, "max_fraction": 0.30, "max_mean_v": 110},
        "confirm_frames": 2,
        "instant_score": 0.75,  # a template match this clear counts on one frame
        # The boss bar vanishing is the first sign of a death in Elden Ring, a
        # moment before YOU DIED is readable. Right after the bar goes, the
        # first faint trace of the banner is enough.
        "with_bar_score": 0.25,
        "bar_window_s": 1.5,
        "cooldown_s": 10.0,
    },
    "victory": None,
    "ocr": {"target_height": 56, "text_v_min": 150, "text_s_max": 80, "psm": 7,
            "min_score": 78, "interval_s": 1.0, "interval_matched_s": 5.0,
            "fast_retry_s": 4.0, "watch_interval_s": 0.4},
    "tracking": {
        "attribution_window_s": 15.0,
        "pre_death_window_s": 3.0,
        "disengage_s": 8.0,
        "bar_hide_frames": 2,  # missed frames in a row before the HUD hides
        "kill_threshold_pct": 3.0,
        # DEFEATED shows once two reads in a row are this low (only trail
        # left), and the kill is saved after the boss's bar and name have been
        # off screen this long. A YOU DIED within defeat_alive_s of the boss
        # last being seen means it survived on a sliver.
        "defeat_pct": 0.5,
        "defeat_confirm_s": 1.5,
        "defeat_alive_s": 0.75,
        "phase_low_pct": 15.0,
        # How long a boss emptied in an earlier phase may stay off screen (a
        # cutscene between phases) before the fight is given up.
        "phase_wait_s": 32.0,
        "phase_refill_pct": 80.0,
        "confirm_reads": 2,
        "instant_score": 92,  # a match this clear engages on the first read
        "accept_unlisted": False,
    },
    "bosses": [],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalize_name(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class BossMatch:
    boss: str  # canonical encounter name
    phase_hint: int | None  # set when the matched text is a phase-specific name
    score: float
    text: str


class Profile:
    def __init__(self, data: dict, path: Path | None = None):
        self.raw = data
        self.data = _deep_merge(DEFAULTS, data)
        self.path = path
        self._build_index()

    # -- basic accessors -------------------------------------------------
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def name(self) -> str:
        return self.data.get("name", self.id)

    @property
    def regions(self) -> dict:
        return self.data["regions"]

    @property
    def boss_slots(self) -> list[dict]:
        return self.data["boss_slots"]

    def boss_info(self, name: str) -> dict:
        for b in self.data["bosses"]:
            if b["name"] == name:
                return b
        return {"name": name}

    def max_phases(self, name: str) -> int | None:
        return self.boss_info(name).get("phases")

    def bar_count(self, name: str) -> int:
        return int(self.boss_info(name).get("bars", 1))

    def asset_path(self, rel: str | None) -> Path | None:
        if not rel:
            return None
        base = self.path.parent if self.path else Path(".")
        return base / rel

    # -- boss matching ---------------------------------------------------
    def _build_index(self):
        self._choices: dict[str, tuple[str, int | None]] = {}
        for b in self.data["bosses"]:
            canonical = b["name"]
            self._choices[normalize_name(canonical)] = (canonical, None)
            for alias in b.get("aliases", []):
                self._choices[normalize_name(alias)] = (canonical, None)
            for alias, phase in b.get("phase_names", {}).items():
                self._choices[normalize_name(alias)] = (canonical, int(phase))

    def match_boss(self, text: str) -> BossMatch | None:
        cleaned = normalize_name(text)
        if len(cleaned) < 3:
            return None
        min_score = self.data["ocr"]["min_score"]
        if self._choices and self.data["ocr"].get("prefix_match"):
            # The name sits at the left of its box, so scenery noise only ever
            # follows it. Score each choice against the best leading run of
            # words instead of letting WRatio find a partial match anywhere
            # in the noise, which turned "Deragcon whi oF ee" into
            # "Demon of Song" over Dark Souls II's bright floors.
            hit = self._prefix_match(cleaned)
            if hit and hit[1] >= min_score:
                canonical, phase = self._choices[hit[0]]
                return BossMatch(canonical, phase, hit[1], text)
        elif self._choices:
            hit = process.extractOne(cleaned, list(self._choices), scorer=fuzz.WRatio)
            # OCR often drops the space in a name ("AsylumDemon"), which costs
            # WRatio a lot once a little scenery noise follows it; compare
            # without spaces as well and keep the better match.
            squashed = {k.replace(" ", ""): k for k in self._choices}
            hit2 = process.extractOne(cleaned.replace(" ", ""), list(squashed), scorer=fuzz.WRatio)
            if hit2 and (not hit or hit2[1] > hit[1]):
                hit = (squashed[hit2[0]], hit2[1])
            if hit and hit[1] >= min_score:
                canonical, phase = self._choices[hit[0]]
                # WRatio is generous with short partial matches ("the" inside
                # a long name); require the lengths to be comparable as well.
                if len(cleaned) >= 0.5 * len(hit[0]):
                    return BossMatch(canonical, phase, hit[1], text)
        if self.data["tracking"]["accept_unlisted"] and len(cleaned) >= 4:
            return BossMatch(text.strip(), None, 0.0, text)
        return None

    def _prefix_match(self, cleaned: str) -> tuple[str, float] | None:
        squashed = {k.replace(" ", ""): k for k in self._choices}
        words = cleaned.split()
        best: tuple[str, float] | None = None
        for k in range(1, len(words) + 1):
            head = " ".join(words[:k])
            hits = [process.extractOne(head, list(self._choices), scorer=fuzz.ratio),
                    process.extractOne(head.replace(" ", ""), list(squashed), scorer=fuzz.ratio)]
            if hits[1]:
                hits[1] = (squashed[hits[1][0]], hits[1][1])
            for hit in hits:
                if hit and (best is None or hit[1] > best[1]):
                    best = (hit[0], hit[1])
        return best

    # -- persistence -----------------------------------------------------
    def to_json(self) -> dict:
        return self.raw

    def update(self, changes: dict):
        self.raw = _deep_merge(self.raw, changes)
        self.data = _deep_merge(DEFAULTS, self.raw)
        self._build_index()

    def save(self, path: Path | None = None):
        path = path or self.path
        if path is None:
            raise ValueError("profile has no path")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
        self.path = path


def load_profile(profiles_dir: Path, game_id: str) -> Profile:
    path = Path(profiles_dir) / f"{game_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no profile for '{game_id}' at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("id", game_id)
    return Profile(data, path)


# Game pickers list Elden Ring first, then the Dark Souls games in release order.
# A game whose preset hasn't been checked in game yet goes in WIP.
ORDER = ("elden_ring", "dark_souls_remastered", "dark_souls_2", "dark_souls_3")
WIP: set[str] = set()
# Shipped as a starting point for other games, but not offered in the game list.
HIDDEN = {"generic"}


def list_profiles(profiles_dir: Path) -> list[dict]:
    out = []
    for p in sorted(Path(profiles_dir).glob("*.json")):
        if p.name.startswith("."):  # .shipped.json, written by app.copy_profiles
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        gid = data.get("id", p.stem)
        if gid in HIDDEN:
            continue
        name = data.get("name", p.stem)
        out.append({"id": gid, "name": f"{name} (WiP)" if gid in WIP else name, "game": name, "wip": gid in WIP})
    # Then any other profiles in file order.
    out.sort(key=lambda g: ORDER.index(g["id"]) if g["id"] in ORDER else len(ORDER))
    return out
