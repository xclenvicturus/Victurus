# /ui/utils/docks.py
"""
Dock Widget Utilities

Helper functions for creating and managing dock widgets with state persistence
and visibility change handling.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDockWidget


def register_persisted_dock(win, dock: QDockWidget, name: str, on_visibility_change) -> None:
    """Register a dock so MainWindow can persist its global state cleanly."""
    try:
        dock.setObjectName(name)
    except Exception:
        pass
    try:
        # Ensure we don't connect twice if called repeatedly
        try:
            dock.visibilityChanged.disconnect()
        except Exception:
            pass
        dock.visibilityChanged.connect(lambda vis: on_visibility_change(bool(vis)))
    except Exception:
        pass
    try:
        # Let MainWindow catch move/resize events to persist geometry
        dock.installEventFilter(win)
    except Exception:
        pass


def pin_for_transition(win, dock: QDockWidget, min_width: int) -> None:
    """Temporarily pin a dock's width to avoid jarring reflows during transitions."""
    try:
        win.resizeDocks([dock], [min_width], Qt.Orientation.Horizontal)
    except Exception:
        pass
    try:
        dock.setMinimumWidth(min_width)
        dock.setMaximumWidth(min_width)
        # Release the max width after a short delay so the user can resize again
        QTimer.singleShot(150, lambda: dock.setMaximumWidth(16777215))
    except Exception:
        pass
