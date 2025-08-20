"""
Save-state schema for <slot>/save.db.
No asset definitions here (those live in <slot>/Database/*.db).
"""
from __future__ import annotations
import os, sqlite3

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS player(
    id INTEGER PRIMARY KEY CHECK (id=1),
    name TEXT NOT NULL,
    credits INTEGER NOT NULL,
    ship_id INTEGER NOT NULL,
    location_type TEXT NOT NULL,
    location_id INTEGER NOT NULL,
    hp INTEGER NOT NULL,
    energy INTEGER NOT NULL,
    fuel INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS hangar_ships(
    ship_id INTEGER PRIMARY KEY,
    acquired_price INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_cargo(
    item_id INTEGER PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quest_instances(
  quest_id INTEGER PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('offered','accepted','completed','failed','rejected','abandoned','hidden')),
  progress INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_events(
  event TEXT PRIMARY KEY,
  meta TEXT
);

CREATE TABLE IF NOT EXISTS events_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  category TEXT DEFAULT 'system',
  message TEXT
);

CREATE TABLE IF NOT EXISTS station_economy(
  station_id INTEGER PRIMARY KEY,
  fuel_index REAL NOT NULL DEFAULT 1.0,
  repair_index REAL NOT NULL DEFAULT 1.0,
  energy_index REAL NOT NULL DEFAULT 1.0
);
"""

def initialize(db_path: str) -> None:
    must_create = not os.path.exists(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA)
    finally:
        conn.close()