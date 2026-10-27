"""Running as the packed SoulsOverlay.exe (PyInstaller).

The exe unpacks itself to a temporary folder (sys._MEIPASS) on every start, so
anything the user changes (config.toml, data/, calibrated profiles) lives next
to the exe instead. Double-clicking it with no arguments opens the launcher
window, which also asks for the OBS details on the first start.
"""

from __future__ import annotations

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


def copy_profiles(dest: Path):
    """Copy the packed game profiles next to the exe, never over the user's calibrated ones."""
    src = bundle_dir() / "profiles"
    for path in src.rglob("*"):
        target = dest / path.relative_to(src)
        if path.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


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
