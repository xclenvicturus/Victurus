"""
spacegame/data/seed.py
Populate a demo galaxy with items, ships, markets, and hierarchical solar locations.
"""

from __future__ import annotations

import datetime as _dt
import math
import random
import sqlite3


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _polar_to_xy(rng: random.Random, r_min: float, r_max: float) -> tuple[float, float]:
    """Uniform angle, radius in [r_min, r_max] (AU)."""
    r = rng.uniform(r_min, r_max)
    theta = rng.uniform(0.0, 2.0 * math.pi)
    return (r * math.cos(theta), r * math.sin(theta))


def seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    rng = random.Random(42)

    # --- Systems ---
    systems = [(f"Sys-{i+1:02d}", 12345 + rng.randint(-50, 50), 12345 + rng.randint(-50, 50)) for i in range(10)]
    cur.executemany("INSERT INTO systems(system_name, system_x, system_y) VALUES (?, ?, ?);", systems)

    # --- Items ---
    items = [
        ("Ore", 100, "description for Ore", "trade_item"),
        ("Food", 60, "description for Food", "trade_item"),
        ("Fuel", 40, "description for Fuel", "consumable_item"),
    ]
    cur.executemany("INSERT INTO items(item_name, item_base_price, item_description, item_category) VALUES (?, ?, ?, ?);", items)

    # --- Ships ---
    ships = [("Shuttle", 20, 200, 20.0, 50, 100, 100), ("Freighter", 80, 200, 3.0, 100, 200, 150)]
    cur.executemany(
        "INSERT INTO ships(ship_name, base_ship_cargo, base_ship_fuel, base_ship_jump_distance, base_ship_shield, base_ship_hull, base_ship_energy) VALUES (?, ?, ?, ?, ?, ?, ?);",
        ships,
    )

    # Fetch IDs
    cur.execute("SELECT system_id, system_name FROM systems;")
    sys_map = {name: sid for sid, name in cur.fetchall()}
    cur.execute("SELECT item_id, item_name FROM items;")
    item_map = {name: iid for iid, name in cur.fetchall()}
    cur.execute("SELECT ship_id, ship_name, base_ship_fuel, base_ship_hull, base_ship_shield, base_ship_energy, base_ship_jump_distance, base_ship_cargo FROM ships;")
    ship_map = {ship_data[1]: ship_data for ship_data in cur.fetchall()}
    
    shuttle_data = ship_map['Shuttle']

    # --- Markets ---
    market_rows = [
        (sys_id, item_id, 100 + rng.randint(-20, 20), 100 + rng.randint(-50, 50))
        for sys_id in sys_map.values() for item_id in item_map.values()
    ]
    cur.executemany("INSERT INTO markets(system_id, item_id, local_market_price, local_market_stock) VALUES (?, ?, ?, ?);", market_rows)

    # --- Locations ---
    for sys_name, sid in sys_map.items():
        planet_ids = []
        for p in range(6):
            dx, dy = _polar_to_xy(rng, 3.0, 40.0)
            cur.execute(
                "INSERT INTO locations(system_id, location_name, location_type, location_x, location_y, parent_location_id, location_description) VALUES (?, ?, 'planet', ?, ?, NULL, ?);",
                (sid, f"{sys_name} Planet {p+1}", dx, dy, f"A lovely planet named Planet {p+1} in the {sys_name} system."),
            )
            planet_ids.append(cur.lastrowid)

        for s in range(4):
            parent_id = rng.choice(planet_ids)
            dx, dy = _polar_to_xy(rng, 0.05, 0.5)
            cur.execute(
                "INSERT INTO locations(system_id, location_name, location_type, location_x, location_y, parent_location_id, location_description) VALUES (?, ?, 'station', ?, ?, ?, ?);",
                (sid, f"{sys_name} Station {s+1}", dx, dy, parent_id, f"A bustling station orbiting a planet in the {sys_name} system."),
            )
            
    # --- Player ---
    first_sid = sys_map["Sys-01"]
    cur.execute("SELECT location_id FROM locations WHERE system_id = ? AND location_name = ?;",(first_sid, "Sys-01 Planet 1"))
    first_planet_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO player(id, name, current_wallet_credits, current_player_system_id, current_player_ship_id, current_player_ship_fuel, current_player_ship_hull, current_player_ship_shield, current_player_ship_energy, current_player_ship_cargo, current_player_location_id)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("Captain Test", 1000, first_sid, shuttle_data[0], shuttle_data[2], shuttle_data[3], shuttle_data[4], shuttle_data[5], shuttle_data[7], first_planet_id),
    )

    # --- Cargohold ---
    cur.executemany("INSERT INTO cargohold(item_id, item_qty) VALUES (?, 0);", [(item_id,) for item_id in item_map.values()])
    conn.commit()