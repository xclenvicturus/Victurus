# /game_controller/sim_tasks.py

# Worker-side tasks for the universe simulator.
# Pure functions only: no Qt, no global mutable state shared across processes.

from __future__ import annotations

import os
import sqlite3
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable


# -----------------------------
# Result Types (lightweight)
# -----------------------------

@dataclass
class MarketDelta:
    """
    Changes to market prices within a single system.

    price_changes: list of (item_id, new_price)
    """
    system_id: int
    price_changes: List[Tuple[int, int]]


@dataclass
class InventoryDelta:
    """
    Per-facility inventory change for a single tick (read-only *plan*).
    Positive delta_qty means production; negative means consumption.
    """
    facility_id: int
    item_id: int
    delta_qty: float


@dataclass
class ShipDelta:
    """
    Planned ship update. Keep it tiny; the sim thread will translate this into
    actual SQL writes. You can evolve fields later (e.g., new course, orders).
    """
    ship_id: int
    new_order: Optional[str] = None
    new_pos: Optional[Tuple[float, float]] = None  # (x, y) in scene units or domain units


__all__ = [
    "MarketDelta",
    "InventoryDelta",
    "ShipDelta",
    "plan_market_drift",
    "plan_market_drift_many",
    "tick_facilities",
    "tick_ships",
]


# -----------------------------
# Read-only DB helper
# -----------------------------

def _detect_db_path() -> Path:
    """
    Best-effort DB path detection:
    1) data.db.get_active_db_path() if available
    2) env VICTURUS_DB_PATH
    3) <project_root>/database/game.db (assuming this file is in game_controller/)
    """
    # Try to use the project's db helper if it exposes get_active_db_path()
    try:
        from data import db as dbmod  # type: ignore
        if hasattr(dbmod, "get_active_db_path"):
            p = dbmod.get_active_db_path()  # might be a Path or str
            return Path(str(p))
    except Exception:
        pass

    # Env override
    env_path = os.getenv("VICTURUS_DB_PATH")
    if env_path:
        return Path(env_path)

    # Fallback relative to repo layout: ../database/game.db
    here = Path(__file__).resolve()
    default_path = here.parents[1] / "database" / "game.db"
    return default_path


def _open_readonly_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Open a read-only SQLite connection to the DB file with sane PRAGMAs for
    worker-side, read-only workloads.
    """
    ap = Path(db_path) if db_path else _detect_db_path()
    ap.parent.mkdir(parents=True, exist_ok=True)

    # sqlite3 URI for read-only mode
    conn = sqlite3.connect(f"file:{ap.as_posix()}?mode=ro", uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row

    # Read-only friendly pragmas
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA query_only = ON;")
        conn.execute("PRAGMA busy_timeout = 750;")
        conn.execute("PRAGMA temp_store = MEMORY;")
    except Exception:
        # Some PRAGMAs may be restricted in ro mode; ignore failures.
        pass

    return conn


# -----------------------------
# Market drift planning
# -----------------------------

def _system_factor(system_id: int, frame: int, drift: float) -> float:
    """
    Deterministic per-(system, frame) factor around 1.0.
    Produces 1.0 +/- drift or a tiny jitter near 1.0.
    """
    r = random.Random((frame * 1_000_003) ^ (system_id * 7_654_321))
    roll = r.random()
    if roll < 1 / 3:
        factor = 1.0 - drift
    elif roll > 2 / 3:
        factor = 1.0 + drift
    else:
        factor = 1.0 + (r.uniform(-drift * 0.25, drift * 0.25))
    # Keep within sensible bounds
    return max(0.50, min(1.50, factor))


def plan_market_drift(system_id: int, frame: int = 0, drift: float = 0.005) -> MarketDelta:
    """
    Compute a per-item *new price* for the given system by applying a small
    multiplicative factor to current prices. Read-only; returns a MarketDelta.
    """
    conn = _open_readonly_connection()
    try:
        factor = _system_factor(system_id, frame, drift)
        rows = conn.execute(
            "SELECT item_id, local_market_price FROM markets WHERE system_id=?",
            (system_id,),
        ).fetchall()
        changes: List[Tuple[int, int]] = []
        for row in rows:
            item_id = int(row["item_id"])
            price = int(row["local_market_price"])
            new_price = max(1, int(price * factor))
            if new_price != price:
                changes.append((item_id, new_price))
        return MarketDelta(system_id=system_id, price_changes=changes)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def plan_market_drift_many(system_ids: Iterable[int], frame: int = 0, drift: float = 0.005) -> List[MarketDelta]:
    """
    Batched variant to reduce connection overhead when a single worker handles
    multiple systems. Still read-only, returns a list of MarketDelta.
    """
    conn = _open_readonly_connection()
    try:
        out: List[MarketDelta] = []
        for sid in system_ids:
            f = _system_factor(int(sid), frame, drift)
            rows = conn.execute(
                "SELECT item_id, local_market_price FROM markets WHERE system_id=?",
                (int(sid),),
            ).fetchall()
            changes: List[Tuple[int, int]] = []
            for row in rows:
                item_id = int(row["item_id"])
                price = int(row["local_market_price"])
                new_price = max(1, int(price * f))
                if new_price != price:
                    changes.append((item_id, new_price))
            out.append(MarketDelta(system_id=int(sid), price_changes=changes))
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


# -----------------------------
# Facilities: IO planning
# -----------------------------

def tick_facilities(system_id: int) -> List[InventoryDelta]:
    """
    Plan inventory deltas for all facilities within the given system.
    Assumes schema tables:
      facilities (facility_id, location_id, facility_type, ...)
      facility_inputs  (facility_id, item_id, rate)
      facility_outputs (facility_id, item_id, rate)
      locations (location_id, system_id, ...)
    Returns a list of InventoryDelta (one per (facility,item) with non-zero delta).
    """
    conn = _open_readonly_connection()
    try:
        # Aggregate outputs (production)
        out_rows = conn.execute(
            """
            SELECT f.facility_id AS fid, fo.item_id AS item_id, SUM(fo.rate) AS rate_out
            FROM facilities f
            JOIN locations l ON l.location_id = f.location_id
            LEFT JOIN facility_outputs fo ON fo.facility_id = f.facility_id
            WHERE l.system_id = ?
            GROUP BY f.facility_id, fo.item_id
            """,
            (system_id,),
        ).fetchall()

        # Aggregate inputs (consumption)
        in_rows = conn.execute(
            """
            SELECT f.facility_id AS fid, fi.item_id AS item_id, SUM(fi.rate) AS rate_in
            FROM facilities f
            JOIN locations l ON l.location_id = f.location_id
            LEFT JOIN facility_inputs fi ON fi.facility_id = f.facility_id
            WHERE l.system_id = ?
            GROUP BY f.facility_id, fi.item_id
            """,
            (system_id,),
        ).fetchall()

        # Merge to per (facility,item) net delta
        # Use dict[(fid,item_id)] -> (out, in)
        prod: Dict[Tuple[int, int], float] = {}
        cons: Dict[Tuple[int, int], float] = {}

        for r in out_rows:
            fid = int(r["fid"])
            item = int(r["item_id"]) if r["item_id"] is not None else None
            if item is None:
                continue
            prod[(fid, item)] = float(r["rate_out"] or 0.0)

        for r in in_rows:
            fid = int(r["fid"])
            item = int(r["item_id"]) if r["item_id"] is not None else None
            if item is None:
                continue
            cons[(fid, item)] = float(r["rate_in"] or 0.0)

        # Union of keys
        keys = set(prod.keys()) | set(cons.keys())
        deltas: List[InventoryDelta] = []
        for (fid, item) in keys:
            out_rate = prod.get((fid, item), 0.0)
            in_rate = cons.get((fid, item), 0.0)
            delta = out_rate - in_rate
            if abs(delta) > 1e-9:
                deltas.append(InventoryDelta(facility_id=fid, item_id=item, delta_qty=delta))
        return deltas
    finally:
        try:
            conn.close()
        except Exception:
            pass


# -----------------------------
# Ships: minimal planning
# -----------------------------

def tick_ships(system_id: int, limit: int = 64) -> List[ShipDelta]:
    """
    Very lightweight ship planning example. Reads a handful of ships that
    belong to / are currently in the given system and proposes a no-op or
    trivial order. Safe default until you design real AI.

    Schema assumptions (best-effort; we try a couple of variants):
      - ships table exists.
      - Either ships.system_id, or ships.current_location_id -> locations.system_id
      - Optional ship_roles table with (ship_id, role)
    """
    conn = _open_readonly_connection()
    try:
        rows = []
        # Try common variants, fall back gracefully
        q_attempts = [
            ("SELECT ship_id FROM ships WHERE system_id=? LIMIT ?", (system_id, limit)),
            ("""
                SELECT s.ship_id
                FROM ships s
                JOIN locations l ON l.location_id = s.current_location_id
                WHERE l.system_id = ?
                LIMIT ?
            """, (system_id, limit)),
        ]
        for sql, params in q_attempts:
            try:
                rows = conn.execute(sql, params).fetchall()
                if rows:
                    break
            except Exception:
                rows = []

        deltas: List[ShipDelta] = []
        # Simple placeholder: keep ships idle (no movement), but we could
        # randomly schedule a local patrol in the future.
        for r in rows:
            ship_id = int(r["ship_id"])
            deltas.append(ShipDelta(ship_id=ship_id, new_order=None, new_pos=None))
        return deltas
    finally:
        try:
            conn.close()
        except Exception:
            pass
