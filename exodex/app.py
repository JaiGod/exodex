"""Pygame application shell: window, main loop and scene switching."""
from __future__ import annotations

import random

import pygame

from . import ui


class Scene:
    def __init__(self, app: "App"):
        self.app = app
        self.buttons: list[ui.Button] = []

    def handle(self, event):
        for b in list(self.buttons):
            if b.handle(event):
                return True
        return False

    def update(self, dt: float):
        pass

    def draw(self, surf: pygame.Surface):
        pass


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ExoDex - Xenobiology Survey")
        self.screen = pygame.display.set_mode((ui.W, ui.H))
        self.clock = pygame.time.Clock()
        self.session = None
        self.scene: Scene | None = None
        self.running = True
        self.toasts: list[list] = []   # [text, time_left, color]
        rng = random.Random(9)
        self.stars = [(rng.randrange(ui.W), rng.randrange(ui.H), rng.random()) for _ in range(220)]
        self.time = 0.0
        self.play_accum = 0.0

    def toast(self, msg: str, color=ui.TEXT, seconds=3.0):
        self.toasts.append([msg, seconds, color])
        self.toasts = self.toasts[-4:]

    def switch(self, scene: Scene):
        self.scene = scene

    def draw_starfield(self, surf):
        surf.fill(ui.BG)
        for x, y, b in self.stars:
            tw = 0.6 + 0.4 * abs(((self.time * (0.3 + b)) % 2) - 1)
            c = int(90 + 165 * b * tw)
            surf.set_at((x, y), (c, c, min(255, c + 20)))

    def run(self):
        from .scenes.title import TitleScene
        self.switch(TitleScene(self))
        while self.running:
            dt = self.clock.tick(60) / 1000
            self.time += dt
            if self.session and self.session.db:
                self.play_accum += dt
                if self.play_accum >= 1:
                    secs = int(self.play_accum)
                    self.play_accum -= secs
                    p = self.session.player
                    self.session.db.update_player(playtime_s=p["playtime_s"] + secs)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                else:
                    self.scene.handle(event)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            self._draw_toasts(dt)
            pygame.display.flip()
        pygame.quit()

    def _draw_toasts(self, dt):
        y = 70
        for t in self.toasts:
            t[1] -= dt
            img = ui.font(17).render(t[0], True, t[2])
            r = img.get_rect(midtop=(ui.W // 2, y))
            bg = r.inflate(24, 12)
            ui.panel(self.screen, bg, (14, 20, 36), ui.ACCENT, 8)
            self.screen.blit(img, r)
            y += bg.h + 6
        self.toasts = [t for t in self.toasts if t[1] > 0]

    def quit(self):
        if self.session:
            self.session.save()
        self.running = False
