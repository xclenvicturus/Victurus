PRAGMA foreign_keys = ON;

-- Galaxy: star systems at integer parsec (pc) coordinates
CREATE TABLE IF NOT EXISTS systems (
    system_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name        TEXT NOT NULL UNIQUE,
    system_x           INTEGER NOT NULL,
    system_y           INTEGER NOT NULL,
    star_icon_path     TEXT
);

-- Items traded in markets
CREATE TABLE IF NOT EXISTS items (
    item_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name        TEXT NOT NULL UNIQUE,
    item_base_price  INTEGER NOT NULL,
    item_description TEXT,
    item_category    TEXT
);

-- Player-controllable ships
CREATE TABLE IF NOT EXISTS ships (
    ship_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ship_name               TEXT NOT NULL UNIQUE,
    base_ship_cargo         INTEGER NOT NULL,
    base_ship_fuel          INTEGER NOT NULL,
    base_ship_jump_distance REAL NOT NULL,
    base_ship_shield        INTEGER NOT NULL,
    base_ship_hull          INTEGER NOT NULL,
    base_ship_energy        INTEGER NOT NULL
);

-- Market snapshot per system for each item
CREATE TABLE IF NOT EXISTS markets (
    system_id           INTEGER NOT NULL,
    item_id             INTEGER NOT NULL,
    local_market_price  INTEGER NOT NULL,
    local_market_stock  INTEGER NOT NULL,
    PRIMARY KEY (system_id, item_id),
    FOREIGN KEY (system_id) REFERENCES systems(system_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- Locations inside a system (for solar map), using HIERARCHICAL LOCAL AU COORDS
CREATE TABLE IF NOT EXISTS locations (
    location_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id            INTEGER NOT NULL,
    location_name        TEXT NOT NULL,
    location_type        TEXT NOT NULL,      -- 'star','planet','moon','station','resource','warp_gate'
    location_x           REAL NOT NULL,      -- local AU offset (relative to parent or system)
    location_y           REAL NOT NULL,      -- local AU offset
    parent_location_id   INTEGER NULL,       -- NULL => parent is system center
    location_description TEXT,
    icon_path            TEXT,               -- assigned at runtime; no duplicates per system/type
    FOREIGN KEY (system_id) REFERENCES systems(system_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_location_id) REFERENCES locations(location_id) ON DELETE CASCADE
);

-- Player single-row table
CREATE TABLE IF NOT EXISTS player (
    id                          INTEGER PRIMARY KEY CHECK (id = 1),
    name                        TEXT NOT NULL,
    current_wallet_credits      INTEGER NOT NULL,
    current_player_system_id    INTEGER NOT NULL,
    current_player_ship_id      INTEGER NOT NULL,
    current_player_ship_fuel    INTEGER NOT NULL,
    current_player_ship_hull    INTEGER NOT NULL,
    current_player_ship_shield  INTEGER NOT NULL,
    current_player_ship_energy  INTEGER NOT NULL,
    current_player_ship_cargo   INTEGER NOT NULL,
    current_player_location_id  INTEGER NULL,
    FOREIGN KEY (current_player_system_id) REFERENCES systems(system_id),
    FOREIGN KEY (current_player_ship_id) REFERENCES ships(ship_id),
    FOREIGN KEY (current_player_location_id) REFERENCES locations(location_id)
);

-- Player inventory
CREATE TABLE IF NOT EXISTS cargohold (
    item_id     INTEGER PRIMARY KEY,
    item_qty    INTEGER NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

-- Price history for future economy ticks
CREATE TABLE IF NOT EXISTS prices_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,            -- ISO timestamp
    system_id INTEGER NOT NULL,
    item_id   INTEGER NOT NULL,
    price     INTEGER NOT NULL,
    FOREIGN KEY (system_id) REFERENCES systems(system_id),
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

-----------------------------------------------------------------
-- New v2 tables for universe seed
-----------------------------------------------------------------

-- Races / factions
CREATE TABLE IF NOT EXISTS races (
  race_id                 INTEGER PRIMARY KEY,
  name                    TEXT NOT NULL,   -- allow duplicate names; ids are authoritative
  adjective               TEXT,
  description             TEXT,
  tech_theme              TEXT,
  ship_doctrine           TEXT,
  government              TEXT,
  color                   TEXT,
  home_system_id          INTEGER,
  home_planet_location_id INTEGER,
  starting_world          INTEGER DEFAULT 1
);

-- System ownership (claimed/unclaimed)
CREATE TABLE IF NOT EXISTS ownerships (
  system_id INTEGER PRIMARY KEY,
  race_id   INTEGER NULL,
  status    TEXT NOT NULL DEFAULT 'unclaimed',
  FOREIGN KEY(system_id) REFERENCES systems(system_id) ON DELETE CASCADE,
  FOREIGN KEY(race_id)   REFERENCES races(race_id)
);

-- Diplomacy between races
CREATE TABLE IF NOT EXISTS diplomacy (
  race_a_id INTEGER NOT NULL,
  race_b_id INTEGER NOT NULL,
  stance    INTEGER NOT NULL,  -- -100..100
  status    TEXT NOT NULL,     -- 'war' | 'neutral' | 'allied'
  PRIMARY KEY (race_a_id, race_b_id),
  FOREIGN KEY(race_a_id) REFERENCES races(race_id),
  FOREIGN KEY(race_b_id) REFERENCES races(race_id)
);

-- Warp network edges
CREATE TABLE IF NOT EXISTS gate_links (
  system_a_id INTEGER NOT NULL,
  system_b_id INTEGER NOT NULL,
  distance_pc REAL NOT NULL,
  PRIMARY KEY (system_a_id, system_b_id),
  FOREIGN KEY(system_a_id) REFERENCES systems(system_id) ON DELETE CASCADE,
  FOREIGN KEY(system_b_id) REFERENCES systems(system_id) ON DELETE CASCADE
);

-- Resource node metadata (attached to a location with location_type='resource')
CREATE TABLE IF NOT EXISTS resource_nodes (
  location_id   INTEGER PRIMARY KEY,
  resource_type TEXT NOT NULL,        -- 'asteroid_field' | 'gas_cloud' | 'ice_field' | 'crystal_vein' | etc.
  richness      INTEGER NOT NULL,     -- total capacity / stock ceiling
  regen_rate    REAL NOT NULL,        -- stock per tick
  FOREIGN KEY(location_id) REFERENCES locations(location_id) ON DELETE CASCADE
);

-- Facilities placed at locations (planet/station/resource)
CREATE TABLE IF NOT EXISTS facilities (
  facility_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  location_id   INTEGER NOT NULL,
  facility_type TEXT NOT NULL,        -- 'Mine' | 'Refinery' | 'AgriDome' | etc.
  notes         TEXT,
  FOREIGN KEY(location_id) REFERENCES locations(location_id) ON DELETE CASCADE
);

-- Facility IO
CREATE TABLE IF NOT EXISTS facility_inputs (
  facility_id INTEGER NOT NULL,
  item_id     INTEGER NOT NULL,
  rate        REAL NOT NULL,
  PRIMARY KEY (facility_id, item_id),
  FOREIGN KEY(facility_id) REFERENCES facilities(facility_id) ON DELETE CASCADE,
  FOREIGN KEY(item_id)     REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS facility_outputs (
  facility_id INTEGER NOT NULL,
  item_id     INTEGER NOT NULL,
  rate        REAL NOT NULL,
  PRIMARY KEY (facility_id, item_id),
  FOREIGN KEY(facility_id) REFERENCES facilities(facility_id) ON DELETE CASCADE,
  FOREIGN KEY(item_id)     REFERENCES items(item_id) ON DELETE CASCADE
);

-- Ship roles for AI/consumption hooks
CREATE TABLE IF NOT EXISTS ship_roles (
  ship_id INTEGER NOT NULL,
  role    TEXT NOT NULL,
  PRIMARY KEY (ship_id, role),
  FOREIGN KEY(ship_id) REFERENCES ships(ship_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_systems_name       ON systems(system_name);
CREATE INDEX IF NOT EXISTS idx_items_name         ON items(item_name);
CREATE INDEX IF NOT EXISTS idx_markets_system     ON markets(system_id);
CREATE INDEX IF NOT EXISTS idx_markets_item       ON markets(item_id);
CREATE INDEX IF NOT EXISTS idx_locations_system   ON locations(system_id);
CREATE INDEX IF NOT EXISTS idx_locations_parent   ON locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_locations_sys_name ON locations(system_id, location_name);
CREATE INDEX IF NOT EXISTS idx_prices_hist_ts     ON prices_history(ts);
CREATE INDEX IF NOT EXISTS idx_gates_a            ON gate_links(system_a_id);
CREATE INDEX IF NOT EXISTS idx_gates_b            ON gate_links(system_b_id);
CREATE INDEX IF NOT EXISTS idx_races_name         ON races(name);
