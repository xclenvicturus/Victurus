"""
ui/main_window.py
Main window hosting the MapView, log dock, status bar, and menus.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Callable

from PySide6.QtCore import Qt, QEvent, QTimer, QPoint, QPointF
from PySide6.QtGui import QFont, QIcon, QVector2D
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStatusBar,
    QWidget,
    QSplitter,
)

from data import db
from game import player_status, travel, ship_state
from .menus.file_menu import install_file_menu
from .state import window_state
from .widgets.status_sheet import StatusSheet
from .widgets.location_list import LocationList
from .maps.tabs import MapTabs
from typing import cast
from collections.abc import Iterable as _Iterable

STAR_ID_SENTINEL = -1  # encode star target as -system_id so LocationList can emit a single int


def _make_map_view() -> MapTabs:
    return MapTabs()


class MainWindow(QMainWindow):
    WIN_ID = "MainWindow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Victurus")
        self._map_view: Optional[MapTabs] = None
        self._pending_logs: List[str] = []
        self._locked_leader_entity_id: Optional[int] = None

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

        # Window state restore
        window_state.restore_mainwindow_state(self, self.WIN_ID)
        window_state.set_window_open(self.WIN_ID, True)

        # Keep status dock narrow on first layout pass
        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # periodic refresh
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1500)
        self._status_timer.timeout.connect(self._safe_refresh_status)

        # Central splitter created in start_game_ui()
        self._central_splitter: Optional[QSplitter] = None
        self.location_panel: Optional[LocationList] = None

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

            central.addWidget(mv)

            # Right panel
            panel = LocationList(
                categories=["All", "System", "Star", "Planet", "Station"],
                sorts=["Name A–Z", "Name Z–A", "Distance", "X", "Y"],
                title="Locations",
            )
            self.location_panel = panel
            central.addWidget(panel)
            central.setStretchFactor(0, 1)
            central.setStretchFactor(1, 0)

            # --- Connect Signals (Including Leader Line) ---
            panel.refreshRequested.connect(self._refresh_location_panel)
            panel.travelHere.connect(self._on_panel_travel_here)
            panel.hovered.connect(self._on_panel_hover)
            panel.clicked.connect(self._on_panel_click)
            panel.doubleClicked.connect(self._on_panel_open)
            panel.leftView.connect(self._on_panel_leave)


            # Refresh list and leader line when tab changes inside MapTabs
            if mv.tabs:
                mv.tabs.currentChanged.connect(self._on_tab_changed)

            self.setCentralWidget(central)

        # Initial refresh
        if self._map_view:
            self._map_view.reload_all()

        self._refresh_location_panel()
        self._safe_refresh_status()
        self._status_timer.start()

        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # Flush pending logs
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Tab awareness and Leader Line Management ----------

    def _on_tab_changed(self, index: int):
        """Called when the user clicks a map tab."""
        self._locked_leader_entity_id = None
        self._hide_leader_line()
        self._refresh_location_panel()

    def _using_galaxy(self) -> bool:
        return self._map_view is not None and self._map_view.tabs.currentIndex() == 0

    def _on_panel_hover(self, entity_id: int):
        """Show a temporary leader line when hovering, if one is not locked."""
        if self._locked_leader_entity_id is None:
            self._attach_leader_line(entity_id)

    def _on_panel_click(self, entity_id: int):
        """Focus the map and toggle the locked leader line."""
        self._on_panel_focus(entity_id) # Center map first

        if self._locked_leader_entity_id == entity_id:
            self._locked_leader_entity_id = None
            self._hide_leader_line()
        else:
            self._locked_leader_entity_id = entity_id
            self._attach_leader_line(entity_id)

    def _on_panel_leave(self):
        """Hide the temporary leader line when the mouse leaves the list."""
        if self._locked_leader_entity_id is None:
            self._hide_leader_line()

    def _attach_leader_line(self, entity_id: int):
        """Attaches the leader line from a list item to its map entity."""
        if not self.location_panel or not self._map_view:
            return
        
        active_map = self._map_view.galaxy if self._using_galaxy() else self._map_view.solar
        list_item = self.location_panel.find_item_by_id(entity_id)

        if not list_item:
            self._hide_leader_line()
            return
            
        anchor_point = self.location_panel.anchor_point_for_item(active_map.viewport(), list_item)

        def destination_getter():
            info = active_map.get_entity_viewport_center_and_radius(entity_id)
            if not info:
                return None
            center, radius = info
            v = QVector2D(center - anchor_point)
            dist = v.length()
            if dist < 1.0:
                return center
            
            offset = v.normalized() * radius
            return QPoint(int(center.x() - offset.x()), int(center.y() - offset.y()))

        active_map.set_leader_from_viewport_to_getter(anchor_point, destination_getter)

    def _hide_leader_line(self):
        """Hides the leader line on the currently active map."""
        if not self._map_view:
            return
        active_map = self._map_view.galaxy if self._using_galaxy() else self._map_view.solar
        active_map.set_leader_from_viewport_to_getter(None, None)

    # ---------- LocationList wiring ----------
    def _refresh_location_panel(self) -> None:
        from collections.abc import Iterable as _Iterable
        
        if not self.location_panel or not self._map_view:
            return

        rows: List[Dict] = []
        list_font = QFont()

        player = db.get_player_full() or {}
        cur_sys_id = int(player.get("current_player_system_id") or 0)
        cur_loc_id = int(player.get("current_player_location_id") or 0)

        if self._using_galaxy():
            entities = [dict(r) for r in db.get_systems()]
            for s in entities:
                sid = int(s.get("id") or 0)
                td = travel.get_travel_display_data(target_id=sid, is_system_target=True) or {}
                rows.append({
                    "id": sid, "name": s.get("name", "System"), "kind": "system",
                    "distance": td.get("distance", "—"), "jump_dist": td.get("dist_ly", 0.0),
                    "fuel_cost": td.get("fuel_cost", "—"), "x": s.get("x", 0.0), "y": s.get("y", 0.0),
                    "can_reach": td.get("can_reach", True), "can_reach_jump": td.get("can_reach_jump", True),
                    "can_reach_fuel": td.get("can_reach_fuel", True), "icon_path": s.get("icon_path"),
                    "is_current": (sid == cur_sys_id),
                })
        else:
            viewed_system_id = self._map_view.solar._system_id
            if not viewed_system_id:
                self.location_panel.populate([], list_font)
                return

            entities = self._map_view.solar.get_entities()

            for e in entities:
                eid = int(e.get("id") or 0)
                kind = (e.get("kind") or "location").lower()
                
                td = travel.get_travel_display_data(
                    target_id=abs(eid),
                    is_system_target=(eid < 0),
                    current_view_system_id=viewed_system_id
                ) or {}

                rows.append({
                    "id": eid, "name": e.get("name", "—"), "kind": kind,
                    "distance": td.get("distance", "—"), "jump_dist": td.get("dist_au", 0.0),
                    "fuel_cost": td.get("fuel_cost", "—"), "can_reach": td.get("can_reach", True),
                    "can_reach_jump": td.get("can_reach_jump", True), "can_reach_fuel": td.get("can_reach_fuel", True),
                    "icon_path": e.get("icon_path"),
                    "is_current": (eid == cur_loc_id) if eid >= 0 else (cur_loc_id == 0 and viewed_system_id == cur_sys_id),
                })

        rows_sorted = self.location_panel.filtered_sorted(rows, player_pos=None)
        self.location_panel.populate(rows_sorted, list_font, icon_provider=self._icon_provider)

    def _icon_provider(self, r: Dict):
        p = r.get("icon_path")
        return QIcon(p) if p else None

    def _on_panel_focus(self, entity_id: int) -> None:
        """Single-click: center the relevant map on the item."""
        if not self._map_view:
            return

        if self._using_galaxy():
            self._map_view.show_galaxy()
            self._map_view.center_galaxy_on_system(int(entity_id))
        else:
            self._map_view.show_solar()
            self._map_view.center_solar_on_location(int(entity_id))

    def _on_panel_open(self, entity_id: int) -> None:
        """Double-click: if in Galaxy view, switch to System tab and load that system."""
        if not self._map_view:
            return

        if self._using_galaxy():
            self._map_view.show_solar()
            self._map_view.center_solar_on_system(int(entity_id))
        else:
            self._on_panel_focus(entity_id)

    def _on_panel_travel_here(self, entity_id: int) -> None:
        """Context menu 'Travel here'."""
        if self._using_galaxy():
            self._begin_travel("star", int(entity_id))
        else:
            if entity_id < 0:
                self._begin_travel("star", abs(entity_id))
            else:
                self._begin_travel("loc", int(entity_id))

    def _begin_travel(self, kind: str, ident: int) -> None:
        try:
            player = db.get_player_full()
            if not player:
                self.append_log("No player loaded.")
                return

            is_system_target = (kind == "star")
            target_id = int(ident or 0)
            
            current_view_system_id = None
            if not self._using_galaxy() and self._map_view:
                current_view_system_id = self._map_view.solar._system_id

            td = travel.get_travel_display_data(
                target_id=target_id, 
                is_system_target=is_system_target,
                current_view_system_id=current_view_system_id
            )
            if not td or not td.get("can_reach"):
                self.append_log("No route available or destination unreachable.")
                return

            sequence: List[tuple[str, int]] = []
            current_status = self._real_ship_status()
            if current_status == "Docked":
                sequence.append(("Un-docking...", 10_000))
            elif current_status == "Orbiting":
                sequence.append(("Leaving Orbit...", 10_000))

            travel_time_ms = int((float(td.get("dist_ly", 0.0)) + float(td.get("dist_au", 0.0))) * 500)
            if travel_time_ms > 0:
                sequence.append(("Traveling", travel_time_ms))

            if is_system_target:
                sequence.append(("Entering Orbit...", 10_000))
            else:
                target_loc = db.get_location(target_id)
                k = (target_loc.get("kind") or "").lower() if target_loc else ""
                sequence.append(("Docking...", 10_000) if k == "station" else ("Entering Orbit...", 10_000))

            def finalize():
                if is_system_target:
                    travel.travel_to_system_star(target_id)
                else:
                    travel.travel_to_location(target_id)
                self._on_player_moved()

            self._execute_sequence(sequence, finalize)
        except Exception as e:
            self.append_log(f"Travel error: {e!r}")

    def _execute_sequence(self, sequence: List[tuple[str, int]], on_done: Callable[[], None]) -> None:
        if not sequence:
            on_done()
            return
        
        def process_next_step():
            if not sequence:
                self._finish_sequence(on_done)()
                return
            
            state, duration = sequence.pop(0)
            ship_state.set_temporary_state(state)
            self.status_panel.refresh()
            QTimer.singleShot(duration, process_next_step)
        
        process_next_step()


    def _finish_sequence(self, on_done: Callable[[], None]) -> Callable[[], None]:
        def inner():
            ship_state.set_temporary_state(None)
            on_done()
            ship_state.set_temporary_state(None)
        return inner

    def _real_ship_status(self) -> str:
        player = db.get_player_full() or {}
        loc_id = player.get("current_player_location_id")
        if loc_id:
            loc = db.get_location(int(loc_id))
            if loc:
                k = (loc.get("kind") or loc.get("location_type") or "").lower()
                return "Docked" if k == "station" else "Orbiting"
        if player.get("current_player_system_id"):
            return "Orbiting"
        return "Traveling"

    def _on_player_moved(self) -> None:
        self.refresh_status_counts()
        self.status_panel.refresh()
        if self._map_view:
            self._map_view.reload_all()
        self._refresh_location_panel()

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
            # This is the root cause of the orbit reset.
            # The map view contains animations and should not be hard-reloaded periodically.
            # Instead, we only refresh the data-driven side panel.
            if self.location_panel:
                self._refresh_location_panel()
        except Exception:
            pass