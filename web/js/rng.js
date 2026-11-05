/* Deterministic cross-platform RNG + noise. Bit-for-bit identical to exodex/rng.py,
   so planets generated in the browser match the Python/Pygame version exactly. */
(function (EX) {
  'use strict';
  function mulberry32(seed) {
    let a = seed >>> 0;
    const next = function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    next.randint = (lo, hi) => lo + Math.floor(next() * (hi - lo + 1));
    next.choice = (arr) => arr[Math.floor(next() * arr.length)];
    return next;
  }
  function hash2(x, y, seed) {
    let h = (seed + x * 374761393 + y * 668265263) >>> 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
    h = (h ^ (h >>> 16)) >>> 0;
    return h / 4294967296;
  }
  const smooth = (t) => t * t * (3 - 2 * t);
  function valueNoise(x, y, seed) {
    const ix = Math.floor(x), iy = Math.floor(y);
    const fx = x - ix, fy = y - iy;
    const a = hash2(ix, iy, seed), b = hash2(ix + 1, iy, seed);
    const c = hash2(ix, iy + 1, seed), d = hash2(ix + 1, iy + 1, seed);
    const u = smooth(fx), v = smooth(fy);
    const top = a + (b - a) * u, bottom = c + (d - c) * u;
    return top + (bottom - top) * v;
  }
  function fractalNoise(x, y, seed, octaves = 3) {
    let total = 0, amp = 1, freq = 1, norm = 0;
    for (let o = 0; o < octaves; o++) {
      total += valueNoise(x * freq, y * freq, seed + o * 1013) * amp;
      norm += amp; amp *= 0.5; freq *= 2;
    }
    return total / norm;
  }
  /* Non-deterministic gameplay RNG helpers (encounters, battles). */
  const R = {
    random: Math.random,
    randint: (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1)),
    uniform: (lo, hi) => lo + Math.random() * (hi - lo),
    choice: (arr) => arr[Math.floor(Math.random() * arr.length)],
    weighted(items, weights) {
      const total = weights.reduce((a, b) => a + b, 0);
      let r = Math.random() * total;
      for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r < 0) return items[i]; }
      return items[items.length - 1];
    },
  };
  Object.assign(EX, { mulberry32, hash2, valueNoise, fractalNoise, R });
})(window.EX = window.EX || {});
