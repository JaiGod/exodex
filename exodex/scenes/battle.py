"""Turn-based battle screen."""
from __future__ import annotations

import math

import pygame

from .. import ui
from ..app import Scene
from ..battle import Battle

BIOME_SKY = {"forest": ((20, 60, 40), (60, 120, 70)), "ocean": ((20, 50, 100), (40, 140, 170)),
             "desert": ((90, 60, 40), (220, 170, 110)), "ice": ((60, 90, 130), (190, 220, 240)),
             "lava": ((40, 10, 10), (170, 60, 30)), "artificial": ((20, 16, 40), (80, 70, 140))}


class BattleScene(Scene):
    def __init__(self, app, enemy, alpha=False):
        super().__init__(app)
        self.s = app.session
        self.data = self.s.data
        self.battle: Battle = self.s.start_battle(enemy, alpha)
        self.queue: list[str] = [("ALPHA ENCOUNTER! " if alpha else "") +
                                 f"A wild {enemy.name} (Lv {enemy.level}) appeared!",
                                 f"Go, {self.battle.me.name}!"]
        self.menu = "main"
        self.finished = False
        self.shake = 0.0
        self.flash_enemy = 0.0
        self._last_hp = (self.battle.me.hp, enemy.hp)
        self.rebuild()

    # ----------------------------------------------------------- menus
    def rebuild(self):
        self.buttons = []
        if self.queue:
            return
        B = ui.Button
        x0, y0 = 700, 560
        b = self.battle
        if self.menu == "main":
            labels = [("Fight", lambda: self._menu("fight")), ("Scan", lambda: self._act(("scan",))),
                      ("Capture", lambda: self._menu("capture")), ("Items", lambda: self._menu("items")),
                      ("Swap", lambda: self._menu("swap")), ("Flee", lambda: self._act(("flee",)))]
            keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]
            for i, (lab, fn) in enumerate(labels):
                self.buttons.append(B((x0 + (i % 3) * 190, y0 + (i // 3) * 60, 180, 52), f"{lab}", fn, key=keys[i]))
        else:
            if self.menu == "fight":
                for i, mid in enumerate(b.me.moves):
                    m = self.data.moves[mid]
                    eff = self.data.effectiveness(m.type, b.enemy.species.types) if m.power else 1
                    hint = " !!" if eff >= 2 else " -" if eff < 1 else ""
                    self.buttons.append(B((x0 + (i % 2) * 285, y0 + (i // 2) * 60, 275, 52),
                                          f"{m.name}  [{m.power or '-'}]{hint}",
                                          lambda i=i: self._act(("move", i)), size=16,
                                          key=[pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4][i]))
            elif self.menu == "capture":
                for i, pod in enumerate(("pod", "pod_plus", "pod_max")):
                    q = self.s.db.qty(pod)
                    pct = int(b.capture_chance(pod) * 100)
                    self.buttons.append(B((x0, y0 - 66 + i * 50, 380, 44),
                                          f"{self.data.items[pod]['name']} x{q}  (~{pct}%)",
                                          lambda p=pod: self._act(("capture", p)), enabled=q > 0, size=16))
            elif self.menu == "items":
                opts = [("medgel", b.active), ("medgel_plus", b.active)]
                fainted = next((i for i, c in enumerate(b.team) if c.fainted), None)
                if fainted is not None:
                    opts.append(("revive", fainted))
                for i, (item, target) in enumerate(opts):
                    q = self.s.db.qty(item)
                    self.buttons.append(B((x0, y0 - 66 + i * 50, 380, 44),
                                          f"{self.data.items[item]['name']} x{q} -> {b.team[target].name}",
                                          lambda it=item, t=target: self._act(("item", it, t)), enabled=q > 0,
                                          size=16))
            elif self.menu == "swap":
                for i, c in enumerate(b.team):
                    self.buttons.append(B((x0 + (i % 2) * 285, y0 - 66 + (i // 2) * 50, 275, 44),
                                          f"{c.name} Lv{c.level} {c.hp}/{c.max_hp}",
                                          lambda i=i: self._act(("swap", i)),
                                          enabled=not c.fainted and i != b.active, size=15))
            self.buttons.append(B((x0 + 400, y0 + 60, 160, 44), "Back", lambda: self._menu("main"),
                                  key=pygame.K_ESCAPE, size=16))

    def _menu(self, m):
        self.menu = m
        self.rebuild()

    def _act(self, action):
        hp_before = (self.battle.me.hp, self.battle.enemy.hp)
        self.queue += self.battle.act(action)
        if self.battle.enemy.hp < hp_before[1]:
            self.flash_enemy = 0.4
        if self.battle.me.hp < hp_before[0]:
            self.shake = 0.35
        self.menu = "main"
        if self.battle.result and not self.finished:
            self.finished = True
            self.queue += self.s.finish_battle(self.battle)
        self.rebuild()

    def _advance(self):
        if self.queue:
            self.queue.pop(0)
        if not self.queue and self.finished:
            from .lab import LabScene
            from .planet import PlanetScene
            self.app.switch(PlanetScene(self.app) if self.s.map else LabScene(self.app))
            return
        self.rebuild()

    def handle(self, event):
        if self.queue:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_z)) or \
                    (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self._advance()
            return True
        return super().handle(event)

    def update(self, dt):
        self.shake = max(0, self.shake - dt)
        self.flash_enemy = max(0, self.flash_enemy - dt)

    # ----------------------------------------------------------- drawing
    def _info(self, surf, c, rect, show_xp):
        ui.panel(surf, rect, (14, 20, 36), ui.LINE)
        ui.text(surf, f"{c.name}", (rect.x + 14, rect.y + 10), 22, bold=True)
        ui.text(surf, f"Lv {c.level}", (rect.right - 14, rect.y + 14), 18, ui.MUTED, right=True)
        bx = rect.x + 14
        for t in c.species.types:
            bx = ui.type_badge(surf, t, (bx, rect.y + 42), 11)
        if c.status:
            ui.text(surf, c.status.upper(), (bx + 4, rect.y + 42), 13, ui.WARN, bold=True)
        frac = c.hp / c.max_hp
        ui.bar(surf, (rect.x + 14, rect.y + 70, rect.w - 28, 12), frac, ui.hp_color(frac))
        ui.text(surf, f"{c.hp}/{c.max_hp} HP", (rect.right - 14, rect.y + 86), 14, ui.MUTED, right=True)
        if show_xp:
            from ..creature import xp_for_level
            cur, nxt = xp_for_level(c.level), xp_for_level(c.level + 1)
            ui.bar(surf, (rect.x + 14, rect.y + 90, 160, 5), (c.xp - cur) / max(1, nxt - cur), ui.ACCENT)

    def draw(self, surf):
        b = self.battle
        top, bottom = BIOME_SKY[self.s.planet.biome if self.s.planet else "forest"]
        for y in range(0, 520, 4):
            f = y / 520
            col = tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3))
            pygame.draw.rect(surf, col, (0, y, ui.W, 4))
        pygame.draw.rect(surf, (12, 16, 28), (0, 520, ui.W, ui.H - 520))
        t = self.app.time
        ox = int(math.sin(t * 60) * 6) if self.shake > 0 else 0
        # platforms
        pygame.draw.ellipse(surf, tuple(max(0, c - 30) for c in bottom), (820, 300, 300, 60))
        pygame.draw.ellipse(surf, tuple(max(0, c - 30) for c in bottom), (150, 450, 360, 70))
        # enemy
        if not b.enemy.fainted or self.queue:
            spr = ui.creature_sprite(b.enemy.species, 260, b.enemy.aberrant)
            if self.flash_enemy > 0 and int(t * 20) % 2:
                spr = spr.copy()
                spr.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            surf.blit(spr, (840, 80 + math.sin(t * 2) * 6))
        # player creature
        me = b.me
        surf.blit(ui.creature_sprite(me.species, 280, me.aberrant), (190 + ox, 210 + math.sin(t * 2 + 1) * 5))
        self._info(surf, b.enemy, pygame.Rect(60, 60, 380, 112), False)
        if b.alpha:
            ui.text(surf, "ALPHA", (60, 36), 18, ui.BAD, bold=True)
        self._info(surf, me, pygame.Rect(ui.W - 460, 380, 400, 112), True)
        # message box
        box = pygame.Rect(20, 540, 660 if not self.queue else ui.W - 40, 160)
        ui.panel(surf, box, (14, 20, 36), ui.ACCENT)
        if self.queue:
            ui.text_block(surf, self.queue[0], box.x + 22, box.y + 24, box.w - 44, 24)
            if int(t * 2) % 2:
                ui.text(surf, "v  (Space / click)", (box.right - 20, box.bottom - 30), 14, ui.MUTED, right=True)
        else:
            hint = {"main": f"What will {me.name} do?", "fight": "Choose a move. !! = super effective",
                    "capture": "Weaken it first - lower HP raises capture odds.",
                    "items": "Use an item.", "swap": "Switch the active creature."}[self.menu]
            ui.text_block(surf, hint, box.x + 22, box.y + 24, box.w - 44, 22)
            pods = self.s.db.qty("pod") + self.s.db.qty("pod_plus") + self.s.db.qty("pod_max")
            ui.text(surf, f"Pods: {pods}   MedGels: {self.s.db.qty('medgel')}", (box.x + 22, box.bottom - 34), 15,
                    ui.MUTED)
        for btn in self.buttons:
            btn.draw(surf)
