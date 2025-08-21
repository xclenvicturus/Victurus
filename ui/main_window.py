"""
ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.

Supports:
- Idle boot (no DB work) until a save is New/Loaded
- File menu: New Game | Save | Save As… | Load Game
- Window state persistence to Documents/Victurus_game/Config/ui_windows.json
"""

from __future__ import annotations

from typing import Optional, cast

from PySide6.QtCore import Qt, QEvent
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
from ui.menus.file_menu import install_file_menu
from ui.state import window_state


# Lazy import MapView to avoid DB usage at idle
def _make_map_view(log_fn):
    from ui.maps.tabs import MapView
    return MapView(log_fn)


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[QWidget] = None
        self._animations_enabled = True
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
        # Settings menu (preserve previous toggle if existed)
        settings_menu = menubar.addMenu("&Settings")
        self.actAnimations = QAction("Enable &Animations", self, checkable=True)
        self.actAnimations.setChecked(self._animations_enabled)
        self.actAnimations.toggled.connect(self._on_toggle_animations)
        settings_menu.addAction(self.actAnimations)

        # File menu (New/Load/Save)
        install_file_menu(self)

        # Restore window layout if possible
        window_state.restore_mainwindow_state(self, self.WIN_ID)

        # Mark main window open
        window_state.set_window_open(self.WIN_ID, True)

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

    # ---------- Idle <-> Live transitions ----------

    def start_game_ui(self) -> None:
        """Switch from idle to live map UI and refresh counts."""
        if self._map_view is None:
            self._map_view = cast(QWidget, _make_map_view(self.append_log))
            self.setCentralWidget(self._map_view)
        self.refresh_status_counts()
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
        window_state.set_window_open(self.WIN_ID, False)
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())
        super().closeEvent(e)

    # ---------- Logging & stats ----------

    def append_log(self, msg: str) -> None:
        # Be robust if called extremely early
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
            # No active DB yet
            self.lbl_systems.setText("Systems: —")
            self.lbl_items.setText("Items: —")
            self.lbl_ships.setText("Ships: —")
            self.lbl_credits.setText("Credits: —")

    # ---------- Settings ----------

    def _on_toggle_animations(self, enabled: bool) -> None:
        self._animations_enabled = bool(enabled)
        self.append_log(f"Animations {'enabled' if enabled else 'disabled'}.")
