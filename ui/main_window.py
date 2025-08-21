"""
spacegame/ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStatusBar,
    QToolBar,
    QWidget,
)

from data import db
from ui.maps.tabs import MapView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus — Space Game Prototype")
        self.resize(1280, 840)

        # --- Create log dock FIRST so early logs (from map init) have a target ---
        self._pending_logs: list[str] = []

        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        dock = QDockWidget("Log", self)
        dock.setObjectName("LogDock")
        dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

        # Central map view (passes append_log; safe now that log exists)
        self.map_view = MapView(log_fn=self.append_log)
        self.setCentralWidget(self.map_view)

        # Flush any logs that might have been queued during very early init
        if self._pending_logs:
            self.log.appendPlainText("\n".join(self._pending_logs))
            self._pending_logs.clear()

        # Status bar
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.lbl_systems = QLabel("Systems: 0", self)
        self.lbl_items = QLabel("Items: 0", self)
        self.lbl_ships = QLabel("Ships: 0", self)
        self.lbl_credits = QLabel("Credits: 0", self)
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            w.setMargin(6)
            self.status.addPermanentWidget(w)

        # Menus & toolbar
        self._create_actions()
        self._create_menus()
        self._create_toolbar()

        # Initial refresh
        self.refresh_status_counts()

    # ----- UI wiring -----
    def _create_actions(self) -> None:
        self.act_center_on_player = QAction("Center camera on player", self)
        self.act_center_on_player.triggered.connect(self.map_view.center_camera_on_player)

        self.act_reload = QAction("Reload maps", self)
        self.act_reload.triggered.connect(self.map_view.reload_all)

        self.act_quit = QAction("Quit", self)
        self.act_quit.triggered.connect(self.close)

    def _create_menus(self) -> None:
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction(self.act_quit)

        m_view = self.menuBar().addMenu("&View")
        m_map = m_view.addMenu("&Map")
        m_map.addAction(self.act_center_on_player)
        m_map.addAction(self.act_reload)

        # (Text size slider removed — map no longer renders text on-scene.)

    def _create_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.addAction(self.act_center_on_player)
        tb.addAction(self.act_reload)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

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
