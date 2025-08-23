from __future__ import annotations

from typing import Dict, Any

from data import db
from game import ship_state

def get_ship_status(player: Dict) -> str:
    """Determines the player's ship status based on their location."""
    # First, check if there is a temporary visual state active
    temp_state = ship_state.get_temporary_state()
    if temp_state:
        return temp_state

    # Otherwise, determine the actual state from the database
    if not player:
        return "Unknown"
    
    location_id = player.get("current_player_location_id")
    if location_id:
        location = db.get_location(location_id)
        if location:
            kind = (location.get("kind") or location.get("location_type") or "").lower()
            if kind == "station":
                return "Docked"
            # If at any other known location type (planet, etc.), the status is Orbiting.
            return "Orbiting"
    
    # Only if location_id is NULL do we check the system_id for orbiting a star
    if player.get("current_player_system_id"):
        return "Orbiting" 
        
    return "Traveling"

def get_status_snapshot() -> Dict[str, Any]:
    """Gathers a comprehensive snapshot of the player's current status."""
    player = db.get_player_full() or {}
    ship = db.get_player_ship() or {}
    system_id = player.get("current_player_system_id")
    system = db.get_system(system_id) if system_id else None
    location_id = player.get("current_player_location_id")
    location = db.get_location(location_id) if location_id else None

    # Determine location name for display
    display_location_name = "—"
    if location:
        display_location_name = location.get("name", "—")
    elif system: # If no location but in a system, player is at the star
        display_location_name = f"{system.get('name')} (Star)"

    fuel_frac = player.get("current_player_ship_fuel", 0) / ship.get("base_ship_fuel", 1) if ship.get("base_ship_fuel") else 0
    
    return {
        "player_name": player.get("name", "—"),
        "credits": player.get("current_wallet_credits", 0),
        "system_name": system.get("name", "—") if system else "—",
        "location_name": display_location_name,
        "ship_name": ship.get("name", "—"),
        "ship_state": get_ship_status(player),
        "hull": player.get("current_player_ship_hull", 0),
        "hull_max": ship.get("base_ship_hull", 1),
        "shield": player.get("current_player_ship_shield", 0),
        "shield_max": ship.get("base_ship_shield", 1),
        "fuel": player.get("current_player_ship_fuel", 0),
        "fuel_max": ship.get("base_ship_fuel", 1),
        "energy": player.get("current_player_ship_energy", 0),
        "energy_max": ship.get("base_ship_energy", 1),
        "cargo": player.get("current_player_ship_cargo", 0),
        "cargo_max": ship.get("base_ship_cargo", 1),
        "base_jump_distance": ship.get("base_ship_jump_distance", 0.0),
        "current_jump_distance": ship.get("base_ship_jump_distance", 0.0) * fuel_frac
    }
