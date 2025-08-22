-- spacegame/data/schema.sql
-- Text-based space game prototype with hierarchical solar coordinates.

PRAGMA foreign_keys = ON;

-- Galaxy: star systems at integer parsec (pc) coordinates
CREATE TABLE IF NOT EXISTS systems (
    system_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name        TEXT NOT NULL UNIQUE,
    system_x           INTEGER NOT NULL,         -- galaxy coords (pc), whole numbers
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
    location_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id           INTEGER NOT NULL,
    location_name       TEXT NOT NULL,
    location_category   TEXT NOT NULL,        -- 'planet', 'station', etc.
    location_x          REAL NOT NULL,        -- local AU offset (relative to parent or system)
    location_y          REAL NOT NULL,        -- local AU offset
    parent_location_id  INTEGER NULL,         -- NULL => parent is system center
    location_description TEXT,
    icon_path           TEXT,
    UNIQUE(system_id, location_name),
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
    current_location_id         INTEGER NULL,
    FOREIGN KEY (current_player_system_id) REFERENCES systems(system_id),
    FOREIGN KEY (current_player_ship_id) REFERENCES ships(ship_id),
    FOREIGN KEY (current_location_id) REFERENCES locations(location_id)
);

-- Player inventory
CREATE TABLE IF NOT EXISTS cargohold (
    item_id     INTEGER PRIMARY KEY,
    item_qty    INTEGER NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

-- Price history for future economy ticks
CREATE TABLE IF NOT EXISTS prices_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,            -- ISO timestamp
    system_id   INTEGER NOT NULL,
    item_id     INTEGER NOT NULL,
    price       INTEGER NOT NULL,
    FOREIGN KEY (system_id) REFERENCES systems(system_id),
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(system_name);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(item_name);
CREATE INDEX IF NOT EXISTS idx_markets_system ON markets(system_id);
CREATE INDEX IF NOT EXISTS idx_markets_item ON markets(item_id);
CREATE INDEX IF NOT EXISTS idx_locations_system ON locations(system_id);
CREATE INDEX IF NOT EXISTS idx_locations_parent ON locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_prices_hist_ts ON prices_history(ts);