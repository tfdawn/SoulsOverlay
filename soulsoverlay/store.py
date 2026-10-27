"""SQLite storage for deaths, attempts and PBs.

Every death is a row; a death during a boss fight carries the boss, the phase
and the boss's health just before the death, so the attempt history and the
PB are both derived from the same table. "Reset boss" and "-1" never delete
anything; they mark rows as voided so a slip of the hotkey can be repaired by
hand in the database.

Each game has one or more characters, and every death and kill belongs to
one, so a new character or a fresh run starts from zero without touching the
others. Exactly one character per game is active.

PB ordering: reaching a later phase beats any % in an earlier phase; within
a phase, lower boss health is better. A kill beats everything.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bosses (
    id      INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES games(id),
    name    TEXT NOT NULL,
    UNIQUE (game_id, name)
);
CREATE TABLE IF NOT EXISTS characters (
    id      INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES games(id),
    name    TEXT NOT NULL,
    active  INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deaths (
    id         INTEGER PRIMARY KEY,
    game_id    TEXT NOT NULL REFERENCES games(id),
    boss_id    INTEGER REFERENCES bosses(id),
    phase      INTEGER NOT NULL DEFAULT 1,
    pct        REAL,
    source     TEXT NOT NULL,          -- auto | manual
    at         TEXT NOT NULL,
    session_id INTEGER REFERENCES sessions(id),
    voided     INTEGER NOT NULL DEFAULT 0,
    character_id INTEGER REFERENCES characters(id)
);
CREATE INDEX IF NOT EXISTS deaths_by_boss ON deaths (boss_id, voided);
CREATE INDEX IF NOT EXISTS deaths_by_game ON deaths (game_id, voided);
CREATE TABLE IF NOT EXISTS kills (
    id         INTEGER PRIMARY KEY,
    game_id    TEXT NOT NULL REFERENCES games(id),
    boss_id    INTEGER NOT NULL REFERENCES bosses(id),
    phase      INTEGER NOT NULL DEFAULT 1,
    source     TEXT NOT NULL,
    at         TEXT NOT NULL,
    session_id INTEGER REFERENCES sessions(id),
    voided     INTEGER NOT NULL DEFAULT 0,
    character_id INTEGER REFERENCES characters(id)
);
"""

DEFAULT_CHARACTER = "Tarnished"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pb_better(a: dict | None, b: dict | None) -> bool:
    """True if attempt a beats attempt b. Attempts are {phase, pct, killed}."""
    if a is None:
        return False
    if b is None:
        return True
    if a.get("killed") != b.get("killed"):
        return bool(a.get("killed"))
    if a["phase"] != b["phase"]:
        return a["phase"] > b["phase"]
    return (a["pct"] if a["pct"] is not None else 101) < (b["pct"] if b["pct"] is not None else 101)


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self._migrate()
        self.lock = threading.RLock()
        self.session_id = self.db.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (_now(),)).lastrowid
        self.db.commit()

    def _migrate(self):
        """Databases from before characters (earlier versions): their stats go to the first character."""
        for table in ("deaths", "kills"):
            cols = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            if "character_id" not in cols:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN character_id INTEGER REFERENCES characters(id)")
        self.db.execute("CREATE INDEX IF NOT EXISTS deaths_by_character ON deaths (character_id, boss_id, voided)")
        for r in self.db.execute("SELECT id FROM games").fetchall():
            char = self._active_character(r["id"])
            for table in ("deaths", "kills"):
                self.db.execute(f"UPDATE {table} SET character_id = ? WHERE game_id = ? AND character_id IS NULL",
                                (char, r["id"]))
        self.db.commit()

    # -- ids -------------------------------------------------------------
    def ensure_game(self, game_id: str, name: str | None = None):
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO games (id, name) VALUES (?, ?)",
                            (game_id, name or game_id))
            if name:
                self.db.execute("UPDATE games SET name = ? WHERE id = ?", (name, game_id))
            self._active_character(game_id)
            self.db.commit()

    def _active_character(self, game_id: str) -> int:
        row = self.db.execute("SELECT id FROM characters WHERE game_id = ? AND active = 1 AND deleted = 0",
                              (game_id,)).fetchone()
        if row:
            return row["id"]
        row = self.db.execute("SELECT id FROM characters WHERE game_id = ? AND deleted = 0 ORDER BY id LIMIT 1",
                              (game_id,)).fetchone()
        if row:
            char = row["id"]
        else:
            self.db.execute("INSERT OR IGNORE INTO games (id, name) VALUES (?, ?)", (game_id, game_id))
            char = self.db.execute("INSERT INTO characters (game_id, name) VALUES (?, ?)",
                                   (game_id, DEFAULT_CHARACTER)).lastrowid
        self.db.execute("UPDATE characters SET active = (id = ?) WHERE game_id = ?", (char, game_id))
        return char

    # -- characters --------------------------------------------------------
    def characters(self, game_id: str) -> list[dict]:
        with self.lock:
            active = self._active_character(game_id)
            self.db.commit()
            rows = self.db.execute(
                "SELECT c.id, c.name, (SELECT COUNT(*) FROM deaths d WHERE d.character_id = c.id AND d.voided = 0)"
                " AS deaths FROM characters c WHERE c.game_id = ? AND c.deleted = 0 ORDER BY c.id", (game_id,))
            return [{"id": r["id"], "name": r["name"], "deaths": r["deaths"], "active": r["id"] == active}
                    for r in rows]

    def character(self, game_id: str) -> dict:
        return next(c for c in self.characters(game_id) if c["active"])

    def _own_character(self, game_id: str, char_id) -> int:
        row = self.db.execute("SELECT id FROM characters WHERE id = ? AND game_id = ? AND deleted = 0",
                              (char_id, game_id)).fetchone()
        if not row:
            raise ValueError("That character doesn't exist.")
        return row["id"]

    @staticmethod
    def _clean_name(name) -> str:
        name = " ".join(str(name or "").split())[:40]
        if not name:
            raise ValueError("Give the character a name.")
        return name

    def add_character(self, game_id: str, name: str) -> int:
        """Add a character and switch to it."""
        with self.lock:
            self.ensure_game(game_id)
            char = self.db.execute("INSERT INTO characters (game_id, name) VALUES (?, ?)",
                                   (game_id, self._clean_name(name))).lastrowid
            self.db.execute("UPDATE characters SET active = (id = ?) WHERE game_id = ?", (char, game_id))
            self.db.commit()
            return char

    def select_character(self, game_id: str, char_id: int):
        with self.lock:
            char = self._own_character(game_id, char_id)
            self.db.execute("UPDATE characters SET active = (id = ?) WHERE game_id = ?", (char, game_id))
            self.db.commit()

    def rename_character(self, game_id: str, char_id: int, name: str):
        with self.lock:
            char = self._own_character(game_id, char_id)
            self.db.execute("UPDATE characters SET name = ? WHERE id = ?", (self._clean_name(name), char))
            self.db.commit()

    def delete_character(self, game_id: str, char_id: int):
        """Hide a character and its stats (kept in the database, like voided deaths)."""
        with self.lock:
            char = self._own_character(game_id, char_id)
            if len(self.characters(game_id)) < 2:
                raise ValueError("You can't delete your only character.")
            self.db.execute("UPDATE characters SET deleted = 1, active = 0 WHERE id = ?", (char,))
            self._active_character(game_id)
            self.db.commit()

    def _boss_id(self, game_id: str, boss: str | None, create: bool = True) -> int | None:
        if not boss:
            return None
        row = self.db.execute("SELECT id FROM bosses WHERE game_id = ? AND name = ?",
                              (game_id, boss)).fetchone()
        if row:
            return row["id"]
        if not create:
            return None
        self.ensure_game(game_id)
        return self.db.execute("INSERT INTO bosses (game_id, name) VALUES (?, ?)",
                               (game_id, boss)).lastrowid

    # -- writes ----------------------------------------------------------
    def record_death(self, game_id: str, boss: str | None, phase: int = 1,
                     pct: float | None = None, source: str = "auto") -> dict:
        with self.lock:
            self.ensure_game(game_id)
            boss_id = self._boss_id(game_id, boss)
            before = self.pb(game_id, boss) if boss else None
            death_id = self.db.execute(
                "INSERT INTO deaths (game_id, boss_id, phase, pct, source, at, session_id, character_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (game_id, boss_id, phase, pct, source, _now(), self.session_id,
                 self._active_character(game_id))).lastrowid
            self.db.commit()
            attempt = {"phase": phase, "pct": pct, "killed": False}
            new_pb = bool(boss and pct is not None and before is not None
                          and pb_better(attempt, before))
            return {"id": death_id, "boss": boss, "phase": phase, "pct": pct,
                    "new_pb": new_pb, "previous_pb": before}

    def record_kill(self, game_id: str, boss: str, phase: int = 1, source: str = "auto") -> dict:
        with self.lock:
            boss_id = self._boss_id(game_id, boss)
            before = self.pb(game_id, boss)
            first = not (before and before.get("killed"))
            self.db.execute(
                "INSERT INTO kills (game_id, boss_id, phase, source, at, session_id, character_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (game_id, boss_id, phase, source, _now(), self.session_id, self._active_character(game_id)))
            self.db.commit()
            return {"boss": boss, "phase": phase, "first_kill": first}

    def undo_last_death(self, game_id: str) -> dict | None:
        with self.lock:
            row = self.db.execute(
                "SELECT d.id, d.phase, d.pct, b.name AS boss FROM deaths d"
                " LEFT JOIN bosses b ON b.id = d.boss_id"
                " WHERE d.game_id = ? AND d.character_id = ? AND d.voided = 0 ORDER BY d.id DESC LIMIT 1",
                (game_id, self._active_character(game_id))).fetchone()
            if not row:
                return None
            self.db.execute("UPDATE deaths SET voided = 1 WHERE id = ?", (row["id"],))
            self.db.commit()
            return dict(row)

    def reset_boss(self, game_id: str, boss: str) -> int:
        with self.lock:
            boss_id = self._boss_id(game_id, boss, create=False)
            if boss_id is None:
                return 0
            char = self._active_character(game_id)
            n = self.db.execute("UPDATE deaths SET voided = 1 WHERE boss_id = ? AND character_id = ? AND voided = 0",
                                (boss_id, char)).rowcount
            self.db.execute("UPDATE kills SET voided = 1 WHERE boss_id = ? AND character_id = ? AND voided = 0",
                            (boss_id, char))
            self.db.commit()
            return n

    # -- reads -----------------------------------------------------------
    def pb(self, game_id: str, boss: str) -> dict | None:
        boss_id = self._boss_id(game_id, boss, create=False)
        if boss_id is None:
            return None
        char = self._active_character(game_id)
        kill = self.db.execute(
            "SELECT phase FROM kills WHERE boss_id = ? AND character_id = ? AND voided = 0"
            " ORDER BY phase DESC LIMIT 1", (boss_id, char)).fetchone()
        if kill:
            return {"phase": kill["phase"], "pct": 0.0, "killed": True}
        row = self.db.execute(
            "SELECT phase, MIN(pct) AS pct FROM deaths WHERE boss_id = ? AND character_id = ? AND voided = 0"
            " AND pct IS NOT NULL GROUP BY phase ORDER BY phase DESC LIMIT 1",
            (boss_id, char)).fetchone()
        if not row:
            return None
        return {"phase": row["phase"], "pct": row["pct"], "killed": False}

    def boss_stats(self, game_id: str, boss: str | None) -> dict | None:
        if not boss:
            return None
        with self.lock:
            boss_id = self._boss_id(game_id, boss, create=False)
            if boss_id is None:
                return {"name": boss, "deaths": 0, "session_deaths": 0, "pb": None,
                        "phase_pbs": {}, "recent": [], "killed": False}
            char = self._active_character(game_id)
            mine = "boss_id = ? AND character_id = ? AND voided = 0"
            deaths = self.db.execute(
                f"SELECT COUNT(*) FROM deaths WHERE {mine}", (boss_id, char)).fetchone()[0]
            session = self.db.execute(
                f"SELECT COUNT(*) FROM deaths WHERE {mine} AND session_id = ?",
                (boss_id, char, self.session_id)).fetchone()[0]
            phase_pbs = {
                r["phase"]: r["pct"] for r in self.db.execute(
                    f"SELECT phase, MIN(pct) AS pct FROM deaths WHERE {mine}"
                    " AND pct IS NOT NULL GROUP BY phase ORDER BY phase", (boss_id, char))
            }
            recent = [
                {"phase": r["phase"], "pct": r["pct"]} for r in self.db.execute(
                    f"SELECT phase, pct FROM deaths WHERE {mine}"
                    " ORDER BY id DESC LIMIT 20", (boss_id, char))
            ]
            pb = self.pb(game_id, boss)
            return {"name": boss, "deaths": deaths, "session_deaths": session, "pb": pb,
                    "phase_pbs": phase_pbs, "recent": recent[::-1],
                    "killed": bool(pb and pb.get("killed"))}

    def game_stats(self, game_id: str) -> dict:
        with self.lock:
            char = self._active_character(game_id)
            total = self.db.execute(
                "SELECT COUNT(*) FROM deaths WHERE game_id = ? AND character_id = ? AND voided = 0",
                (game_id, char)).fetchone()[0]
            session = self.db.execute(
                "SELECT COUNT(*) FROM deaths WHERE game_id = ? AND character_id = ? AND voided = 0"
                " AND session_id = ?", (game_id, char, self.session_id)).fetchone()[0]
            return {"deaths": total, "session_deaths": session}

    def all_bosses(self, game_id: str) -> list[dict]:
        rows = self.db.execute("SELECT name FROM bosses WHERE game_id = ? ORDER BY id", (game_id,))
        return [self.boss_stats(game_id, r["name"]) for r in rows.fetchall()]
