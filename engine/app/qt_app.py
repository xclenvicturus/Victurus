# Victurus/engine/app/qt_app.py
"""
Qt shell bootstrap.
- Builds QApplication and MainWindow
- Provides clear SCAFFOLD points to inject your existing services/controllers
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# SCAFFOLD: we import the new Qt UI MainWindow
from engine.qtui.main_window import MainWindow  # central window with docks/map

# Optional: if you want to pass context/services later, define a light struct
class AppContext:  # SCAFFOLD: minimal context used by Qt shell
    def __init__(self, save_root: Path):
        self.save_root = save_root
        # TODO: attach your Settings, EventBus, services, etc.


def run_qt_app(save_root: Optional[str] = None) -> int:
    app = QApplication(sys.argv)

    # SCAFFOLD: assemble a very small context
    save_root_path = Path(save_root or "./saves").resolve()
    ctx = AppContext(save_root=save_root_path)

    # Create and show the main window
    win = MainWindow(ctx=ctx)
    win.resize(1280, 800)
    win.show()

    # SCAFFOLD: demo "economy tick" timer (replace with your real tick later)
    tick = QTimer(win)
    tick.setInterval(1000)  # 1s
    tick.timeout.connect(lambda: win.log_panel.append_log("system", "tick", "Economy tick…"))  # SCAFFOLD
    tick.start()

    return app.exec()
