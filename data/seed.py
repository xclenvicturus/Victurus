"""
spacegame/data/seed.py
Populate a demo galaxy with items, ships, markets, and hierarchical solar locations.

Seeds:
- 10 star systems scattered near (12345,12345)
- per system: 6 planets (parent=NULL, local AU offsets from star) and 4 stations
  (parent=one of the planets, small local offsets)
- Player starts in Sys-01 at Planet 1
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

    # --- Deterministic RNG for repeatable dev runs ---
    rng = random.Random(42)

    # --- Systems (integer pc coordinates) ---
    systems = []
    center_x, center_y = 12345, 12345
    for i in range(10):
        sx = center_x + rng.randint(-50, 50)
        sy = center_y + rng.randint(-50, 50)
        name = f"Sys-{i+1:02d}"
        systems.append((name, sx, sy))

    cur.executemany(
        "INSERT INTO systems(name, x, y) VALUES (?, ?, ?);",
        systems,
    )

    # --- Items ---
    items = [
        ("Ore", 100),
        ("Food", 60),
        ("Fuel", 40),
    ]
    cur.executemany(
        "INSERT INTO items(name, base_price) VALUES (?, ?);",
        items,
    )

    # --- Ships ---
    ships = [
        ("Shuttle", 20, 100),
        ("Freighter", 80, 200),
    ]
    cur.executemany(
        "INSERT INTO ships(name, cargo, fuel_max) VALUES (?, ?, ?);",
        ships,
    )

    # Fetch IDs
    cur.execute("SELECT id, name, x, y FROM systems ORDER BY name;")
    sys_rows = cur.fetchall()  # [(id, name, x, y), ...]
    sys_by_name = {row[1]: (row[0], row[2], row[3]) for row in sys_rows}

    cur.execute("SELECT id, name, fuel_max FROM ships WHERE name = 'Shuttle';")
    shuttle_row = cur.fetchone()
    shuttle_id, _shuttle_name, shuttle_fuel_max = shuttle_row

    cur.execute("SELECT id, name FROM items;")
    item_map = {row[1]: row[0] for row in cur.fetchall()}

    # --- Markets (prices & stock) ---
    market_rows = []
    for sys_name, (sys_id, _, _) in sys_by_name.items():
        for item_name, item_id in item_map.items():
            base = {"Ore": 100, "Food": 60, "Fuel": 40}[item_name]
            price = base + (abs(hash(sys_name + item_name)) % 25) - 12 + rng.randint(-5, 5)
            stock = 50 + (abs(hash(item_name + sys_name)) % 40) + rng.randint(-10, 10)
            market_rows.append((sys_id, item_id, max(1, price), max(0, stock)))

    cur.executemany(
        "INSERT INTO markets(system_id, item_id, price, stock) VALUES (?, ?, ?, ?);",
        market_rows,
    )

    # --- Locations (hierarchical local AU coordinates) ---
    # Spread planets MUCH farther: 3..40 AU from star; stations 0.05..0.5 AU from their parent planet.
    for sys_name, (sid, _sx, _sy) in sys_by_name.items():
        planet_ids: list[int] = []
        for p in range(6):
            dx, dy = _polar_to_xy(rng, 3.0, 40.0)  # farther spread
            name = f"{sys_name} Planet {p+1}"
            cur.execute(
                "INSERT INTO locations(system_id, name, kind, x, y, parent_location_id) "
                "VALUES (?, ?, 'planet', ?, ?, NULL);",
                (sid, name, dx, dy),
            )
            pid = cur.lastrowid
            if pid is None:
                raise RuntimeError("Failed to insert planet row")
            planet_ids.append(pid)

        for s in range(4):
            parent_id = rng.choice(planet_ids)
            dx, dy = _polar_to_xy(rng, 0.05, 0.5)  # around a planet
            name = f"{sys_name} Station {s+1}"
            cur.execute(
                "INSERT INTO locations(system_id, name, kind, x, y, parent_location_id) "
                "VALUES (?, ?, 'station', ?, ?, ?);",
                (sid, name, dx, dy, parent_id),
            )

    # --- Player ---
    first_sys = "Sys-01"
    first_sid, _first_sx, _first_sy = sys_by_name[first_sys]
    cur.execute(
        "SELECT id FROM locations WHERE system_id = ? AND name = ?;",
        (first_sid, f"{first_sys} Planet 1"),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Failed to find starting planet for player")
    first_planet_id = row[0]

    cur.execute(
        """
        INSERT INTO player(id, name, credits, system_id, ship_id, fuel, current_location_id)
        VALUES (1, ?, ?, ?, ?, ?, ?);
        """,
        ("Captain Test", 1000, first_sid, shuttle_id, shuttle_fuel_max, first_planet_id),
    )

    # --- Inventory (start empty) ---
    for item_id in item_map.values():
        cur.execute("INSERT INTO inventory(item_id, qty) VALUES (?, ?);", (item_id, 0))

    # --- Price history snapshot ---
    now = _now_iso()
    cur.execute("SELECT system_id, item_id, price FROM markets;")
    hist_rows = [(now, r[0], r[1], r[2]) for r in cur.fetchall()]
    cur.executemany(
        "INSERT INTO prices_history(ts, system_id, item_id, price) VALUES (?, ?, ?, ?);",
        hist_rows,
    )
    # Done. Caller commits.
