"""Planet exploration: walk the procedural surface, gather resources, find life."""
from __future__ import annotations

import math

import pygame

from .. import ui
from ..app import Scene
from ..procgen import BIOZONE, GROUND, HAZARD, NEST, NODE, PAD, ROCK
from ..rng import hash2

TILE = 32
PALETTE = {
    "forest": {GROUND: (48, 92, 52), BIOZONE: (34, 130, 70), HAZARD: (40, 90, 120), ROCK: (60, 70, 58)},
    "ocean": {GROUND: (196, 186, 140), BIOZONE: (40, 150, 140), HAZARD: (30, 80, 170), ROCK: (90, 100, 110)},
    "desert": {GROUND: (206, 170, 110), BIOZONE: (170, 140, 80), HAZARD: (150, 60, 40), ROCK: (130, 96, 70)},
    "ice": {GROUND: (200, 222, 236), BIOZONE: (150, 200, 230), HAZARD: (40, 90, 150), ROCK: (120, 140, 160)},
    "lava": {GROUND: (62, 46, 46), BIOZONE: (110, 50, 40), HAZARD: (240, 90, 30), ROCK: (34, 28, 30)},
    "artificial": {GROUND: (54, 58, 80), BIOZONE: (70, 60, 120), HAZARD: (20, 20, 30), ROCK: (90, 96, 120)},
}
MOVE_KEYS = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
             pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


class PlanetScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.s = app.session
        self.map = self.s.map
        self.planet = self.s.planet
        self.surface = self._render_map()
        self.move_cd = 0.0
        self.facing = (0, 1)
        self.buttons = [ui.Button((ui.W - 200, ui.H - 56, 180, 40), "Return to Orbit [R]", self._orbit,
                                  key=pygame.K_r, size=15)]

    def _render_map(self) -> pygame.Surface:
        pal = PALETTE[self.planet.biome]
        surf = pygame.Surface((self.map.w * TILE, self.map.h * TILE))
        seed = self.planet.seed
        for y in range(self.map.h):
            for x in range(self.map.w):
                t = self.map.tiles[y][x]
                base = pal.get(t, pal[GROUND])
                f = 0.88 + 0.24 * self.map.shade[y][x]
                r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                pygame.draw.rect(surf, shade(base, f), r)
                h = hash2(x, y, seed + 5)
                if t == BIOZONE:
                    for k in range(3):
                        ox = 6 + int(hash2(x, y, seed + k) * 20)
                        pygame.draw.line(surf, shade(base, 1.35), (r.x + ox, r.bottom - 4),
                                         (r.x + ox + 3, r.y + 8 + k * 3), 2)
                elif t == ROCK:
                    pygame.draw.polygon(surf, shade(base, 1.25), [(r.x + 4, r.bottom - 3), (r.centerx, r.y + 4 + h * 8),
                                                                  (r.right - 4, r.bottom - 3)])
                elif t == HAZARD:
                    if h < 0.3:
                        pygame.draw.circle(surf, shade(base, 1.3), (r.x + 10 + int(h * 30), r.y + 14), 3)
                elif t == GROUND and h < 0.08:
                    pygame.draw.circle(surf, shade(base, 0.75), (r.x + 16, r.y + 16), 3)
        return surf

    def _orbit(self):
        p = self.s.player
        if (p["pos_x"], p["pos_y"]) != self.map.pad:
            dist = abs(p["pos_x"] - self.map.pad[0]) + abs(p["pos_y"] - self.map.pad[1])
            self.app.toast(f"Return to the landing pad first ({dist} tiles away).", ui.WARN)
            return
        self.s.return_to_lab()
        from .lab import LabScene
        self.app.switch(LabScene(self.app))
        self.app.toast("Docked with the Orbital Lab. Team healed.", ui.GOOD)

    def handle(self, event):
        if super().handle(event):
            return True
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_e, pygame.K_SPACE):
                msg = self.s.gather()
                if msg:
                    self.app.toast(msg, ui.GOOD)
                    self.surface = self._render_map()
                else:
                    self.app.toast("Nothing to gather here. Stand next to a glowing node.", ui.MUTED, 1.5)
            elif event.key == pygame.K_l:
                if self.s.use_lure():
                    self.app.toast("Bio Lure released! Encounters doubled.", ui.GOOD)
                else:
                    self.app.toast("No Bio Lures - craft one at the Fabricator.", ui.WARN)
            elif event.key == pygame.K_ESCAPE:
                self.s.save()
                self.app.toast("Saved.", ui.GOOD, 1.2)
        return False

    def update(self, dt):
        self.move_cd -= dt
        if self.move_cd > 0:
            return
        keys = pygame.key.get_pressed()
        for k, d in MOVE_KEYS.items():
            if keys[k]:
                self.facing = d
                self.move_cd = 0.11
                event = self.s.step(*d)
                if event:
                    from .battle import BattleScene
                    kind, creature = event
                    self.app.switch(BattleScene(self.app, creature, alpha=(kind == "alpha")))
                return

    def draw(self, surf):
        p = self.s.player
        px, py = p["pos_x"], p["pos_y"]
        cam_x = max(0, min(self.map.w * TILE - ui.W, px * TILE + TILE // 2 - ui.W // 2))
        cam_y = max(0, min(self.map.h * TILE - ui.H, py * TILE + TILE // 2 - ui.H // 2))
        surf.fill(ui.BG)
        surf.blit(self.surface, (-cam_x, -cam_y))
        t = self.app.time
        # animated overlays: resource nodes, pad, nest
        for (nx, ny) in self.map.nodes:
            cx, cy = nx * TILE + 16 - cam_x, ny * TILE + 16 - cam_y
            g = 6 + 2 * math.sin(t * 4 + nx)
            pygame.draw.circle(surf, (255, 230, 120), (cx, cy), int(g + 4), 1)
            pygame.draw.polygon(surf, (250, 210, 90), [(cx, cy - 8), (cx + 6, cy), (cx, cy + 8), (cx - 6, cy)])
        ax, ay = self.map.pad
        pygame.draw.circle(surf, ui.ACCENT, (ax * TILE + 16 - cam_x, ay * TILE + 16 - cam_y), 14, 2)
        ui.text(surf, "PAD", (ax * TILE + 16 - cam_x, ay * TILE - 6 - cam_y), 11, ui.ACCENT, center=True)
        nx, ny = self.map.nest
        if str(self.planet.id) not in p["alphas_beaten"].split(","):
            r = 12 + 3 * math.sin(t * 3)
            pygame.draw.circle(surf, ui.BAD, (nx * TILE + 16 - cam_x, ny * TILE + 16 - cam_y), int(r), 3)
            ui.text(surf, "ALPHA", (nx * TILE + 16 - cam_x, ny * TILE - 8 - cam_y), 12, ui.BAD, center=True)
        # player (explorer in suit)
        cx, cy = px * TILE + 16 - cam_x, py * TILE + 16 - cam_y
        bob = math.sin(t * 8) * 1.5
        pygame.draw.ellipse(surf, (0, 0, 0), (cx - 10, cy + 10, 20, 6))
        pygame.draw.rect(surf, (230, 236, 245), (cx - 8, cy - 6 + bob, 16, 16), border_radius=5)
        pygame.draw.circle(surf, (230, 236, 245), (cx, int(cy - 9 + bob)), 8)
        fx, fy = self.facing
        pygame.draw.circle(surf, (60, 200, 230), (cx + fx * 3, int(cy - 9 + bob + fy * 2)), 5)
        pygame.draw.rect(surf, (255, 150, 60), (cx - 8, cy + 2 + bob, 16, 3))
        # HUD
        ui.panel(surf, pygame.Rect(12, 12, 420, 92), (10, 16, 30), ui.LINE)
        ui.text(surf, f"{self.planet.name}", (26, 20), 24, ui.ACCENT, bold=True)
        ui.text(surf, f"Lv {self.planet.min_level}-{self.planet.max_level}  |  {self.planet.biome.title()}  |  "
                      f"Rank {self.s.rank()}" + (f"  |  Lure {p['lure_steps']}" if p["lure_steps"] else ""),
                (26, 52), 15, ui.MUTED)
        ui.text(surf, "WASD/Arrows move  E gather  L lure  Esc save", (26, 76), 13, ui.MUTED)
        team = self.s.team()
        for i, c in enumerate(team):
            r = pygame.Rect(ui.W - 230, 12 + i * 50, 218, 46)
            ui.panel(surf, r, (10, 16, 30), ui.LINE, 8)
            surf.blit(ui.creature_sprite(c.species, 40, c.aberrant), (r.x + 3, r.y + 3))
            ui.text(surf, f"{c.name} Lv{c.level}", (r.x + 48, r.y + 5), 14)
            ui.bar(surf, (r.x + 48, r.y + 28, 158, 8), c.hp / c.max_hp, ui.hp_color(c.hp / c.max_hp))
        for b in self.buttons:
            b.draw(surf)
