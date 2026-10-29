"""Configuration loading.

Settings live in a TOML file (default: ./config.toml). Everything has a sane
default so the agent can start with only the OBS password filled in.

The control token is a secret and is *not* stored in config.toml: it is
generated on first run into <data_dir>/control_token and only ever sent in an
Authorization header, never in a URL that could end up on stream.
"""

from __future__ import annotations

import json
import re
import secrets
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ObsConfig:
    host: str = "127.0.0.1"
    port: int = 4455
    password: str = ""
    source: str = "Game Capture"
    # Screenshots are scaled down to this width before analysis. Regions are
    # stored as fractions of the frame, so this only trades accuracy for CPU.
    capture_width: int = 1280
    fps: float = 4.0
    fight_fps: float = 10.0  # while a boss bar is up, so deaths land sooner


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    # Extra Origins allowed to call the control API from a browser (e.g. a
    # Stream Deck web plugin). The calibration page on this server is always
    # allowed. Requests without an Origin header (CLI, scripts) are allowed if
    # they carry the token.
    allowed_origins: list[str] = field(default_factory=list)


@dataclass
class HotkeyConfig:
    enabled: bool = True
    death_add: str = "<ctrl>+<alt>+="
    death_undo: str = "<ctrl>+<alt>+-"
    boss_reset: str = "<ctrl>+<alt>+r"
    boss_clear: str = "<ctrl>+<alt>+c"
    snapshot: str = "<ctrl>+<alt>+s"
    # Actions switched off in the window; they keep their keys for when they're ticked again.
    off: list[str] = field(default_factory=list)


@dataclass
class GameDetectConfig:
    # Switch to the game that's running (its own characters and PBs). Off: the
    # window only offers to switch.
    auto_switch: bool = True


@dataclass
class Config:
    game: str = "elden_ring"
    data_dir: Path = Path("data")
    profiles_dir: Path = Path("profiles")
    obs: ObsConfig = field(default_factory=ObsConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    game_detect: GameDetectConfig = field(default_factory=GameDetectConfig)
    # Python modules with a `setup(bus, store, config)` function, loaded at
    # startup. This is where a chat bot bridge plugs in later.
    plugins: list[str] = field(default_factory=list)
    plugin_settings: dict = field(default_factory=dict)
    tesseract_cmd: str = ""
    # SoulsOverlay.exe: look for a newer release on GitHub when it starts.
    check_updates: bool = True
    # The file this was loaded from, so the launcher can save OBS details back.
    path: Path | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "soulsoverlay.sqlite3"

    @property
    def custom_css_path(self) -> Path:
        return self.data_dir / "overlay.css"

    @property
    def style_path(self) -> Path:
        return self.data_dir / "style.json"

    def control_token(self) -> str:
        path = self.data_dir / "control_token"
        if path.exists():
            token = path.read_text().strip()
            if token:
                return token
        self.data_dir.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        path.write_text(token + "\n")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return token


def _merge(dc, values: dict, section: str = ""):
    for key, value in values.items():
        if not hasattr(dc, key):
            where = f"in [{section}]" if section else "at the top of the file"
            raise ValueError(f"config.toml: unknown setting '{key}' {where}. Top-level settings"
                             " such as game or plugins must come before the first [section].")
        current = getattr(dc, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _merge(current, value, key)
        elif isinstance(current, Path):
            setattr(dc, key, Path(value))
        else:
            setattr(dc, key, value)


def load_config(path: str | Path | None) -> Config:
    cfg = Config()
    if path is not None:
        path = Path(path)
        cfg.path = path
        if path.exists():
            with path.open("rb") as f:
                _merge(cfg, tomllib.load(f))
            base = path.parent
            if not cfg.data_dir.is_absolute():
                cfg.data_dir = base / cfg.data_dir
            if not cfg.profiles_dir.is_absolute():
                cfg.profiles_dir = base / cfg.profiles_dir
    if cfg.server.host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            "server.host must be a loopback address; the overlay is never exposed to the network"
        )
    return cfg


def _toml_str(value: str) -> str:
    # JSON string escapes are valid TOML basic-string escapes.
    return json.dumps(value)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return _toml_str(str(value))


def save_section(path: Path, section: str, values: dict):
    """Write these keys into one [section] of config.toml, keeping everything else as it is."""
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:  # first save: start from the documented example
        from .app import bundle_dir

        example = bundle_dir() / "config.example.toml"
        text = example.read_text(encoding="utf-8") if example.exists() else ""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == f"[{section}]")
    except StopIteration:
        lines += ["", f"[{section}]"]
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    for key, value in values.items():
        new = f"{key} = {_toml_value(value)}"
        found = next((i for i in range(start + 1, end) if re.match(rf"\s*{key}\s*=", lines[i])), None)
        if found is None:
            lines.insert(end, new)
            end += 1
        else:
            lines[found] = new
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_top(path: Path, key: str, value):
    """Write one top-level setting (above the first [section]) into config.toml."""
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        from .app import bundle_dir

        example = bundle_dir() / "config.example.toml"
        text = example.read_text(encoding="utf-8") if example.exists() else ""
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    new = f"{key} = {_toml_value(value)}"
    found = next((i for i in range(first) if re.match(rf"\s*{key}\s*=", lines[i])), None)
    if found is None:
        lines.insert(first, new)
    else:
        lines[found] = new
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_obs(path: Path, password: str, source: str):
    """Write the OBS password and source name into config.toml."""
    save_section(path, "obs", {"password": password, "source": source})
