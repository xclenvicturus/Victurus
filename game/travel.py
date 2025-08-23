from __future__ import annotations

from typing import Dict, Any, Optional, Tuple

from data import db
from game import player_status
import math


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

def _intra_fuel_cost(au: float) -> int:
    return max(1, math.ceil(au / 5.0))

def _get_travel_costs(target_sys_id: int, target_pos_au: Tuple[float, float]) -> Dict:
    player = db.get_player_full()
    if not player: return {}

    player_sys_id = player.get("current_player_system_id")
    if player_sys_id is None: return {}
    player_pos_au = get_absolute_au(player.get("current_player_location_id"))

    if player_sys_id == target_sys_id:
        dist_au = get_distance(player_pos_au, target_pos_au)
        return {"jump_dist": 0.0, "fuel_cost": _intra_fuel_cost(dist_au)}

    current_gate = db.get_warp_gate(player_sys_id)
    if not current_gate: return {}
    current_gate_pos = get_absolute_au(current_gate.get("id"))
    intra_current_au = get_distance(player_pos_au, current_gate_pos)
    intra_current_fuel = _intra_fuel_cost(intra_current_au)

    target_gate = db.get_warp_gate(target_sys_id)
    if not target_gate: return {}
    target_gate_pos = get_absolute_au(target_gate.get("id"))
    intra_target_au = get_distance(target_gate_pos, target_pos_au)
    intra_target_fuel = _intra_fuel_cost(intra_target_au)

    current_system = db.get_system(player_sys_id)
    if not current_system: return {}
    target_system = db.get_system(target_sys_id)
    if not target_system: return {}
    dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))
    inter_fuel = int(dist_ly * 10)

    total_fuel = intra_current_fuel + inter_fuel + intra_target_fuel
    return {"jump_dist": dist_ly, "fuel_cost": total_fuel}

def _calculate_travel_costs(target_location_id: int) -> Dict:
    """
    Internal helper to calculate core travel costs for action execution.
    """
    target_loc = db.get_location(target_location_id)
    if not target_loc: return {}
    target_sys_id = target_loc.get("system_id")
    if target_sys_id is None: return {}
    target_pos_au = get_absolute_au(target_location_id)
    return _get_travel_costs(target_sys_id, target_pos_au)


def get_travel_display_data(target_id: int, is_system_target: bool, current_view_system_id: Optional[int] = None) -> Dict:
    """
    Calculates detailed distance and feasibility information for UI display.
    """
    status = player_status.get_status_snapshot()
    player = db.get_player_full()
    if not player:
        return {}

    player_sys_id = player.get("current_player_system_id")
    if player_sys_id is None:
        return {}
    player_pos_au = get_absolute_au(player.get("current_player_location_id"))

    # Determine target_sys_id and target_pos_au
    if is_system_target:
        target_sys_id = target_id
        target_pos_au = (0.0, 0.0)
    else:
        target_loc = db.get_location(target_id)
        if not target_loc: return {}
        target_sys_id = target_loc.get("system_id")
        if target_sys_id is None: return {}
        target_pos_au = get_absolute_au(target_id)

    if current_view_system_id is None:
        current_view_system_id = target_sys_id

    if player_sys_id == current_view_system_id:
        # Same system
        dist_au = get_distance(player_pos_au, target_pos_au)
        dist_ly = 0.0
        fuel_cost = _intra_fuel_cost(dist_au)
        jump_dist = 0.0
        can_reach_jump = True
        can_reach_fuel = status["fuel"] >= fuel_cost
        can_reach = can_reach_jump and can_reach_fuel
        total_au = dist_au
    else:
        # Different system
        current_gate = db.get_warp_gate(player_sys_id)
        if not current_gate: return {}
        current_gate_pos = get_absolute_au(current_gate.get("id"))
        intra_current_au = get_distance(player_pos_au, current_gate_pos)

        target_gate = db.get_warp_gate(current_view_system_id)
        if not target_gate: return {}
        target_gate_pos = get_absolute_au(target_gate.get("id"))
        intra_target_au = get_distance(target_gate_pos, target_pos_au)

        current_system = db.get_system(player_sys_id)
        if not current_system: return {}
        target_system = db.get_system(current_view_system_id)
        if not target_system: return {}
        dist_ly = get_distance((current_system["x"], current_system["y"]), (target_system["x"], target_system["y"]))

        intra_current_fuel = _intra_fuel_cost(intra_current_au)
        intra_target_fuel = _intra_fuel_cost(intra_target_au)
        inter_fuel = int(dist_ly * 10)
        fuel_cost = intra_current_fuel + inter_fuel + intra_target_fuel
        jump_dist = dist_ly
        can_reach_jump = status["current_jump_distance"] >= dist_ly
        can_reach_fuel = status["fuel"] >= fuel_cost
        can_reach = can_reach_jump and can_reach_fuel
        total_au = intra_current_au + intra_target_au

    distance_str = f"{dist_ly:.2f} ly, {total_au:.2f} AU"
    return {
        "distance": distance_str, "dist_ly": dist_ly, "dist_au": total_au,
        "jump_dist": jump_dist, "fuel_cost": fuel_cost, "can_reach": can_reach, "can_reach_jump": can_reach_jump, "can_reach_fuel": can_reach_fuel
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

    travel_info = _get_travel_costs(target_system_id, (0.0, 0.0))
    if not travel_info:
        return "Cannot calculate travel costs."

    jump_dist = travel_info.get("jump_dist", float('inf'))
    fuel_cost = travel_info.get("fuel_cost", float('inf'))

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
        new_fuel = player["current_player_ship_fuel"] - fuel_cost
        conn = db.get_connection()
        conn.execute("UPDATE player SET current_player_ship_fuel=? WHERE id=1", (new_fuel,))
        conn.commit()
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