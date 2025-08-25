# /data/db.py

"""
SQLite access layer: connection, schema/seed, and query helpers.

"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "game.db"

_active_db_path_override: Optional[Path] = None
_connection: Optional[sqlite3.Connection] = None

DATA_DIR = ROOT / "data"
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED_PY = DATA_DIR / "seed.py"


def set_active_db_path(p: Path | str) -> None:
    global _active_db_path_override
    _active_db_path_override = Path(p)


def get_active_db_path() -> Path:
    return _active_db_path_override if _active_db_path_override else DB_PATH


def _is_connection_open(conn: Optional[sqlite3.Connection]) -> bool:
    if conn is None:
        return False
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


def _ensure_schema_and_seed(conn: sqlite3.Connection) -> None:
    # Always ensure schema exists; seed on first run.
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


def _ensure_icon_column(conn: sqlite3.Connection) -> None:
    """DB column for per-location icon paths (assigned by UI layer)."""
    cur = conn.execute("PRAGMA table_info(locations)")
    columns = [row[1] for row in cur.fetchall()]
    if "icon_path" not in columns:
        conn.execute("ALTER TABLE locations ADD COLUMN icon_path TEXT;")
        conn.commit()


def _ensure_system_star_column(conn: sqlite3.Connection) -> None:
    """DB column for per-system star icon (assigned by UI layer)."""
    cur = conn.execute("PRAGMA table_info(systems)")
    columns = [row[1] for row in cur.fetchall()]
    if "star_icon_path" not in columns:
        conn.execute("ALTER TABLE systems ADD COLUMN star_icon_path TEXT;")
        conn.commit()


def get_connection() -> sqlite3.Connection:
    """
    Lazily open (and initialize) the global connection.
    Note: This only ensures schema and required columns; it does NOT assign icons.
    """
    global _connection
    if _connection is None or not _is_connection_open(_connection):
        _connection = _open_new_connection()
        _ensure_schema_and_seed(_connection)
        _ensure_icon_column(_connection)
        _ensure_system_star_column(_connection)
    return _connection


def close_active_connection() -> None:
    """Closes the current global database connection, if it's open."""
    global _connection
    if _connection is not None and _is_connection_open(_connection):
        _connection.close()
    _connection = None


# ---------- Query helpers ----------

def get_counts() -> Dict[str, int]:
    conn = get_connection()
    return {
        "systems": conn.execute("SELECT COUNT(system_id) FROM systems").fetchone()[0],
        "items": conn.execute("SELECT COUNT(item_id) FROM items").fetchone()[0],
        "ships": conn.execute("SELECT COUNT(ship_id) FROM ships").fetchone()[0],
    }


def get_systems() -> List[Dict]:
    return [
        dict(row)
        for row in get_connection().execute(
            """
            SELECT
              *,
              system_id   AS id,
              system_name AS name,
              system_x    AS x,
              system_y    AS y
            FROM systems
            ORDER BY system_name
            """
        )
    ]


def get_system(system_id: int) -> Optional[Dict]:
    row = get_connection().execute(
        """
        SELECT
          *,
          system_id   AS id,
          system_name AS name,
          system_x    AS x,
          system_y    AS y
        FROM systems
        WHERE system_id=?
        """,
        (system_id,),
    ).fetchone()
    return dict(row) if row else None


def get_locations(system_id: int) -> List[Dict]:
    return [
        dict(row)
        for row in get_connection().execute(
            """
            SELECT
              *,
              location_id   AS id,
              location_name AS name,
              location_type AS kind,
              location_x    AS local_x_au,
              location_y    AS local_y_au
            FROM locations
            WHERE system_id=?
            ORDER BY location_name
            """,
            (system_id,),
        )
    ]


def get_location(location_id: int) -> Optional[Dict]:
    row = get_connection().execute(
        """
        SELECT
          *,
          location_id   AS id,
          location_name AS name,
          location_x    AS local_x_au,
          location_y    AS local_y_au
        FROM locations
        WHERE location_id=?
        """,
        (location_id,),
    ).fetchone()
    return dict(row) if row else None


def get_warp_gate(system_id: int) -> Optional[Dict]:
    row = get_connection().execute(
        """
        SELECT
          *,
          location_id   AS id,
          location_name AS name,
          location_x    AS local_x_au,
          location_y    AS local_y_au
        FROM locations
        WHERE system_id=? AND location_type='warp_gate'
        LIMIT 1
        """,
        (system_id,),
    ).fetchone()
    return dict(row) if row else None


def get_player_full() -> Optional[Dict]:
    row = get_connection().execute("SELECT * FROM player WHERE id=1").fetchone()
    return dict(row) if row else None


def get_player_summary() -> Dict:
    player = get_player_full()
    return {"credits": player.get("current_wallet_credits", 0)} if player else {"credits": 0}


def get_player_ship() -> Optional[Dict]:
    player = get_player_full()
    if not player or not player.get("current_player_ship_id"):
        return None
    row = get_connection().execute(
        "SELECT *, ship_id AS id, ship_name AS name FROM ships WHERE ship_id = ?",
        (player["current_player_ship_id"],),
    ).fetchone()
    return dict(row) if row else None
