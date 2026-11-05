/* ExoDex browser UI: screens, input, rendering. */
(function (EX) {
  'use strict';
  const { D, Store, Session, T } = EX;
  const $ = (s) => document.querySelector(s);
  const h = (tag, attrs = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') el.className = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const badge = (t) => h('span', { class: 'badge t-' + t }, t);
  const pct = (a, b) => Math.max(0, Math.min(100, (a / Math.max(1, b)) * 100));
  const hpColor = (f) => (f > 0.5 ? 'var(--good)' : f > 0.2 ? 'var(--warn)' : 'var(--bad)');
  const bar = (frac, cls = '', color) => h('div', { class: 'bar ' + cls }, h('i', { style: `width:${pct(frac, 1)}%;${color ? 'background:' + color : ''}` }));

  const BIOME = {
    forest: { color: '#50be6e', sky: ['#143c28', '#3c7846'], pal: { 0: [48, 92, 52], 1: [34, 130, 70], 2: [40, 90, 120], 3: [60, 70, 58] } },
    ocean: { color: '#3c82e6', sky: ['#143264', '#288caa'], pal: { 0: [196, 186, 140], 1: [40, 150, 140], 2: [30, 80, 170], 3: [90, 100, 110] } },
    desert: { color: '#dcb46e', sky: ['#5a3c28', '#dcaa6e'], pal: { 0: [206, 170, 110], 1: [170, 140, 80], 2: [150, 60, 40], 3: [130, 96, 70] } },
    ice: { color: '#aae1f5', sky: ['#3c5a82', '#bedcf0'], pal: { 0: [200, 222, 236], 1: [150, 200, 230], 2: [40, 90, 150], 3: [120, 140, 160] } },
    lava: { color: '#f06432', sky: ['#280a0a', '#aa3c1e'], pal: { 0: [62, 46, 46], 1: [110, 50, 40], 2: [240, 90, 30], 3: [34, 28, 30] } },
    artificial: { color: '#aa82f0', sky: ['#141028', '#50468c'], pal: { 0: [54, 58, 80], 1: [70, 60, 120], 2: [20, 20, 30], 3: [90, 96, 120] } },
  };

  const G = { session: null, slot: 1, screen: null, time: 0, dirty: false };
  EX.G = G;

  // ------------------------------------------------------------ utilities
  function toast(msg, kind = '') {
    const box = $('#toasts');
    if (box.lastChild && box.lastChild.textContent === msg) box.lastChild.remove();
    const t = h('div', { class: 'toast ' + kind }, msg);
    box.append(t);
    while (box.children.length > 4) box.firstChild.remove();
    setTimeout(() => t.remove(), 3200);
  }
  function result([ok, msg]) { toast(msg, ok ? 'good' : 'warn'); save(); return ok; }
  function save() {
    if (!G.session) return;
    try { Store.save(G.slot, G.session); } catch (e) { console.error(e); toast('Save failed: ' + e.message, 'warn'); }
  }
  function show(id) {
    document.querySelectorAll('.screen').forEach((s) => s.classList.toggle('active', s.id === 'screen-' + id));
    G.screen = id;
  }
  function fitCanvas(cv) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = cv.clientWidth, hh = cv.clientHeight;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(hh * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(hh * dpr); }
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [g, w, hh];
  }

  // ------------------------------------------------------------ starfield
  const stars = Array.from({ length: 260 }, () => [Math.random(), Math.random(), Math.random()]);
  function drawStars() {
    const [g, w, hh] = fitCanvas($('#stars'));
    g.fillStyle = '#070b16'; g.fillRect(0, 0, w, hh);
    const grd = g.createRadialGradient(w * 0.7, hh * 0.2, 0, w * 0.7, hh * 0.2, w * 0.7);
    grd.addColorStop(0, 'rgba(60,40,120,.25)'); grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd; g.fillRect(0, 0, w, hh);
    for (const [x, y, b] of stars) {
      const tw = 0.55 + 0.45 * Math.abs(((G.time * (0.3 + b)) % 2) - 1);
      g.fillStyle = `rgba(220,230,255,${(0.25 + 0.75 * b) * tw})`;
      g.fillRect(x * w, y * hh, b > 0.85 ? 2 : 1, b > 0.85 ? 2 : 1);
    }
  }

  // ================================================================ TITLE
  const PARADE = [1, 37, 92, 140, 175, 211, 214, 217].map((i) => D.species[i]).filter(Boolean);
  function renderTitle() {
    show('title');
    const slots = $('#slots');
    slots.innerHTML = '';
    if (!G.ready) { slots.append(h('div', { class: 'slot panel', style: 'grid-column:1/-1;align-items:center;justify-content:center' }, h('div', { class: 'muted' }, 'Loading SQLite save engine…'))); return; }
    for (const slot of [1, 2, 3]) {
      const m = Store.meta(slot);
      const card = h('div', { class: 'slot panel' }, h('h4', {}, `SAVE SLOT ${slot}`));
      if (m) {
        card.append(h('div', { class: 'name' }, m.name),
          h('div', {}, `ExoDex ${m.scanned}/${D.speciesList.length} · ${m.caught} specimens`),
          h('div', { class: 'muted' }, `RP ${m.rp} · ${Math.floor(m.play / 3600)}h ${Math.floor(m.play / 60) % 60}m played`),
          h('div', { class: 'row' },
            h('button', { class: 'btn primary', onclick: () => continueGame(slot) }, 'Continue'),
            h('button', { class: 'btn', onclick: () => newGame(slot, true) }, 'New'),
          ));
      } else {
        card.append(h('div', { class: 'name muted' }, 'Empty'),
          h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => newGame(slot) }, 'New Expedition')));
      }
      slots.append(card);
    }
    $('#engine-note').textContent = Store.SQL
      ? 'Save engine: SQLite (sql.js / WebAssembly). Saves use the same schema as the Python desktop version — export a .db and open it in the Pygame build or any SQLite browser.'
      : 'Save engine: JSON fallback (SQLite engine could not be downloaded — check your connection). Progress is still saved in this browser.';
  }
  function drawParade() {
    const cv = $('#parade');
    const [g, w, hh] = fitCanvas(cv);
    g.clearRect(0, 0, w, hh);
    const n = PARADE.length, size = Math.min(120, w / n * 1.1);
    PARADE.forEach((sp, i) => {
      const x = (w / n) * (i + 0.5), y = hh / 2 + Math.sin(G.time * 1.6 + i) * 10;
      g.drawImage(EX.sprite(sp, size), x - size / 2, y - size / 2, size, size);
    });
  }
  function continueGame(slot) {
    try {
      G.session = Store.load(slot); G.slot = slot;
      toast(`Welcome back, ${G.session.player.name}.`);
      G.session.map ? enterPlanet() : renderLab('Galaxy');
    } catch (e) { console.error(e); toast('Could not load save: ' + e.message, 'warn'); }
  }
  function newGame(slot, confirmOverwrite) {
    if (confirmOverwrite) {
      modal('Start a new expedition?', `This overwrites save slot ${slot}. Export it first if you want to keep it.`, 'Overwrite', () => renderStarter(slot));
    } else renderStarter(slot);
  }
  function modal(title, text, okLabel, onOk) {
    const bg = h('div', { class: 'modal-bg' });
    const close = () => bg.remove();
    bg.append(h('div', { class: 'modal panel' }, h('h3', { style: 'margin-top:0' }, title), h('p', { class: 'muted' }, text),
      h('div', { style: 'display:flex;gap:10px;justify-content:flex-end' },
        h('button', { class: 'btn', onclick: close }, 'Cancel'),
        h('button', { class: 'btn primary', onclick: () => { close(); onOk(); } }, okLabel))));
    document.body.append(bg);
  }

  // ============================================================== STARTER
  let starterChoice = 0;
  function renderStarter(slot) {
    G.slot = slot;
    show('starter');
    const box = $('#starters');
    box.innerHTML = '';
    D.starters().forEach((sp, i) => {
      const card = h('div', { class: 'starter panel' + (i === starterChoice ? ' sel' : ''), onclick: () => { starterChoice = i; renderStarter(slot); } },
        EX.spriteEl(sp, 170), h('h3', {}, sp.name), h('div', {}, badge(sp.type1)),
        h('div', { class: 'muted', style: 'margin-top:6px;font-size:13px' }, `${sp.kingdom} · evolves at Lv ${sp.evolve_level}`),
        h('p', {}, sp.description));
      box.append(card);
    });
  }
  function startGame() {
    const sp = D.starters()[starterChoice];
    const name = $('#player-name').value.trim() || 'Explorer';
    G.session = Session.newGame(name, sp.id);
    save();
    renderLab('Galaxy');
    toast(`${sp.name} joined your research team!`, 'good');
  }

  // ================================================================== LAB
  const TABS = ['Galaxy', 'Team', 'ExoDex', 'Research', 'Fabricator', 'Missions', 'Data Log'];
  const LAB = { tab: 'Galaxy', planet: 1, creature: null, species: 1, kingdom: 'All', dexView: 'all', sql: '' };

  function renderLab(tab) {
    if (tab) LAB.tab = tab;
    show('lab');
    const s = G.session, p = s.player, c = s.dexCounts();
    $('#lab-stats').innerHTML = `<span>${esc(p.name)}</span><span>Rank <b>${c.scanned}</b></span><span>RP <b>${p.rp}</b></span>` +
      `<span>Fuel <b>${s.qty('fuel')}</b></span><span>Pods <b>${s.qty('pod') + s.qty('pod_plus') + s.qty('pod_max')}</b></span>` +
      `<span>ExoDex <b>${c.scanned}/${D.speciesList.length}</b></span><span>Caught <b>${c.captured}</b></span>`;
    const tabs = $('#tabs');
    tabs.innerHTML = '';
    const claimable = D.missions.filter((m) => s.st.missions[m.id].progress >= m.goal && !s.st.missions[m.id].claimed).length;
    for (const t of TABS) {
      const b = h('button', { class: 'btn' + (t === LAB.tab ? ' on' : ''), onclick: () => renderLab(t) }, t);
      if (t === 'Missions' && claimable) b.append(h('span', { class: 'notif' }, claimable));
      tabs.append(b);
    }
    tabs.append(h('div', { class: 'spacer' }),
      h('button', { class: 'btn small', onclick: () => { save(); toast('Progress saved.', 'good'); } }, 'Save'),
      h('button', { class: 'btn small', onclick: () => toast('Downloaded ' + Store.exportFile(G.slot, s), 'good') }, Store.SQL ? 'Export .db' : 'Export save'),
      h('button', { class: 'btn small', onclick: () => { save(); G.session = null; renderTitle(); } }, 'Title Screen'));
    const el = $('#tab-content');
    const scroll = el.scrollTop;
    el.innerHTML = '';
    ({ Galaxy: tabGalaxy, Team: tabTeam, ExoDex: tabDex, Research: tabResearch, Fabricator: tabFab, Missions: tabMissions, 'Data Log': tabLog })[LAB.tab](el);
    el.scrollTop = scroll;
  }
  const rerender = () => renderLab();

  // ---------------------------------------------------------------- galaxy
  function planetPos(p, w, hh) {
    const a = p.id / 6 * Math.PI * 2 + G.time * 0.03;
    const r = (0.16 + p.id * 0.055);
    return [w / 2 + Math.cos(a) * r * w * 0.95, hh / 2 + Math.sin(a) * r * hh * 1.25];
  }
  function tabGalaxy(el) {
    const s = G.session, p = D.planets[LAB.planet];
    const cv = h('canvas', { id: 'galaxy' });
    cv.addEventListener('click', (e) => {
      const r = cv.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      let best = null, bd = 1e9;
      for (const q of Object.values(D.planets)) {
        const [x, y] = planetPos(q, r.width, r.height); const d = Math.hypot(x - mx, y - my);
        if (d < bd) { bd = d; best = q; }
      }
      if (bd < 60) { LAB.planet = best.id; rerender(); }
    });
    const unlocked = s.unlocked(p);
    const beaten = s.player.alphas_beaten.split(',').includes(String(p.id));
    const found = s.scannedWhere((sp, d) => d.planet_id === p.id);
    const detail = h('div', { class: 'detail panel' },
      h('h2', { style: `color:${BIOME[p.biome].color}` }, p.name),
      h('div', { class: 'muted' }, `${p.biome[0].toUpperCase() + p.biome.slice(1)} world · wild Lv ${p.min_level}-${p.max_level}`),
      h('p', {}, p.description),
      h('div', { class: 'section-title' }, 'DOMINANT LIFEFORM TYPES'), h('div', {}, p.types.map(badge)),
      h('div', { class: 'kv', style: 'margin-top:14px' },
        h('span', { class: 'muted' }, 'Species scanned here'), h('span', {}, String(found)),
        h('span', { class: 'muted' }, 'Native resource'), h('span', {}, D.items[p.material].name),
        h('span', { class: 'muted' }, 'Alpha'), h('span', { style: `color:${beaten ? 'var(--good)' : 'var(--warn)'}` },
          `${beaten ? D.species[p.alpha_species].name + ' (subdued)' : '??? '} Lv ${p.alpha_level}`),
        h('span', { class: 'muted' }, 'Travel cost'), h('span', {}, p.id === 1 ? 'Free (shuttle)' : '1 Fuel Cell')),
      !unlocked ? h('p', { style: 'color:var(--bad);font-weight:700' }, `Unlocks at Explorer Rank ${p.unlock_rank} (you: ${s.rank()})`) : null,
      h('button', { class: 'btn primary', style: 'width:100%;margin-top:14px;padding:14px', disabled: !unlocked,
        onclick: () => { const [ok, msg] = s.travel(p.id); toast(msg, ok ? 'good' : 'warn'); if (ok) { save(); enterPlanet(); } } },
      unlocked ? `Launch to ${p.name}` : 'Locked'));
    el.append(h('div', { class: 'cols' }, h('div', { class: 'panel', style: 'padding:6px' }, cv,
      h('div', { class: 'muted', style: 'padding:6px 10px;font-size:13px' }, 'Click a planet to select it. Scan more species to raise your Explorer Rank and unlock outer worlds.')), detail));
    LAB.galaxy = cv;
  }
  function drawGalaxy() {
    const cv = LAB.galaxy;
    if (!cv || !cv.isConnected) return;
    const [g, w, hh] = fitCanvas(cv);
    g.clearRect(0, 0, w, hh);
    const cx = w / 2, cy = hh / 2;
    const sun = g.createRadialGradient(cx, cy, 0, cx, cy, 70);
    sun.addColorStop(0, '#fff6c8'); sun.addColorStop(0.35, '#ffc850'); sun.addColorStop(1, 'rgba(255,120,40,0)');
    g.fillStyle = sun; g.beginPath(); g.arc(cx, cy, 70, 0, 7); g.fill();
    for (const p of Object.values(D.planets)) {
      const r = (0.16 + p.id * 0.055);
      g.strokeStyle = '#22304e'; g.lineWidth = 1; g.beginPath(); g.ellipse(cx, cy, r * w * 0.95, r * hh * 1.25, 0, 0, 7); g.stroke();
    }
    for (const p of Object.values(D.planets)) {
      const [x, y] = planetPos(p, w, hh);
      const unlocked = G.session.unlocked(p);
      const rad = 12 + p.id * 2.2;
      const grd = g.createRadialGradient(x - rad / 3, y - rad / 3, 2, x, y, rad);
      grd.addColorStop(0, unlocked ? '#ffffff' : '#666c80'); grd.addColorStop(0.25, unlocked ? BIOME[p.biome].color : '#3c4256'); grd.addColorStop(1, '#0b1020');
      g.fillStyle = grd; g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill();
      if (p.id === LAB.planet) { g.strokeStyle = '#5adcc8'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, rad + 8 + Math.sin(G.time * 3) * 2, 0, 7); g.stroke(); }
      g.fillStyle = unlocked ? '#e3eaf8' : '#6b7896'; g.font = '600 13px Space Grotesk, sans-serif'; g.textAlign = 'center';
      g.fillText(unlocked ? p.name : `${p.name} (Rank ${p.unlock_rank})`, x, y + rad + 18);
    }
  }

  // ------------------------------------------------------------------ team
  function tabTeam(el) {
    const s = G.session, all = s.allCreatures();
    if (!LAB.creature || !s.byId(LAB.creature)) LAB.creature = all[0].id;
    const list = h('div', { class: 'clist' });
    const row = (c) => h('div', { class: 'citem panel' + (c.id === LAB.creature ? ' sel' : ''), onclick: () => { LAB.creature = c.id; rerender(); } },
      EX.spriteEl(c.species, 48, c.aberrant),
      h('div', {}, h('div', { style: 'font-weight:700' }, `${c.name} `, h('span', { class: 'muted' }, `Lv ${c.level}`)),
        h('div', { class: 'tag ' + (c.team_slot !== null ? '' : 'muted'), style: c.team_slot !== null ? 'color:var(--accent)' : '' },
          c.team_slot !== null ? `TEAM ${c.team_slot + 1}` : 'LAB STORAGE', c.aberrant ? ' · ABERRANT' : '')),
      h('div', {}, bar(c.hp / c.maxHp, '', hpColor(c.hp / c.maxHp)), h('div', { class: 'muted', style: 'font-size:12px;margin-top:3px' }, c.fainted ? 'FAINTED' : `${c.hp}/${c.maxHp} HP`)));
    const team = s.team(), stor = s.storage();
    list.append(h('div', { class: 'section-title', style: 'margin-top:0;display:flex;justify-content:space-between;align-items:center' },
      `ACTIVE TEAM (${team.length}/6)`, h('button', { class: 'btn small', onclick: () => { s.healTeam(); save(); toast('Med Bay restored every specimen.', 'good'); rerender(); } }, 'Heal all (free in orbit)')));
    team.forEach((c) => list.append(row(c)));
    list.append(h('div', { class: 'section-title' }, `LAB STORAGE (${stor.length})`));
    if (!stor.length) list.append(h('div', { class: 'muted' }, 'Captured specimens beyond your team of six are stored here.'));
    stor.forEach((c) => list.append(row(c)));

    const c = s.byId(LAB.creature);
    const d = s.discovery(c.species.id) || { dna: 0 };
    const cur = EX.xpForLevel(c.level), nxt = EX.xpForLevel(c.level + 1);
    const inTeam = c.team_slot !== null;
    const statRow = (lab, val, iv) => h('div', { class: 'stat-row' }, h('span', { class: 'muted' }, lab), h('b', {}, String(val)), bar(iv / 15, 'gene'), h('span', { class: 'muted', style: 'font-size:12px' }, `gene ${iv}/15`));
    const detail = h('div', { class: 'detail panel' },
      h('div', { style: 'display:flex;gap:12px;align-items:center' }, EX.spriteEl(c.species, 150, c.aberrant),
        h('div', {}, h('h2', {}, c.name), h('div', {}, c.species.types.map(badge)),
          h('div', { class: 'r-' + c.species.rarity, style: 'margin-top:6px;font-size:13px' }, `${c.species.kingdom} · ${c.species.rarity}`),
          c.nickname ? h('div', { class: 'muted', style: 'font-size:12px' }, `Species: ${c.species.name}`) : null)),
      h('div', { style: 'margin-top:8px' }, `Level ${c.level} · Trait `, h('b', {}, c.trait)),
      h('div', { class: 'muted', style: 'font-size:13px' }, D.traits[c.trait]),
      h('div', { style: 'margin:8px 0 2px;font-size:12px', class: 'muted' }, `XP ${c.xp - cur}/${nxt - cur}`), bar((c.xp - cur) / (nxt - cur), 'xp'),
      h('div', { class: 'section-title' }, 'STATS & GENOME'),
      statRow('HP', c.maxHp, c.ivs.hp), statRow('ATK', c.atk, c.ivs.atk), statRow('DEF', c.defense, c.ivs.def), statRow('SPD', c.spd, c.ivs.spd),
      h('div', { class: 'section-title' }, 'MOVES'),
      h('div', {}, c.moves.map((m) => h('div', { style: 'font-size:14px;margin:3px 0' }, badge(D.moves[m].type), ` ${D.moves[m].name} `, h('span', { class: 'muted' }, D.moves[m].power ? `pow ${D.moves[m].power}` : D.moves[m].description)))),
      h('div', { class: 'muted', style: 'margin-top:10px;font-size:13px' }, `${c.species.name} DNA stored: ${d.dna}` + (c.species.evolves_to ? ` · evolves at Lv ${c.species.evolve_level}` : ' · final form')),
      h('div', { class: 'actions' },
        h('button', { class: 'btn small', disabled: !inTeam || c.team_slot === 0, onclick: () => { s.setLead(c.id); save(); rerender(); } }, 'Make lead'),
        h('button', { class: 'btn small', onclick: () => { result(s.swapTeam(c.id)); rerender(); } }, inTeam ? 'Move to storage' : 'Add to team'),
        h('button', { class: 'btn small', onclick: () => { result(s.sequenceGenome(c.id)); rerender(); } }, `Sequence genome (${s.sequenceCost()} DNA)`),
        h('button', { class: 'btn small', disabled: !c.species.evolves_to, onclick: () => { result(s.accelerateEvolution(c.id)); rerender(); } }, `Accelerate evolution (${EX.ACCEL_COST} DNA)`),
        h('button', { class: 'btn small', disabled: !s.qty('medgel') || c.fainted, onclick: () => { result(s.useItemOn('medgel', c.id)); rerender(); } }, `MedGel (${s.qty('medgel')})`),
        h('button', { class: 'btn small', disabled: !s.qty('revive') || !c.fainted, onclick: () => { result(s.useItemOn('revive', c.id)); rerender(); } }, `Revive (${s.qty('revive')})`),
        h('button', { class: 'btn small', onclick: () => {
          const n = prompt('Nickname (blank to clear):', c.nickname || '');
          if (n !== null) { s.rename(c.id, n); save(); rerender(); }
        } }, 'Rename')));
    el.append(h('div', { class: 'cols' }, list, detail));
  }

  // ---------------------------------------------------------------- exodex
  function tabDex(el) {
    const s = G.session;
    if (!(s.discovery(LAB.species) || {}).seen) {
      const first = D.speciesList.find((sp) => (s.discovery(sp.id) || {}).scanned);
      if (first) LAB.species = first.id;
    }
    const kingdoms = ['All', 'Fauna', 'Flora', 'Fungoid', 'Microbe', 'Mechanoid', 'Crystalline'];
    const filters = h('div', { class: 'filters' });
    kingdoms.forEach((k) => filters.append(h('button', { class: 'btn small' + (LAB.kingdom === k ? ' on' : ''), onclick: () => { LAB.kingdom = k; rerender(); } }, k)));
    filters.append(h('span', { class: 'muted', style: 'margin:0 6px' }, '|'));
    [['all', 'All entries'], ['scanned', 'Scanned'], ['missing', 'Missing']].forEach(([v, lab]) =>
      filters.append(h('button', { class: 'btn small' + (LAB.dexView === v ? ' on' : ''), onclick: () => { LAB.dexView = v; rerender(); } }, lab)));
    const grid = h('div', { class: 'dexgrid' });
    let list = D.speciesList.filter((sp) => LAB.kingdom === 'All' || sp.kingdom === LAB.kingdom);
    if (LAB.dexView === 'scanned') list = list.filter((sp) => (s.discovery(sp.id) || {}).scanned);
    if (LAB.dexView === 'missing') list = list.filter((sp) => !(s.discovery(sp.id) || {}).scanned);
    for (const sp of list) {
      const d = s.discovery(sp.id) || {};
      const cell = h('div', { class: 'dexcell panel' + (sp.id === LAB.species ? ' sel' : '') + (d.captured ? ' caught' : ''), onclick: () => { LAB.species = sp.id; rerender(); } },
        d.seen ? EX.spriteEl(sp, 64, false, !d.scanned) : h('div', { class: 'unk' }, '?'),
        h('div', { class: 'num' }, '#' + String(sp.id).padStart(3, '0')),
        h('div', { class: 'nm' }, d.scanned ? sp.name : '???'));
      grid.append(cell);
    }
    const c = s.dexCounts();
    const head = h('div', { class: 'muted', style: 'margin-bottom:10px' }, `Seen ${c.seen} · Scanned ${c.scanned} · Captured ${c.captured} · Total ${D.speciesList.length} species`);
    const sp = D.species[LAB.species], d = s.discovery(sp.id) || {};
    let detail;
    if (!d.seen) {
      detail = h('div', { class: 'detail panel' }, h('h2', { class: 'muted' }, `#${String(sp.id).padStart(3, '0')} Unknown lifeform`),
        h('p', { class: 'muted' }, 'Encounter this species in the field to log it.'));
    } else if (!d.scanned) {
      detail = h('div', { class: 'detail panel' }, EX.spriteEl(sp, 200, false, true), h('h2', {}, `#${String(sp.id).padStart(3, '0')} ???`),
        h('p', { class: 'muted' }, 'Seen but not scanned. Use SCAN during a battle to record its biology.'));
    } else {
      const evo = sp.evolves_to ? D.species[sp.evolves_to] : null, prev = D.prevStage[sp.id] ? D.species[D.prevStage[sp.id]] : null;
      detail = h('div', { class: 'detail panel' }, h('div', { style: 'text-align:center' }, EX.spriteEl(sp, 200)),
        h('h2', {}, `#${String(sp.id).padStart(3, '0')} ${sp.name}`), h('div', {}, sp.types.map(badge)),
        h('div', { class: 'r-' + sp.rarity, style: 'margin:6px 0' }, `${sp.kingdom} · ${sp.rarity}`),
        h('p', {}, sp.description),
        h('div', { class: 'kv' },
          h('span', { class: 'muted' }, 'Habitat'), h('span', {}, sp.biomes.map((b) => b[0].toUpperCase() + b.slice(1)).join(', ')),
          h('span', { class: 'muted' }, 'Size'), h('span', {}, `${sp.height_m} m · ${sp.mass_kg} kg`),
          h('span', { class: 'muted' }, 'Base stats'), h('span', {}, `HP ${sp.hp} · ATK ${sp.atk} · DEF ${sp.defense} · SPD ${sp.spd}`),
          h('span', { class: 'muted' }, 'Lineage'), h('span', {}, [prev ? `from ${prev.name}` : 'base form', evo ? `→ ${evo.name} at Lv ${sp.evolve_level}` : 'final form'].join(' · ')),
          h('span', { class: 'muted' }, 'First logged'), h('span', {}, d.planet_id ? D.planets[d.planet_id].name : 'Lab'),
          h('span', { class: 'muted' }, 'DNA samples'), h('span', {}, String(d.dna)),
          h('span', { class: 'muted' }, 'Status'), h('span', { style: d.captured ? 'color:var(--good)' : '' }, d.captured ? 'Captured' : 'Scanned')),
        h('button', { class: 'btn', style: 'width:100%;margin-top:14px', disabled: d.dna < EX.SYNTH_COST || sp.rarity === 'legendary',
          onclick: () => { result(s.synthesize(sp.id)); rerender(); } }, `Synthesize specimen from DNA (${EX.SYNTH_COST} DNA)`));
    }
    el.append(h('div', { class: 'cols' }, h('div', {}, head, filters, grid), detail));
  }

  // -------------------------------------------------------------- research
  function tabResearch(el) {
    const s = G.session;
    el.append(h('div', { style: 'margin-bottom:12px' }, 'Research Points available: ', h('b', { style: 'color:var(--accent)' }, String(s.player.rp)),
      h('span', { class: 'muted' }, ' — earned by new scans, captures, battles, Alphas and missions.')));
    const grid = h('div', { class: 'grid2' });
    for (const r of D.raw.research) {
      const lvl = s.research(r.id), maxed = lvl >= r.max_level;
      grid.append(h('div', { class: 'card panel' }, h('h3', {}, r.name), h('div', { class: 'muted' }, r.description),
        h('div', { class: 'pips' }, Array.from({ length: r.max_level }, (_, i) => h('i', { class: i < lvl ? 'on' : '' }))),
        h('button', { class: 'btn' + (maxed ? '' : ' primary'), disabled: maxed || s.player.rp < s.researchCost(r.id),
          onclick: () => { result(s.upgradeResearch(r.id)); rerender(); } }, maxed ? 'MAXED' : `Upgrade — ${s.researchCost(r.id)} RP`)));
    }
    el.append(grid);
  }

  // ------------------------------------------------------------ fabricator
  function tabFab(el) {
    const s = G.session;
    const list = h('div', { class: 'clist' });
    list.append(h('div', { class: 'section-title', style: 'margin-top:0' }, 'FABRICATOR — combine materials gathered on planets'));
    for (const r of D.recipes) {
      const out = D.items[r.output];
      list.append(h('div', { class: 'recipe panel' },
        h('div', {}, h('b', {}, `${r.qty}x ${out.name}`), h('div', { class: 'muted', style: 'font-size:12px' }, out.description),
          h('div', { class: 'in', html: Object.entries(r.inputs).map(([k, v]) => `<span class="${s.qty(k) >= v ? 'have' : 'need'}">${v} ${esc(D.items[k].name)}</span> (${s.qty(k)})`).join(' + ') })),
        h('button', { class: 'btn primary', disabled: !s.canCraft(r), onclick: () => { result(s.craft(r.id)); rerender(); } }, 'Craft')));
    }
    const inv = h('div', { class: 'inv panel detail' }, h('h3', { style: 'margin-top:0' }, 'Cargo hold'));
    const items = Object.entries(s.st.inventory).filter(([, q]) => q > 0);
    if (!items.length) inv.append(h('p', { class: 'muted' }, 'Empty.'));
    for (const [k, q] of items) inv.append(h('div', { title: D.items[k].description }, h('span', {}, D.items[k].name), h('b', {}, 'x' + q)));
    inv.append(h('p', { class: 'muted', style: 'font-size:13px' }, 'Tip: each planet has its own material. Gather glowing nodes with E. Bio Lures double encounters and triple rare spawns.'));
    el.append(h('div', { class: 'cols' }, list, inv));
  }

  // -------------------------------------------------------------- missions
  function tabMissions(el) {
    const s = G.session;
    s.refreshMissions();
    const list = h('div', { class: 'clist' });
    for (const m of D.missions) {
      const st = s.st.missions[m.id], done = st.progress >= m.goal;
      list.append(h('div', { class: 'mission panel' + (done ? ' done' : '') + (st.claimed ? ' claimed' : '') },
        h('div', {}, h('b', {}, m.title), h('div', { class: 'muted', style: 'font-size:13px' }, m.description),
          h('div', { class: 'rw' }, `Reward: +${m.reward_rp} RP, ${m.reward_qty}x ${D.items[m.reward_item].name}`)),
        h('div', {}, bar(st.progress / m.goal, 'xp'), h('div', { class: 'muted', style: 'font-size:12px;margin-top:4px' }, `${st.progress}/${m.goal}`)),
        h('button', { class: 'btn' + (done && !st.claimed ? ' primary' : ''), disabled: !done || st.claimed, onclick: () => { result(s.claimMission(m.id)); rerender(); } }, st.claimed ? 'Claimed' : 'Claim')));
    }
    el.append(list);
  }

  // -------------------------------------------------------------- data log
  const EXAMPLES = [
    ['Rarest captures', "SELECT s.name, s.rarity, c.level, c.trait\nFROM creatures c JOIN species s ON s.id = c.species_id\nORDER BY CASE s.rarity WHEN 'legendary' THEN 5 WHEN 'epic' THEN 4 WHEN 'rare' THEN 3 WHEN 'uncommon' THEN 2 ELSE 1 END DESC, c.level DESC;"],
    ['Scans per planet', 'SELECT p.name AS planet, COUNT(*) AS species_scanned\nFROM discoveries d JOIN planets p ON p.id = d.planet_id\nWHERE d.scanned = 1 GROUP BY p.id ORDER BY 2 DESC;'],
    ['Win rate by planet', "SELECT p.name, COUNT(*) AS battles,\n  ROUND(100.0 * SUM(b.result IN ('win','captured')) / COUNT(*), 1) AS success_pct\nFROM battle_history b JOIN planets p ON p.id = b.planet_id GROUP BY p.id;"],
    ['Strongest species', 'SELECT name, type1, type2, hp + atk + defense + spd AS base_total\nFROM species ORDER BY base_total DESC LIMIT 10;'],
    ['Type distribution', 'SELECT type1 AS type, COUNT(*) AS species FROM species GROUP BY type1 ORDER BY 2 DESC;'],
  ];
  function tabLog(el) {
    const s = G.session, hist = s.st.battle_history;
    const cnt = (r) => hist.filter((b) => b.result === r).length;
    el.append(h('div', { class: 'section-title', style: 'margin-top:0' }, 'FIELD STATISTICS'),
      h('div', {}, `Battles ${hist.length} · Wins ${cnt('win')} · Captures ${cnt('captured')} · Losses ${cnt('loss')} · Fled ${cnt('fled')} · Steps walked ${s.player.steps} · Alphas ${s.stat('alpha')}/6`));
    el.append(h('div', { class: 'section-title' }, 'DISCOVERIES BY RARITY'));
    for (const r of EX.RARITY_ORDER) {
      const total = D.speciesList.filter((sp) => sp.rarity === r).length;
      const found = s.scannedWhere((sp) => sp.rarity === r);
      el.append(h('div', { style: 'display:grid;grid-template-columns:100px 1fr 70px;gap:10px;align-items:center;margin:6px 0' },
        h('span', { class: 'r-' + r }, r), bar(found / total, '', `var(--r-${r})`), h('span', { class: 'muted' }, `${found}/${total}`)));
    }
    el.append(h('div', { class: 'section-title' }, 'RECENT FIELD REPORTS'));
    if (!hist.length) el.append(h('div', { class: 'muted' }, 'No battles yet.'));
    hist.slice(-10).reverse().forEach((b) => el.append(h('div', { class: 'log-row' },
      h('span', { class: 'muted' }, b.at.slice(0, 16).replace('T', ' ')), h('span', {}, b.planet_id ? D.planets[b.planet_id].name : '-'),
      h('span', {}, `${D.species[b.enemy_species].name} Lv ${b.enemy_level}`),
      h('span', { style: `color:${{ win: 'var(--good)', captured: 'var(--accent)', loss: 'var(--bad)' }[b.result] || 'var(--muted)'}` }, `${b.result.toUpperCase()} in ${b.turns} turns`))));

    el.append(h('div', { class: 'section-title' }, 'SQL CONSOLE — query your save database'));
    if (!Store.SQL) { el.append(h('p', { class: 'muted' }, 'The SQLite engine (sql.js) did not load, so the console is unavailable. Your progress is still saved.')); return; }
    const ta = h('textarea', { class: 'sqlbox', spellcheck: 'false' });
    ta.value = LAB.sql || EXAMPLES[0][1];
    const out = h('div', { class: 'qwrap' });
    const run = () => {
      LAB.sql = ta.value;
      out.innerHTML = '';
      try {
        const res = Store.query(s, ta.value);
        const tbl = h('table', { class: 'qtable' }, h('tr', {}, res.columns.map((c) => h('th', {}, c))));
        res.values.slice(0, 200).forEach((row) => tbl.append(h('tr', {}, row.map((v) => h('td', {}, v === null ? 'NULL' : String(v))))));
        out.append(tbl, h('div', { class: 'muted', style: 'font-size:12px;margin-top:6px' }, `${res.values.length} row(s)`));
      } catch (e) { out.append(h('div', { style: 'color:var(--bad);font-family:var(--mono);font-size:13px;margin-top:8px' }, e.message)); }
    };
    const ex = h('div', { class: 'filters', style: 'margin-top:8px' }, EXAMPLES.map(([lab, q]) => h('button', { class: 'btn small', onclick: () => { ta.value = q; run(); } }, lab)),
      h('button', { class: 'btn small primary', onclick: run }, 'Run query'));
    el.append(h('div', { class: 'muted', style: 'font-size:13px;margin-bottom:6px' }, 'Tables: species, moves, species_moves, planets, items, recipes, recipe_inputs, research, missions, player, creatures, inventory, discoveries, battle_history, stats'), ta, ex, out);
    run();
  }

  // =============================================================== PLANET
  const TILE = 32;
  const PL = { mapCanvas: null, rx: 0, ry: 0, cd: 0, held: null, facing: [0, 1] };
  function shade(c, f) { return `rgb(${c.map((v) => Math.max(0, Math.min(255, Math.round(v * f)))).join(',')})`; }
  function renderMapCanvas() {
    const s = G.session, m = s.map, p = s.planet, pal = BIOME[p.biome].pal;
    const cv = document.createElement('canvas');
    cv.width = m.w * TILE; cv.height = m.h * TILE;
    const g = cv.getContext('2d');
    for (let y = 0; y < m.h; y++) for (let x = 0; x < m.w; x++) {
      const t = m.tiles[y][x], base = pal[t] || pal[0];
      const f = 0.88 + 0.24 * m.shade[y][x];
      const X = x * TILE, Y = y * TILE;
      g.fillStyle = shade(base, f); g.fillRect(X, Y, TILE, TILE);
      const hv = EX.hash2(x, y, p.seed + 5);
      if (t === T.BIOZONE) {
        g.strokeStyle = shade(base, 1.4); g.lineWidth = 2; g.lineCap = 'round';
        for (let k = 0; k < 3; k++) {
          const ox = 6 + Math.floor(EX.hash2(x, y, p.seed + k) * 20);
          g.beginPath(); g.moveTo(X + ox, Y + TILE - 4); g.quadraticCurveTo(X + ox - 2, Y + 16, X + ox + 3, Y + 8 + k * 3); g.stroke();
        }
      } else if (t === T.ROCK) {
        g.fillStyle = shade(base, 1.25);
        g.beginPath(); g.moveTo(X + 4, Y + TILE - 3); g.lineTo(X + 16, Y + 4 + hv * 8); g.lineTo(X + TILE - 4, Y + TILE - 3); g.fill();
        g.fillStyle = shade(base, 0.7);
        g.beginPath(); g.moveTo(X + 16, Y + 4 + hv * 8); g.lineTo(X + TILE - 4, Y + TILE - 3); g.lineTo(X + 18, Y + TILE - 3); g.fill();
      } else if (t === T.HAZARD) {
        if (hv < 0.35) { g.fillStyle = shade(base, 1.35); g.beginPath(); g.ellipse(X + 8 + hv * 40, Y + 14, 5, 2, 0, 0, 7); g.fill(); }
      } else if ((t === T.GROUND || t === T.NODE) && hv < 0.08) {
        g.fillStyle = shade(base, 0.75); g.beginPath(); g.arc(X + 16, Y + 16, 3, 0, 7); g.fill();
      }
    }
    PL.mapCanvas = cv;
  }
  function enterPlanet() {
    show('planet');
    renderMapCanvas();
    PL.rx = G.session.player.pos_x; PL.ry = G.session.player.pos_y;
    updateHud();
  }
  function updateHud() {
    const s = G.session, p = s.planet, pl = s.player;
    if (!p) return;
    $('#hud').innerHTML = `<h3>${esc(p.name)}</h3><div class="muted">Lv ${p.min_level}-${p.max_level} · ${p.biome} · Rank ${s.rank()}` +
      `${pl.lure_steps ? ` · <span style="color:var(--good)">Lure ${pl.lure_steps}</span>` : ''}</div>` +
      `<div class="muted">Pods ${s.qty('pod') + s.qty('pod_plus') + s.qty('pod_max')} · MedGel ${s.qty('medgel')} · ${esc(D.items[p.material].name)} ${s.qty(p.material)}</div>`;
    const tm = $('#team-mini');
    tm.innerHTML = '';
    for (const c of s.team()) {
      tm.append(h('div', { class: 'm panel' }, EX.spriteEl(c.species, 36, c.aberrant),
        h('div', {}, h('div', {}, `${c.name} Lv${c.level}`), bar(c.hp / c.maxHp, '', hpColor(c.hp / c.maxHp)))));
    }
  }
  function planetStep(dx, dy) {
    const s = G.session;
    PL.facing = [dx, dy];
    const before = [s.player.pos_x, s.player.pos_y];
    const ev = s.step(dx, dy);
    if (s.player.pos_x !== before[0] || s.player.pos_y !== before[1]) G.dirty = true;
    if (s.player.steps % 15 === 0) updateHud();
    if (ev) { PL.held = null; startBattle(ev[1], ev[0] === 'alpha'); }
  }
  function doGather() {
    const msg = G.session.gather();
    if (msg) { toast(msg, 'good'); renderMapCanvas(); updateHud(); save(); }
    else toast('Nothing to gather here. Stand on or next to a glowing node.');
  }
  function doLure() {
    if (G.session.useLure()) { toast('Bio Lure released! Encounters doubled for 60 steps.', 'good'); updateHud(); }
    else toast('No Bio Lures. Craft one at the Fabricator.', 'warn');
  }
  function doOrbit() {
    const s = G.session, [px, py] = s.map.pad, pl = s.player;
    if (pl.pos_x !== px || pl.pos_y !== py) {
      toast(`Return to the landing pad first (${Math.abs(pl.pos_x - px) + Math.abs(pl.pos_y - py)} tiles away).`, 'warn');
      return;
    }
    s.returnToLab(); save();
    toast('Docked with the Orbital Lab. Team healed.', 'good');
    renderLab('Galaxy');
  }
  function drawPlanet(dt) {
    const s = G.session;
    if (!s || !s.map) return;
    if (PL.held) {
      PL.cd -= dt;
      if (PL.cd <= 0) { PL.cd = 0.12; planetStep(PL.held[0], PL.held[1]); if (G.screen !== 'planet') return; }
    }
    const [g, w, hh] = fitCanvas($('#planet-canvas'));
    const pl = s.player;
    const k = Math.min(1, dt * 14);
    PL.rx += (pl.pos_x - PL.rx) * k; PL.ry += (pl.pos_y - PL.ry) * k;
    if (Math.abs(pl.pos_x - PL.rx) > 3 || Math.abs(pl.pos_y - PL.ry) > 3) { PL.rx = pl.pos_x; PL.ry = pl.pos_y; }
    const scale = w < 700 ? 0.8 : 1;
    const ts = TILE * scale;
    const mw = s.map.w * ts, mh = s.map.h * ts;
    let camX = PL.rx * ts + ts / 2 - w / 2, camY = PL.ry * ts + ts / 2 - hh / 2;
    camX = mw <= w ? (mw - w) / 2 : Math.max(0, Math.min(mw - w, camX));
    camY = mh <= hh ? (mh - hh) / 2 : Math.max(0, Math.min(mh - hh, camY));
    g.fillStyle = '#070b16'; g.fillRect(0, 0, w, hh);
    g.imageSmoothingEnabled = false;
    g.drawImage(PL.mapCanvas, -camX, -camY, mw, mh);
    const t = G.time;
    const sx = (x) => x * ts + ts / 2 - camX, sy = (y) => y * ts + ts / 2 - camY;
    // biozone sway shimmer
    for (const key of s.map.nodes) {
      const [nx, ny] = key.split(',').map(Number);
      const cx = sx(nx), cy = sy(ny);
      if (cx < -40 || cy < -40 || cx > w + 40 || cy > hh + 40) continue;
      const r = (8 + 2 * Math.sin(t * 4 + nx)) * scale;
      g.strokeStyle = 'rgba(255,230,120,.7)'; g.lineWidth = 1.5; g.beginPath(); g.arc(cx, cy, r + 4, 0, 7); g.stroke();
      g.fillStyle = '#fad25a'; g.beginPath(); g.moveTo(cx, cy - 8 * scale); g.lineTo(cx + 6 * scale, cy); g.lineTo(cx, cy + 8 * scale); g.lineTo(cx - 6 * scale, cy); g.fill();
    }
    const [ax, ay] = s.map.pad;
    g.strokeStyle = '#5adcc8'; g.lineWidth = 2; g.beginPath(); g.arc(sx(ax), sy(ay), 13 * scale, 0, 7); g.stroke();
    g.beginPath(); g.arc(sx(ax), sy(ay), 6 * scale, 0, 7); g.stroke();
    g.fillStyle = '#5adcc8'; g.font = '700 11px Space Grotesk, sans-serif'; g.textAlign = 'center'; g.fillText('PAD', sx(ax), sy(ay) - 18 * scale);
    const [nx, ny] = s.map.nest;
    if (!pl.alphas_beaten.split(',').includes(String(s.planet.id))) {
      const r = (12 + 3 * Math.sin(t * 3)) * scale;
      g.strokeStyle = '#ff6470'; g.lineWidth = 3; g.beginPath(); g.arc(sx(nx), sy(ny), r, 0, 7); g.stroke();
      g.fillStyle = '#ff6470'; g.fillText('ALPHA', sx(nx), sy(ny) - 20 * scale);
    }
    // explorer
    const cx = (PL.rx * ts) + ts / 2 - camX, cy = (PL.ry * ts) + ts / 2 - camY;
    const moving = Math.abs(pl.pos_x - PL.rx) + Math.abs(pl.pos_y - PL.ry) > 0.05;
    const bob = moving ? Math.sin(t * 18) * 2 : Math.sin(t * 3) * 1;
    g.save(); g.translate(cx, cy); g.scale(scale, scale);
    g.fillStyle = 'rgba(0,0,0,.35)'; g.beginPath(); g.ellipse(0, 12, 10, 4, 0, 0, 7); g.fill();
    g.fillStyle = '#e6ecf5'; if (g.roundRect) { g.beginPath(); g.roundRect(-8, -6 + bob, 16, 16, 5); g.fill(); } else g.fillRect(-8, -6 + bob, 16, 16);
    g.beginPath(); g.arc(0, -9 + bob, 8, 0, 7); g.fill();
    g.fillStyle = '#3cc8e6'; g.beginPath(); g.arc(PL.facing[0] * 3, -9 + bob + PL.facing[1] * 2, 5, 0, 7); g.fill();
    g.fillStyle = '#ff963c'; g.fillRect(-8, 2 + bob, 16, 3);
    g.restore();
    // minimap
    const mmW = Math.min(170, w * 0.28), mmS = mmW / s.map.w;
    const mx0 = 12, my0 = hh - s.map.h * mmS - 12;
    if (w > 700) {
      g.globalAlpha = 0.85; g.drawImage(PL.mapCanvas, mx0, my0, s.map.w * mmS, s.map.h * mmS); g.globalAlpha = 1;
      g.strokeStyle = '#2a3a5e'; g.strokeRect(mx0, my0, s.map.w * mmS, s.map.h * mmS);
      g.fillStyle = '#fff'; g.fillRect(mx0 + pl.pos_x * mmS - 2, my0 + pl.pos_y * mmS - 2, 4, 4);
      g.fillStyle = '#5adcc8'; g.fillRect(mx0 + ax * mmS - 2, my0 + ay * mmS - 2, 4, 4);
    }
  }

  // =============================================================== BATTLE
  const B = { battle: null, queue: [], menu: 'main', finished: false, shake: 0, flash: 0, enemyIn: 0, lungeMe: 0, lungeEn: 0, pod: 0 };
  function startBattle(enemy, alpha) {
    const s = G.session;
    Object.assign(B, { battle: s.startBattle(enemy, alpha), menu: 'main', finished: false, shake: 0, flash: 0, enemyIn: 0, pod: 0 });
    B.queue = [(alpha ? 'ALPHA ENCOUNTER! ' : '') + `A wild ${enemy.name} (Lv ${enemy.level}) appeared!`];
    if (enemy.aberrant) B.queue.push('Its colouring is unusual... an ABERRANT mutation!');
    B.queue.push(`Go, ${B.battle.me.name}!`);
    show('battle');
    renderBattleUi();
  }
  function infoBox(el, c, isMe) {
    const cur = EX.xpForLevel(c.level), nxt = EX.xpForLevel(c.level + 1);
    const f = c.hp / c.maxHp;
    el.innerHTML = '';
    if (!isMe && B.battle.alpha) el.append(h('div', { class: 'alpha-tag' }, 'ALPHA SPECIMEN'));
    el.append(...[h('div', { class: 'top' }, h('span', { class: 'nm' }, c.name, c.status ? h('span', { class: 'st' }, c.status.toUpperCase()) : null), h('span', { class: 'muted' }, `Lv ${c.level}`)),
      h('div', { style: 'margin:4px 0 8px' }, c.species.types.map(badge),
        !isMe ? h('span', { class: 'r-' + c.species.rarity, style: 'font-size:12px;margin-left:4px' }, ((G.session.discovery(c.species.id) || {}).scanned ? c.species.rarity : '')) : null),
      bar(f, '', hpColor(f)),
      h('div', { class: 'muted', style: 'font-size:12px;text-align:right;margin-top:3px' }, `${c.hp}/${c.maxHp} HP`),
      isMe ? bar((c.xp - cur) / (nxt - cur), 'xp') : null].filter(Boolean));
  }
  function renderBattleUi() {
    const b = B.battle, s = G.session;
    infoBox($('#b-enemy'), b.enemy, false);
    infoBox($('#b-me'), b.me, true);
    const msg = $('#msgbox'), cmds = $('#cmds');
    cmds.innerHTML = ''; cmds.className = 'cmds';
    if (B.queue.length) {
      msg.innerHTML = `${esc(B.queue[0])}<span class="more">▼ tap / Space</span>`;
      return;
    }
    const me = b.me;
    const add = (label, sub, fn, dis, cls = '') => {
      const bt = h('button', { class: 'btn ' + cls, disabled: !!dis, onclick: fn }, label);
      if (sub) bt.append(h('small', { html: sub }));
      cmds.append(bt);
    };
    if (B.menu === 'main') {
      msg.textContent = `What will ${me.name} do?`;
      const pods = s.qty('pod') + s.qty('pod_plus') + s.qty('pod_max');
      add('Fight', '1', () => { B.menu = 'fight'; renderBattleUi(); });
      add('Scan', b.scanned ? 'done' : '2 · log + DNA', () => act(['scan']), false);
      add('Capture', `3 · ${pods} pods`, () => { B.menu = 'capture'; renderBattleUi(); }, !pods);
      add('Items', '4', () => { B.menu = 'items'; renderBattleUi(); });
      add('Swap', '5', () => { B.menu = 'swap'; renderBattleUi(); }, b.team.filter((c) => !c.fainted).length < 2);
      add('Flee', b.alpha ? 'blocked' : '6', () => act(['flee']));
      return;
    }
    cmds.className = 'cmds two';
    if (B.menu === 'fight') {
      msg.textContent = 'Choose a move. Green = super effective.';
      me.moves.forEach((mid, i) => {
        const m = D.moves[mid];
        const eff = m.power ? D.effectiveness(m.type, b.enemy.species.types) : 1;
        const tag = eff >= 2 ? '<span class="eff">super effective</span>' : eff < 1 ? 'not very effective' : '';
        add(m.name, `<span class="badge t-${m.type}">${m.type}</span> ${m.power ? 'pow ' + m.power : esc(m.description)} ${tag}`, () => act(['move', i]));
      });
    } else if (B.menu === 'capture') {
      msg.textContent = 'Weaken it first — low HP and status effects raise capture odds.';
      for (const pod of ['pod', 'pod_plus', 'pod_max']) {
        add(`${D.items[pod].name} ×${s.qty(pod)}`, `~${Math.round(b.captureChance(pod) * 100)}% chance`, () => act(['capture', pod]), !s.qty(pod));
      }
    } else if (B.menu === 'items') {
      msg.textContent = 'Use an item.';
      add(`MedGel ×${s.qty('medgel')}`, `+50 HP to ${me.name}`, () => act(['item', 'medgel', b.active]), !s.qty('medgel') || me.hp >= me.maxHp);
      add(`MedGel+ ×${s.qty('medgel_plus')}`, `+150 HP to ${me.name}`, () => act(['item', 'medgel_plus', b.active]), !s.qty('medgel_plus') || me.hp >= me.maxHp);
      const fi = b.team.findIndex((c) => c.fainted);
      if (fi >= 0) add(`Revive ×${s.qty('revive')}`, `revive ${b.team[fi].name}`, () => act(['item', 'revive', fi]), !s.qty('revive'));
    } else if (B.menu === 'swap') {
      msg.textContent = 'Switch your active creature (uses your turn).';
      b.team.forEach((c, i) => add(`${c.name} Lv${c.level}`, `${c.hp}/${c.maxHp} HP`, () => act(['swap', i]), c.fainted || i === b.active));
    }
    add('Back', 'Esc', () => { B.menu = 'main'; renderBattleUi(); });
  }
  function act(action) {
    const b = B.battle;
    const before = [b.me.hp, b.enemy.hp];
    b.lastHit = null;
    const msgs = b.act(action);
    if (action[0] === 'capture') B.pod = 1.4;
    if (b.enemy.hp < before[1]) { B.flash = 0.45; B.lungeMe = 0.25; }
    if (b.me.hp < before[0]) { B.shake = 0.4; B.lungeEn = 0.25; }
    B.queue = B.queue.concat(msgs);
    B.menu = 'main';
    if (b.result && !B.finished) {
      B.finished = true;
      B.queue = B.queue.concat(G.session.finishBattle(b));
      save();
    }
    if (!B.queue.length) B.queue.push('...');
    renderBattleUi();
  }
  function advance() {
    if (!B.queue.length) return;
    B.queue.shift();
    if (!B.queue.length && B.finished) {
      if (G.session.map) { enterPlanet(); } else renderLab('Galaxy');
      return;
    }
    renderBattleUi();
  }
  function drawBattle(dt) {
    const b = B.battle;
    if (!b) return;
    const [g, w, hh] = fitCanvas($('#battle-canvas'));
    const biome = G.session.planet ? G.session.planet.biome : 'forest';
    const [top, bot] = BIOME[biome].sky;
    const grd = g.createLinearGradient(0, 0, 0, hh);
    grd.addColorStop(0, top); grd.addColorStop(0.62, bot); grd.addColorStop(0.62, '#0c1222'); grd.addColorStop(1, '#070b16');
    g.fillStyle = grd; g.fillRect(0, 0, w, hh);
    // distant hills
    g.fillStyle = 'rgba(0,0,0,.18)';
    g.beginPath(); g.moveTo(0, hh * 0.62);
    for (let x = 0; x <= w; x += 20) g.lineTo(x, hh * 0.62 - 30 - Math.sin(x / 90 + 1.3) * 22 - Math.sin(x / 37) * 8);
    g.lineTo(w, hh * 0.62); g.fill();
    B.shake = Math.max(0, B.shake - dt); B.flash = Math.max(0, B.flash - dt); B.enemyIn = Math.min(1, B.enemyIn + dt * 2.2);
    B.lungeMe = Math.max(0, B.lungeMe - dt); B.lungeEn = Math.max(0, B.lungeEn - dt); B.pod = Math.max(0, B.pod - dt);
    const t = G.time;
    const mobile = w < 860;
    const eSize = Math.min(mobile ? 170 : 250, w * 0.32), mSize = Math.min(mobile ? 180 : 270, w * 0.34);
    const ex = w * (mobile ? 0.7 : 0.72), ey = hh * (mobile ? 0.3 : 0.33);
    const mx = w * (mobile ? 0.28 : 0.27), my = hh * (mobile ? 0.5 : 0.56);
    // platforms
    g.fillStyle = 'rgba(0,0,0,.28)';
    g.beginPath(); g.ellipse(ex, ey + eSize * 0.38, eSize * 0.55, eSize * 0.12, 0, 0, 7); g.fill();
    g.beginPath(); g.ellipse(mx, my + mSize * 0.38, mSize * 0.6, mSize * 0.13, 0, 0, 7); g.fill();
    // enemy
    const enemyVisible = !b.enemy.fainted || (B.queue.length && !B.finished) || b.result === 'captured' && B.pod > 0;
    if (enemyVisible && !(b.result === 'captured' && B.pod <= 0.5)) {
      const slide = (1 - B.enemyIn) * w * 0.5;
      const lunge = B.lungeEn > 0 ? -Math.sin(B.lungeEn / 0.25 * Math.PI) * 30 : 0;
      const spr = EX.sprite(b.enemy.species, eSize, b.enemy.aberrant);
      g.save();
      if (B.flash > 0 && Math.floor(t * 24) % 2) g.globalAlpha = 0.35;
      if (b.enemy.fainted && b.result === 'win') g.globalAlpha = 0.25;
      g.drawImage(spr, ex - eSize / 2 + slide + lunge, ey - eSize / 2 + Math.sin(t * 2) * 6, eSize, eSize);
      g.restore();
    }
    // capture pod animation
    if (B.pod > 0) {
      const k = 1 - B.pod / 1.4;
      const fly = Math.min(1, k * 2.5);
      const px = mx + (ex - mx) * fly, py = my - Math.sin(fly * Math.PI) * hh * 0.25 + (ey - my) * fly;
      const wob = fly >= 1 ? Math.sin(t * 20) * 6 * (1 - k) : 0;
      g.save(); g.translate(px, py); g.rotate(wob / 20);
      g.fillStyle = '#e6ecf5'; g.beginPath(); g.arc(0, 0, 14, Math.PI, 0); g.fill();
      g.fillStyle = '#5adcc8'; g.beginPath(); g.arc(0, 0, 14, 0, Math.PI); g.fill();
      g.fillStyle = '#0b1020'; g.fillRect(-14, -2, 28, 4); g.beginPath(); g.arc(0, 0, 4, 0, 7); g.fill();
      g.restore();
    }
    // player creature (back view = mirrored)
    const me = b.me;
    const shake = B.shake > 0 ? Math.sin(t * 70) * 7 : 0;
    const lungeM = B.lungeMe > 0 ? Math.sin(B.lungeMe / 0.25 * Math.PI) * 34 : 0;
    g.save();
    g.translate(mx + shake + lungeM, my + Math.sin(t * 2 + 1) * 5);
    g.scale(-1, 1);
    if (me.fainted) g.globalAlpha = 0.3;
    g.drawImage(EX.sprite(me.species, mSize, me.aberrant), -mSize / 2, -mSize / 2, mSize, mSize);
    g.restore();
    // particles for biome
    g.fillStyle = biome === 'lava' ? 'rgba(255,140,60,.6)' : biome === 'ice' ? 'rgba(255,255,255,.7)' : 'rgba(200,255,220,.35)';
    for (let i = 0; i < 24; i++) {
      const px = (EX.hash2(i, 1, 9) * w + t * 20 * (biome === 'ice' ? -1 : 1) * (0.5 + EX.hash2(i, 2, 9))) % w;
      const py = (EX.hash2(i, 3, 9) * hh * 0.6 + (biome === 'lava' ? -t * 30 : t * 25) * (0.5 + EX.hash2(i, 4, 9)) % (hh * 0.6) + hh * 0.6) % (hh * 0.6);
      g.fillRect((px + w) % w, py, 2, 2);
    }
    document.documentElement.style.setProperty('--console-h', $('#console').offsetHeight + 'px');
  }

  // ================================================================ INPUT
  const KEYDIR = { ArrowUp: [0, -1], w: [0, -1], W: [0, -1], ArrowDown: [0, 1], s: [0, 1], S: [0, 1],
    ArrowLeft: [-1, 0], a: [-1, 0], A: [-1, 0], ArrowRight: [1, 0], d: [1, 0], D: [1, 0] };
  const keysDown = new Set();
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (G.screen === 'planet') {
      if (KEYDIR[e.key]) {
        e.preventDefault();
        if (!keysDown.has(e.key)) { keysDown.add(e.key); PL.held = KEYDIR[e.key]; PL.cd = 0; }
      } else if (e.key === 'e' || e.key === 'E' || e.key === ' ') { e.preventDefault(); doGather(); }
      else if (e.key === 'l' || e.key === 'L') doLure();
      else if (e.key === 'r' || e.key === 'R') doOrbit();
    } else if (G.screen === 'battle') {
      if (B.queue.length) { if ([' ', 'Enter', 'z', 'Z'].includes(e.key)) { e.preventDefault(); advance(); } return; }
      if (e.key === 'Escape' && B.menu !== 'main') { B.menu = 'main'; renderBattleUi(); return; }
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= 6) {
        const btns = [...document.querySelectorAll('#cmds .btn')];
        if (btns[n - 1] && !btns[n - 1].disabled) btns[n - 1].click();
      }
    } else if (G.screen === 'starter' && e.key === 'Enter') startGame();
  });
  window.addEventListener('keyup', (e) => {
    keysDown.delete(e.key);
    if (KEYDIR[e.key]) {
      const rest = [...keysDown].filter((k) => KEYDIR[k]);
      PL.held = rest.length ? KEYDIR[rest[rest.length - 1]] : null;
    }
  });
  window.addEventListener('blur', () => { keysDown.clear(); PL.held = null; });
  document.querySelectorAll('#dpad button').forEach((bt) => {
    const d = bt.dataset.d.split(',').map(Number);
    const start = (e) => { e.preventDefault(); PL.held = d; PL.cd = 0; };
    const end = (e) => { e.preventDefault(); PL.held = null; };
    bt.addEventListener('pointerdown', start);
    ['pointerup', 'pointerleave', 'pointercancel'].forEach((ev) => bt.addEventListener(ev, end));
  });
  // tap-to-walk on the planet canvas (mobile friendly)
  $('#planet-canvas').addEventListener('pointerdown', (e) => {
    const r = e.target.getBoundingClientRect();
    const dx = e.clientX - r.left - r.width / 2, dy = e.clientY - r.top - r.height / 2;
    PL.held = Math.abs(dx) > Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)];
    PL.cd = 0;
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach((ev) => $('#planet-canvas').addEventListener(ev, () => { if (!keysDown.size) PL.held = null; }));
  $('#btn-gather').onclick = doGather;
  $('#btn-lure').onclick = doLure;
  $('#btn-orbit').onclick = doOrbit;
  $('#msgbox').onclick = advance;
  $('#starter-go').onclick = startGame;
  $('#starter-back').onclick = renderTitle;
  $('#import-file').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const sess = await Store.importFile(f);
      const slot = [1, 2, 3].find((n) => !Store.meta(n)) || 3;
      G.session = sess; G.slot = slot; save();
      toast(`Imported ${sess.player.name}'s save into slot ${slot}.`, 'good');
      renderTitle();
    } catch (err) { toast('Import failed: ' + err.message, 'warn'); }
    e.target.value = '';
  });

  // ================================================================= LOOP
  let last = performance.now(), saveTimer = 0, playTimer = 0;
  function frame(now) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now; G.time += dt;
    if (G.screen === 'title' || G.screen === 'starter' || G.screen === 'lab') drawStars();
    if (G.screen === 'title') drawParade();
    if (G.screen === 'lab' && LAB.tab === 'Galaxy') drawGalaxy();
    if (G.screen === 'planet') drawPlanet(dt);
    if (G.screen === 'battle') drawBattle(dt);
    if (G.session && G.screen !== 'title') {
      playTimer += dt;
      if (playTimer >= 1) { G.session.player.playtime_s += Math.floor(playTimer); playTimer %= 1; }
      saveTimer += dt;
      if (saveTimer > 15 && G.dirty) { saveTimer = 0; G.dirty = false; save(); }
    }
    requestAnimationFrame(frame);
  }
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', () => { if (document.hidden) save(); });

  // ================================================================= BOOT
  function loadScript(src, ms) {
    return new Promise((resolve) => {
      const sc = document.createElement('script');
      const timer = setTimeout(() => resolve(false), ms);
      sc.src = src; sc.onload = () => { clearTimeout(timer); resolve(true); }; sc.onerror = () => { clearTimeout(timer); resolve(false); };
      document.head.append(sc);
    });
  }
  EX.SQLJS_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/';
  async function boot() {
    renderTitle();
    requestAnimationFrame(frame);
    if (!/[?&]nosql\b/.test(location.search) && await loadScript(EX.SQLJS_CDN + 'sql-wasm.js', 8000)) await Store.init();
    G.ready = true;
    renderTitle();
  }
  EX.ui = { renderTitle, renderLab, enterPlanet, startBattle, act, advance, doGather, doOrbit, planetStep, B, PL, LAB };
  boot();
})(window.EX = window.EX || {});
