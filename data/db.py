"""
data/db.py
SQLite access layer + schema/seed + first-run icon assignment.

Adds:
- Per-save DB path override (SaveManager sets it)
- systems.star_icon_path column (created if missing)
- One-time random star/planet/station icon assignment
- get_locations(): uses x,y aliased as local_x_au/local_y_au
- get_status_snapshot(): unified player + active ship + jump info for StatusSheet
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

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
        if r.get("icon_path"):
            continue
        chosen = cycle[idx % len(cycle)]
        idx += 1
        rel = chosen.relative_to(ROOT).as_posix()
        conn.execute("UPDATE locations SET icon_path=? WHERE id=?", (rel, r["id"]))

def _assign_location_icons_if_missing(conn: sqlite3.Connection) -> None:
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

# ---------- status helpers for StatusSheet ----------
def _table_has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def _get_name_by_id(conn: sqlite3.Connection, table: str, id_val: Optional[int]) -> Optional[str]:
    if not id_val:
        return None
    cur = conn.execute(f"SELECT name FROM {table} WHERE id=?", (id_val,))
    r = cur.fetchone()
    return r[0] if r else None

def _read_first_row(conn: sqlite3.Connection, q: str, args: Tuple=()) -> Dict[str, Any]:
    cur = conn.execute(q, args)
    row = cur.fetchone()
    return dict(row) if row else {}

def _get_active_ship_row(conn: sqlite3.Connection, player_id: int = 1) -> Dict[str, Any]:
    # 1) Prefer player.active_ship_id if present
    if _table_has_column(conn, "player", "active_ship_id"):
        r = _read_first_row(conn, "SELECT active_ship_id FROM player WHERE id=?", (player_id,))
        ship_id = r.get("active_ship_id")
        if ship_id:
            return _read_first_row(conn, "SELECT * FROM ships WHERE id=?", (ship_id,))

    # 2) Try 'ships.owner_player_id' + is_active flag if present
    owner_col = _table_has_column(conn, "ships", "owner_player_id")
    active_col = _table_has_column(conn, "ships", "is_active")
    if owner_col:
        if active_col:
            r = _read_first_row(conn, "SELECT * FROM ships WHERE owner_player_id=? AND is_active=1 LIMIT 1", (player_id,))
            if r:
                return r
        r = _read_first_row(conn, "SELECT * FROM ships WHERE owner_player_id=? LIMIT 1", (player_id,))
        if r:
            return r

    # 3) Fallback: first ship
    return _read_first_row(conn, "SELECT * FROM ships LIMIT 1")

def _pick_stat(row: Dict[str, Any], names: List[str], default: int|float=0) -> int|float:
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return default

def _pair(row: Dict[str, Any], curr_names: List[str], max_names: List[str], default_curr=0, default_max=1) -> Tuple[int, int]:
    cur = int(round(_pick_stat(row, curr_names, default_curr)))
    mx = int(round(_pick_stat(row, max_names, default_max)))
    mx = max(1, mx)
    cur = max(0, min(cur, mx))
    return cur, mx

def _float(row: Dict[str, Any], names: List[str], default: float=0.0) -> float:
    v = _pick_stat(row, names, default)
    try:
        return float(v)
    except Exception:
        return float(default)

def _infer_ship_state(conn: sqlite3.Connection, ship_row: Dict[str, Any], player_row: Dict[str, Any]) -> str:
    """
    Try to produce a human-friendly ship state string using whatever columns exist.
    Priority:
      1) ships.state or ships.status
      2) explicit booleans (in_combat, is_docked, is_traveling)
      3) derived from player current_location_id (Docked vs Traveling)
    """
    # 1) Direct string columns on ships
    for col in ("state", "status", "ship_state"):
        if col in ship_row and ship_row[col]:
            return str(ship_row[col])

    # 2) Booleans/ints on ships or player
    truthy = lambda v: bool(v) and str(v) not in ("0", "False", "false", "None")
    if "in_combat" in ship_row and truthy(ship_row["in_combat"]):
        return "Combat"
    if "is_docked" in ship_row and truthy(ship_row["is_docked"]):
        return "Docked"
    if "is_traveling" in ship_row and truthy(ship_row["is_traveling"]):
        return "Traveling"

    # 3) Derived from player position
    loc_id = player_row.get("current_location_id")
    if loc_id:
        return "Docked"
    if player_row.get("system_id"):
        return "Traveling"

    return "Idle"

def get_status_snapshot() -> Dict[str, Any]:
    """
    Return a robust snapshot for StatusSheet:
      - player_name, credits, system_name, location_name
      - ship_name, ship_state
      - hull/hull_max, shield/shield_max, fuel/fuel_max, energy/energy_max, cargo/cargo_max
      - base_jump_distance, current_jump_distance
    We attempt multiple column names to adapt to schema diffs.
    """
    conn = get_connection()
    player = get_player_full()
    player_name = player.get("name") or "—"
    credits = int(player.get("credits") or 0)
    system_id = player.get("system_id")
    location_id = player.get("current_location_id")

    system_name = _get_name_by_id(conn, "systems", system_id) or ""
    location_name = _get_name_by_id(conn, "locations", location_id) or ""

    ship_row = _get_active_ship_row(conn)
    ship_name = ship_row.get("name") or ship_row.get("model") or "—"
    ship_state = _infer_ship_state(conn, ship_row, player) or "—"

    # stats pairs
    hull, hull_max = _pair(
        ship_row,
        curr_names=["hull", "hull_current", "hp", "hp_current"],
        max_names=["hull_max", "hp_max", "structure_max", "structure"],
        default_curr=0,
        default_max=100,
    )
    shield, shield_max = _pair(
        ship_row,
        curr_names=["shield", "shield_current", "shields", "shields_current"],
        max_names=["shield_max", "shields_max"],
        default_curr=0,
        default_max=100,
    )
    fuel, fuel_max = _pair(
        ship_row,
        curr_names=["fuel", "fuel_current"],
        max_names=["fuel_max", "fuel_capacity"],
        default_curr=0,
        default_max=100,
    )
    energy, energy_max = _pair(
        ship_row,
        curr_names=["energy", "energy_current", "power", "power_current"],
        max_names=["energy_max", "power_max", "reactor_capacity"],
        default_curr=0,
        default_max=100,
    )
    cargo, cargo_max = _pair(
        ship_row,
        curr_names=["cargo", "cargo_current", "cargo_used"],
        max_names=["cargo_max", "cargo_capacity"],
        default_curr=0,
        default_max=50,
    )

    # jump distances
    base_jump = _float(ship_row, ["base_jump_distance", "jump_range", "jump_distance"], 5.0)

    # If we don't have explicit fuel->jump math, assume linear scaling with fuel fraction.
    fuel_frac = (float(fuel) / float(max(1, fuel_max))) if fuel_max else 0.0
    current_jump = max(0.0, base_jump * fuel_frac)

    return {
        "player_name": player_name,
        "credits": credits,
        "system_id": system_id,
        "system_name": system_name,
        "location_id": location_id,
        "location_name": location_name,
        "ship_name": ship_name,
        "ship_state": ship_state,
        "hull": hull,
        "hull_max": hull_max,
        "shield": shield,
        "shield_max": shield_max,
        "fuel": fuel,
        "fuel_max": fuel_max,
        "energy": energy,
        "energy_max": energy_max,
        "cargo": cargo,
        "cargo_max": cargo_max,
        "base_jump_distance": base_jump,
        "current_jump_distance": current_jump,
    }
