# /save/icon_paths.py

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"

# Map normalized kind/resource_type -> folder name under assets/
_KIND_TO_FOLDER: Dict[str, str] = {
    "stars": "stars",
    "planets": "planets",
    "moons": "moons",
    "stations": "stations",
    "warpgate": "warpgates",
    # resources
    "asteroid_fields": "asteroid_fields",
    "gas_clouds": "gas_clouds",
    "ice_fields": "ice_fields",
    "crystal_veins": "crystal_veins",
}

def _list_gifs(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower()==".gif"])

def _choose_deterministic(idx_seed: int, files: List[Path]) -> Optional[Path]:
    if not files:
        return None
    # Simple modular pick (stable across runs)
    return files[idx_seed % len(files)]

def _norm(s: Optional[str]) -> str:
    try:
        s2 = str(s or "").strip().lower().replace(" ", "_")
    except Exception:
        return ""
    if s2 == "warp gate":
        s2 = "warp_gate"
    return s2

def _folder_for_kind(kind: str) -> Optional[Path]:
    k = _norm(kind)
    sub = _KIND_TO_FOLDER.get(k)
    return (ASSETS_ROOT / sub) if sub else None

def _folder_for_resource(rt: str) -> Optional[Path]:
    k = _norm(rt)
    sub = _KIND_TO_FOLDER.get(k)
    return (ASSETS_ROOT / sub) if sub else None

def bake_icon_paths(conn: sqlite3.Connection, *, only_missing: bool = True) -> Dict[str, int]:
    """
    Assign star/planet/moon/station/warp_gate/resource GIF paths into DB columns:
      - systems.star_icon_path
      - locations.icon_path

    Args:
        conn: open sqlite3 Connection (row_factory not required).
        only_missing: if True, do not overwrite non-null paths.

    Returns:
        Dict with counters of rows updated.
    """
    updated = {"systems": 0, "locations": 0}

    # Stars (systems table)
    cur = conn.cursor()
    systems = cur.execute("SELECT system_id, COALESCE(star_icon_path, '') FROM systems ORDER BY system_id;").fetchall()
    star_gifs = _list_gifs(_folder_for_kind("star") or ASSETS_ROOT / "stars")
    for sid, existing in systems:
        if only_missing and str(existing or "").strip():
            continue
        chosen = _choose_deterministic(9176 * int(sid) + 37, star_gifs)
        if chosen is None:
            continue
        cur.execute("UPDATE systems SET star_icon_path=? WHERE system_id=?;", (str(chosen), int(sid)))
        updated["systems"] += 1

    # Locations
    # Fetch locations and join resource_nodes for resource types
    rows = cur.execute("""
        SELECT l.location_id, l.system_id, l.location_type, l.icon_path, rn.resource_type
          FROM locations AS l
          LEFT JOIN resource_nodes AS rn ON rn.location_id = l.location_id
         ORDER BY l.system_id, l.location_type, l.location_id;
    """).fetchall()

    # Preload GIF lists per folder
    cache_files: Dict[str, List[Path]] = {}
    def _get_files_for_kind(kind: str, resource_type: Optional[str]) -> List[Path]:
        key = (resource_type or kind or "").lower()
        if resource_type:
            folder = _folder_for_resource(resource_type)
        else:
            folder = _folder_for_kind(kind)
        if folder is None:
            return []
        k = str(folder)
        if k not in cache_files:
            cache_files[k] = _list_gifs(folder)
        return cache_files[k]

    # For uniqueness per system/type, we stride choice by index within that bucket
    # Track counters per (system_id, bucket_key)
    per_bucket_idx: Dict[Tuple[int, str], int] = {}

    for loc_id, sys_id, loc_type, icon_path, rtype in rows:
        if only_missing and str(icon_path or "").strip():
            continue
        kind = _norm(loc_type)
        # Bucket key distinguishes resources by their specific resource_type
        bucket_key = f"{kind}:{_norm(rtype) if rtype else ''}"
        files = _get_files_for_kind(kind, rtype)
        if not files:
            continue

        # The n-th item in this (system, bucket) picks a deterministic offset, unique-ish
        idx = per_bucket_idx.get((int(sys_id), bucket_key), 0)
        seed = (77_000 + int(sys_id) * 13 + idx * 101)
        chosen = _choose_deterministic(seed, files)
        per_bucket_idx[(int(sys_id), bucket_key)] = idx + 1
        if chosen is None:
            continue
        cur.execute("UPDATE locations SET icon_path=? WHERE location_id=?;", (str(chosen), int(loc_id)))
        updated["locations"] += 1

    conn.commit()
    return updated
