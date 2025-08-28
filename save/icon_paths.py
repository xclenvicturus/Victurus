# /save/icon_paths.py

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from data import db

# Configure a module-level logger (caller can override handlers/level)
log = logging.getLogger(__name__)

# Project assets root is ../assets relative to this file (project root / assets)
# save/icon_paths.py is located at <repo>/save/, so parents[1] is repo root.
ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets"

# Normalization helpers ----------------------------------------------------
def _norm(s: Optional[str]) -> str:
    try:
        s2 = str(s or "").strip().lower().replace(" ", "_")
    except Exception:
        return ""
    # a few common variants
    if s2 in {"warp_gates"}:
        return "warp_gates"
    if s2 in {"asteroid_fields"}:
        return "asteroid_fields"
    if s2 in {"gas_clouds"}:
        return "gas_clouds"
    if s2 in {"ice_fields"}:
        return "ice_fields"
    if s2 in {"crystal_veins"}:
        return "crystal_veins"
    if s2 in {"stars"}:
        return "stars"
    if s2 in {"planets"}:
        return "planets"
    if s2 in {"moons"}:
        return "moons"
    if s2 in {"stations"}:
        return "stations"
    if s2.startswith("resource:"):
        return s2.split("resource:", 1)[1]
    return s2

# Map normalized kind/resource_type -> folder name under assets/
_KIND_TO_FOLDER: Dict[str, str] = {
    "stars": "stars",
    "planets": "planets",
    "moons": "moons",
    "stations": "stations",
    "warp_gates": "warp_gates",
    # resources (normalized to plural folder names)
    "asteroid_fields": "asteroid_fields",
    "gas_clouds": "gas_clouds",
    "ice_fields": "ice_fields",
    "crystal_veins": "crystal_veins",
}

_ALLOWED_EXTS = {".gif", ".png", ".jpg", ".jpeg", ".svg"}

def _list_images(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_EXTS])

def _rel_to_assets(p: Path) -> str:
    """Return a POSIX-style relative path that starts with 'assets/'."""
    try:
        rp = p.relative_to(ASSETS_ROOT)
        return str(Path("assets") / rp).replace("\\", "/")
    except Exception:
        # fall back to a best-effort portable path
        return f"assets/{p.name}"


def _to_storable_path(p: Optional[str | Path]) -> Optional[str]:
    """Convert a supplied path (absolute or relative) to a storable POSIX path.

    If the path is under the project's `assets/` folder, store a portable
    `assets/...` relative path. Otherwise, store the given string with
    backslashes normalized to forward slashes.
    """
    if p is None:
        return None
    try:
        path = Path(str(p))
    except Exception:
        return str(p)

    # Prefer assets-relative storage when possible
    try:
        return _rel_to_assets(path)
    except Exception:
        # Normalize separators for portability
        return str(path).replace("\\", "/")


def persist_location_icon(location_id: int, icon_path: Optional[str | Path]) -> None:
    """Persist a selected icon path for a location into the active DB.

    The path will be normalized to an `assets/...` POSIX path if it points
    inside the project's assets folder. Passing None clears the stored value.
    """
    storable = _to_storable_path(icon_path)
    db.set_location_icon_path(location_id, storable)


def persist_system_icon(system_id: int, icon_path: Optional[str | Path]) -> None:
    """Persist a selected star/system icon path into the active DB.

    Mirrors the path into any star-type location rows in the same system for
    convenience (same behavior as set_system_icon_path in `data.db`).
    """
    storable = _to_storable_path(icon_path)
    db.set_system_icon_path(system_id, storable)


def persist_icon_paths_bulk(pairs: List[tuple[int, Optional[str]]]) -> None:
    """Persist multiple (location_id, icon_path) pairs in a single transaction.

    Paths are normalized the same as `persist_location_icon`.
    """
    normalized = [(loc_id, _to_storable_path(p)) for (loc_id, p) in pairs]
    # data.db exposes a similar batch helper, but we update via SQL here for
    # simplicity and to keep this module self-contained.
    if not normalized:
        return
    conn = db.get_connection()
    cur = conn.cursor()
    cur.executemany("UPDATE locations SET icon_path=? WHERE location_id=?", [(p, lid) for (lid, p) in normalized])
    conn.commit()

def _inventory_assets() -> Dict[str, List[Path]]:
    inv: Dict[str, List[Path]] = {}
    for kind, sub in _KIND_TO_FOLDER.items():
        inv[kind] = _list_images(ASSETS_ROOT / sub)
    return inv

# Core: bake_icon_paths ----------------------------------------------------
def bake_icon_paths(conn: sqlite3.Connection, *, only_missing: bool = True) -> Dict[str, int]:
    """
    Assign icon paths into the DB for systems.icon_path and locations.icon_path.

    - Enforces no duplicate image *within the same system* per bucket (planets, stations, moons, resources, gates).
    - Stores POSIX-style relative paths (e.g., 'assets/planets/planet_07.gif') for portability.
    - If an asset bucket has no files, that bucket is skipped (leaves NULL/empty).
    - `only_missing=True` updates rows where the column is NULL/empty; False forces overwrite.
    """
    cur = conn.cursor()
    updated = {"systems": 0, "locations": 0}

    inv = _inventory_assets()

    # ----- Systems / stars -----
    star_files = inv.get("stars", [])
    if star_files:
        if only_missing:
            sys_rows = cur.execute(
                "SELECT system_id FROM systems WHERE COALESCE(icon_path,'') = '' ORDER BY system_id"
            ).fetchall()
        else:
            sys_rows = cur.execute("SELECT system_id FROM systems ORDER BY system_id").fetchall()
        for (sys_id,) in sys_rows:
            # deterministic but varied index
            idx = int((int(sys_id) * 1103 + 37) % len(star_files))
            chosen = star_files[idx]
            cur.execute(
                "UPDATE systems SET icon_path=? WHERE system_id=?",
                (_rel_to_assets(chosen), int(sys_id)),
            )
            updated["systems"] += 1
    else:
        log.warning("No star images found under %s", ASSETS_ROOT / _KIND_TO_FOLDER["stars"])

    # ----- Locations -----
    if only_missing:
        loc_rows = cur.execute(
            "SELECT location_id, system_id, location_type, resource_type FROM locations "
            "WHERE COALESCE(icon_path,'') = '' ORDER BY system_id, location_id"
        ).fetchall()
    else:
        loc_rows = cur.execute(
            "SELECT location_id, system_id, location_type, resource_type FROM locations "
            "ORDER BY system_id, location_id"
        ).fetchall()

    # Track used indices per (system_id, bucket) to ensure uniqueness
    used_indices: Dict[Tuple[int, str], set[int]] = {}

    def pick_unique(files: List[Path], sys_id: int, bucket: str, row_idx: int) -> Optional[Path]:
        if not files:
            return None
        used = used_indices.setdefault((sys_id, bucket), set())
        # Seed distributes choices by system and row index, but remains deterministic
        start = (sys_id * 2657 + row_idx * 161) % len(files)
        for off in range(len(files)):
            idx = (start + off) % len(files)
            if idx not in used:
                used.add(idx)
                return files[idx]
        # fallback if pool smaller than count; reuse deterministically
        return files[start % len(files)]

    for row_idx, (loc_id, sys_id, loc_type, resource_type) in enumerate(loc_rows):
        lt = _norm(loc_type)
        # Normalize common singular/variant kinds to the inventory keys (plural, underscore form)
        kind_map = {
            "star": "stars",
            "planet": "planets",
            "moon": "moons",
            "station": "stations",
            "warp_gate": "warp_gates",
            "warpgate": "warp_gates",
            "warp gate": "warp_gates",
            # resource variants
            "asteroid_field": "asteroid_fields",
            "gas_cloud": "gas_clouds",
            "ice_field": "ice_fields",
            "crystal_vein": "crystal_veins",
        }

        key = None
        if lt == "resource":
            # Location stored as generic 'resource' with a separate resource_type
            tail = _norm(resource_type)
            key = kind_map.get(tail) or _KIND_TO_FOLDER.get(tail)
        elif lt.startswith("resource:"):
            # resource:asteroid_field -> asteroid_fields
            tail = _norm(lt.split("resource:", 1)[1])
            key = kind_map.get(tail) or _KIND_TO_FOLDER.get(tail)
        else:
            key = kind_map.get(lt) or _KIND_TO_FOLDER.get(lt) or (lt + "s")

        if not key:
            # unrecognized type; skip
            continue

        files = inv.get(key, [])
        chosen = pick_unique(files, int(sys_id), lt, row_idx)
        if not chosen:
            continue
        cur.execute(
            "UPDATE locations SET icon_path=? WHERE location_id=?",
            (_rel_to_assets(chosen), int(loc_id)),
        )
        updated["locations"] += 1

    # Resource locations (asteroid_field, gas_cloud, ice_field, crystal_vein)
    # are handled in the main locations loop above because their
    # `location_type`/mapping maps to the appropriate asset buckets.

    conn.commit()
    return updated
