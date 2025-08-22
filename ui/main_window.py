"""
ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.
"""

from __future__ import annotations

from typing import Optional, cast

from PySide6.QtCore import Qt, QEvent, QTimer
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
from .widgets.status_sheet import StatusSheet
from .maps.highlighting import apply_green_text_to_current_location
from .maps.tabs import MapView


def _make_map_view(log_fn):
    return MapView(log_fn)


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[MapView] = None
        self._pending_logs = []

        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        log_dock = QDockWidget("Log", self)
        log_dock.setObjectName("dock_Log")
        log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self._register_dock(log_dock)

        self.status_panel = StatusSheet(self)
        self.status_dock = QDockWidget("Status", self)
        self.status_dock.setObjectName("dock_Status")
        self.status_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.status_dock.setWidget(self.status_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.status_dock)
        self._register_dock(self.status_dock)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_systems = QLabel("Systems: —")
        self.lbl_items = QLabel("Items: —")
        self.lbl_ships = QLabel("Ships: —")
        self.lbl_credits = QLabel("Credits: —")
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            sb.addPermanentWidget(w)

        install_file_menu(self)

        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

    def _register_dock(self, dock: QDockWidget) -> None:
        dock.visibilityChanged.connect(
            lambda vis, d=dock: window_state.set_window_open(d.objectName(), bool(vis))
        )
        dock.installEventFilter(self)

    def eventFilter(self, obj, event):
        if isinstance(obj, QDockWidget) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self._save_window_state()
        return super().eventFilter(obj, event)

    def _status_min_width(self) -> int:
        return max(220, self.status_panel.minimumSizeHint().width())

    def _pin_status_dock_for_transition(self) -> None:
        w = self._status_min_width()
        self.resizeDocks([self.status_dock], [w], Qt.Orientation.Horizontal)
        self.status_dock.setMinimumWidth(w)
        self.status_dock.setMaximumWidth(w)
        QTimer.singleShot(150, lambda: self.status_dock.setMaximumWidth(16777215))

    def start_game_ui(self) -> None:
        if self._map_view is None:
            self._map_view = _make_map_view(self.append_log)
            self.setCentralWidget(self._map_view)
            self._map_view.playerMoved.connect(self._safe_refresh_status)

        self._map_view.reload_all()
        self._safe_refresh_status()
        self._status_timer.start()

        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()
        
    def _save_window_state(self):
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())

    def moveEvent(self, e):
        super().moveEvent(e)
        self._save_window_state()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._save_window_state()

    def closeEvent(self, e):
        self._status_timer.stop()
        window_state.set_window_open(self.WIN_ID, False)
        self._save_window_state()
        super().closeEvent(e)

    def append_log(self, msg: str) -> None:
        if hasattr(self, "log"):
            self.log.appendPlainText(str(msg))
        else:
            self._pending_logs.append(str(msg))

    def refresh_status_counts(self) -> None:
        try:
            counts = db.get_counts()
            status = db.get_status_snapshot()
            self.lbl_systems.setText(f"Systems: {counts.get('systems', '—')}")
            self.lbl_items.setText(f"Items: {counts.get('items', '—')}")
            self.lbl_ships.setText(f"Ships: {counts.get('ships', '—')}")
            self.lbl_credits.setText(f"Credits: {status.get('credits', '—'):,}")
        except Exception:
            self.lbl_systems.setText("Systems: —")
            self.lbl_items.setText("Items: —")
            self.lbl_ships.setText("Ships: —")
            self.lbl_credits.setText("Credits: —")

    def _safe_refresh_status(self) -> None:
        try:
            self.status_panel.refresh()
            self.refresh_status_counts()
            if self._map_view:
                self._map_view.update_lists()
                apply_green_text_to_current_location(self._map_view)
        except Exception:
            pass