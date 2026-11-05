"""Title screen (save slots) and new-game starter selection."""
from __future__ import annotations

import math
import sqlite3

import pygame

from .. import ui
from ..app import Scene
from ..data import load
from ..session import GameSession, default_save_path


def slot_summary(slot: int) -> dict | None:
    path = default_save_path(slot)
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(path)
        name, rp, play = con.execute("SELECT name, rp, playtime_s FROM player WHERE id=1").fetchone()
        scanned = con.execute("SELECT COALESCE(SUM(scanned),0) FROM discoveries").fetchone()[0]
        caught = con.execute("SELECT COUNT(*) FROM creatures").fetchone()[0]
        con.close()
        return dict(name=name, rp=rp, play=play, scanned=scanned, caught=caught)
    except sqlite3.Error:
        return None


class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.data = load()
        self.preview = [self.data.species[i] for i in (1, 37, 92, 140, 211, 217)]
        self._build()

    def _build(self):
        self.buttons = []
        self._cache = {s: slot_summary(s) for s in (1, 2, 3)}
        for slot in (1, 2, 3):
            x = 220 + (slot - 1) * 290
            info = self._cache[slot]
            if info:
                self.buttons.append(ui.Button((x + 20, 560, 110, 40), "Continue", lambda s=slot: self._load(s)))
                self.buttons.append(ui.Button((x + 140, 560, 110, 40), "New", lambda s=slot: self._new(s)))
            else:
                self.buttons.append(ui.Button((x + 20, 560, 230, 40), "New Expedition", lambda s=slot: self._new(s)))
        self.buttons.append(ui.Button((ui.W - 140, ui.H - 60, 110, 38), "Quit", self.app.quit, key=pygame.K_ESCAPE))

    def _load(self, slot):
        self.app.session = GameSession.load_game(default_save_path(slot))
        from .lab import LabScene
        from .planet import PlanetScene
        self.app.switch(PlanetScene(self.app) if self.app.session.map else LabScene(self.app))
        self.app.toast(f"Welcome back, {self.app.session.player['name']}.")

    def _new(self, slot):
        self.app.switch(StarterScene(self.app, slot))

    def draw(self, surf):
        self.app.draw_starfield(surf)
        t = self.app.time
        ui.text(surf, "EXODEX", (ui.W // 2, 120), 96, ui.ACCENT, bold=True, center=True)
        ui.text(surf, "Xenobiology Survey Program  -  discover, scan & study alien life", (ui.W // 2, 190), 22,
                ui.MUTED, center=True)
        for i, sp in enumerate(self.preview):
            x = 190 + i * 180
            y = 300 + math.sin(t * 1.5 + i) * 10
            surf.blit(ui.creature_sprite(sp, 120), (x - 60, y - 60))
        for slot in (1, 2, 3):
            x = 220 + (slot - 1) * 290
            r = pygame.Rect(x, 420, 270, 200)
            ui.panel(surf, r)
            ui.text(surf, f"SAVE SLOT {slot}", (x + 20, 435), 16, ui.MUTED, bold=True)
            info = self._cache[slot]
            if info:
                ui.text(surf, info["name"], (x + 20, 462), 24, ui.TEXT, bold=True)
                ui.text(surf, f"ExoDex: {info['scanned']}  |  Specimens: {info['caught']}", (x + 20, 498), 16)
                ui.text(surf, f"RP: {info['rp']}  |  Time: {info['play'] // 3600}h {info['play'] // 60 % 60}m",
                        (x + 20, 522), 16, ui.MUTED)
            else:
                ui.text(surf, "Empty", (x + 20, 470), 22, ui.MUTED)
        for b in self.buttons:
            b.draw(surf)
        ui.text(surf, "Python + Pygame + SQLite  |  by Jaineil R.", (20, ui.H - 34), 15, ui.MUTED)


class StarterScene(Scene):
    def __init__(self, app, slot: int):
        super().__init__(app)
        self.slot = slot
        self.data = load()
        self.starters = self.data.starters()
        self.choice = 0
        self.name = "Explorer"
        self.buttons = [
            ui.Button((ui.W // 2 - 120, 620, 240, 50), "Begin Expedition", self._start, key=pygame.K_RETURN),
            ui.Button((30, ui.H - 60, 110, 38), "Back", self._back, key=pygame.K_ESCAPE),
        ]

    def _back(self):
        self.app.switch(TitleScene(self.app))

    def _start(self):
        sp = self.starters[self.choice]
        self.app.session = GameSession.new_game(default_save_path(self.slot), self.name.strip() or "Explorer", sp.id)
        from .lab import LabScene
        self.app.switch(LabScene(self.app))
        self.app.toast(f"{sp.name} joined your research team!", ui.GOOD)

    def handle(self, event):
        if super().handle(event):
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.choice = (self.choice - 1) % 3
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.choice = (self.choice + 1) % 3
            elif event.unicode and event.unicode.isprintable() and len(self.name) < 16:
                self.name += event.unicode
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(3):
                if pygame.Rect(170 + i * 330, 200, 280, 360).collidepoint(event.pos):
                    self.choice = i
        return False

    def draw(self, surf):
        self.app.draw_starfield(surf)
        ui.text(surf, "Choose your first research partner", (ui.W // 2, 60), 34, ui.TEXT, bold=True, center=True)
        ui.text(surf, f"Explorer name: {self.name}_", (ui.W // 2, 120), 22, ui.ACCENT, center=True)
        ui.text(surf, "(type to rename, arrows or click to choose)", (ui.W // 2, 152), 15, ui.MUTED, center=True)
        for i, sp in enumerate(self.starters):
            r = pygame.Rect(170 + i * 330, 200, 280, 380)
            ui.panel(surf, r, ui.PANEL_HI if i == self.choice else ui.PANEL, ui.ACCENT if i == self.choice else ui.LINE)
            surf.blit(ui.creature_sprite(sp, 170), (r.centerx - 85, r.y + 10))
            ui.text(surf, sp.name, (r.centerx, r.y + 195), 26, bold=True, center=True)
            ui.type_badge(surf, sp.type1, (r.centerx - 40, r.y + 215))
            ui.text(surf, sp.kingdom, (r.centerx, r.y + 255), 15, ui.MUTED, center=True)
            ui.text_block(surf, sp.description, r.x + 18, r.y + 282, r.w - 36, 14, ui.TEXT)
        for b in self.buttons:
            b.draw(surf)
