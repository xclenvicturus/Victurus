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
    QMenuBar,
    QMenu,
)

from data import db
from game import player_status
from save.manager import SaveManager
from .menus.file_menu import install_file_menu
from .state import window_state
from .widgets.status_sheet import StatusSheet
from .widgets.location_list import LocationList
from .maps.tabs import MapTabs

# merged controller lives here
from .maps.leadline import LeaderLineController

from .controllers.location_presenter import LocationPresenter
from .controllers.map_actions import MapActions
from game.travel_flow import TravelFlow


def _make_map_view() -> MapTabs:
    return MapTabs()


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[str] = []

        # Predeclare central/content pieces before menus use them
        self._central_splitter: Optional[QSplitter] = None
        self.location_panel: Optional[LocationList] = None

        # Leader-line style state (defaults match LeadLine)
        self._leader_color: QColor = QColor(0, 255, 128)
        self._leader_width: int = 2
        self._leader_glow: bool = True
        self.act_leader_glow: Optional[QAction] = None

        # controllers (declare early so methods can safely reference them)
        self.lead: Optional[LeaderLineController] = None
        self.presenter: Optional[LocationPresenter] = None
        self.map_actions: Optional[MapActions] = None
        self.travel_flow: Optional[TravelFlow] = None

        # Central placeholder (idle)
        self._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._idle_label)

        # Log dock
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        self.log_dock = QDockWidget("Log", self)  # store as attribute
        self.log_dock.setObjectName("dock_Log")
        self.log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self._register_dock(self.log_dock)

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

        # Menu action handles for Panels submenu
        self.act_panel_status: Optional[QAction] = None
        self.act_panel_log: Optional[QAction] = None
        self.act_panel_location: Optional[QAction] = None
        self.act_panels_show_all: Optional[QAction] = None
        self.act_panels_hide_all: Optional[QAction] = None

        # Menus (installed after attributes exist)
        install_file_menu(self)
        self._install_view_menu_extras()

        # Window state restore (global)
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # Keep status dock narrow on first layout pass
        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # periodic refresh
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

        # Per-save UI-state persistence
        SaveManager.install_ui_state_provider(self._collect_ui_state)

    # ---------- menus: View → Leader Line + Panels ----------

    def _install_view_menu_extras(self) -> None:
        mb = self.menuBar()
        if not isinstance(mb, QMenuBar):
            return  # safety: no menubar available

        # Find or create the "&View" menu
        view_menu: QMenu | None = None
        for a in mb.actions():
            m = a.menu()
            if isinstance(m, QMenu) and a.text().replace("&", "").lower() == "view":
                view_menu = m
                break
        if view_menu is None:
            view_menu = mb.addMenu("&View")  # returns QMenu

        # Leader Line submenu
        ll_menu = QMenu("Leader Line", self)
        view_menu.addMenu(ll_menu)

        act_color = QAction("Set Color…", self)
        act_color.triggered.connect(self._choose_leader_color)
        ll_menu.addAction(act_color)

        act_width_set = QAction("Set Width…", self)
        act_width_set.triggered.connect(self._choose_leader_width)
        ll_menu.addAction(act_width_set)

        # --- Toggle glow effect ---
        act_glow = QAction("Glow", self)
        act_glow.setCheckable(True)
        act_glow.setChecked(bool(self._leader_glow))
        act_glow.toggled.connect(self._toggle_leader_glow)
        ll_menu.addAction(act_glow)
        self.act_leader_glow = act_glow

        # Panels submenu
        panels_menu = QMenu("Panels", self)
        view_menu.addMenu(panels_menu)

        # Status dock
        act_p_status = QAction("Status", self)
        act_p_status.setCheckable(True)
        act_p_status.setChecked(self.status_dock.isVisible())
        act_p_status.toggled.connect(self._toggle_status_panel)
        panels_menu.addAction(act_p_status)
        self.act_panel_status = act_p_status

        # Log dock
        act_p_log = QAction("Log", self)
        act_p_log.setCheckable(True)
        act_p_log.setChecked(self.log_dock.isVisible())
        act_p_log.toggled.connect(self._toggle_log_panel)
        panels_menu.addAction(act_p_log)
        self.act_panel_log = act_p_log

        # Location List (created later; start disabled)
        act_p_loc = QAction("Location List", self)
        act_p_loc.setCheckable(True)
        act_p_loc.setEnabled(False)  # will enable once start_game_ui creates it
        act_p_loc.toggled.connect(self._toggle_location_list_panel)
        panels_menu.addAction(act_p_loc)
        self.act_panel_location = act_p_loc

        panels_menu.addSeparator()

        # Show/Hide all
        act_show_all = QAction("Show All", self)
        act_show_all.triggered.connect(lambda: self._set_all_panels_visible(True))
        panels_menu.addAction(act_show_all)
        self.act_panels_show_all = act_show_all

        act_hide_all = QAction("Hide All", self)
        act_hide_all.triggered.connect(lambda: self._set_all_panels_visible(False))
        panels_menu.addAction(act_hide_all)
        self.act_panels_hide_all = act_hide_all

        # Safe: these no-op until self.lead exists
        self._apply_leader_style()
        # Sync panel action states
        self._sync_panels_menu_state()

    # ----- Panels submenu handlers -----

    def _toggle_status_panel(self, visible: bool) -> None:
        try:
            self.status_dock.setVisible(bool(visible))
        finally:
            self._sync_panels_menu_state()

    def _toggle_log_panel(self, visible: bool) -> None:
        try:
            self.log_dock.setVisible(bool(visible))
        finally:
            self._sync_panels_menu_state()

    def _toggle_location_list_panel(self, visible: bool) -> None:
        # Location panel exists after start_game_ui
        if self.location_panel is None:
            # Keep action unchecked/disabled until available
            if self.act_panel_location:
                self._with_blocked(self.act_panel_location, lambda a: a.setChecked(False))
                self.act_panel_location.setEnabled(False)
            return
        try:
            self.location_panel.setVisible(bool(visible))
        finally:
            self._sync_panels_menu_state()

    def _set_all_panels_visible(self, visible: bool) -> None:
        # Show/hide docks
        self.status_dock.setVisible(bool(visible))
        self.log_dock.setVisible(bool(visible))
        # Show/hide location list if present
        if self.location_panel is not None:
            self.location_panel.setVisible(bool(visible))
        self._sync_panels_menu_state()

    def _sync_panels_menu_state(self) -> None:
        """Reflect actual widget visibility into the Panels submenu actions."""
        # Status
        if self.act_panel_status is not None:
            self._with_blocked(self.act_panel_status, lambda a: a.setChecked(self.status_dock.isVisible()))
        # Log
        if self.act_panel_log is not None:
            self._with_blocked(self.act_panel_log, lambda a: a.setChecked(self.log_dock.isVisible()))
        # Location List
        if self.act_panel_location is not None:
            loc = getattr(self, "location_panel", None)
            has_loc = loc is not None
            self.act_panel_location.setEnabled(has_loc)
            if has_loc:
                self._with_blocked(self.act_panel_location, lambda a, loc=loc: a.setChecked(loc.isVisible()))
            else:
                self._with_blocked(self.act_panel_location, lambda a: a.setChecked(False))

    @staticmethod
    def _with_blocked(action: QAction, fn) -> None:
        """Run fn(action) with the action's signals blocked to avoid recursive toggles."""
        old = action.blockSignals(True)
        try:
            fn(action)
        finally:
            action.blockSignals(old)

    # ----- Leader Line submenu -----

    def _toggle_leader_glow(self, enabled: bool) -> None:
        self._leader_glow = bool(enabled)
        if self.act_leader_glow and self.act_leader_glow.isChecked() != self._leader_glow:
            self.act_leader_glow.setChecked(self._leader_glow)
        self._apply_leader_style()

    def _apply_leader_style(self) -> None:
        """Push the current leader-line style to the overlay via controller."""
        self._leader_color = getattr(self, "_leader_color", None) or QColor("#00FF80")
        self._leader_width = int(getattr(self, "_leader_width", 2))
        self._leader_glow  = bool(getattr(self, "_leader_glow", True))

        lead = getattr(self, "lead", None)
        if lead is None:
            return  # controller not created yet; start_game_ui will re-apply

        try:
            lead.set_line_style(
                color=self._leader_color,
                width=self._leader_width,
                glow_enabled=self._leader_glow,
            )
        except Exception:
            pass

    def _choose_leader_color(self) -> None:
        c = QColorDialog.getColor(self._leader_color, self, "Choose Leader Line Color")
        if c.isValid():
            self._leader_color = c
            self._apply_leader_style()

    def _nudge_leader_width(self, delta: int) -> None:
        self._leader_width = max(1, self._leader_width + int(delta))
        self._apply_leader_style()

    def _choose_leader_width(self) -> None:
        w, ok = QInputDialog.getInt(
            self,
            "Set Leader Line Width",
            "Width (px):",
            self._leader_width,
            1,   # min
            12,  # max
        )
        if ok:
            self._leader_width = int(w)
            self._apply_leader_style()

    # ---------- helpers ----------

    def _register_dock(self, dock: QDockWidget) -> None:
        dock.visibilityChanged.connect(
            lambda vis, d=dock: window_state.set_window_open(d.objectName(), bool(vis))
        )
        dock.visibilityChanged.connect(lambda _vis: self._sync_panels_menu_state())
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
                sorts=["Name A–Z", "Name Z–A", "Distance ↑", "Distance ↓", "Fuel ↑", "Fuel ↓"],
                title="Locations",
            )

            self.location_panel = panel
            central.addWidget(panel)
            central.setStretchFactor(0, 1)
            central.setStretchFactor(1, 0)

            # Presenter / Actions
            self.presenter = LocationPresenter(mv, panel)
            self.map_actions = MapActions(mv, begin_travel_cb=lambda kind, ident: self._begin_travel(kind, ident))

            # Leader line
            self.lead = LeaderLineController(mv, panel, log=self.append_log, enable_lock=False)
            self.lead.attach()
            self._apply_leader_style()  # now the controller exists

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

            # ---- Restore per-save UI state (if any) ----
            try:
                ui_state = SaveManager.read_ui_state_for_active()
                if ui_state:
                    self._restore_ui_state(ui_state)
            except Exception:
                pass

            # Now that Location List exists, enable its menu action and sync
            if self.act_panel_location is not None:
                self.act_panel_location.setEnabled(True)
                self._sync_panels_menu_state()

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

        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Travel plumbing ----------

    def _ensure_travel_flow(self) -> TravelFlow:
        if self.travel_flow is None:
            self.travel_flow = TravelFlow(on_arrival=self._on_player_moved, log=self.append_log)
            try:
                self.travel_flow.progressTick.connect(self._safe_refresh_status)
            except Exception:
                pass
        return self.travel_flow

    def _begin_travel(self, kind: str, ident: int) -> None:
        self._ensure_travel_flow().begin(kind, ident)

    def _on_player_moved(self) -> None:
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
            self.status_panel.refresh()
            self.refresh_status_counts()
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
            tabs = getattr(self._map_view, "tabs", None)
            state["map_tab_index"] = int(tabs.currentIndex()) if tabs else 0
        except Exception:
            state["map_tab_index"] = 0

        # Leader line style
        try:
            state["leader_color"] = self._leader_color.name()
            state["leader_width"] = int(self._leader_width)
            state["leader_glow"]  = bool(self._leader_glow)
        except Exception:
            pass

        # Location List visibility
        try:
            state["location_list_visible"] = bool(self.location_panel.isVisible()) if self.location_panel else True
        except Exception:
            pass

        # Location panel settings + column widths
        try:
            if self.location_panel:
                state["panel_category_index"] = int(self.location_panel.category.currentIndex())
                state["panel_sort_text"] = str(self.location_panel.sort.currentText())
                state["panel_search"] = str(self.location_panel.search.text())
                tree = self.location_panel.tree
                state["panel_col_widths"] = [tree.columnWidth(i) for i in range(tree.columnCount())]
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
            self._leader_glow  = bool(g)
            if self.act_leader_glow:
                self.act_leader_glow.setChecked(self._leader_glow)
            self._apply_leader_style()
        except Exception:
            pass

        # Location List visibility (apply after panel exists)
        try:
            vis = state.get("location_list_visible", True)
            if self.location_panel is not None:
                self.location_panel.setVisible(bool(vis))
                self._sync_panels_menu_state()
        except Exception:
            pass

        # Location panel settings
        try:
            if self.location_panel:
                cat_idx = int(state.get("panel_category_index", 0))
                self.location_panel.category.setCurrentIndex(cat_idx)

                sort_text = state.get("panel_sort_text")
                if isinstance(sort_text, str) and sort_text:
                    i = self.location_panel.sort.findText(sort_text)
                    if i >= 0:
                        self.location_panel.sort.setCurrentIndex(i)

                self.location_panel.search.setText(str(state.get("panel_search", "")))

                widths = state.get("panel_col_widths")
                if isinstance(widths, list):
                    tree = self.location_panel.tree
                    for i, w in enumerate(widths):
                        try:
                            tree.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass
