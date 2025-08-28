# /game_controller/config.py

# Centralized configuration for Victurus. Values are environment-driven,
# with safe defaults. Import and use wherever needed.
#
# Example env:
#   VICTURUS_TICK_HZ=2.0
#   VICTURUS_USE_POOL=1
#   VICTURUS_POOL_WORKERS=6
#   VICTURUS_MARKET_DRIFT=0.005
#   VICTURUS_MARKET_SUBSET=0.25
#   VICTURUS_IDS_REFRESH=300
#   VICTURUS_APPLY_CHUNK_MAX=250
#   VICTURUS_DB_PATH=/abs/path/to/game.db
#   VICTURUS_LOG_LEVEL=INFO
#   VICTURUS_LOG_FILE=victurus.log
#   VICTURUS_LOG_JSON=0

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


__all__ = ["Config", "load", "apply_to_sim"]


def _parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    v = val.strip().lower()
    return v in ("1", "true", "yes", "on")


def _parse_float(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, str(default)))
    except Exception:
        return default


def _parse_int(env: str, default: int) -> int:
    try:
        return int(os.getenv(env, str(default)))
    except Exception:
        return default


@dataclass(frozen=True)
class Config:
    # Simulator
    tick_hz: float = 2.0
    use_process_pool: bool = False
    pool_workers: int = 0  # 0 means derive from cpu_count()-1 at runtime
    market_drift: float = 0.005
    market_subset_fraction: float = 0.25
    ids_refresh_every: int = 300
    apply_chunk_max: int = 250

    # Paths
    db_path: Optional[Path] = None

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    log_json: bool = False


def load() -> Config:
    # Workers default to cpu_count() - 1
    try:
        default_workers = max(1, (os.cpu_count() or 2) - 1)
    except Exception:
        default_workers = 1

    db_path_str = os.getenv("VICTURUS_DB_PATH", "").strip()
    db_path = Path(db_path_str) if db_path_str else None

    return Config(
        tick_hz=_parse_float("VICTURUS_TICK_HZ", 2.0),
        use_process_pool=_parse_bool(os.getenv("VICTURUS_USE_POOL"), False),
        pool_workers=_parse_int("VICTURUS_POOL_WORKERS", default_workers),
        market_drift=_parse_float("VICTURUS_MARKET_DRIFT", 0.005),
        market_subset_fraction=_parse_float("VICTURUS_MARKET_SUBSET", 0.25),
        ids_refresh_every=_parse_int("VICTURUS_IDS_REFRESH", 300),
        apply_chunk_max=_parse_int("VICTURUS_APPLY_CHUNK_MAX", 250),
        db_path=db_path,
        log_level=os.getenv("VICTURUS_LOG_LEVEL", "INFO").upper(),
        log_file=os.getenv("VICTURUS_LOG_FILE", "").strip() or None,
        log_json=_parse_bool(os.getenv("VICTURUS_LOG_JSON"), False),
    )


# Optional helper to apply core settings to the running simulator
def apply_to_sim(sim) -> None:
    """
    Apply a subset of config to UniverseSimulator without importing UI.
    Only uses methods the simulator actually exposes.
    """
    cfg = load()
    try:
        if hasattr(sim, "set_tick_rate"):
            sim.set_tick_rate(cfg.tick_hz)
    except Exception:
        pass
    try:
        if hasattr(sim, "set_max_workers"):
            sim.set_max_workers(max(1, int(cfg.pool_workers or max(1, (os.cpu_count() or 2) - 1))))
    except Exception:
        pass
    try:
        if hasattr(sim, "set_use_process_pool"):
            sim.set_use_process_pool(bool(cfg.use_process_pool))
    except Exception:
        pass
    # The simulator currently keeps its own defaults for drift/subset/chunk sizes.
    # If you expose setters later (e.g., set_market_drift / set_subset_fraction),
    # you can wire them here similarly.
