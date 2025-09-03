# /game/travel.py

"""
Travel System

Handles player movement between systems and locations, including travel time calculations,
fuel consumption, and travel state management.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple, cast
import math

from data import db
from game import player_status
from settings import system_config as cfg

# ------------------------------------------------------------------
# Shared fuel model (single source of truth for display + flow)
# Read from central config with safe fallbacks
# ------------------------------------------------------------------
try:
    FUEL_PER_AU = float(getattr(cfg, "TRAVEL_FUEL_PER_AU", 1.0 / 5.0))
except Exception:
    FUEL_PER_AU = 1.0 / 5.0
try:
    WARP_FUEL_PER_LY = float(getattr(cfg, "TRAVEL_WARP_FUEL_PER_LY", 2.0))
except Exception:
    WARP_FUEL_PER_LY = 2.0
try:
    WARP_FUEL_WEIGHT = float(getattr(cfg, "TRAVEL_WARP_FUEL_WEIGHT", 1.40))
except Exception:
    WARP_FUEL_WEIGHT = 1.40

# ---------------------------
# Safe helpers
# ---------------------------

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)  # type: ignore[call-arg]
    except Exception:
        return default


def _norm_kind(value: Optional[str]) -> str:
    """
    Normalize various kind/location_type aliases used by DB/UI into a compact set.
    Now includes 'moon' to support the new moon locations.
    """
    v = (value or "").strip().lower()
    aliases = {
        "location_type": {
            "star": "star", "sun": "star",
            "planet": "planet", "world": "planet",
            "station": "station", "outpost": "station", "dock": "station",
            "warp gate": "warpgate", "warp_gate": "warpgate", "gate": "warpgate",
            "moon": "moon",
        },
        "kind": {
            "star": "star", "planet": "planet", "station": "station",
            "warp gate": "warpgate", "warpgate": "warpgate", "gate": "warpgate",
            "moon": "moon",
        },
    }
    if v in ("star", "planet", "station", "warpgate", "moon"):
        return v
    if v in aliases["location_type"]:
        return aliases["location_type"][v]
    if v in aliases["kind"]:
        return aliases["kind"][v]
    return v


def _loc_kind(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return ""
    return _norm_kind(
        cast(Optional[str], row.get("kind") or row.get("location_type") or row.get("category"))
    )


def _loc_name(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return "Unknown"
    return cast(str, row.get("name") or row.get("location_name") or row.get("label") or f"Loc {row.get('id')}")


def _sys_name(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return "Unknown System"
    return cast(str, row.get("name") or row.get("system_name") or f"Sys {row.get('system_id') or row.get('id')}")


def _sys_xy(system_row: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    if not system_row:
        return (0.0, 0.0)
    # Expect x,y in galaxy (pc/ly) coordinates; db.py aliases expose x/y
    x = float(system_row.get("x") or 0.0)
    y = float(system_row.get("y") or 0.0)
    return (x, y)


def _loc_xy_au(loc_row: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    """
    AU-space coordinates inside a system.

    db.get_location / db.get_warp_gate expose 'local_x_au' / 'local_y_au' aliases.
    Fall back to raw 'location_x' / 'location_y', then legacy keys.
    """
    if not loc_row:
        return (0.0, 0.0)
    x = float(
        loc_row.get("local_x_au")
        or loc_row.get("location_x")
        or loc_row.get("x")
        or loc_row.get("ax")
        or loc_row.get("au_x")
        or 0.0
    )
    y = float(
        loc_row.get("local_y_au")
        or loc_row.get("location_y")
        or loc_row.get("y")
        or loc_row.get("ay")
        or loc_row.get("au_y")
        or 0.0
    )
    return (x, y)


def _dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    dx = (p1[0] - p2[0])
    dy = (p1[1] - p2[1])
    return math.hypot(dx, dy)


# ------------------------------------------------------------------
# Unified fuel estimator used by both display and flow
# ------------------------------------------------------------------
def estimate_total_fuel(dist_ly: float, intra_current_au: float, intra_target_au: float, same_system: bool) -> float:
    """
    Compute the total fuel that TravelFlow will drip for the planned route
    using the exact same model constants.

    - Cruise (AU): continuous, FUEL_PER_AU * AU
    - Warp (LY):   WARP_FUEL_PER_LY * LY * WARP_FUEL_WEIGHT (overhead factor)
    """
    au_total = (intra_current_au + intra_target_au) if not same_system else intra_current_au  # same_system path passes dist_au in 'intra_current_au'
    intra_total = FUEL_PER_AU * max(0.0, float(au_total))
    warp_total = (WARP_FUEL_PER_LY * max(0.0, float(dist_ly)) * WARP_FUEL_WEIGHT)
    return intra_total + warp_total


# ---------------------------
# Route planning / display data
# ---------------------------

def get_travel_display_data(kind: str, ident: int) -> Dict[str, Any]:
    """
    Return a dict describing the route and distances needed for UI/flow sequencing.

    Keys:
      ok: bool
      same_system: bool
      source_kind: 'station'|'planet'|'moon'|'star'|'warpgate'|''  (where the player is parked, if any)
      target_kind: same set as above
      dist_au: float (only for intra-system routes)
      dist_ly: float (for inter-system routes; measured between system centers/gates)
      intra_current_au: float (player -> source system's warp gate)
      intra_target_au: float (dest system's warp gate -> target)
      target_system_id: int
      target_location_id: Optional[int]

      # UI helpers
      distance: str           # "<ly> ly, <au> AU"
      jump_dist: float        # same as dist_ly (info column)
      fuel_cost: int          # unified model (ceil of total drip)
      can_reach: bool
      can_reach_jump: bool    # jump-range constraint
      can_reach_fuel: bool    # fuel constraint
    """
    player = cast(Dict[str, Any], db.get_player_full() or {})
    cur_sys_id = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)
    cur_loc_id_raw = player.get("current_player_location_id") or player.get("location_id")
    cur_loc_id = _safe_int(cur_loc_id_raw, 0) or None

    target_loc: Optional[Dict[str, Any]] = None
    target_sys: Optional[Dict[str, Any]] = None

    if kind == "loc":
        target_loc = cast(Optional[Dict[str, Any]], db.get_location(int(ident)))
        if not target_loc:
            return {"ok": False}
        target_sys_id = _safe_int(target_loc.get("system_id"), 0)
        target_sys = cast(Optional[Dict[str, Any]], db.get_system(target_sys_id))
        if not target_sys:
            return {"ok": False}
    elif kind == "star":
        target_sys = cast(Optional[Dict[str, Any]], db.get_system(int(ident)))
        if not target_sys:
            return {"ok": False}
        target_sys_id = _safe_int(target_sys.get("system_id") or target_sys.get("id"), 0)
    else:
        return {"ok": False}

    same_system = (cur_sys_id == _safe_int(target_sys.get("system_id") or target_sys.get("id"), 0))

    # Source info (for depart wrapper)
    source_kind = ""
    if cur_loc_id is not None:
        src_loc = cast(Optional[Dict[str, Any]], db.get_location(cur_loc_id))
        source_kind = _loc_kind(src_loc)
    elif cur_sys_id:
        source_kind = "star"

    # Target kind (now includes 'moon')
    target_kind = _loc_kind(target_loc) if target_loc else "star"

    out: Dict[str, Any] = {
        "ok": True,
        "same_system": bool(same_system),
        "source_kind": source_kind,
        "target_kind": target_kind,
        "target_system_id": _safe_int(target_sys.get("system_id") or target_sys.get("id"), 0),
        "target_location_id": _safe_int(target_loc.get("location_id") or target_loc.get("id"), 0) if target_loc else None,
    }

    # Player status for reachability
    try:
        status = player_status.get_status_snapshot()
        player_fuel = float(status.get("fuel", 0))
        # Status may expose 'current_jump_distance' (preferred) or just base.
        jump_range_ly = float(status.get("current_jump_distance", status.get("base_jump_distance", 0.0)) or 0.0)
    except Exception:
        player_fuel = 0.0
        jump_range_ly = 0.0

    if same_system:
        # pure intra-system leg (planet <-> moon <-> station <-> star)
        target_xy = _loc_xy_au(target_loc) if target_loc else (0.0, 0.0)
        cur_xy = (0.0, 0.0)
        if cur_loc_id is not None:
            cur_loc = cast(Optional[Dict[str, Any]], db.get_location(cur_loc_id))
            cur_xy = _loc_xy_au(cur_loc)
        dist_au = float(_dist(cur_xy, target_xy))
        dist_ly = 0.0

        # unified fuel estimate (pass AU in intra_current_au; intra_target_au=0)
        total_fuel = estimate_total_fuel(dist_ly=0.0, intra_current_au=dist_au, intra_target_au=0.0, same_system=True)
        fuel_cost = int(math.ceil(total_fuel))

        can_reach_jump = True
        can_reach_fuel = (player_fuel >= fuel_cost)
        can_reach = can_reach_jump and can_reach_fuel

        out.update({
            "dist_au": dist_au,
            "dist_ly": dist_ly,
            "intra_current_au": 0.0,
            "intra_target_au": 0.0,
            "fuel_cost": fuel_cost,
            "jump_dist": dist_ly,
            "distance": f"{dist_ly:.2f} ly, {dist_au:.2f} AU",
            "can_reach": can_reach,
            "can_reach_jump": can_reach_jump,
            "can_reach_fuel": can_reach_fuel,
        })
        return out

    # Inter-system: galaxy ly distance + two in-system AU legs
    src_sys = cast(Optional[Dict[str, Any]], db.get_system(cur_sys_id))
    src_xy_ly = _sys_xy(src_sys)
    dst_xy_ly = _sys_xy(target_sys)
    dist_ly = float(_dist(src_xy_ly, dst_xy_ly))

    # AU leg from player to source gate
    source_gate = cast(Optional[Dict[str, Any]], db.get_warp_gate(cur_sys_id))
    gate_xy = _loc_xy_au(source_gate)

    cur_xy = (0.0, 0.0)
    if cur_loc_id is not None:
        cur_loc = cast(Optional[Dict[str, Any]], db.get_location(cur_loc_id))
        cur_xy = _loc_xy_au(cur_loc)
    intra_current_au = float(_dist(cur_xy, gate_xy))

    # AU leg from destination gate to target
    dest_gate = cast(Optional[Dict[str, Any]], db.get_warp_gate(_safe_int(out["target_system_id"], 0)))
    dest_gate_xy = _loc_xy_au(dest_gate)

    target_xy = _loc_xy_au(target_loc) if target_loc else (0.0, 0.0)  # star center if None
    intra_target_au = float(_dist(dest_gate_xy, target_xy))

    # Unified total fuel (exact same model as TravelFlow)
    total_fuel = estimate_total_fuel(dist_ly, intra_current_au, intra_target_au, same_system=False)
    fuel_cost = int(math.ceil(total_fuel))
    total_au = intra_current_au + intra_target_au

    # Reachability checks
    can_reach_jump = (jump_range_ly >= dist_ly)  # jump range must cover ly distance
    can_reach_fuel = (player_fuel >= float(fuel_cost))
    can_reach = can_reach_jump and can_reach_fuel

    out.update({
        "dist_ly": dist_ly,
        "dist_au": 0.0,
        "intra_current_au": intra_current_au,
        "intra_target_au": intra_target_au,
        "fuel_cost": fuel_cost,
        "jump_dist": dist_ly,
        "distance": f"{dist_ly:.2f} ly, {total_au:.2f} AU",
        "can_reach": can_reach,
        "can_reach_jump": can_reach_jump,
        "can_reach_fuel": can_reach_fuel,
    })
    return out


# ---------------------------
# Fuel mutation helpers (used by TravelFlow)
# ---------------------------

def get_player_fuel() -> Tuple[float, float]:
    """
    Returns (fuel, fuel_max) as floats.
    """
    player = cast(Dict[str, Any], db.get_player_full() or {})
    try:
        fuel = float(player.get("current_player_ship_fuel") or 0.0)
    except Exception:
        fuel = 0.0
    ship = cast(Dict[str, Any], db.get_player_ship() or {})
    try:
        fuel_max = float(ship.get("base_ship_fuel") or 1.0)
    except Exception:
        fuel_max = 1.0
    return fuel, fuel_max


def consume_fuel(amount: float) -> float:
    """
    Subtracts up to `amount` fuel from the player's ship. Returns the actual amount consumed.
    Uses float precision and clamps at zero.
    """
    amt = float(max(0.0, amount))
    if amt <= 0.0:
        return 0.0

    fuel, _ = get_player_fuel()
    take = min(fuel, amt)

    if take <= 0.0:
        return 0.0

    new_val = float(max(0.0, fuel - take))
    conn = db.get_connection()
    conn.execute("UPDATE player SET current_player_ship_fuel=? WHERE id=1", (new_val,))
    conn.commit()
    return take


# ---------------------------
# Apply travel to the DB
# ---------------------------

def perform_travel(kind: str, ident: int) -> str:
    """
    Actually move the player in the DB to the destination (system or location).
    Called by TravelFlow once transit is complete, before arrival wrappers.
    NOTE: Fuel is now deducted progressively by TravelFlow; do not subtract here.
    Returns a short log message.
    """
    player = cast(Dict[str, Any], db.get_player_full() or {})
    _ = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)

    if kind == "loc":
        dest_loc = cast(Optional[Dict[str, Any]], db.get_location(int(ident)))
        if not dest_loc:
            return "Destination not found."
        dest_sys_id = _safe_int(dest_loc.get("system_id"), 0)
        dest_loc_id = _safe_int(dest_loc.get("location_id") or dest_loc.get("id"), 0)
        
        # Always enter orbit around the destination, never dock directly
        conn = db.get_connection()
        try:
            # Try to use the new location status field
            conn.execute(
                "UPDATE player SET current_player_system_id=?, current_player_location_id=?, current_location_status='orbiting' WHERE id=1",
                (dest_sys_id, dest_loc_id),
            )
        except Exception:
            # Fallback for databases without the new column
            conn.execute(
                "UPDATE player SET current_player_system_id=?, current_player_location_id=? WHERE id=1",
                (dest_sys_id, dest_loc_id),
            )
        conn.commit()
        
        sys_row = cast(Optional[Dict[str, Any]], db.get_system(dest_sys_id))
        return f"Arrived in {_sys_name(sys_row)}, now orbiting {_loc_name(dest_loc)}."
    elif kind == "star":
        dest_sys = cast(Optional[Dict[str, Any]], db.get_system(int(ident)))
        if not dest_sys:
            return "Destination system not found."
        dest_sys_id = _safe_int(dest_sys.get("system_id") or dest_sys.get("id"), 0)
        conn = db.get_connection()
        try:
            # Try to use the new location status field
            conn.execute(
                "UPDATE player SET current_player_system_id=?, current_player_location_id=NULL, current_location_status='orbiting' WHERE id=1",
                (dest_sys_id,),
            )
        except Exception:
            # Fallback for databases without the new column
            conn.execute(
                "UPDATE player SET current_player_system_id=?, current_player_location_id=NULL WHERE id=1",
                (dest_sys_id,),
            )
        conn.commit()
        return f"Arrived in {_sys_name(dest_sys)}, orbiting the star."
    else:
        return "Unsupported travel target."
