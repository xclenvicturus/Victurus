# /ui/main_window.py
from __future__ import annotations

from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QEvent, QTimer, QByteArray
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
    QWidget,  # ← added to satisfy Protocol typing
)

from data import db
from game import player_status
from save.manager import SaveManager

from .maps.tabs import MapTabs
from .maps.leadline import LeaderLineController
from .widgets.status_sheet import StatusSheet
from .widgets.location_list import LocationList

from .controllers.dual_location_presenter import DualLocationPresenter

# Window geometry/state (app-wide)
from .state import window_state

# Menus
from .menus.file_menu import install_file_menu
from .menus.view_menu import install_view_menu_extras, sync_panels_menu_state


def _make_map_view() -> MapTabs:
    return MapTabs()


class _LeaderPrefsAdapter:
    """Adapter for view_menu.install_view_menu_extras"""
    def __init__(self, win: "MainWindow") -> None:
        self._win = win

    @property
    def glow(self) -> bool:
        return bool(self._win._leader_glow)

    def pick_color(self, win: "MainWindow") -> None:
        self._win._choose_leader_color()

    def pick_width(self, win: "MainWindow") -> None:
        self._win._choose_leader_width()

    def set_glow(self, v: bool, win: "MainWindow") -> None:
        self._win._toggle_leader_glow(bool(v))


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")

        # ---- Core refs ----
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[str] = []

        # ---- Leader-line style state ----
        self._leader_color: QColor = QColor("#00FF80")
        self._leader_width: int = 2
        self._leader_glow: bool = True

        # ---- Controllers ----
        self.lead: Optional[LeaderLineController] = None
        self.presenter_dual: Optional[DualLocationPresenter] = None
        self.travel_flow = None  # created lazily by _ensure_travel_flow()

        # ---- Splitters ----
        self._central_splitter: Optional[QSplitter] = None
        self._right_splitter: Optional[QSplitter] = None

        # ---- Location panels (typed to QWidget|None to satisfy protocol) ----
        self.location_panel_galaxy: QWidget | None = None
        self.location_panel_solar: QWidget | None = None
        self.location_panel: QWidget | None = None  # legacy alias to system list

        # ---- Actions expected by view_menu protocol (predeclare) ----
        self.act_panel_status: QAction | None = None
        self.act_panel_log: QAction | None = None
        self.act_panel_location_galaxy: QAction | None = None
        self.act_panel_location_solar: QAction | None = None
        self.act_panel_location: QAction | None = None  # legacy single list
        self.act_leader_glow: QAction | None = None

        # ---- Central placeholder while idle ----
        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        # ---- Log dock (exists at startup) ----
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        self.log_dock: QDockWidget | None = QDockWidget("Log", self)  # Optional for protocol match
        ldock = self.log_dock  # narrow type for calls below
        ldock.setObjectName("dock_Log")
        ldock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, ldock)
        self._register_dock(ldock)

        # ---- Status dock is LAZY (created after new/load) ----
        self.status_panel: StatusSheet | None = None
        self.status_dock: QDockWidget | None = None

        # ---- Status bar counters ----
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_systems = QLabel("Systems: —")
        self.lbl_items = QLabel("Items: —")
        self.lbl_ships = QLabel("Ships: —")
        self.lbl_credits = QLabel("Credits: —")
        for w in (self.lbl_systems, self.lbl_items, self.lbl_ships, self.lbl_credits):
            sb.addPermanentWidget(w)

        # ---- Menus ----
        install_file_menu(self)
        self.leader_prefs = _LeaderPrefsAdapter(self)
        install_view_menu_extras(self, self.leader_prefs)  # creates View + Panels actions

        # ---- Window state restore (global/app-wide) ----
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # ---- periodic status refresh (timer starts after start_game_ui) ----
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

        # ---- Per-save UI-state persistence ----
        SaveManager.install_ui_state_provider(self._collect_ui_state)

        # Panels menu initial sync (Status disabled until created)
        self._sync_panels_menu_state()

    # ---------- helpers: docks & leader-line ----------

    def _register_dock(self, dock: QDockWidget) -> None:
        dock.visibilityChanged.connect(
            lambda vis, d=dock: window_state.set_window_open(d.objectName(), bool(vis))
        )
        dock.visibilityChanged.connect(lambda _vis: self._sync_panels_menu_state())
        dock.installEventFilter(self)

    def _status_min_width(self) -> int:
        try:
            return max(220, self.status_panel.minimumSizeHint().width()) if self.status_panel else 220
        except Exception:
            return 220

    def _pin_status_dock_for_transition(self) -> None:
        if not self.status_dock:
            return
        w = self._status_min_width()
        try:
            self.resizeDocks([self.status_dock], [w], Qt.Orientation.Horizontal)
        except Exception:
            pass
        self.status_dock.setMinimumWidth(w)
        self.status_dock.setMaximumWidth(w)
        QTimer.singleShot(150, lambda: self.status_dock and self.status_dock.setMaximumWidth(16777215))

    def _ensure_status_dock(self) -> None:
        """Create the Status panel lazily (first time a game is started/loaded)."""
        if self.status_dock is not None:
            return
        self.status_panel = StatusSheet(self)
        dock = QDockWidget("Status", self)
        dock.setObjectName("dock_Status")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        dock.setWidget(self.status_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.status_dock = dock
        self._register_dock(dock)
        QTimer.singleShot(0, self._pin_status_dock_for_transition)
        self._sync_panels_menu_state()

    def _toggle_leader_glow(self, enabled: bool) -> None:
        self._leader_glow = bool(enabled)
        if self.act_leader_glow and self.act_leader_glow.isChecked() != self._leader_glow:
            self.act_leader_glow.setChecked(self._leader_glow)
        self._apply_leader_style()

    def _apply_leader_style(self) -> None:
        if not self.lead:
            return
        try:
            self.lead.set_line_style(
                color=self._leader_color,
                width=int(self._leader_width),
                glow_enabled=bool(self._leader_glow),
            )
        except Exception:
            pass

    def _choose_leader_color(self) -> None:
        c = QColorDialog.getColor(self._leader_color, self, "Choose Leader Line Color")
        if c.isValid():
            self._leader_color = c
            self._apply_leader_style()

    def _choose_leader_width(self) -> None:
        w, ok = QInputDialog.getInt(
            self,
            "Set Leader Line Width",
            "Width (px):",
            int(self._leader_width),
            1, 12,
        )
        if ok:
            self._leader_width = int(w)
            self._apply_leader_style()

    # ---------- Idle <-> Live ----------

    def start_game_ui(self) -> None:
        if self._map_view is None:
            # central splitter: [MapTabs | (right vertical splitter)]
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

            # ---- Right side: vertical splitter with Galaxy (top) and System (bottom) ----
            right = QSplitter(Qt.Orientation.Vertical, self)
            self._right_splitter = right

            panel_galaxy = LocationList(
                categories=["All", "System"],
                sorts=["Default View", "Name A–Z", "Name Z–A", "Distance ↑", "Distance ↓", "Fuel ↑", "Fuel ↓"],
                title="Galaxy",
            )
            panel_system = LocationList(
                categories=["All", "Star", "Planet", "Moon", "Station", "Warp Gate"],
                sorts=["Default View", "Name A–Z", "Name Z–A", "Distance ↑", "Distance ↓", "Fuel ↑", "Fuel ↓"],
                title="System",
            )
            # Default their sort to "Default View"
            for panel in (panel_galaxy, panel_system):
                try:
                    i = panel.sort.findText("Default View")
                    if i >= 0:
                        panel.sort.setCurrentIndex(i)
                except Exception:
                    pass

            # Assign to Optional QWidget-typed attributes (satisfies protocol)
            self.location_panel_galaxy = panel_galaxy
            self.location_panel_solar = panel_system
            self.location_panel = panel_system  # legacy alias

            right.addWidget(panel_galaxy)
            right.addWidget(panel_system)
            right.setStretchFactor(0, 1)
            right.setStretchFactor(1, 1)

            central.addWidget(right)
            central.setStretchFactor(0, 1)  # map
            central.setStretchFactor(1, 0)  # lists

            # Presenter (fills both lists)
            self.presenter_dual = DualLocationPresenter(self._map_view, panel_galaxy, panel_system)

            # Leader line (attach to the System list by default)
            self.lead = LeaderLineController(mv, panel_system, log=self.append_log, enable_lock=False)
            self._apply_leader_style()

            # Wire signals for both panels
            for panel in (panel_galaxy, panel_system):
                panel.refreshRequested.connect(self.presenter_dual.refresh)
                panel.clicked.connect(self.presenter_dual.focus)
                panel.doubleClicked.connect(self.presenter_dual.open)
                panel.travelHere.connect(self.presenter_dual.travel_here)

            # Tabs hook
            tabs = getattr(mv, "tabs", None)
            if tabs is not None:
                tabs.currentChanged.connect(lambda _i: self.presenter_dual and self.presenter_dual.refresh())
                tabs.currentChanged.connect(lambda i: self.lead and self.lead.on_tab_changed(i))

            self.setCentralWidget(central)
            self.lead.attach()
            self._sync_panels_menu_state()

            # ---- Restore per-save UI state (if any) ----
            try:
                ui_state = SaveManager.read_ui_state_for_active()
                if ui_state:
                    self._restore_ui_state(ui_state)
            except Exception:
                pass

        # Create Status dock lazily (first time we enter live mode)
        self._ensure_status_dock()

        # Initial refreshes
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try:
                mv_reload()
            except Exception:
                pass

        if self.presenter_dual:
            self.presenter_dual.refresh()

        self._safe_refresh_status()
        self._status_timer.start()

        # Flush pending logs
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Travel plumbing ----------

    def _ensure_travel_flow(self):
        if self.travel_flow is None:
            from game.travel_flow import TravelFlow  # local import avoids cycles
            self.travel_flow = TravelFlow(on_arrival=self._on_player_moved, log=self.append_log)
            try:
                self.travel_flow.progressTick.connect(self._safe_refresh_status)
            except Exception:
                pass
        return self.travel_flow

    def _on_player_moved(self) -> None:
        try:
            self.refresh_status_counts()
            if self.status_panel:
                self.status_panel.refresh()
        except Exception:
            pass
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try:
                mv_reload()
            except Exception:
                pass
        if self.presenter_dual:
            self.presenter_dual.refresh()
        if self.lead:
            self.lead.refresh()

    # ---------- window events & state ----------

    def eventFilter(self, obj, event):
        if isinstance(obj, QDockWidget) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self._save_window_state()
        return super().eventFilter(obj, event)

    def _save_window_state(self):
        window_state.save_mainwindow_state(self.WIN_ID, self.saveGeometry(), self.saveState())

    def moveEvent(self, e):
        super().moveEvent(e)
        self._save_window_state()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._save_window_state()

    def closeEvent(self, e):
        try:
            SaveManager.write_ui_state()
        except Exception:
            pass
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
            if self.status_panel:
                self.status_panel.refresh()
            self.refresh_status_counts()
        except Exception:
            pass

    # ---------- Panels menu sync (proxy to menu util) ----------

    def _sync_panels_menu_state(self) -> None:
        try:
            sync_panels_menu_state(self)
        except Exception:
            pass

    # ---------- per-save UI state capture/restore ----------

    def _collect_ui_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        try:
            geo_hex = bytes(self.saveGeometry().toHex().data()).decode("ascii")
            sta_hex = bytes(self.saveState().toHex().data()).decode("ascii")
            state["main_geometry_hex"] = geo_hex
            state["main_state_hex"] = sta_hex
        except Exception:
            pass

        try:
            if self._central_splitter:
                state["central_splitter_sizes"] = list(self._central_splitter.sizes())
        except Exception:
            pass

        try:
            if self._right_splitter:
                state["right_splitter_sizes"] = list(self._right_splitter.sizes())
        except Exception:
            pass

        try:
            tabs = getattr(self._map_view, "tabs", None)
            state["map_tab_index"] = int(tabs.currentIndex()) if tabs else 0
        except Exception:
            state["map_tab_index"] = 0

        # Leader line style
        try:
            state["leader_color"] = self._leader_color.name()
            state["leader_width"] = int(self._leader_width)
            state["leader_glow"] = bool(self._leader_glow)
        except Exception:
            pass

        # Location lists visibility
        try:
            state["galaxy_list_visible"] = bool(self.location_panel_galaxy.isVisible()) if self.location_panel_galaxy else True
            state["system_list_visible"] = bool(self.location_panel_solar.isVisible()) if self.location_panel_solar else True
        except Exception:
            pass

        # Panel settings + column widths
        try:
            if isinstance(self.location_panel_galaxy, LocationList):
                tree = self.location_panel_galaxy.tree
                state["galaxy_col_widths"] = [tree.columnWidth(i) for i in range(tree.columnCount())]
                state["galaxy_sort_text"] = str(self.location_panel_galaxy.sort.currentText())
                state["galaxy_category_index"] = int(self.location_panel_galaxy.category.currentIndex())
                state["galaxy_search"] = str(self.location_panel_galaxy.search.text())
        except Exception:
            pass

        try:
            if isinstance(self.location_panel_solar, LocationList):
                tree = self.location_panel_solar.tree
                state["system_col_widths"] = [tree.columnWidth(i) for i in range(tree.columnCount())]
                state["system_sort_text"] = str(self.location_panel_solar.sort.currentText())
                state["system_category_index"] = int(self.location_panel_solar.category.currentIndex())
                state["system_search"] = str(self.location_panel_solar.search.text())
        except Exception:
            pass

        return state

    def _restore_ui_state(self, state: Dict[str, Any]) -> None:
        try:
            geo_hex = state.get("main_geometry_hex")
            sta_hex = state.get("main_state_hex")
            if isinstance(geo_hex, str) and geo_hex:
                self.restoreGeometry(QByteArray.fromHex(geo_hex.encode("ascii")))
            elif isinstance(state.get("main_geometry_b64"), str):
                self.restoreGeometry(QByteArray.fromBase64(state["main_geometry_b64"].encode("ascii")))
            if isinstance(sta_hex, str) and sta_hex:
                self.restoreState(QByteArray.fromHex(sta_hex.encode("ascii")))
            elif isinstance(state.get("main_state_b64"), str):
                self.restoreState(QByteArray.fromBase64(state["main_state_b64"].encode("ascii")))
        except Exception:
            pass

        try:
            sizes = state.get("central_splitter_sizes")
            if sizes and self._central_splitter:
                self._central_splitter.setSizes([int(x) for x in sizes])
        except Exception:
            pass

        try:
            sizes = state.get("right_splitter_sizes")
            if sizes and self._right_splitter:
                self._right_splitter.setSizes([int(x) for x in sizes])
        except Exception:
            pass

        try:
            idx = int(state.get("map_tab_index", 0))
            tabs = getattr(self._map_view, "tabs", None)
            if tabs:
                tabs.setCurrentIndex(max(0, min(1, idx)))
        except Exception:
            pass

        # Leader line style
        try:
            c = state.get("leader_color")
            w = int(state.get("leader_width", self._leader_width))
            g = state.get("leader_glow", self._leader_glow)
            if isinstance(c, str) and c:
                self._leader_color = QColor(c)
            self._leader_width = max(1, w)
            self._leader_glow = bool(g)
            if self.act_leader_glow:
                self.act_leader_glow.setChecked(self._leader_glow)
            self._apply_leader_style()
        except Exception:
            pass

        # Lists visibility (apply after panels exist)
        try:
            vis_g = state.get("galaxy_list_visible", True)
            if self.location_panel_galaxy:
                self.location_panel_galaxy.setVisible(bool(vis_g))
        except Exception:
            pass

        try:
            vis_s = state.get("system_list_visible", True)
            if self.location_panel_solar:
                self.location_panel_solar.setVisible(bool(vis_s))
        except Exception:
            pass

        # Panel settings + widths
        try:
            if isinstance(self.location_panel_galaxy, LocationList):
                cat_idx = int(state.get("galaxy_category_index", 0))
                self.location_panel_galaxy.category.setCurrentIndex(cat_idx)
                sort_text = state.get("galaxy_sort_text")
                if isinstance(sort_text, str) and sort_text:
                    i = self.location_panel_galaxy.sort.findText(sort_text)
                    if i >= 0:
                        self.location_panel_galaxy.sort.setCurrentIndex(i)
                self.location_panel_galaxy.search.setText(str(state.get("galaxy_search", "")))
                widths = state.get("galaxy_col_widths")
                if isinstance(widths, list):
                    tree = self.location_panel_galaxy.tree
                    for i, w in enumerate(widths):
                        try:
                            tree.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            if isinstance(self.location_panel_solar, LocationList):
                cat_idx = int(state.get("system_category_index", 0))
                self.location_panel_solar.category.setCurrentIndex(cat_idx)
                sort_text = state.get("system_sort_text")
                if isinstance(sort_text, str) and sort_text:
                    i = self.location_panel_solar.sort.findText(sort_text)
                    if i >= 0:
                        self.location_panel_solar.sort.setCurrentIndex(i)
                self.location_panel_solar.search.setText(str(state.get("system_search", "")))
                widths = state.get("system_col_widths")
                if isinstance(widths, list):
                    tree = self.location_panel_solar.tree
                    for i, w in enumerate(widths):
                        try:
                            tree.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass
