import json

import pytest
from soulsoverlay.store import Store, pb_better


def test_pb_ordering():
    assert pb_better({"phase": 2, "pct": 90}, {"phase": 1, "pct": 1})
    assert pb_better({"phase": 1, "pct": 10}, {"phase": 1, "pct": 20})
    assert not pb_better({"phase": 1, "pct": 20}, {"phase": 1, "pct": 10})
    assert pb_better({"phase": 1, "pct": 0, "killed": True}, {"phase": 3, "pct": 1})


def test_deaths_pb_undo_reset():
    s = Store(":memory:")
    g, b = "elden_ring", "Malenia, Blade of Miquella"
    first = s.record_death(g, b, 1, 60.0)
    assert not first["new_pb"]  # nothing to beat yet
    assert s.record_death(g, b, 1, 40.0)["new_pb"]
    assert not s.record_death(g, b, 1, 55.0)["new_pb"]
    assert s.record_death(g, b, 2, 95.0)["new_pb"]
    s.record_death(g, None)
    st = s.boss_stats(g, b)
    assert st["deaths"] == 4
    assert st["pb"] == {"phase": 2, "pct": 95.0, "killed": False}
    assert st["phase_pbs"] == {1: 40.0, 2: 95.0}
    assert s.game_stats(g)["deaths"] == 5

    assert s.undo_last_death(g)["boss"] is None
    assert s.undo_last_death(g)["pct"] == 95.0
    assert s.boss_stats(g, b)["pb"]["phase"] == 1

    k = s.record_kill(g, b, 2)
    assert k["first_kill"]
    assert s.boss_stats(g, b)["killed"]
    assert not s.record_kill(g, b, 2)["first_kill"]

    assert s.reset_boss(g, b) == 3
    st = s.boss_stats(g, b)
    assert st["deaths"] == 0 and st["pb"] is None and not st["killed"]


def test_manual_death_without_pct_never_pb():
    s = Store(":memory:")
    s.record_death("g", "Boss", 1, 50.0)
    assert not s.record_death("g", "Boss", 1, None, "manual")["new_pb"]
    assert s.boss_stats("g", "Boss")["deaths"] == 2


def test_example_config_loads():
    from pathlib import Path

    from soulsoverlay.config import load_config

    cfg = load_config(Path(__file__).resolve().parents[1] / "config.example.toml")
    assert cfg.plugins == [] and cfg.obs.port == 4455 and cfg.hotkeys.enabled


def test_save_obs_keeps_the_rest_of_config(tmp_path):
    from soulsoverlay.config import load_config, save_obs

    path = tmp_path / "config.toml"
    save_obs(path, 'pa"ss\\word', "Game 'Capture'")  # first save starts from the example
    cfg = load_config(path)
    assert cfg.obs.password == 'pa"ss\\word' and cfg.obs.source == "Game 'Capture'" and cfg.obs.fps == 4.0
    path.write_text('game = "dark_souls_3"\n[obs]\nport = 4456\n# keep me\n[server]\nport = 9000\n')
    save_obs(path, "pw", "Game")
    cfg = load_config(path)
    assert (cfg.game, cfg.obs.port, cfg.obs.password, cfg.obs.source, cfg.server.port) == (
        "dark_souls_3", 4456, "pw", "Game", 9000)
    assert "# keep me" in path.read_text()


def test_copy_profiles_keeps_calibrated_ones(tmp_path):
    from soulsoverlay import app

    (tmp_path / "elden_ring.json").write_text("calibrated")
    app.copy_profiles(tmp_path)
    assert (tmp_path / "elden_ring.json").read_text() == "calibrated"
    assert (tmp_path / "dark_souls_3.json").exists() and (tmp_path / "templates" / "elden_ring_death.png").exists()


def test_copy_profiles_updates_untouched_ones(tmp_path):
    from soulsoverlay import app
    from soulsoverlay.profiles import list_profiles

    src = app.bundle_dir() / "profiles"
    # As left by v1.0.1: the old DSR preset, never calibrated, and no manifest.
    old = tmp_path / "dark_souls_remastered.json"
    old.write_text("old preset")
    app.OLD_SHIPPED["dark_souls_remastered.json"] = app._digest(old)
    try:
        app.copy_profiles(tmp_path)
    finally:
        del app.OLD_SHIPPED["dark_souls_remastered.json"]
    assert old.read_bytes() == (src / "dark_souls_remastered.json").read_bytes()

    # A later update replaces what we shipped, but not what the user calibrated.
    old.write_text("shipped in 1.0.2")
    (tmp_path / "elden_ring.json").write_text("calibrated")
    manifest = tmp_path / ".shipped.json"
    data = json.loads(manifest.read_text())
    data["dark_souls_remastered.json"] = app._digest(old)
    manifest.write_text(json.dumps(data))
    app.copy_profiles(tmp_path)
    assert old.read_bytes() == (src / "dark_souls_remastered.json").read_bytes()
    assert (tmp_path / "elden_ring.json").read_text() == "calibrated"
    assert ".shipped" not in {g["id"] for g in list_profiles(tmp_path)}


def test_game_list_puts_elden_ring_first():
    from pathlib import Path

    from soulsoverlay.profiles import list_profiles

    games = list_profiles(Path(__file__).resolve().parents[1] / "profiles")
    assert [g["id"] for g in games] == ["elden_ring", "dark_souls_remastered", "dark_souls_2", "dark_souls_3"]
    names = {g["id"]: g["name"] for g in games}
    assert names["dark_souls_3"] == "Dark Souls III" and not any(g["wip"] for g in games)


def test_characters_keep_separate_stats(tmp_path):
    from soulsoverlay.store import Store
    s = Store(tmp_path / "db.sqlite3")
    s.ensure_game("elden_ring", "Elden Ring")
    first = s.character("elden_ring")
    assert first["name"] == "Tarnished"
    s.record_death("elden_ring", "Margit", 1, 40.0)
    s.record_death("elden_ring", "Margit", 1, 20.0)
    second = s.add_character("elden_ring", "  Strength   build ")
    assert s.character("elden_ring") == {"id": second, "name": "Strength build", "deaths": 0, "active": True}
    assert s.boss_stats("elden_ring", "Margit")["deaths"] == 0 and s.pb("elden_ring", "Margit") is None
    s.record_death("elden_ring", "Margit", 1, 70.0)
    assert s.undo_last_death("elden_ring")["pct"] == 70.0
    assert s.undo_last_death("elden_ring") is None  # never reaches the other character's deaths
    s.select_character("elden_ring", first["id"])
    assert s.boss_stats("elden_ring", "Margit")["deaths"] == 2 and s.pb("elden_ring", "Margit")["pct"] == 20.0
    s.rename_character("elden_ring", first["id"], "Tarnished")
    s.delete_character("elden_ring", first["id"])
    assert [c["name"] for c in s.characters("elden_ring")] == ["Strength build"]
    assert s.character("elden_ring")["id"] == second
    with pytest.raises(ValueError):
        s.delete_character("elden_ring", second)
    with pytest.raises(ValueError):
        s.add_character("elden_ring", "   ")


def test_old_database_becomes_character_1(tmp_path):
    import sqlite3
    from soulsoverlay.store import Store
    path = tmp_path / "old.sqlite3"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE games (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE bosses (id INTEGER PRIMARY KEY, game_id TEXT NOT NULL, name TEXT NOT NULL, UNIQUE (game_id, name));
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, started_at TEXT NOT NULL);
        CREATE TABLE deaths (id INTEGER PRIMARY KEY, game_id TEXT NOT NULL, boss_id INTEGER, phase INTEGER NOT NULL DEFAULT 1,
            pct REAL, source TEXT NOT NULL, at TEXT NOT NULL, session_id INTEGER, voided INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE kills (id INTEGER PRIMARY KEY, game_id TEXT NOT NULL, boss_id INTEGER NOT NULL, phase INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL, at TEXT NOT NULL, session_id INTEGER, voided INTEGER NOT NULL DEFAULT 0);
        INSERT INTO games VALUES ('elden_ring', 'Elden Ring');
        INSERT INTO bosses VALUES (1, 'elden_ring', 'Margit');
        INSERT INTO deaths (game_id, boss_id, pct, source, at) VALUES ('elden_ring', 1, 30, 'auto', 'x'), ('elden_ring', 1, 10, 'auto', 'x');
        INSERT INTO kills (game_id, boss_id, source, at) VALUES ('elden_ring', 1, 'auto', 'x');
    """)
    db.commit(); db.close()
    s = Store(path)
    assert s.character("elden_ring") == {"id": 1, "name": "Tarnished", "deaths": 2, "active": True}
    stats = s.boss_stats("elden_ring", "Margit")
    assert stats["deaths"] == 2 and stats["killed"]
