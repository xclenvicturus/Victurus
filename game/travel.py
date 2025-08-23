from __future__ import annotations

from typing import Dict, Any, Optional, Tuple

from data import db
from game import player_status


# --- Travel and Game Logic ---

def get_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculates Euclidean distance between two points."""
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def get_absolute_au(loc_id: Optional[int]) -> Tuple[float, float]:
    if loc_id is None:
        return (0.0, 0.0)
    pos = (0.0, 0.0)
    current_id = loc_id
    while current_id is not None:
        loc = db.get_location(current_id)
        if loc is None:
            break
        pos = (pos[0] + loc.get("local_x_au", 0.0), pos[1] + loc.get("local_y_au", 0.0))
        current_id = loc.get("parent_location_id")
    return pos

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
                "jump_dist": 0.0, "fuel_cost": 0, "can_reach": True, "can_reach_jump": True, "can_reach_fuel": True
            }
        target_system = db.get_system(target_id)
        if not target_system: return {}
        current_system = db.get_system(player_sys_id) if player_sys_id else None
        if not current_system: return {}
        dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
        fuel_cost = int(dist_ly * 10)
        can_reach_jump = status["current_jump_distance"] >= dist_ly
        can_reach_fuel = status["fuel"] >= fuel_cost
        can_reach = can_reach_jump and can_reach_fuel
        return {
            "distance": f"{dist_ly:.2f} ly, {player_dist_from_star_au:.2f} AU", "dist_ly": dist_ly, "dist_au": player_dist_from_star_au,
            "jump_dist": dist_ly, "fuel_cost": fuel_cost, "can_reach": can_reach, "can_reach_jump": can_reach_jump, "can_reach_fuel": can_reach_fuel
        }

    # --- SOLAR VIEW TARGET (A location) ---
    else:
        target_loc = db.get_location(target_id)
        if not target_loc: return {}
        target_sys_id = target_loc.get("system_id")
        if target_sys_id is None: return {}
        if not current_view_system_id: current_view_system_id = player_sys_id
        if player_sys_id == current_view_system_id:
            # Same system: intra-system travel (AU only)
            player_pos = get_absolute_au(player_loc_id)
            target_pos = get_absolute_au(target_id)
            dist_au = get_distance(player_pos, target_pos)
            return {
                "distance": f"0.00 ly, {dist_au:.2f} AU", "dist_ly": 0.0, "dist_au": dist_au,
                "jump_dist": 0.0, "fuel_cost": 1, "can_reach": True, "can_reach_jump": True, "can_reach_fuel": status["fuel"] >= 1
            }
        else:
            # Different system: inter-system jump to location
            current_system = db.get_system(player_sys_id) if player_sys_id else None
            target_system = db.get_system(target_sys_id)
            if not current_system or not target_system: return {}
            dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
            fuel_cost = int(dist_ly * 10)
            target_pos = get_absolute_au(target_id)
            dist_au = get_distance((0.0, 0.0), target_pos)
            can_reach_jump = status["current_jump_distance"] >= dist_ly
            can_reach_fuel = status["fuel"] >= fuel_cost
            can_reach = can_reach_jump and can_reach_fuel
            return {
                "distance": f"{dist_ly:.2f} ly, {dist_au:.2f} AU", "dist_ly": dist_ly, "dist_au": dist_au,
                "jump_dist": dist_ly, "fuel_cost": fuel_cost, "can_reach": can_reach, "can_reach_jump": can_reach_jump, "can_reach_fuel": can_reach_fuel
            }

def travel_to_system(target_system_id: int) -> str:
    """
    Handles the logic for jumping to a new system.
    """
    player = db.get_player_full()
    if not player:
        return "Player data not found."
    status = player_status.get_status_snapshot()
    current_sys_id = player.get("current_player_system_id")
    if current_sys_id == target_system_id:
        return "Already in this system."
    target_system = db.get_system(target_system_id)
    if not target_system: return f"System with ID {target_system_id} not found."
    current_system = db.get_system(current_sys_id) if current_sys_id else None
    if not current_system: return "Current system data not found."
    dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
    fuel_cost = int(dist_ly * 10)
    if status["current_jump_distance"] < dist_ly:
        return f"Cannot jump: jump range is {status['current_jump_distance']:.2f} ly, but {dist_ly:.2f} ly is required."
    
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