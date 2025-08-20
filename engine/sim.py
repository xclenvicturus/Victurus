from __future__ import annotations
import sqlite3
import random

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def economy_tick(conn: sqlite3.Connection):
    """
    Adjust station_economy indices to simulate demand/supply shocks.
    If the content DB lacks `is_warzone` on stations, treat as 0.
    """
    # Detect whether `is_warzone` exists
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(stations)").fetchall()]
    has_wz = "is_warzone" in cols

    if has_wz:
        rows = conn.execute("SELECT id, is_warzone FROM stations").fetchall()
    else:
        rows = conn.execute("SELECT id FROM stations").fetchall()

    for r in rows:
        sid = int(r["id"])
        wz = int(r["is_warzone"]) if has_wz and r["is_warzone"] is not None else 0
        base_up = 0.01 if wz else 0.0

        conn.execute("""
            INSERT INTO station_economy(station_id) VALUES(?)
            ON CONFLICT(station_id) DO NOTHING
        """, (sid,))

        econ = conn.execute(
            "SELECT fuel_index, repair_index, energy_index FROM station_economy WHERE station_id=?",
            (sid,)
        ).fetchone()

        def _jitter():
            return random.uniform(-0.02, 0.03 + base_up)

        fi = _clamp(float(econ["fuel_index"])   * (1.0 + _jitter()), 0.5, 5.0)
        ri = _clamp(float(econ["repair_index"]) * (1.0 + _jitter()), 0.5, 5.0)
        ei = _clamp(float(econ["energy_index"]) * (1.0 + _jitter()), 0.5, 5.0)

        conn.execute(
            "UPDATE station_economy SET fuel_index=?, repair_index=?, energy_index=? WHERE station_id=?",
            (fi, ri, ei, sid)
        )

    conn.commit()

def faction_skirmish_tick(conn: sqlite3.Connection):
    # placeholder hook you already had; left intact
    pass

def wars_tick(conn: sqlite3.Connection):
    # placeholder hook; left intact
    pass