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
    QWidget,
    QMenu,
)

from data import db
from game import player_status
from save.manager import SaveManager

from .maps.tabs import MapTabs
from .maps.system_leadline import SystemLeaderLineController
from .maps.galaxy_leadline import GalaxyLeaderLineController
from .widgets.status_sheet import StatusSheet
from .widgets.galaxy_system_list import GalaxySystemList
from .widgets.system_location_list import SystemLocationList

from .controllers.galaxy_location_presenter import GalaxyLocationPresenter
from .controllers.system_location_presenter import SystemLocationPresenter

# Window geometry/state (app-wide)
from .state import window_state

# Separate prefs for each leader line
from .state.leader_line_prefs import GalaxyLeaderLinePrefs, SystemLeaderLinePrefs

# Menus
from .menus.file_menu import install_file_menu
from .menus.view_menu import install_view_menu_extras, sync_panels_menu_state


def _make_map_view() -> MapTabs:
    return MapTabs()


class _LeaderPrefsAdapter:
    """
    Adapter for view_menu.install_view_menu_extras.
    Legacy hooks are mapped to our per-line prefs so existing menu items still work.
    """
    def __init__(self, win: "MainWindow") -> None:
        self._win = win

    @property
    def glow(self) -> bool:
        # Report "system" glow by default for the legacy checkbox.
        return bool(self._win._system_ll_prefs.glow)

    def pick_color(self, win: "MainWindow") -> None:
        win._prompt_pick_leader_and_color()

    def pick_width(self, win: "MainWindow") -> None:
        win._prompt_pick_leader_and_width()

    def set_glow(self, v: bool, win: "MainWindow") -> None:
        # Legacy global glow toggle -> apply to both
        win._toggle_leader_glow(bool(v))


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")

        # ---- Core refs ----
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[str] = []

        # ---- Per-leader-line prefs ----
        self._galaxy_ll_prefs = GalaxyLeaderLinePrefs("#00FF80", 2, True)
        self._system_ll_prefs = SystemLeaderLinePrefs("#00FF80", 2, True)

        # ---- Controllers ----
        self.lead: Optional[SystemLeaderLineController] = None          # System list → System map
        self.lead_galaxy: Optional[GalaxyLeaderLineController] = None   # Galaxy list → Galaxy map
        self.presenter_galaxy: Optional[GalaxyLocationPresenter] = None
        self.presenter_system: Optional[SystemLocationPresenter] = None
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

        # Legacy leader-line glow action (needed for protocol compatibility)
        self.act_leader_glow: QAction | None = None

        # Separate leader-line actions
        self.act_system_leader_glow: QAction | None = None
        self.act_galaxy_leader_glow: QAction | None = None

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
        # Keep existing View/Panel wiring
        self.leader_prefs = _LeaderPrefsAdapter(self)
        install_view_menu_extras(self, self.leader_prefs)
        # Add our separate per-line menus
    
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

    # ---------- Legacy/global glow toggle (applies to both leaders) ----------

    def _toggle_leader_glow(self, enabled: bool) -> None:
        self._system_ll_prefs.set_glow(bool(enabled), self)
        self._galaxy_ll_prefs.set_glow(bool(enabled), self)
        if self.act_leader_glow and self.act_leader_glow.isChecked() != bool(enabled):
            self.act_leader_glow.setChecked(bool(enabled))

    # ---------- Per-leader-line style application ----------

    def _apply_leader_styles(self) -> None:
        if self.lead:
            self._system_ll_prefs.apply_to(self.lead)
        if self.lead_galaxy:
            self._galaxy_ll_prefs.apply_to(self.lead_galaxy)

    def _prompt_pick_leader_and_color(self) -> None:
        # Legacy helper: ask both, system then galaxy
        c = QColorDialog.getColor(self._system_ll_prefs.color, self, "Choose System Leader Line Color")
        if c.isValid():
            self._system_ll_prefs.color = c
            self._system_ll_prefs.apply_to_parent(self)
        c2 = QColorDialog.getColor(self._galaxy_ll_prefs.color, self, "Choose Galaxy Leader Line Color")
        if c2.isValid():
            self._galaxy_ll_prefs.color = c2
            self._galaxy_ll_prefs.apply_to_parent(self)

    def _prompt_pick_leader_and_width(self) -> None:
        w, ok = QInputDialog.getInt(self, "Set System Leader Line Width", "Width (px):", self._system_ll_prefs.width, 1, 12)
        if ok:
            self._system_ll_prefs.width = int(w)
            self._system_ll_prefs.apply_to_parent(self)
        w2, ok2 = QInputDialog.getInt(self, "Set Galaxy Leader Line Width", "Width (px):", self._galaxy_ll_prefs.width, 1, 12)
        if ok2:
            self._galaxy_ll_prefs.width = int(w2)
            self._galaxy_ll_prefs.apply_to_parent(self)


    # ---- individual menu handlers ----

    def _pick_galaxy_leader_color(self) -> None:
        c = QColorDialog.getColor(self._galaxy_ll_prefs.color, self, "Choose Galaxy Leader Line Color")
        if c.isValid():
            self._galaxy_ll_prefs.color = c
            self._galaxy_ll_prefs.apply_to_parent(self)

    def _pick_galaxy_leader_width(self) -> None:
        w, ok = QInputDialog.getInt(self, "Set Galaxy Leader Line Width", "Width (px):", self._galaxy_ll_prefs.width, 1, 12)
        if ok:
            self._galaxy_ll_prefs.width = int(w)
            self._galaxy_ll_prefs.apply_to_parent(self)

    def _set_galaxy_leader_glow(self, enabled: bool) -> None:
        self._galaxy_ll_prefs.set_glow(bool(enabled), self)

    def _pick_system_leader_color(self) -> None:
        c = QColorDialog.getColor(self._system_ll_prefs.color, self, "Choose System Leader Line Color")
        if c.isValid():
            self._system_ll_prefs.color = c
            self._system_ll_prefs.apply_to_parent(self)

    def _pick_system_leader_width(self) -> None:
        w, ok = QInputDialog.getInt(self, "Set System Leader Line Width", "Width (px):", self._system_ll_prefs.width, 1, 12)
        if ok:
            self._system_ll_prefs.width = int(w)
            self._system_ll_prefs.apply_to_parent(self)

    def _set_system_leader_glow(self, enabled: bool) -> None:
        self._system_ll_prefs.set_glow(bool(enabled), self)

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

            panel_galaxy = GalaxySystemList(
                categories=["All", "System"],
                sorts=["Name A–Z", "Name Z–A", "Distance ↑", "Distance ↓", "Fuel ↑", "Fuel ↓"],
                title="Galaxy",
            )
            panel_system = SystemLocationList(
                categories=["All", "Star", "Planet", "Moon", "Station", "Warp Gate"],
                sorts=["Default View", "Name A–Z", "Name Z–A", "Distance ↑", "Distance ↓", "Fuel ↑", "Fuel ↓"],
                title="System",
            )
            # Default sorts: Galaxy uses Name A–Z; System uses Default View (grouped)
            try:
                i_g = panel_galaxy.sort.findText("Name A–Z")
                if i_g >= 0:
                    panel_galaxy.sort.setCurrentIndex(i_g)
            except Exception:
                pass
            try:
                i_s = panel_system.sort.findText("Default View")
                if i_s >= 0:
                    panel_system.sort.setCurrentIndex(i_s)
            except Exception:
                pass
            # Set initial (visual) sort indicators to match the defaults
            try:
                panel_galaxy.tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
            except Exception:
                pass
            try:
                panel_system.tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
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

            # Presenters (one per list)
            self.presenter_galaxy = GalaxyLocationPresenter(self._map_view, panel_galaxy)
            self.presenter_system = SystemLocationPresenter(self._map_view, panel_system)

            # Leader lines: attach dedicated controllers (hover-only, no click-lock)
            self.lead = SystemLeaderLineController(mv, panel_system, log=self.append_log)
            self.lead_galaxy = GalaxyLeaderLineController(mv, panel_galaxy, log=self.append_log)
            self._apply_leader_styles()

            # Wire signals
            panel_galaxy.refreshRequested.connect(lambda: self.presenter_galaxy and self.presenter_galaxy.refresh())
            panel_galaxy.clicked.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.focus(eid))
            panel_galaxy.doubleClicked.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.open(eid))
            panel_galaxy.travelHere.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.travel_here(eid))

            panel_system.refreshRequested.connect(lambda: self.presenter_system and self.presenter_system.refresh())
            panel_system.clicked.connect(lambda eid: self.presenter_system and self.presenter_system.focus(eid))
            panel_system.doubleClicked.connect(lambda eid: self.presenter_system and self.presenter_system.open(eid))
            panel_system.travelHere.connect(lambda eid: self.presenter_system and self.presenter_system.travel_here(eid))

            # Tabs hook
            tabs = getattr(mv, "tabs", None)
            if tabs is not None:
                tabs.currentChanged.connect(lambda _i: self.presenter_galaxy and self.presenter_galaxy.refresh())
                tabs.currentChanged.connect(lambda _i: self.presenter_system and self.presenter_system.refresh())
                tabs.currentChanged.connect(lambda i: self.lead and self.lead.on_tab_changed(i))
                tabs.currentChanged.connect(lambda i: self.lead_galaxy and self.lead_galaxy.on_tab_changed(i))

            self.setCentralWidget(central)
            # Attach overlays once central widget is set so viewports exist
            if self.lead:
                self.lead.attach()
            if self.lead_galaxy:
                self.lead_galaxy.attach()
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

        if self.presenter_galaxy:
            self.presenter_galaxy.refresh()
        if self.presenter_system:
            self.presenter_system.refresh()

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
        if self.presenter_galaxy:
            self.presenter_galaxy.refresh()
        if self.presenter_system:
            self.presenter_system.refresh()
        if self.lead:
            self.lead.refresh()
        if self.lead_galaxy:
            self.lead_galaxy.refresh()

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

        # Save separate leader line styles (with fallback compatibility handled on restore)
        try:
            state["galaxy_leader_color"] = self._galaxy_ll_prefs.color.name()
            state["galaxy_leader_width"] = int(self._galaxy_ll_prefs.width)
            state["galaxy_leader_glow"] = bool(self._galaxy_ll_prefs.glow)
            state["system_leader_color"] = self._system_ll_prefs.color.name()
            state["system_leader_width"] = int(self._system_ll_prefs.width)
            state["system_leader_glow"] = bool(self._system_ll_prefs.glow)
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
            if isinstance(self.location_panel_galaxy, GalaxySystemList):
                tree = self.location_panel_galaxy.tree
                state["galaxy_col_widths"] = [tree.columnWidth(i) for i in range(tree.columnCount())]
                state["galaxy_sort_text"] = str(self.location_panel_galaxy.sort.currentText())
                state["galaxy_category_index"] = int(self.location_panel_galaxy.category.currentIndex())
                state["galaxy_search"] = str(self.location_panel_galaxy.search.text())
        except Exception:
            pass

        try:
            if isinstance(self.location_panel_solar, SystemLocationList):
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

        # Restore separate leader line styles (fallback to legacy combined keys if present)
        try:
            gal_color = state.get("galaxy_leader_color") or state.get("leader_color")
            gal_width = int(state.get("galaxy_leader_width", state.get("leader_width", self._galaxy_ll_prefs.width)))
            gal_glow = state.get("galaxy_leader_glow", state.get("leader_glow", self._galaxy_ll_prefs.glow))
            if isinstance(gal_color, str) and gal_color:
                self._galaxy_ll_prefs.color = QColor(gal_color)
            self._galaxy_ll_prefs.width = max(1, gal_width)
            self._galaxy_ll_prefs.glow = bool(gal_glow)

            sys_color = state.get("system_leader_color") or state.get("leader_color")
            sys_width = int(state.get("system_leader_width", state.get("leader_width", self._system_ll_prefs.width)))
            sys_glow = state.get("system_leader_glow", state.get("leader_glow", self._system_ll_prefs.glow))
            if isinstance(sys_color, str) and sys_color:
                self._system_ll_prefs.color = QColor(sys_color)
            self._system_ll_prefs.width = max(1, sys_width)
            self._system_ll_prefs.glow = bool(sys_glow)

            # Reflect in our checkboxes if they exist
            if self.act_galaxy_leader_glow:
                self.act_galaxy_leader_glow.setChecked(self._galaxy_ll_prefs.glow)
            if self.act_system_leader_glow:
                self.act_system_leader_glow.setChecked(self._system_ll_prefs.glow)

            self._apply_leader_styles()
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
            if isinstance(self.location_panel_galaxy, GalaxySystemList):
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
            if isinstance(self.location_panel_solar, SystemLocationList):
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
