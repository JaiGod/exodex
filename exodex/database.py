"""SQLite persistence layer.

Every save slot is its own SQLite database file (saves/slot1.db ...). It holds
the static catalogue (species, moves, planets, items...) *and* the player's
progress, so a save file is self-describing and can be opened in any SQLite
browser. The browser build uses the same schema (via sql.js), so .db files
exported from the web version load here too.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .creature import Creature
from .data import SCHEMA_FILE, GameData

# Saves live next to the game (or next to ExoDex.exe when packaged with PyInstaller).
SAVE_DIR = (Path(sys.executable).parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent.parent) / "saves"
SCHEMA_VERSION = "1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path, data: GameData):
        self.path = str(path)
        self.data = data
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------ setup
    @classmethod
    def create(cls, path: str | Path, data: GameData, player_name: str) -> "Database":
        path = Path(path)
        if str(path) != ":memory:" and path.exists():
            path.unlink()
        db = cls(path, data)
        db.conn.executescript(SCHEMA_FILE.read_text())
        db._seed_catalogue()
        ts = now()
        db.conn.execute(
            "INSERT INTO player (id, name, rp, current_planet, created_at, saved_at) VALUES (1, ?, 0, NULL, ?, ?)",
            (player_name, ts, ts))
        for item, qty in {"pod": 5, "medgel": 3, "fuel": 3, "iron": 4}.items():
            db.add_item(item, qty)
        db.conn.commit()
        return db

    def _seed_catalogue(self):
        c, d = self.conn, self.data
        c.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
        c.execute("INSERT INTO meta VALUES ('game', 'ExoDex')")
        c.executemany("INSERT INTO moves VALUES (?,?,?,?,?,?,?)",
                      [(m.id, m.name, m.type, m.power, m.accuracy, m.effect, m.description) for m in d.moves.values()])
        rows, learn = [], []
        for s in d.species.values():
            rows.append((s.id, s.name, s.type1, s.type2, s.kingdom, s.rarity, s.hp, s.atk, s.defense, s.spd,
                         None, s.evolve_level, s.family, s.stage, ",".join(s.biomes), s.hue, s.sprite_seed,
                         s.height_m, s.mass_kg, s.description))
            learn += [(s.id, lv, mid) for lv, mid in s.learnset]
        c.executemany("INSERT INTO species VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        # evolves_to references species rows, so link after all rows exist
        c.executemany("UPDATE species SET evolves_to=? WHERE id=?",
                      [(s.evolves_to, s.id) for s in d.species.values() if s.evolves_to])
        c.executemany("INSERT OR IGNORE INTO species_moves VALUES (?,?,?)", learn)
        c.executemany("INSERT INTO planets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      [(p.id, p.name, p.biome, p.description, p.min_level, p.max_level, p.unlock_rank, p.seed,
                        p.material, p.alpha_species, p.alpha_level) for p in d.planets.values()])
        c.executemany("INSERT INTO items VALUES (?,?,?,?,?)",
                      [(i["id"], i["name"], i["kind"], i["description"], i["value"]) for i in d.items.values()])
        for r in d.recipes:
            c.execute("INSERT INTO recipes VALUES (?,?,?)", (r["id"], r["output"], r["qty"]))
            c.executemany("INSERT INTO recipe_inputs VALUES (?,?,?)",
                          [(r["id"], k, v) for k, v in r["inputs"].items()])
        c.executemany("INSERT INTO research (id,name,description,cost,max_level) VALUES (?,?,?,?,?)",
                      [(r["id"], r["name"], r["description"], r["cost"], r["max_level"]) for r in d.research.values()])
        c.executemany("INSERT INTO missions (id,title,description,kind,target,goal,reward_rp,reward_item,reward_qty)"
                      " VALUES (?,?,?,?,?,?,?,?,?)",
                      [(m["id"], m["title"], m["description"], m["kind"], m["target"], m["goal"], m["reward_rp"],
                        m["reward_item"], m["reward_qty"]) for m in d.missions])

    def commit(self):
        self.conn.execute("UPDATE player SET saved_at=? WHERE id=1", (now(),))
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ----------------------------------------------------------------- player
    def player(self) -> sqlite3.Row:
        return self.conn.execute("SELECT * FROM player WHERE id=1").fetchone()

    def update_player(self, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE player SET {cols} WHERE id=1", tuple(fields.values()))

    def add_rp(self, amount: int):
        self.conn.execute("UPDATE player SET rp = rp + ? WHERE id=1", (amount,))

    # -------------------------------------------------------------- inventory
    def qty(self, item_id: str) -> int:
        row = self.conn.execute("SELECT qty FROM inventory WHERE item_id=?", (item_id,)).fetchone()
        return row["qty"] if row else 0

    def add_item(self, item_id: str, qty: int = 1):
        self.conn.execute("INSERT INTO inventory VALUES (?, ?) ON CONFLICT(item_id) DO UPDATE SET qty = qty + ?",
                          (item_id, qty, qty))

    def remove_item(self, item_id: str, qty: int = 1) -> bool:
        if self.qty(item_id) < qty:
            return False
        self.conn.execute("UPDATE inventory SET qty = qty - ? WHERE item_id=?", (qty, item_id))
        return True

    def inventory(self) -> list[tuple[dict, int]]:
        rows = self.conn.execute("SELECT item_id, qty FROM inventory WHERE qty > 0 ORDER BY item_id").fetchall()
        return [(self.data.items[r["item_id"]], r["qty"]) for r in rows]

    # -------------------------------------------------------------- creatures
    def _row_to_creature(self, r) -> Creature:
        c = Creature(species=self.data.species[r["species_id"]], level=r["level"], trait=r["trait"],
                     ivs={"hp": r["iv_hp"], "atk": r["iv_atk"], "def": r["iv_def"], "spd": r["iv_spd"]},
                     moves=[int(m) for m in r["moves"].split(",") if m], xp=r["xp"], hp=r["hp_current"],
                     aberrant=bool(r["aberrant"]), nickname=r["nickname"], id=r["id"], team_slot=r["team_slot"],
                     planet_id=r["planet_id"])
        return c

    def add_creature(self, c: Creature, planet_id: int | None) -> int:
        team = self.team()
        slot = len(team) if len(team) < 6 else None
        cur = self.conn.execute(
            "INSERT INTO creatures (species_id,nickname,level,xp,hp_current,trait,iv_hp,iv_atk,iv_def,iv_spd,"
            "aberrant,team_slot,moves,planet_id,caught_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c.species.id, c.nickname, c.level, c.xp, max(c.hp, 0), c.trait, c.ivs["hp"], c.ivs["atk"],
             c.ivs["def"], c.ivs["spd"], int(c.aberrant), slot, ",".join(map(str, c.moves)), planet_id, now()))
        c.id, c.team_slot, c.planet_id = cur.lastrowid, slot, planet_id
        return c.id

    def save_creature(self, c: Creature):
        self.conn.execute(
            "UPDATE creatures SET species_id=?, nickname=?, level=?, xp=?, hp_current=?, iv_hp=?, iv_atk=?,"
            " iv_def=?, iv_spd=?, team_slot=?, moves=? WHERE id=?",
            (c.species.id, c.nickname, c.level, c.xp, max(c.hp, 0), c.ivs["hp"], c.ivs["atk"], c.ivs["def"],
             c.ivs["spd"], c.team_slot, ",".join(map(str, c.moves)), c.id))

    def team(self) -> list[Creature]:
        rows = self.conn.execute("SELECT * FROM creatures WHERE team_slot IS NOT NULL ORDER BY team_slot").fetchall()
        return [self._row_to_creature(r) for r in rows]

    def storage(self) -> list[Creature]:
        rows = self.conn.execute(
            "SELECT * FROM creatures WHERE team_slot IS NULL ORDER BY level DESC, id").fetchall()
        return [self._row_to_creature(r) for r in rows]

    def all_creatures(self) -> list[Creature]:
        return [self._row_to_creature(r) for r in
                self.conn.execute("SELECT * FROM creatures ORDER BY team_slot IS NULL, team_slot, id").fetchall()]

    def set_team(self, ids: list[int]):
        self.conn.execute("UPDATE creatures SET team_slot = NULL")
        for slot, cid in enumerate(ids[:6]):
            self.conn.execute("UPDATE creatures SET team_slot=? WHERE id=?", (slot, cid))

    # ------------------------------------------------------------ discoveries
    def discovery(self, species_id: int):
        return self.conn.execute("SELECT * FROM discoveries WHERE species_id=?", (species_id,)).fetchone()

    def mark(self, species_id: int, planet_id: int | None, seen=False, scanned=False, captured=False,
             dna: int = 0) -> dict:
        """Upserts a discovery row; returns which flags are *new*."""
        old = self.discovery(species_id)
        if old is None:
            self.conn.execute("INSERT INTO discoveries (species_id, planet_id, first_seen) VALUES (?,?,?)",
                              (species_id, planet_id, now()))
            old = self.discovery(species_id)
        new = {"seen": seen and not old["seen"], "scanned": scanned and not old["scanned"],
               "captured": captured and not old["captured"]}
        self.conn.execute(
            "UPDATE discoveries SET seen = MAX(seen, ?), scanned = MAX(scanned, ?), captured = MAX(captured, ?),"
            " dna = dna + ? WHERE species_id=?",
            (int(seen or scanned or captured), int(scanned or captured), int(captured), dna, species_id))
        return new

    def spend_dna(self, species_id: int, amount: int) -> bool:
        row = self.discovery(species_id)
        if not row or row["dna"] < amount:
            return False
        self.conn.execute("UPDATE discoveries SET dna = dna - ? WHERE species_id=?", (amount, species_id))
        return True

    def dex_counts(self) -> dict:
        r = self.conn.execute("SELECT COALESCE(SUM(seen),0) seen, COALESCE(SUM(scanned),0) scanned,"
                              " COALESCE(SUM(captured),0) captured FROM discoveries").fetchone()
        return dict(r)

    def explorer_rank(self) -> int:
        return self.dex_counts()["scanned"]

    def journal(self, kingdom: str | None = None) -> list[sqlite3.Row]:
        """All species joined with discovery status - the ExoDex journal."""
        sql = ("SELECT s.*, COALESCE(d.seen,0) seen, COALESCE(d.scanned,0) scanned,"
               " COALESCE(d.captured,0) captured, COALESCE(d.dna,0) dna, p.name planet_name"
               " FROM species s LEFT JOIN discoveries d ON d.species_id = s.id"
               " LEFT JOIN planets p ON p.id = d.planet_id")
        args: tuple = ()
        if kingdom:
            sql += " WHERE s.kingdom = ?"
            args = (kingdom,)
        return self.conn.execute(sql + " ORDER BY s.id", args).fetchall()

    def count_scanned_where(self, sql_filter: str, args: tuple = ()) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM discoveries d JOIN species s ON s.id = d.species_id"
            f" WHERE d.scanned = 1 AND {sql_filter}", args).fetchone()[0]

    # ------------------------------------------------------- stats & history
    def bump(self, key: str, amount: int = 1):
        self.conn.execute("INSERT INTO stats VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
                          (key, amount, amount))

    def stat(self, key: str) -> int:
        row = self.conn.execute("SELECT value FROM stats WHERE key=?", (key,)).fetchone()
        return row["value"] if row else 0

    def log_battle(self, planet_id, enemy_species: int, enemy_level: int, result: str, turns: int):
        self.conn.execute("INSERT INTO battle_history (planet_id, enemy_species, enemy_level, result, turns, at)"
                          " VALUES (?,?,?,?,?,?)", (planet_id, enemy_species, enemy_level, result, turns, now()))

    def recent_battles(self, n: int = 8):
        return self.conn.execute(
            "SELECT b.*, s.name species_name FROM battle_history b JOIN species s ON s.id = b.enemy_species"
            " ORDER BY b.id DESC LIMIT ?", (n,)).fetchall()

    # ------------------------------------------------- research & missions
    def research_level(self, rid: str) -> int:
        return self.conn.execute("SELECT level FROM research WHERE id=?", (rid,)).fetchone()["level"]

    def research_rows(self):
        return self.conn.execute("SELECT * FROM research ORDER BY cost").fetchall()

    def missions(self):
        return self.conn.execute("SELECT * FROM missions ORDER BY id").fetchall()

    def execute(self, sql: str, args: tuple = ()):
        return self.conn.execute(sql, args)


def list_saves() -> list[Path]:
    SAVE_DIR.mkdir(exist_ok=True)
    return sorted(SAVE_DIR.glob("*.db"))
