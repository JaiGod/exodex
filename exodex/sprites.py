"""Procedural creature sprites.

Every species has a sprite_seed. `sprite_recipe` turns (species, aberrant) into a
list of vector primitives in a normalised [-0.5, 0.5] box, so the same alien can
be drawn at any size by any renderer (Pygame here, <canvas> in the web build).
"""
from __future__ import annotations

import colorsys
import math

from .data import Species
from .rng import Mulberry32


def hsl(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def sprite_recipe(sp: Species, aberrant: bool = False) -> list[tuple]:
    rng = Mulberry32(sp.sprite_seed)
    hue = sp.hue + (150 if aberrant else 0)
    body = hsl(hue, 0.62, 0.55)
    dark = hsl(hue, 0.55, 0.30)
    accent = hsl(hue + 35 + rng.random() * 40, 0.70, 0.66)
    glow = hsl(hue + 180, 0.9, 0.7)
    sc = 0.62 + 0.13 * sp.stage + (0.12 if sp.rarity == "legendary" else 0)
    sc = min(sc, 1.0)
    shapes: list[tuple] = []
    k = sp.kingdom
    eye_y = -0.08 * sc
    eyes = 1 + int(rng.random() * 3)

    def spikes(cx, cy, r, n, length, color):
        for i in range(n):
            a = -math.pi / 2 + (i - (n - 1) / 2) * 0.45
            shapes.append(("poly", [(cx + math.cos(a - 0.15) * r, cy + math.sin(a - 0.15) * r),
                                    (cx + math.cos(a) * (r + length), cy + math.sin(a) * (r + length)),
                                    (cx + math.cos(a + 0.15) * r, cy + math.sin(a + 0.15) * r)], color))

    if k == "Fauna":
        legs = 2 + 2 * int(rng.random() * 2)
        for i in range(legs):
            x = (-0.18 + 0.36 * i / max(1, legs - 1)) * sc
            shapes.append(("line", x, 0.08 * sc, x * 1.15, 0.36 * sc, max(0.03, 0.05 * sc), dark))
        shapes.append(("poly", [(0.2 * sc, 0.05 * sc), (0.46 * sc, -0.12 * sc - rng.random() * 0.1),
                                (0.24 * sc, 0.14 * sc)], dark))
        shapes.append(("ellipse", 0, 0.06 * sc, 0.3 * sc, 0.2 * sc, body))
        shapes.append(("ellipse", 0, 0.12 * sc, 0.2 * sc, 0.09 * sc, accent))
        shapes.append(("circle", -0.16 * sc, -0.1 * sc, 0.17 * sc, body))
        if rng.random() < 0.6:
            spikes(-0.16 * sc, -0.1 * sc, 0.15 * sc, 2 + int(rng.random() * 3), 0.12 * sc, accent)
        eye_cx = -0.18 * sc
    elif k == "Flora":
        shapes.append(("rect", -0.03 * sc, 0.0, 0.06 * sc, 0.42 * sc, dark))
        for side in (-1, 1):
            shapes.append(("ellipse", side * 0.13 * sc, 0.22 * sc, 0.12 * sc, 0.05 * sc, hsl(120, 0.5, 0.4)))
        petals = 5 + int(rng.random() * 4)
        for i in range(petals):
            a = i / petals * math.tau
            shapes.append(("circle", math.cos(a) * 0.2 * sc, -0.08 * sc + math.sin(a) * 0.2 * sc, 0.11 * sc,
                           accent))
        shapes.append(("circle", 0, -0.08 * sc, 0.17 * sc, body))
        eye_cx = 0
    elif k == "Fungoid":
        shapes.append(("rect", -0.09 * sc, -0.02 * sc, 0.18 * sc, 0.36 * sc, hsl(hue, 0.25, 0.8)))
        pts = [(math.cos(math.pi + i / 12 * math.pi) * 0.38 * sc, -0.02 * sc + math.sin(math.pi + i / 12 * math.pi)
                * 0.32 * sc) for i in range(13)]
        shapes.append(("poly", pts, body))
        for _ in range(4 + int(rng.random() * 4)):
            shapes.append(("circle", (rng.random() - 0.5) * 0.5 * sc, -0.12 * sc - rng.random() * 0.14 * sc,
                           0.035 * sc + rng.random() * 0.02, accent))
        eye_cx = 0
        eye_y = 0.1 * sc
    elif k == "Microbe":
        n = 14
        pts = []
        for i in range(n):
            a = i / n * math.tau
            r = (0.3 + rng.random() * 0.08) * sc
            pts.append((math.cos(a) * r, math.sin(a) * r * 0.9))
        for (x, y) in pts[::2]:
            shapes.append(("line", x, y, x * 1.35, y * 1.35, 0.02, dark))
        shapes.append(("poly", pts, body))
        shapes.append(("circle", 0.08 * sc, 0.1 * sc, 0.1 * sc, accent))
        shapes.append(("circle", -0.12 * sc, 0.12 * sc, 0.05 * sc, glow))
        eye_cx = -0.02 * sc
    elif k == "Mechanoid":
        shapes.append(("line", 0, -0.25 * sc, 0.1 * sc, -0.46 * sc, 0.02, dark))
        shapes.append(("circle", 0.1 * sc, -0.46 * sc, 0.04 * sc, glow))
        for side in (-1, 1):
            shapes.append(("circle", side * 0.2 * sc, 0.3 * sc, 0.09 * sc, dark))
        shapes.append(("rect", -0.3 * sc, -0.26 * sc, 0.6 * sc, 0.5 * sc, body))
        shapes.append(("rect", -0.22 * sc, -0.18 * sc, 0.44 * sc, 0.16 * sc, dark))
        shapes.append(("rect", -0.24 * sc, 0.1 * sc, 0.48 * sc, 0.05 * sc, accent))
        eye_cx = 0
        eye_y = -0.1 * sc
    else:  # Crystalline
        for _ in range(3 + int(rng.random() * 3)):
            x = (rng.random() - 0.5) * 0.5 * sc
            h = (0.25 + rng.random() * 0.25) * sc
            w = (0.08 + rng.random() * 0.06) * sc
            shapes.append(("poly", [(x, 0.3 * sc - h * 1.6), (x + w, 0.3 * sc - h * 0.6), (x, 0.3 * sc),
                                    (x - w, 0.3 * sc - h * 0.6)], accent))
        shapes.append(("poly", [(0, -0.3 * sc), (0.24 * sc, 0.0), (0.12 * sc, 0.3 * sc), (-0.12 * sc, 0.3 * sc),
                                (-0.24 * sc, 0.0)], body))
        shapes.append(("poly", [(0, -0.3 * sc), (0.24 * sc, 0.0), (0, 0.05 * sc)], dark))
        eye_cx = -0.02 * sc

    # eyes
    spacing = 0.09 * sc
    for i in range(eyes):
        ex = eye_cx + (i - (eyes - 1) / 2) * spacing
        shapes.append(("circle", ex, eye_y, 0.045 * sc, (245, 245, 250)))
        shapes.append(("circle", ex + 0.01 * sc, eye_y + 0.005, 0.022 * sc, (20, 20, 30)))
    if sp.rarity == "legendary":
        shapes.insert(0, ("ring", 0, 0, 0.48, glow))
    return shapes
