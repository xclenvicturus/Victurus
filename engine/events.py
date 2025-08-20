# engine/events.py
from __future__ import annotations
import sqlite3
from typing import Final, Optional

# ---- Event name constants (import these elsewhere) ----
log: Final[str] = "log"
status_changed: Final[str] = "status_changed"
travel_progress: Final[str] = "travel_progress"
open_combat: Final[str] = "open_combat"
combat_over: Final[str] = "combat_over"
arrived: Final[str] = "arrived"
departed: Final[str] = "departed"
quests_changed: Final[str] = "quests_changed"
combat_turn: Final[str] = "combat_turn"  # used by CombatController

# ---- Optional logging helper (safe if table missing) ----
def log_event(conn: sqlite3.Connection, text: str) -> None:
    """
    Append a row to events_log if present; otherwise no-op.
    """
    try:
        # ensure table exists before writing (won't create it)
        has = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events_log';"
        ).fetchone()
        if not has:
            return
        from datetime import datetime
        conn.execute(
            "INSERT INTO events_log(created_at, text) VALUES (?, ?)",
            (datetime.utcnow().isoformat(timespec="seconds"), text),
        )
        conn.commit()
    except Exception:
        # keep the app resilient
        pass

def emit_and_log(bus, conn: Optional[sqlite3.Connection], category: str, message: str) -> None:
    """
    Convenience to both write to events_log (if available) and emit 'log' on the bus.
    """
    if conn is not None:
        try:
            log_event(conn, f"[{category}] {message}")
        except Exception:
            pass
    try:
        bus.emit(log, category, message)
    except Exception:
        pass
