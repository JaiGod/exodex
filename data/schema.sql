-- ExoDex SQLite schema (shared by the Python/Pygame game and the browser build).
-- A save file IS one of these databases: static catalogue tables + player state.

PRAGMA foreign_keys = ON;

-- ---------- static catalogue ----------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS species (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE,
    type1        TEXT    NOT NULL,
    type2        TEXT,
    kingdom      TEXT    NOT NULL,
    rarity       TEXT    NOT NULL CHECK (rarity IN ('common','uncommon','rare','epic','legendary')),
    hp           INTEGER NOT NULL,
    atk          INTEGER NOT NULL,
    defense      INTEGER NOT NULL,
    spd          INTEGER NOT NULL,
    evolves_to   INTEGER REFERENCES species(id),
    evolve_level INTEGER,
    family       INTEGER NOT NULL,
    stage        INTEGER NOT NULL,
    biomes       TEXT    NOT NULL,           -- comma separated biome keys
    hue          INTEGER NOT NULL,
    sprite_seed  INTEGER NOT NULL,
    height_m     REAL    NOT NULL,
    mass_kg      REAL    NOT NULL,
    description  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS moves (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    type        TEXT    NOT NULL,
    power       INTEGER NOT NULL,
    accuracy    INTEGER NOT NULL,
    effect      TEXT,
    description TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS species_moves (
    species_id INTEGER NOT NULL REFERENCES species(id),
    level      INTEGER NOT NULL,
    move_id    INTEGER NOT NULL REFERENCES moves(id),
    PRIMARY KEY (species_id, level, move_id)
);

CREATE TABLE IF NOT EXISTS planets (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    biome         TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    min_level     INTEGER NOT NULL,
    max_level     INTEGER NOT NULL,
    unlock_rank   INTEGER NOT NULL,
    seed          INTEGER NOT NULL,
    material      TEXT    NOT NULL,
    alpha_species INTEGER NOT NULL REFERENCES species(id),
    alpha_level   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    description TEXT NOT NULL,
    value       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS recipes (
    id      INTEGER PRIMARY KEY,
    output  TEXT    NOT NULL REFERENCES items(id),
    qty     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_inputs (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id),
    item_id   TEXT    NOT NULL REFERENCES items(id),
    qty       INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, item_id)
);

CREATE TABLE IF NOT EXISTS research (
    id          TEXT PRIMARY KEY,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL,
    cost        INTEGER NOT NULL,
    max_level   INTEGER NOT NULL,
    level       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    target      TEXT    NOT NULL,
    goal        INTEGER NOT NULL,
    reward_rp   INTEGER NOT NULL,
    reward_item TEXT REFERENCES items(id),
    reward_qty  INTEGER NOT NULL,
    progress    INTEGER NOT NULL DEFAULT 0,
    claimed     INTEGER NOT NULL DEFAULT 0
);

-- ---------- player state ----------
CREATE TABLE IF NOT EXISTS player (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    name           TEXT    NOT NULL,
    rp             INTEGER NOT NULL DEFAULT 0,      -- research points
    current_planet INTEGER REFERENCES planets(id),
    pos_x          INTEGER NOT NULL DEFAULT 0,
    pos_y          INTEGER NOT NULL DEFAULT 0,
    steps          INTEGER NOT NULL DEFAULT 0,
    lure_steps     INTEGER NOT NULL DEFAULT 0,
    battles_won    INTEGER NOT NULL DEFAULT 0,
    alphas_beaten  TEXT    NOT NULL DEFAULT '',     -- comma separated planet ids
    playtime_s     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL,
    saved_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS creatures (                -- captured individual specimens
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id  INTEGER NOT NULL REFERENCES species(id),
    nickname    TEXT,
    level       INTEGER NOT NULL,
    xp          INTEGER NOT NULL DEFAULT 0,
    hp_current  INTEGER NOT NULL,
    trait       TEXT    NOT NULL,
    iv_hp       INTEGER NOT NULL,
    iv_atk      INTEGER NOT NULL,
    iv_def      INTEGER NOT NULL,
    iv_spd      INTEGER NOT NULL,
    aberrant    INTEGER NOT NULL DEFAULT 0,          -- rare colour mutation
    team_slot   INTEGER,                             -- 0..5 when in the active team, NULL in storage
    moves       TEXT    NOT NULL,                    -- comma separated move ids (max 4)
    planet_id   INTEGER REFERENCES planets(id),
    caught_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    item_id TEXT PRIMARY KEY REFERENCES items(id),
    qty     INTEGER NOT NULL CHECK (qty >= 0)
);

CREATE TABLE IF NOT EXISTS discoveries (
    species_id  INTEGER PRIMARY KEY REFERENCES species(id),
    seen        INTEGER NOT NULL DEFAULT 0,
    scanned     INTEGER NOT NULL DEFAULT 0,
    captured    INTEGER NOT NULL DEFAULT 0,
    dna         INTEGER NOT NULL DEFAULT 0,
    planet_id   INTEGER REFERENCES planets(id),
    first_seen  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS battle_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    planet_id     INTEGER REFERENCES planets(id),
    enemy_species INTEGER NOT NULL REFERENCES species(id),
    enemy_level   INTEGER NOT NULL,
    result        TEXT    NOT NULL CHECK (result IN ('win','loss','fled','captured')),
    turns         INTEGER NOT NULL,
    at            TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (                    -- counters that drive missions
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_creatures_team ON creatures(team_slot);
CREATE INDEX IF NOT EXISTS idx_species_family ON species(family);
CREATE INDEX IF NOT EXISTS idx_history_planet ON battle_history(planet_id);
