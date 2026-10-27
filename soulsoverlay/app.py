"""Running as the packed SoulsOverlay.exe (PyInstaller).

The exe unpacks itself to a temporary folder (sys._MEIPASS) on every start, so
anything the user changes (config.toml, data/, calibrated profiles) lives next
to the exe instead. Double-clicking it with no arguments opens the launcher
window, which also asks for the OBS details on the first start.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Read-only files packed into the exe (profiles, Tesseract, example config)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def app_dir() -> Path:
    """The folder holding SoulsOverlay.exe, where the user's own files go."""
    return Path(sys.executable).resolve().parent


def bundled_tesseract() -> Path | None:
    exe = bundle_dir() / "tesseract" / ("tesseract.exe" if os.name == "nt" else "tesseract")
    return exe if FROZEN and exe.exists() else None


# Every profile file shipped before v1.0.2, which started recording what it
# ships in .shipped.json. A file next to the exe that still matches one of
# these was never calibrated, so an update can replace it.
OLD_SHIPPED = {
    "dark_souls_2.json": "135690c10b41a90af2e487cf54ccb1e6b20fc78a19d43ac10f9cd7fdec667337",
    "dark_souls_3.json": "5aa1dcc07029c0691ca32ead2ddf0809d9a38262654954208aaaeef34ae246c3",
    "dark_souls_remastered.json": "ca1cb6018729665bb5be2c63c275b4ce76ef743e3bdef18631e6e97d5febc5f4",
    "elden_ring.json": "6ae4faee94fb8a61d16e8d473a2b2d6c5fe36c91486c608727e9f07d58737613",
    "generic.json": "2a8dfce990ff3388a1b8b6331112e641ed4cec9d4ccad1e1c73a25ec0f1bfff0",
    "templates/elden_ring_death.png": "7158ecf48ada382256ece781a5e202c96b9860cfde01eab8afc8c621b6abea36",
}


def _digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".json":  # a git checkout on Windows may have CRLF endings
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def copy_profiles(dest: Path):
    """Copy the packed game profiles next to the exe, never over the user's calibrated ones.

    A file the user hasn't changed since we shipped it is replaced when the
    packed one is newer, so fixes to a game's preset reach people on update.
    """
    src = bundle_dir() / "profiles"
    manifest_path = dest / ".shipped.json"
    try:
        shipped = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        shipped = {}
    for path in src.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(src).as_posix()
        target = dest / rel
        new = _digest(path)
        if target.exists():
            have = _digest(target)
            if have == new or have not in (shipped.get(rel), OLD_SHIPPED.get(rel)):
                if have == new:
                    shipped[rel] = new
                continue  # already up to date, or calibrated by the user
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        shipped[rel] = new
    if shipped:
        dest.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(shipped, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare(argv: list[str]) -> list[str]:
    """Set up the folder next to the exe and return the arguments to run with."""
    if not argv:
        argv = ["launcher"]
    if "--config" not in argv:
        argv = ["--config", str(app_dir() / "config.toml"), *argv]
    config = Path(argv[argv.index("--config") + 1])
    # Plugins named in config.toml can be .py files next to the exe.
    sys.path.insert(0, str(config.parent))
    copy_profiles(config.parent / "profiles")
    return argv


def attach_console(want: bool):
    """The exe has no terminal of its own. For commands typed in a terminal,
    print there; otherwise send output nowhere instead of crashing on it."""
    if sys.stdout is not None:  # a terminal or a pipe was handed to us
        return
    if want and os.name == "nt":
        import ctypes

        if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            sys.stdout = sys.stderr = open("CONOUT$", "w", buffering=1, encoding="utf-8")
            sys.stdin = open("CONIN$", encoding="utf-8")
            print()
            return
    sys.stdout = sys.stderr = open(os.devnull, "w")


def error_box(message: str):
    if os.name == "nt" and FROZEN:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "SoulsOverlay", 0x10)  # MB_ICONERROR
    else:
        print(message, file=sys.stderr)
