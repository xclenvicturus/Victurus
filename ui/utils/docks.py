# /ui/utils/docks.py

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDockWidget

def register_persisted_dock(win, dock: QDockWidget, name: str, on_visibility_change) -> None:
    dock.setObjectName(name)
    dock.visibilityChanged.connect(lambda vis: on_visibility_change(bool(vis)))
    dock.installEventFilter(win)  # let MainWindow catch move/resize to persist global state

def pin_for_transition(win, dock: QDockWidget, min_width: int) -> None:
    try:
        win.resizeDocks([dock], [min_width], Qt.Orientation.Horizontal)
    except Exception:
        pass
    dock.setMinimumWidth(min_width)
    dock.setMaximumWidth(min_width)
    QTimer.singleShot(150, lambda: dock.setMaximumWidth(16777215))
