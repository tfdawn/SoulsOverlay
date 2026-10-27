import hashlib
import io
import json

import pytest

from soulsoverlay import updater


def test_version_compare():
    assert updater.is_newer("v1.1.0", "1.0.0")
    assert updater.is_newer("v1.0.1", "1.0")
    assert not updater.is_newer("v1.0.0", "1.0.0")
    assert not updater.is_newer("v0.9.9", "1.0.0")
    assert not updater.is_newer("nightly", "1.0.0")


def release(tag, exe=True):
    base = f"https://github.com/{updater.REPO}/releases/download/{tag}/"
    assets = [{"name": "SHA256SUMS.txt", "browser_download_url": base + "SHA256SUMS.txt"}]
    if exe:
        assets.append({"name": "SoulsOverlay.exe", "browser_download_url": base + "SoulsOverlay.exe"})
    return json.dumps({"tag_name": tag, "html_url": "https://github.com/x", "assets": assets}).encode()


def test_check_finds_newer_release(monkeypatch):
    up = updater.Updater()
    monkeypatch.setattr(updater, "_get", lambda url, timeout=15: release("v99.0.0"))
    up.check()
    assert up.state == "available" and up.latest["version"] == "99.0.0"
    monkeypatch.setattr(updater, "_get", lambda url, timeout=15: release("v0.0.1"))
    up.check()
    assert up.state == "latest"
    monkeypatch.setattr(updater, "_get", lambda url, timeout=15: release("v99.0.0", exe=False))
    up.check()
    assert up.state == "latest"  # a release without the exe isn't offered


def test_check_offline_stays_quiet(monkeypatch):
    def fail(url, timeout=15):
        raise OSError("HTTP Error 404: Not Found")  # e.g. a private repo
    monkeypatch.setattr(updater, "_get", fail)
    up = updater.Updater()
    up.check()
    assert up.state == "idle" and up.error is None


class FakeResponse(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


@pytest.mark.parametrize("good", [True, False])
def test_download_checks_the_checksum(monkeypatch, tmp_path, good):
    exe = b"MZ new exe" * 1000
    digest = hashlib.sha256(exe if good else b"something else").hexdigest()
    monkeypatch.setattr(updater.sys, "executable", str(tmp_path / "SoulsOverlay.exe"))
    monkeypatch.setattr(updater, "_get", lambda url, timeout=15: f"{digest}  SoulsOverlay.exe\n".encode())
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=30: FakeResponse(exe))
    up = updater.Updater()
    up.can_install = True
    base = f"https://github.com/{updater.REPO}/releases/download/v9.0.0/"
    up.latest = {"version": "9.0.0", "url": "", "exe": base + "SoulsOverlay.exe", "sums": base + "SHA256SUMS.txt"}
    if good:
        path = up.download()
        assert path.read_bytes() == exe and path.name == "SoulsOverlay.exe.new"
    else:
        with pytest.raises(RuntimeError, match="checksum"):
            up.download()
        assert not (tmp_path / "SoulsOverlay.exe.new").exists()


def test_download_only_from_github(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.sys, "executable", str(tmp_path / "SoulsOverlay.exe"))
    up = updater.Updater()
    up.can_install = True
    up.latest = {"version": "9", "url": "", "exe": "https://evil.example/SoulsOverlay.exe",
                 "sums": "https://evil.example/SHA256SUMS.txt"}
    with pytest.raises(RuntimeError, match="refusing"):
        up.download()


def test_swap_keeps_old_exe_aside(tmp_path, monkeypatch):
    current = tmp_path / "SoulsOverlay.exe"
    current.write_bytes(b"old")
    new = tmp_path / "SoulsOverlay.exe.new"
    new.write_bytes(b"new")
    started = []
    monkeypatch.setattr(updater.sys, "executable", str(current))
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.append(args))
    updater.Updater().swap_and_restart(new)
    assert current.read_bytes() == b"new" and (tmp_path / "SoulsOverlay.exe.old").read_bytes() == b"old"
    assert started[0][1:] == ["launcher", "--after-update"]
