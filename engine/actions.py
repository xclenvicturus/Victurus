# engine/actions.py
from __future__ import annotations
import sqlite3
from typing import Tuple, Dict, Optional


# -----------------------------
# Small helpers used elsewhere
# -----------------------------

def get_player(conn: sqlite3.Connection) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM player WHERE id=1;").fetchone()
    if not r:
        raise RuntimeError("Player row missing (id=1).")
    return r

def player_ship(conn: sqlite3.Connection) -> sqlite3.Row:
    """
    Returns the active ship row joined from hangar_ships -> ships.
    """
    r = conn.execute("""
        SELECT s.*
        FROM hangar_ships h
        JOIN ships s ON s.id = h.ship_id
        WHERE h.is_active=1
        LIMIT 1
    """).fetchone()
    if not r:
        raise RuntimeError("No active ship found in hangar_ships.")
    return r


# -----------------------------
# Introspection / ensure helpers
# -----------------------------

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table});").fetchall()}
    return column in cols

def _ensure_station_econ_table(conn: sqlite3.Connection) -> None:
    """
    Ensure dynamic economy table exists in MAIN save DB.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_economy(
            station_id   INTEGER PRIMARY KEY,
            fuel_index   REAL    NOT NULL DEFAULT 1.0,
            repair_index REAL    NOT NULL DEFAULT 1.0,
            energy_index REAL    NOT NULL DEFAULT 1.0
        );
    """)

def _ensure_station_econ_row(conn: sqlite3.Connection, station_id: int) -> None:
    _ensure_station_econ_table(conn)
    conn.execute("""
        INSERT INTO station_economy(station_id) VALUES(?)
        ON CONFLICT(station_id) DO NOTHING
    """, (int(station_id),))


# -----------------------------
# Service pricing
# -----------------------------

def _service_base_prices(conn: sqlite3.Connection, station_id: int) -> Tuple[int, int, int]:
    """
    Base per-unit prices for services. Prefer *_price_base columns on stations.
    Fallback to defaults if absent.
    """
    # Probe columns once
    has_fpb = _column_exists(conn, "stations", "fuel_price_base")
    has_rpb = _column_exists(conn, "stations", "repair_price_base")
    has_epb = _column_exists(conn, "stations", "energy_price_base")

    if has_fpb and has_rpb and has_epb:
        row = conn.execute(
            "SELECT fuel_price_base, repair_price_base, energy_price_base FROM stations WHERE id=?",
            (int(station_id),)
        ).fetchone()
        if row:
            fp = int(row["fuel_price_base"]) if row["fuel_price_base"] is not None else 5
            rp = int(row["repair_price_base"]) if row["repair_price_base"] is not None else 2
            ep = int(row["energy_price_base"]) if row["energy_price_base"] is not None else 3
            return fp, rp, ep

    # Defaults when columns are missing
    return 5, 2, 3

def _service_indices(conn: sqlite3.Connection, station_id: int) -> Tuple[float, float, float]:
    _ensure_station_econ_row(conn, station_id)
    row = conn.execute(
        "SELECT fuel_index, repair_index, energy_index FROM station_economy WHERE station_id=?",
        (int(station_id),)
    ).fetchone()
    return float(row["fuel_index"]), float(row["repair_index"]), float(row["energy_index"])

def current_service_prices(conn: sqlite3.Connection, station_id: int) -> Dict[str, int]:
    """
    Returns integer per-unit prices (after dynamic indices):
      { "fuel": int, "repair": int, "energy": int }
    """
    fpb, rpb, epb = _service_base_prices(conn, station_id)
    fi, ri, ei = _service_indices(conn, station_id)
    return {
        "fuel":   max(1, int(round(fpb * fi))),
        "repair": max(1, int(round(rpb * ri))),
        "energy": max(1, int(round(epb * ei))),
    }


# -----------------------------
# Refuel / Repair / Recharge
# -----------------------------

def refuel(conn: sqlite3.Connection, station_id: int, units: int) -> str:
    """
    Add up to `units` fuel to the player's tank, respecting capacity and credits.
    Also nudges local fuel price via station_economy.
    """
    units = max(0, int(units))
    # Player fuel & credits
    p = conn.execute("SELECT credits, fuel FROM player WHERE id=1").fetchone()
    have_fuel = int(p["fuel"])
    credits = int(p["credits"])

    # Active ship capacity
    ship = conn.execute("""
        SELECT s.fuel_capacity
        FROM hangar_ships h JOIN ships s ON s.id=h.ship_id
        WHERE h.is_active=1
    """).fetchone()
    if not ship:
        return "No active ship."
    cap = int(ship["fuel_capacity"])
    space = max(0, cap - have_fuel)
    if space <= 0:
        return "Fuel tank already full."

    units = min(units, space)
    if units <= 0:
        return "Fuel tank already full."

    price_unit = current_service_prices(conn, station_id)["fuel"]
    cost = units * price_unit
    if credits < cost:
        return "Not enough credits."

    with conn:
        conn.execute("UPDATE player SET credits=credits-?, fuel=fuel+? WHERE id=1", (cost, units))
        # demand pushes price up a bit
        _ensure_station_econ_row(conn, station_id)
        conn.execute(
            "UPDATE station_economy SET fuel_index = fuel_index * (1.0 + (?*0.002)) WHERE station_id=?",
            (units, int(station_id))
        )
    return f"Refueled {units} units for {cost} credits."

def repair_full(conn: sqlite3.Connection, station_id: int) -> str:
    """
    Repair hull to ship max hull (assumed to be 100 if not in ships).
    Uses per-HP repair price and nudges local repair price.
    """
    p = conn.execute("SELECT credits, hp FROM player WHERE id=1").fetchone()
    credits = int(p["credits"])
    hp = int(p["hp"])

    # Determine max hull:
    # Prefer ships.hull; fallback to 100.
    max_hull = 100
    try:
        s = conn.execute("""
            SELECT s.hull
            FROM hangar_ships h JOIN ships s ON s.id=h.ship_id
            WHERE h.is_active=1
        """).fetchone()
        if s and s["hull"] is not None:
            max_hull = int(s["hull"])
    except sqlite3.OperationalError:
        pass  # ships.hull may not exist in very old templates

    if hp >= max_hull:
        return "Ship is already fully repaired."
    missing = max_hull - hp

    price_unit = current_service_prices(conn, station_id)["repair"]
    cost = missing * price_unit
    if credits < cost:
        return "Not enough credits."

    with conn:
        conn.execute("UPDATE player SET credits=credits-?, hp=? WHERE id=1", (cost, max_hull))
        _ensure_station_econ_row(conn, station_id)
        conn.execute(
            "UPDATE station_economy SET repair_index = repair_index * (1.0 + (?*0.002)) WHERE station_id=?",
            (missing, int(station_id))
        )
    return f"Repaired {missing} hull for {cost} credits."

def recharge_full(conn: sqlite3.Connection, station_id: int, max_energy: Optional[int] = None) -> str:
    """
    Recharge energy to ship.energy_capacity (or given max_energy as a hard cap).
    """
    p = conn.execute("SELECT credits, energy FROM player WHERE id=1").fetchone()
    credits = int(p["credits"])
    have = int(p["energy"])

    # Determine energy cap from ship; fallback to 10.
    cap = 10
    try:
        s = conn.execute("""
            SELECT s.energy_capacity
            FROM hangar_ships h JOIN ships s ON s.id=h.ship_id
            WHERE h.is_active=1
        """).fetchone()
        if s and s["energy_capacity"] is not None:
            cap = int(s["energy_capacity"])
    except sqlite3.OperationalError:
        pass

    if max_energy is not None:
        cap = min(cap, int(max_energy))

    if have >= cap:
        return "Energy already full."
    need = cap - have

    price_unit = current_service_prices(conn, station_id)["energy"]
    cost = need * price_unit
    if credits < cost:
        return "Not enough credits."

    with conn:
        conn.execute("UPDATE player SET credits=credits-?, energy=? WHERE id=1", (cost, cap))
        _ensure_station_econ_row(conn, station_id)
        conn.execute(
            "UPDATE station_economy SET energy_index = energy_index * (1.0 + (?*0.003)) WHERE station_id=?",
            (need, int(station_id))
        )
    return f"Recharged {need} energy for {cost} credits."


# -----------------------------
# Market buy/sell
# -----------------------------

def buy_item(conn: sqlite3.Connection, station_id: int, item_id: int, qty: int) -> str:
    qty = max(1, int(qty))
    row = conn.execute("""
        SELECT m.quantity, m.price FROM market_prices m
        WHERE m.station_id=? AND m.item_id=?
    """, (int(station_id), int(item_id))).fetchone()
    if not row:
        return "Item not sold here."
    mqty = int(row["quantity"]); price = int(row["price"])
    if mqty < qty:
        return "Not enough stock."

    credits = int(conn.execute("SELECT credits FROM player WHERE id=1").fetchone()["credits"])
    cost = price * qty
    if credits < cost:
        return "Not enough credits."

    # cargo capacity check (1 unit per item)
    cap_row = conn.execute("""
        SELECT s.cargo_capacity
        FROM hangar_ships h JOIN ships s ON s.id=h.ship_id
        WHERE h.is_active=1
    """).fetchone()
    cap = int(cap_row["cargo_capacity"]) if cap_row else 0
    used = int(conn.execute("SELECT COALESCE(SUM(quantity),0) AS q FROM player_cargo").fetchone()["q"])
    if used + qty > cap:
        return "Not enough cargo space."

    with conn:
        conn.execute("UPDATE player SET credits=credits-? WHERE id=1", (cost,))
        conn.execute("""
            INSERT INTO player_cargo(item_id, quantity) VALUES(?, ?)
            ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + excluded.quantity
        """, (int(item_id), qty))
        conn.execute("""
            UPDATE market_prices SET quantity=quantity-?
            WHERE station_id=? AND item_id=?
        """, (qty, int(station_id), int(item_id)))
    return f"Bought x{qty} for {cost} credits."

def sell_item(conn: sqlite3.Connection, station_id: int, item_id: int, qty: int) -> str:
    qty = max(1, int(qty))
    have = conn.execute("SELECT quantity FROM player_cargo WHERE item_id=?", (int(item_id),)).fetchone()
    if not have or int(have["quantity"]) < qty:
        return "You don't have enough."

    row = conn.execute("""
        SELECT price FROM market_prices WHERE station_id=? AND item_id=?
    """, (int(station_id), int(item_id))).fetchone()
    price = int(row["price"]) if row else 1
    revenue = price * qty

    with conn:
        conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (revenue,))
        conn.execute("UPDATE player_cargo SET quantity = quantity - ? WHERE item_id=?", (qty, int(item_id)))
        conn.execute("""
            INSERT INTO market_prices(station_id, item_id, quantity, price)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(station_id, item_id) DO UPDATE SET quantity=COALESCE(market_prices.quantity,0)+excluded.quantity
        """, (int(station_id), int(item_id), qty, price))
        conn.execute("DELETE FROM player_cargo WHERE quantity<=0")
    return f"Sold x{qty} for {revenue} credits."


# -----------------------------
# Ships
# -----------------------------

def buy_ship(conn: sqlite3.Connection, station_id: int, ship_id: int) -> str:
    """
    Buy a ship available at ship_market (station-scoped price/qty).
    Places it in hangar_ships as inactive.
    """
    row = conn.execute("""
        SELECT price, quantity FROM ship_market
        WHERE station_id=? AND ship_id=?
    """, (int(station_id), int(ship_id))).fetchone()
    if not row or int(row["quantity"]) <= 0:
        return "Ship not available."

    price = int(row["price"])
    credits = int(conn.execute("SELECT credits FROM player WHERE id=1").fetchone()["credits"])
    if credits < price:
        return "Not enough credits."

    with conn:
        conn.execute("UPDATE player SET credits=credits-? WHERE id=1", (price,))
        conn.execute("UPDATE ship_market SET quantity=quantity-1 WHERE station_id=? AND ship_id=?",
                     (int(station_id), int(ship_id)))
        conn.execute("INSERT INTO hangar_ships(ship_id, is_active) VALUES(?, 0)", (int(ship_id),))
    return f"Purchased ship #{ship_id} for {price} credits."

def sell_ship(conn: sqlite3.Connection, ship_id: int) -> str:
    """
    Sell a ship from the hangar. Value is half the ship's base price (ships.base_price),
    falling back to ships.price or 100 if base_price is absent.
    If selling the active ship and other ships remain, the first remaining becomes active.
    """
    value = 100
    try:
        # Prefer base_price, fallback to price
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ships);").fetchall()}
        if "base_price" in cols:
            pr = conn.execute("SELECT base_price FROM ships WHERE id=?", (int(ship_id),)).fetchone()
            if pr and pr["base_price"] is not None:
                value = max(0, int(pr["base_price"]) // 2)
        elif "price" in cols:
            pr = conn.execute("SELECT price FROM ships WHERE id=?", (int(ship_id),)).fetchone()
            if pr and pr["price"] is not None:
                value = max(0, int(pr["price"]) // 2)
    except sqlite3.OperationalError:
        pass

    with conn:
        conn.execute("DELETE FROM hangar_ships WHERE ship_id=?", (int(ship_id),))
        conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (value,))
        row = conn.execute("SELECT ship_id FROM hangar_ships LIMIT 1").fetchone()
        if row:
            conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (int(row["ship_id"]),))
    return f"Sold ship #{ship_id} for {value} credits."

def set_active_ship(conn: sqlite3.Connection, ship_id: int) -> str:
    with conn:
        conn.execute("UPDATE hangar_ships SET is_active=0")
        conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (int(ship_id),))
    return f"Active ship set to #{ship_id}."