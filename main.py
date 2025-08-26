# /main.py

from __future__ import annotations

# --- ensure project root is on sys.path BEFORE importing ui.* ---
import sys
import os
import pathlib
import multiprocessing

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ----------------------------------------------------------------

# Optional HiDPI behavior (Qt6-safe, no deprecated AA_* attributes)
try:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtCore import Qt
    # In Qt6, high-DPI scaling is enabled by default. We can still set a rounding policy.
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
except Exception:
    # Best-effort; defaults are fine if this isn't available.
    pass

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Simulator config (env-driven so we avoid code edits per machine)
def _configure_sim() -> None:
    from game_controller.sim_loop import (
        ensure_running,
        set_use_process_pool,
        set_max_workers,
        set_tick_rate,
    )

    # Toggle pool with env var: VICTURUS_USE_POOL=1
    use_pool_env = os.getenv("VICTURUS_USE_POOL", "0").strip().lower()
    use_pool = use_pool_env in ("1", "true", "yes", "on")

    # Workers: default = max(1, os.cpu_count() - 1)
    try:
        default_workers = max(1, (os.cpu_count() or 2) - 1)
        workers = int(os.getenv("VICTURUS_POOL_WORKERS", str(default_workers)))
        if workers < 1:
            workers = 1
    except Exception:
        workers = max(1, (os.cpu_count() or 2) - 1)

    # Tick Hz
    try:
        tick_hz = float(os.getenv("VICTURUS_TICK_HZ", "2.0"))
        if tick_hz < 1.0:
            tick_hz = 1.0
    except Exception:
        tick_hz = 2.0

    # Apply settings
    set_tick_rate(tick_hz)
    set_max_workers(workers)
    set_use_process_pool(use_pool)
    ensure_running()  # harmless if already running


def main() -> int:
    # Configure the simulator before the UI spins up.
    _configure_sim()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    # Needed for Windows spawn (and when freezing into an exe)
    multiprocessing.freeze_support()
    raise SystemExit(main())
