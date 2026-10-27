"""The overlay's look, as edited on the settings page.

SCHEMA lists every setting the page offers. The HUD and the settings
page both read it from /overlay/settings.json, so a setting is added here
once. Defaults are the values in hud.css, and only the
settings someone changed are saved, to <data_dir>/style.json. Deleting that
file (or "Reset all" on the page) brings back the default look.

data/overlay.css still loads after all of this and wins over it.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

TEXT, MUTED, ACCENT = "#e9e1cb", "#b8ad92", "#e3c16f"


HUD_FONT = '"Cinzel", "Trajan Pro", "Palatino Linotype", "Book Antiqua", Georgia, serif'
FONTS = [
    ('Georgia, serif', "Georgia"),
    ('"Palatino Linotype", "Book Antiqua", Palatino, serif', "Palatino"),
    ('"Times New Roman", Times, serif', "Times New Roman"),
    ('"Segoe UI", Arial, sans-serif', "Segoe UI"),
    ('Arial, Helvetica, sans-serif', "Arial"),
    ('"Trebuchet MS", sans-serif', "Trebuchet MS"),
    ('Impact, "Arial Black", sans-serif', "Impact"),
    ('Consolas, "Courier New", monospace', "Consolas"),
]
SHADOWS = [
    ("normal", "Normal", "0 0 2px #000, 0 1px 3px #000, 0 0 8px rgba(0, 0, 0, 0.8)"),
    ("strong", "Strong", "0 0 2px #000, 0 0 3px #000, 0 1px 4px #000, 0 0 12px #000"),
    ("soft", "Soft", "0 1px 3px rgba(0, 0, 0, 0.7)"),
    ("none", "None", "none"),
]


def _font(key, target, default):
    options = [{"value": default, "label": "Souls serif (default)"}]
    options += [{"value": v, "label": label} for v, label in FONTS]
    return {"key": key, "target": target, "group": "Text", "label": "Font", "type": "font",
            "var": "--font", "default": default, "options": options,
            "help": "Pick one, or type the name of any font installed on this PC."}


def _color(key, target, group, label, var, default, help=""):
    return {"key": key, "target": target, "group": group, "label": label, "type": "color",
            "var": var, "default": default, "help": help}


def _num(key, target, group, label, var, default, lo, hi, step, unit="", help=""):
    return {"key": key, "target": target, "group": group, "label": label, "type": "number",
            "var": var, "default": default, "min": lo, "max": hi, "step": step, "unit": unit,
            "help": help}


def _show(key, target, label, part, help=""):
    # Unticked adds hide-<part> to the overlay, like ?hide=<part> in the URL.
    return {"key": key, "target": target, "group": "Show", "label": label, "type": "bool",
            "default": True, "hide": part, "help": help}


def _flag(key, target, label, default, help=""):
    return {"key": key, "target": target, "group": "Show", "label": label, "type": "bool",
            "default": default, "help": help}


def _text(key, target, label, default, help=""):
    return {"key": key, "target": target, "group": "Labels", "label": label, "type": "text",
            "default": default, "maxlength": 40, "help": help}


# The custom NEW PB effect from the "HP Bar Lab", as its settings file has
# them (sizes in px for a bar 10px tall; fx.js scales them to the real bar).
# hp, barWidth, pb and speed only drive the Advanced tab's own preview, so the
# lab's files round-trip; the overlay ignores them. `area` is ours: how much
# of the game's bar the light spreads over.
FX_DEFAULTS = {
    "hp": 100, "barWidth": 860, "reach": 100, "direction": "center",
    "curveType": "bezier",
    "curve": [0.16, 1, 0.3, 1],
    "points": [[0, 0], [0.12, 0.7], [0.45, 0.95], [1, 1]],
    "interp": "smooth",
    "power": {"dir": "out", "exp": 5},
    "spring": {"stiffness": 220, "damping": 14},
    "steps": {"n": 6, "pos": "end"},
    "spread": 800, "hold": 450, "fade": 700, "fadeCurve": "in", "colorShift": 600, "soft": 6, "speed": 1,
    "fill": {"brightness": 1, "coreWidth": 40, "endFade": 8, "pulse": 0, "pulseRate": 2, "shimmer": 0, "shimmerSpeed": 1},
    "streak": {"on": True, "intensity": 1, "delay": 0, "open": 70, "dur": 420, "thickness": 4, "length": 100, "blur": 0},
    "flash": {"on": True, "intensity": 1, "delay": 0, "attack": 0, "dur": 320, "decay": "quad", "size": 110, "height": 55,
              "blur": 5, "growFrom": 0.7, "growTo": 1.3, "flicker": 0, "inset": 0},
    "glow": {"on": True, "intensity": 0.65, "height": 84, "blur": 8, "overscan": 0, "offsetY": 0},
    "waves": {"on": False, "intensity": 0.8, "size": 46, "trail": 0},
    "landing": {"on": False, "intensity": 0.6, "dur": 300},
    "sheen": {"on": False, "intensity": 0.8, "delay": 0, "dur": 500, "width": 8, "angle": 20},
    "particles": {"on": True, "mode": "front", "shape": "dot", "count": 50, "delay": 0, "life": 900, "speed": 70,
                  "rise": 60, "drag": 0, "jitter": 0.6, "size": 2, "sizeEnd": 0.5, "stretch": 1, "twinkle": 0.25,
                  "intensity": 0.9, "colorVar": 0, "seed": 7},
    "grain": {"on": False, "amount": 0.15, "blend": "overlay", "area": "effect", "size": 1, "fps": 24, "mono": True},
    "jolt": 0.3, "joltDur": 140, "shake": 0, "shakeDur": 250, "coreLine": 0.9, "pb": False,
    "pale": "#ffeabc", "warm": "#fa963c", "coreColor": "#fff0cd", "glowColor": "#ffcd82", "partColor": "#ffd08a",
    # The lab's preview stage only (the HUD ignores these).
    "bg": "dark", "showText": True,
    # Ours: in the game, how much of the bar the light covers.
    "area": "bar",
}
FX_CHOICES = {
    "direction": {"center", "ltr", "rtl", "edges"},
    "curveType": {"bezier", "points", "power", "spring", "steps", "linear"},
    "interp": {"smooth", "spline", "linear"},
    "power.dir": {"in", "out", "inout"},
    "steps.pos": {"start", "end"},
    "fadeCurve": {"in", "linear", "out", "smooth"},
    "flash.decay": {"fast", "quad", "linear", "slow", "smooth"},
    "particles.mode": {"front", "burst", "bar"},
    "particles.shape": {"dot", "spark"},
    "grain.blend": {"overlay", "soft-light", "screen", "normal"},
    "grain.area": {"effect", "full"},
    "bg": {"dark", "warm", "stone", "light", "black", "checker"},
    "area": {"bar", "health"},
}
FX_COLORS = {"partColor", "pale", "warm", "coreColor", "glowColor"}
# Limits: the lab's number boxes go past its sliders, so these are wider than
# the sliders, but still keep a hand-made file from making the overlay crawl
# (thousands of sparks, minute-long animations).
_MS = (0, 10000)
FX_RANGES = {
    "hp": (1, 100), "barWidth": (200, 4000), "speed": (0.05, 4),
    "reach": (5, 100), "spread": (50, 10000), "hold": _MS, "fade": (50, 10000),
    "colorShift": _MS, "soft": (0, 50), "jolt": (0, 3), "joltDur": (20, 3000), "shake": (0, 40),
    "shakeDur": (50, 5000), "coreLine": (0, 1),
    "power.exp": (1, 20), "spring.stiffness": (20, 2000), "spring.damping": (1, 200), "steps.n": (1, 60),
    "fill.brightness": (0, 4), "fill.coreWidth": (0, 100), "fill.endFade": (0, 50), "fill.pulse": (0, 1),
    "fill.pulseRate": (0, 30), "fill.shimmer": (0, 1), "fill.shimmerSpeed": (0, 20),
    "streak.intensity": (0, 3), "streak.delay": _MS, "streak.open": (0, 3000), "streak.dur": (10, 10000),
    "streak.thickness": (0.5, 60), "streak.length": (5, 200), "streak.blur": (0, 40),
    "flash.intensity": (0, 3), "flash.delay": _MS, "flash.attack": (0, 5000), "flash.dur": (10, 10000),
    "flash.size": (5, 2000), "flash.height": (5, 2000), "flash.blur": (0, 100), "flash.growFrom": (0, 10),
    "flash.growTo": (0, 10), "flash.flicker": (0, 1), "flash.inset": (-1000, 1000),
    "glow.intensity": (0, 3), "glow.height": (5, 1000), "glow.blur": (0, 100), "glow.overscan": (0, 1000),
    "glow.offsetY": (-200, 200),
    "waves.intensity": (0, 3), "waves.size": (5, 600), "waves.trail": (0, 2000),
    "landing.intensity": (0, 3), "landing.dur": (10, 5000),
    "sheen.intensity": (0, 3), "sheen.delay": (-10000, 10000), "sheen.dur": (50, 10000), "sheen.width": (1, 100),
    "sheen.angle": (-89, 89),
    "particles.count": (0, 600), "particles.delay": _MS, "particles.life": (50, 10000), "particles.speed": (0, 2000),
    "particles.rise": (-2000, 2000), "particles.drag": (0, 50), "particles.jitter": (0, 2), "particles.size": (0.1, 20),
    "particles.sizeEnd": (0, 5), "particles.stretch": (0, 20), "particles.twinkle": (0, 1),
    "particles.intensity": (0, 3), "particles.colorVar": (0, 1), "particles.seed": (1, 100000),
    "grain.amount": (0, 1), "grain.size": (1, 8), "grain.fps": (0, 60),
}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e6


def check_fx(value) -> dict:
    """The lab's settings merged over the defaults: unknown keys are ignored
    (so the lab's own file loads as it is), wrong types are errors."""
    if not isinstance(value, dict):
        raise ValueError("hud.fx: must be an object")

    def merge(base: dict, src: dict, prefix: str) -> dict:
        out = {}
        for k, default in base.items():
            path = prefix + k
            v = src.get(k, default)
            if isinstance(default, dict):
                if not isinstance(v, dict):
                    raise ValueError(f"hud.fx.{path}: must be an object")
                out[k] = merge(default, v, path + ".")
            elif k == "curve":
                if not (isinstance(v, list) and len(v) == 4 and all(_is_num(n) for n in v)):
                    raise ValueError("hud.fx.curve: must be 4 numbers")
                out[k] = [min(1, max(0, v[0])), min(1.5, max(-0.5, v[1])),
                          min(1, max(0, v[2])), min(1.5, max(-0.5, v[3]))]
            elif k == "points":
                if not (isinstance(v, list) and 2 <= len(v) <= 32 and all(
                        isinstance(p, list) and len(p) == 2 and all(_is_num(n) for n in p) for p in v)):
                    raise ValueError("hud.fx.points: must be 2 to 32 [x, y] pairs")
                out[k] = [[min(1, max(0, x)), min(1.5, max(-0.5, y))] for x, y in v]
            elif isinstance(default, bool):
                if not isinstance(v, bool):
                    raise ValueError(f"hud.fx.{path}: must be true or false")
                out[k] = v
            elif isinstance(default, (int, float)):
                if not _is_num(v):
                    raise ValueError(f"hud.fx.{path}: not a number")
                lo, hi = FX_RANGES.get(path, (-1e5, 1e5))
                out[k] = min(hi, max(lo, v))
            elif k in FX_COLORS:
                if not (isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)):
                    raise ValueError(f"hud.fx.{path}: colours are #rrggbb")
                out[k] = v
            else:
                if v not in FX_CHOICES[path]:
                    raise ValueError(f"hud.fx.{path}: must be one of {sorted(FX_CHOICES[path])}")
                out[k] = v
        return out

    return merge(FX_DEFAULTS, value, "")


SCHEMA = [
    # -- HUD on the game's boss bar ---------------------------------------
    _font("hud.font", "hud", HUD_FONT),
    _num("hud.size", "hud", "Text", "Text size", "--size", 1.75, 0.8, 4, 0.05, "vh",
         "Relative to the screen height."),
    # One colour per part of the HUD.
    _color("hud.deaths_label_color", "hud", "Colours", "DEATHS word", "--deaths-label", MUTED),
    _color("hud.deaths_color", "hud", "Colours", "Death count", "--deaths", TEXT),
    _color("hud.danger", "hud", "Colours", "Death count flash", "--danger", "#d0453c",
           "The death count flashes this colour when it goes up."),
    _color("hud.pb_label_color", "hud", "Colours", "PB word", "--pb-label", MUTED),
    _color("hud.pb_color", "hud", "Colours", "PB %", "--pb", ACCENT),
    _color("hud.mark_color", "hud", "Colours", "PB marker on the bar", "--mark", ACCENT),
    _color("hud.phase_color", "hud", "Colours", "Phase", "--phase", MUTED, "\"Phase 1/2\" on two-phase bosses."),
    _color("hud.new_pb_color", "hud", "Colours", "NEW PB", "--new-pb", ACCENT),
    _color("hud.defeated_color", "hud", "Colours", "DEFEATED", "--defeated", ACCENT),
    _color("hud.callout_sub_color", "hud", "Colours", "Line under NEW PB / DEFEATED", "--callout-sub", ACCENT,
           "The new PB %, or \"after N deaths\"."),
    {"key": "hud.shadow", "target": "hud", "group": "Text", "label": "Text outline", "type": "enum",
     "var": "--shadow", "default": "normal",
     "options": [{"value": v, "label": label, "css": css} for v, label, css in SHADOWS]},
    _num("hud.gap", "hud", "Layout", "Space under the bar", "--gap", 0.55, 0, 6, 0.05, "vh"),
    _num("hud.mark_width", "hud", "Layout", "PB marker width", "--mark-width", 0.16, 0.08, 0.6, 0.02,
         "vh"),
    _num("hud.glow_time", "hud", "NEW PB glow", "Length", "--shine-time", 3.2, 1, 8, 0.1, "s",
         "It spreads out for the first 37% of this, holds, then fades."),
    _num("hud.aura_size", "hud", "NEW PB glow", "Aura height", "--aura-size", 6, 1, 14, 0.5, "",
         "In bar heights."),
    _num("hud.aura_blur", "hud", "NEW PB glow", "Aura softness", "--aura-blur", 0.45, 0, 2, 0.05, "vh"),
    _color("hud.shine_core", "hud", "NEW PB glow", "Flare centre", "--shine-core",
           "rgba(255, 244, 205, 0.95)"),
    _color("hud.shine", "hud", "NEW PB glow", "Flare", "--shine", "rgba(255, 196, 100, 0.8)"),
    _color("hud.shine_edge", "hud", "NEW PB glow", "Flare edge", "--shine-edge",
           "rgba(240, 120, 40, 0.5)"),
    _color("hud.shine_tail", "hud", "NEW PB glow", "Flare fade-out", "--shine-tail",
           "rgba(200, 60, 20, 0.2)"),
    _color("hud.aura_core", "hud", "NEW PB glow", "Aura centre", "--aura-core",
           "rgba(255, 230, 170, 0.95)"),
    _color("hud.aura", "hud", "NEW PB glow", "Aura", "--aura", "rgba(255, 175, 80, 0.75)"),
    _color("hud.aura_edge", "hud", "NEW PB glow", "Aura edge", "--aura-edge", "rgba(240, 110, 35, 0.35)"),
    {"key": "hud.fx", "target": "adv", "group": "Advanced", "type": "fx",
     "label": "Effect", "default": FX_DEFAULTS},
    _text("hud.label_deaths", "hud", "Deaths", "Deaths",
          "Under the bar, on the left: how many times you've died to this boss."),
    _text("hud.label_pb", "hud", "PB", "PB",
          "Under the bar, on the right: the lowest health % you've got this boss to."),
    _text("hud.label_new_pb", "hud", "New PB callout", "NEW PB",
          "Pops up under the bar, with the glow, the moment the boss's health drops below your PB."),
    _text("hud.label_defeated", "hud", "Defeated callout", "DEFEATED",
          "Pops up the first time you beat a boss, with \"after N deaths\" under it."),
    _show("hud.show_deaths", "hud", "Deaths", "deaths", "Your death count for this boss, under the bar."),
    _show("hud.show_pb", "hud", "PB", "pb", "Your best health % for this boss, under the bar."),
    _show("hud.show_phase", "hud", "Phase", "phase",
          "\"Phase 1/2\" under the bar, for bosses with more than one phase."),
    _show("hud.show_mark", "hud", "PB marker on the bar", "mark",
          "The gold line on the boss's health bar where your PB is."),
    _flag("hud.callouts", "hud", "New PB and Defeated callouts", True,
          "The big text under the bar when you beat your PB or the boss. The glow plays either way."),
    _flag("hud.always", "hud", "Stay visible between fights", False,
          "Off: the HUD only shows while the game's boss bar is on screen."),
    _num("hud.linger", "hud", "Timing", "Stay after the bar goes", "--linger", 0, 0, 10, 0.5, "s"),
    _num("hud.death_hold", "hud", "Timing", "Stay to show a new death", "--death-hold", 0, 0, 10, 0.5,
         "s"),
]
BY_KEY = {f["key"]: f for f in SCHEMA}

_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_NUM = r"\s*\d{1,3}(?:\.\d+)?\s*"
_RGB = re.compile(rf"rgba?\({_NUM},{_NUM},{_NUM}(?:,\s*(?:0|1|0?\.\d+|1\.0+)\s*)?\)")
# Font names end up in a CSS value, so only plain names, commas and quotes.
_FONT = re.compile(r"[A-Za-z0-9 ,'\"\-]{1,200}")


def check(key: str, value):
    """The value, cleaned up, or ValueError saying what's wrong with it."""
    f = BY_KEY.get(key)
    if f is None:
        raise ValueError(f"unknown setting {key!r}")
    kind = f["type"]
    if kind == "color":
        if isinstance(value, str) and (_HEX.fullmatch(value.strip()) or _RGB.fullmatch(value.strip())):
            return value.strip()
        raise ValueError(f"{key}: not a colour: {value!r}")
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key}: not a number")
        if not f["min"] <= value <= f["max"]:
            raise ValueError(f"{key}: must be between {f['min']} and {f['max']}")
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{key}: must be true or false")
        return value
    if kind == "enum":
        if value not in [o["value"] for o in f["options"]]:
            raise ValueError(f"{key}: must be one of {[o['value'] for o in f['options']]}")
        return value
    if kind == "font":
        if isinstance(value, str) and _FONT.fullmatch(value.strip()):
            return value.strip()
        raise ValueError(f"{key}: font names may only use letters, digits, spaces, commas and quotes")
    if kind == "fx":
        return check_fx(value)
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError(f"{key}: not text")
        value = "".join(ch for ch in value if ch.isprintable())
        if len(value) > f["maxlength"]:
            raise ValueError(f"{key}: at most {f['maxlength']} characters")
        return value
    raise ValueError(f"{key}: unsupported type {kind}")


def validate(values: dict) -> dict:
    """Checks every value; drops the ones equal to the default."""
    if not isinstance(values, dict):
        raise ValueError("values must be an object")
    out = {}
    for key, value in values.items():
        value = check(key, value)
        if value != BY_KEY[key]["default"]:
            out[key] = value
    return out


def load(path: Path) -> dict:
    """The saved settings. A bad entry (hand edits, an older version) is
    skipped with a warning, so it can't break the overlay."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        values = data.get("values", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        log.warning("ignoring %s: %s", path, e)
        return {}
    out = {}
    for key, value in values.items() if isinstance(values, dict) else ():
        try:
            out[key] = check(key, value)
        except ValueError as e:
            log.warning("%s: skipping %s", path.name, e)
    return out


def save(path: Path, values: dict) -> dict:
    values = validate(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "values": values}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return values
