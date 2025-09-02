# /main.py
"""
Victurus Game - Main Entry Point

A space exploration and trading game built with Python and PySide6/Qt.
This module initializes the application, sets up logging, and starts the main window.
"""

from __future__ import annotations

# --- ensure project root is on sys.path BEFORE importing ui.* ---
import sys
import os
import pathlib
import multiprocessing
import logging

# Configure comprehensive logging system
ROOT = pathlib.Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Set up comprehensive logging
try:
    from game_controller.log_config import setup_victurus_logging
    log_config = setup_victurus_logging(LOG_DIR)
    logging.getLogger('system.startup').info("Victurus logging system initialized")
except Exception as e:
    # Fallback to basic logging if comprehensive logging fails
    log_file = LOG_DIR / "ui_state_debug.log"
    try:
        handlers = []
        try:
            fh = logging.FileHandler(str(log_file), encoding='utf-8')
            handlers.append(fh)
        except Exception:
            pass
        if handlers:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s', handlers=handlers)
        else:
            logging.basicConfig(level=logging.WARNING)
        logging.getLogger('PySide6').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ----------------------------------------------------------------

from ui.main_window import MainWindow
from ui.state.ui_state_manager import initialize_ui_state
from ui.error_handler import install_error_handler
from ui.dialogs.error_reporter_dialog import ErrorReporterDialog

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
    # Configure HiDPI BEFORE creating any Qt applications or importing Qt modules
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

    # Install global error handler
    error_handler = install_error_handler()
    
    # Configure the simulator before the UI spins up.
    _configure_sim()

    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    # Configure error handler with app instance and dialog class
    error_handler.set_app_instance(app)
    error_handler.set_error_dialog_class(ErrorReporterDialog)
    
    # Initialize UI state system - check for config file and create defaults if needed
    config_existed = initialize_ui_state()
    if not config_existed:
        logging.getLogger(__name__).info("Created new UI state configuration with defaults")
    
    try:
        win = MainWindow()
        error_handler.set_main_window(win)
        win.show()
        return app.exec()
    except Exception as e:
        # Handle startup errors
        error_handler.handle_error(e, "Application startup")
        return 1
    finally:
        # Cleanup
        error_handler.uninstall()


if __name__ == "__main__":
    # Needed for Windows spawn (and when freezing into an exe)
    multiprocessing.freeze_support()
    raise SystemExit(main())
