from __future__ import annotations
import sqlite3, math
from typing import List, Dict, Optional, Tuple

def get_player(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM player WHERE id=1").fetchone()
    return dict(row) if row else {}

def player_ship(conn: sqlite3.Connection) -> dict:
    r = conn.execute("SELECT s.* FROM player p JOIN ships s ON p.ship_id=s.id WHERE p.id=1").fetchone()
    return dict(r)

def get_system(conn: sqlite3.Connection, system_id: int) -> dict:
    r = conn.execute("SELECT * FROM systems WHERE id=?", (system_id,)).fetchone()
    return dict(r)

def system_of_station(conn: sqlite3.Connection, station_id: int) -> int:
    r = conn.execute("SELECT sys.id as sid FROM stations st JOIN planets pl ON st.planet_id=pl.id JOIN systems sys ON pl.system_id=sys.id WHERE st.id=?", (station_id,)).fetchone()
    return r["sid"]

def distance_between_systems(conn: sqlite3.Connection, sys_a: int, sys_b: int) -> float:
    a = get_system(conn, sys_a); b = get_system(conn, sys_b)
    dx, dy = a["x"] - b["x"], a["y"] - b["y"]
    return float(math.hypot(dx, dy))

def get_location_name(conn: sqlite3.Connection, location_type: str, location_id: int) -> str:
    if location_type == "station":
        r = conn.execute("SELECT s.name || ' (' || p.name || ', ' || sys.name || ')' AS n FROM stations s JOIN planets p ON s.planet_id=p.id JOIN systems sys ON p.system_id=sys.id WHERE s.id=?", (location_id,)).fetchone()
        return r["n"] if r else f"Station#{location_id}"
    return "Deep Space"

def map_data(conn: sqlite3.Connection):
    systems = [dict(r) for r in conn.execute("SELECT * FROM systems ORDER BY id")]
    planets = [dict(r) for r in conn.execute("SELECT * FROM planets ORDER BY id")]
    stations = [dict(r) for r in conn.execute("SELECT s.*, f.name AS faction_name, p.system_id FROM stations s JOIN factions f ON s.faction_id=f.id JOIN planets p ON s.planet_id=p.id ORDER BY s.id")]
    by_sys: Dict[int, Dict] = {s["id"]: {"system": s, "planets": []} for s in systems}
    for pl in planets:
        by_sys[pl["system_id"]].setdefault("planets", []).append({**pl, "stations": []})
    for st in stations:
        # append to the correct planet within system
        pls = by_sys[st["system_id"]]["planets"]
        for p in pls:
            if p["id"] == st["planet_id"]:
                p["stations"].append(st)
    return by_sys

def station_detail(conn: sqlite3.Connection, station_id: int) -> dict:
    station = conn.execute("SELECT s.*, p.name AS planet_name, f.name AS faction_name, p.system_id AS system_id FROM stations s JOIN planets p ON s.planet_id=p.id JOIN factions f ON s.faction_id=f.id WHERE s.id=?", (station_id,)).fetchone()
    npcs = conn.execute("SELECT * FROM npcs WHERE station_id=? ORDER BY id", (station_id,)).fetchall()
    market = conn.execute("""
        SELECT i.id AS item_id, i.name, i.type, i.description, m.quantity, m.price
        FROM markets m JOIN items i ON m.item_id=i.id WHERE m.station_id=? ORDER BY i.id
    """, (station_id,)).fetchall()
    fuel_price = conn.execute("SELECT fuel_price FROM stations WHERE id=?", (station_id,)).fetchone()["fuel_price"]
    ship_market = conn.execute("""
        SELECT sm.ship_id, s.name, sm.price, sm.quantity
        FROM ship_market sm JOIN ships s ON sm.ship_id=s.id WHERE sm.station_id=?
    """, (station_id,)).fetchall()
    return {"station": dict(station), "npcs": [dict(n) for n in npcs], "market": [dict(m) for m in market], "fuel_price": fuel_price, "ship_market": [dict(r) for r in ship_market]}

def update_player_location(conn: sqlite3.Connection, location_type: str, location_id: int):
    conn.execute("UPDATE player SET location_type=?, location_id=? WHERE id=1", (location_type, location_id))
    conn.commit()

def adjust_player(conn: sqlite3.Connection, credits_delta: int = 0, hp_delta: int = 0, energy_delta: int = 0, fuel_delta: int = 0):
    conn.execute("UPDATE player SET credits=credits+?, hp=hp+?, energy=max(0, energy+?), fuel=max(0, fuel+?) WHERE id=1", (credits_delta, hp_delta, energy_delta, fuel_delta))
    conn.commit()

def set_active_ship(conn: sqlite3.Connection, ship_id: int):
    # set active ship, ensure fuel not exceeding capacity
    conn.execute("UPDATE player SET ship_id=? WHERE id=1", (ship_id,))
    conn.execute("UPDATE hangar_ships SET is_active=0")
    conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (ship_id,))
    cap = conn.execute("SELECT fuel_capacity FROM ships WHERE id=?", (ship_id,)).fetchone()["fuel_capacity"]
    conn.execute("UPDATE player SET fuel=min(fuel, ?) WHERE id=1", (cap,))
    conn.commit()

def player_cargo(conn: sqlite3.Connection) -> List[dict]:
    rows = conn.execute("""
        SELECT i.id AS item_id, i.name, i.type, pc.quantity, i.base_price
        FROM player_cargo pc JOIN items i ON pc.item_id=i.id ORDER BY i.id
    """).fetchall()
    return [dict(r) for r in rows]

def set_player_cargo(conn: sqlite3.Connection, item_id: int, delta: int):
    conn.execute("UPDATE player_cargo SET quantity=max(0, quantity+?) WHERE item_id=?", (delta, item_id))
    conn.commit()

def quests_at_station(conn: sqlite3.Connection, station_id: int):
    rows = conn.execute("""
        SELECT q.*, qi.status FROM quests q
        JOIN quest_instances qi ON qi.quest_id=q.id
        WHERE q.giver_npc_id IN (SELECT id FROM npcs WHERE station_id=?)
        ORDER BY q.id
    """, (station_id,)).fetchall()
    return [dict(r) for r in rows]

def accept_quest(conn: sqlite3.Connection, quest_id: int):
    conn.execute("UPDATE quest_instances SET status='accepted' WHERE quest_id=?", (quest_id,))
    conn.commit()

def complete_quest_if_applicable(conn: sqlite3.Connection, quest_id: int):
    q = conn.execute("SELECT * FROM quests WHERE id=?", (quest_id,)).fetchone()
    if not q:
        return None
    qi = conn.execute("SELECT * FROM quest_instances WHERE quest_id=?", (quest_id,)).fetchone()
    if not qi or qi["status"] != "accepted":
        return None
    player = get_player(conn)
    cargo = {r["item_id"]: r["quantity"] for r in (conn.execute("SELECT * FROM player_cargo").fetchall())}
    if q["id"] == 1 and player["location_type"] == "station" and player["location_id"] == 2 and cargo.get(1,0) >= 10:
        conn.execute("UPDATE player_cargo SET quantity=quantity-10 WHERE item_id=1")
        conn.execute("UPDATE quest_instances SET status='completed' WHERE quest_id=1")
        conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (q["reward_credits"],))
        conn.commit()
        return q["reward_credits"]
    if q["id"] == 2 and player["location_type"] == "station" and player["location_id"] == 1 and cargo.get(3,0) >= 5:
        conn.execute("UPDATE player_cargo SET quantity=quantity-5 WHERE item_id=3")
        conn.execute("UPDATE quest_instances SET status='completed' WHERE quest_id=2")
        conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (q["reward_credits"],))
        conn.commit()
        return q["reward_credits"]
    if q["id"] == 3 and player["location_type"] == "station" and player["location_id"] == 4 and cargo.get(2,0) >= 20:
        conn.execute("UPDATE player_cargo SET quantity=quantity-20 WHERE item_id=2")
        conn.execute("UPDATE quest_instances SET status='completed' WHERE quest_id=3")
        conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (q["reward_credits"],))
        conn.commit()
        return q["reward_credits"]
    return None

def rep_with(conn: sqlite3.Connection, faction_id: int) -> int:
    r = conn.execute("SELECT rep FROM faction_rep WHERE faction_id=?", (faction_id,)).fetchone()
    return r["rep"] if r else 0

def adjust_rep(conn: sqlite3.Connection, faction_id: int, delta: int):
    conn.execute("UPDATE faction_rep SET rep=rep+? WHERE faction_id=?", (delta, faction_id))
    conn.commit()

def relation_between(conn: sqlite3.Connection, a: int, b: int) -> str:
    fa, fb = (a,b) if a < b else (b,a)
    r = conn.execute("SELECT state FROM faction_relations WHERE faction_a=? AND faction_b=?", (fa, fb)).fetchone()
    return r["state"] if r else "neutral"
