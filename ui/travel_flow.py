# ui/travel_flow.py
from __future__ import annotations

from typing import Callable, List, Tuple

from PySide6.QtCore import QTimer

from data import db
from game import travel, ship_state


class TravelFlow:
    """
    Simple UI wrapper around game.travel with a "progression" sequence using timers.
    Call begin(kind, ident) where kind is 'star' or 'loc'.
    """

    def __init__(self, on_arrival: Callable[[], None], log: Callable[[str], None]) -> None:
        self._on_arrival = on_arrival
        self._log = log

    # -------- public API --------

    def begin(self, kind: str, ident: int) -> None:
        try:
            player = db.get_player_full()
            if not player:
                self._log("No player loaded.")
                return

            is_system_target = (kind == "star")
            target_id = int(ident or 0)
            td = travel.get_travel_display_data(target_id=target_id, is_system_target=is_system_target)
            if not td:
                self._log("No route available.")
                return

            sequence: List[tuple[str, int]] = []
            current_status = ship_state.get_temporary_state() or self._real_ship_status()
            if current_status == "Docked":
                sequence.append(("Un-docking...", 10_000))
            elif current_status == "Orbiting":
                sequence.append(("Leaving Orbit...", 10_000))

            travel_time_ms = int((float(td.get("dist_ly", 0.0)) + float(td.get("dist_au", 0.0))) * 500)
            if travel_time_ms <= 0:
                travel_time_ms = 500
            sequence.append(("Traveling", travel_time_ms))

            if is_system_target:
                sequence.append(("Entering Orbit...", 10_000))
            else:
                target_loc = db.get_location(target_id)
                k = (target_loc.get("kind") or target_loc.get("location_type") or "").lower() if target_loc else ""
                sequence.append(("Docking...", 10_000) if k == "station" else ("Entering Orbit...", 10_000))

            def finalize():
                if is_system_target:
                    travel.travel_to_system(target_id)
                else:
                    travel.travel_to_location(target_id)
                self._after_arrival()

            self._execute_sequence(sequence, finalize)

        except Exception as e:
            self._log(f"Travel error: {e!r}")

    # -------- internals --------

    def _execute_sequence(self, sequence: List[tuple[str, int]], on_done: Callable[[], None]) -> None:
        if not sequence:
            on_done()
            return

        # Kick off and chain timers
        ship_state.set_temporary_state(sequence[0][0])
        elapsed = 0
        for i, (label, dur) in enumerate(sequence):
            def make_cb(lbl=label, last=(i == len(sequence) - 1), d=dur):
                def cb():
                    ship_state.set_temporary_state(lbl)
                    if last:
                        fin = QTimer()
                        fin.setSingleShot(True)
                        fin.timeout.connect(self._finish_sequence(on_done))
                        fin.start(d)
                return cb
            t = QTimer()
            t.setSingleShot(True)
            t.timeout.connect(make_cb())
            t.start(elapsed)
            elapsed += dur

    def _finish_sequence(self, on_done: Callable[[], None]) -> Callable[[], None]:
        def inner():
            ship_state.clear_temporary_state()
            on_done()
            ship_state.clear_temporary_state()
        return inner

    def _real_ship_status(self) -> str:
        player = db.get_player_full() or {}
        loc_id = player.get("current_player_location_id")
        if loc_id:
            loc = db.get_location(int(loc_id))
            if loc:
                k = (loc.get("kind") or loc.get("location_type") or "").lower()
                return "Docked" if k == "station" else "Orbiting"
        if player.get("current_player_system_id"):
            return "Orbiting"
        return "Traveling"

    def _after_arrival(self) -> None:
        try:
            self._on_arrival()
        except Exception:
            pass
