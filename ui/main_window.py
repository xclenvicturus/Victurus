from __future__ import annotations

from typing import Optional, List

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStatusBar,
    QSplitter,
    QColorDialog,
    QInputDialog,
    QMenuBar,
    QMenu,
)

from data import db
from game import player_status
from .menus.file_menu import install_file_menu
from .state import window_state
from .widgets.status_sheet import StatusSheet
from .widgets.location_list import LocationList
from .maps.tabs import MapTabs

# controllers
from .leadline_controller import LeaderLineController
from .location_presenter import LocationPresenter
from .map_actions import MapActions
from .travel_flow import TravelFlow


def _make_map_view() -> MapTabs:
    return MapTabs()


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[str] = []

        # Leader-line style state (UI-adjustable)
        self._leader_color: QColor = QColor(0, 255, 128)
        self._leader_width: int = 2

        # Central placeholder (idle)
        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        # Log dock
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        log_dock = QDockWidget("Log", self)
        log_dock.setObjectName("dock_Log")
        log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self._register_dock(log_dock)

        # Status Sheet dock
        self.status_panel = StatusSheet(self)
        self.status_dock = QDockWidget("Status", self)
        self.status_dock.setObjectName("dock_Status")
        self.status_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.status_dock.setWidget(self.status_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.status_dock)
        self._register_dock(self.status_dock)

        # Status bar
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_systems = QLabel("Systems: —")
        self.lbl_items = QLabel("Items: —")
        self.lbl_ships = QLabel("Ships: —")
        self.lbl_credits = QLabel("Credits: —")
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            sb.addPermanentWidget(w)

        # Menus
        install_file_menu(self)
        self._install_view_menu_extras()

        # Window state restore
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # Keep status dock narrow on first layout pass
        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # periodic refresh
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

        # central UI built in start_game_ui()
        self._central_splitter: Optional[QSplitter] = None
        self.location_panel: Optional[LocationList] = None

        # controllers (created in start_game_ui)
        self.lead: Optional[LeaderLineController] = None
        self.presenter: Optional[LocationPresenter] = None
        self.map_actions: Optional[MapActions] = None      # <-- renamed (avoid QWidget.actions clash)
        self.travel_flow: Optional[TravelFlow] = None

    # ---------- menus: View → Leader Line ----------
    def _install_view_menu_extras(self) -> None:
        mb = self.menuBar()
        if not isinstance(mb, QMenuBar):
            return  # safety

        # Find or create the "&View" menu
        view_menu: QMenu | None = None
        for a in mb.actions():
            m = a.menu()
            if isinstance(m, QMenu) and a.text().replace("&", "").lower() == "view":
                view_menu = m
                break
        if view_menu is None:
            view_menu = mb.addMenu("&View")  # QMenuBar.addMenu returns QMenu

        # Create a real submenu object (avoid the str overload)
        ll_menu = QMenu("Leader Line", self)
        view_menu.addMenu(ll_menu)

        act_color = QAction("Set Color…", self)
        act_color.triggered.connect(self._choose_leader_color)
        ll_menu.addAction(act_color)

        act_width_inc = QAction("Increase Width", self)
        act_width_inc.setShortcut("Ctrl++")
        act_width_inc.triggered.connect(lambda: self._nudge_leader_width(+1))
        ll_menu.addAction(act_width_inc)

        act_width_dec = QAction("Decrease Width", self)
        act_width_dec.setShortcut("Ctrl+-")
        act_width_dec.triggered.connect(lambda: self._nudge_leader_width(-1))
        ll_menu.addAction(act_width_dec)

        act_width_set = QAction("Set Width…", self)
        act_width_set.triggered.connect(self._choose_leader_width)
        ll_menu.addAction(act_width_set)

    def _apply_leader_style(self) -> None:
        if self.lead:
            self.lead.set_line_style(color=self._leader_color, width=self._leader_width)

    def _choose_leader_color(self) -> None:
        c = QColorDialog.getColor(self._leader_color, self, "Choose Leader Line Color")
        if c.isValid():
            self._leader_color = c
            self._apply_leader_style()

    def _nudge_leader_width(self, delta: int) -> None:
        self._leader_width = max(1, self._leader_width + int(delta))
        self._apply_leader_style()

    def _choose_leader_width(self) -> None:
        # getInt(parent, title, label, value=0, min=-2147483647, max=2147483647, step=1, ok=None, ...)
        w, ok = QInputDialog.getInt(
            self,
            "Set Leader Line Width",
            "Width (px):",
            self._leader_width,
            1,      # min
            12,     # max
            1,      # step
        )
        if ok:
            self._leader_width = int(w)
            self._apply_leader_style()

    # ---------- helpers ----------

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
        try:
            self.resizeDocks([self.status_dock], [w], Qt.Orientation.Horizontal)
        except Exception:
            pass
        self.status_dock.setMinimumWidth(w)
        self.status_dock.setMaximumWidth(w)
        QTimer.singleShot(150, lambda: self.status_dock.setMaximumWidth(16777215))

    # ---------- Idle <-> Live ----------

    def start_game_ui(self) -> None:
        if self._map_view is None:
            # central splitter: [MapTabs | LocationList]
            central = QSplitter(Qt.Orientation.Horizontal, self)
            self._central_splitter = central

            mv = _make_map_view()
            self._map_view = mv

            # optional MapTabs.logMessage
            log_sig = getattr(mv, "logMessage", None)
            connect = getattr(log_sig, "connect", None)
            if callable(connect):
                try:
                    connect(self.append_log)
                except Exception:
                    pass

            central.addWidget(mv)

            # Right panel
            panel = LocationList(
                categories=["All", "System", "Star", "Planet", "Station", "Warp Gate"],
                sorts=["Name A–Z", "Name Z–A", "Distance", "X", "Y"],
                title="Locations",
            )
            self.location_panel = panel
            central.addWidget(panel)
            central.setStretchFactor(0, 1)
            central.setStretchFactor(1, 0)

            # Presenter
            self.presenter = LocationPresenter(mv, panel)

            # Actions (focus/open/travel)
            self.map_actions = MapActions(mv, begin_travel_cb=lambda kind, ident: self._begin_travel(kind, ident))

            # Leader line (hover; set enable_lock=True if you want click-lock)
            self.lead = LeaderLineController(mv, panel, log=self.append_log, enable_lock=False)

            # Apply initial style to leader line
            self._apply_leader_style()

            # Wire signals
            panel.refreshRequested.connect(self.presenter.refresh)
            panel.clicked.connect(self.map_actions.focus)
            panel.doubleClicked.connect(self.map_actions.open)
            panel.travelHere.connect(self.map_actions.travel_here)

            tabs = getattr(mv, "tabs", None)
            if tabs is not None:
                tabs.currentChanged.connect(lambda _i: self.presenter and self.presenter.refresh())
                tabs.currentChanged.connect(lambda i: self.lead and self.lead.on_tab_changed(i))

            self.setCentralWidget(central)

            # Create leader overlay + first refresh
            self.lead.attach()

        # Initial refresh
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try:
                mv_reload()
            except Exception:
                pass

        if self.presenter:
            self.presenter.refresh()

        self._safe_refresh_status()
        self._status_timer.start()

        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # Flush pending logs
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Travel plumbing ----------

    def _ensure_travel_flow(self) -> TravelFlow:
        if self.travel_flow is None:
            # arrival callback reloads maps + UI
            self.travel_flow = TravelFlow(on_arrival=self._on_player_moved, log=self.append_log)
        return self.travel_flow

    def _begin_travel(self, kind: str, ident: int) -> None:
        self._ensure_travel_flow().begin(kind, ident)

    def _on_player_moved(self) -> None:
        """Refresh UI and maps after travel completes."""
        try:
            self.refresh_status_counts()
            self.status_panel.refresh()
        except Exception:
            pass
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try:
                mv_reload()
            except Exception:
                pass
        if self.presenter:
            self.presenter.refresh()
        if self.lead:
            self.lead.refresh()

    # ---------- window events & state ----------

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

    # ---------- logging & stats ----------

    def append_log(self, msg: str) -> None:
        if hasattr(self, "log"):
            self.log.appendPlainText(str(msg))
        else:
            self._pending_logs.append(str(msg))

    def refresh_status_counts(self) -> None:
        try:
            counts = db.get_counts()
            status = player_status.get_status_snapshot()
            self.lbl_systems.setText(f"Systems: {counts.get('systems', '—')}")
            self.lbl_items.setText(f"Items: {counts.get('items', '—')}")
            self.lbl_ships.setText(f"Ships: {counts.get('ships', '—')}")
            self.lbl_credits.setText(f"Credits: {status.get('credits', 0):,}")
        except Exception:
            self.lbl_systems.setText("Systems: —")
            self.lbl_items.setText("Items: —")
            self.lbl_ships.setText("Ships: —")
            self.lbl_credits.setText("Credits: —")

    def _safe_refresh_status(self) -> None:
        try:
            self.status_panel.refresh()
            self.refresh_status_counts()
            # DO NOT reload maps here — it overrides the user's manually opened system.
            # mv_reload = getattr(self._map_view, "reload_all", None)
            # if callable(mv_reload):
            #     try: mv_reload()
            #     except Exception: pass
        except Exception:
            pass
