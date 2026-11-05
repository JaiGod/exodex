/* Persistence. When sql.js (SQLite compiled to WebAssembly) is available, every
   save is a real SQLite database using data/schema.sql - the same file format as
   the Python version, so .db saves can be moved between desktop and browser.
   If sql.js can't load (offline), saves fall back to JSON with the same shape. */
(function (EX) {
  'use strict';
  const D = EX.D;
  const KEY = (slot) => `exodex.slot${slot}`;
  const META = (slot) => `exodex.meta${slot}`;
  const ls = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };

  // ------------------------------------------------------------ SQL builders
  function catalogueStatements() {
    const out = [];
    out.push(['INSERT INTO meta VALUES (?, ?)', ['schema_version', '1']]);
    out.push(['INSERT INTO meta VALUES (?, ?)', ['game', 'ExoDex']]);
    for (const m of D.raw.moves) out.push(['INSERT INTO moves VALUES (?,?,?,?,?,?,?)', [m.id, m.name, m.type, m.power, m.accuracy, m.effect, m.description]]);
    for (const s of D.speciesList) {
      out.push(['INSERT INTO species VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', [s.id, s.name, s.type1, s.type2,
        s.kingdom, s.rarity, s.hp, s.atk, s.defense, s.spd, null, s.evolve_level, s.family, s.stage, s.biomes.join(','),
        s.hue, s.sprite_seed, s.height_m, s.mass_kg, s.description]]);
    }
    for (const s of D.speciesList) if (s.evolves_to) out.push(['UPDATE species SET evolves_to=? WHERE id=?', [s.evolves_to, s.id]]);
    for (const s of D.speciesList) for (const [lv, mid] of s.learnset) out.push(['INSERT OR IGNORE INTO species_moves VALUES (?,?,?)', [s.id, lv, mid]]);
    for (const p of D.raw.planets) out.push(['INSERT INTO planets VALUES (?,?,?,?,?,?,?,?,?,?,?)', [p.id, p.name, p.biome, p.description,
      p.min_level, p.max_level, p.unlock_rank, p.seed, p.material, p.alpha_species, p.alpha_level]]);
    for (const i of D.raw.items) out.push(['INSERT INTO items VALUES (?,?,?,?,?)', [i.id, i.name, i.kind, i.description, i.value]]);
    for (const r of D.recipes) {
      out.push(['INSERT INTO recipes VALUES (?,?,?)', [r.id, r.output, r.qty]]);
      for (const [k, v] of Object.entries(r.inputs)) out.push(['INSERT INTO recipe_inputs VALUES (?,?,?)', [r.id, k, v]]);
    }
    return out;
  }

  /** Every table row for a game state, as [sql, params] pairs. */
  function stateStatements(st) {
    const out = [];
    for (const r of D.raw.research) out.push(['INSERT INTO research (id,name,description,cost,max_level,level) VALUES (?,?,?,?,?,?)',
      [r.id, r.name, r.description, r.cost, r.max_level, st.research[r.id] || 0]]);
    for (const m of D.missions) {
      const s = st.missions[m.id] || { progress: 0, claimed: 0 };
      out.push(['INSERT INTO missions (id,title,description,kind,target,goal,reward_rp,reward_item,reward_qty,progress,claimed) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        [m.id, m.title, m.description, m.kind, m.target, m.goal, m.reward_rp, m.reward_item, m.reward_qty, s.progress, s.claimed]]);
    }
    const p = st.player;
    out.push(['INSERT INTO player (id,name,rp,current_planet,pos_x,pos_y,steps,lure_steps,battles_won,alphas_beaten,playtime_s,created_at,saved_at) VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?)',
      [p.name, p.rp, p.current_planet, p.pos_x, p.pos_y, p.steps, p.lure_steps, p.battles_won, p.alphas_beaten, p.playtime_s, p.created_at, p.saved_at]]);
    for (const c of st.creatures) out.push(['INSERT INTO creatures (id,species_id,nickname,level,xp,hp_current,trait,iv_hp,iv_atk,iv_def,iv_spd,aberrant,team_slot,moves,planet_id,caught_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
      [c.id, c.species_id, c.nickname, c.level, c.xp, c.hp_current, c.trait, c.iv_hp, c.iv_atk, c.iv_def, c.iv_spd, c.aberrant, c.team_slot, c.moves, c.planet_id, c.caught_at]]);
    for (const [k, v] of Object.entries(st.inventory)) if (v > 0) out.push(['INSERT INTO inventory VALUES (?,?)', [k, v]]);
    for (const [sid, d] of Object.entries(st.discoveries)) out.push(['INSERT INTO discoveries VALUES (?,?,?,?,?,?,?)',
      [Number(sid), d.seen, d.scanned, d.captured, d.dna, d.planet_id, d.first_seen]]);
    for (const b of st.battle_history) out.push(['INSERT INTO battle_history VALUES (?,?,?,?,?,?,?)',
      [b.id, b.planet_id, b.enemy_species, b.enemy_level, b.result, b.turns, b.at]]);
    for (const [k, v] of Object.entries(st.stats)) out.push(['INSERT INTO stats VALUES (?,?)', [k, v]]);
    return out;
  }

  /** Rebuild a game state from a database. `q(sql)` returns an array of row objects. */
  function readState(q) {
    const p = q('SELECT * FROM player WHERE id=1')[0];
    if (!p) throw new Error('Not an ExoDex save (no player row).');
    const st = { player: p, creatures: q('SELECT * FROM creatures ORDER BY id'), inventory: {}, discoveries: {},
      missions: {}, research: {}, stats: {}, battle_history: q('SELECT * FROM battle_history ORDER BY id') };
    q('SELECT * FROM inventory').forEach((r) => (st.inventory[r.item_id] = r.qty));
    q('SELECT * FROM discoveries').forEach((r) => (st.discoveries[r.species_id] = { seen: r.seen, scanned: r.scanned,
      captured: r.captured, dna: r.dna, planet_id: r.planet_id, first_seen: r.first_seen }));
    q('SELECT id, progress, claimed FROM missions').forEach((r) => (st.missions[r.id] = { progress: r.progress, claimed: r.claimed }));
    D.missions.forEach((m) => { if (!st.missions[m.id]) st.missions[m.id] = { progress: 0, claimed: 0 }; });
    q('SELECT id, level FROM research').forEach((r) => (st.research[r.id] = r.level));
    q('SELECT * FROM stats').forEach((r) => (st.stats[r.key] = r.value));
    st.nextId = st.creatures.reduce((m, c) => Math.max(m, c.id), 0) + 1;
    return st;
  }

  // ------------------------------------------------------------ sql.js glue
  const Store = { SQL: null, lastDb: null, mode: 'json' };

  Store.init = async function () {
    if (typeof window.initSqlJs !== 'function') return false;
    try {
      const timeout = new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 8000));
      Store.SQL = await Promise.race([window.initSqlJs({ locateFile: (f) => EX.SQLJS_CDN + f }), timeout]);
      Store.mode = 'sqlite';
      return true;
    } catch (e) {
      console.warn('sql.js unavailable, using JSON saves', e);
      return false;
    }
  };

  function buildDb(st) {
    const db = new Store.SQL.Database();
    db.exec(window.EXODEX_SCHEMA);
    db.exec('BEGIN');
    for (const [sql, params] of catalogueStatements().concat(stateStatements(st))) db.run(sql, params);
    db.exec('COMMIT');
    return db;
  }
  function dbQuery(db) {
    return (sql) => {
      const res = db.exec(sql);
      if (!res.length) return [];
      const { columns, values } = res[0];
      return values.map((v) => Object.fromEntries(columns.map((c, i) => [c, v[i]])));
    };
  }
  const toB64 = (u8) => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); };
  const fromB64 = (b) => Uint8Array.from(atob(b), (c) => c.charCodeAt(0));

  Store.save = function (slot, session) {
    const st = session.snapshot();
    let payload;
    if (Store.SQL) {
      if (Store.lastDb) Store.lastDb.close();
      Store.lastDb = buildDb(st);
      payload = 'sqlite:' + toB64(Store.lastDb.export());
    } else {
      payload = 'json:' + JSON.stringify(st);
    }
    const c = session.dexCounts();
    ls.set(META(slot), JSON.stringify({ name: st.player.name, scanned: c.scanned, caught: session.creatures.length,
      rp: st.player.rp, play: st.player.playtime_s, saved: st.player.saved_at }));
    return ls.set(KEY(slot), payload);
  };

  function stateFromBytes(bytes) {
    if (!Store.SQL) throw new Error('SQLite engine not loaded (are you offline?)');
    const db = new Store.SQL.Database(bytes);
    try { return readState(dbQuery(db)); } finally { db.close(); }
  }

  Store.load = function (slot) {
    const raw = ls.get(KEY(slot));
    if (!raw) return null;
    let st;
    if (raw.startsWith('sqlite:')) st = stateFromBytes(fromB64(raw.slice(7)));
    else st = JSON.parse(raw.slice(5));
    return new EX.Session(st);
  };
  Store.meta = (slot) => { try { return JSON.parse(ls.get(META(slot)) || 'null'); } catch (e) { return null; } };
  Store.remove = (slot) => { ls.del(KEY(slot)); ls.del(META(slot)); };

  Store.exportFile = function (slot, session) {
    Store.save(slot, session);
    let blob, name;
    if (Store.SQL) { blob = new Blob([Store.lastDb.export()], { type: 'application/x-sqlite3' }); name = `exodex-slot${slot}.db`; }
    else { blob = new Blob([JSON.stringify(session.snapshot(), null, 1)], { type: 'application/json' }); name = `exodex-slot${slot}.json`; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    return name;
  };

  Store.importFile = async function (file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const head = String.fromCharCode.apply(null, bytes.subarray(0, 15));
    const st = head === 'SQLite format 3' ? stateFromBytes(bytes) : JSON.parse(new TextDecoder().decode(bytes));
    return new EX.Session(st);
  };

  /** Run a read-only query against the current save (SQL console in the Data Log). */
  Store.query = function (session, sql) {
    if (!Store.SQL) throw new Error('SQLite engine not loaded.');
    if (!/^\s*(select|with|pragma\s+table_info)/i.test(sql)) throw new Error('Only SELECT queries are allowed here.');
    if (Store.lastDb) Store.lastDb.close();
    Store.lastDb = buildDb(session.snapshot());
    const res = Store.lastDb.exec(sql);
    return res.length ? res[0] : { columns: [], values: [] };
  };

  Object.assign(EX, { Store, catalogueStatements, stateStatements, readState });
})(window.EX = window.EX || {});
