import asyncio
import json
import shutil
import socket

import cv2
import pytest
from aiohttp.test_utils import TestClient, TestServer

from soulsoverlay.server import OverlayServer
from soulsoverlay.service import Service
from synth import make_frame

TOKEN = "test-token-123"


class FakeCapture:
    def __init__(self, frames):
        self.frames = list(frames)

    def grab(self):
        if not self.frames:
            raise RuntimeError("no more frames")
        return self.frames.pop(0)

    def close(self):
        pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def with_client(config, frames=(), body=None):
    async def runner():
        config.server.port = free_port()
        service = Service(config, capture=FakeCapture(frames))
        server = OverlayServer(service, TOKEN)
        client = TestClient(TestServer(server.app(), host="127.0.0.1", port=config.server.port))
        await client.start_server()
        try:
            return await body(client, service)
        finally:
            await client.close()

    return asyncio.run(runner())


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_hud_is_public_and_control_needs_token(config):
    async def body(client, service):
        assert (await client.get("/overlay")).status == 404
        assert (await client.get("/overlay/hud")).status == 200
        state = await (await client.get("/api/state")).json()
        assert len(state["layout"]["bar"]) == 4
        assert (await client.get("/api/state")).status == 200
        r = await client.post("/api/control", json={"command": "death_add"})
        assert r.status == 401
        r = await client.post("/api/control", json={"command": "death_add"},
                              headers={"Authorization": "Bearer nope"})
        assert r.status == 401
        r = await client.post("/api/control", json={"command": "death_add"}, headers=AUTH)
        assert r.status == 200
        state = await (await client.get("/api/state")).json()
        assert state["game"]["deaths"] == 1
        assert (await client.get("/api/calibrate/profile")).status == 401

    with_client(config, body=body)


def test_origin_host_and_content_type_checks(config):
    async def body(client, service):
        r = await client.post("/api/control", json={"command": "death_add"},
                              headers={**AUTH, "Origin": "https://evil.example"})
        assert r.status == 403
        r = await client.get("/api/state", headers={"Host": "evil.example:8765"})
        assert r.status == 421
        r = await client.post("/api/control", data="command=death_add",
                              headers={**AUTH, "Content-Type": "application/x-www-form-urlencoded"})
        assert r.status == 415
        origin = f"http://127.0.0.1:{service.config.server.port}"
        r = await client.post("/api/control", json={"command": "death_add"}, headers={**AUTH, "Origin": origin})
        assert r.status == 200
        # no CORS headers, ever
        assert "Access-Control-Allow-Origin" not in r.headers

    with_client(config, body=body)


def test_overlay_websocket_gets_state_and_events(config):
    async def body(client, service):
        ws = await client.ws_connect("/overlay/ws")
        first = await ws.receive_json(timeout=2)
        assert first["kind"] == "state"
        await client.post("/api/control", json={"command": "boss_set", "args": {"boss": "margit"}}, headers=AUTH)
        await client.post("/api/control", json={"command": "death_add"}, headers=AUTH)
        seen = []
        while not any(m.get("event", {}).get("type") == "death" for m in seen):
            seen.append(await ws.receive_json(timeout=2))
        death = [m for m in seen if m.get("event", {}).get("type") == "death"][0]["event"]
        assert death["boss"] == "Margit, the Fell Omen" and death["source"] == "manual"
        # read-only: sending something does nothing harmful
        await ws.send_str(json.dumps({"command": "death_add"}))
        await asyncio.sleep(0.1)
        assert service.store.game_stats("elden_ring")["deaths"] == 1
        await ws.close()

    with_client(config, body=body)


def test_calibration_upload_save_and_template(config):
    async def body(client, service):
        shot = make_frame(service.profile, death=True, bosses=[("Margit, the Fell Omen", 30)])
        ok, buf = cv2.imencode(".png", shot)
        r = await client.post("/api/calibrate/upload", data=buf.tobytes(),
                              headers={**AUTH, "Content-Type": "image/png"})
        assert r.status == 200 and service.paused
        r = await client.post("/api/calibrate/profile", json={"regions": {"death": [0.2, 0.4, 0.6, 0.2]}},
                              headers=AUTH)
        assert r.status == 200
        assert service.profile.regions["death"] == [0.2, 0.4, 0.6, 0.2]
        r = await client.post("/api/calibrate/profile", json={"regions": {"death": [0.2, 0.4, 2, 0.2]}},
                              headers=AUTH)
        assert r.status == 400
        r = await client.post("/api/calibrate/template", json={"kind": "death"}, headers=AUTH)
        assert r.status == 200
        assert service.analyzer.death.mode == "template"
        diag = await (await client.post("/api/calibrate/diagnose", json={}, headers=AUTH)).json()
        assert diag["death"] is True
        assert diag["slots"][0]["pct"] == pytest.approx(30, abs=1)

    with_client(config, body=body)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_end_to_end_capture_loop(config):
    """Two attempts at Margit from synthetic frames: deaths, attribution, new PB."""
    from soulsoverlay.profiles import load_profile

    p = load_profile(config.profiles_dir, "elden_ring")
    margit = "Margit, the Fell Omen"

    def attempt(start, end, seed):
        frames = [make_frame(p, bosses=[(margit, pct)], seed=seed) for pct in range(start, end - 1, -8)]
        frames += [make_frame(p, bosses=[(margit, end)], death=True, seed=seed)]
        frames += [make_frame(p, death=True, seed=seed)] * 2
        frames += [make_frame(p, seed=seed)] * 2
        return frames

    frames = attempt(100, 60, 1) + attempt(100, 36, 2)
    config.obs.fps = 50
    p.data["death"]["cooldown_s"] = 0.0

    async def body(client, service):
        service.profile.data["death"]["cooldown_s"] = 0.0
        ws = await client.ws_connect("/overlay/ws")
        task = asyncio.create_task(service.run())
        events = []
        try:
            while len([e for e in events if e["type"] == "death"]) < 2:
                msg = await ws.receive_json(timeout=20)
                if msg["kind"] == "event":
                    events.append(msg["event"])
            # new_pb follows its death event; drain what's left of the burst
            while True:
                try:
                    msg = await ws.receive_json(timeout=0.5)
                except asyncio.TimeoutError:
                    break
                if msg["kind"] == "event":
                    events.append(msg["event"])
        finally:
            task.cancel()
        deaths = [e for e in events if e["type"] == "death"]
        assert [d["boss"] for d in deaths] == [margit, margit]
        assert deaths[0]["pct"] == pytest.approx(60, abs=2)
        assert deaths[1]["pct"] == pytest.approx(36, abs=2)
        new_pb = [e for e in events if e["type"] == "new_pb"]
        assert len(new_pb) == 1 and new_pb[0]["pct"] == pytest.approx(36, abs=2)
        st = service.state()
        assert st["boss"]["name"] == margit and st["boss"]["deaths"] == 2

    with_client(config, frames=frames, body=body)


def test_snapshot_and_black_frame_warning(config, caplog):
    import numpy as np

    from soulsoverlay.profiles import load_profile

    p = load_profile(config.profiles_dir, "elden_ring")
    frames = [np.zeros((720, 1280, 3), np.uint8)] * 3 + [make_frame(p, bosses=[("Margit, the Fell Omen", 40)])] * 5
    config.obs.fps = 50

    async def body(client, service):
        task = asyncio.create_task(service.run())
        try:
            for _ in range(100):
                await asyncio.sleep(0.02)
                if service.status.get("picture") == "ok":
                    break
        finally:
            task.cancel()
        r = await client.post("/api/control", json={"command": "snapshot"}, headers=AUTH)
        body = await r.json()
        assert r.status == 200 and body["slots"][0]["pct"] == pytest.approx(40, abs=1)
        assert Path(body["path"]).exists()

    from pathlib import Path
    with caplog.at_level("INFO"):
        with_client(config, frames=frames, body=body)
    text = caplog.text
    assert text.count("black picture") == 1 and "picture from OBS is back" in text


def test_launcher_start_stop_and_obs_details(config, tmp_path):
    config.path = tmp_path / "config.toml"
    config.obs.password = "old"

    async def body(client, service):
        assert (await client.get("/launcher")).status == 200
        assert (await client.get("/api/launcher")).status == 401
        info = await (await client.get("/api/launcher", headers=AUTH)).json()
        assert info["setup_needed"] and info["obs"]["password_set"] and not info["stopped"]
        assert "password" not in json.dumps(info["obs"]).replace("password_set", "")

        r = await client.post("/api/control", json={"command": "stop"}, headers=AUTH)
        assert r.status == 200 and service.stopped
        assert (await (await client.get("/api/state")).json())["status"]["capture"] == "stopped"
        await client.post("/api/control", json={"command": "start"}, headers=AUTH)
        assert not service.stopped

        r = await client.post("/api/launcher/obs", json={"password": "", "source": ""}, headers=AUTH)
        assert r.status == 400
        # An empty password keeps the saved one.
        r = await client.post("/api/launcher/obs", json={"password": "", "source": "Game"}, headers=AUTH)
        assert r.status == 200 and config.obs.password == "old" and config.obs.source == "Game"
        r = await client.post("/api/launcher/obs", json={"password": "new", "source": "Game"}, headers=AUTH)
        info = await (await client.get("/api/launcher", headers=AUTH)).json()
        assert not info["setup_needed"] and config.obs.password == "new"
        assert 'password = "new"' in config.path.read_text()

    with_client(config, body=body)


def test_update_endpoints_need_the_launcher(config):
    async def body(client, service):
        assert (await client.get("/api/update")).status == 401
        assert (await (await client.get("/api/update", headers=AUTH)).json())["state"] == "unsupported"
        assert (await client.post("/api/update/install", json={}, headers=AUTH)).status == 409

    with_client(config, body=body)


def test_hotkeys_saved_to_config(config, tmp_path):
    config.path = tmp_path / "config.toml"

    async def body(client, service):
        data = await (await client.get("/api/hotkeys", headers=AUTH)).json()
        assert data["keys"]["death_add"] == "<ctrl>+<alt>+="
        keys = {**data["keys"], "death_add": "<ctrl>+<shift>+d", "boss_clear": ""}
        r = await client.post("/api/hotkeys", json={"enabled": False, "keys": keys}, headers=AUTH)
        assert r.status == 200
        assert config.hotkeys.death_add == "<ctrl>+<shift>+d" and not config.hotkeys.enabled
        text = config.path.read_text()
        assert 'death_add = "<ctrl>+<shift>+d"' in text and "enabled = false" in text
        same = {**keys, "death_undo": "<ctrl>+<shift>+d"}
        r = await client.post("/api/hotkeys", json={"enabled": False, "keys": same}, headers=AUTH)
        assert r.status == 400
        # an action that's switched off keeps its keys and may share them
        r = await client.post("/api/hotkeys", json={"enabled": True, "keys": same, "off": ["death_undo", "nope"]},
                              headers=AUTH)
        assert r.status == 200 and (await r.json())["off"] == ["death_undo"]
        assert config.hotkeys.off == ["death_undo"] and config.hotkeys.death_undo == "<ctrl>+<shift>+d"
        assert 'off = ["death_undo"]' in config.path.read_text()
        from soulsoverlay.config import load_config
        assert load_config(config.path).hotkeys.off == ["death_undo"]

    with_client(config, body=body)
