"""Procedural generation: planet surface maps and wild encounters."""
from __future__ import annotations

import random
from collections import deque

from .creature import Creature
from .data import GameData, Planet, Species
from .rng import Mulberry32, fractal_noise

MAP_W, MAP_H = 56, 40

GROUND, BIOZONE, HAZARD, ROCK, NODE, PAD, NEST = range(7)
WALKABLE = {GROUND, BIOZONE, NODE, PAD, NEST}


class PlanetMap:
    """A deterministic tile map generated from a planet's seed."""

    def __init__(self, planet: Planet):
        self.planet = planet
        self.w, self.h = MAP_W, MAP_H
        self.tiles: list[list[int]] = [[GROUND] * self.w for _ in range(self.h)]
        self.shade: list[list[float]] = [[0.0] * self.w for _ in range(self.h)]
        self.pad = (0, 0)
        self.nest = (0, 0)
        self.nodes: set[tuple[int, int]] = set()
        self._generate()

    def _generate(self):
        seed = self.planet.seed
        for y in range(self.h):
            for x in range(self.w):
                e = fractal_noise(x / 9.0, y / 9.0, seed)
                m = fractal_noise(x / 6.0, y / 6.0, seed + 77)
                self.shade[y][x] = m
                edge = min(x, y, self.w - 1 - x, self.h - 1 - y)
                if edge == 0:
                    t = ROCK
                elif e < 0.34:
                    t = HAZARD
                elif e > 0.70:
                    t = ROCK
                elif m > 0.55:
                    t = BIOZONE
                else:
                    t = GROUND
                self.tiles[y][x] = t

        # landing pad: nearest walkable tile to the centre, with a cleared 3x3 area
        cx, cy = self.w // 2, self.h // 2
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                self.tiles[cy + dy][cx + dx] = GROUND
        self.tiles[cy][cx] = PAD
        self.pad = (cx, cy)

        reach = self.reachable(self.pad)
        rng = Mulberry32(seed)
        order = sorted(reach)  # deterministic order across platforms
        # alpha nest: farthest reachable tile from the pad
        dist = self._distances(self.pad)
        far = max(order, key=lambda p: (dist[p], -p[1], -p[0]))
        self.nest = far
        self.tiles[far[1]][far[0]] = NEST
        # resource nodes on reachable ground
        candidates = [p for p in order if self.tiles[p[1]][p[0]] in (GROUND, BIOZONE)
                      and abs(p[0] - cx) + abs(p[1] - cy) > 3]
        for _ in range(26):
            if not candidates:
                break
            i = int(rng.random() * len(candidates))
            p = candidates.pop(i)
            self.tiles[p[1]][p[0]] = NODE
            self.nodes.add(p)

    def _neighbors(self, p):
        x, y = p
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < self.w and 0 <= ny < self.h and self.tiles[ny][nx] in WALKABLE:
                yield nx, ny

    def _distances(self, start):
        dist = {start: 0}
        q = deque([start])
        while q:
            p = q.popleft()
            for n in self._neighbors(p):
                if n not in dist:
                    dist[n] = dist[p] + 1
                    q.append(n)
        return dist

    def reachable(self, start) -> set:
        return set(self._distances(start))

    def tile(self, x: int, y: int) -> int:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.tiles[y][x]
        return ROCK

    def walkable(self, x: int, y: int) -> bool:
        return self.tile(x, y) in WALKABLE

    def harvest(self, x: int, y: int) -> bool:
        if (x, y) in self.nodes:
            self.nodes.discard((x, y))
            self.tiles[y][x] = GROUND
            return True
        return False


# ---------------------------------------------------------------- encounters
def encounter_pool(data: GameData, planet: Planet) -> list[Species]:
    return [s for s in data.species.values() if planet.biome in s.biomes and s.rarity != "legendary"]


def roll_wild(data: GameData, planet: Planet, rng: random.Random, lure: bool = False) -> Creature:
    pool = encounter_pool(data, planet)
    weights = []
    for s in pool:
        w = data.rarity_weight[s.rarity]
        if lure and s.rarity in ("rare", "epic"):
            w *= 3
        # evolved species are rarer in the wild
        w /= (1 + (s.stage - 1) * 1.5)
        # stage gates: an evolved species only spawns if its minimum level fits on this planet
        if data.min_wild_level(s) > planet.max_level + 2:
            w = 0
        weights.append(w)
    sp = rng.choices(pool, weights=weights)[0]
    level = max(rng.randint(planet.min_level, planet.max_level), data.min_wild_level(sp))
    return Creature.generate(data, sp, level, rng)


def alpha_creature(data: GameData, planet: Planet, rng: random.Random) -> Creature:
    sp = data.species[planet.alpha_species]
    c = Creature.generate(data, sp, planet.alpha_level, rng, trait="Hardy")
    c.ivs = {k: 15 for k in c.ivs}
    c.hp = c.max_hp
    return c
