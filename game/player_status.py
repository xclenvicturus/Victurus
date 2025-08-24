# /game/player_status.py

from __future__ import annotations

from typing import Dict, Any, Optional, cast

from data import db
from game import ship_state

# In-memory UI hints controlled by travel_flow
_TRANSIENT_LOCATION: Optional[str] = None
# Optional local fallback if ship_state module doesn't provide setters
_LOCAL_TEMP_STATE: Optional[str] = None


# ---------- Helpers ----------

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


def _get_temp_state() -> Optional[str]:
    """Read temporary state from ship_state if available, else our local fallback."""
    try:
        temp = ship_state.get_temporary_state()
        if temp is not None:
            return str(temp)
    except Exception:
        pass
    return _LOCAL_TEMP_STATE


# ---------- Public setters used by travel/travel_flow ----------

def set_ship_state(state: Optional[str]) -> None:
    """
    Set a temporary ship phase (e.g., 'Entering Cruise', 'Warping', 'Docking', ...).
    travel_flow calls this at each phase boundary.
    """
    global _LOCAL_TEMP_STATE
    try:
        # Prefer the canonical module if it exposes a setter
        setter = getattr(ship_state, "set_temporary_state", None)
        if callable(setter):
            setter(state)
        else:
            _LOCAL_TEMP_STATE = state
    except Exception:
        _LOCAL_TEMP_STATE = state


def set_transient_location(label: Optional[str]) -> None:
    """
    While cruising/warping, override the default location label:
      - cruising: <System Name>
      - warping:  The Warp
    travel_flow calls this as each phase starts.
    """
    global _TRANSIENT_LOCATION
    _TRANSIENT_LOCATION = str(label) if label else None


def clear_transient_location() -> None:
    """Clear any phase-based location override (e.g., upon arrival)."""
    set_transient_location(None)


def adjust_fuel(delta: float) -> None:
    """
    Add 'delta' (can be negative) to current fuel; clamp to [0, fuel_max];
    write back to DB as a float. Used each tick by travel_flow for smooth drip.
    """
    try:
        player = cast(Dict[str, Any], db.get_player_full() or {})
        ship = cast(Dict[str, Any], db.get_player_ship() or {})

        cur = float(player.get("current_player_ship_fuel") or 0.0)
        fmax = float(ship.get("base_ship_fuel") or 0.0)
        new_val = cur + float(delta)
        if fmax <= 0:
            new_val = 0.0
        else:
            if new_val < 0.0:
                new_val = 0.0
            elif new_val > fmax:
                new_val = fmax

        con = db.get_connection()
        con.execute(
            "UPDATE player SET current_player_ship_fuel=? WHERE id=1",
            (new_val,),
        )
        con.commit()
    except Exception:
        # Never let UI drips crash the app
        pass


# ---------- Status getters ----------

def get_ship_status(player: Dict[str, Any]) -> str:
    """
    Return any active temporary phase first (e.g., 'Docking', 'Warping', ...),
    otherwise fall back to a stable status inferred from the DB.
    """
    temp = _get_temp_state()
    if temp:
        return str(temp)
    return _stable_status(player)


def get_status_snapshot() -> Dict[str, Any]:
    """
    Collect a UI-friendly snapshot of player + ship status.
    Numeric fields are numbers; labels are friendly fallbacks.
    """
    player = cast(Dict[str, Any], db.get_player_full() or {})
    ship = cast(Dict[str, Any], db.get_player_ship() or {})

    # --- IDs ---
    sys_id = player.get("current_player_system_id") or player.get("system_id")
    loc_id = player.get("current_player_location_id") or player.get("location_id")

    sys_row = cast(Optional[Dict[str, Any]], db.get_system(int(sys_id)) if sys_id else None)
    loc_row = cast(Optional[Dict[str, Any]], db.get_location(int(loc_id)) if loc_id else None)

    system_name = (sys_row.get("name") if sys_row else None) or "—"

    # Default display location from DB
    if loc_row:
        display_location = (loc_row.get("name") or loc_row.get("location_name") or "—")
    else:
        display_location = f"{system_name} (Star)" if system_name != "—" else "—"

    # Transient override from travel_flow (preferred over parsing temp strings)
    if _TRANSIENT_LOCATION:
        display_location = _TRANSIENT_LOCATION
    else:
        # Back-compat: if no explicit transient, infer from temporary phase name
        temp = _get_temp_state() or ""
        tl = temp.lower()
        if any(k in tl for k in ("entering cruise", "cruising", "leaving cruise")):
            display_location = f"{system_name}" if system_name != "—" else "Cruise"
        elif "warping" in tl or "warp" in tl:
            display_location = "The Warp"

    # Credits (numeric)
    credits_raw = player.get("credits") or player.get("current_wallet_credits") or 0
    try:
        credits = int(credits_raw)
    except Exception:
        try:
            credits = int(float(str(credits_raw)))
        except Exception:
            credits = 0

    # Basic ship stats (coerced)
    try:
        hull = int(player.get("current_player_ship_hull") or 0)
    except Exception:
        hull = 0
    try:
        hull_max = int(ship.get("base_ship_hull") or 1)
    except Exception:
        hull_max = 1

    try:
        shield = int(player.get("current_player_ship_shield") or 0)
    except Exception:
        shield = 0
    try:
        shield_max = int(ship.get("base_ship_shield") or 1)
    except Exception:
        shield_max = 1

    # Fuel/energy as floats (gauges show decimals smoothly)
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

    try:
        cargo = int(player.get("current_player_ship_cargo") or 0)
    except Exception:
        cargo = 0
    try:
        cargo_max = int(ship.get("base_ship_cargo") or 1)
    except Exception:
        cargo_max = 1

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

        # jump distances (return both keys for UI/back-compat)
        "base_jump_distance": base_jump,
        "jump_distance": current_jump,
        "current_jump_distance": current_jump,

        # labels
        "player_name": player.get("player_name") or player.get("name"),
        "ship_name": ship.get("ship_name") or ship.get("name"),
        "system_name": system_name,
        "location_name": display_location,
    }
