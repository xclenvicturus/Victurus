"""
data/db.py
SQLite access layer + schema/seed + first-run icon assignment.

Now also assigns a star icon per system on first run:
- systems.star_icon_path TEXT column (added if missing)
- picks a random file from assets/stars/* and stores a RELATIVE path
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "game.db"

ASSETS = ROOT / "assets"
PLANETS_DIR = ASSETS / "planets"
STATIONS_DIR = ASSETS / "stations"
STARS_DIR = ASSETS / "stars"

SCHEMA_PATH = ROOT / "data" / "schema.sql"
SEED_PY = ROOT / "data" / "seed.py"

_connection: Optional[sqlite3.Connection] = None


# ---------- connection mgmt ----------
def _is_connection_open(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
        return True
    except sqlite3.ProgrammingError as e:
        if "closed" in str(e).lower():
            return False
        raise


def _open_new_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
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
        # Idempotent on reopen
        _ensure_schema_and_seed(_connection)
        _ensure_icon_column(_connection)
        _ensure_system_star_column(_connection)
        _assign_location_icons_if_missing(_connection)
        _assign_system_star_icons_if_missing(_connection)

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


# ---------- utilities ----------
def _list_image_files(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    exts = (".svg", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
    return sorted([p for p in directory.iterdir() if p.suffix.lower() in exts and p.is_file()])


# ---------- first-run assignments ----------
def _assign_for_kind(
    conn: sqlite3.Connection,
    system_id: int,
    kind: str,
    pool_files: List[Path],
) -> None:
    """Assign icon_path for all locations of 'kind' within 'system_id' if missing.
    Avoid duplicates within the same system where possible (no repeats until pool exhausted).
    """
    if not pool_files:
        return

    cur = conn.execute(
        "SELECT id, icon_path FROM locations WHERE system_id=? AND kind=? ORDER BY id",
        (system_id, kind),
    )
    rows = cur.fetchall()
    used = {Path(r["icon_path"]).name for r in rows if r["icon_path"]}

    fresh = [p for p in pool_files if p.name not in used]
    stale = [p for p in pool_files if p.name in used]
    random.shuffle(fresh)
    random.shuffle(stale)
    cycle = fresh + stale
    if not cycle:
        return

    idx = 0
    for r in rows:
        if r["icon_path"]:
            continue  # already assigned
        chosen = cycle[idx % len(cycle)]
        idx += 1
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
    """Assign a star icon to each system if missing."""
    star_files = _list_image_files(STARS_DIR)
    if not star_files:
        return

    cur = conn.execute("SELECT id, star_icon_path FROM systems ORDER BY id")
    rows = cur.fetchall()
    random.shuffle(star_files)  # variety across runs
    idx = 0
    for r in rows:
        if r["star_icon_path"]:
            continue
        chosen = star_files[idx % len(star_files)]
        idx += 1
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE systems SET star_icon_path=? WHERE id=?", (rel, r["id"]))
    conn.commit()


# ---------- public API ----------
def get_counts() -> Dict[str, int]:
    conn = get_connection()
    res = {}
    for name, table in [("systems", "systems"), ("items", "items"), ("ships", "ships")]:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        res[name] = cur.fetchone()[0]
    return res


def get_systems() -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, x, y, star_icon_path FROM systems ORDER BY name")
    return cur.fetchall()


def get_system(system_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, x, y, star_icon_path FROM systems WHERE id=?", (system_id,))
    return cur.fetchone()


def get_locations(system_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT id, system_id, name, kind, icon_path FROM locations WHERE system_id=? ORDER BY name",
        (system_id,),
    )
    return cur.fetchall()


def get_location(location_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT id, system_id, name, kind, icon_path FROM locations WHERE id=?",
        (location_id,),
    )
    return cur.fetchone()


def set_player_system(system_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE player SET system_id=?, current_location_id=NULL", (system_id,))
    conn.commit()


def set_player_location(location_id: Optional[int]) -> None:
    conn = get_connection()
    if location_id is None:
        conn.execute("UPDATE player SET current_location_id=NULL")
    else:
        conn.execute("UPDATE player SET current_location_id=?", (location_id,))
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
