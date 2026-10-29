import asyncio

from soulsoverlay import gamedetect
from soulsoverlay.service import Service
from test_server import AUTH, FakeCapture, with_client



def test_steam_app_ids_map_to_games():
    ids = {"elden_ring", "dark_souls_remastered", "dark_souls_2", "dark_souls_3"}
    assert gamedetect.detect(1245620, ids) == "elden_ring"
    assert gamedetect.detect(374320, ids) == "dark_souls_3"
    assert gamedetect.detect(236430, ids) == gamedetect.detect(335300, ids) == "dark_souls_2"
    assert gamedetect.detect(570940, ids) == "dark_souls_remastered"
    assert gamedetect.detect(730, ids) is None  # another Steam game
    assert gamedetect.detect(None, ids) is None
    assert gamedetect.detect(1245620, {"dark_souls_3"}) is None  # no profile for it


def test_reads_only_steams_running_app_id(monkeypatch):
    import types

    reads = []

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def open_key(root, path):
        reads.append(("open", root, path))
        return Key()

    def query(key, name):
        reads.append(("value", name))
        return 374320, 4

    fake = types.SimpleNamespace(HKEY_CURRENT_USER="HKCU", OpenKey=open_key, QueryValueEx=query)
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake)
    monkeypatch.setattr(gamedetect.sys, "platform", "win32")
    assert gamedetect.steam_running_app() == 374320
    assert reads == [("open", "HKCU", r"Software\Valve\Steam"), ("value", "RunningAppID")]

    fake.QueryValueEx = lambda key, name: (0, 4)  # Steam open, no game
    assert gamedetect.steam_running_app() is None

    def missing(*a):
        raise FileNotFoundError("no Steam")
    fake.OpenKey = missing
    assert gamedetect.steam_running_app() is None


def test_not_windows_means_no_game():
    if __import__("sys").platform != "win32":
        assert gamedetect.steam_running_app() is None


def run(coro):
    return asyncio.run(coro)


def test_switches_to_the_running_game(config):
    service = Service(config, capture=FakeCapture([]))
    events = []

    async def on_event(e):
        events.append(e)
    service.bus.subscribe(on_event)

    async def go():
        assert await service.on_game_detected("dark_souls_3")
    run(go())
    assert service.profile.id == "dark_souls_3"
    gd = service.state()["game_detect"]
    assert gd["running"]["id"] == "dark_souls_3" and not gd["offer"]
    assert gd["switched_from"]["id"] == "elden_ring"
    assert [(e.type, e.data) for e in events] == [("game_changed", {"game": "dark_souls_3", "auto": True})]
    # Same game still running: nothing new.
    assert not run(service.on_game_detected("dark_souls_3"))


def test_waits_for_the_fight_to_end(config):
    service = Service(config, capture=FakeCapture([]))
    service.tracker.encounter = object()
    run(service.on_game_detected("dark_souls_3"))
    assert service.profile.id == "elden_ring"
    service.tracker.encounter = None
    assert run(service.on_game_detected("dark_souls_3"))
    assert service.profile.id == "dark_souls_3"


def test_only_offers_when_auto_switch_is_off(config):
    config.game_detect.auto_switch = False
    service = Service(config, capture=FakeCapture([]))
    run(service.on_game_detected("dark_souls_3"))
    assert service.profile.id == "elden_ring"
    gd = service.state()["game_detect"]
    assert gd["offer"] and gd["running"]["name"] == "Dark Souls III"
    run(service.control("game_keep"))
    assert not service.state()["game_detect"]["offer"]


def test_picking_another_game_by_hand_sticks_while_that_game_runs(config):
    service = Service(config, capture=FakeCapture([]))

    async def go():
        await service.on_game_detected("dark_souls_3")
        await service.control("game_set", {"game": "elden_ring"})
        await service.on_game_detected("dark_souls_3")
        assert service.profile.id == "elden_ring"
        assert service.state()["game_detect"]["switched_from"] is None
        # The game closes, then a game starts again: switch as usual.
        await service.on_game_detected(None)
        await service.on_game_detected("dark_souls_3")
        assert service.profile.id == "dark_souls_3"
    run(go())


def test_characters_follow_the_game(config):
    service = Service(config, capture=FakeCapture([]))

    async def go():
        await service.control("game_set", {"game": "dark_souls_3"})
        ds3_char = (await service.control("character_add", {"name": "Ashen One"}))["id"]
        await service.control("game_set", {"game": "elden_ring"})
        await service.on_game_detected("dark_souls_3")
        active = next(c for c in service.state()["characters"] if c["active"])
        assert active["id"] == ds3_char
    run(go())


def test_check_game_asks_steam(config, monkeypatch):
    service = Service(config, capture=FakeCapture([]))
    monkeypatch.setattr(gamedetect, "steam_running_app", lambda: 570940)
    run(service.check_game())
    assert service.profile.id == "dark_souls_remastered"
    monkeypatch.setattr(gamedetect, "steam_running_app", lambda: None)
    run(service.check_game())
    assert service.profile.id == "dark_souls_remastered" and service.detected is None


def test_auto_switch_remembers_the_game(config, tmp_path):
    config.path = tmp_path / "config.toml"
    config.path.write_text('game = "elden_ring"\n\n[obs]\npassword = "x"\n')
    service = Service(config, capture=FakeCapture([]))
    run(service.on_game_detected("dark_souls_3"))
    assert 'game = "dark_souls_3"' in config.path.read_text()


def test_auto_switch_setting_is_saved(config, tmp_path):
    config.path = tmp_path / "config.toml"
    config.path.write_text('game = "elden_ring"\n\n[obs]\npassword = "x"\n')

    async def body(client, service):
        r = await client.post("/api/game_detect", json={"auto_switch": False}, headers=AUTH)
        assert r.status == 200 and (await r.json()) == {"auto_switch": False}
        assert service.config.game_detect.auto_switch is False
        assert (await client.post("/api/game_detect", json={"auto_switch": False})).status == 401
    with_client(config, body=body)
    text = config.path.read_text()
    assert "[game_detect]\nauto_switch = false" in text
    from soulsoverlay.config import load_config
    assert load_config(config.path).game_detect.auto_switch is False
