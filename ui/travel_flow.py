# ui/travel_flow.py
from __future__ import annotations

from typing import Callable, List, Tuple, Optional

from PySide6.QtCore import QObject, QTimer

from data import db
from game import travel, ship_state


PHASE_WRAP_MS = 5000          # fixed 5s for all enter/leave phases
CRUISE_MS_PER_AU = 500        # scaling for cruising time (ms per AU)
WARP_MS_PER_LY = 500          # scaling for warp time (ms per LY)


class TravelFlow(QObject):
    """
    UI wrapper around game.travel with a phase-based sequence.
    Call begin(kind, ident) where kind is 'loc' (location_id) or 'star' (system_id).
    """

    def __init__(self, on_arrival: Callable[[], None], log: Optional[Callable[[str], None]] = None) -> None:
        super().__init__()
        self._on_arrival = on_arrival
        self._log = log or (lambda m: None)
        self._timers: List[QTimer] = []

    # ---- public API ----
    def begin(self, kind: str, ident: int) -> None:
        """
        Start a travel sequence to a target.
        kind: 'loc' for a location_id target, 'star' for a system_id target (to its star).
        """
        try:
            route = travel.get_travel_display_data(kind, ident)
        except Exception as e:
            self._log(f"Travel error: {e}")
            return

        if not isinstance(route, dict) or not route.get("ok", True):
            self._log("Unable to plan route.")
            return

        seq: List[Tuple[str, int]] = []

        # --- source depart wrapper if currently parked somewhere ---
        source_kind = (route.get("source_kind") or "").lower()
        if source_kind == "station":
            seq.append(("Undocking", PHASE_WRAP_MS))
        elif source_kind in ("planet", "star", "warpgate"):
            seq.append(("Leaving Orbit", PHASE_WRAP_MS))

        same_system = bool(route.get("same_system", False))
        if same_system:
            # -------- Intra-system: single cruise leg --------
            dist_au = float(route.get("dist_au", 0.0))
            cruise_ms = max(0, int(round(dist_au * CRUISE_MS_PER_AU)))
            seq.extend([
                ("Entering Cruise", PHASE_WRAP_MS),
                ("Cruising", cruise_ms),
                ("Leaving Cruise", PHASE_WRAP_MS),
            ])
        else:
            # -------- Inter-system: cruise to gate, warp, cruise from gate --------
            intra_current_au = float(route.get("intra_current_au", 0.0))
            intra_target_au = float(route.get("intra_target_au", 0.0))
            dist_ly = float(route.get("dist_ly", 0.0))

            seq.extend([
                ("Entering Cruise", PHASE_WRAP_MS),
                ("Cruising", max(0, int(round(intra_current_au * CRUISE_MS_PER_AU)))),
                ("Leaving Cruise", PHASE_WRAP_MS),

                ("Initializing Warp", PHASE_WRAP_MS),
                ("Warping", max(0, int(round(dist_ly * WARP_MS_PER_LY)))),
                ("Leaving Warp", PHASE_WRAP_MS),

                ("Entering Cruise", PHASE_WRAP_MS),
                ("Cruising", max(0, int(round(intra_target_au * CRUISE_MS_PER_AU)))),
                ("Leaving Cruise", PHASE_WRAP_MS),
            ])

        # --- perform the actual DB move just before arrival wrappers ---
        def _do_move() -> None:
            try:
                msg = travel.perform_travel(kind, ident)
                if msg:
                    self._log(str(msg))
            except Exception as e:
                self._log(f"Travel apply error: {e}")

        # --- arrival wrapper ---
        target_kind = (route.get("target_kind") or "").lower()
        if target_kind == "station":
            arrival_tail: List[Tuple[str, int]] = [
                ("Docking", PHASE_WRAP_MS),
                ("Docked", 0),
            ]
        else:
            arrival_tail = [
                ("Entering Orbit", PHASE_WRAP_MS),
                ("Orbiting", 0),
            ]

        # Split run: transit (pre-arrival), then perform move, then arrival wrapper
        pre_arrival = list(seq)            # all phases up to arrival
        post_arrival = arrival_tail        # the arrival wrapper

        def _after_transit() -> None:
            _do_move()
            self._run_sequence(post_arrival, on_done=self._after_arrival)

        self._run_sequence(pre_arrival, on_done=_after_transit)

    # ---- internals ----

    def _set_temp_state(self, label: str, ms: int) -> None:
        """
        Call ship_state.set_temporary_state in a way that satisfies both runtime and Pylance.
        Some builds accept (label, ms); others accept only (label).
        """
        set_tmp = getattr(ship_state, "set_temporary_state", None)
        if callable(set_tmp):
            try:
                set_tmp(label, ms)  # type: ignore[call-arg]
            except TypeError:
                try:
                    set_tmp(label)  # type: ignore[misc]
                except Exception:
                    pass

    def _run_sequence(self, phases: List[Tuple[str, int]], on_done: Optional[Callable[[], None]] = None) -> None:
        """Drive the temporary ship status through the given phases."""
        # Clean up any existing timers
        for t in self._timers:
            try:
                t.stop()
                t.deleteLater()
            except Exception:
                pass
        self._timers.clear()

        if not phases:
            if on_done:
                on_done()
            return

        # Chain timers
        def _kick(i: int) -> None:
            if i >= len(phases):
                if on_done:
                    on_done()
                return
            label, ms = phases[i]
            try:
                self._set_temp_state(label, ms)
            except Exception:
                pass

            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(max(0, int(ms)))
            self._timers.append(t)
            t.timeout.connect(lambda: _kick(i + 1))
            t.start()

        _kick(0)

    def _after_arrival(self) -> None:
        try:
            self._on_arrival()
        except Exception:
            pass
