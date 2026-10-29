"""Which game is being played, from Steam.

While a game runs, Steam keeps its app id in one registry value,
HKEY_CURRENT_USER\\Software\\Valve\\Steam\\RunningAppID (0 when no game is
running). That one value is all this reads: not the list of programs, and
nothing of the game itself.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

# Steam app id -> profile id.
STEAM_APPS = {
    1245620: "elden_ring",
    570940: "dark_souls_remastered",
    335300: "dark_souls_2",  # Scholar of the First Sin
    236430: "dark_souls_2",
    374320: "dark_souls_3",
}


def steam_running_app() -> int | None:
    """The Steam app id of the game running now, or None (no game, no Steam, not Windows)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "RunningAppID")
        return int(value) or None
    except (OSError, ValueError, TypeError) as e:
        log.debug("couldn't read Steam's RunningAppID: %s", e)
        return None


def detect(app_id: int | None, profile_ids: set[str]) -> str | None:
    """The profile id for this Steam app id, if it's one of ours."""
    gid = STEAM_APPS.get(app_id) if app_id else None
    return gid if gid in profile_ids else None
