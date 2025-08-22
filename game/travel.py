from __future__ import annotations

from data import db

def travel_to_location(location_id: int):
    """
    Handles the logic for traveling to a new location.
    This is a simplified implementation. A real implementation would
    involve time, fuel consumption, and potential events during travel.
    """
    player = db.get_player_full()
    if not player:
        return "Player data not found."

    location = db.get_location(location_id)
    if not location:
        return f"Location with ID {location_id} not found."

    current_system = player.get("system_id")
    target_system = location.get("system_id")

    if current_system != target_system:
        # For now, we only support travel within the same system.
        # A more complex implementation would handle interstellar travel.
        return f"Cannot travel to a different system yet."

    db.set_player_location(location_id)
    return f"Traveled to {location['name']}."