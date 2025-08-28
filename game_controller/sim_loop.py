# /game_controller/sim_loop.py

# Background "universe" simulator that runs off the UI thread and
# advances all NON-visible systems, markets, ships, etc.
# It also exposes a small publish_tick() hook the UI can call to
# annotate what's happening during visible rendering.

from __future__ import annotations

import os
import math
import threading
import time
import random
import queue
from typing import Callable, Optional, Dict, Any, List, Sequence, Iterable, Tuple, TYPE_CHECKING

from data import db

# Optional multi-core compute
try:
    from concurrent.futures import ProcessPoolExecutor  # runtime use
except Exception:  # pragma: no cover
    ProcessPoolExecutor = None  # type: ignore[assignment]

# For type checking only (prevents "Variable not allowed in type expression")
if TYPE_CHECKING:
    from concurrent.futures import ProcessPoolExecutor as _PPE


def _make_in_clause(values: Sequence[int]) -> str:
    # Helper to construct (?, ?, ?, ...) safely for IN clauses
    return "(" + ",".join("?" for _ in values) + ")" if values else "(NULL)"


# -------- Worker-side pure functions (must be top-level / importable) --------

def _plan_market_drift_task(args: Tuple[int, Sequence[int], float]) -> Dict[int, float]:
    """
    Compute tiny multiplicative price nudges per system_id, read-only planning.
    Returns {system_id: factor}, where factor ~ 1.0 +/- drift.
    """
    frame, sys_ids, drift = args
    out: Dict[int, float] = {}
    # Keep it deterministic per (frame, system) and process-safe
    for sid in sys_ids:
        # stable-ish seed per (frame, sid) but different across frames
        r = random.Random((frame * 1_000_003) ^ (sid * 7_654_321))
        roll = r.random()
        if roll < 1 / 3:
            factor = 1.0 - drift
        elif roll > 2 / 3:
            factor = 1.0 + drift
        else:
            # slight jitter around 1.0 to avoid totally static prices
            factor = 1.0 + (r.uniform(-drift * 0.25, drift * 0.25))
        # clamp factor a bit just in case
        out[int(sid)] = max(0.50, min(1.50, factor))
    return out


# -------- Simulator --------

class UniverseSimulator:
    """
    Runs a lightweight tick loop on a background thread.

    - Skips the 'visible' system (the one currently shown in the Solar view).
    - Keeps basic economy/ship/etc. calculations moving for other systems.
    - Streams optional debug lines to a sink (UI log or file), and to tick_debug.

    Performance notes:
    - Reuses a thread-local DB connection (from data.db).
    - Caches system IDs and refreshes periodically.
    - Updates off-screen systems in subsets each tick to reduce contention.
    - Commits after each logical batch to shorten write locks (WAL-friendly).

    Multi-core option:
    - If enabled, shards off-screen systems to a ProcessPool for **read-only planning**,
      then applies all writes in a single batched commit on the sim thread.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Lower default tick to reduce contention & CPU; can be raised via set_tick_rate()
        self._tick_rate_hz = 2.0

        self._visible_system_id: Optional[int] = None

        # Debug/logging
        self._debug_enabled: bool = False
        self._debug_sink: Optional[Callable[[str], None]] = None

        # Async logger so _emit never blocks the tick thread
        self._log_q: queue.Queue[str] = queue.Queue(maxsize=1000)
        self._emitter_thread: Optional[threading.Thread] = None
        self._emitter_stop = threading.Event()

        # Profiling / cadence
        self._frame = 0
        self._last_target_dt = 1.0 / self._tick_rate_hz

        # Cached system ids
        self._all_system_ids: List[int] = []
        self._ids_refresh_every = 300  # frames
        self._ids_next_refresh_at = 0

        # Cadence knobs
        self._market_subset_fraction = 0.25   # update ~25% of off-screen systems per tick
        self._market_every_frames = 1         # or raise to update less frequently
        self._ships_sample_limit = 50         # cap sampling work
        self._market_drift = 0.005            # +/- 0.5% price nudge baseline

        # ----- Multiprocessing knobs -----
        self._use_process_pool: bool = False
        self._max_workers: int = max(1, (os.cpu_count() or 2) - 1)
        self._pool: Optional["_PPE"] = None  # type: ignore[name-defined]
        # To avoid giant SQL statements, apply factors in reasonable chunks
        self._apply_chunk_max = 250  # systems per SQL CASE/IN block (~3 params/system)

    # ---- lifecycle ----
    def ensure_running(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="UniverseSim", daemon=True)
        self._thread.start()
        self._start_emitter()
        self._emit("[sim] started")

        # Eagerly spin up pool if requested (safe to do here;
        # also lazily created inside tick if not present).
        if self._use_process_pool:
            self._ensure_pool()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            t.join(timeout=1.0)
        self._stop_emitter()
        self._shutdown_pool()
        self._emit("[sim] stopped")

    # ---- config ----
    def set_tick_rate(self, hz: float) -> None:
        self._tick_rate_hz = max(1.0, float(hz))
        self._last_target_dt = 1.0 / self._tick_rate_hz
        self._emit(f"[sim] tick_rate_hz => {self._tick_rate_hz:.2f}")

    def set_visible_system(self, system_id: Optional[int]) -> None:
        self._visible_system_id = int(system_id) if system_id is not None else None
        self._emit(f"[sim] visible system => {self._visible_system_id}")

    def enable_debug(self, enabled: bool, sink: Optional[Callable[[str], None]] = None) -> None:
        self._debug_enabled = bool(enabled)
        self._debug_sink = sink
        if enabled and not self._emitter_thread:
            self._start_emitter()
        elif not enabled and self._emitter_thread:
            # keep emitter running but it will no-op without sink
            pass

    def set_use_process_pool(self, enabled: bool) -> None:
        """Enable/disable multi-core planning."""
        want = bool(enabled)
        if want == self._use_process_pool:
            return
        self._use_process_pool = want
        self._emit(f"[sim] process_pool => {self._use_process_pool}")
        if want:
            self._ensure_pool()
        else:
            self._shutdown_pool()

    def set_max_workers(self, n: int) -> None:
        n = int(max(1, n))
        self._max_workers = n
        self._emit(f"[sim] max_workers => {self._max_workers}")
        # Rebuild the pool if currently enabled
        if self._pool is not None:
            self._shutdown_pool()
            self._ensure_pool()

    # ---- emitter thread (async logging) ----
    def _start_emitter(self) -> None:
        if self._emitter_thread and self._emitter_thread.is_alive():
            return
        self._emitter_stop.clear()
        self._emitter_thread = threading.Thread(target=self._emit_loop, name="UniverseSimLog", daemon=True)
        self._emitter_thread.start()

    def _stop_emitter(self) -> None:
        self._emitter_stop.set()
        if self._emitter_thread and self._emitter_thread.is_alive():
            # Push a sentinel to unblock
            try:
                self._log_q.put_nowait("")
            except Exception:
                pass
            self._emitter_thread.join(timeout=1.0)
        self._emitter_thread = None

    def _emit_loop(self) -> None:
        while not self._emitter_stop.is_set():
            try:
                msg = self._log_q.get(timeout=0.25)
            except queue.Empty:
                continue
            if not msg:
                continue
            sink = self._debug_sink
            if self._debug_enabled and sink:
                try:
                    sink(msg)
                except Exception:
                    # swallow logging errors
                    pass

    # ---- main loop ----
    def _run(self) -> None:
        while not self._stop.is_set():
            target_dt = 1.0 / self._tick_rate_hz
            t0 = time.perf_counter()
            try:
                self._tick_once(target_dt)
            except Exception as e:
                self._emit(f"[sim][ERROR] {e!r}")
            dt = time.perf_counter() - t0
            # Profile slow frames
            if dt > (target_dt * 1.5):
                self._emit(f"[sim][SLOW] frame={self._frame} dt={dt:.4f}s target={target_dt:.4f}s")
            sleep_for = max(0.0, target_dt - dt)
            time.sleep(sleep_for)

    def _refresh_system_ids_if_needed(self, conn) -> None:
        if self._frame >= self._ids_next_refresh_at or not self._all_system_ids:
            rows = conn.execute("SELECT system_id FROM systems").fetchall()
            self._all_system_ids = [r[0] for r in rows]
            self._ids_next_refresh_at = self._frame + self._ids_refresh_every

    def _choose_subset(self, ids: List[int], fraction: float) -> List[int]:
        if not ids or fraction >= 1.0:
            return ids[:]
        k = max(1, int(len(ids) * max(0.0, min(1.0, fraction))))
        # Random sample each frame to spread write load
        return random.sample(ids, k)

    def _ensure_pool(self) -> None:
        if not self._use_process_pool:
            return
        if ProcessPoolExecutor is None:
            self._emit("[sim][WARN] ProcessPoolExecutor not available; disabling pool.")
            self._use_process_pool = False
            return
        if self._pool is not None:
            return
        try:
            self._pool = ProcessPoolExecutor(max_workers=self._max_workers)  # type: ignore[call-arg]
            self._emit(f"[sim] process pool started (workers={self._max_workers})")
        except Exception as e:  # pragma: no cover
            self._emit(f"[sim][WARN] failed to start process pool: {e!r}")
            self._pool = None
            self._use_process_pool = False

    def _shutdown_pool(self) -> None:
        p = self._pool
        self._pool = None
        if p is not None:
            try:
                p.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._emit("[sim] process pool stopped")

    def _apply_market_factors(self, conn, factors: Dict[int, float]) -> int:
        """
        Apply per-system multiplicative price factors in chunks using a single
        UPDATE with CASE to keep it efficient. Returns total changed rows.
        """
        if not factors:
            return 0

        system_ids = list(factors.keys())
        total_changed = 0

        # Chunk to stay under SQLite param limits (~999)
        chunk_size = max(1, min(self._apply_chunk_max, 300))
        for i in range(0, len(system_ids), chunk_size):
            chunk = system_ids[i:i + chunk_size]

            # Build CASE WHEN system_id THEN factor ...
            case_parts = []
            params: List[Any] = []
            for sid in chunk:
                case_parts.append("WHEN ? THEN ?")
                params.extend([sid, float(factors[sid])])

            case_sql = "CASE system_id " + " ".join(case_parts) + " ELSE 1.0 END"

            in_clause = _make_in_clause(chunk)
            sql = f"""
                UPDATE markets
                SET local_market_price = MAX(
                    1,
                    CAST(local_market_price * {case_sql} AS INTEGER)
                )
                WHERE system_id IN {in_clause}
            """
            params.extend(chunk)  # for WHERE IN
            conn.execute(sql, tuple(params))
            total_changed += conn.total_changes

        return total_changed

    def _tick_once(self, target_dt: float) -> None:
        self._frame += 1
        conn = db.get_connection()  # thread-local; safe for this background thread

        # Cache/refresh list of system ids
        self._refresh_system_ids_if_needed(conn)

        visible = self._visible_system_id
        sim_ids = [sid for sid in self._all_system_ids if sid != visible]

        updated_counts: Dict[str, int] = {"markets": 0, "ships": 0}

        # ---- Markets: small drift, subset each frame ----
        if self._frame % self._market_every_frames == 0 and sim_ids:
            subset = self._choose_subset(sim_ids, self._market_subset_fraction)

            # If process pool enabled, plan factors off-thread then apply in one commit.
            if subset and self._use_process_pool and self._pool is not None:
                # ensure pool exists (lazy)
                self._ensure_pool()

                # Shard subset ids into roughly-even chunks
                workers = max(1, self._max_workers)
                shard_count = min(len(subset), workers * 2)
                shard_count = max(1, shard_count)
                shards: List[List[int]] = [[] for _ in range(shard_count)]
                for idx, sid in enumerate(subset):
                    shards[idx % shard_count].append(sid)

                futures = []
                for sh in shards:
                    if not sh:
                        continue
                    futures.append(self._pool.submit(_plan_market_drift_task,
                                                     (self._frame, tuple(sh), float(self._market_drift))))  # type: ignore[union-attr]

                factors: Dict[int, float] = {}
                # Gather results (small dicts)
                for fut in futures:
                    try:
                        res = fut.result(timeout=max(0.1, target_dt * 4))
                        if res:
                            factors.update(res)
                    except Exception as e:
                        self._emit(f"[sim][WARN] pool task failed: {e!r}")

                if factors:
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        updated_counts["markets"] = self._apply_market_factors(conn, factors)
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        self._emit(f"[sim][ERROR] market apply failed: {e!r}")
                else:
                    # nothing planned; skip
                    pass

            elif subset:
                # Single-threaded SQL-side random nudge (legacy path)
                in_clause = _make_in_clause(subset)
                # +/- drift (e.g., 0.5%) using DB-side random; clamp >= 1
                sql = f"""
                    UPDATE markets
                    SET local_market_price = MAX(
                        1,
                        CAST(local_market_price * (1.0 + ((ABS(RANDOM()) % 3) - 1) * ?) AS INTEGER)
                    )
                    WHERE system_id IN {in_clause}
                """
                conn.execute(sql, (float(self._market_drift), *subset))
                conn.commit()
                updated_counts["markets"] = conn.total_changes

        # ---- Facilities: (no-op placeholder) ----
        # For future: plan facility IO deltas in pool workers and apply here.

        # ---- Ship roles: cheap sample read to mimic AI step ----
        try:
            ship_roles = conn.execute(
                "SELECT ship_id, role FROM ship_roles LIMIT ?",
                (self._ships_sample_limit,),
            ).fetchall()
            updated_counts["ships"] = len(ship_roles)
        except Exception:
            pass

        # Emit a small debug line each tick (and to tick_debug)
        msg = (f"tick={self._frame} "
               f"visible={visible} "
               f"sim_systems={len(sim_ids)} "
               f"markets~={updated_counts['markets']} "
               f"ships~={updated_counts['ships']} "
               f"pool={'on' if (self._use_process_pool and self._pool is not None) else 'off'}")
        self._emit(msg)

    # ---- helpers ----
    def _emit(self, msg: str) -> None:
        # Non-blocking; drops if queue is full to protect the tick loop
        try:
            self._log_q.put_nowait(msg)
        except queue.Full:
            pass

    # ---- UI hook ----
    def publish_tick(self, **kv: Any) -> None:
        """
        Optional: the *visible* Solar view can call this once per frame to push
        a summary of on-screen work without paying logging costs when disabled.
        """
        if not self._debug_enabled:
            return
        parts = [f"{k}={v}" for k, v in kv.items()]
        line = "[ui] " + " ".join(parts) if parts else "[ui]"
        self._emit(line)


# Singleton used by UI
universe_sim = UniverseSimulator()

# Convenience wrappers (import-friendly)
def ensure_running() -> None:
    universe_sim.ensure_running()

def stop() -> None:
    universe_sim.stop()

def set_visible_system(system_id: Optional[int]) -> None:
    universe_sim.set_visible_system(system_id)

def set_tick_rate(hz: float) -> None:
    universe_sim.set_tick_rate(hz)

def enable_debug(enabled: bool, sink: Optional[Callable[[str], None]] = None) -> None:
    universe_sim.enable_debug(enabled, sink)

def publish_tick(**kv: Any) -> None:
    universe_sim.publish_tick(**kv)

def set_use_process_pool(enabled: bool) -> None:
    universe_sim.set_use_process_pool(enabled)

def set_max_workers(n: int) -> None:
    universe_sim.set_max_workers(n)
