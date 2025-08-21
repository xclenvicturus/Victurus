from __future__ import annotations
from .starter_locations import list_starting_locations  # re-export for UI
from save.manager import SaveManager

def start_new_game(save_name: str, commander_name: str, starting_location_label: str):
    return SaveManager.create_new_save(save_name, commander_name, starting_location_label)
