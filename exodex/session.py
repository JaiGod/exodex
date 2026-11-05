"""GameSession: the game's rules layer. Ties together the database, the static
catalogue, procedural maps, battles, crafting, research and missions.
The Pygame scenes only call methods on this class, so all gameplay is
unit-testable without a window."""
from __future__ import annotations

import random
from pathlib import Path

from .battle import Battle
from .creature import Creature
from .data import RARITY_ORDER, RARITY_RP, GameData, Planet, load
from .database import SAVE_DIR, Database
from .procgen import BIOZONE, NEST, NODE, PlanetMap, alpha_creature, roll_wild

ENCOUNTER_RATE = 0.12
SEQUENCE_COST = 3
ACCEL_EVOLVE_COST = 6
SYNTH_COST = 10


class GameSession:
    def __init__(self, db: Database, data: GameData, rng: random.Random | None = None):
        self.db = db
        self.data = data
        self.rng = rng or random.Random()
        self.map: PlanetMap | None = None
        self._maps: dict[int, PlanetMap] = {}
        p = db.player()
        if p["current_planet"]:
            self._enter_map(p["current_planet"], (p["pos_x"], p["pos_y"]))

    # ---------------------------------------------------------- lifecycle
    @classmethod
    def new_game(cls, path: str | Path, name: str, starter_species: int, rng=None) -> "GameSession":
        data = load()
        db = Database.create(path, data, name)
        s = cls(db, data, rng)
        starter = Creature.generate(data, data.species[starter_species], 6, s.rng, trait="Hardy", iv_min=8, iv_max=15)
        db.add_creature(starter, None)
        db.mark(starter_species, None, seen=True, scanned=True, captured=True, dna=1)
        db.commit()
        return s

    @classmethod
    def load_game(cls, path: str | Path, rng=None) -> "GameSession":
        return cls(Database(path, load()), load(), rng)

    def save(self):
        self.db.commit()

    # ---------------------------------------------------------- queries
    @property
    def player(self):
        return self.db.player()

    @property
    def planet(self) -> Planet | None:
        pid = self.player["current_planet"]
        return self.data.planets[pid] if pid else None

    def rank(self) -> int:
        return self.db.explorer_rank()

    def unlocked(self, planet: Planet) -> bool:
        return self.rank() >= planet.unlock_rank

    def team(self) -> list[Creature]:
        return self.db.team()

    # ---------------------------------------------------------- travel
    def travel(self, planet_id: int) -> tuple[bool, str]:
        planet = self.data.planets[planet_id]
        if not self.unlocked(planet):
            return False, f"Requires Explorer Rank {planet.unlock_rank} (scan more species)."
        if all(c.fainted for c in self.team()):
            return False, "Your team needs healing before a mission."
        if planet_id == 1:  # the home world is in shuttle range: no fuel needed (prevents soft-locks)
            self._enter_map(planet_id, None)
            self.db.commit()
            return True, f"Shuttle landed on {planet.name}."
        free = self.rng.random() < 0.3 * self.db.research_level("propulsion")
        if not free and not self.db.remove_item("fuel", 1):
            return False, "No Fuel Cells! Craft some at the Fabricator."
        self._enter_map(planet_id, None)
        self.db.commit()
        return True, f"Landed on {planet.name}." + (" Ion drive saved a Fuel Cell!" if free else "")

    def _enter_map(self, planet_id: int, pos):
        planet = self.data.planets[planet_id]
        self.map = PlanetMap(planet)  # fresh map each landing -> resource nodes respawn
        x, y = pos if pos and self.map.walkable(*pos) else self.map.pad
        self.db.update_player(current_planet=planet_id, pos_x=x, pos_y=y)

    def return_to_lab(self):
        self.map = None
        self.db.update_player(current_planet=None)
        self.heal_team()
        self.db.commit()

    def heal_team(self):
        for c in self.db.all_creatures():
            c.heal_full()
            self.db.save_creature(c)

    # ---------------------------------------------------------- exploration
    def step(self, dx: int, dy: int):
        """Move one tile. Returns None or an event tuple: ('encounter', creature) / ('alpha', creature)."""
        if not self.map:
            return None
        p = self.player
        nx, ny = p["pos_x"] + dx, p["pos_y"] + dy
        if not self.map.walkable(nx, ny):
            return None
        lure = max(0, p["lure_steps"] - 1)
        self.db.update_player(pos_x=nx, pos_y=ny, steps=p["steps"] + 1, lure_steps=lure)
        tile = self.map.tile(nx, ny)
        if tile == NEST and str(self.planet.id) not in p["alphas_beaten"].split(","):
            return ("alpha", alpha_creature(self.data, self.planet, self.rng))
        if tile == BIOZONE:
            rate = ENCOUNTER_RATE * (2 if lure else 1)
            if self.rng.random() < rate:
                return ("encounter", roll_wild(self.data, self.planet, self.rng, lure=bool(lure)))
        return None

    def gather(self) -> str | None:
        """Harvest a resource node on or next to the player."""
        if not self.map:
            return None
        p = self.player
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = p["pos_x"] + dx, p["pos_y"] + dy
            if self.map.tile(x, y) == NODE and self.map.harvest(x, y):
                mat = self.planet.material
                n = self.rng.randint(1, 2) + self.db.research_level("logistics")
                self.db.add_item(mat, n)
                got = [f"{n}x {self.data.items[mat]['name']}"]
                if self.rng.random() < 0.6:
                    k = self.rng.randint(1, 2)
                    self.db.add_item("iron", k)
                    got.append(f"{k}x Iron Ingot")
                if self.rng.random() < 0.15:
                    other = self.rng.choice([pl.material for pl in self.data.planets.values()])
                    self.db.add_item(other, 1)
                    got.append(f"1x {self.data.items[other]['name']}")
                self.db.bump("gather")
                self._refresh_missions()
                return "Gathered " + ", ".join(got) + "."
        return None

    def use_lure(self) -> bool:
        if self.db.remove_item("lure", 1):
            self.db.update_player(lure_steps=60)
            return True
        return False

    # ---------------------------------------------------------- battles
    def start_battle(self, enemy: Creature, alpha: bool = False) -> Battle:
        team = self.team()
        self.db.mark(enemy.species.id, self.planet.id if self.planet else None, seen=True)
        return Battle(self.data, team, enemy, alpha=alpha, rng=self.rng, inventory=self.db,
                      scanner_level=self.db.research_level("scanner"),
                      containment_level=self.db.research_level("containment"))

    def finish_battle(self, b: Battle) -> list[str]:
        msgs: list[str] = []
        planet_id = self.planet.id if self.planet else None
        e = b.enemy
        if b.scanned or b.result == "captured":
            dna = 1 + self.db.research_level("scanner") if b.scanned else 0
            new = self.db.mark(e.species.id, planet_id, scanned=True, dna=dna)
            if new["scanned"]:
                rp = RARITY_RP[e.species.rarity]
                self.db.add_rp(rp)
                msgs.append(f"New ExoDex entry: {e.species.name}! +{rp} RP")
                self.db.bump("scan")
        if b.result == "captured":
            e.reset_battle_state()
            new = self.db.mark(e.species.id, planet_id, captured=True, dna=1)
            self.db.add_creature(e, planet_id)
            self.db.bump("capture")
            if RARITY_ORDER.index(e.species.rarity) >= RARITY_ORDER.index("rare"):
                self.db.bump("capture_rare")
            if new["captured"]:
                self.db.add_rp(5)
            where = "your team" if e.team_slot is not None else "lab storage"
            msgs.append(f"{e.name} was sent to {where}.")
        if b.result == "win":
            self.db.bump("win")
            self.db.add_rp(2)
            self.db.update_player(battles_won=self.player["battles_won"] + 1)
        if b.alpha and b.result in ("win", "captured"):
            beaten = [x for x in self.player["alphas_beaten"].split(",") if x]
            beaten.append(str(planet_id))
            self.db.update_player(alphas_beaten=",".join(beaten))
            self.db.bump("alpha")
            self.db.add_rp(30)
            msgs.append("Alpha subdued! +30 RP")
        self.db.log_battle(planet_id, e.species.id, e.level, b.result or "fled", b.turns)

        medbay = self.db.research_level("medbay")
        for c in b.team:
            c.reset_battle_state()
            if medbay and not c.fainted:
                c.hp = min(c.max_hp, c.hp + int(c.max_hp * 0.15 * medbay))
            if c.can_evolve():
                msgs.append(c.evolve(self.data))
                self.db.mark(c.species.id, planet_id, seen=True, scanned=True, captured=True)
                self.db.bump("evolve")
            self.db.save_creature(c)
        if b.result == "loss" or all(c.fainted for c in b.team):
            self.return_to_lab()
            msgs.append("You were airlifted back to the Orbital Lab. Team restored.")
        msgs += self._refresh_missions()
        self.db.commit()
        return msgs

    # ---------------------------------------------------------- lab systems
    def can_craft(self, recipe: dict) -> bool:
        return all(self.db.qty(k) >= v for k, v in recipe["inputs"].items())

    def craft(self, recipe_id: int) -> tuple[bool, str]:
        r = next(r for r in self.data.recipes if r["id"] == recipe_id)
        if not self.can_craft(r):
            return False, "Missing materials."
        for k, v in r["inputs"].items():
            self.db.remove_item(k, v)
        self.db.add_item(r["output"], r["qty"])
        self.db.bump("craft")
        self._refresh_missions()
        self.db.commit()
        return True, f"Fabricated {r['qty']}x {self.data.items[r['output']]['name']}."

    def research_cost(self, rid: str) -> int:
        r = self.data.research[rid]
        return r["cost"] * (self.db.research_level(rid) + 1)

    def upgrade_research(self, rid: str) -> tuple[bool, str]:
        lvl = self.db.research_level(rid)
        r = self.data.research[rid]
        if lvl >= r["max_level"]:
            return False, "Already at max level."
        cost = self.research_cost(rid)
        if self.player["rp"] < cost:
            return False, f"Need {cost} RP."
        self.db.add_rp(-cost)
        self.db.execute("UPDATE research SET level = level + 1 WHERE id=?", (rid,))
        self.db.commit()
        return True, f"{r['name']} upgraded to level {lvl + 1}!"

    def sequence_cost(self) -> int:
        return max(1, round(SEQUENCE_COST * (1 - 0.25 * self.db.research_level("genetics"))))

    def sequence_genome(self, creature_id: int) -> tuple[bool, str]:
        c = next(c for c in self.db.all_creatures() if c.id == creature_id)
        if c.iv_total >= 60:
            return False, "Genome already perfect."
        if not self.db.spend_dna(c.species.id, self.sequence_cost()):
            return False, f"Need {self.sequence_cost()} {c.species.name} DNA."
        gains = []
        for k in c.ivs:
            add = self.rng.randint(1, 4)
            new = min(15, c.ivs[k] + add)
            if new > c.ivs[k]:
                gains.append(f"{k.upper()}+{new - c.ivs[k]}")
            c.ivs[k] = new
        c.hp = min(c.hp, c.max_hp)
        self.db.save_creature(c)
        self.db.bump("sequence")
        self._refresh_missions()
        self.db.commit()
        return True, "Genome sequenced: " + (", ".join(gains) or "no change")

    def accelerate_evolution(self, creature_id: int) -> tuple[bool, str]:
        c = next(c for c in self.db.all_creatures() if c.id == creature_id)
        s = c.species
        if not s.evolves_to:
            return False, f"{s.name} has no further evolution."
        if c.level < s.evolve_level - 5:
            return False, f"Must be at least level {s.evolve_level - 5}."
        if not self.db.spend_dna(s.id, ACCEL_EVOLVE_COST):
            return False, f"Need {ACCEL_EVOLVE_COST} {s.name} DNA."
        msg = c.evolve(self.data)
        self.db.mark(c.species.id, None, seen=True, scanned=True, captured=True)
        self.db.save_creature(c)
        self.db.bump("evolve")
        self._refresh_missions()
        self.db.commit()
        return True, msg

    def synthesize(self, species_id: int) -> tuple[bool, str]:
        sp = self.data.species[species_id]
        if sp.rarity == "legendary":
            return False, "Legendary genomes are too complex to synthesize."
        if not self.db.spend_dna(species_id, SYNTH_COST):
            return False, f"Need {SYNTH_COST} {sp.name} DNA."
        c = Creature.generate(self.data, sp, max(5, self.data.min_wild_level(sp)), self.rng, iv_min=4, iv_max=15)
        self.db.add_creature(c, None)
        new = self.db.mark(species_id, None, captured=True)
        if new["captured"]:
            self.db.add_rp(5)
        self.db.bump("capture")
        self._refresh_missions()
        self.db.commit()
        return True, f"Synthesized a {sp.name} from DNA!"

    def use_item_on(self, item_id: str, creature_id: int) -> tuple[bool, str]:
        c = next(c for c in self.db.all_creatures() if c.id == creature_id)
        item = self.data.items[item_id]
        if item["kind"] == "heal" and not c.fainted and c.hp < c.max_hp and self.db.remove_item(item_id):
            c.hp = min(c.max_hp, c.hp + item["value"])
        elif item["kind"] == "revive" and c.fainted and self.db.remove_item(item_id):
            c.hp = c.max_hp // 2
        else:
            return False, "That won't have any effect."
        self.db.save_creature(c)
        self.db.commit()
        return True, f"Used {item['name']} on {c.name}."

    def swap_team(self, creature_id: int) -> tuple[bool, str]:
        """Toggle a creature between team and storage."""
        team = [c.id for c in self.team()]
        if creature_id in team:
            if len(team) == 1:
                return False, "You need at least one creature in your team."
            team.remove(creature_id)
        else:
            if len(team) >= 6:
                return False, "Team is full (6). Move one to storage first."
            team.append(creature_id)
        self.db.set_team(team)
        self.db.commit()
        return True, "Team updated."

    def set_lead(self, creature_id: int):
        team = [c.id for c in self.team()]
        if creature_id in team:
            team.remove(creature_id)
            team.insert(0, creature_id)
            self.db.set_team(team)
            self.db.commit()

    # ---------------------------------------------------------- missions
    def mission_value(self, m) -> int:
        kind, target = m["kind"], m["target"]
        if kind == "scan":
            return self.db.explorer_rank()
        if kind == "scan_planet":
            return self.db.count_scanned_where("d.planet_id = ?", (int(target),))
        if kind == "scan_type":
            return self.db.count_scanned_where("(s.type1 = ? OR s.type2 = ?)", (target, target))
        if kind == "capture_rarity":
            return self.db.stat("capture_rare")
        return self.db.stat(kind)

    def _refresh_missions(self) -> list[str]:
        msgs = []
        for m in self.db.missions():
            val = min(m["goal"], self.mission_value(m))
            if val != m["progress"]:
                self.db.execute("UPDATE missions SET progress=? WHERE id=?", (val, m["id"]))
                if val >= m["goal"] and not m["claimed"]:
                    msgs.append(f"Mission complete: {m['title']}! Claim it at the Lab.")
        return msgs

    def claim_mission(self, mid: str) -> tuple[bool, str]:
        m = next(m for m in self.db.missions() if m["id"] == mid)
        if m["claimed"] or m["progress"] < m["goal"]:
            return False, "Not ready."
        self.db.execute("UPDATE missions SET claimed=1 WHERE id=?", (mid,))
        self.db.add_rp(m["reward_rp"])
        self.db.add_item(m["reward_item"], m["reward_qty"])
        self.db.commit()
        return True, (f"+{m['reward_rp']} RP, {m['reward_qty']}x "
                      f"{self.data.items[m['reward_item']]['name']}")


def default_save_path(slot: int) -> Path:
    SAVE_DIR.mkdir(exist_ok=True)
    return SAVE_DIR / f"slot{slot}.db"
