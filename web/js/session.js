/* Game session: player state + rules (JS port of exodex/session.py).
   State is held in plain objects shaped exactly like the SQLite tables, so
   store.js can write it straight into a real SQLite database (sql.js). */
(function (EX) {
  'use strict';
  const { D, Creature, PlanetMap, Battle, rollWild, alphaCreature, R, RARITY_ORDER, RARITY_RP } = EX;
  const ENCOUNTER_RATE = 0.12, SEQUENCE_COST = 3, ACCEL_COST = 6, SYNTH_COST = 10;
  const now = () => new Date().toISOString().slice(0, 19) + '+00:00';

  function newState(name) {
    const ts = now();
    return {
      player: { id: 1, name, rp: 0, current_planet: null, pos_x: 0, pos_y: 0, steps: 0, lure_steps: 0,
        battles_won: 0, alphas_beaten: '', playtime_s: 0, created_at: ts, saved_at: ts },
      creatures: [], inventory: { pod: 5, medgel: 3, fuel: 3, iron: 4 }, discoveries: {},
      missions: Object.fromEntries(D.missions.map((m) => [m.id, { progress: 0, claimed: 0 }])),
      research: Object.fromEntries(Object.keys(D.research).map((k) => [k, 0])),
      stats: {}, battle_history: [], nextId: 1,
    };
  }

  class Session {
    constructor(state) {
      this.st = state;
      this.creatures = state.creatures.map((r) => Creature.fromRow(r));
      this.map = null;
      const p = state.player;
      if (p.current_planet) this._enterMap(p.current_planet, [p.pos_x, p.pos_y]);
    }
    static newGame(name, starterId) {
      const s = new Session(newState(name));
      const c = Creature.generate(D.species[starterId], 6, 'Hardy', 8, 15);
      s._addCreature(c, null);
      s.mark(starterId, null, { seen: 1, scanned: 1, captured: 1, dna: 1 });
      return s;
    }
    // serialisable snapshot (table rows)
    snapshot() {
      this.st.creatures = this.creatures.map((c) => c.toRow());
      this.st.player.saved_at = now();
      return this.st;
    }

    // --------------------------------------------------------- queries
    get player() { return this.st.player; }
    get planet() { return this.player.current_planet ? D.planets[this.player.current_planet] : null; }
    qty(id) { return this.st.inventory[id] || 0; }
    addItem(id, n = 1) { this.st.inventory[id] = this.qty(id) + n; }
    removeItem(id, n = 1) { if (this.qty(id) < n) return false; this.st.inventory[id] -= n; return true; }
    stat(k) { return this.st.stats[k] || 0; }
    bump(k, n = 1) { this.st.stats[k] = this.stat(k) + n; }
    research(k) { return this.st.research[k] || 0; }
    team() { return this.creatures.filter((c) => c.team_slot !== null).sort((a, b) => a.team_slot - b.team_slot); }
    storage() { return this.creatures.filter((c) => c.team_slot === null).sort((a, b) => b.level - a.level); }
    allCreatures() { return this.team().concat(this.storage()); }
    discovery(sid) { return this.st.discoveries[sid]; }
    dexCounts() {
      const v = Object.values(this.st.discoveries);
      return { seen: v.filter((d) => d.seen).length, scanned: v.filter((d) => d.scanned).length,
        captured: v.filter((d) => d.captured).length };
    }
    rank() { return this.dexCounts().scanned; }
    unlocked(p) { return this.rank() >= p.unlock_rank; }
    scannedWhere(fn) {
      return Object.entries(this.st.discoveries).filter(([sid, d]) => d.scanned && fn(D.species[sid], d)).length;
    }

    mark(sid, planetId, f) {
      let d = this.st.discoveries[sid];
      if (!d) d = this.st.discoveries[sid] = { seen: 0, scanned: 0, captured: 0, dna: 0, planet_id: planetId, first_seen: now() };
      const isNew = { seen: !!f.seen && !d.seen, scanned: !!f.scanned && !d.scanned, captured: !!f.captured && !d.captured };
      if (f.seen || f.scanned || f.captured) d.seen = 1;
      if (f.scanned || f.captured) d.scanned = 1;
      if (f.captured) d.captured = 1;
      d.dna += f.dna || 0;
      return isNew;
    }
    spendDna(sid, n) { const d = this.discovery(sid); if (!d || d.dna < n) return false; d.dna -= n; return true; }

    _addCreature(c, planetId) {
      const team = this.team();
      c.id = this.st.nextId++;
      c.team_slot = team.length < 6 ? team.length : null;
      c.planet_id = planetId;
      c.caught_at = now();
      this.creatures.push(c);
    }
    setTeam(ids) {
      this.creatures.forEach((c) => (c.team_slot = null));
      ids.slice(0, 6).forEach((id, i) => (this.creatures.find((c) => c.id === id).team_slot = i));
    }

    // --------------------------------------------------------- travel
    travel(pid) {
      const p = D.planets[pid];
      if (!this.unlocked(p)) return [false, `Requires Explorer Rank ${p.unlock_rank} (scan more species).`];
      if (this.team().every((c) => c.fainted)) return [false, 'Your team needs healing before a mission.'];
      if (pid === 1) { this._enterMap(pid, null); return [true, `Shuttle landed on ${p.name}.`]; }
      const free = Math.random() < 0.3 * this.research('propulsion');
      if (!free && !this.removeItem('fuel', 1)) return [false, 'No Fuel Cells! Craft some at the Fabricator.'];
      this._enterMap(pid, null);
      return [true, `Landed on ${p.name}.` + (free ? ' Ion drive saved a Fuel Cell!' : '')];
    }
    _enterMap(pid, pos) {
      this.map = new PlanetMap(D.planets[pid]);
      const [x, y] = pos && this.map.walkable(pos[0], pos[1]) ? pos : this.map.pad;
      Object.assign(this.player, { current_planet: pid, pos_x: x, pos_y: y });
    }
    returnToLab() { this.map = null; this.player.current_planet = null; this.healTeam(); }
    healTeam() { this.creatures.forEach((c) => c.healFull()); }

    step(dx, dy) {
      if (!this.map) return null;
      const p = this.player, nx = p.pos_x + dx, ny = p.pos_y + dy;
      if (!this.map.walkable(nx, ny)) return null;
      const lure = Math.max(0, p.lure_steps - 1);
      Object.assign(p, { pos_x: nx, pos_y: ny, steps: p.steps + 1, lure_steps: lure });
      const t = this.map.tile(nx, ny);
      if (t === EX.T.NEST && !p.alphas_beaten.split(',').includes(String(this.planet.id))) return ['alpha', alphaCreature(this.planet)];
      if (t === EX.T.BIOZONE && Math.random() < ENCOUNTER_RATE * (lure ? 2 : 1)) return ['encounter', rollWild(this.planet, !!lure)];
      return null;
    }
    gather() {
      if (!this.map) return null;
      const p = this.player;
      for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const x = p.pos_x + dx, y = p.pos_y + dy;
        if (this.map.tile(x, y) === EX.T.NODE && this.map.harvest(x, y)) {
          const mat = this.planet.material;
          const n = R.randint(1, 2) + this.research('logistics');
          this.addItem(mat, n);
          const got = [`${n}x ${D.items[mat].name}`];
          if (Math.random() < 0.6) { const k = R.randint(1, 2); this.addItem('iron', k); got.push(`${k}x Iron Ingot`); }
          if (Math.random() < 0.15) {
            const o = R.choice(Object.values(D.planets)).material; this.addItem(o, 1); got.push(`1x ${D.items[o].name}`);
          }
          this.bump('gather');
          this.refreshMissions();
          return 'Gathered ' + got.join(', ') + '.';
        }
      }
      return null;
    }
    useLure() { if (this.removeItem('lure', 1)) { this.player.lure_steps = 60; return true; } return false; }

    // --------------------------------------------------------- battles
    startBattle(enemy, alpha) {
      this.mark(enemy.species.id, this.planet ? this.planet.id : null, { seen: 1 });
      return new Battle(this.team(), enemy, { alpha, inventory: this, scannerLevel: this.research('scanner'),
        containmentLevel: this.research('containment') });
    }
    finishBattle(b) {
      const msgs = [];
      const pid = this.planet ? this.planet.id : null;
      const e = b.enemy;
      if (b.scanned || b.result === 'captured') {
        const n = this.mark(e.species.id, pid, { scanned: 1, dna: b.scanned ? 1 + this.research('scanner') : 0 });
        if (n.scanned) {
          const rp = RARITY_RP[e.species.rarity];
          this.player.rp += rp; this.bump('scan');
          msgs.push(`New ExoDex entry: ${e.species.name}! +${rp} RP`);
        }
      }
      if (b.result === 'captured') {
        e.resetBattle();
        const n = this.mark(e.species.id, pid, { captured: 1, dna: 1 });
        this._addCreature(e, pid);
        this.bump('capture');
        if (RARITY_ORDER.indexOf(e.species.rarity) >= 2) this.bump('capture_rare');
        if (n.captured) this.player.rp += 5;
        msgs.push(`${e.name} was sent to ${e.team_slot !== null ? 'your team' : 'lab storage'}.`);
      }
      if (b.result === 'win') { this.bump('win'); this.player.rp += 2; this.player.battles_won++; }
      if (b.alpha && (b.result === 'win' || b.result === 'captured')) {
        const beaten = this.player.alphas_beaten.split(',').filter(Boolean);
        beaten.push(String(pid));
        this.player.alphas_beaten = beaten.join(',');
        this.bump('alpha'); this.player.rp += 30;
        msgs.push('Alpha subdued! +30 RP');
      }
      this.st.battle_history.push({ id: this.st.battle_history.length + 1, planet_id: pid, enemy_species: e.species.id,
        enemy_level: e.level, result: b.result || 'fled', turns: b.turns, at: now() });
      const medbay = this.research('medbay');
      for (const c of b.team) {
        c.resetBattle();
        if (medbay && !c.fainted) c.hp = Math.min(c.maxHp, c.hp + Math.floor(c.maxHp * 0.15 * medbay));
        if (c.canEvolve()) {
          msgs.push(c.evolve());
          this.mark(c.species.id, pid, { captured: 1 });
          this.bump('evolve');
        }
      }
      if (b.result === 'loss' || b.team.every((c) => c.fainted)) { this.returnToLab(); msgs.push('You were airlifted back to the Orbital Lab. Team restored.'); }
      return msgs.concat(this.refreshMissions());
    }

    // --------------------------------------------------------- lab systems
    canCraft(r) { return Object.entries(r.inputs).every(([k, v]) => this.qty(k) >= v); }
    craft(rid) {
      const r = D.recipes.find((x) => x.id === rid);
      if (!this.canCraft(r)) return [false, 'Missing materials.'];
      Object.entries(r.inputs).forEach(([k, v]) => this.removeItem(k, v));
      this.addItem(r.output, r.qty); this.bump('craft'); this.refreshMissions();
      return [true, `Fabricated ${r.qty}x ${D.items[r.output].name}.`];
    }
    researchCost(k) { return D.research[k].cost * (this.research(k) + 1); }
    upgradeResearch(k) {
      const r = D.research[k], lvl = this.research(k);
      if (lvl >= r.max_level) return [false, 'Already at max level.'];
      const cost = this.researchCost(k);
      if (this.player.rp < cost) return [false, `Need ${cost} RP.`];
      this.player.rp -= cost; this.st.research[k] = lvl + 1;
      return [true, `${r.name} upgraded to level ${lvl + 1}!`];
    }
    sequenceCost() { return Math.max(1, Math.round(SEQUENCE_COST * (1 - 0.25 * this.research('genetics')))); }
    byId(id) { return this.creatures.find((c) => c.id === id); }
    sequenceGenome(id) {
      const c = this.byId(id);
      if (c.ivTotal >= 60) return [false, 'Genome already perfect.'];
      if (!this.spendDna(c.species.id, this.sequenceCost())) return [false, `Need ${this.sequenceCost()} ${c.species.name} DNA.`];
      const gains = [];
      for (const k of Object.keys(c.ivs)) {
        const nv = Math.min(15, c.ivs[k] + R.randint(1, 4));
        if (nv > c.ivs[k]) gains.push(`${k.toUpperCase()}+${nv - c.ivs[k]}`);
        c.ivs[k] = nv;
      }
      c.hp = Math.min(c.hp, c.maxHp);
      this.bump('sequence'); this.refreshMissions();
      return [true, 'Genome sequenced: ' + (gains.join(', ') || 'no change')];
    }
    accelerateEvolution(id) {
      const c = this.byId(id), s = c.species;
      if (!s.evolves_to) return [false, `${s.name} has no further evolution.`];
      if (c.level < s.evolve_level - 5) return [false, `Must be at least level ${s.evolve_level - 5}.`];
      if (!this.spendDna(s.id, ACCEL_COST)) return [false, `Need ${ACCEL_COST} ${s.name} DNA.`];
      const msg = c.evolve();
      this.mark(c.species.id, null, { captured: 1 }); this.bump('evolve'); this.refreshMissions();
      return [true, msg];
    }
    synthesize(sid) {
      const sp = D.species[sid];
      if (sp.rarity === 'legendary') return [false, 'Legendary genomes are too complex to synthesize.'];
      if (!this.spendDna(sid, SYNTH_COST)) return [false, `Need ${SYNTH_COST} ${sp.name} DNA.`];
      const c = Creature.generate(sp, Math.max(5, D.minWildLevel(sp)), null, 4, 15);
      this._addCreature(c, null);
      if (this.mark(sid, null, { captured: 1 }).captured) this.player.rp += 5;
      this.bump('capture'); this.refreshMissions();
      return [true, `Synthesized a ${sp.name} from DNA!`];
    }
    useItemOn(itemId, id) {
      const c = this.byId(id), it = D.items[itemId];
      if (it.kind === 'heal' && !c.fainted && c.hp < c.maxHp && this.removeItem(itemId)) c.hp = Math.min(c.maxHp, c.hp + it.value);
      else if (it.kind === 'revive' && c.fainted && this.removeItem(itemId)) c.hp = Math.floor(c.maxHp / 2);
      else return [false, "That won't have any effect."];
      return [true, `Used ${it.name} on ${c.name}.`];
    }
    swapTeam(id) {
      const team = this.team().map((c) => c.id);
      if (team.includes(id)) {
        if (team.length === 1) return [false, 'You need at least one creature in your team.'];
        team.splice(team.indexOf(id), 1);
      } else {
        if (team.length >= 6) return [false, 'Team is full (6). Move one to storage first.'];
        team.push(id);
      }
      this.setTeam(team);
      return [true, 'Team updated.'];
    }
    setLead(id) {
      const team = this.team().map((c) => c.id);
      if (!team.includes(id)) return;
      team.splice(team.indexOf(id), 1); team.unshift(id); this.setTeam(team);
    }
    rename(id, name) { const c = this.byId(id); c.nickname = (name || '').trim().slice(0, 16) || null; }

    // --------------------------------------------------------- missions
    missionValue(m) {
      switch (m.kind) {
        case 'scan': return this.rank();
        case 'scan_planet': return this.scannedWhere((s, d) => String(d.planet_id) === m.target);
        case 'scan_type': return this.scannedWhere((s) => s.type1 === m.target || s.type2 === m.target);
        case 'capture_rarity': return this.stat('capture_rare');
        default: return this.stat(m.kind);
      }
    }
    refreshMissions() {
      const msgs = [];
      for (const m of D.missions) {
        const st = this.st.missions[m.id];
        const val = Math.min(m.goal, this.missionValue(m));
        if (val !== st.progress) {
          st.progress = val;
          if (val >= m.goal && !st.claimed) msgs.push(`Mission complete: ${m.title}! Claim it at the Lab.`);
        }
      }
      return msgs;
    }
    claimMission(id) {
      const m = D.missions.find((x) => x.id === id), st = this.st.missions[id];
      if (st.claimed || st.progress < m.goal) return [false, 'Not ready.'];
      st.claimed = 1; this.player.rp += m.reward_rp; this.addItem(m.reward_item, m.reward_qty);
      return [true, `+${m.reward_rp} RP, ${m.reward_qty}x ${D.items[m.reward_item].name}`];
    }
  }

  Object.assign(EX, { Session, newState, SYNTH_COST, ACCEL_COST });
})(window.EX = window.EX || {});
