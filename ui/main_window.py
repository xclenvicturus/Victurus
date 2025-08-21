"""
ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStatusBar,
)

from data import db
from ui.maps.tabs import MapView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self.resize(1280, 840)

        # --- Settings ---
        self._settings = QSettings("Victurus", "App")
        self._animations_enabled = bool(self._settings.value("ui/animationsEnabled", True, type=bool))

        # --- Log dock FIRST (capture early logs) ---
        self._pending_logs: list[str] = []
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        dock = QDockWidget("Log", self)
        dock.setObjectName("LogDock")
        dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

        # --- Central map tabs ---
        self.tabs = MapView(log_fn=self.append_log)
        self.setCentralWidget(self.tabs)

        # --- Status bar (counts + credits) ---
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_systems = QLabel("Systems: 0")
        self.lbl_items = QLabel("Items: 0")
        self.lbl_ships = QLabel("Ships: 0")
        self.lbl_credits = QLabel("Credits: 0")
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            sb.addPermanentWidget(w)
        self.refresh_status_counts()

        # --- Menus ---
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("&Settings")
        self.actAnimations = QAction("Enable &Animations", self, checkable=True)
        self.actAnimations.setChecked(self._animations_enabled)
        self.actAnimations.toggled.connect(self._on_toggle_animations)
        settings_menu.addAction(self.actAnimations)

        # Apply initial animation setting
        self._apply_animation_setting()

        # Flush cached logs (if any)
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ----- Menu handlers -----
    def _apply_animation_setting(self) -> None:
        try:
            for v in (self.tabs.galaxy, self.tabs.solar):
                if hasattr(v, "set_animations_enabled"):
                    v.set_animations_enabled(self._animations_enabled)
        except Exception:
            pass

    def _on_toggle_animations(self, enabled: bool) -> None:
        self._animations_enabled = bool(enabled)
        self._settings.setValue("ui/animationsEnabled", self._animations_enabled)
        self._apply_animation_setting()

    # ----- Helpers -----
    def append_log(self, msg: str) -> None:
        # Be robust if called extremely early
        if hasattr(self, "log") and isinstance(self.log, QPlainTextEdit):
            self.log.appendPlainText(str(msg))
        else:
            self._pending_logs.append(str(msg))

    def refresh_status_counts(self) -> None:
        counts = db.get_counts()
        self.lbl_systems.setText(f"Systems: {counts.get('systems', 0)}")
        self.lbl_items.setText(f"Items: {counts.get('items', 0)}")
        self.lbl_ships.setText(f"Ships: {counts.get('ships', 0)}")
        ps = db.get_player_summary()
        self.lbl_credits.setText(f"Credits: {ps.get('credits', 0)}")
