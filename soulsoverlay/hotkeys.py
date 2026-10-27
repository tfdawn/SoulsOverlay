"""Global hotkeys for manual corrections (optional, needs `pip install pynput`).

pynput listens to keyboard events system-wide but never sends any, so it
does not touch the game. If you'd rather not run a global listener, set
hotkeys.enabled = false and bind `soulsoverlay ctl ...` commands to a
Stream Deck or OBS instead.
"""

from __future__ import annotations

import asyncio
import logging

from .config import HotkeyConfig

log = logging.getLogger(__name__)


def start_hotkeys(cfg: HotkeyConfig, service, loop: asyncio.AbstractEventLoop):
    if not cfg.enabled:
        return None
    try:
        from pynput import keyboard
    except ImportError:
        log.warning("hotkeys disabled: install pynput (pip install pynput)")
        return None

    def fire(command: str):
        def handler():
            fut = asyncio.run_coroutine_threadsafe(service.control(command), loop)
            fut.add_done_callback(lambda f: f.exception() and log.error("hotkey %s failed: %s", command, f.exception()))
        return handler

    bindings = {
        cfg.death_add: fire("death_add"),
        cfg.death_undo: fire("death_undo"),
        cfg.boss_reset: fire("boss_reset"),
        cfg.boss_clear: fire("boss_clear"),
        cfg.snapshot: fire("snapshot"),
    }
    off = {getattr(cfg, a) for a in cfg.off if a in ACTIONS}
    bindings = {k: v for k, v in bindings.items() if k and k not in off}
    try:
        listener = keyboard.GlobalHotKeys(bindings)
    except ValueError as e:
        log.error("bad hotkey definition: %s", e)
        return None
    listener.daemon = True
    listener.start()
    log.info("hotkeys active: %s", ", ".join(k for k in bindings if k))
    return listener


ACTIONS = ("death_add", "death_undo", "boss_reset", "boss_clear", "snapshot")


def check(combo: str) -> str | None:
    """None if pynput accepts this hotkey, else why not."""
    try:
        from pynput import keyboard
    except ImportError:
        return None  # can't check, and hotkeys are off anyway
    try:
        keyboard.HotKey.parse(combo)
    except ValueError as e:
        return str(e) or "not a valid hotkey"
    return None
