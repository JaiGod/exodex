/* ExoDex core rules - a JavaScript port of the Python `exodex` package
   (data.py, creature.py, procgen.py, battle.py, session.py). No DOM code here. */
(function (EX) {
  'use strict';
  const R = EX.R;
  const RAW = window.EXODEX_DATA;

  // ------------------------------------------------------------------ data
  const RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
  const RARITY_CAPTURE = { common: 1.0, uncommon: 0.75, rare: 0.5, epic: 0.3, legendary: 0.12 };
  const RARITY_RP = { common: 5, uncommon: 8, rare: 12, epic: 20, legendary: 40 };
  const D = {
    raw: RAW,
    types: RAW.types,
    chart: RAW.type_chart,
    moves: {}, species: {}, planets: {}, items: {}, research: {},
    recipes: RAW.recipes, missions: RAW.missions,
    traits: {}, rarityWeight: RAW.rarity_weight, prevStage: {},
  };
  RAW.moves.forEach((m) => (D.moves[m.id] = m));
  RAW.species.forEach((s) => {
    s.types = s.type2 ? [s.type1, s.type2] : [s.type1];
    s.baseTotal = s.hp + s.atk + s.defense + s.spd;
    D.species[s.id] = s;
    if (s.evolves_to) D.prevStage[s.evolves_to] = s.id;
  });
  RAW.planets.forEach((p) => (D.planets[p.id] = p));
  RAW.items.forEach((i) => (D.items[i.id] = i));
  RAW.research.forEach((r) => (D.research[r.id] = r));
  RAW.traits.forEach((t) => (D.traits[t.name] = t.description));
  D.speciesList = RAW.species;

  D.movesAt = function (sp, level) {
    const learned = [];
    for (const [lv, mid] of sp.learnset) if (lv <= level && !learned.includes(mid)) learned.push(mid);
    return learned.slice(-4);
  };
  D.effectiveness = function (moveType, defTypes) {
    const c = D.chart[moveType];
    if (!c) return 1;
    let m = 1;
    for (const t of defTypes) { if (c[0].includes(t)) m *= 2; else if (c[1].includes(t)) m *= 0.5; }
    return m;
  };
  D.starters = function () {
    return ['FLORA', 'HYDRO', 'THERMAL'].map((t) => D.speciesList.find((s) =>
      s.type1 === t && s.stage === 1 && s.evolves_to && D.species[s.evolves_to].evolves_to && s.rarity === 'common'));
  };
  D.minWildLevel = (sp) => (D.prevStage[sp.id] ? D.species[D.prevStage[sp.id]].evolve_level : 1);

  // -------------------------------------------------------------- creature
  const TRAIT_STAT = { Hardy: 'hp', Ferocious: 'atk', Armored: 'def', Swift: 'spd' };
  const xpForLevel = (l) => Math.floor(l ** 3 * 0.8);

  class Creature {
    constructor(o) {
      Object.assign(this, { xp: 0, hp: -1, aberrant: false, nickname: null, id: null, team_slot: null,
        planet_id: null }, o);
      if (this.xp < xpForLevel(this.level)) this.xp = xpForLevel(this.level);
      if (this.hp < 0) this.hp = this.maxHp;
      this.resetBattle();
    }
    static generate(sp, level, trait, ivMin = 0, ivMax = 12) {
      const ivs = {};
      ['hp', 'atk', 'def', 'spd'].forEach((k) => (ivs[k] = R.randint(ivMin, ivMax)));
      return new Creature({ species: sp, level, trait: trait || R.choice(Object.keys(D.traits)), ivs,
        moves: D.movesAt(sp, level), aberrant: Math.random() < 1 / 64 });
    }
    get name() { return this.nickname || this.species.name; }
    _stat(base, iv, key) {
      let v = Math.floor((2 * base + iv * 2) * this.level / 100) + 5;
      if (TRAIT_STAT[this.trait] === key) v = Math.floor(v * 1.12);
      if (this.trait === 'Volatile' && key === 'def') v = Math.floor(v * 0.92);
      return Math.max(1, v);
    }
    get maxHp() {
      let v = Math.floor((2 * this.species.hp + this.ivs.hp * 2) * this.level / 100) + this.level + 10;
      if (this.trait === 'Hardy') v = Math.floor(v * 1.12);
      return v;
    }
    get atk() { return this._stat(this.species.atk, this.ivs.atk, 'atk'); }
    get defense() { return this._stat(this.species.defense, this.ivs.def, 'def'); }
    get spd() { return this._stat(this.species.spd, this.ivs.spd, 'spd'); }
    get fainted() { return this.hp <= 0; }
    get ivTotal() { return this.ivs.hp + this.ivs.atk + this.ivs.def + this.ivs.spd; }
    resetBattle() { this.status = null; this.statusTurns = 0; this.stages = { atk: 0, def: 0, spd: 0, acc: 0 }; }
    healFull() { this.hp = this.maxHp; this.status = null; }
    xpReward(alpha) { return Math.floor(this.species.baseTotal / 4 * this.level / 4 * (alpha ? 1.6 : 1)); }
    gainXp(amount) {
      if (this.trait === 'Ancient') amount = Math.floor(amount * 1.25);
      const msgs = [`${this.name} gained ${amount} XP.`];
      this.xp += amount;
      while (this.level < 100 && this.xp >= xpForLevel(this.level + 1)) {
        const oldMax = this.maxHp;
        this.level++;
        this.hp += this.maxHp - oldMax;
        msgs.push(`${this.name} grew to level ${this.level}!`);
        for (const [lv, mid] of this.species.learnset) {
          if (lv === this.level && !this.moves.includes(mid)) {
            if (this.moves.length >= 4) msgs.push(`${this.name} forgot ${D.moves[this.moves.shift()].name}...`);
            this.moves.push(mid);
            msgs.push(`${this.name} learned ${D.moves[mid].name}!`);
          }
        }
      }
      return msgs;
    }
    canEvolve() { const s = this.species; return !!(s.evolves_to && s.evolve_level && this.level >= s.evolve_level); }
    evolve() {
      const old = this.name;
      const frac = this.hp / this.maxHp;
      this.species = D.species[this.species.evolves_to];
      this.hp = Math.max(1, Math.floor(this.maxHp * frac));
      for (const mid of D.movesAt(this.species, this.level)) {
        if (!this.moves.includes(mid)) { if (this.moves.length >= 4) this.moves.shift(); this.moves.push(mid); }
      }
      return `${old} evolved into ${this.species.name}!`;
    }
    toRow() {
      return { id: this.id, species_id: this.species.id, nickname: this.nickname, level: this.level, xp: this.xp,
        hp_current: Math.max(0, this.hp), trait: this.trait, iv_hp: this.ivs.hp, iv_atk: this.ivs.atk,
        iv_def: this.ivs.def, iv_spd: this.ivs.spd, aberrant: this.aberrant ? 1 : 0, team_slot: this.team_slot,
        moves: this.moves.join(','), planet_id: this.planet_id, caught_at: this.caught_at || new Date().toISOString() };
    }
    static fromRow(r) {
      return new Creature({ species: D.species[r.species_id], level: r.level, trait: r.trait,
        ivs: { hp: r.iv_hp, atk: r.iv_atk, def: r.iv_def, spd: r.iv_spd },
        moves: String(r.moves).split(',').filter(Boolean).map(Number), xp: r.xp, hp: r.hp_current,
        aberrant: !!r.aberrant, nickname: r.nickname, id: r.id, team_slot: r.team_slot,
        planet_id: r.planet_id, caught_at: r.caught_at });
    }
  }

  // ------------------------------------------------------------- planet map
  const MAP_W = 56, MAP_H = 40;
  const T = { GROUND: 0, BIOZONE: 1, HAZARD: 2, ROCK: 3, NODE: 4, PAD: 5, NEST: 6 };
  const WALK = new Set([T.GROUND, T.BIOZONE, T.NODE, T.PAD, T.NEST]);

  class PlanetMap {
    constructor(planet) {
      this.planet = planet; this.w = MAP_W; this.h = MAP_H;
      this.tiles = []; this.shade = []; this.nodes = new Set();
      this._generate();
    }
    _generate() {
      const seed = this.planet.seed;
      for (let y = 0; y < this.h; y++) {
        const row = [], srow = [];
        for (let x = 0; x < this.w; x++) {
          const e = EX.fractalNoise(x / 9.0, y / 9.0, seed);
          const m = EX.fractalNoise(x / 6.0, y / 6.0, seed + 77);
          srow.push(m);
          const edge = Math.min(x, y, this.w - 1 - x, this.h - 1 - y);
          let t;
          if (edge === 0) t = T.ROCK; else if (e < 0.34) t = T.HAZARD; else if (e > 0.70) t = T.ROCK;
          else if (m > 0.55) t = T.BIOZONE; else t = T.GROUND;
          row.push(t);
        }
        this.tiles.push(row); this.shade.push(srow);
      }
      const cx = Math.floor(this.w / 2), cy = Math.floor(this.h / 2);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) this.tiles[cy + dy][cx + dx] = T.GROUND;
      this.tiles[cy][cx] = T.PAD;
      this.pad = [cx, cy];
      const dist = this.distances(this.pad);
      const order = [...dist.keys()].map((k) => k.split(',').map(Number))
        .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      // farthest reachable tile (same tie-break as Python: max of (dist, -y, -x))
      let far = order[0];
      for (const p of order) {
        const dp = dist.get(p.join(',')), df = dist.get(far.join(','));
        if (dp > df || (dp === df && (-p[1] > -far[1] || (-p[1] === -far[1] && -p[0] > -far[0])))) far = p;
      }
      this.nest = far;
      this.tiles[far[1]][far[0]] = T.NEST;
      const rng = EX.mulberry32(seed);
      const cand = order.filter((p) => (this.tiles[p[1]][p[0]] === T.GROUND || this.tiles[p[1]][p[0]] === T.BIOZONE)
        && Math.abs(p[0] - cx) + Math.abs(p[1] - cy) > 3);
      for (let i = 0; i < 26 && cand.length; i++) {
        const idx = Math.floor(rng() * cand.length);
        const p = cand.splice(idx, 1)[0];
        this.tiles[p[1]][p[0]] = T.NODE;
        this.nodes.add(p.join(','));
      }
    }
    distances(start) {
      const dist = new Map([[start.join(','), 0]]);
      const q = [start];
      while (q.length) {
        const [x, y] = q.shift();
        const d = dist.get(x + ',' + y);
        for (const [nx, ny] of [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]]) {
          if (nx >= 0 && ny >= 0 && nx < this.w && ny < this.h && WALK.has(this.tiles[ny][nx])) {
            const k = nx + ',' + ny;
            if (!dist.has(k)) { dist.set(k, d + 1); q.push([nx, ny]); }
          }
        }
      }
      return dist;
    }
    tile(x, y) { return (x >= 0 && y >= 0 && x < this.w && y < this.h) ? this.tiles[y][x] : T.ROCK; }
    walkable(x, y) { return WALK.has(this.tile(x, y)); }
    harvest(x, y) {
      const k = x + ',' + y;
      if (this.nodes.has(k)) { this.nodes.delete(k); this.tiles[y][x] = T.GROUND; return true; }
      return false;
    }
  }

  function rollWild(planet, lure) {
    const pool = D.speciesList.filter((s) => s.biomes.includes(planet.biome) && s.rarity !== 'legendary');
    const weights = pool.map((s) => {
      let w = D.rarityWeight[s.rarity];
      if (lure && (s.rarity === 'rare' || s.rarity === 'epic')) w *= 3;
      w /= (1 + (s.stage - 1) * 1.5);
      if (D.minWildLevel(s) > planet.max_level + 2) w = 0;
      return w;
    });
    const sp = R.weighted(pool, weights);
    const level = Math.max(R.randint(planet.min_level, planet.max_level), D.minWildLevel(sp));
    return Creature.generate(sp, level);
  }
  function alphaCreature(planet) {
    const c = Creature.generate(D.species[planet.alpha_species], planet.alpha_level, 'Hardy', 15, 15);
    c.hp = c.maxHp;
    return c;
  }

  // ----------------------------------------------------------------- battle
  const CAPTURE_MULT = { pod: 1.0, pod_plus: 1.8, pod_max: 3.0 };
  const STATUS_NAMES = { burn: 'burned', freeze: 'frozen', poison: 'poisoned', stun: 'stunned', sleep: 'asleep' };
  const stageMult = (s) => (s >= 0 ? (2 + s) / 2 : 2 / (2 - s));

  class Battle {
    constructor(team, enemy, opts) {
      Object.assign(this, { team, enemy, alpha: false, inventory: null, scannerLevel: 0, containmentLevel: 0 }, opts);
      this.active = team.findIndex((c) => !c.fainted);
      this.turns = 0; this.result = null; this.scanned = false;
      this.participants = new Set([this.active]);
      team.forEach((c) => c.resetBattle()); enemy.resetBattle();
    }
    get me() { return this.team[this.active]; }
    act(action) {
      if (this.result) return [];
      this.turns++;
      let msgs = [];
      const kind = action[0];
      const em = this._enemyChoice();
      if (kind === 'move') {
        const mv = D.moves[this.me.moves[action[1]]];
        if (this._speed(this.me) >= this._speed(this.enemy)) {
          msgs = msgs.concat(this._useMove(this.me, this.enemy, mv));
          if (!this.enemy.fainted && !this.me.fainted) msgs = msgs.concat(this._useMove(this.enemy, this.me, em));
        } else {
          msgs = msgs.concat(this._useMove(this.enemy, this.me, em));
          if (!this.me.fainted && !this.enemy.fainted) msgs = msgs.concat(this._useMove(this.me, this.enemy, mv));
        }
      } else {
        if (kind === 'flee') {
          if (this.alpha) msgs.push('The Alpha blocks your escape!');
          else {
            const chance = 0.5 + 0.5 * this._speed(this.me) / Math.max(1, this._speed(this.enemy));
            if (Math.random() < Math.min(0.95, chance)) { this.result = 'fled'; return msgs.concat(['You retreated safely.']); }
            msgs.push("Couldn't get away!");
          }
        } else if (kind === 'scan') msgs = msgs.concat(this._scan());
        else if (kind === 'capture') { msgs = msgs.concat(this._capture(action[1])); if (this.result) return msgs; }
        else if (kind === 'item') msgs = msgs.concat(this._useItem(action[1], action[2]));
        else if (kind === 'swap') { this.active = action[1]; this.participants.add(this.active); msgs.push(`Go, ${this.me.name}!`); }
        if (!this.enemy.fainted) msgs = msgs.concat(this._useMove(this.enemy, this.me, em));
      }
      msgs = msgs.concat(this._endOfTurn(), this._checkFaints());
      return msgs;
    }
    _speed(c) { return c.spd * stageMult(c.stages.spd) * (c.status === 'stun' ? 0.5 : 1); }
    _enemyChoice() {
      const moves = this.enemy.moves.map((m) => D.moves[m]);
      if (this.enemy.hp < this.enemy.maxHp * 0.3) {
        const heals = moves.filter((m) => m.effect === 'heal');
        if (heals.length && Math.random() < 0.7) return heals[0];
      }
      if (Math.random() < 0.7) {
        const score = (m) => m.power === 0 ? 25 : m.power * D.effectiveness(m.type, this.me.species.types)
          * (this.enemy.species.types.includes(m.type) ? 1.25 : 1) * m.accuracy / 100;
        return moves.reduce((a, b) => (score(b) > score(a) ? b : a));
      }
      return R.choice(moves);
    }
    _blocked(u) {
      if (u.status === 'freeze') {
        if (Math.random() < 0.3) { u.status = null; return `${u.name} thawed out!`; }
        return `${u.name} is frozen solid!`;
      }
      if (u.status === 'sleep') {
        u.statusTurns--;
        if (u.statusTurns <= 0) { u.status = null; return `${u.name} woke up!`; }
        return `${u.name} is fast asleep.`;
      }
      if (u.status === 'stun' && Math.random() < 0.25) return `${u.name} is stunned and can't move!`;
      return null;
    }
    damage(u, t, mv, crit, roll) {
      const atk = u.atk * stageMult(u.stages.atk) * (u.status === 'burn' ? 0.75 : 1);
      const dfn = t.defense * stageMult(t.stages.def);
      const base = ((2 * u.level / 5 + 2) * mv.power * atk / dfn) / 50 + 2;
      let eff = D.effectiveness(mv.type, t.species.types);
      if (eff > 1 && t.trait === 'Adaptive') eff *= 0.75;
      const stab = u.species.types.includes(mv.type) ? 1.25 : 1;
      const dmg = base * eff * stab * roll * (crit ? 1.5 : 1) * (u.trait === 'Volatile' ? 1.2 : 1);
      return [Math.max(1, Math.floor(dmg)), eff];
    }
    _useMove(u, t, mv) {
      const blocked = this._blocked(u);
      if (blocked) return [blocked];
      const msgs = [`${u.name} used ${mv.name}!`];
      const acc = mv.accuracy * stageMult(u.stages.acc);
      if ((mv.power > 0 || mv.effect === 'sleep') && Math.random() * 100 > acc) return msgs.concat(['...but it missed!']);
      if (mv.power > 0) {
        const crit = Math.random() < (1 / 16) * (u.trait === 'Bioluminescent' ? 2 : 1);
        const [dmg, eff] = this.damage(u, t, mv, crit, R.uniform(0.85, 1));
        t.hp = Math.max(0, t.hp - dmg);
        this.lastHit = { target: t, dmg, eff };
        if (crit) msgs.push('A critical hit!');
        if (eff >= 2) msgs.push("It's super effective!"); else if (eff < 1) msgs.push("It's not very effective...");
        if (mv.effect === 'drain') { const h = Math.floor(dmg / 2); u.hp = Math.min(u.maxHp, u.hp + h); msgs.push(`${u.name} drained ${h} HP.`); }
        else if (STATUS_NAMES[mv.effect] && !t.fainted && Math.random() < 0.3) msgs.push(...this._status(t, mv.effect));
        else if (mv.effect && mv.effect.startsWith('debuff') && Math.random() < 0.4) {
          const st = mv.effect.split('_')[1]; t.stages[st] = Math.max(-3, t.stages[st] - 1);
          msgs.push(`${t.name}'s ${st.toUpperCase()} fell!`);
        }
      } else {
        const e = mv.effect;
        if (e === 'heal') { u.hp = Math.min(u.maxHp, u.hp + Math.floor(u.maxHp * 0.4)); msgs.push(`${u.name} restored HP!`); }
        else if (e && e.startsWith('buff')) { const st = e.split('_')[1]; u.stages[st] = Math.min(3, u.stages[st] + 1); msgs.push(`${u.name}'s ${st.toUpperCase()} rose!`); }
        else if (e === 'sleep') msgs.push(...this._status(t, 'sleep'));
      }
      return msgs;
    }
    _status(t, s) {
      if (t.status) return [];
      if (t.trait === 'Resilient') return [`${t.name}'s Resilient trait blocks the effect!`];
      t.status = s; t.statusTurns = s === 'sleep' ? R.randint(1, 3) : 0;
      return [`${t.name} is ${STATUS_NAMES[s]}!`];
    }
    _endOfTurn() {
      const msgs = [];
      for (const c of [this.me, this.enemy]) {
        if (c.fainted) continue;
        if (c.status === 'burn' || c.status === 'poison') {
          c.hp = Math.max(0, c.hp - Math.max(1, Math.floor(c.maxHp * (c.status === 'burn' ? 0.06 : 0.08))));
          msgs.push(`${c.name} is hurt by its ${c.status}.`);
        }
        if (c.trait === 'Regenerative' && !c.fainted && c.hp < c.maxHp) {
          c.hp = Math.min(c.maxHp, c.hp + Math.max(1, Math.floor(c.maxHp * 0.06)));
          msgs.push(`${c.name} regenerates.`);
        }
      }
      return msgs;
    }
    _checkFaints() {
      const msgs = [];
      if (this.enemy.fainted) {
        msgs.push(`The wild ${this.enemy.name} fainted!`);
        this.result = 'win';
        const xp = this.enemy.xpReward(this.alpha);
        this.team.forEach((c, i) => { if (!c.fainted) msgs.push(...c.gainXp(this.participants.has(i) ? xp : Math.floor(xp / 2))); });
        return msgs;
      }
      if (this.me.fainted) {
        msgs.push(`${this.me.name} fainted!`);
        const nxt = this.team.findIndex((c) => !c.fainted);
        if (nxt < 0) { this.result = 'loss'; msgs.push('Your team was defeated... emergency beacon activated.'); }
        else { this.active = nxt; this.participants.add(nxt); msgs.push(`Go, ${this.me.name}!`); }
      }
      return msgs;
    }
    _scan() {
      const e = this.enemy; this.scanned = true;
      const dna = 1 + this.scannerLevel;
      return [`Scanning ${e.name}... [${e.species.types.join('/')}] ${e.species.kingdom}, ${e.species.rarity.toUpperCase()}.`,
        `Trait: ${e.trait}. Collected ${dna} DNA sample${dna > 1 ? 's' : ''}.`];
    }
    captureChance(pod) {
      const e = this.enemy;
      const hpF = 1 - (2 / 3) * (e.hp / e.maxHp);
      const st = (e.status === 'sleep' || e.status === 'freeze') ? 1.6 : e.status ? 1.25 : 1;
      const c = hpF * RARITY_CAPTURE[e.species.rarity] * CAPTURE_MULT[pod] * st * (1 + 0.15 * this.containmentLevel) * (this.alpha ? 0.5 : 1);
      return Math.max(0.02, Math.min(0.95, c));
    }
    _capture(pod) {
      if (this.inventory && !this.inventory.removeItem(pod, 1)) return ["You don't have any of those pods!"];
      const msgs = [`You launched a ${D.items[pod].name}!`];
      const chance = this.captureChance(pod);
      let shakes = 0;
      for (let i = 0; i < 3; i++) if (Math.random() < Math.cbrt(chance)) shakes++;
      this.lastShakes = shakes;
      if (shakes === 3) { this.result = 'captured'; msgs.push(`Containment successful! ${this.enemy.name} was captured.`); return msgs; }
      msgs.push(['It broke free immediately!', 'Almost had it...', 'So close! It broke free!'][shakes]);
      return msgs;
    }
    _useItem(itemId, idx) {
      const t = this.team[idx], it = D.items[itemId];
      if (it.kind === 'heal' && t.fainted) return ["You can't heal a fainted creature - use a Revive Serum."];
      if (it.kind === 'revive' && !t.fainted) return [`${t.name} hasn't fainted.`];
      if (this.inventory && !this.inventory.removeItem(itemId, 1)) return ["You don't have that item."];
      if (it.kind === 'heal') { const b = t.hp; t.hp = Math.min(t.maxHp, t.hp + it.value); return [`${t.name} recovered ${t.hp - b} HP.`]; }
      t.hp = Math.floor(t.maxHp / 2);
      return [`${t.name} was revived!`];
    }
  }

  Object.assign(EX, { D, Creature, PlanetMap, Battle, rollWild, alphaCreature, xpForLevel, T, MAP_W, MAP_H,
    RARITY_ORDER, RARITY_RP });
})(window.EX = window.EX || {});
