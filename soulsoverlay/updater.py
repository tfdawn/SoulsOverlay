"""One-click updates for SoulsOverlay.exe from the GitHub Releases page.

On start the launcher asks GitHub for the latest release. If it is newer, the
window offers it; nothing is downloaded until the user clicks Update and
confirms. Then the new SoulsOverlay.exe is downloaded next to the running one,
checked against the release's SHA256SUMS.txt, and swapped in: Windows lets a
running exe be renamed, so the old one becomes SoulsOverlay.exe.old (deleted on
the next start), the new one takes its name, and it is started in place of
this one. config.toml, data/ and profiles/ are never touched.

The repository must be public: GitHub's API answers 404 for private ones.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

from . import __version__, app

log = logging.getLogger(__name__)


def fresh_env() -> dict:
    """Environment for starting the new exe as a program of its own.

    PyInstaller passes its unpack folder (_MEI...) to child processes, so the
    new exe would run out of this one's folder; when this one quits, it can't
    delete that folder ("Failed to remove temporary directory"). Ask the new
    exe to unpack its own copy instead.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("_PYI_") and k not in ("_MEIPASS2", "_PYI_ONEDIR_MODE")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env

REPO = "tfdawn/SoulsOverlay"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "SoulsOverlay.exe"
SUMS = "SHA256SUMS.txt"
# Downloads may only come from GitHub itself (release assets redirect to its storage host).
ALLOWED_PREFIXES = (f"https://github.com/{REPO}/releases/download/",)


def parse_version(text: str) -> tuple[int, ...]:
    m = re.match(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_newer(latest: str, current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    return bool(a) and a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _get(url: str, timeout: float = 15) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"SoulsOverlay/{__version__}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cleanup_old():
    """Remove the exe left behind by the last update."""
    if app.FROZEN:
        old = Path(sys.executable).with_name(ASSET + ".old")
        try:
            old.unlink(missing_ok=True)
        except OSError:  # still running for a moment; next start gets it
            pass


class Updater:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = "idle"  # idle | checking | available | latest | downloading | restarting | error
        self.latest: dict | None = None
        self.progress = 0.0
        self.error: str | None = None
        self.can_install = app.FROZEN and os.name == "nt"

    def status(self) -> dict:
        with self.lock:
            return {"state": self.state, "current": __version__, "latest": self.latest,
                    "progress": round(self.progress, 3), "error": self.error, "can_install": self.can_install}

    def _set(self, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)

    # -- check ------------------------------------------------------------
    def check(self):
        self._set(state="checking", error=None)
        try:
            release = json.loads(_get(API))
        except Exception as e:  # offline, private repo (404), rate limit...
            log.info("update check failed: %s", e)
            self._set(state="idle", error=None)
            return
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        tag = release.get("tag_name", "")
        info = {"version": tag.lstrip("v"), "url": release.get("html_url", ""),
                "exe": assets.get(ASSET), "sums": assets.get(SUMS)}
        newer = bool(is_newer(tag) and info["exe"] and info["sums"])
        self._set(latest=info, state="available" if newer else "latest")
        if newer:
            log.info("SoulsOverlay %s is available (running %s)", info["version"], __version__)

    # -- install ----------------------------------------------------------
    def download(self) -> Path:
        """Download and verify the new exe; returns its path next to the running one."""
        info = self.latest
        if not info or not self.can_install:
            raise RuntimeError("no update to install")
        for url in (info["exe"], info["sums"]):
            if not url.startswith(ALLOWED_PREFIXES):
                raise RuntimeError(f"refusing to download from {url}")
        self._set(state="downloading", progress=0.0, error=None)
        sums = _get(info["sums"]).decode("utf-8", "replace")
        expected = next((line.split()[0].lower() for line in sums.splitlines()
                         if line.strip().endswith(ASSET)), None)
        if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError("the release has no checksum for SoulsOverlay.exe")

        target = Path(sys.executable).with_name(ASSET + ".new")
        digest = hashlib.sha256()
        req = urllib.request.Request(info["exe"], headers={"User-Agent": f"SoulsOverlay/{__version__}"})
        with urllib.request.urlopen(req, timeout=30) as r, target.open("wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total:
                    self._set(progress=done / total)
        if digest.hexdigest() != expected:
            target.unlink(missing_ok=True)
            raise RuntimeError("the download didn't match its checksum, so it wasn't installed")
        return target

    def swap_and_restart(self, new: Path):
        """Put the new exe in place of the running one and start it."""
        current = Path(sys.executable)
        old = current.with_name(ASSET + ".old")
        old.unlink(missing_ok=True)
        current.rename(old)
        try:
            new.rename(current)
        except OSError:
            old.rename(current)  # put things back as they were
            raise
        self._set(state="restarting")
        subprocess.Popen([str(current), "launcher", "--after-update"], cwd=str(current.parent),
                         close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                         env=fresh_env())
