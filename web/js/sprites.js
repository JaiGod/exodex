/* Procedural creature sprites (port of exodex/sprites.py) drawn onto <canvas>. */
(function (EX) {
  'use strict';
  const TAU = Math.PI * 2;
  const hsl = (h, s, l) => `hsl(${((h % 360) + 360) % 360},${Math.round(s * 100)}%,${Math.round(l * 100)}%)`;

  function recipe(sp, aberrant) {
    const rng = EX.mulberry32(sp.sprite_seed);
    const hue = sp.hue + (aberrant ? 150 : 0);
    const body = hsl(hue, 0.62, 0.55), dark = hsl(hue, 0.55, 0.30);
    const accent = hsl(hue + 35 + rng() * 40, 0.70, 0.66), glow = hsl(hue + 180, 0.9, 0.7);
    const sc = Math.min(1, 0.62 + 0.13 * sp.stage + (sp.rarity === 'legendary' ? 0.12 : 0));
    const S = [];
    const k = sp.kingdom;
    let eyeY = -0.08 * sc, eyeCx = 0;
    const eyes = 1 + Math.floor(rng() * 3);
    const spikes = (cx, cy, r, n, len, col) => {
      for (let i = 0; i < n; i++) {
        const a = -Math.PI / 2 + (i - (n - 1) / 2) * 0.45;
        S.push(['poly', [[cx + Math.cos(a - 0.15) * r, cy + Math.sin(a - 0.15) * r], [cx + Math.cos(a) * (r + len), cy + Math.sin(a) * (r + len)],
          [cx + Math.cos(a + 0.15) * r, cy + Math.sin(a + 0.15) * r]], col]);
      }
    };
    if (k === 'Fauna') {
      const legs = 2 + 2 * Math.floor(rng() * 2);
      for (let i = 0; i < legs; i++) {
        const x = (-0.18 + 0.36 * i / Math.max(1, legs - 1)) * sc;
        S.push(['line', x, 0.08 * sc, x * 1.15, 0.36 * sc, Math.max(0.03, 0.05 * sc), dark]);
      }
      S.push(['poly', [[0.2 * sc, 0.05 * sc], [0.46 * sc, -0.12 * sc - rng() * 0.1], [0.24 * sc, 0.14 * sc]], dark]);
      S.push(['ellipse', 0, 0.06 * sc, 0.3 * sc, 0.2 * sc, body]);
      S.push(['ellipse', 0, 0.12 * sc, 0.2 * sc, 0.09 * sc, accent]);
      S.push(['circle', -0.16 * sc, -0.1 * sc, 0.17 * sc, body]);
      if (rng() < 0.6) spikes(-0.16 * sc, -0.1 * sc, 0.15 * sc, 2 + Math.floor(rng() * 3), 0.12 * sc, accent);
      eyeCx = -0.18 * sc;
    } else if (k === 'Flora') {
      S.push(['rect', -0.03 * sc, 0, 0.06 * sc, 0.42 * sc, dark]);
      for (const side of [-1, 1]) S.push(['ellipse', side * 0.13 * sc, 0.22 * sc, 0.12 * sc, 0.05 * sc, hsl(120, 0.5, 0.4)]);
      const petals = 5 + Math.floor(rng() * 4);
      for (let i = 0; i < petals; i++) {
        const a = i / petals * TAU;
        S.push(['circle', Math.cos(a) * 0.2 * sc, -0.08 * sc + Math.sin(a) * 0.2 * sc, 0.11 * sc, accent]);
      }
      S.push(['circle', 0, -0.08 * sc, 0.17 * sc, body]);
    } else if (k === 'Fungoid') {
      S.push(['rect', -0.09 * sc, -0.02 * sc, 0.18 * sc, 0.36 * sc, hsl(hue, 0.25, 0.8)]);
      const pts = [];
      for (let i = 0; i < 13; i++) { const a = Math.PI + i / 12 * Math.PI; pts.push([Math.cos(a) * 0.38 * sc, -0.02 * sc + Math.sin(a) * 0.32 * sc]); }
      S.push(['poly', pts, body]);
      const n = 4 + Math.floor(rng() * 4);
      for (let i = 0; i < n; i++) S.push(['circle', (rng() - 0.5) * 0.5 * sc, -0.12 * sc - rng() * 0.14 * sc, 0.035 * sc + rng() * 0.02, accent]);
      eyeY = 0.1 * sc;
    } else if (k === 'Microbe') {
      const pts = [];
      for (let i = 0; i < 14; i++) { const a = i / 14 * TAU, r = (0.3 + rng() * 0.08) * sc; pts.push([Math.cos(a) * r, Math.sin(a) * r * 0.9]); }
      pts.forEach((p, i) => { if (i % 2 === 0) S.push(['line', p[0], p[1], p[0] * 1.35, p[1] * 1.35, 0.02, dark]); });
      S.push(['poly', pts, body]);
      S.push(['circle', 0.08 * sc, 0.1 * sc, 0.1 * sc, accent]);
      S.push(['circle', -0.12 * sc, 0.12 * sc, 0.05 * sc, glow]);
      eyeCx = -0.02 * sc;
    } else if (k === 'Mechanoid') {
      S.push(['line', 0, -0.25 * sc, 0.1 * sc, -0.46 * sc, 0.02, dark]);
      S.push(['circle', 0.1 * sc, -0.46 * sc, 0.04 * sc, glow]);
      for (const side of [-1, 1]) S.push(['circle', side * 0.2 * sc, 0.3 * sc, 0.09 * sc, dark]);
      S.push(['rect', -0.3 * sc, -0.26 * sc, 0.6 * sc, 0.5 * sc, body]);
      S.push(['rect', -0.22 * sc, -0.18 * sc, 0.44 * sc, 0.16 * sc, dark]);
      S.push(['rect', -0.24 * sc, 0.1 * sc, 0.48 * sc, 0.05 * sc, accent]);
      eyeY = -0.1 * sc;
    } else {
      const n = 3 + Math.floor(rng() * 3);
      for (let i = 0; i < n; i++) {
        const x = (rng() - 0.5) * 0.5 * sc, h = (0.25 + rng() * 0.25) * sc, w = (0.08 + rng() * 0.06) * sc;
        S.push(['poly', [[x, 0.3 * sc - h * 1.6], [x + w, 0.3 * sc - h * 0.6], [x, 0.3 * sc], [x - w, 0.3 * sc - h * 0.6]], accent]);
      }
      S.push(['poly', [[0, -0.3 * sc], [0.24 * sc, 0], [0.12 * sc, 0.3 * sc], [-0.12 * sc, 0.3 * sc], [-0.24 * sc, 0]], body]);
      S.push(['poly', [[0, -0.3 * sc], [0.24 * sc, 0], [0, 0.05 * sc]], dark]);
      eyeCx = -0.02 * sc;
    }
    const spacing = 0.09 * sc;
    for (let i = 0; i < eyes; i++) {
      const ex = eyeCx + (i - (eyes - 1) / 2) * spacing;
      S.push(['circle', ex, eyeY, 0.045 * sc, '#f5f5fa']);
      S.push(['circle', ex + 0.01 * sc, eyeY + 0.005, 0.022 * sc, '#14141e']);
    }
    if (sp.rarity === 'legendary') S.unshift(['ring', 0, 0, 0.48, glow]);
    return S;
  }

  const cache = new Map();
  /** Returns an offscreen canvas with the creature drawn at `size` px. */
  function sprite(sp, size, aberrant = false, silhouette = false) {
    const key = `${sp.id}|${size}|${aberrant}|${silhouette}`;
    if (cache.has(key)) return cache.get(key);
    const cv = document.createElement('canvas');
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = cv.height = Math.round(size * dpr);
    const g = cv.getContext('2d');
    g.scale(dpr, dpr);
    const P = (x) => size / 2 + x * size;
    for (const s of recipe(sp, aberrant)) {
      const col = silhouette ? '#1e2840' : s[s.length - 1];
      g.fillStyle = col; g.strokeStyle = col;
      g.beginPath();
      switch (s[0]) {
        case 'circle': g.arc(P(s[1]), P(s[2]), Math.max(1, s[3] * size), 0, TAU); g.fill(); break;
        case 'ring': g.lineWidth = 2; g.arc(P(s[1]), P(s[2]), s[3] * size, 0, TAU); g.stroke(); break;
        case 'ellipse': g.ellipse(P(s[1]), P(s[2]), s[3] * size, s[4] * size, 0, 0, TAU); g.fill(); break;
        case 'poly': s[1].forEach((p, i) => (i ? g.lineTo(P(p[0]), P(p[1])) : g.moveTo(P(p[0]), P(p[1])))); g.closePath(); g.fill(); break;
        case 'line': g.lineWidth = Math.max(1, s[5] * size); g.lineCap = 'round'; g.moveTo(P(s[1]), P(s[2])); g.lineTo(P(s[3]), P(s[4])); g.stroke(); break;
        case 'rect': if (g.roundRect) g.roundRect(P(s[1]), P(s[2]), s[3] * size, s[4] * size, size * 0.04); else g.rect(P(s[1]), P(s[2]), s[3] * size, s[4] * size); g.fill(); break;
      }
    }
    cache.set(key, cv);
    return cv;
  }
  /** <img>-like element for DOM lists. */
  function spriteEl(sp, size, aberrant, silhouette) {
    const src = sprite(sp, size, aberrant, silhouette);
    const cv = document.createElement('canvas');
    cv.width = src.width; cv.height = src.height;
    cv.style.width = cv.style.height = size + 'px';
    cv.getContext('2d').drawImage(src, 0, 0);
    cv.className = 'sprite';
    return cv;
  }
  Object.assign(EX, { sprite, spriteEl, spriteRecipe: recipe, hsl });
})(window.EX = window.EX || {});
