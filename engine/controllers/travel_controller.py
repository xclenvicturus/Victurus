# engine/controllers/travel_controller.py
from __future__ import annotations
import tkinter as tk
import sqlite3
from typing import Optional, Callable


class TravelController:
    """
    Drives travel progress between locations. Emits events on the bus:
      - "departed"
      - "travel_progress" with payload {"progress": int, "total": int}
      - "arrived" with payload {"station_id": int}
    """

    def __init__(
        self,
        root: tk.Misc,
        conn: sqlite3.Connection,
        bus,
        ask_yes_no: Callable[[str, str], bool],
    ):
        self.root = root
        self.conn = conn
        self.bus = bus
        self.ask_yes_no = ask_yes_no

        self._timer: Optional[str] = None
        self._total_steps = 100
        self._progress = 0
        self._dest_station: Optional[int] = None
        self._step_ms = 150  # tick speed

    # ---------- helpers ----------

    def _link_distance(self, from_station: int, to_station: int) -> int:
        # Prefer links.distance if present; else fallback to 5
        try:
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(links);").fetchall()}
            if "distance" in cols:
                r = self.conn.execute("""
                    SELECT distance FROM links
                    WHERE (a=? AND b=?) OR (a=? AND b=?)
                    LIMIT 1
                """, (from_station, to_station, to_station, from_station)).fetchone()
                if r and r["distance"] is not None:
                    d = int(r["distance"])
                    return max(1, d)
        except sqlite3.OperationalError:
            pass
        return 5  # sensible non-zero fallback

    def _player_station(self) -> Optional[int]:
        r = self.conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
        if r and r["location_id"] is not None:
            return int(r["location_id"])
        return None

    def _set_player_station(self, sid: int) -> None:
        self.conn.execute("UPDATE player SET location_id=? WHERE id=1", (int(sid),))
        self.conn.commit()

    # ---------- API ----------

    def begin_travel(self, station_id: int) -> None:
        current = self._player_station()
        if current is None:
            return

        self._dest_station = int(station_id)
        distance = self._link_distance(current, self._dest_station)

        # Travel budget mapped to steps; 1 unit distance = 20 steps
        self._total_steps = max(20, distance * 20)
        self._progress = 0

        # depart
        try:
            self.bus.emit("departed")
        except Exception:
            pass

        self._tick()

    def _tick(self):
        if self._dest_station is None:
            return
        self._progress = min(self._total_steps, self._progress + 1)

        try:
            self.bus.emit("travel_progress", {"progress": self._progress, "total": self._total_steps})
        except Exception:
            pass

        if self._progress >= self._total_steps:
            dest = self._dest_station
            self._dest_station = None
            self._set_player_station(int(dest))
            try:
                self.bus.emit("arrived", {"station_id": int(dest)})
            except Exception:
                pass
            return

        self.root.after(self._step_ms, self._tick)
