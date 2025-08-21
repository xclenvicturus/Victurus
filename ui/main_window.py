"""
ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.

Supports:
- Idle boot (no DB work) until a save is New/Loaded
- File menu: New Game | Save | Save As… | Load Game
- Window state persistence to Documents/Victurus_game/Config/ui_windows.json
- Status Sheet dock with player/ship bars and jump range
- Green text on current location in selection lists
- Status dock stays at its minimum width unless the user drags it wider
"""

from __future__ import annotations

from typing import Optional, cast

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStatusBar,
    QWidget,
)

from data import db
from .menus.file_menu import install_file_menu
from .state import window_state
from .panels.status_sheet import StatusSheet
from .maps.highlighting import apply_green_text_to_current_location


# Lazy import MapView to avoid DB usage at idle
def _make_map_view(log_fn):
    from .maps.tabs import MapView
    return MapView(log_fn)


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[QWidget] = None
        self._pending_logs = []

        # --- Central placeholder (idle) ---
        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        # --- Log dock ---
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        log_dock = QDockWidget("Log", self)
        log_dock.setObjectName("dock_Log")
        log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self._register_dock(log_dock)

        # --- Status Sheet dock ---
        self.status_panel = StatusSheet(self)
        self.status_dock = QDockWidget("Status", self)
        self.status_dock.setObjectName("dock_Status")
        self.status_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.status_dock.setWidget(self.status_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.status_dock)
        self._register_dock(self.status_dock)

        # --- Status bar ---
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_systems = QLabel("Systems: —")
        self.lbl_items = QLabel("Items: —")
        self.lbl_ships = QLabel("Ships: —")
        self.lbl_credits = QLabel("Credits: —")
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            sb.addPermanentWidget(w)

        # --- Menus ---
        menubar = self.menuBar()
        # Settings menu removed (no animation toggle needed)

        # File menu (New/Load/Save)
        install_file_menu(self)

        # Restore saved geometry/state
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # After restore, keep Status dock narrow for this pass
        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # periodic status refresh (only meaningful once a save is active)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

    # ---------- helper ----------

    def _register_dock(self, dock: QDockWidget) -> None:
        dock.visibilityChanged.connect(
            lambda vis, d=dock: window_state.set_window_open(d.objectName() or "dock", bool(vis))
        )
        dock.installEventFilter(self)

    def eventFilter(self, obj, event):
        if isinstance(obj, QDockWidget) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())
        return super().eventFilter(obj, event)

    # ----- size management for Status dock -----

    def _status_min_width(self) -> int:
        # Reasonable floor; respect panel’s own hint
        return max(220, self.status_panel.minimumSizeHint().width())

    def _pin_status_dock_for_transition(self) -> None:
        """
        Keep Status dock at min width during layout transitions (restore, New/Load).
        We:
          1) resize the dock to min width,
          2) temporarily set maximumWidth to that min so splitter can't expand it,
          3) release the max after a tick so player can drag it wider.
        """
        w = self._status_min_width()
        try:
            self.resizeDocks([self.status_dock], [w], Qt.Orientation.Horizontal)
        except Exception:
            pass

        self.status_dock.setMinimumWidth(w)
        self.status_dock.setMaximumWidth(w)
        # Release the cap shortly after layout settles; player can then drag it wider
        QTimer.singleShot(150, lambda: self.status_dock.setMaximumWidth(16777215))

    # ---------- Idle <-> Live transitions ----------

    def start_game_ui(self) -> None:
        """Switch from idle to live map UI and refresh counts."""
        if self._map_view is None:
            self._map_view = cast(QWidget, _make_map_view(self.append_log))
            self.setCentralWidget(self._map_view)

        self.refresh_status_counts()
        self.status_panel.refresh()
        apply_green_text_to_current_location(self._map_view)  # color current location text
        self._status_timer.start()

        # After switching central widget, pin the status dock so it doesn't jump
        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # Flush any pending logs captured before log constructed
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Window state persistence ----------

    def moveEvent(self, e):
        super().moveEvent(e)
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())

    def closeEvent(self, e):
        self._status_timer.stop()
        window_state.set_window_open(self.WIN_ID, False)
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())
        super().closeEvent(e)

    # ---------- Logging & stats ----------

    def append_log(self, msg: str) -> None:
        if hasattr(self, "log") and isinstance(self.log, QPlainTextEdit):
            self.log.appendPlainText(str(msg))
        else:
            self._pending_logs.append(str(msg))

    def refresh_status_counts(self) -> None:
        try:
            counts = db.get_counts()
            self.lbl_systems.setText(f"Systems: {counts.get('systems', 0)}")
            self.lbl_items.setText(f"Items: {counts.get('items', 0)}")
            self.lbl_ships.setText(f"Ships: {counts.get('ships', 0)}")
            ps = db.get_player_summary()
            self.lbl_credits.setText(f"Credits: {ps.get('credits', 0)}")
        except Exception:
            self.lbl_systems.setText("Systems: —")
            self.lbl_items.setText("Items: —")
            self.lbl_ships.setText("Ships: —")
            self.lbl_credits.setText("Credits: —")

    def _safe_refresh_status(self) -> None:
        try:
            self.status_panel.refresh()
            self.refresh_status_counts()
            if self._map_view is not None:
                apply_green_text_to_current_location(self._map_view)  # keep text up to date
        except Exception:
            pass
