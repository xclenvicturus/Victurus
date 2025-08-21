"""
data/db.py
SQLite access layer + schema/seed + first-run icon assignment.

Adds:
- Per-save DB path override (SaveManager sets it)
- systems.star_icon_path column (created if missing)
- One-time random star/planet/station icon assignment
- get_locations() fixed to use schema columns x,y (aliased as local_x_au/local_y_au)
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "game.db"

# -------- per-save DB override --------
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

# ---------- connection mgmt ----------
def _is_connection_open(conn: Optional[sqlite3.Connection]) -> bool:
    if conn is None:
        return False
    try:
        conn.execute("SELECT 1;")
        return True
    except Exception:
        return False

def _open_new_connection() -> sqlite3.Connection:
    # Ensure parent exists for whichever DB path is active
    ap = get_active_db_path()
    ap.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ap))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = _open_new_connection()
        _ensure_schema_and_seed(_connection)
        _ensure_icon_column(_connection)
        _ensure_system_star_column(_connection)
        _assign_location_icons_if_missing(_connection)
        _assign_system_star_icons_if_missing(_connection)
        return _connection

    if not _is_connection_open(_connection):
        _connection = _open_new_connection()
        _ensure_schema_and_seed(_connection)
        _ensure_icon_column(_connection)
        _ensure_system_star_column(_connection)
        _assign_location_icons_if_missing(_connection)
        _assign_system_star_icons_if_missing(_connection)
        return _connection

    return _connection

# ---------- schema & seed ----------
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
            seed_fn(conn)  # seed() commits

# ---------- schema evolution ----------
def _ensure_icon_column(conn: sqlite3.Connection) -> None:
    """Ensure locations.icon_path TEXT exists."""
    cur = conn.execute("PRAGMA table_info(locations)")
    cols = {row[1] for row in cur.fetchall()}
    if "icon_path" not in cols:
        conn.execute("ALTER TABLE locations ADD COLUMN icon_path TEXT")
        conn.commit()

def _ensure_system_star_column(conn: sqlite3.Connection) -> None:
    """Ensure systems.star_icon_path TEXT exists."""
    cur = conn.execute("PRAGMA table_info(systems)")
    cols = {row[1] for row in cur.fetchall()}
    if "star_icon_path" not in cols:
        conn.execute("ALTER TABLE systems ADD COLUMN star_icon_path TEXT")
        conn.commit()

# ---------- icon helpers ----------
def _list_image_files(p: Path) -> List[Path]:
    if not p.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return [q for q in p.iterdir() if q.suffix.lower() in exts]

def _assign_for_kind(conn: sqlite3.Connection, system_id: int, kind: str, candidates: List[Path]) -> None:
    """Assign icons in a deterministic cycle for a given system & kind."""
    cur = conn.execute(
        "SELECT id, icon_path FROM locations WHERE system_id=? AND kind=? ORDER BY id",
        (system_id, kind),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cycle = candidates[:]
    if not cycle:
        return

    idx = 0
    for r in rows:
        if r["icon_path"]:
            continue  # already assigned
        chosen = cycle[idx % len(cycle)]
        idx += 1
        # store path relative to repo root for portability
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE locations SET icon_path=? WHERE id=?", (rel, r["id"]))

def _assign_location_icons_if_missing(conn: sqlite3.Connection) -> None:
    """Assign per-location icons once, system by system."""
    planet_files = _list_image_files(PLANETS_DIR)
    station_files = _list_image_files(STATIONS_DIR)
    if not planet_files and not station_files:
        return

    cur = conn.execute("SELECT id FROM systems ORDER BY id")
    systems = [r["id"] for r in cur.fetchall()]
    for sid in systems:
        if planet_files:
            _assign_for_kind(conn, sid, "planet", planet_files)
        if station_files:
            _assign_for_kind(conn, sid, "station", station_files)
    conn.commit()

def _assign_system_star_icons_if_missing(conn: sqlite3.Connection) -> None:
    star_imgs = _list_image_files(STARS_DIR)
    if not star_imgs:
        return
    cur = conn.execute("SELECT id, star_icon_path FROM systems ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if r.get("star_icon_path"):
            continue
        chosen = random.choice(star_imgs)
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE systems SET star_icon_path=? WHERE id=?", (rel, r["id"]))
    conn.commit()

# ---------- queries ----------
def get_counts() -> Dict[str, int]:
    conn = get_connection()
    d = {}
    for k, q in {
        "systems": "SELECT COUNT(*) FROM systems",
        "items": "SELECT COUNT(*) FROM items",
        "ships": "SELECT COUNT(*) FROM ships",
    }.items():
        cur = conn.execute(q)
        d[k] = int(cur.fetchone()[0])
    return d

def get_systems() -> List[Dict]:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, x, y, IFNULL(star_icon_path,'') AS star_icon_path FROM systems ORDER BY name")
    return [dict(row) for row in cur.fetchall()]

def get_system(system_id: int) -> Dict:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, x, y, IFNULL(star_icon_path,'') AS star_icon_path FROM systems WHERE id=?", (system_id,))
    row = cur.fetchone()
    return dict(row) if row else {}

def get_locations(system_id: int) -> List[Dict]:
    """
    Return locations for a system.

    NOTE:
      - Schema uses columns x,y (local AU offsets). We alias them as local_x_au/local_y_au
        for compatibility with any UI that expects those keys.
    """
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT
            id,
            system_id,
            name,
            kind,
            x AS local_x_au,
            y AS local_y_au,
            parent_location_id,
            IFNULL(icon_path,'') AS icon_path
        FROM locations
        WHERE system_id=?
        ORDER BY name
        """,
        (system_id,),
    )
    return [dict(row) for row in cur.fetchall()]

def get_location(location_id: int) -> Dict:
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT
            id,
            system_id,
            name,
            kind,
            x AS local_x_au,
            y AS local_y_au,
            parent_location_id,
            IFNULL(icon_path,'') AS icon_path
        FROM locations
        WHERE id=?
        """,
        (location_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else {}

def set_player_system(system_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET system_id=?, current_location_id=NULL WHERE id=1", (system_id,))
    conn.commit()

def set_player_location(location_id: Optional[int]) -> None:
    conn = get_connection()
    if location_id is None:
        conn.execute("UPDATE player SET current_location_id=NULL WHERE id=1")
    else:
        conn.execute("UPDATE player SET current_location_id=? WHERE id=1", (location_id,))
    conn.commit()

def get_player_full() -> Dict:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, credits, system_id, current_location_id FROM player LIMIT 1")
    row = cur.fetchone()
    if row is None:
        return {}
    return dict(row)

def get_player_summary() -> Dict:
    d = get_player_full()
    return {"credits": d.get("credits", 0)}
