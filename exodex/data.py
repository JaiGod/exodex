"""Static game data: loads data/gamedata.json into typed, indexed objects."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "gamedata.json"
SCHEMA_FILE = ROOT / "data" / "schema.sql"

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_CAPTURE = {"common": 1.0, "uncommon": 0.75, "rare": 0.5, "epic": 0.3, "legendary": 0.12}
RARITY_RP = {"common": 5, "uncommon": 8, "rare": 12, "epic": 20, "legendary": 40}


@dataclass(frozen=True)
class Move:
    id: int
    name: str
    type: str
    power: int
    accuracy: int
    effect: str | None
    description: str


@dataclass(frozen=True)
class Species:
    id: int
    name: str
    type1: str
    type2: str | None
    kingdom: str
    rarity: str
    hp: int
    atk: int
    defense: int
    spd: int
    evolves_to: int | None
    evolve_level: int | None
    family: int
    stage: int
    biomes: tuple
    hue: int
    sprite_seed: int
    height_m: float
    mass_kg: float
    description: str
    learnset: tuple = field(default=())

    @property
    def types(self) -> tuple:
        return (self.type1,) + ((self.type2,) if self.type2 else ())

    @property
    def base_total(self) -> int:
        return self.hp + self.atk + self.defense + self.spd

    def moves_at(self, level: int) -> list[int]:
        """Up to four most recently learned move ids at a given level."""
        learned: list[int] = []
        for lv, mid in self.learnset:
            if lv <= level and mid not in learned:
                learned.append(mid)
        return learned[-4:]


@dataclass(frozen=True)
class Planet:
    id: int
    name: str
    biome: str
    description: str
    min_level: int
    max_level: int
    unlock_rank: int
    seed: int
    material: str
    alpha_species: int
    alpha_level: int
    types: tuple


class GameData:
    """Indexed, read-only view of the generated catalogue."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.types: list[str] = raw["types"]
        self.type_chart: dict = raw["type_chart"]
        self.type_hue: dict = raw["type_hue"]
        self.moves = {m["id"]: Move(**m) for m in raw["moves"]}
        self.species: dict[int, Species] = {}
        for s in raw["species"]:
            s = dict(s)
            s["biomes"] = tuple(s["biomes"])
            s["learnset"] = tuple(tuple(x) for x in s["learnset"])
            self.species[s["id"]] = Species(**s)
        self.planets = {p["id"]: Planet(**p) for p in raw["planets"]}
        self.items = {i["id"]: i for i in raw["items"]}
        self.recipes = raw["recipes"]
        self.research = {r["id"]: r for r in raw["research"]}
        self.missions = raw["missions"]
        self.traits = {t["name"]: t["description"] for t in raw["traits"]}
        self.rarity_weight = raw["rarity_weight"]
        self.prev_stage = {s.evolves_to: s.id for s in self.species.values() if s.evolves_to}

    def effectiveness(self, move_type: str, defender_types) -> float:
        if move_type not in self.type_chart:
            return 1.0
        strong, weak = self.type_chart[move_type]
        mult = 1.0
        for t in defender_types:
            if t in strong:
                mult *= 2.0
            elif t in weak:
                mult *= 0.5
        return mult

    def starters(self) -> list[Species]:
        """First stage of the first three-stage family for FLORA, HYDRO and THERMAL."""
        out = []
        for t in ("FLORA", "HYDRO", "THERMAL"):
            for s in self.species.values():
                if (s.type1 == t and s.stage == 1 and s.evolves_to
                        and self.species[s.evolves_to].evolves_to and s.rarity == "common"):
                    out.append(s)
                    break
        return out

    def min_wild_level(self, sp: Species) -> int:
        """Lowest level a wild specimen of this (possibly evolved) species can be."""
        prev = self.prev_stage.get(sp.id)
        return self.species[prev].evolve_level if prev else 1


@lru_cache(maxsize=1)
def load() -> GameData:
    return GameData(json.loads(DATA_FILE.read_text()))
