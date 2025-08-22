"""
data/db.py
SQLite access layer + schema/seed + first-run icon assignment.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "game.db"

_active_db_path_override: Optional[Path] = None

def set_active_db_path(p: Path | str) -> None:
    global _active_db_path_override
    _active_db_path_override = Path(p)

def get_active_db_path() -> Path:
    return _active_db_path_override if _active_db_path_override else DB_PATH

ASSETS = ROOT / "assets"
PLANETS_DIR = ASSETS / "planets"
STATIONS_DIR = ASSETS / "stations"
STARS_DIR = ASSETS / "stars"

DATA_DIR = ROOT / "data"
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED_PY = DATA_DIR / "seed.py"

_connection: Optional[sqlite3.Connection] = None

def _is_connection_open(conn: Optional[sqlite3.Connection]) -> bool:
    if conn is None: return False
    try:
        conn.execute("SELECT 1;")
        return True
    except sqlite3.ProgrammingError:
        return False

def _open_new_connection() -> sqlite3.Connection:
    ap = get_active_db_path()
    ap.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ap))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None or not _is_connection_open(_connection):
        _connection = _open_new_connection()
        _ensure_schema_and_seed(_connection)
        _ensure_icon_column(_connection)
        _ensure_system_star_column(_connection)
        _assign_location_icons_if_missing(_connection)
        _assign_system_star_icons_if_missing(_connection)
    return _connection

def _ensure_schema_and_seed(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) FROM systems")
    if cur.fetchone()[0] == 0:
        import runpy
        ns = runpy.run_path(str(SEED_PY), run_name="__seed__")
        seed_fn = ns.get("seed")
        if callable(seed_fn):
            seed_fn(conn)
            conn.commit()

def _table_has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def _ensure_icon_column(conn: sqlite3.Connection) -> None:
    if not _table_has_column(conn, "locations", "icon_path"):
        conn.execute("ALTER TABLE locations ADD COLUMN icon_path TEXT")
        conn.commit()

def _ensure_system_star_column(conn: sqlite3.Connection) -> None:
    if not _table_has_column(conn, "systems", "star_icon_path"):
        conn.execute("ALTER TABLE systems ADD COLUMN star_icon_path TEXT")
        conn.commit()

def _list_image_files(p: Path) -> List[Path]:
    if not p.exists(): return []
    exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return [q for q in p.iterdir() if q.suffix.lower() in exts]

def _assign_for_kind(conn: sqlite3.Connection, system_id: int, kind: str, candidates: List[Path]) -> None:
    cur = conn.execute(
        "SELECT location_id FROM locations WHERE system_id=? AND location_category=? AND icon_path IS NULL ORDER BY location_id",
        (system_id, kind),
    )
    rows_to_update = [r[0] for r in cur.fetchall()]
    if not rows_to_update or not candidates: return

    for i, loc_id in enumerate(rows_to_update):
        chosen = candidates[i % len(candidates)]
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE locations SET icon_path=? WHERE location_id=?", (rel, loc_id))

def _assign_location_icons_if_missing(conn: sqlite3.Connection) -> None:
    planet_files = _list_image_files(PLANETS_DIR)
    station_files = _list_image_files(STATIONS_DIR)
    if not planet_files and not station_files: return

    cur = conn.execute("SELECT system_id FROM systems ORDER BY system_id")
    systems = [r["system_id"] for r in cur.fetchall()]
    for sid in systems:
        if planet_files:
            _assign_for_kind(conn, sid, "planet", planet_files)
        if station_files:
            _assign_for_kind(conn, sid, "station", station_files)
    conn.commit()

def _assign_system_star_icons_if_missing(conn: sqlite3.Connection) -> None:
    star_imgs = _list_image_files(STARS_DIR)
    if not star_imgs: return
    cur = conn.execute("SELECT system_id FROM systems WHERE star_icon_path IS NULL ORDER BY system_id")
    rows = [r[0] for r in cur.fetchall()]
    for sid in rows:
        chosen = random.choice(star_imgs)
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE systems SET star_icon_path=? WHERE system_id=?", (rel, sid))
    conn.commit()

def get_counts() -> Dict[str, int]:
    conn = get_connection()
    return {
        "systems": conn.execute("SELECT COUNT(*) FROM systems").fetchone()[0],
        "items": conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "ships": conn.execute("SELECT COUNT(*) FROM ships").fetchone()[0],
    }

def get_systems() -> List[Dict]:
    return [dict(row) for row in get_connection().execute("SELECT *, system_id as id, system_name as name, system_x as x, system_y as y FROM systems ORDER BY system_name")]

def get_system(system_id: int) -> Optional[Dict]:
    row = get_connection().execute("SELECT *, system_id as id, system_name as name, system_x as x, system_y as y FROM systems WHERE system_id=?", (system_id,)).fetchone()
    return dict(row) if row else None

def get_locations(system_id: int) -> List[Dict]:
    return [dict(row) for row in get_connection().execute(
        "SELECT *, location_id as id, location_name as name, location_category as kind, location_x as local_x_au, location_y as local_y_au FROM locations WHERE system_id=? ORDER BY location_name", (system_id,))]

def get_location(location_id: int) -> Optional[Dict]:
    row = get_connection().execute("SELECT *, location_id as id, location_name as name, location_x as local_x_au, location_y as local_y_au FROM locations WHERE location_id=?", (location_id,)).fetchone()
    return dict(row) if row else None

def set_player_system(system_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET current_player_system_id=?, current_location_id=NULL WHERE id=1", (system_id,))
    conn.commit()

def set_player_location(location_id: Optional[int]) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET current_location_id=? WHERE id=1", (location_id,))
    conn.commit()

def get_player_full() -> Optional[Dict]:
    row = get_connection().execute("SELECT * FROM player WHERE id=1").fetchone()
    return dict(row) if row else None

def get_player_ship() -> Optional[Dict]:
    player = get_player_full()
    if not player or not player.get("current_player_ship_id"): return None
    row = get_connection().execute("SELECT *, ship_id as id, ship_name as name FROM ships WHERE ship_id = ?", (player["current_player_ship_id"],)).fetchone()
    return dict(row) if row else None

def get_status_snapshot() -> Dict[str, Any]:
    player = get_player_full() or {}
    ship = get_player_ship() or {}
    system = get_system(player.get("current_player_system_id", 0)) if player.get("current_player_system_id") else None
    location = get_location(player.get("current_location_id", 0)) if player.get("current_location_id") else None

    fuel_frac = player.get("current_player_ship_fuel", 0) / ship.get("base_ship_fuel", 1) if ship.get("base_ship_fuel") else 0
    
    return {
        "player_name": player.get("name", "—"),
        "credits": player.get("current_wallet_credits", 0),
        "system_name": system.get("system_name", "—") if system else "—",
        "location_name": location.get("location_name", "—") if location else "—",
        "ship_name": ship.get("ship_name", "—"),
        "ship_state": "Docked" if player.get("current_location_id") else "Traveling",
        "hull": player.get("current_player_ship_hull", 0),
        "hull_max": ship.get("base_ship_hull", 1),
        "shield": player.get("current_player_ship_shield", 0),
        "shield_max": ship.get("base_ship_shield", 1),
        "fuel": player.get("current_player_ship_fuel", 0),
        "fuel_max": ship.get("base_ship_fuel", 1),
        "energy": player.get("current_player_ship_energy", 0),
        "energy_max": ship.get("base_ship_energy", 1),
        "cargo": player.get("current_player_ship_cargo", 0),
        "cargo_max": ship.get("base_ship_cargo", 1),
        "base_jump_distance": ship.get("base_ship_jump_distance", 0.0),
        "current_jump_distance": ship.get("base_ship_jump_distance", 0.0) * fuel_frac
    }

def get_distance(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def can_reach(distance):
    status = get_status_snapshot()
    return status["current_jump_distance"] >= distance