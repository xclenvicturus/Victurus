# /ui/main_window.py

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

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
from save.save_manager import SaveManager
from save.ui_config import install_ui_state_provider, persist_provider_snapshot
from ui.state.ui_state_manager import get_ui_state_manager
from game_controller.log_config import get_ui_logger

from .maps.tabs import MapTabs
from .maps.travel_coordinator import TravelCoordinator
from .maps.system_leadline import SystemLeaderLineController
from .maps.galaxy_leadline import GalaxyLeaderLineController
from .widgets.status_sheet import StatusSheet
from .widgets.galaxy_system_list import GalaxySystemList
from .widgets.system_location_list import SystemLocationList

from .controllers.galaxy_location_presenter import GalaxyLocationPresenter
from .controllers.system_location_presenter import SystemLocationPresenter

# Window geometry/state (app-wide)
from .state import window_state
from save.ui_state_tracer import append_event

# Separate prefs for each leader line
from .state.lead_line_prefs import GalaxyLeaderLinePrefs, SystemLeaderLinePrefs

# Menus
from .menus.file_menu import install_file_menu
from .menus.view_menu import install_view_menu_extras, sync_panels_menu_state

# Set up UI logger
logger = get_ui_logger('main_window')


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
        # Prevent programmatic startup events from triggering writes.
        try:
            from save.save_manager import SaveManager
            try:
                SaveManager.suspend_ui_state_writes()
            except Exception:
                pass
        except Exception:
            pass
        super().__init__()
        self.setWindowTitle("Victurus")

        # ---- Core refs ----
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[Tuple[Optional[str], str]] = []  # (category, message)

        # ---- Per-leader-line prefs ----
        self._galaxy_ll_prefs = GalaxyLeaderLinePrefs("#00FF80", 2, True)
        self._system_ll_prefs = SystemLeaderLinePrefs("#00FF80", 2, True)

        # ---- Controllers ----
        self.lead: Optional[SystemLeaderLineController] = None
        self.lead_galaxy: Optional[GalaxyLeaderLineController] = None
        self.presenter_galaxy: Optional[GalaxyLocationPresenter] = None
        self.presenter_system: Optional[SystemLocationPresenter] = None
        self.travel_flow = None
        self._travel_coordinator = None

        # ---- Splitters ----
        self._central_splitter: Optional[QSplitter] = None
        self._right_splitter: Optional[QSplitter] = None

        # ---- Location panels (typed to QWidget|None to satisfy protocol) ----
        self.location_panel_galaxy: QWidget | None = None
        self.location_panel_system: QWidget | None = None
        self.location_panel: QWidget | None = None

        # ---- Actions expected by view_menu protocol (predeclare) ----
        self.act_panel_status: QAction | None = None
        self.act_panel_location_galaxy: QAction | None = None
        self.act_panel_location_system: QAction | None = None
        self.act_panel_location: QAction | None = None

        # Legacy leader-line glow action (needed for protocol compatibility)
        self.act_leader_glow: QAction | None = None
        self.act_system_leader_glow: QAction | None = None
        self.act_galaxy_leader_glow: QAction | None = None

        # ---- Central placeholder while idle ----
        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        # (Log docks are created lazily in _pin_status_dock_for_transition)
        # Legacy single-dock placeholder kept for compatibility
        self.log_dock: QDockWidget | None = None

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

        install_file_menu(self)
        self.leader_prefs = _LeaderPrefsAdapter(self)
        install_view_menu_extras(self, self.leader_prefs)

        # ---- Window state restore (using new UI state manager) ----
        self._ui_state = get_ui_state_manager()
        
        # Suspend UI state saves during initialization
        self._ui_state.suspend_saves()
        
        main_state = self._ui_state.get_main_window_state()
        
        # Apply main window geometry from saved state
        geometry = main_state.get("main_geometry", {})
        if geometry:
            try:
                x = int(geometry.get("x", 100))
                y = int(geometry.get("y", 100))
                w = int(geometry.get("w", 1200))
                h = int(geometry.get("h", 800))
                self.setGeometry(x, y, w, h)
                if geometry.get("maximized", False):
                    self.showMaximized()
            except Exception:
                pass
        
        # Also use legacy system for compatibility
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # ---- periodic status refresh (timer starts after start_game_ui) ----
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

        # ---- Per-save UI-state persistence ----
        # Register the provider with the centralized UI config controller
        install_ui_state_provider(self._collect_ui_state)
        # Pending dock visibility to apply once docks are created
        self._pending_dock_visibility = None

        # Panels menu initial sync (Status disabled until created)
        self._sync_panels_menu_state()
        
        # Resume UI state saves after initialization - use a timer so other 
        # initialization can complete first
        QTimer.singleShot(100, self._ui_state.resume_saves)

    # ---------- helpers: docks & leader-line ----------

    def _register_dock(self, dock: QDockWidget) -> None:
        # Connect to both old and new state management systems for compatibility
        dock.visibilityChanged.connect(
            lambda vis, d=dock: window_state.set_window_open(d.objectName(), bool(vis))
            if not (hasattr(self, '_ui_state') and self._ui_state.is_save_suspended()) else None
        )
        
        # Also update the new UI state manager (only if saves not suspended)
        dock.visibilityChanged.connect(
            lambda vis, d=dock: self._ui_state.set_dock_visible(d.objectName(), bool(vis)) 
            if not self._ui_state.is_save_suspended() else None
        )
        
        dock.visibilityChanged.connect(lambda _vis: self._sync_panels_menu_state())
        dock.installEventFilter(self)
        
        # Dock registration for event handling - state will be restored later
        dock.installEventFilter(self)
        dock_name = dock.objectName()
        if dock_name:
            # Don't apply state here - will be restored in batch after all docks are created
            # This prevents individual dock updates from triggering saves during initialization
            pass

    def _status_min_width(self) -> int:
        try:
            return max(220, self.status_panel.minimumSizeHint().width()) if self.status_panel else 220
        except Exception:
            return 220

    def _on_right_splitter_moved(self, *args) -> None:
        try:
            # Avoid persisting during programmatic restore/layout
            if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                return
            rs = getattr(self, '_right_splitter', None)
            if rs is not None:
                sizes = list(rs.sizes())
                # Only use new UI state manager (disable legacy system when new system exists)
                if hasattr(self, '_ui_state') and not self._ui_state.is_save_suspended():
                    self._ui_state.update_main_window_state({"right_splitter_sizes": sizes})
        except Exception:
            pass

    def _on_central_splitter_moved(self, *args) -> None:
        try:
            # Avoid persisting during programmatic restore/layout
            if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                return
            cs = getattr(self, '_central_splitter', None)
            if cs is not None:
                sizes = list(cs.sizes())
                # Only use new UI state manager (disable legacy system when new system exists)  
                if hasattr(self, '_ui_state') and not self._ui_state.is_save_suspended():
                    self._ui_state.update_main_window_state({"central_splitter_sizes": sizes})
                
                # Only save to new UI state manager if saves are not suspended
                if not self._ui_state.is_save_suspended():
                    self._ui_state.update_main_window_state({"central_splitter_sizes": sizes})
        except Exception:
            pass

    def _pin_status_dock_for_transition(self) -> None:
        # Only run when the status dock exists (created via _ensure_status_dock)
        if not self.status_dock:
            return
        # ---- Log docks (one per category) ----
        from .widgets.log_panel import LogPanel

        # Create log docks once
        if not getattr(self, "_log_docks", None):
            self._log_categories = ["All", "Combat", "Trade", "Dialogue", "Reputation", "Loot", "Quest"]
            self._log_panels: Dict[str, LogPanel] = {}
            self._log_docks: Dict[str, QDockWidget] = {}
            self._log_entries: List[Tuple[str, str, str]] = []  # (ts_iso, category, text)

            for cat in self._log_categories:
                panel = LogPanel(self)
                dock = QDockWidget(f"Log - {cat}", self)
                dock.setObjectName(f"dock_Log_{cat}")
                dock.setWidget(panel)
                dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
                self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
                self._register_dock(dock)
                self._log_panels[cat] = panel
                self._log_docks[cat] = dock
            
            # If we had buffered dock visibility from restore, apply it now
            try:
                if getattr(self, '_pending_dock_visibility', None):
                    vismap = self._pending_dock_visibility or {}
                    # Temporarily suspend SaveManager writes so programmatic
                    # setVisible() calls don't produce intermediate persisted states.
                    try:
                        SaveManager.suspend_ui_state_writes()
                    except Exception:
                        pass
                    try:
                        for obj_name, visible in vismap.items():
                            try:
                                for cat, dock_obj in self._log_docks.items():
                                    if isinstance(dock_obj, QDockWidget) and dock_obj.objectName() == obj_name:
                                        dock_obj.setVisible(bool(visible))
                            except Exception:
                                pass
                    finally:
                        # Clear after applying. Resume writes after a short
                        # delay so any programmatic layout signals settle.
                        self._pending_dock_visibility = None
                        try:
                            QTimer.singleShot(50, lambda: SaveManager.resume_ui_state_writes())
                        except Exception:
                            try:
                                SaveManager.resume_ui_state_writes()
                            except Exception:
                                pass
            except Exception:
                pass
        self._sync_panels_menu_state()



    def _ensure_status_dock(self) -> None:
        """Create the Status dock lazily (first time we enter live mode)."""
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
        # Schedule creation of log docks after event loop settles
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
            try:
                # Persist only the specific value; do not trigger a full UI-state
                # write since this is not a move/open/close action.
                window_state.user_update_window_data(self.WIN_ID, {"system_leader_color": self._system_ll_prefs.color.name()})
            except Exception:
                pass
        c2 = QColorDialog.getColor(self._galaxy_ll_prefs.color, self, "Choose Galaxy Leader Line Color")
        if c2.isValid():
            self._galaxy_ll_prefs.color = c2
            self._galaxy_ll_prefs.apply_to_parent(self)
            try:
                window_state.user_update_window_data(self.WIN_ID, {"galaxy_leader_color": self._galaxy_ll_prefs.color.name()})
            except Exception:
                pass

    def _prompt_pick_leader_and_width(self) -> None:
        w, ok = QInputDialog.getInt(self, "Set System Leader Line Width", "Width (px):", self._system_ll_prefs.width, 1, 12)
        if ok:
            self._system_ll_prefs.width = int(w)
            self._system_ll_prefs.apply_to_parent(self)
            try:
                window_state.user_update_window_data(self.WIN_ID, {"system_leader_width": int(self._system_ll_prefs.width)})
            except Exception:
                pass
        w2, ok2 = QInputDialog.getInt(self, "Set Galaxy Leader Line Width", "Width (px):", self._galaxy_ll_prefs.width, 1, 12)
        if ok2:
            self._galaxy_ll_prefs.width = int(w2)
            self._galaxy_ll_prefs.apply_to_parent(self)
            try:
                window_state.user_update_window_data(self.WIN_ID, {"galaxy_leader_width": int(self._galaxy_ll_prefs.width)})
            except Exception:
                pass


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
        try:
            # Only persist the specific flag; avoid a full UI-state write.
            window_state.user_update_window_data(self.WIN_ID, {"galaxy_leader_glow": bool(self._galaxy_ll_prefs.glow)})
        except Exception:
            pass

    def _pick_system_leader_color(self) -> None:
        c = QColorDialog.getColor(self._system_ll_prefs.color, self, "Choose System Leader Line Color")
        if c.isValid():
            self._system_ll_prefs.apply_to_parent(self)

    def _pick_system_leader_width(self) -> None:
        w, ok = QInputDialog.getInt(self, "Set System Leader Line Width", "Width (px):", self._system_ll_prefs.width, 1, 12)
        if ok:
            self._system_ll_prefs.width = int(w)
            self._system_ll_prefs.apply_to_parent(self)

    def _set_system_leader_glow(self, enabled: bool) -> None:
        self._system_ll_prefs.set_glow(bool(enabled), self)
        try:
            window_state.user_update_window_data(self.WIN_ID, {"system_leader_glow": bool(self._system_ll_prefs.glow)})
        except Exception:
            pass

    # ---------- Idle <-> Live ----------

    def start_game_ui(self) -> None:
        # Suspend UI state saves during game UI initialization
        self._ui_state.suspend_saves()
        
        if self._map_view is None:
            # central splitter: [MapTabs | (right vertical splitter)]
            central = QSplitter(Qt.Orientation.Horizontal, self)
            self._central_splitter = central

            mv = _make_map_view()
            self._map_view = mv
            
            # Initialize travel flow before setting up visualizer
            self._ensure_travel_flow()
            
            # Setup travel visualization coordinator
            self._setup_travel_coordinator(mv)

            # optional MapTabs.logMessage
            log_sig = getattr(mv, "logMessage", None)
            connect = getattr(log_sig, "connect", None)
            if callable(connect):
                try:
                    connect(self.append_log)
                except Exception:
                    pass

            central.addWidget(mv)

            # ---- Create Galaxy/System list panels and dock them so they are
            # movable and persistent like other docks (Status/Logs).
            # We do NOT rely on a right-side splitter anymore; docks are
            # managed by Qt's dock system.
            self._right_splitter = None

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
            # Give panels stable object names so global UI state (ui_windows.json)
            # can record their per-panel settings and open/closed flag.
            try:
                panel_galaxy.setObjectName("panel_Galaxy")
            except Exception:
                pass
            try:
                panel_system.setObjectName("panel_System")
            except Exception:
                pass
            
            # Restore panel settings from saved state, otherwise use defaults
            main_state = self._ui_state.get_main_window_state()
            
            # Galaxy panel settings
            try:
                galaxy_category_idx = main_state.get("galaxy_category_index", 0)
                galaxy_sort_text = main_state.get("galaxy_sort_text", "Name A–Z")
                galaxy_search = main_state.get("galaxy_search", "")
                
                panel_galaxy.category.setCurrentIndex(int(galaxy_category_idx))
                
                i_g = panel_galaxy.sort.findText(galaxy_sort_text)
                if i_g >= 0:
                    panel_galaxy.sort.setCurrentIndex(i_g)
                else:
                    # Fallback to default
                    i_g = panel_galaxy.sort.findText("Name A–Z")
                    if i_g >= 0:
                        panel_galaxy.sort.setCurrentIndex(i_g)
                
                panel_galaxy.search.setText(galaxy_search)
            except Exception:
                pass
                
            # System panel settings
            try:
                system_category_idx = main_state.get("system_category_index", 0)
                system_sort_text = main_state.get("system_sort_text", "Default View")
                system_search = main_state.get("system_search", "")
                
                panel_system.category.setCurrentIndex(int(system_category_idx))
                
                i_s = panel_system.sort.findText(system_sort_text)
                if i_s >= 0:
                    panel_system.sort.setCurrentIndex(i_s)
                else:
                    # Fallback to default
                    i_s = panel_system.sort.findText("Default View")
                    if i_s >= 0:
                        panel_system.sort.setCurrentIndex(i_s)
                
                panel_system.search.setText(system_search)
            except Exception:
                pass
                
            # Restore column widths
            try:
                galaxy_col_widths = main_state.get("galaxy_col_widths")
                if galaxy_col_widths and isinstance(galaxy_col_widths, list):
                    for i, width in enumerate(galaxy_col_widths):
                        if i < panel_galaxy.tree.columnCount():
                            panel_galaxy.tree.setColumnWidth(i, int(width))
            except Exception:
                pass
                
            try:
                system_col_widths = main_state.get("system_col_widths") 
                if system_col_widths and isinstance(system_col_widths, list):
                    for i, width in enumerate(system_col_widths):
                        if i < panel_system.tree.columnCount():
                            panel_system.tree.setColumnWidth(i, int(width))
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

            # Assign to attributes used by presenters and other code
            self.location_panel_galaxy = panel_galaxy
            self.location_panel_system = panel_system
            self.location_panel = panel_system  # legacy alias

            # Create docks that wrap the panels so they can be docked/floated.
            try:
                dock_galaxy = QDockWidget("Galaxy", self)
                dock_galaxy.setObjectName("dock_Panel_Galaxy")
                dock_galaxy.setWidget(panel_galaxy)
                dock_galaxy.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea)
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_galaxy)
                self._register_dock(dock_galaxy)
                # expose reference for other code (optional)
                self._dock_panel_galaxy = dock_galaxy
            except Exception:
                pass

            try:
                dock_system = QDockWidget("System", self)
                dock_system.setObjectName("dock_Panel_System")
                dock_system.setWidget(panel_system)
                dock_system.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea)
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_system)
                self._register_dock(dock_system)
                self._dock_panel_system = dock_system
            except Exception:
                pass

            # Central area only contains the map view now
            central.addWidget(mv)
            central.setStretchFactor(0, 1)

            # Restore splitter sizes from saved state
            try:
                main_state = self._ui_state.get_main_window_state()
                central_sizes = main_state.get("central_splitter_sizes")
                if central_sizes and isinstance(central_sizes, list):
                    central.setSizes([int(x) for x in central_sizes])
            except Exception:
                pass

            # Persist splitter changes immediately when the user moves them
            try:
                central.splitterMoved.connect(self._on_central_splitter_moved)
            except Exception:
                pass

            # Presenters (one per list)
            self.presenter_galaxy = GalaxyLocationPresenter(self._map_view, panel_galaxy, None)
            self.presenter_system = SystemLocationPresenter(self._map_view, panel_system, None)

            # Leader lines: attach dedicated controllers (hover-only, no click-lock)
            self.lead = SystemLeaderLineController(mv, panel_system, log=self.append_log)
            self.lead_galaxy = GalaxyLeaderLineController(mv, panel_galaxy, log=self.append_log)
            self._apply_leader_styles()

            # Wire signals
            panel_galaxy.refreshRequested.connect(lambda: self.presenter_galaxy and self.presenter_galaxy.refresh())
            panel_galaxy.clicked.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.focus(eid))
            panel_galaxy.doubleClicked.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.open(eid))
            panel_galaxy.travelHere.connect(lambda eid: self.presenter_galaxy and self.presenter_galaxy.travel_here(eid))

            try:
                def save_galaxy_panel_state():
                    if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                        return
                    if self._ui_state.is_save_suspended():
                        return
                        
                    state = {
                        "galaxy_category_index": int(panel_galaxy.category.currentIndex()),
                        "galaxy_sort_text": str(panel_galaxy.sort.currentText()),
                        "galaxy_search": str(panel_galaxy.search.text())
                    }
                    window_state.user_update_window_data("panel_Galaxy", state)
                    self._ui_state.update_main_window_state(state)
                
                panel_galaxy.category.currentIndexChanged.connect(lambda _i: save_galaxy_panel_state())
            except Exception:
                pass
            try:
                panel_galaxy.sort.currentIndexChanged.connect(lambda _i: save_galaxy_panel_state())
            except Exception:
                pass
            try:
                panel_galaxy.search.textChanged.connect(lambda _t: save_galaxy_panel_state())
            except Exception:
                pass
            try:
                def save_galaxy_column_widths():
                    if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                        return
                    if self._ui_state.is_save_suspended():
                        return
                        
                    widths = [panel_galaxy.tree.columnWidth(i) for i in range(panel_galaxy.tree.columnCount())]
                    window_state.user_update_window_data("panel_Galaxy", {"galaxy_col_widths": widths})
                    self._ui_state.update_main_window_state({"galaxy_col_widths": widths})
                
                panel_galaxy.tree.header().sectionResized.connect(lambda *a: save_galaxy_column_widths())
            except Exception:
                pass

            panel_system.refreshRequested.connect(lambda: self.presenter_system and self.presenter_system.refresh())
            panel_system.clicked.connect(lambda eid: self.presenter_system and self.presenter_system.focus(eid))
            panel_system.doubleClicked.connect(lambda eid: self.presenter_system and self.presenter_system.open(eid))
            panel_system.travelHere.connect(lambda eid: self.presenter_system and self.presenter_system.travel_here(eid))

            try:
                def save_system_panel_state():
                    if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                        return
                    if self._ui_state.is_save_suspended():
                        return
                        
                    state = {
                        "system_category_index": int(panel_system.category.currentIndex()),
                        "system_sort_text": str(panel_system.sort.currentText()),
                        "system_search": str(panel_system.search.text())
                    }
                    window_state.user_update_window_data("panel_System", state)
                    self._ui_state.update_main_window_state(state)
                
                panel_system.category.currentIndexChanged.connect(lambda _i: save_system_panel_state())
            except Exception:
                pass
            try:
                panel_system.sort.currentIndexChanged.connect(lambda _i: save_system_panel_state())
            except Exception:
                pass
            try:
                panel_system.search.textChanged.connect(lambda _t: save_system_panel_state())
            except Exception:
                pass
            try:
                def save_system_column_widths():
                    if window_state.writes_suspended() or getattr(self, '_restoring_ui', False):
                        return
                    if self._ui_state.is_save_suspended():
                        return
                        
                    widths = [panel_system.tree.columnWidth(i) for i in range(panel_system.tree.columnCount())]
                    window_state.update_window_data("panel_System", {"system_col_widths": widths})
                    self._ui_state.update_main_window_state({"system_col_widths": widths})
                
                panel_system.tree.header().sectionResized.connect(lambda *a: save_system_column_widths())
            except Exception:
                pass

            # Tabs hook
            tabs = getattr(mv, "tabs", None)
            if tabs is not None:
                # Restore saved tab index
                try:
                    saved_tab_idx = main_state.get("map_tab_index", 0)
                    if 0 <= saved_tab_idx < tabs.count():
                        tabs.setCurrentIndex(saved_tab_idx)
                except Exception:
                    pass
                
                tabs.currentChanged.connect(lambda _i: self.presenter_galaxy and self.presenter_galaxy.refresh())
                tabs.currentChanged.connect(lambda _i: self.presenter_system and self.presenter_system.refresh())
                tabs.currentChanged.connect(lambda i: self.lead and self.lead.on_tab_changed(i))
                tabs.currentChanged.connect(lambda i: self.lead_galaxy and self.lead_galaxy.on_tab_changed(i))
                
                # Save tab changes
                tabs.currentChanged.connect(lambda i: self._ui_state.update_main_window_state({"map_tab_index": i})
                                            if not self._ui_state.is_save_suspended() else None)

            self.setCentralWidget(central)
            # Attach overlays once central widget is set so viewports exist
            if self.lead:
                self.lead.attach()
            if self.lead_galaxy:
                self.lead_galaxy.attach()
            self._sync_panels_menu_state()

        # After UI initialization, if a provider is installed, persist a
        # full snapshot immediately so the global config is complete when
        # starting a new game or loading one. This write is only done once
        # here when the UI becomes ready.
        # Persist a provider snapshot now (if present) so the global config
        # is fully populated once the UI is initialized.
        try:
            from save.save_manager import SaveManager as _SM
            # Ensure global ui_state exists (this will call the provider and
            # write readable fields immediately if missing).
            try:
                _SM._ensure_global_ui_state_present(_SM.active_save_dir() or Path('.'))
            except Exception:
                pass

            # Also, if a provider exists, call it now and persist via
            # update_window_data to ensure the global config has full fields.
            prov = getattr(_SM, '_UI_STATE_PROVIDER', None)
            if callable(prov):
                try:
                    snap = prov() or {}
                except Exception:
                    snap = {}
                if isinstance(snap, dict) and snap:
                    try:
                        # Only persist the provider snapshot into the global
                        # Config/ui_state.json if the global file does not
                        # already exist. We must never overwrite an existing
                        # user config during startup; creation is handled by
                        # SaveManager.ensure/_create helpers.
                        from ui.state.window_state import update_window_data
                        try:
                            from save.paths import get_ui_state_path
                            pglob = get_ui_state_path()
                        except Exception:
                            pglob = None
                        if pglob is None or not pglob.exists():
                            update_window_data('MainWindow', snap)
                            vis = (snap or {}).get('dock_visibility') or {}
                            if isinstance(vis, dict):
                                for obj_name, is_open in vis.items():
                                    try:
                                        update_window_data(obj_name, {'open': bool(is_open)})
                                    except Exception:
                                        pass
                    except Exception:
                        pass
        except Exception:
            pass

            # ---- Restore per-save UI state (if any) ----
            try:
                ui_state = SaveManager.read_ui_state_for_active()
                # If no per-save UI state exists, fall back to the global
                # Config/ui_state.json 'MainWindow' entry so app start uses
                # the centrally-persisted layout.
                if not ui_state:
                    try:
                        from ui.state import window_state as _ws
                        global_state = _ws._load_state() or {}
                        ui_state = global_state.get('MainWindow') or {}
                    except Exception:
                        ui_state = {}

                if ui_state:
                    # Suspend UI-state writes while we perform a programmatic
                    # restore so signals (like currentIndexChanged or
                    # textChanged) don't trigger a persisted write. Also set
                    # a local restoring flag to avoid handlers scheduling
                    # writes.
                    try:
                        SaveManager.suspend_ui_state_writes()
                    except Exception:
                        pass
                    try:
                        # Mark as restoring so internal handlers can short-
                        # circuit write calls.
                        try:
                            self._restoring_ui = True
                        except Exception:
                            pass
                        self._restore_ui_state(ui_state)
                    finally:
                        # Keep writes suspended until we've created docks
                        # and applied buffered visibility; resume happens
                        # just after _pin_status_dock_for_transition below.
                        pass
            except Exception:
                pass

            # Load persisted game log entries (per-save) and populate panels if present
            try:
                saved_entries = SaveManager.read_log_entries_for_active()
                if saved_entries and hasattr(self, "_log_panels") and isinstance(self._log_panels, dict):
                    # store and populate panels
                    try:
                        self._log_entries = list(saved_entries)
                    except Exception:
                        self._log_entries = []
                    for cat, panel in list(self._log_panels.items()):
                        try:
                            # Feed only entries relevant to this panel (All gets all)
                            if cat == "All":
                                panel.load_entries(self._log_entries)
                            else:
                                panel.load_entries([e for e in self._log_entries if e[1] == cat])
                        except Exception:
                            pass
            except Exception:
                pass

            # Ensure the Status dock exists now so external callers (menus) can call status_panel.refresh()
            try:
                self._ensure_status_dock()
            except Exception:
                pass

            # Create Status dock lazily (first time we enter live mode)
            # legacy name replaced by _pin_status_dock_for_transition; call it here
            self._pin_status_dock_for_transition()

            # NOTE: Do NOT persist UI state automatically here. Per-user
            # preference, UI state should only be saved when the user
            # performs explicit actions (move/open/close). Programmatic
            # restores during startup must not overwrite the last user
            # driven state.
            try:
                # Clear restoring flag and resume writes now that
                # programmatic restore and dock creation have completed.
                try:
                    self._restoring_ui = False
                except Exception:
                    pass
                # Resume writes after the event loop has a chance to process
                # pending layout/resized events. This prevents transient
                # programmatic adjustments from being captured immediately.
                # Define a small helper so we can call it via QTimer or
                # directly as a fallback.
                def _apply_pending_and_resume() -> None:
                    try:
                        pending = getattr(self, '_pending_dock_layout', None)
                        if isinstance(pending, dict) and pending:
                            for oname, layout in pending.items():
                                try:
                                    dock_obj = None
                                    for extra in self.findChildren(QDockWidget):
                                        try:
                                            if extra.objectName() == oname:
                                                dock_obj = extra
                                                break
                                        except Exception:
                                            pass
                                    if dock_obj is None:
                                        continue
                                    # Apply floating/open flags
                                    try:
                                        if 'floating' in layout:
                                            dock_obj.setFloating(bool(layout.get('floating', False)))
                                    except Exception:
                                        pass
                                    try:
                                        if 'open' in layout:
                                            dock_obj.setVisible(bool(layout.get('open', True)))
                                    except Exception:
                                        pass
                                    try:
                                        if all(k in layout for k in ('x','y','w','h')) and bool(layout.get('floating', False)):
                                            dock_obj.move(int(layout.get('x', 0)), int(layout.get('y', 0)))
                                            dock_obj.resize(int(layout.get('w', dock_obj.width())), int(layout.get('h', dock_obj.height())))
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    try:
                        SaveManager.resume_ui_state_writes()
                    except Exception:
                        pass

                try:
                    QTimer.singleShot(50, lambda: _apply_pending_and_resume())
                except Exception:
                    _apply_pending_and_resume()
            except Exception:
                pass

        # After the UI has settled, schedule a short delayed persist of the
        # provider snapshot. This ensures lazily-created docks (status and
        # per-category log docks) are present so their geometry is captured
        # in the global Config/ui_state.json. Use a small delay so the event
        # loop can finish creating widgets and layouts.
        # Suspend writes briefly during initial startup so programmatic
        # show/move/resize events don't get treated as user-driven changes.
        try:
            from save.save_manager import SaveManager as _SM
            try:
                _SM.suspend_ui_state_writes()
                # Resume after a short grace period once the event loop settles.
                try:
                    QTimer.singleShot(250, lambda: _SM.resume_ui_state_writes())
                except Exception:
                    _SM.resume_ui_state_writes()
            except Exception:
                pass
        except Exception:
            pass
        # NOTE: Do not call persist_provider_snapshot here as it could overwrite
        # user UI settings. The global config should already exist and contain
        # the user's preferred UI layout. Provider snapshots are only for
        # first-run initialization.
        
        # Resume SaveManager writes shortly after init to ensure programmatic
        # layout settles first.
        try:
            from save.save_manager import SaveManager as _SM
            try:
                QTimer.singleShot(350, lambda: _SM.resume_ui_state_writes())
            except Exception:
                try:
                    _SM.resume_ui_state_writes()
                except Exception:
                    pass
        except Exception:
            pass

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

        # Flush pending logs into the new append_log routing
        for m in list(self._pending_logs):
            try:
                # m may be a plain string (legacy) or a (cat,text) tuple
                if isinstance(m, (list, tuple)) and len(m) == 2:
                    self.append_log(tuple(m))
                else:
                    self.append_log(str(m))
            except Exception:
                pass
        self._pending_logs.clear()
        
        # Restore the full dock layout from saved state before resuming saves
        # This ensures docks are positioned correctly instead of using defaults
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            main_state = self._ui_state.get_main_window_state()
            dock_layout = main_state.get("dock_layout", {})
            
            if dock_layout:
                # Apply saved layout to each dock that was just created
                for dock_name, layout_info in dock_layout.items():
                    dock_obj = self.findChild(QDockWidget, dock_name)
                    if dock_obj:
                        try:
                            # Set floating state
                            if "floating" in layout_info:
                                dock_obj.setFloating(bool(layout_info["floating"]))
                            
                            # Set visibility
                            if "open" in layout_info:
                                dock_obj.setVisible(bool(layout_info["open"]))
                            
                            # Set position and size for floating docks
                            if layout_info.get("floating", False):
                                if all(key in layout_info for key in ["x", "y", "w", "h"]):
                                    dock_obj.move(int(layout_info["x"]), int(layout_info["y"]))
                                    dock_obj.resize(int(layout_info["w"]), int(layout_info["h"]))
                        except Exception as e:
                            logger.warning("Failed to restore layout for dock %s: %s", dock_name, e)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to restore dock layout: %s", e)
        
        # Resume UI state saves after initialization is complete
        # Use a timer to ensure all initialization has finished
        QTimer.singleShot(200, self._ui_state.resume_saves)

    # ---------- Travel plumbing ----------

    def _ensure_travel_flow(self):
        logger.debug(f"_ensure_travel_flow called - current travel_flow: {self.travel_flow}")
        if self.travel_flow is None:
            from game.travel_flow import TravelFlow  # local import avoids cycles
            self.travel_flow = TravelFlow(on_arrival=self._on_player_moved, log=self.append_log)
            logger.debug(f"Created new travel_flow: {self.travel_flow}")
            try:
                self.travel_flow.progressTick.connect(self._safe_refresh_status)
                logger.debug(f"Connected travel_flow progressTick to _safe_refresh_status")
            except Exception as e:
                logger.error(f"Failed to connect progressTick: {e}")
                pass
                
        # Travel flow is now connected automatically via map widget travel status systems
        # No need for manual visualizer connection
            
        return self.travel_flow
        
    def _setup_travel_coordinator(self, map_view) -> None:
        """Setup travel status tracking with map widgets"""
        try:
            # Get the galaxy and system map widgets from the MapTabs
            galaxy_widget = getattr(map_view, 'galaxy', None)
            system_widget = getattr(map_view, 'system', None)
            
            logger.debug(f"Setting up travel status tracking")
            logger.debug(f"Galaxy widget: {galaxy_widget}")
            logger.debug(f"System widget: {system_widget}")
            
            # Connect travel flow to both map travel status trackers
            if self.travel_flow:
                if galaxy_widget and hasattr(galaxy_widget, 'get_travel_status'):
                    galaxy_status = galaxy_widget.get_travel_status()
                    galaxy_status.set_travel_flow(self.travel_flow)
                    logger.debug("Connected galaxy travel status to travel flow")
                
                if system_widget and hasattr(system_widget, 'get_travel_status'):
                    system_status = system_widget.get_travel_status()
                    system_status.set_travel_flow(self.travel_flow)
                    logger.debug("Connected system travel status to travel flow")
            
            logger.debug("Travel status setup complete")
            
        except Exception as e:
            logger.error(f"Failed to setup travel status: {e}")
            import traceback
            traceback.print_exc()

    def _on_player_moved(self) -> None:
        try:
            # Travel visualization is now handled automatically by SimpleTravelStatus
            # No manual coordination needed
            
            self.refresh_status_counts()
            if self.status_panel:
                self.status_panel.refresh()
        except Exception as e:
            logger.error(f"Error in _on_player_moved: {e}")
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
        # Persist per-dock geometry when docks move/resize. This captures
        # floating dock positions and sizes immediately when the user moves
        # or resizes them. Skip when writes are suspended or we're restoring.
        try:
            if isinstance(obj, QDockWidget) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
                # Skip if either system is suspended or we're restoring UI
                if (window_state.writes_suspended() or 
                    getattr(self, '_restoring_ui', False) or
                    (hasattr(self, '_ui_state') and self._ui_state.is_save_suspended())):
                    return super().eventFilter(obj, event)
                try:
                    # Capture dock geometry into its own top-level entry
                    on = obj.objectName() or None
                    if on:
                        try:
                            g = obj.geometry()
                            dock_data = {
                                'open': bool(obj.isVisible()),
                                'floating': bool(obj.isFloating()),
                                'x': int(g.x()),
                                'y': int(g.y()),
                                'w': int(g.width()),
                                'h': int(g.height()),
                            }
                            
                            # Only use the new UI state manager (disable old system)
                            if hasattr(self, '_ui_state') and not self._ui_state.is_save_suspended():
                                self._ui_state.set_dock_geometry(
                                    on, 
                                    int(g.x()), int(g.y()), 
                                    int(g.width()), int(g.height()),
                                    bool(obj.isFloating()),
                                    bool(obj.isVisible())
                                )
                        except Exception:
                            pass
                except Exception:
                    pass
                return super().eventFilter(obj, event)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _save_window_state(self):
        # Persist a readable numeric geometry snapshot instead of binary hex.
        try:
            g = self.geometry()
            geom = {
                "x": int(g.x()),
                "y": int(g.y()),
                "w": int(g.width()),
                "h": int(g.height()),
                "maximized": bool(self.isMaximized()),
            }
            
            # Only use new UI state manager (disable legacy system when new system exists)
            if hasattr(self, '_ui_state') and not self._ui_state.is_save_suspended():
                self._ui_state.update_main_window_state({"main_geometry": geom, "open": True})
        except Exception:
            # Fallback: do nothing if geometry can't be read
            pass

    def moveEvent(self, e):
        super().moveEvent(e)
        self._save_window_state()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._save_window_state()

    def closeEvent(self, e):
        # During app/window close we must NOT persist the transient 'closed'
        # visibility state caused by Qt hiding widgets. Suspend SaveManager
        # writes so programmatic visibility changes don't overwrite the last
        # user-driven state. Persist logs and basic window_state while
        # suspended, then resume writes after the close completes.
        try:
            SaveManager.suspend_ui_state_writes()
        except Exception:
            pass
        try:
            # persist logs for the active save (always desired)
            try:
                SaveManager.write_log_entries(getattr(self, "_log_entries", []))
            except Exception:
                pass
        except Exception:
            pass

        # stop timers and update open flag / geometry while writes are suspended
        try:
            self._status_timer.stop()
        except Exception:
            pass
        try:
            window_state.set_window_open(self.WIN_ID, False)
        except Exception:
            pass
        try:
            self._save_window_state()
        except Exception:
            pass

        try:
            super().closeEvent(e)
        except Exception:
            # Ensure we don't crash during close; leave UI writes suspended
            # so programmatic hide events won't be persisted.
            pass

    # ---------- logging & stats ----------

    def append_log(self, msg) -> None:
        """Append a log entry.

        Accepts either a plain string (legacy) or a tuple (category, message).
        Routes to LogPanel widgets when available; otherwise queues into _pending_logs.
        """
        try:
            # Normalize incoming message to (category, text)
            cat: Optional[str]
            text: str
            if isinstance(msg, (list, tuple)) and len(msg) == 2:
                cat, text = msg  # type: ignore
            else:
                cat = None
                text = str(msg)

            ts_iso = datetime.utcnow().isoformat()

            # If panels exist, route there and also store in _log_entries
            if hasattr(self, "_log_panels") and isinstance(self._log_panels, dict):
                category = cat or "All"
                entry = (ts_iso, category, text)
                try:
                    self._log_entries.append(entry)
                except Exception:
                    # _log_entries may not be initialized yet
                    pass
                # Always append to All
                try:
                    if "All" in self._log_panels:
                        self._log_panels["All"].append_entry(ts_iso, category, text)
                except Exception:
                    pass
                # Append to specific category panel as well
                try:
                    if category in self._log_panels and category != "All":
                        self._log_panels[category].append_entry(ts_iso, category, text)
                except Exception:
                    pass
            else:
                # Legacy fallback: queue for flush or append to single text widget
                # Try legacy single-dock widget if present
                try:
                    if self.log_dock and self.log_dock.widget():
                        w = self.log_dock.widget()
                        append = getattr(w, "appendPlainText", None)
                        if callable(append):
                            try:
                                append(f"[{ts_iso}][{cat or 'All'}] {text}")
                                return
                            except Exception:
                                pass
                except Exception:
                    pass
                # Queue as tuple for later processing
                try:
                    self._pending_logs.append((cat, text))
                except Exception:
                    pass
        except Exception:
            pass

        # Also schedule applying any pending dock layout entries after
        # UI init so floating/open geometry from the global snapshot gets
        # applied to lazily-created docks.
        try:
            try:
                QTimer.singleShot(200, lambda: getattr(self, '_apply_pending_dock_layout', lambda: None)())
            except Exception:
                try:
                    getattr(self, '_apply_pending_dock_layout', lambda: None)()
                except Exception:
                    pass
        except Exception:
            pass

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
            
            # Update travel progress if traveling
            self._update_travel_progress()
        except Exception:
            pass
    
    def _update_travel_progress(self) -> None:
        """Update travel progress visualization with stage-specific map targeting"""
        try:
            # Travel progress is now handled by SimpleTravelStatus in map widgets
            # No central coordination needed
            
            from game import player_status
            status = player_status.get_status_snapshot()
            ship_state = status.get("status", "").lower()
            
            # Define stage categories
            warp_stages = {"enter warp", "warping", "leaving warp"}  # Galaxy map only
            cruise_stages = {"leaving orbit", "entering cruise", "cruise", "cruising", "leaving cruise", "entering orbit", "docking", "approach"}  # System map only
            
            is_warp_stage = ship_state in warp_stages
            is_cruise_stage = ship_state in cruise_stages
            is_traveling = is_warp_stage or is_cruise_stage
            
            # Debug: Always log the ship state to see what we're getting
            current_time = __import__('time').time()
            if not hasattr(self, '_last_debug_time') or current_time - self._last_debug_time > 1.0:
                stage_type = "WARP" if is_warp_stage else ("CRUISE" if is_cruise_stage else "OTHER")
                logger.debug(f"Ship state: '{ship_state}' (traveling: {is_traveling}, type: {stage_type})")
                self._last_debug_time = current_time
            
            # Initialize global progress session tracker (persists between travels)
            if not hasattr(self, '_travel_session'):
                self._travel_session = {
                    'journey_count': 0,
                    'active_journey': None
                }
            
            if is_traveling:
                # Check if this is a new journey or stage transition
                if (self._travel_session['active_journey'] is None or 
                    self._travel_session['active_journey']['last_state'] not in (warp_stages | cruise_stages)):
                    
                    # Start new journey tracking
                    self._travel_session['journey_count'] += 1
                    stage_type = "WARP" if is_warp_stage else "CRUISE"
                    self._travel_session['active_journey'] = {
                        'start_time': current_time,
                        'journey_id': self._travel_session['journey_count'],
                        'last_update': 0,
                        'last_state': ship_state,
                        'completed': False,
                        'current_stage_type': stage_type
                    }
                    logger.debug(f"Started journey #{self._travel_session['journey_count']} - initial state: '{ship_state}' ({stage_type})")
                
                journey = self._travel_session['active_journey']
                elapsed = current_time - journey['start_time']
                
                # Check for stage type transitions (warp <-> cruise)
                current_stage_type = "WARP" if is_warp_stage else "CRUISE"
                if journey.get('current_stage_type') != current_stage_type:
                    logger.debug(f"Journey #{journey['journey_id']} stage transition: {journey.get('current_stage_type', 'UNKNOWN')} -> {current_stage_type}")
                    # Reset progress tracking for new stage type but keep journey continuity
                    journey['start_time'] = current_time
                    journey['last_update'] = 0
                    journey['current_stage_type'] = current_stage_type
                    elapsed = 0
                
                # Log state changes but don't reset progress within same stage type
                if journey['last_state'] != ship_state:
                    logger.debug(f"Journey #{journey['journey_id']} state: '{journey['last_state']}' -> '{ship_state}' ({current_stage_type})")
                    journey['last_state'] = ship_state
                
                # Progress rate depends on stage type
                if is_warp_stage:
                    # Warp stages: faster progression (for galaxy map)
                    progress = min(elapsed * 0.08, 1.0)  # 8% per second, ~12.5s total
                else:
                    # Cruise stages: standard progression (for system map)  
                    progress = min(elapsed * 0.055, 1.0)  # 5.5% per second, ~18s total
                
                # Only update if progress changed significantly
                if abs(progress - journey['last_update']) > 0.01:
                    logger.debug(f"Journey #{journey['journey_id']} progress: {progress:.1%} ({elapsed:.1f}s elapsed, {current_stage_type})")
                    journey['last_update'] = progress
                
                # Note: Travel progress is now handled by SimpleTravelStatus in map widgets
                # The overlay system automatically displays progress based on TravelFlow updates
                
                # Mark as completed when reaching 100%
                if progress >= 1.0 and not journey['completed']:
                    journey['completed'] = True
                    logger.debug(f"Journey #{journey['journey_id']} {current_stage_type} stage completed!")
                    
            else:
                # Not traveling - mark current journey as finished but keep session
                if (self._travel_session['active_journey'] is not None and 
                    not self._travel_session['active_journey']['completed']):
                    journey_id = self._travel_session['active_journey']['journey_id']
                    elapsed = current_time - self._travel_session['active_journey']['start_time']
                    progress = self._travel_session['active_journey']['last_update']
                    stage_type = self._travel_session['active_journey'].get('current_stage_type', 'UNKNOWN')
                    logger.debug(f"Journey #{journey_id} ended early at {progress:.1%} after {elapsed:.1f}s - state: '{ship_state}' ({stage_type})")
                    self._travel_session['active_journey']['completed'] = True
                
                # Clear active journey (but keep session for next travel)
                self._travel_session['active_journey'] = None
                
                # Clear manual progress override to allow automatic progress for next travel
                if self._travel_coordinator:
                    self._travel_coordinator.clear_manual_progress_override()
                    
        except Exception as e:
            # Debug: log any errors
            logger.error(f"Error in travel progress: {e}")

    def showEvent(self, event) -> None:
        """Apply any pending geometry/layout once the window is shown.

        Using the showEvent ensures the platform windowing has created the
        native window so floating dock geometry and explicit setGeometry
        calls are honored by the system.
        """
        try:
            super().showEvent(event)
        except Exception:
            try:
                super(QMainWindow, self).showEvent(event)
            except Exception:
                pass
        # Apply pending main geometry if present
        try:
            pmg = getattr(self, '_pending_main_geometry', None)
            if isinstance(pmg, dict):
                try:
                    x = int(pmg.get('x', 0))
                    y = int(pmg.get('y', 0))
                    w = int(pmg.get('w', 800))
                    h = int(pmg.get('h', 600))
                    self.setGeometry(x, y, w, h)
                    if bool(pmg.get('maximized', False)):
                        try:
                            self.showMaximized()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self._pending_main_geometry = None
                except Exception:
                    pass

        except Exception:
            pass

        # Apply pending dock layout after a short delay so child docks
        # added during start_game_ui are present and ready to be moved.
        try:
            def _apply_and_resume():
                try:
                    getattr(self, '_apply_pending_dock_layout', lambda: None)()
                except Exception:
                    pass
                try:
                    from save.save_manager import SaveManager as _SM
                    _SM.resume_ui_state_writes()
                except Exception:
                    pass
            try:
                QTimer.singleShot(120, _apply_and_resume)
            except Exception:
                _apply_and_resume()
        except Exception:
            pass

    def _apply_pending_dock_layout(self) -> None:
        """Apply any buffered dock_layout entries captured during restore.

        This sets floating/open flags and attempts to move/resize floating
        docks so saved geometry takes effect for lazily-created docks.
        Also applies Qt native state restoration after docks are created.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # First, try to restore Qt's native state if we have it and haven't done so yet
            pending_qt_state = getattr(self, '_pending_qt_state', None)
            if pending_qt_state and isinstance(pending_qt_state, str):
                try:
                    from PySide6.QtCore import QByteArray
                    # Check if it's base64 (longer) or hex format
                    if len(pending_qt_state) > 500:  # Base64 is typically longer
                        self.restoreState(QByteArray.fromBase64(pending_qt_state.encode("ascii")))
                    else:
                        self.restoreState(QByteArray.fromHex(pending_qt_state.encode("ascii")))
                    # Clear the pending state so we don't apply it again
                    self._pending_qt_state = None
                    
                    # After Qt state restoration, enforce dock sizes from config for new games
                    # to prevent dock panels from appearing maximized due to stale Qt state
                    self._enforce_dock_sizes_from_config()
                except Exception as e:
                    logger.debug(f"Failed to apply deferred Qt state: {e}")
            
            # Then apply individual dock layout settings
            pending = getattr(self, '_pending_dock_layout', None)
            if not isinstance(pending, dict) or not pending:
                return
            for oname, layout in pending.items():
                try:
                    dock_obj = None
                    for extra in self.findChildren(QDockWidget):
                        try:
                            if extra.objectName() == oname:
                                dock_obj = extra
                                break
                        except Exception:
                            pass
                    if dock_obj is None:
                        continue
                    try:
                        if 'floating' in layout:
                            dock_obj.setFloating(bool(layout.get('floating', False)))
                    except Exception:
                        pass
                    try:
                        if 'open' in layout:
                            dock_obj.setVisible(bool(layout.get('open', True)))
                    except Exception:
                        pass
                    try:
                        # Apply geometry only for floating docks (docked widgets ignore move/resize)
                        if all(k in layout for k in ('x','y','w','h')) and bool(layout.get('floating', False)):
                            dock_obj.move(int(layout.get('x', 0)), int(layout.get('y', 0)))
                            dock_obj.resize(int(layout.get('w', dock_obj.width())), int(layout.get('h', dock_obj.height())))
                            logger.debug(f"Applied geometry to floating dock {oname}: {layout['x']},{layout['y']} {layout['w']}x{layout['h']}")
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def _enforce_dock_sizes_from_config(self) -> None:
        """Force dock panel sizes to match config values instead of Qt state.
        
        This prevents dock panels from appearing maximized when the Qt state
        contains stale dock sizes from previous sessions. Called after Qt state
        restoration to ensure dock sizes match the JSON configuration.
        """
        try:
            main_state = self._ui_state.get_main_window_state()
            dock_layout = main_state.get("dock_layout", {})
            
            # For Galaxy and System panels specifically, ensure reasonable sizes
            for dock_name in ["dock_Panel_Galaxy", "dock_Panel_System"]:
                dock_obj = self.findChild(QDockWidget, dock_name)
                if dock_obj:
                    layout_info = dock_layout.get(dock_name, {})
                    config_width = layout_info.get("w")
                    if isinstance(config_width, (int, float)) and 100 <= config_width <= 800:
                        # Use the config width if it's reasonable (100-800 pixels)
                        try:
                            # For docked panels, try to influence their size through splitter manipulation
                            if not dock_obj.isFloating():
                                # Find the dock's current area and try to resize it
                                dock_area = self.dockWidgetArea(dock_obj)
                                if dock_area in [Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea]:
                                    # For side-docked panels, constrain width temporarily
                                    dock_obj.setMinimumWidth(int(config_width))
                                    dock_obj.setMaximumWidth(int(config_width))
                                    # Schedule size constraint removal with multiple attempts
                                    try:
                                        from PySide6.QtCore import QTimer
                                        def reset_constraints(dock=dock_obj):
                                            try:
                                                if dock:  # Check if dock still exists
                                                    dock.setMinimumWidth(0)
                                                    dock.setMaximumWidth(16777215)
                                            except Exception:
                                                pass
                                        # Multiple attempts to ensure it takes effect
                                        QTimer.singleShot(50, reset_constraints)
                                        QTimer.singleShot(200, reset_constraints)
                                        QTimer.singleShot(500, reset_constraints)
                                    except Exception:
                                        pass
                            else:
                                # For floating docks, directly resize them
                                config_height = layout_info.get("h", dock_obj.height())
                                if isinstance(config_height, (int, float)):
                                    dock_obj.resize(int(config_width), int(config_height))
                        except Exception:
                            pass
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
        # If UI state manager saves are suspended, don't provide state data
        # This prevents the SaveManager from calling us during initialization
        if hasattr(self, '_ui_state') and self._ui_state.is_save_suspended():
            return {}
            
        state: Dict[str, Any] = {}

        # Save Qt's native state for proper dock layout restoration
        try:
            qt_state = self.saveState()
            if qt_state:
                # Convert QByteArray to base64 string for JSON storage
                state["main_state_b64"] = bytes(qt_state.toBase64().data()).decode("ascii")
        except Exception:
            pass

    # Also persist human-readable numeric geometry for inspection

        # Also persist a human-readable geometry snapshot (x/y/width/height)
        # so the global config is easier to inspect and edit by hand.
        try:
            g = self.geometry()
            state["main_geometry"] = {
                "x": int(g.x()),
                "y": int(g.y()),
                "w": int(g.width()),
                "h": int(g.height()),
                "maximized": bool(self.isMaximized()),
            }
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

        # Persist dock ordering and visibility for known docks (status + logs)
        try:
            docks = []
            vis = {}
            # collect known dock widgets by objectName
            for attr in ("status_dock",):
                d = getattr(self, attr, None)
                if isinstance(d, QDockWidget) and d.objectName():
                    docks.append(d.objectName())
                    vis[d.objectName()] = bool(d.isVisible())
            if hasattr(self, "_log_docks") and isinstance(self._log_docks, dict):
                for name, dock in self._log_docks.items():
                    try:
                        if isinstance(dock, QDockWidget) and dock.objectName():
                            docks.append(dock.objectName())
                            vis[dock.objectName()] = bool(dock.isVisible())
                    except Exception:
                        pass
            # Also include any other QDockWidget children that may have been
            # created by other modules; use objectName() as the persistence key.
            try:
                for extra in self.findChildren(QDockWidget):
                    try:
                        on = extra.objectName()
                        if not on:
                            continue
                        if on in vis:
                            continue
                        docks.append(on)
                        vis[on] = bool(extra.isVisible())
                    except Exception:
                        pass
            except Exception:
                pass
            if docks:
                state["dock_order"] = docks
                state["dock_visibility"] = vis
                # Also record per-dock geometry/layout so we can persist
                # sizes and positions for each dock (status + logs).
                try:
                    dock_layout = {}
                    for oname in docks:
                        try:
                            # find the dock object by objectName
                            dobj = None
                            if self.status_dock and self.status_dock.objectName() == oname:
                                dobj = self.status_dock
                            elif hasattr(self, "_log_docks"):
                                for k, d in self._log_docks.items():
                                    try:
                                        if isinstance(d, QDockWidget) and d.objectName() == oname:
                                            dobj = d
                                            break
                                    except Exception:
                                        pass
                            if dobj is None:
                                # fallback: search among children
                                try:
                                    for extra in self.findChildren(QDockWidget):
                                        try:
                                            if extra.objectName() == oname:
                                                dobj = extra
                                                break
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            if dobj is None:
                                continue
                            try:
                                g = dobj.geometry()
                                dock_layout[oname] = {
                                    "open": bool(dobj.isVisible()),
                                    "floating": bool(dobj.isFloating()),
                                    "x": int(g.x()),
                                    "y": int(g.y()),
                                    "w": int(g.width()),
                                    "h": int(g.height()),
                                }
                            except Exception:
                                # best-effort: at least record open/floating
                                dock_layout[oname] = {"open": bool(dobj.isVisible()), "floating": bool(dobj.isFloating())}
                        except Exception:
                            pass
                    if dock_layout:
                        state["dock_layout"] = dock_layout
                except Exception:
                    pass
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
            state["system_list_visible"] = bool(self.location_panel_system.isVisible()) if self.location_panel_system else True
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
            if isinstance(self.location_panel_system, SystemLocationList):
                tree = self.location_panel_system.tree
                state["system_col_widths"] = [tree.columnWidth(i) for i in range(tree.columnCount())]
                state["system_sort_text"] = str(self.location_panel_system.sort.currentText())
                state["system_category_index"] = int(self.location_panel_system.category.currentIndex())
                state["system_search"] = str(self.location_panel_system.search.text())
        except Exception:
            pass

        return state

    def _restore_ui_state(self, state: Dict[str, Any]) -> None:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            append_event("restore_start", f"has_keys={','.join(sorted(list(state.keys()))) if isinstance(state, dict) else ''}")
            # Prefer human-readable numeric geometry if available
            mg = state.get("main_geometry")
            if isinstance(mg, dict):
                try:
                    x = int(mg.get("x", 0))
                    y = int(mg.get("y", 0))
                    w = int(mg.get("w", 800))
                    h = int(mg.get("h", 600))
                    self.setGeometry(x, y, w, h)
                    if bool(mg.get("maximized", False)):
                        try:
                            self.showMaximized()
                        except Exception:
                            pass
                    try:
                        append_event("applied_main_geometry", f"x={x} y={y} w={w} h={h} maximized={bool(mg.get('maximized', False))}")
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                # Fallback to Qt binary format if no numeric geometry
                geo_hex = state.get("main_geometry_hex")
                if isinstance(geo_hex, str) and geo_hex:
                    self.restoreGeometry(QByteArray.fromHex(geo_hex.encode("ascii")))
                elif isinstance(state.get("main_geometry_b64"), str):
                    self.restoreGeometry(QByteArray.fromBase64(state["main_geometry_b64"].encode("ascii")))

            # Always try to restore Qt state for dock layout (regardless of geometry method)
            # But defer Qt state restoration until docks are created by saving it for _apply_pending_dock_layout
            sta_hex = state.get("main_state_hex")
            if isinstance(sta_hex, str) and sta_hex:
                self._pending_qt_state = sta_hex  # Save hex format for later
            elif isinstance(state.get("main_state_b64"), str):
                self._pending_qt_state = state["main_state_b64"]  # Save base64 format for later
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

        # Restore dock visibility/order if present
        try:
            order = state.get("dock_order") or []
            vis = state.get("dock_visibility") or {}
            # Buffer any per-dock layout so it can be applied after lazy
            # docks are created. Store unconditionally so we can apply
            # floating/open/geometry later via _apply_pending_dock_layout.
            try:
                self._pending_dock_layout = state.get("dock_layout", {}) or {}
                try:
                    append_event("buffered_pending_dock_layout", f"count={len(self._pending_dock_layout) if isinstance(self._pending_dock_layout, dict) else 0}")
                except Exception:
                    pass
            except Exception:
                self._pending_dock_layout = {}
            # Restore visibility
            for obj_name, visible in vis.items():
                try:
                    # find dock by objectName among known docks
                    d = None
                    if self.status_dock and self.status_dock.objectName() == obj_name:
                        d = self.status_dock
                    elif hasattr(self, "_log_docks"):
                        # _log_docks keys are categories (e.g. 'All', 'Combat'); match by dock.objectName()
                        for cat, dock_obj in self._log_docks.items():
                            try:
                                if isinstance(dock_obj, QDockWidget) and dock_obj.objectName() == obj_name:
                                    d = dock_obj
                                    break
                            except Exception:
                                pass
                    # If still not found, look among all dock children by objectName
                    if d is None:
                        try:
                            for extra in self.findChildren(QDockWidget):
                                try:
                                    if extra.objectName() == obj_name:
                                        d = extra
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    # If the dock isn't created yet (common for log docks), buffer visibility to apply later
                    if d is None:
                        # Only buffer if this looks like a dock name
                        if isinstance(obj_name, str) and obj_name.startswith("dock_"):
                            # store the whole map for later application
                            self._pending_dock_visibility = vis
                            try:
                                self._pending_dock_layout = state.get("dock_layout", {}) or {}
                            except Exception:
                                self._pending_dock_layout = {}
                            try:
                                append_event("buffered_pending_dock_visibility", f"keys={','.join(sorted(list(vis.keys()))) if isinstance(vis, dict) else ''}")
                            except Exception:
                                pass
                            break
                    if isinstance(d, QDockWidget):
                        d.setVisible(bool(visible))
                except Exception:
                    pass
            # Note: precise dock stacking/order restoration is handled by restoreState above
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
            if self.location_panel_system:
                self.location_panel_system.setVisible(bool(vis_s))
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
            if isinstance(self.location_panel_system, SystemLocationList):
                cat_idx = int(state.get("system_category_index", 0))
                self.location_panel_system.category.setCurrentIndex(cat_idx)
                sort_text = state.get("system_sort_text")
                if isinstance(sort_text, str) and sort_text:
                    i = self.location_panel_system.sort.findText(sort_text)
                    if i >= 0:
                        self.location_panel_system.sort.setCurrentIndex(i)
                self.location_panel_system.search.setText(str(state.get("system_search", "")))
                widths = state.get("system_col_widths")
                if isinstance(widths, list):
                    tree = self.location_panel_system.tree
                    for i, w in enumerate(widths):
                        try:
                            tree.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass
