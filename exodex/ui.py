"""Pygame drawing helpers shared by every scene."""
from __future__ import annotations

import pygame

from .sprites import sprite_recipe

W, H = 1280, 720

BG = (8, 12, 24)
PANEL = (18, 26, 46)
PANEL_HI = (30, 42, 72)
LINE = (52, 70, 110)
TEXT = (226, 234, 248)
MUTED = (140, 156, 190)
ACCENT = (90, 220, 200)
WARN = (255, 190, 80)
BAD = (255, 100, 110)
GOOD = (120, 230, 140)

TYPE_COLOR = {
    "THERMAL": (240, 110, 70), "CRYO": (120, 210, 240), "HYDRO": (70, 140, 240), "LITHIC": (200, 160, 100),
    "FLORA": (100, 200, 110), "SYNTH": (170, 120, 240), "VOLT": (240, 220, 80), "PSIONIC": (240, 110, 200),
    "NEUTRAL": (170, 175, 190),
}
RARITY_COLOR = {"common": (170, 180, 200), "uncommon": (110, 220, 140), "rare": (90, 170, 255),
                "epic": (200, 120, 255), "legendary": (255, 200, 80)}

_fonts: dict = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.SysFont("segoeui,dejavusans,arial", size, bold=bold)
        _fonts[key] = f
    return _fonts[key]


def text(surf, s: str, pos, size=18, color=TEXT, bold=False, center=False, right=False):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def wrap(s: str, size: int, width: int) -> list[str]:
    f = font(size)
    words, lines, cur = s.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if f.size(test)[0] > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def text_block(surf, s: str, x, y, width, size=16, color=TEXT, spacing=4) -> int:
    for line in wrap(s, size, width):
        text(surf, line, (x, y), size, color)
        y += size + spacing
    return y


def panel(surf, rect, color=PANEL, border=LINE, radius=10):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, 1, border_radius=radius)


def bar(surf, rect, frac, color, back=(40, 48, 70)):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=4)
    f = max(0.0, min(1.0, frac))
    if f > 0:
        pygame.draw.rect(surf, color, (rect.x, rect.y, max(2, int(rect.w * f)), rect.h), border_radius=4)


def hp_color(frac: float):
    return GOOD if frac > 0.5 else WARN if frac > 0.2 else BAD


def type_badge(surf, t: str, pos, size=13) -> int:
    img = font(size, True).render(t, True, (15, 15, 25))
    r = pygame.Rect(pos[0], pos[1], img.get_width() + 12, img.get_height() + 4)
    pygame.draw.rect(surf, TYPE_COLOR.get(t, MUTED), r, border_radius=6)
    surf.blit(img, (r.x + 6, r.y + 2))
    return r.right + 6


class Button:
    def __init__(self, rect, label, on_click, enabled=True, size=18, key=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.enabled = enabled
        self.size = size
        self.key = key

    def draw(self, surf):
        hover = self.rect.collidepoint(pygame.mouse.get_pos()) and self.enabled
        col = PANEL_HI if hover else PANEL
        border = ACCENT if hover else LINE
        if not self.enabled:
            col, border = (20, 24, 36), (40, 46, 62)
        panel(surf, self.rect, col, border, 8)
        text(surf, self.label, self.rect.center, self.size, TEXT if self.enabled else MUTED, center=True)

    def handle(self, event) -> bool:
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.on_click()
            return True
        if self.key and event.type == pygame.KEYDOWN and event.key == self.key:
            self.on_click()
            return True
        return False


_sprite_cache: dict = {}


def creature_sprite(species, size: int, aberrant=False, silhouette=False) -> pygame.Surface:
    key = (species.id, size, aberrant, silhouette)
    if key in _sprite_cache:
        return _sprite_cache[key]
    surf = pygame.Surface((size, size), pygame.SRCALPHA)

    def P(x, y):
        return int(size / 2 + x * size), int(size / 2 + y * size)

    for shp in sprite_recipe(species, aberrant):
        kind = shp[0]
        color = shp[-1]
        if silhouette:
            color = (30, 40, 64)
        if kind == "circle":
            pygame.draw.circle(surf, color, P(shp[1], shp[2]), max(1, int(shp[3] * size)))
        elif kind == "ring":
            pygame.draw.circle(surf, color, P(shp[1], shp[2]), int(shp[3] * size), 2)
        elif kind == "ellipse":
            cx, cy = P(shp[1], shp[2])
            rx, ry = int(shp[3] * size), int(shp[4] * size)
            pygame.draw.ellipse(surf, color, (cx - rx, cy - ry, rx * 2, ry * 2))
        elif kind == "poly":
            pygame.draw.polygon(surf, color, [P(x, y) for x, y in shp[1]])
        elif kind == "line":
            pygame.draw.line(surf, color, P(shp[1], shp[2]), P(shp[3], shp[4]), max(1, int(shp[5] * size)))
        elif kind == "rect":
            x, y = P(shp[1], shp[2])
            pygame.draw.rect(surf, color, (x, y, int(shp[3] * size), int(shp[4] * size)),
                             border_radius=max(1, int(size * 0.04)))
    _sprite_cache[key] = surf
    return surf
