# data/db.py
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
WARP_GATE_DIR = ASSETS / "warp_gate"

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

    cur = conn.execute("SELECT COUNT(system_id) FROM systems")
    if cur.fetchone()[0] == 0:
        import runpy
        ns = runpy.run_path(str(SEED_PY), run_name="__seed__")
        seed_fn = ns.get("seed")
        if callable(seed_fn):
            seed_fn(conn)
            conn.commit()

def close_active_connection() -> None:
    """Closes the current global database connection, if it's open."""
    global _connection
    if _connection is not None and _is_connection_open(_connection):
        _connection.close()
    _connection = None

def _ensure_icon_column(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(locations)")
    columns = [row[1] for row in cur.fetchall()]
    if "icon_path" not in columns:
        conn.execute("ALTER TABLE locations ADD COLUMN icon_path TEXT;")
        conn.commit()

def _ensure_system_star_column(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(systems)")
    columns = [row[1] for row in cur.fetchall()]
    if "star_icon_path" not in columns:
        conn.execute("ALTER TABLE systems ADD COLUMN star_icon_path TEXT;")
        conn.commit()

def _assign_location_icons_if_missing(conn: sqlite3.Connection) -> None:
    from ui.maps.icons import list_gifs  # Delay import to avoid circular deps
    cur = conn.execute("SELECT location_id, location_type, system_id FROM locations WHERE icon_path IS NULL")
    rows = cur.fetchall()
    if not rows:
        return
    updates = []
    for loc_id, kind, sys_id in rows:
        kind = (kind or "").lower()
        gifs: List[Path] = []
        if kind == "planet":
            gifs = list_gifs(PLANETS_DIR)
        elif kind == "station":
            gifs = list_gifs(STATIONS_DIR)
        elif kind == "warp_gate":
            gifs = list_gifs(WARP_GATE_DIR)
        if not gifs:
            continue
        idx = (int(loc_id) * 9176 + int(sys_id) * 37) % len(gifs)
        updates.append((str(gifs[idx]), loc_id))
    if updates:
        conn.executemany("UPDATE locations SET icon_path=? WHERE location_id=?", updates)
        conn.commit()

def _assign_system_star_icons_if_missing(conn: sqlite3.Connection) -> None:
    from ui.maps.icons import list_gifs  # Delay import to avoid circular deps
    cur = conn.execute("SELECT system_id FROM systems WHERE star_icon_path IS NULL")
    rows = cur.fetchall()
    if not rows:
        return
    gifs = list_gifs(STARS_DIR)
    if not gifs:
        return
    updates = []
    for (sys_id,) in rows:
        idx = (int(sys_id) * 9176 + 37) % len(gifs)
        updates.append((str(gifs[idx]), sys_id))
    if updates:
        conn.executemany("UPDATE systems SET star_icon_path=? WHERE system_id=?", updates)
        conn.commit()

def get_counts() -> Dict[str, int]:
    conn = get_connection()
    return {
        "systems": conn.execute("SELECT COUNT(system_id) FROM systems").fetchone()[0],
        "items": conn.execute("SELECT COUNT(item_id) FROM items").fetchone()[0],
        "ships": conn.execute("SELECT COUNT(ship_id) FROM ships").fetchone()[0],
    }

def get_systems() -> List[Dict]:
    return [dict(row) for row in get_connection().execute("SELECT *, system_id as id, system_name as name, system_x as x, system_y as y FROM systems ORDER BY system_name")]

def get_system(system_id: int) -> Optional[Dict]:
    row = get_connection().execute("SELECT *, system_id as id, system_name as name, system_x as x, system_y as y FROM systems WHERE system_id=?", (system_id,)).fetchone()
    return dict(row) if row else None

def get_locations(system_id: int) -> List[Dict]:
    return [dict(row) for row in get_connection().execute(
        "SELECT *, location_id as id, location_name as name, location_type as kind, location_x as local_x_au, location_y as local_y_au FROM locations WHERE system_id=? ORDER BY location_name", (system_id,))]

def get_location(location_id: int) -> Optional[Dict]:
    row = get_connection().execute("SELECT *, location_id as id, location_name as name, location_x as local_x_au, location_y as local_y_au FROM locations WHERE location_id=?", (location_id,)).fetchone()
    return dict(row) if row else None

def get_warp_gate(system_id: int) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT *, location_id as id, location_name as name, location_x as local_x_au, location_y as local_y_au FROM locations WHERE system_id=? AND location_type='warp_gate' LIMIT 1",
        (system_id,),
    ).fetchone()
    return dict(row) if row else None

def set_player_system(system_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET current_player_system_id=?, current_player_location_id=NULL WHERE id=1", (system_id,))
    conn.commit()

def set_player_location(location_id: Optional[int]) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET current_player_location_id=? WHERE id=1", (location_id,))
    conn.commit()

def get_player_full() -> Optional[Dict]:
    row = get_connection().execute("SELECT * FROM player WHERE id=1").fetchone()
    return dict(row) if row else None

def get_player_summary() -> Dict:
    player = get_player_full()
    return {"credits": player.get("current_wallet_credits", 0)} if player else {"credits": 0}

def get_player_ship() -> Optional[Dict]:
    player = get_player_full()
    if not player or not player.get("current_player_ship_id"): return None
    row = get_connection().execute("SELECT *, ship_id as id, ship_name as name FROM ships WHERE ship_id = ?", (player["current_player_ship_id"],)).fetchone()
    return dict(row) if row else None