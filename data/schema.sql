-- spacegame/data/schema.sql
-- Text-based space game prototype with hierarchical solar coordinates.

PRAGMA foreign_keys = ON;

-- Galaxy: star systems at integer parsec (pc) coordinates
CREATE TABLE IF NOT EXISTS systems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    x           INTEGER NOT NULL,         -- galaxy coords (pc), whole numbers
    y           INTEGER NOT NULL
);

-- Items traded in markets
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    base_price  INTEGER NOT NULL
);

-- Player-controllable ships
CREATE TABLE IF NOT EXISTS ships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    cargo       INTEGER NOT NULL,
    fuel_max    INTEGER NOT NULL
);

-- Market snapshot per system for each item
CREATE TABLE IF NOT EXISTS markets (
    system_id   INTEGER NOT NULL,
    item_id     INTEGER NOT NULL,
    price       INTEGER NOT NULL,
    stock       INTEGER NOT NULL,
    PRIMARY KEY (system_id, item_id),
    FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- Locations inside a system (for solar map), using HIERARCHICAL LOCAL AU COORDS
-- (x,y) are LOCAL offsets in AU relative to the parent:
--  - If parent_location_id IS NULL: offsets are relative to the SYSTEM CENTER (0,0).
--  - If parent_location_id references another location (e.g., a planet),
--    offsets are relative to that parent (e.g., stations around a planet).
CREATE TABLE IF NOT EXISTS locations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id           INTEGER NOT NULL,
    name                TEXT NOT NULL,
    kind                TEXT NOT NULL,        -- 'planet', 'station', etc.
    x                   REAL NOT NULL,        -- local AU offset (relative to parent or system)
    y                   REAL NOT NULL,        -- local AU offset
    parent_location_id  INTEGER NULL,         -- NULL => parent is system center
    UNIQUE(system_id, name),
    FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_location_id) REFERENCES locations(id) ON DELETE CASCADE
);

-- Player single-row table
CREATE TABLE IF NOT EXISTS player (
    id                      INTEGER PRIMARY KEY CHECK (id = 1),
    name                    TEXT NOT NULL,
    credits                 INTEGER NOT NULL,
    system_id               INTEGER NOT NULL,
    ship_id                 INTEGER NOT NULL,
    fuel                    INTEGER NOT NULL,
    current_location_id     INTEGER NULL,
    FOREIGN KEY (system_id) REFERENCES systems(id),
    FOREIGN KEY (ship_id) REFERENCES ships(id),
    FOREIGN KEY (current_location_id) REFERENCES locations(id)
);

-- Player inventory
CREATE TABLE IF NOT EXISTS inventory (
    item_id     INTEGER PRIMARY KEY,
    qty         INTEGER NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Price history for future economy ticks
CREATE TABLE IF NOT EXISTS prices_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,            -- ISO timestamp
    system_id   INTEGER NOT NULL,
    item_id     INTEGER NOT NULL,
    price       INTEGER NOT NULL,
    FOREIGN KEY (system_id) REFERENCES systems(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_markets_system ON markets(system_id);
CREATE INDEX IF NOT EXISTS idx_markets_item ON markets(item_id);
CREATE INDEX IF NOT EXISTS idx_locations_system ON locations(system_id);
CREATE INDEX IF NOT EXISTS idx_locations_parent ON locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_prices_hist_ts ON prices_history(ts);
