from __future__ import annotations

from typing import Callable, List, Tuple, Optional

import math
from PySide6.QtCore import QObject, QTimer

from data import db
from game import travel, ship_state


# --- Transit timing & fuel cadence knobs -------------------------------------
PHASE_WRAP_MS = 5000
# Duration (ms) of *wrapper* phases that bracket motion:
# - Undocking / Docking
# - Entering / Leaving Cruise
# - Initializing / Leaving Warp
# - Entering / Leaving Orbit
# Purely cinematic: longer values feel weightier but add to total trip time.
# Has no effect on fuel math except that fuel "drip" only runs during the timed
# motion phases (“Cruising” / “Warping”), not these wrappers.

CRUISE_MS_PER_AU = 500
# In-system travel speed. The cruise leg time is:
#     cruise_time_ms = distance_AU * CRUISE_MS_PER_AU
# Example: 12 AU → 12 * 500 = 6000 ms (6.0 s), plus wrapper phases.
# Increasing this slows intra-system travel and stretches the fuel drip window.

WARP_MS_PER_LY = 500
# Inter-system travel speed. The warp leg time is:
#     warp_time_ms = distance_LY * WARP_MS_PER_LY
# Example: 3.2 ly → 3.2 * 500 = 1600 ms (1.6 s), plus wrapper phases.
# Higher values make warps feel longer and drip fuel over a longer period.

DRIP_STEP_MS = 100
# Fuel “drip” cadence during timed legs (“Cruising” / “Warping”).
# Every DRIP_STEP_MS, a small slice of that leg’s fuel budget is deducted.
# Smaller = smoother gauges (e.g., 50 ms ≈ 20 updates/sec) but more DB writes.
# Practical ranges:
#   - 30–75 ms: very smooth UI, heavier write frequency
#   - 100–250 ms: good balance for most machines
#   - >250 ms: chunky updates but minimal overhead

def _intra_fuel_cost(au: float) -> int:
    """1 fuel per 5 AU, rounded up; min 1 if distance > 0."""
    au = float(au or 0.0)
    if au <= 0.0:
        return 0
    return max(1, int(math.ceil(au / 5.0)))


def _warp_fuel_cost_ly(ly: float) -> int:
    """2 fuel per 1 ly, rounded up."""
    ly = float(ly or 0.0)
    if ly <= 0.0:
        return 0
    return int(math.ceil(2.0 * ly))


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

        # A phase is (label, ms, fuel_delta_total_for_phase)
        seq: List[Tuple[str, int, int]] = []

        # --- source depart wrapper if currently parked somewhere ---
        source_kind = (route.get("source_kind") or "").lower()
        if source_kind == "station":
            seq.append(("Undocking", PHASE_WRAP_MS, 0))
        elif source_kind in ("planet", "star", "warpgate"):
            seq.append(("Leaving Orbit", PHASE_WRAP_MS, 0))

        same_system = bool(route.get("same_system", False))
        if same_system:
            # -------- Intra-system: single cruise leg --------
            dist_au = float(route.get("dist_au", 0.0))
            cruise_ms = max(0, int(round(dist_au * CRUISE_MS_PER_AU)))
            fuel_cruise = _intra_fuel_cost(dist_au)
            seq.extend([
                ("Entering Cruise", PHASE_WRAP_MS, 0),
                ("Cruising", cruise_ms, fuel_cruise),
                ("Leaving Cruise", PHASE_WRAP_MS, 0),
            ])
        else:
            # -------- Inter-system: cruise to gate, warp, cruise from gate --------
            intra_current_au = float(route.get("intra_current_au", 0.0))
            intra_target_au = float(route.get("intra_target_au", 0.0))
            dist_ly = float(route.get("dist_ly", 0.0))

            fuel_cruise_src = _intra_fuel_cost(intra_current_au)
            fuel_warp = _warp_fuel_cost_ly(dist_ly)
            fuel_cruise_dst = _intra_fuel_cost(intra_target_au)

            seq.extend([
                ("Entering Cruise", PHASE_WRAP_MS, 0),
                ("Cruising", max(0, int(round(intra_current_au * CRUISE_MS_PER_AU))), fuel_cruise_src),
                ("Leaving Cruise", PHASE_WRAP_MS, 0),

                ("Initializing Warp", PHASE_WRAP_MS, 0),
                ("Warping", max(0, int(round(dist_ly * WARP_MS_PER_LY))), fuel_warp),
                ("Leaving Warp", PHASE_WRAP_MS, 0),

                ("Entering Cruise", PHASE_WRAP_MS, 0),
                ("Cruising", max(0, int(round(intra_target_au * CRUISE_MS_PER_AU))), fuel_cruise_dst),
                ("Leaving Cruise", PHASE_WRAP_MS, 0),
            ])

        # --- perform the actual DB move just before arrival wrappers ---
        def _do_move() -> None:
            try:
                msg = travel.perform_travel(kind, ident)   # only moves player; fuel deducted via drip
                if msg:
                    self._log(str(msg))
            except Exception as e:
                self._log(f"Travel apply error: {e}")

        # --- arrival wrapper ---
        target_kind = (route.get("target_kind") or "").lower()
        if target_kind == "station":
            arrival_tail: List[Tuple[str, int, int]] = [
                ("Docking", PHASE_WRAP_MS, 0),
                ("Docked", 0, 0),
            ]
        else:
            arrival_tail = [
                ("Entering Orbit", PHASE_WRAP_MS, 0),
                ("Orbiting", 0, 0),
            ]

        # Split run: transit (pre-arrival), then perform move, then arrival wrapper
        pre_arrival = list(seq)
        post_arrival = arrival_tail

        def _after_transit() -> None:
            _do_move()
            self._run_sequence(post_arrival, on_done=self._after_arrival)

        self._run_sequence(pre_arrival, on_done=_after_transit)

    # ---- internals ----

    def _apply_fuel_delta(self, delta: int) -> None:
        """Subtract a positive delta of fuel from the player's ship immediately."""
        if not delta or delta <= 0:
            return
        try:
            player = db.get_player_full() or {}
            cur = int(player.get("current_player_ship_fuel") or 0)
            new_val = max(0, cur - int(delta))
            conn = db.get_connection()
            conn.execute(
                "UPDATE player SET current_player_ship_fuel=? WHERE id=1",
                (new_val,),
            )
            conn.commit()
        except Exception:
            # Don't let transient DB issues break the sequence
            pass

    def _start_fuel_drip(self, total_ms: int, total_delta: int) -> None:
        """
        Gradually subtract fuel over total_ms in fixed DRIP_STEP_MS increments.
        Distributes integers exactly (base + remainder spread).
        """
        total_ms = int(total_ms)
        total_delta = int(total_delta)
        if total_delta <= 0 or total_ms <= 0:
            return

        ticks = max(1, int(math.ceil(total_ms / float(DRIP_STEP_MS))))
        per = total_delta // ticks
        rem = total_delta % ticks

        # repeating timer
        t = QTimer(self)
        t.setInterval(DRIP_STEP_MS)
        t.setSingleShot(False)

        state = {"left": ticks, "per": per, "rem": rem, "timer": t}

        def _step() -> None:
            if state["left"] <= 0:
                try:
                    state["timer"].stop()
                    state["timer"].deleteLater()
                except Exception:
                    pass
                return
            chunk = state["per"] + (1 if state["rem"] > 0 else 0)
            if state["rem"] > 0:
                state["rem"] -= 1
            state["left"] -= 1
            self._apply_fuel_delta(chunk)
            if state["left"] <= 0:
                try:
                    state["timer"].stop()
                    state["timer"].deleteLater()
                except Exception:
                    pass

        t.timeout.connect(_step)
        t.start()
        # Track so we can cancel on interruption
        self._timers.append(t)

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

    def _run_sequence(
        self,
        phases: List[Tuple[str, int, int]],
        on_done: Optional[Callable[[], None]] = None
    ) -> None:
        """Drive the temporary ship status through the phases, dripping fuel during timed legs."""
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

        def _kick(i: int) -> None:
            if i >= len(phases):
                if on_done:
                    on_done()
                return

            label, ms, fuel_total = phases[i]
            try:
                self._set_temp_state(label, ms)
                # For timed legs, drip fuel across the duration; for instant legs, subtract immediately
                if ms > 0 and fuel_total > 0:
                    self._start_fuel_drip(ms, fuel_total)
                elif fuel_total > 0:
                    self._apply_fuel_delta(fuel_total)
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
