# /data/db.py

"""
Victurus Database Interface

Thread-safe SQLite database wrapper providing:
- Thread-local connections with WAL mode
- Foreign key constraint enforcement
- CRUD operations for game entities (systems, locations, players, ships)
- Transaction management and connection lifecycle
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union

from game_controller.log_config import get_system_logger

logger = get_system_logger('database')

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "game.db"

_active_db_path_override: Optional[Path] = None

# --- Thread-local connections + one-time init ---
_tls = threading.local()
_init_lock = threading.Lock()
_is_initialized = False

DATA_DIR = ROOT / "data"
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED_PY = DATA_DIR / "seed.py"   # will load universe_seed.json


def set_active_db_path(p: Path | str) -> None:
    """Override the default database path (useful for tests or rebuilding)."""
    global _active_db_path_override
    _active_db_path_override = Path(p)


def get_active_db_path() -> Path:
    """Return the currently active database file path."""
    return _active_db_path_override if _active_db_path_override else DB_PATH


def get_active_db_uri(read_only: bool = False) -> str:
    """
    Return a sqlite3 file: URI for the active DB.
    When read_only=True, adds ?mode=ro for workers.
    """
    ap = get_active_db_path().as_posix()
    return f"file:{ap}?mode=ro" if read_only else f"file:{ap}"


def _open_new_connection() -> sqlite3.Connection:
    ap = get_active_db_path()
    ap.parent.mkdir(parents=True, exist_ok=True)
    # Default sqlite3 connections are NOT threadsafe across threads.
    # We keep one connection per thread via _tls below.
    conn = sqlite3.connect(str(ap), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row

    # Pragmas tuned for UI + background sim concurrency
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 1000;")  # 1s backoff on brief writer conflicts
    # Optional: put temp tables in memory for speed.
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


def _ensure_schema_and_seed(conn: sqlite3.Connection) -> None:
    """
    Ensure schema exists; if the DB is empty (no systems), run the seed script
    which ingests data/universe_seed.json (or ..._v2.json).
    Idempotent; guarded by _init_lock to avoid duplicate seeding.
    """
    global _is_initialized
    with _init_lock:
        if _is_initialized:
            return
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

        # Keep compatibility columns (idempotent checks)
        _ensure_icon_column(conn)
        _deprecated_ensure_system_star_column(conn)
        _ensure_location_status_column(conn)
        _ensure_custom_ship_name_column(conn)
        _ensure_docked_bay_column(conn)

        _is_initialized = True


def _ensure_icon_column(conn: sqlite3.Connection) -> None:
    """
    Keep compatibility: a column to store per-location icon paths the UI
    selects at runtime (no duplicates per system/type).
    """
    cur = conn.execute("PRAGMA table_info(locations)")
    columns = [row[1] for row in cur.fetchall()]
    if "icon_path" not in columns:
        conn.execute("ALTER TABLE locations ADD COLUMN icon_path TEXT;")
        conn.commit()


def _deprecated_ensure_system_star_column(conn: sqlite3.Connection) -> None:
    """Optional per-system star icon path assigned by UI/runtime."""
    cur = conn.execute("PRAGMA table_info(systems)")
    columns = [row[1] for row in cur.fetchall()]
    if "icon_path" not in columns:
        conn.execute("ALTER TABLE systems ADD COLUMN icon_path TEXT;")
        conn.commit()


def _ensure_location_status_column(conn: sqlite3.Connection) -> None:
    """Add current_location_status column to player table for orbit/docked tracking."""
    try:
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        if "current_location_status" not in columns:
            conn.execute("ALTER TABLE player ADD COLUMN current_location_status TEXT NOT NULL DEFAULT 'orbiting';")
            conn.commit()
            print("Added current_location_status column to player table")
    except Exception as e:
        print(f"Warning: Could not add current_location_status column: {e}")


def _ensure_custom_ship_name_column(conn: sqlite3.Connection) -> None:
    """Add custom_ship_name column to player table for custom ship naming."""
    try:
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        if "custom_ship_name" not in columns:
            conn.execute("ALTER TABLE player ADD COLUMN custom_ship_name TEXT NULL;")
            conn.commit()
            print("Added custom_ship_name column to player table")
    except Exception as e:
        print(f"Warning: Could not add custom_ship_name column: {e}")


def _ensure_docked_bay_column(conn: sqlite3.Connection) -> None:
    """Add docked_bay column to player table for bay number tracking."""
    from game_controller.log_config import get_system_logger
    logger = get_system_logger("database")
    
    try:
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        logger.debug(f"Player table columns: {columns}")
        
        if "docked_bay" not in columns:
            logger.info("Adding docked_bay column to player table")
            conn.execute("ALTER TABLE player ADD COLUMN docked_bay INTEGER NULL;")
            conn.commit()
            logger.info("Successfully added docked_bay column to player table")
            # Force a checkpoint to ensure the change is written to disk
            conn.execute("PRAGMA wal_checkpoint(FULL);")
            logger.debug("WAL checkpoint completed")
        else:
            logger.debug("docked_bay column already exists")
            
    except Exception as e:
        logger.error(f"Error adding docked_bay column: {e}")
        import traceback
        traceback.print_exc()


def get_connection() -> sqlite3.Connection:
    """
    Lazily open (and initialize) a connection bound to the CURRENT THREAD.
    This provides concurrency safety with sqlite3 while keeping WAL benefits.
    """
    conn: Optional[sqlite3.Connection] = getattr(_tls, "conn", None)
    try:
        if conn is not None:
            conn.execute("SELECT 1;")
    except sqlite3.ProgrammingError:
        conn = None

    if conn is None:
        conn = _open_new_connection()
        _tls.conn = conn
        _ensure_schema_and_seed(conn)
    return conn


def close_active_connection() -> None:
    """Closes the current THREAD's database connection, if it's open."""
    conn: Optional[sqlite3.Connection] = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _tls.conn = None


# ---------- NEW: worker-friendly read-only connector ----------

def connect_readonly(path: Optional[Union[Path, str]] = None, timeout: float = 1.0) -> sqlite3.Connection:
    """
    Open a read-only SQLite connection using a file: URI.
    Intended for worker processes (e.g., ProcessPool) to avoid write locks.
    """
    ap = Path(path) if path is not None else get_active_db_path()
    ap.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{ap.as_posix()}?mode=ro", uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row

    # Read-only friendly pragmas (silently ignore if not allowed in RO)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA journal_mode = WAL;")  # harmless if DB already in WAL
    except Exception:
        pass
    try:
        conn.execute("PRAGMA query_only = ON;")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA busy_timeout = 750;")
        conn.execute("PRAGMA temp_store = MEMORY;")
    except Exception:
        pass

    return conn


# ---------- Basic query helpers ----------

def get_counts() -> Dict[str, int]:
    conn = get_connection()
    return {
        "systems": conn.execute("SELECT COUNT(system_id) FROM systems").fetchone()[0],
        "items": conn.execute("SELECT COUNT(item_id) FROM items").fetchone()[0],
        "ships": conn.execute("SELECT COUNT(ship_id) FROM ships").fetchone()[0],
        "locations": conn.execute("SELECT COUNT(location_id) FROM locations").fetchone()[0],
    }


def get_systems() -> List[Dict]:
    return [
        dict(row)
        for row in get_connection().execute(
            """
            SELECT
              * ,
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
          * ,
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
              * ,
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
          * ,
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
    """Return the warp gate location in a system (type 'warp_gate')."""
    row = get_connection().execute(
        """
        SELECT
          * ,
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


# ---------- New helpers for the v2 universe ----------

def get_gate_links(system_id: int) -> List[Dict]:
    """Neighbor systems reachable via warp from this system."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
          CASE WHEN gl.system_a_id=? THEN gl.system_b_id ELSE gl.system_a_id END AS neighbor_system_id,
          gl.distance_pc
        FROM gate_links gl
        WHERE gl.system_a_id=? OR gl.system_b_id=?
        """,
        (system_id, system_id, system_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_resource_nodes(system_id: int) -> List[Dict]:
    """All resource nodes (asteroids, gas, ice, etc.) in a system.

    Resource metadata is now stored on `locations` (columns: resource_type,
    richness, regen_rate). This returns location rows filtered to those with a
    non-null resource_type to preserve existing call sites.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT l.*, l.location_name, l.location_x, l.location_y, l.location_id
        FROM locations l
        WHERE l.system_id = ? AND COALESCE(l.resource_type, '') != ''
        ORDER BY l.location_name
        """,
        (system_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_facilities(system_id: int) -> List[Dict]:
    """Facilities (mines, refineries, domes…) located in a system."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT f.*, l.location_name, l.location_type, l.system_id
        FROM facilities f
        JOIN locations l ON l.location_id = f.location_id
        WHERE l.system_id = ?
        ORDER BY f.facility_type, l.location_name
        """,
        (system_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_facility_io(facility_id: int) -> Dict[str, List[Dict]]:
    """Inputs/outputs for a facility (per-tick rates)."""
    conn = get_connection()
    inputs = conn.execute(
        """
        SELECT fi.item_id, i.item_name, fi.rate
        FROM facility_inputs fi
        JOIN items i ON i.item_id = fi.item_id
        WHERE fi.facility_id=?
        """,
        (facility_id,),
    ).fetchall()
    outputs = conn.execute(
        """
        SELECT fo.item_id, i.item_name, fo.rate
        FROM facility_outputs fo
        JOIN items i ON i.item_id = fo.item_id
        WHERE fo.facility_id=?
        """,
        (facility_id,),
    ).fetchall()
    return {"inputs": [dict(r) for r in inputs], "outputs": [dict(r) for r in outputs]}


def get_player_full() -> Optional[Dict]:
    """Return the single player row (id=1) or None if not seeded yet."""
    row = get_connection().execute(
        "SELECT * FROM player WHERE id=1"
    ).fetchone()
    return dict(row) if row else None


def get_player_summary() -> Dict:
    """Lightweight summary (currently just credits)."""
    player = get_player_full()
    return {"credits": player.get("current_wallet_credits", 0)} if player else {"credits": 0}


def get_player_ship() -> Optional[Dict]:
    """Return the player's current ship record (with id/name aliases)."""
    player = get_player_full()
    if not player or not player.get("current_player_ship_id"):
        return None
    row = get_connection().execute(
        """
        SELECT *,
               ship_id   AS id,
               ship_name AS name
        FROM ships
        WHERE ship_id = ?
        """,
        (player["current_player_ship_id"],),
    ).fetchone()
    return dict(row) if row else None


def get_player_location() -> Optional[Dict]:
    """Return the player's current location row with friendly aliases."""
    player = get_player_full()
    if not player or player.get("current_player_location_id") is None:
        return None
    row = get_connection().execute(
        """
        SELECT *,
               location_id   AS id,
               location_name AS name,
               location_type AS kind,
               location_x    AS local_x_au,
               location_y    AS local_y_au
        FROM locations
        WHERE location_id = ?
        """,
        (player["current_player_location_id"],),
    ).fetchone()
    return dict(row) if row else None


# ---------- Icon path helpers (persist runtime image choices) ----------

def set_location_icon_path(location_id: int, icon_path: Optional[str]) -> None:
    """Persist/clear the assigned icon for a specific location."""
    conn = get_connection()
    conn.execute("UPDATE locations SET icon_path=? WHERE location_id=?", (icon_path, location_id))
    conn.commit()


def set_system_icon_path(system_id: int, icon_path: Optional[str]) -> None:
    """[DEPRECATED] Writes to systems.icon_path for new schema."""
    """Persist/clear the assigned star GIF path for a system."""
    conn = get_connection()
    conn.execute("UPDATE systems SET icon_path=? WHERE system_id=?", (icon_path, system_id))
    # If the star also exists as a location row, mirror it for convenience
    conn.execute(
        "UPDATE locations SET icon_path=? WHERE system_id=? AND location_type='star'",
        (icon_path, system_id),
    )
    conn.commit()


def set_icon_paths_bulk(pairs: List[tuple[int, Optional[str]]]) -> None:
    """Batch update location icon paths in a single transaction."""
    if not pairs:
        return
    conn = get_connection()
    conn.executemany(
        "UPDATE locations SET icon_path=? WHERE location_id=?",
        [(p, lid) for (lid, p) in pairs],
    )
    conn.commit()


def clear_icon_paths_for_system(system_id: int, kinds: Optional[List[str]] = None) -> None:
    """Clear stored icon assignments for a system (optionally limited to some kinds).
    kinds examples: ['planet','station','moon','resource','warp_gate']. """
    conn = get_connection()
    if kinds:
        qmarks = ",".join(["?"] * len(kinds))
        sql = f"UPDATE locations SET icon_path=NULL WHERE system_id=? AND location_type IN ({qmarks})"
        conn.execute(sql, (system_id, *kinds))
    else:
        conn.execute("UPDATE locations SET icon_path=NULL WHERE system_id=?", (system_id,))
    conn.commit()


def set_resource_node_icon_path(location_id: int, icon_path: Optional[str]) -> None:
    """Persist/clear the assigned icon for a specific resource node (by location_id).

    After merging, resource icons live on `locations.icon_path` so this updates
    that column for the resource's location id.
    """
    conn = get_connection()
    conn.execute("UPDATE locations SET icon_path=? WHERE location_id=?", (icon_path, location_id))
    conn.commit()


def set_resource_node_icons_bulk(pairs: List[tuple[int, Optional[str]]]) -> None:
    """Batch update locations.icon_path for resource nodes (location_id, icon_path)."""
    if not pairs:
        return
    conn = get_connection()
    conn.executemany(
        "UPDATE locations SET icon_path=? WHERE location_id=?",
        [(p, lid) for (lid, p) in pairs],
    )
    conn.commit()


def get_custom_ship_name() -> Optional[str]:
    """Get the player's custom name for their current ship."""
    try:
        conn = get_connection()
        row = conn.execute("SELECT custom_ship_name FROM player WHERE id = 1").fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        # Column doesn't exist yet (old DB) or other error
        return None


def set_custom_ship_name(ship_name: str) -> None:
    """Set the player's custom name for their current ship."""
    try:
        conn = get_connection()
        conn.execute("UPDATE player SET custom_ship_name = ? WHERE id = 1", (ship_name,))
        conn.commit()
        logger.debug(f"Set custom ship name to: {ship_name}")
    except Exception as e:
        logger.error(f"Error setting custom ship name: {e}")


def clear_custom_ship_name() -> None:
    """Clear the player's custom ship name (revert to default ship name)."""
    try:
        conn = get_connection()
        conn.execute("UPDATE player SET custom_ship_name = NULL WHERE id = 1")
        conn.commit()
        logger.debug("Cleared custom ship name")
    except Exception as e:
        logger.error(f"Error clearing custom ship name: {e}")


def set_docked_bay(bay_number: int) -> None:
    """Set the bay number where the player is currently docked."""
    from game_controller.log_config import get_system_logger
    logger = get_system_logger("database")
    
    try:
        conn = get_connection()
        logger.debug(f"Setting docked bay to: {bay_number}")
        
        # Verify column exists before trying to use it
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        if "docked_bay" not in columns:
            logger.error(f"docked_bay column missing! Available columns: {columns}")
            _ensure_docked_bay_column(conn)
            
        conn.execute("UPDATE player SET docked_bay = ? WHERE id = 1", (bay_number,))
        conn.commit()
        logger.debug(f"Successfully set docked bay to: {bay_number}")
        
    except Exception as e:
        logger.error(f"Error setting docked bay: {e}")
        import traceback
        logger.error(traceback.format_exc())


def get_docked_bay() -> Optional[int]:
    """Get the bay number where the player is currently docked."""
    from game_controller.log_config import get_system_logger
    logger = get_system_logger("database")
    
    try:
        conn = get_connection()
        logger.debug("Getting docked bay number")
        
        # Verify column exists before trying to use it
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        if "docked_bay" not in columns:
            logger.error(f"docked_bay column missing! Available columns: {columns}")
            _ensure_docked_bay_column(conn)
            return None
            
        cur = conn.execute("SELECT docked_bay FROM player WHERE id = 1")
        result = cur.fetchone()
        bay_number = int(result[0]) if result and result[0] is not None else None
        logger.debug(f"Retrieved docked bay: {bay_number}")
        return bay_number
        
    except Exception as e:
        logger.error(f"Error getting docked bay: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def clear_docked_bay() -> None:
    """Clear the docked bay (when undocking)."""
    from game_controller.log_config import get_system_logger
    logger = get_system_logger("database")
    
    try:
        conn = get_connection()
        logger.debug("Clearing docked bay")
        
        # Verify column exists before trying to use it
        cur = conn.execute("PRAGMA table_info(player)")
        columns = [row[1] for row in cur.fetchall()]
        if "docked_bay" not in columns:
            logger.error(f"docked_bay column missing! Available columns: {columns}")
            _ensure_docked_bay_column(conn)
            return
            
        conn.execute("UPDATE player SET docked_bay = NULL WHERE id = 1")
        conn.commit()
        logger.debug("Successfully cleared docked bay")
        
    except Exception as e:
        logger.error(f"Error clearing docked bay: {e}")
        import traceback
        logger.error(traceback.format_exc())
