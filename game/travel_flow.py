from __future__ import annotations

from typing import Callable, Optional, Dict, Any, List, Tuple

from PySide6.QtCore import QObject, QTimer, Signal, QElapsedTimer

from game import travel
from game import player_status
from data import db  # for system-name fallbacks

# ---- Timing knobs (unchanged) ----
PHASE_WRAP_MS    = 5000   # fixed 5s for all enter/leave phases
CRUISE_MS_PER_AU = 500    # ms per AU
WARP_MS_PER_LY   = 500    # ms per LY
DRIP_STEP_MS     = 10     # ms cadence for progress ticks

# ---- Fuel weights (your values) ----
WRAP_FUEL_WEIGHT   = 2.00
CRUISE_FUEL_WEIGHT = 1.00
WARP_FUEL_WEIGHT   = 1.40

# Continuous model (aligns with UI): 1 fuel per 5 AU
FUEL_PER_AU = 1.0 / 5.0
# Warp base rate (pre-weight): 2 fuel per 1 LY
WARP_FUEL_PER_LY = 2.0


def _ms_for_cruise(au: float) -> int:
    """Return a duration that is >=1 ms when AU > 0, else 0."""
    au = float(au or 0.0)
    if au <= 0.0:
        return 0
    return max(1, int(au * CRUISE_MS_PER_AU))


def _ms_for_warp(ly: float) -> int:
    """Return a duration that is >=1 ms when LY > 0, else 0."""
    ly = float(ly or 0.0)
    if ly <= 0.0:
        return 0
    return max(1, int(ly * WARP_MS_PER_LY))


def _weighted_split(total: float, parts: List[Tuple[float, int]]) -> List[float]:
    """
    Split 'total' across N parts using weight * duration_ms for each part.
    Each part is (weight, duration_ms).
    Returns list of floats that sum ~ total.
    """
    weights = []
    total_w = 0.0
    for w, dur in parts:
        wv = max(0.0, float(w)) * max(0, int(dur))
        weights.append(wv)
        total_w += wv
    if total_w <= 0.0 or total <= 0.0:
        return [0.0 for _ in parts]
    # proportional allocation with float precision
    alloc = [total * (wv / total_w) for wv in weights]
    # fix rounding drift to match 'total' as closely as possible
    drift = total - sum(alloc)
    if alloc:
        alloc[-1] += drift
    return alloc


def _sys_name_from_id(sys_id: int) -> Optional[str]:
    """Best-effort lookup of a system's display name."""
    try:
        row = db.get_system(int(sys_id))
        if row:
            return str(row.get("name") or row.get("system_name") or f"System {sys_id}")
    except Exception:
        pass
    return None


class TravelFlow(QObject):
    """Orchestrates multi-phase travel with smooth, per-tick fuel drip and status updates."""

    # Emitted every DRIP_STEP_MS during travel (used by MainWindow to refresh gauges smoothly)
    progressTick = Signal()

    def __init__(self, on_arrival: Optional[Callable[[], None]] = None, log: Optional[Callable[[str], None]] = None) -> None:
        super().__init__()
        self._on_arrival = on_arrival
        self._log = log or (lambda _m: None)

        self._seq: List[Dict[str, Any]] = []
        self._seq_index: int = 0

        self._tick = QTimer(self)
        self._tick.setInterval(DRIP_STEP_MS)
        self._tick.timeout.connect(self._on_tick)

        self._phase_timer = QElapsedTimer()
        self._phase_duration_ms = 0
        self._phase_fuel_total = 0.0
        self._phase_fuel_dripped = 0.0

        # Track where we are for status/location hints
        self._phase_name: str = ""

    # ---------------- Public API ----------------

    def begin(self, kind: str, ident: int) -> None:
        """Plan and start a full travel sequence to a system or location."""
        route = travel.get_travel_display_data(kind, ident)
        if not route.get("ok"):
            self._log("Unable to plan travel.")
            return

        self._seq = self._plan_sequence(route, kind, ident)
        self._seq_index = 0
        if not self._seq:
            self._log("Nothing to do.")
            return
        self._start_next_phase()

    # ---------------- Internals ----------------

    def _plan_sequence(self, route: Dict[str, Any], kind: str, ident: int) -> List[Dict[str, Any]]:
        """
        Create a linear list of phases with durations and fuel budgets.
        Fuel is allocated by (weight × duration_ms) so cruise always gets a non-zero share.
        Warp fuel is added on top of intra-system fuel (not reallocated from it).
        """
        same_system = bool(route.get("same_system", False))
        seq: List[Dict[str, Any]] = []

        # Distances
        dist_ly = float(route.get("dist_ly", 0.0))
        if same_system:
            dist_au = float(route.get("dist_au", 0.0))
            au_legs = [("cruise_only", dist_au)]
        else:
            # two intra legs: to source gate, from dest gate
            au_legs = [
                ("to_gate", float(route.get("intra_current_au", 0.0))),
                ("from_gate", float(route.get("intra_target_au", 0.0))),
            ]

        # ---- Durations ----
        wrap_ms = PHASE_WRAP_MS

        # Cruise durations (could be one or two segments)
        cruise_segments_ms: List[Tuple[str, int]] = []
        for name, au in au_legs:
            cruise_segments_ms.append((name, _ms_for_cruise(au)))

        # Warp durations
        warp_ms_total = _ms_for_warp(dist_ly)
        # split warp into enter/warp/exit
        warp_enter_ms = wrap_ms
        warp_exit_ms = wrap_ms
        warp_mid_ms = max(0, warp_ms_total)

        # ---- Intra-system fuel bucket (AU-based; continuous) ----
        intra_total_fuel = FUEL_PER_AU * sum(au for _n, au in au_legs)

        # Build the list of weighted parts for intra allocation
        intra_parts: List[Tuple[float, int]] = []
        if same_system:
            # leave orbit / enter cruise
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            # cruise (one segment; ensure duration>0 if AU>0)
            intra_parts.append((CRUISE_FUEL_WEIGHT, cruise_segments_ms[0][1]))
            # leave cruise / enter orbit
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
        else:
            # Undock/leave orbit -> enter cruise to gate
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            # cruise to gate
            intra_parts.append((CRUISE_FUEL_WEIGHT, cruise_segments_ms[0][1]))
            # leave cruise (at gate)
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            # later: after warp, enter cruise from gate
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            # cruise from gate
            intra_parts.append((CRUISE_FUEL_WEIGHT, cruise_segments_ms[1][1] if len(cruise_segments_ms) > 1 else 0))
            # leave cruise / enter orbit
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))
            intra_parts.append((WRAP_FUEL_WEIGHT, wrap_ms))

        intra_alloc = _weighted_split(intra_total_fuel, intra_parts)

        # ---- Warp fuel bucket (LY-based; extra on top of intra fuel) ----
        warp_total_fuel = WARP_FUEL_PER_LY * dist_ly * WARP_FUEL_WEIGHT
        if dist_ly > 0.0:
            warp_parts = [
                (WRAP_FUEL_WEIGHT, warp_enter_ms),
                (1.0,              warp_mid_ms),  # mid-warp burn dominated by distance; weight already in total
                (WRAP_FUEL_WEIGHT, warp_exit_ms),
            ]
            warp_alloc = _weighted_split(warp_total_fuel, warp_parts)
        else:
            warp_parts = []
            warp_alloc = []

        # ---- Fallback system names for location hints ----
        src_sys_name = None
        try:
            pf = db.get_player_full() or {}
            src_sys_id = int(pf.get("current_player_system_id") or pf.get("system_id") or 0)
            if src_sys_id:
                src_sys_name = _sys_name_from_id(src_sys_id)
        except Exception:
            pass

        tgt_sys_name = None
        try:
            tgt_id = int(route.get("target_system_id") or 0)
            if tgt_id:
                tgt_sys_name = _sys_name_from_id(tgt_id)
        except Exception:
            pass

        # Prefer names supplied by route (if any)
        src_name = route.get("source_system_name") or src_sys_name
        tgt_name = route.get("target_system_name") or tgt_sys_name

        # ---- Build the executable sequence with named phases ----
        def _add_phase(name: str, ms: int, fuel: float, set_state: Optional[str] = None, loc_hint: Optional[str] = None):
            seq.append({
                "name": name,
                "ms": int(ms),
                "fuel": float(max(0.0, fuel)),
                "set_state": set_state,
                "loc_hint": loc_hint,
            })

        ia = iter(intra_alloc)

        if same_system:
            # leave orbit
            _add_phase("leaving_orbit",   wrap_ms, next(ia), set_state="Leaving Orbit")
            # enter cruise
            _add_phase("entering_cruise", wrap_ms, next(ia), set_state="Entering Cruise", loc_hint=tgt_name)
            # cruise
            _add_phase("cruising", cruise_segments_ms[0][1], next(ia), set_state="Cruising", loc_hint=tgt_name)
            # leave cruise
            _add_phase("leaving_cruise",  wrap_ms, next(ia), set_state="Leaving Cruise")
            # entering orbit/docking (based on target kind)
            arrive_state = "Docking" if route.get("target_kind") == "station" else "Entering Orbit"
            _add_phase("approach", wrap_ms, next(ia), set_state=arrive_state)
        else:
            # undock/leave orbit -> enter cruise to gate
            _add_phase("undocking_or_depart", wrap_ms, next(ia),
                       set_state="Undocking" if route.get("source_kind") == "station" else "Leaving Orbit")
            _add_phase("entering_cruise_src", wrap_ms, next(ia), set_state="Entering Cruise", loc_hint=src_name)

            # cruise to gate
            _add_phase("cruise_to_gate", cruise_segments_ms[0][1], next(ia), set_state="Cruising", loc_hint=src_name)

            # leave cruise at gate
            _add_phase("leaving_cruise_src", wrap_ms, next(ia), set_state="Leaving Cruise")

            # ---- Warp block (if any) ----
            if dist_ly > 0.0:
                wa = iter(warp_alloc)
                _add_phase("init_warp",  warp_enter_ms, next(wa), set_state="Initializing Warp", loc_hint="The Warp")
                _add_phase("warping",    warp_mid_ms,   next(wa), set_state="Warping",          loc_hint="The Warp")
                _add_phase("exit_warp",  warp_exit_ms,  next(wa), set_state="Leaving Warp")

            # enter cruise from gate
            _add_phase("entering_cruise_dst", wrap_ms, next(ia), set_state="Entering Cruise", loc_hint=tgt_name)

            # cruise from gate to target
            _add_phase("cruise_from_gate",
                       cruise_segments_ms[1][1] if len(cruise_segments_ms) > 1 else 0,
                       next(ia),
                       set_state="Cruising",
                       loc_hint=tgt_name)

            # leave cruise / approach target
            _add_phase("leaving_cruise_dst", wrap_ms, next(ia), set_state="Leaving Cruise")
            arrive_state = "Docking" if route.get("target_kind") == "station" else "Entering Orbit"
            _add_phase("approach", wrap_ms, next(ia), set_state=arrive_state)

        # Final arrival commit (no fuel; instant)
        seq.append({
            "name": "arrive_commit",
            "ms": 0,
            "fuel": 0.0,
            "commit": (kind, ident),
        })


        return seq

    def _start_next_phase(self) -> None:
        if self._seq_index >= len(self._seq):
            return
        phase = self._seq[self._seq_index]
        self._phase_name = str(phase.get("name", ""))
        ms = int(phase.get("ms", 0))
        fuel = float(phase.get("fuel", 0.0))
        set_state = phase.get("set_state")
        loc_hint = phase.get("loc_hint")

        # Update live status (state + transient location text for cruise/warp)
        if set_state:
            if loc_hint:
                player_status.set_transient_location(loc_hint)
            elif self._phase_name not in ("warping", "init_warp"):
                # clear transient if not in warp/cruise with a hint
                player_status.clear_transient_location()
            player_status.set_ship_state(set_state)

        # Commit arrival?
        if self._phase_name == "arrive_commit" and "commit" in phase:
            k, ident = phase["commit"]
            msg = travel.perform_travel(k, int(ident))
            self._log(msg)

            # Clear all transient UI overrides so DB status (Docked/Orbiting) shows
            try:
                player_status.set_ship_state("")          # clear temporary phase text
            except Exception:
                pass
            player_status.clear_transient_location()

            if callable(self._on_arrival):
                self._on_arrival()
            return

        # Start timers for this phase
        self._phase_duration_ms = max(0, ms)
        self._phase_fuel_total = max(0.0, fuel)
        self._phase_fuel_dripped = 0.0

        if self._phase_duration_ms <= 0:
            # no time, no fuel — step through immediately
            self._seq_index += 1
            self._start_next_phase()
            return

        self._phase_timer.restart()
        if not self._tick.isActive():
            self._tick.start()

    def _on_tick(self) -> None:
        if self._seq_index >= len(self._seq):
            self._tick.stop()
            return

        elapsed = self._phase_timer.elapsed()
        duration = max(1, self._phase_duration_ms)
        t = min(1.0, elapsed / float(duration))

        # Smooth, proportional drip over the whole phase
        target_used = self._phase_fuel_total * t
        delta = target_used - self._phase_fuel_dripped
        if delta > 0.0:
            player_status.adjust_fuel(-delta)
            self._phase_fuel_dripped += delta

        # UI update hook
        self.progressTick.emit()

        if elapsed >= duration:
            # ensure exact fuel consumed for this phase
            residual = self._phase_fuel_total - self._phase_fuel_dripped
            if residual > 0:
                player_status.adjust_fuel(-residual)
                self._phase_fuel_dripped += residual

            # next phase
            self._seq_index += 1
            if self._seq_index >= len(self._seq):
                self._tick.stop()
                return
            self._start_next_phase()
