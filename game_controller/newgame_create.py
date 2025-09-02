# /game_controller/newgame_create.py

"""
Victurus New Game Creation System

Handles creation of new game saves:
- Initialize fresh save directory structure
- Set up initial player and ship data
- Configure starting location and resources
- Integrate with save management system
"""

from __future__ import annotations

from typing import Optional, Dict

from save.save_manager import SaveManager
from data.db import get_connection


def create_new_game(
    save_name: str,
    commander: str,
    starting_label: str,
    start_ids: Optional[Dict[str, int]] = None,
) -> None:
    """
    One-stop entry point for creating a new game:
      1) Creates a new save via SaveManager (initializes DB files).
      2) Spawns the player at the chosen race/system/location (or a safe fallback).
      3) Ensures cargohold rows exist for all items.

    Args:
      save_name:      Name for the save directory / metadata.
      commander:      Player-visible commander name.
      starting_label: Human-friendly label (what UI shows in menus).
      start_ids:      Optional dict of explicit IDs:
                        { 'race_id': int, 'system_id': int, 'location_id': int }
                      If omitted, we fall back to the first race flagged as starting_world.

    Raises:
      Exception: bubbled up from SaveManager or DB calls on critical failure.
    """
    # Step 1: create the save (idempotent if the name is reused)
    SaveManager.create_new_save(save_name, commander, starting_label)

    # Step 2: apply (race, system, location) selection to the freshly-initialized DB
    _apply_start_selection(commander, start_ids)

    # Step 3: ensure cargohold rows exist for every item
    _ensure_cargohold_rows()


# ---------- internals ----------

def _apply_start_selection(commander: str, start_ids: Optional[Dict[str, int]]) -> None:
    """
    Write/overwrite the player's starting state in the current DB.

    - Picks a starter ship (prefers 'Shuttle', else smallest cargo).
    - Sets player system / location and base ship stats.
    - Preserves existing wallet if present, else 1000 credits.
    - If start_ids is None, falls back to the first race with starting_world=1.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Fallback to first 'starting_world' race if no explicit selection was provided.
    if not start_ids:
        row = cur.execute(
            """
            SELECT race_id, home_system_id, home_planet_location_id
            FROM races
            WHERE COALESCE(starting_world, 1) = 1
            ORDER BY race_id
            LIMIT 1;
            """
        ).fetchone()
        if not row:
            # Last-ditch fallback: stay with whatever the seeder created.
            return
        start_ids = {
            "race_id": int(row["race_id"]),
            "system_id": int(row["home_system_id"]),
            "location_id": int(row["home_planet_location_id"]),
        }

    # Pick a starter ship (prefer Shuttle, else smallest cargo)
    ship = cur.execute(
        """
        SELECT ship_id, ship_name, base_ship_fuel, base_ship_hull, base_ship_shield,
               base_ship_energy, base_ship_jump_distance, base_ship_cargo
        FROM ships
        ORDER BY (ship_name='Shuttle') DESC, base_ship_cargo ASC
        LIMIT 1;
        """
    ).fetchone()
    if not ship:
        raise RuntimeError("No ships found to assign as a starter ship.")

    # Preserve wallet if present; otherwise 1000
    row = cur.execute("SELECT current_wallet_credits FROM player WHERE id=1").fetchone()
    credits = int(row[0]) if row and row[0] is not None else 1000

    # Overwrite player row with the chosen start
    cur.execute(
        """
        INSERT OR REPLACE INTO player(
            id, name, current_wallet_credits, current_player_system_id,
            current_player_ship_id, current_player_ship_fuel, current_player_ship_hull,
            current_player_ship_shield, current_player_ship_energy, current_player_ship_cargo,
            current_player_location_id
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            commander or "Captain",
            credits,
            int(start_ids["system_id"]),
            int(ship["ship_id"]),
            int(ship["base_ship_fuel"]),
            int(ship["base_ship_hull"]),
            int(ship["base_ship_shield"]),
            int(ship["base_ship_energy"]),
            0,
            int(start_ids["location_id"]),
        ),
    )

    conn.commit()


def _ensure_cargohold_rows() -> None:
    """
    Make sure the player's cargohold has a row for every item (qty=0 if missing).
    Safe to call repeatedly.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO cargohold(item_id, item_qty)
        SELECT item_id, 0 FROM items;
        """
    )
    conn.commit()
