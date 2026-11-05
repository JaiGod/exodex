"""A single creature specimen (wild or captured) with procedural traits."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .data import GameData, Species

TRAIT_STAT = {"Hardy": "hp", "Ferocious": "atk", "Armored": "def", "Swift": "spd"}
ABERRANT_CHANCE = 1 / 64


def xp_for_level(level: int) -> int:
    """Total XP needed to *reach* a level (medium-fast cubic curve)."""
    return int(level ** 3 * 0.8)


@dataclass
class Creature:
    species: Species
    level: int
    trait: str
    ivs: dict
    moves: list
    xp: int = 0
    hp: int = -1
    aberrant: bool = False
    nickname: str | None = None
    id: int | None = None            # database id once captured
    team_slot: int | None = None
    planet_id: int | None = None
    # battle-only state
    status: str | None = None
    status_turns: int = 0
    stages: dict = field(default_factory=lambda: {"atk": 0, "def": 0, "spd": 0, "acc": 0})

    def __post_init__(self):
        if self.xp < xp_for_level(self.level):
            self.xp = xp_for_level(self.level)
        if self.hp < 0:
            self.hp = self.max_hp

    # ---- construction ----
    @classmethod
    def generate(cls, data: GameData, species: Species, level: int, rng: random.Random | None = None,
                 trait: str | None = None, iv_min: int = 0, iv_max: int = 12) -> "Creature":
        rng = rng or random.Random()
        ivs = {k: rng.randint(iv_min, iv_max) for k in ("hp", "atk", "def", "spd")}
        trait = trait or rng.choice(list(data.traits))
        return cls(species=species, level=level, trait=trait, ivs=ivs, moves=species.moves_at(level),
                   aberrant=rng.random() < ABERRANT_CHANCE)

    # ---- stats ----
    @property
    def name(self) -> str:
        return self.nickname or self.species.name

    def _stat(self, base: int, iv: int, key: str) -> int:
        val = (2 * base + iv * 2) * self.level // 100 + 5
        if TRAIT_STAT.get(self.trait) == key:
            val = int(val * 1.12)
        if self.trait == "Volatile" and key == "def":
            val = int(val * 0.92)
        return max(1, val)

    @property
    def max_hp(self) -> int:
        val = (2 * self.species.hp + self.ivs["hp"] * 2) * self.level // 100 + self.level + 10
        if self.trait == "Hardy":
            val = int(val * 1.12)
        return val

    @property
    def atk(self) -> int:
        return self._stat(self.species.atk, self.ivs["atk"], "atk")

    @property
    def defense(self) -> int:
        return self._stat(self.species.defense, self.ivs["def"], "def")

    @property
    def spd(self) -> int:
        return self._stat(self.species.spd, self.ivs["spd"], "spd")

    @property
    def fainted(self) -> bool:
        return self.hp <= 0

    @property
    def iv_total(self) -> int:
        return sum(self.ivs.values())

    def reset_battle_state(self):
        self.status, self.status_turns = None, 0
        self.stages = {"atk": 0, "def": 0, "spd": 0, "acc": 0}

    def heal_full(self):
        self.hp = self.max_hp
        self.status = None

    # ---- growth ----
    def xp_reward(self, alpha: bool = False) -> int:
        return int(self.species.base_total / 4 * self.level / 4 * (1.6 if alpha else 1.0))

    def gain_xp(self, amount: int, data: GameData) -> list[str]:
        """Adds XP; returns messages for level-ups and newly learned moves."""
        if self.trait == "Ancient":
            amount = int(amount * 1.25)
        msgs = [f"{self.name} gained {amount} XP."]
        self.xp += amount
        while self.level < 100 and self.xp >= xp_for_level(self.level + 1):
            old_max = self.max_hp
            self.level += 1
            self.hp += self.max_hp - old_max
            msgs.append(f"{self.name} grew to level {self.level}!")
            for lv, mid in self.species.learnset:
                if lv == self.level and mid not in self.moves:
                    if len(self.moves) >= 4:
                        forgotten = data.moves[self.moves.pop(0)].name
                        msgs.append(f"{self.name} forgot {forgotten}...")
                    self.moves.append(mid)
                    msgs.append(f"{self.name} learned {data.moves[mid].name}!")
        return msgs

    def can_evolve(self) -> bool:
        s = self.species
        return bool(s.evolves_to and s.evolve_level and self.level >= s.evolve_level)

    def evolve(self, data: GameData) -> str:
        old = self.name
        frac = self.hp / self.max_hp if self.max_hp else 1
        self.species = data.species[self.species.evolves_to]
        self.hp = max(1, int(self.max_hp * frac))
        for mid in self.species.moves_at(self.level):
            if mid not in self.moves:
                if len(self.moves) >= 4:
                    self.moves.pop(0)
                self.moves.append(mid)
        return f"{old} evolved into {self.species.name}!"
