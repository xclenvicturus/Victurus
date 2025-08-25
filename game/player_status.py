# /game/player_status.py

from __future__ import annotations

from typing import Dict, Any, Optional, cast, Iterable

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


def _first_nonempty_str(d: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    """Return the first non-empty string value found in d[keys[i]]."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _first_numeric(d: Dict[str, Any], keys: Iterable[str]) -> Optional[float]:
    """Return the first value convertible to float from d[key] (None if not found)."""
    for k in keys:
        if k not in d:
            continue
        v = d.get(k)
        # Skip explicit None to avoid passing None to float() (fixes type-checker error)
        if v is None:
            continue
        try:
            # Accept ints, floats, numeric strings
            return float(v)
        except Exception:
            try:
                # Try str() fallback (e.g., Decimal, numpy, etc.)
                return float(str(v))
            except Exception:
                continue
    return None


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


def clear_temporary_state() -> None:
    """
    Clear any temporary ship state override (moved here from game.ship_state).
    Keeping this in player_status gives the UI one surface for transient phases.
    """
    set_ship_state(None)


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

    Keys provided (not exhaustive):
      - player_name: string (derived from common player-name fields)
      - ship_name:   string (from ships.name/ship_name)
      - current_jump_distance: float (best available, in ly)
      - system_id, location_id
      - system_name, display_location
      - status
      - credits (int)
      - hull/hull_max, shield/shield_max
      - fuel/fuel_max, energy/energy_max
      - cargo/cargo_max
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

    # ---- Names ----
    player_name = _first_nonempty_str(
        player,
        [
            "player_name",
            "commander",
            "commander_name",
            "name",
            "player",
            "current_commander_name",
            "current_player_name",
        ],
    ) or "—"

    # db.get_player_ship() aliases ship_name AS name; keep fallbacks too
    ship_name = _first_nonempty_str(
        ship,
        [
            "name",
            "ship_name",
            "current_player_ship_name",
        ],
    ) or "—"

    # ---- Jump range (ly): populate `current_jump_distance` if any known field exists ----
    # Try likely player fields first (runtime/current values), then ship/base fields.
    jump_player = _first_numeric(
        player,
        (
            "current_jump_distance",
            "jump_distance",
            "current_player_jump_distance",
            "current_player_ship_jump_distance",
        ),
    )
    jump_ship = _first_numeric(
        ship,
        (
            "jump_range_ly",
            "jump_distance_ly",
            "base_ship_jump_distance",
            "base_jump_distance",
            "max_jump_ly",
        ),
    )
    current_jump_distance = jump_player if jump_player is not None else (jump_ship if jump_ship is not None else 0.0)

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
    def _int(x, default=0):
        try:
            return int(x)
        except Exception:
            return default

    def _float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    hull      = _int(player.get("current_player_ship_hull"))
    hull_max  = _int(ship.get("base_ship_hull"), 1)
    shield    = _int(player.get("current_player_ship_shield"))
    shield_max= _int(ship.get("base_ship_shield"), 1)
    fuel      = _float(player.get("current_player_ship_fuel"))
    fuel_max  = _float(ship.get("base_ship_fuel"), 1.0)
    energy    = _float(player.get("current_player_ship_energy"))
    energy_max= _float(ship.get("base_ship_energy"), 1.0)
    cargo     = _int(player.get("current_player_ship_cargo"))
    cargo_max = _int(ship.get("base_ship_cargo"), 1)

    return {
        # IDs & names
        "system_id": sys_id,
        "location_id": loc_id,
        "system_name": system_name,
        "display_location": display_location,
        "player_name": player_name,
        "ship_name": ship_name,

        # Status & resources
        "status": get_ship_status(player),
        "credits": credits,
        "hull": hull, "hull_max": hull_max,
        "shield": shield, "shield_max": shield_max,
        "fuel": fuel, "fuel_max": fuel_max,
        "energy": energy, "energy_max": energy_max,
        "cargo": cargo, "cargo_max": cargo_max,

        # Jump range (as displayed by StatusSheet)
        "current_jump_distance": current_jump_distance,
    }
