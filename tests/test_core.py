"""Core gameplay tests (no Pygame needed):  python -m unittest discover tests"""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from exodex.battle import Battle
from exodex.creature import Creature, xp_for_level
from exodex.data import load
from exodex.procgen import HAZARD, MAP_H, MAP_W, NEST, PAD, PlanetMap, roll_wild
from exodex.rng import Mulberry32, fractal_noise
from exodex.session import GameSession


class DataTests(unittest.TestCase):
    def setUp(self):
        self.data = load()

    def test_catalogue_size(self):
        self.assertGreaterEqual(len(self.data.species), 200)
        self.assertEqual(len(self.data.planets), 6)

    def test_evolution_chains_valid(self):
        for s in self.data.species.values():
            if s.evolves_to:
                nxt = self.data.species[s.evolves_to]
                self.assertEqual(nxt.family, s.family)
                self.assertEqual(nxt.stage, s.stage + 1)
                self.assertIsNotNone(s.evolve_level)

    def test_every_species_has_moves(self):
        for s in self.data.species.values():
            self.assertTrue(s.moves_at(1), s.name)

    def test_type_chart(self):
        self.assertEqual(self.data.effectiveness("HYDRO", ["THERMAL"]), 2.0)
        self.assertEqual(self.data.effectiveness("THERMAL", ["HYDRO"]), 0.5)
        self.assertEqual(self.data.effectiveness("NEUTRAL", ["HYDRO"]), 1.0)

    def test_three_starters(self):
        self.assertEqual(len(self.data.starters()), 3)


class RngTests(unittest.TestCase):
    def test_mulberry_known_values(self):
        # Reference values shared with web/js/rng.js (checked in the browser test too)
        r = Mulberry32(12345)
        vals = [round(r.random(), 10) for _ in range(3)]
        self.assertEqual(vals, MULBERRY_12345)

    def test_noise_range(self):
        for i in range(200):
            v = fractal_noise(i * 0.37, i * 0.11, 42)
            self.assertTrue(0 <= v < 1)


MULBERRY_12345 = [0.9797282678, 0.3067522645, 0.4842054215]


class MapTests(unittest.TestCase):
    def test_maps_deterministic_and_connected(self):
        data = load()
        for p in data.planets.values():
            a, b = PlanetMap(p), PlanetMap(p)
            self.assertEqual(a.tiles, b.tiles)
            self.assertEqual(a.tile(*a.pad), PAD)
            self.assertEqual(a.tile(*a.nest), NEST)
            self.assertIn(a.nest, a.reachable(a.pad))
            self.assertGreater(len(a.nodes), 10)
            hazard = sum(row.count(HAZARD) for row in a.tiles)
            self.assertLess(hazard, MAP_W * MAP_H * 0.6)


class CreatureTests(unittest.TestCase):
    def test_level_up_and_evolution(self):
        data = load()
        sp = data.starters()[0]
        c = Creature.generate(data, sp, 5, random.Random(1))
        c.gain_xp(xp_for_level(sp.evolve_level) - c.xp, data)
        self.assertEqual(c.level, sp.evolve_level)
        self.assertTrue(c.can_evolve())
        c.evolve(data)
        self.assertEqual(c.species.id, sp.evolves_to)
        self.assertLessEqual(len(c.moves), 4)


class BattleTests(unittest.TestCase):
    def test_battle_runs_to_completion(self):
        data = load()
        rng = random.Random(7)
        for _ in range(30):
            team = [Creature.generate(data, data.starters()[0], 12, rng)]
            enemy = roll_wild(data, data.planets[1], rng)
            b = Battle(data, team, enemy, rng=rng)
            for _turn in range(200):
                if b.result:
                    break
                b.act(("move", rng.randrange(len(b.me.moves))))
            self.assertIn(b.result, ("win", "loss"))

    def test_capture_chance_increases_when_weak(self):
        data = load()
        rng = random.Random(3)
        enemy = roll_wild(data, data.planets[1], rng)
        b = Battle(data, [Creature.generate(data, data.starters()[0], 10, rng)], enemy, rng=rng)
        full = b.capture_chance("pod")
        enemy.hp = 1
        self.assertGreater(b.capture_chance("pod"), full)
        self.assertGreaterEqual(b.capture_chance("pod_max"), b.capture_chance("pod"))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        data = load()
        self.s = GameSession.new_game(self.path, "Tester", data.starters()[1].id, rng=random.Random(5))

    def tearDown(self):
        self.s.db.close()
        self.tmp.cleanup()

    def test_new_game_state(self):
        self.assertEqual(len(self.s.team()), 1)
        self.assertEqual(self.s.db.qty("pod"), 5)
        self.assertEqual(self.s.rank(), 1)

    def test_full_loop_explore_battle_capture_save_load(self):
        s = self.s
        ok, _ = s.travel(1)
        self.assertTrue(ok)
        self.assertEqual(s.db.qty("fuel"), 3)  # Verdance is fuel-free
        event = None
        for i in range(4000):
            d = [(1, 0), (-1, 0), (0, 1), (0, -1)][s.rng.randrange(4)]
            event = s.step(*d)
            if event and event[0] == "encounter":
                break
        self.assertIsNotNone(event)
        b = s.start_battle(event[1])
        b.act(("scan",))
        b.enemy.hp = 1
        for _ in range(20):
            if b.result:
                break
            if s.db.qty("pod") == 0:
                s.db.add_item("pod", 5)
            b.act(("capture", "pod"))
        if b.result != "captured":
            b.result = "captured"
        msgs = s.finish_battle(b)
        self.assertTrue(any("ExoDex" in m or "sent to" in m for m in msgs))
        self.assertEqual(len(s.db.all_creatures()), 2)
        s.save()
        s.db.close()
        s2 = GameSession.load_game(self.path)
        self.assertEqual(len(s2.db.all_creatures()), 2)
        self.assertIsNotNone(s2.map)
        self.s = s2

    def test_crafting_and_research(self):
        s = self.s
        s.db.add_item("silica", 2)
        recipe = next(r for r in s.data.recipes if r["output"] == "pod" and "silica" in r["inputs"])
        ok, _ = s.craft(recipe["id"])
        self.assertTrue(ok)
        self.assertEqual(s.db.qty("pod"), 7)
        s.db.add_rp(100)
        ok, _ = s.upgrade_research("containment")
        self.assertTrue(ok)
        self.assertEqual(s.db.research_level("containment"), 1)

    def test_missions_complete(self):
        s = self.s
        s.db.add_item("silica", 10)
        s.db.add_item("iron", 10)
        recipe = next(r for r in s.data.recipes if r["output"] == "pod" and "silica" in r["inputs"])
        for _ in range(3):
            s.craft(recipe["id"])
        ok, msg = s.claim_mission("m03")
        self.assertTrue(ok, msg)

    def test_save_is_plain_sqlite(self):
        self.s.save()
        con = sqlite3.connect(self.path)
        n = con.execute("SELECT COUNT(*) FROM species").fetchone()[0]
        self.assertGreaterEqual(n, 200)
        row = con.execute("SELECT s.name FROM creatures c JOIN species s ON s.id=c.species_id").fetchone()
        self.assertTrue(row[0])
        con.close()


if __name__ == "__main__":
    unittest.main()
