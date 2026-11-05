"""Deterministic, cross-platform random numbers.

ExoDex generates planet maps procedurally. The same algorithms are implemented
in Python (this file) and JavaScript (web/js/rng.js) with identical 32-bit
integer maths, so a planet generated from a seed looks *exactly* the same in the
desktop game and in the browser build -- which also lets save files move
between the two versions.
"""
from __future__ import annotations

MASK = 0xFFFFFFFF


def imul(a: int, b: int) -> int:
    """32-bit integer multiply (like JavaScript's Math.imul), unsigned result."""
    return (a * b) & MASK


class Mulberry32:
    """Tiny, fast seeded PRNG (mulberry32). Produces floats in [0, 1)."""

    def __init__(self, seed: int):
        self.state = seed & MASK

    def random(self) -> float:
        self.state = (self.state + 0x6D2B79F5) & MASK
        t = self.state
        t = imul(t ^ (t >> 15), t | 1)
        t = ((t + imul(t ^ (t >> 7), t | 61)) & MASK) ^ t
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    def randint(self, lo: int, hi: int) -> int:
        """Inclusive integer range."""
        return lo + int(self.random() * (hi - lo + 1))

    def choice(self, seq):
        return seq[int(self.random() * len(seq))]


def hash2(x: int, y: int, seed: int) -> float:
    """Hash a lattice point to a float in [0, 1)."""
    h = (seed + x * 374761393 + y * 668265263) & MASK
    h = imul(h ^ (h >> 13), 1274126177)
    h = (h ^ (h >> 16)) & MASK
    return h / 4294967296


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def value_noise(x: float, y: float, seed: int) -> float:
    ix, iy = int(x // 1), int(y // 1)
    fx, fy = x - ix, y - iy
    a = hash2(ix, iy, seed)
    b = hash2(ix + 1, iy, seed)
    c = hash2(ix, iy + 1, seed)
    d = hash2(ix + 1, iy + 1, seed)
    u, v = _smooth(fx), _smooth(fy)
    top = a + (b - a) * u
    bottom = c + (d - c) * u
    return top + (bottom - top) * v


def fractal_noise(x: float, y: float, seed: int, octaves: int = 3) -> float:
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        total += value_noise(x * freq, y * freq, seed + o * 1013) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm
