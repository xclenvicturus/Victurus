# game/player_status.py
from __future__ import annotations

from typing import Dict, Any, Optional, cast

from data import db
from game import ship_state


def _stable_status(player: Dict[str, Any]) -> str:
    """
    Derive a stable ship status from the DB when no temporary UI state is active.
    - If at a station location -> "Docked"
    - If at any other location or in a system without a location -> "Orbiting"
    - Otherwise -> "Traveling"
    """
    if not player:
        return "Unknown"

    loc_id = player.get("current_player_location_id") or player.get("location_id")
    sys_id = player.get("current_player_system_id") or player.get("system_id")

    if loc_id:
        try:
            loc = cast(Optional[Dict[str, Any]], db.get_location(int(loc_id)))
        except Exception:
            loc = None
        kind = (loc.get("kind") or loc.get("location_type") or "").lower() if loc else ""
        if kind == "station":
            return "Docked"
        return "Orbiting"

    if sys_id:
        return "Orbiting"

    return "Traveling"


def get_ship_status(player: Dict[str, Any]) -> str:
    """
    Returns any active temporary phase first (e.g., 'Docking', 'Warping', ...),
    otherwise falls back to a stable status inferred from the DB.
    """
    temp = ship_state.get_temporary_state()
    if temp:
        return str(temp)
    return _stable_status(player)


def get_status_snapshot() -> Dict[str, Any]:
    """
    Collects a UI-friendly snapshot of player + ship status.
    All numeric fields are guaranteed to be numbers (not strings),
    and location/system names are always filled with a friendly fallback.
    """
    player = cast(Dict[str, Any], db.get_player_full() or {})
    ship = cast(Dict[str, Any], db.get_player_ship() or {})

    # --- IDs ---
    sys_id = player.get("current_player_system_id") or player.get("system_id")
    loc_id = player.get("current_player_location_id") or player.get("location_id")

    sys_row = cast(Optional[Dict[str, Any]], db.get_system(int(sys_id)) if sys_id else None)
    loc_row = cast(Optional[Dict[str, Any]], db.get_location(int(loc_id)) if loc_id else None)

    system_name = (sys_row.get("name") if sys_row else None) or "—"
    if loc_row:
        # db layer already aliases location_name -> name, location_type -> kind where possible
        display_location = (loc_row.get("name") or loc_row.get("location_name") or "—")
    else:
        # Not parked at a location → treat as being at the star within the system
        display_location = f"{system_name} (Star)" if system_name != "—" else "—"

    # Credits (ensure numeric) — read from DB column 'current_wallet_credits'
    credits_raw = (
        player.get("credits")
        or player.get("current_wallet_credits")
        or 0
    )
    try:
        credits = int(credits_raw)
    except Exception:
        try:
            credits = int(float(str(credits_raw)))
        except Exception:
            credits = 0

    # Basic ship stats (coerced)
    hull = int(player.get("current_player_ship_hull") or 0)
    hull_max = int(ship.get("base_ship_hull") or 1)

    shield = int(player.get("current_player_ship_shield") or 0)
    shield_max = int(ship.get("base_ship_shield") or 1)

    # Fuel/energy as floats
    try:
        fuel = float(player.get("current_player_ship_fuel") or 0.0)
    except Exception:
        fuel = 0.0
    try:
        fuel_max = float(ship.get("base_ship_fuel") or 1.0)
    except Exception:
        fuel_max = 1.0

    try:
        energy = float(player.get("current_player_ship_energy") or 0.0)
    except Exception:
        energy = 0.0
    try:
        energy_max = float(ship.get("base_ship_energy") or 1.0)
    except Exception:
        energy_max = 1.0

    cargo = int(player.get("current_player_ship_cargo") or 0)
    cargo_max = int(ship.get("base_ship_cargo") or 1)

    # Jump distances (derived current based on fuel fraction)
    try:
        base_jump = float(ship.get("base_ship_jump_distance") or 0.0)
    except Exception:
        base_jump = 0.0
    fuel_frac = (fuel / fuel_max) if fuel_max > 0 else 0.0
    current_jump = base_jump * fuel_frac

    return {
        # high-level state
        "ship_state": get_ship_status(player),

        # ship resources
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

        # economy
        "credits": credits,

        # jump distances
        "base_jump_distance": base_jump,
        "current_jump_distance": current_jump,

        # labels (now always have a friendly Location)
        "player_name": player.get("player_name") or player.get("name"),
        "ship_name": ship.get("ship_name") or ship.get("name"),
        "system_name": system_name,
        "location_name": display_location,
    }
