from __future__ import annotations

from typing import Dict, Any, Optional

from data import db
from game import player_status


# --- Travel and Game Logic ---

def get_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculates Euclidean distance between two points."""
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def _calculate_travel_costs(target_location_id: int) -> Dict:
    """
    Internal helper to calculate core travel costs for action execution.
    """
    player = db.get_player_full()
    if not player: return {}

    current_sys_id = player.get("current_player_system_id")
    target_loc = db.get_location(target_location_id)
    if not target_loc: return {}

    target_sys_id = target_loc.get("system_id")
    if target_sys_id is None: return {}

    if current_sys_id == target_sys_id:
        return {"jump_dist": 0.0, "fuel_cost": 1}
    else:
        if current_sys_id is None: return {}
        current_system = db.get_system(current_sys_id)
        target_system = db.get_system(target_sys_id)
        if not current_system or not target_system: return {}
        dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
        fuel_cost = int(dist_ly * 10)
        return {"jump_dist": dist_ly, "fuel_cost": fuel_cost}


def get_travel_display_data(target_id: int, is_system_target: bool, current_view_system_id: Optional[int] = None) -> Dict:
    """
    Calculates detailed distance and feasibility information for UI display.
    """
    status = player_status.get_status_snapshot()
    player = db.get_player_full()
    if not player:
        return {}

    player_sys_id = player.get("current_player_system_id")
    player_loc_id = player.get("current_player_location_id")
    player_loc = db.get_location(player_loc_id) if player_loc_id else None

    player_dist_from_star_au = 0.0
    if player_loc and player_loc.get("system_id") == player_sys_id:
        player_dist_from_star_au = get_distance((0, 0), (player_loc["local_x_au"], player_loc["local_y_au"]))

    # --- GALAXY VIEW TARGET (A system) ---
    if is_system_target:
        if player_sys_id == target_id:
            return {
                "distance": "0.00 ly, 0.00 AU", "dist_ly": 0.0, "dist_au": 0.0,
                "jump_dist": 0.0, "fuel_cost": 0, "can_reach_jump": True, "can_reach_fuel": True, "can_reach": True,
            }

        target_sys = db.get_system(target_id)
        if not target_sys or player_sys_id is None: return {}
        player_sys = db.get_system(player_sys_id)
        if not player_sys: return {}
            
        dist_ly = get_distance((player_sys["x"], player_sys["y"]), (target_sys["x"], target_sys["y"]))
        fuel_cost = int(dist_ly * 10) if dist_ly > 0 else 0
        display_dist = f"{dist_ly:.2f} ly, {player_dist_from_star_au:.2f} AU"

        can_jump = status.get('current_jump_distance', 0) >= dist_ly
        can_fuel = status.get('fuel', 0) >= fuel_cost
        can_overall = (can_jump and can_fuel) if dist_ly > 0 else True

        return {
            "distance": display_dist, "dist_ly": dist_ly, "dist_au": player_dist_from_star_au,
            "jump_dist": dist_ly, "fuel_cost": fuel_cost, "can_reach_jump": can_jump,
            "can_reach_fuel": can_fuel, "can_reach": can_overall,
        }
        
    # --- SOLAR VIEW TARGET (A location) ---
    else:
        target_loc = db.get_location(target_id)
        if not target_loc or current_view_system_id is None: return {}
        target_sys_id = target_loc.get("system_id")
        
        # Case 1: Target is in the player's current system
        if player_sys_id == current_view_system_id:
            start_pos = (player_loc["local_x_au"], player_loc["local_y_au"]) if player_loc else (0.0, 0.0)
            target_pos = (target_loc["local_x_au"], target_loc["local_y_au"])
            dist_au = get_distance(start_pos, target_pos)
            fuel_cost = 1 if dist_au > 0 else 0
            can_fuel = status.get('fuel', 0) >= fuel_cost
            
            return {
                "distance": f"{dist_au:.2f} AU", "dist_ly": 0.0, "dist_au": dist_au,
                "jump_dist": 0.0, "fuel_cost": fuel_cost, "can_reach_jump": True,
                "can_reach_fuel": can_fuel, "can_reach": can_fuel,
            }
        # Case 2: Target is in a different system
        else:
            if player_sys_id is None or target_sys_id is None: return {}
            player_sys = db.get_system(player_sys_id)
            target_sys = db.get_system(target_sys_id)
            if not player_sys or not target_sys: return {}

            dist_ly = get_distance((player_sys["x"], player_sys["y"]), (target_sys["x"], target_sys["y"]))
            fuel_cost = int(dist_ly * 10)
            target_dist_from_star_au = get_distance((0,0), (target_loc["local_x_au"], target_loc["local_y_au"]))
            total_au = player_dist_from_star_au + target_dist_from_star_au
            display_dist = f"{dist_ly:.2f} ly, {total_au:.2f} AU"

            can_jump = status.get('current_jump_distance', 0) >= dist_ly
            can_fuel = status.get('fuel', 0) >= fuel_cost
            can_overall = can_jump and can_fuel

            return {
                "distance": display_dist, "dist_ly": dist_ly, "dist_au": total_au,
                "jump_dist": dist_ly, "fuel_cost": fuel_cost, "can_reach_jump": can_jump,
                "can_reach_fuel": can_fuel, "can_reach": can_overall,
            }

def travel_to_system_star(target_system_id: int) -> str:
    """Handles logic for traveling to the star of a given system."""
    player = db.get_player_full()
    if not player:
        return "Player data not found."

    current_sys_id = player.get("current_player_system_id")
    if current_sys_id == target_system_id:
        db.set_player_location(None)
        return "Traveled to the system's star."
    
    status = player_status.get_status_snapshot()
    if current_sys_id is None:
        return "Cannot jump: current system unknown."

    current_system = db.get_system(current_sys_id)
    target_system = db.get_system(target_system_id)
    if not current_system or not target_system:
        return "Could not find system data for jump calculation."

    jump_dist = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
    fuel_cost = int(jump_dist * 10)

    if status["current_jump_distance"] < jump_dist:
        return f"Cannot jump: jump range is {status['current_jump_distance']:.2f} ly, but {jump_dist:.2f} ly is required."
        
    if status["fuel"] < fuel_cost:
        return f"Cannot jump: not enough fuel. Requires {fuel_cost}, but only have {status['fuel']}."
    
    new_fuel = player["current_player_ship_fuel"] - fuel_cost
    conn = db.get_connection()
    conn.execute("UPDATE player SET current_player_system_id=?, current_player_location_id=NULL, current_player_ship_fuel=? WHERE id=1", (target_system_id, new_fuel))
    conn.commit()
    
    return f"Jumped to {target_system['name']}. Now orbiting the star."


def travel_to_location(location_id: int) -> str:
    """
    Handles the logic for traveling to a new location, including inter-system jumps.
    """
    player = db.get_player_full()
    if not player:
        return "Player data not found."
    
    status = player_status.get_status_snapshot()
    travel_info = _calculate_travel_costs(location_id)
    if not travel_info:
        return "Cannot calculate travel costs."

    jump_dist = travel_info.get("jump_dist", float('inf'))
    fuel_cost = travel_info.get("fuel_cost", float('inf'))

    if status["current_jump_distance"] < jump_dist:
        return f"Cannot jump: jump range is {status['current_jump_distance']:.2f} ly, but {jump_dist:.2f} ly is required."
        
    if status["fuel"] < fuel_cost:
        return f"Cannot jump: not enough fuel. Requires {fuel_cost}, but only have {status['fuel']}."
    
    target_loc = db.get_location(location_id)
    if not target_loc: return f"Location with ID {location_id} not found."

    current_sys_id = player.get("current_player_system_id")
    target_sys_id = target_loc.get("system_id")

    if current_sys_id == target_sys_id:
        db.set_player_location(location_id)
        return f"Traveled to {target_loc['name']}."
    else:
        if target_sys_id is None: return f"Target location has no valid system ID."
        target_system = db.get_system(target_sys_id)
        if not target_system: return f"System data for system ID {target_sys_id} not found."

        new_fuel = player["current_player_ship_fuel"] - fuel_cost
        conn = db.get_connection()
        conn.execute("UPDATE player SET current_player_system_id=?, current_player_location_id=?, current_player_ship_fuel=? WHERE id=1", (target_sys_id, location_id, new_fuel))
        conn.commit()
        
        return f"Jumped to {target_system['name']} and arrived at {target_loc['name']}."