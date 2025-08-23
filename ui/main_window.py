from __future__ import annotations

from typing import Optional, List, Dict, Callable

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QFont
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
                categories=["All", "System", "Star", "Planet", "Station"],
                sorts=["Name A–Z", "Name Z–A", "Distance", "X", "Y"],
                title="Locations",
            )
            self.location_panel = panel
            central.addWidget(panel)
            central.setStretchFactor(0, 1)
            central.setStretchFactor(1, 0)

            # Signals
            panel.refreshRequested.connect(self._refresh_location_panel)
            panel.clicked.connect(self._on_panel_focus)          # single-click = focus/center
            panel.doubleClicked.connect(self._on_panel_open)     # double-click = open / switch tab
            panel.travelHere.connect(self._on_panel_travel_here)

            # Refresh list when tab changes inside MapTabs
            tabs = getattr(mv, "tabs", None)
            if tabs is not None:
                try:
                    tabs.currentChanged.connect(lambda _i: self._refresh_location_panel())
                except Exception:
                    pass

            self.setCentralWidget(central)

        # Initial refresh
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try:
                mv_reload()
            except Exception:
                pass

        self._refresh_location_panel()
        self._safe_refresh_status()
        self._status_timer.start()

        QTimer.singleShot(0, self._pin_status_dock_for_transition)

        # Flush pending logs
        for m in self._pending_logs:
            self.log.appendPlainText(m)
        self._pending_logs.clear()

    # ---------- Tab awareness ----------

    def _using_galaxy(self) -> bool:
        mv = self._map_view
        if not mv:
            return False
        tabs = getattr(mv, "tabs", None)
        if tabs is None:
            return False
        try:
            return tabs.currentIndex() == 0  # 0=Galaxy, 1=System
        except Exception:
            return False

    # ---------- LocationList wiring ----------
    def _refresh_location_panel(self) -> None:
        from collections.abc import Iterable as _Iterable
        from math import hypot

        if not self.location_panel:
            return

        rows: List[Dict] = []
        list_font = QFont()

        # Current context
        player = db.get_player_full() or {}
        cur_sys_id = int(player.get("current_player_system_id") or 0)
        cur_loc_id = int(player.get("current_player_location_id") or 0)

        # Helper to safely coerce results to a list of dicts
        def _coerce_entities(obj) -> List[Dict]:
            if isinstance(obj, list):
                return obj
            if isinstance(obj, tuple):
                return list(obj)
            if isinstance(obj, _Iterable):
                return list(obj)
            return []

        if self._using_galaxy():
            # ----- GALAXY (systems) -----
            entities: List[Dict] = []
            gal = getattr(self._map_view, "galaxy", None)
            get_entities = getattr(gal, "get_entities", None)
            if callable(get_entities):
                try:
                    entities = _coerce_entities(get_entities())
                except Exception:
                    entities = []
            if not entities:
                try:
                    entities = [dict(r) for r in db.get_systems()]
                except Exception:
                    entities = []

            for s in entities:
                sid = int(s.get("id") or 0)
                try:
                    td = travel.get_travel_display_data(target_id=sid, is_system_target=True) or {}
                except Exception:
                    td = {}
                dist_ly = float(td.get("dist_ly", 0.0) or 0.0)
                fuel_cost = td.get("fuel_cost", "—")

                rows.append({
                    "id": sid,
                    "name": s.get("name", "System"),
                    "kind": "system",
                    # Galaxy view shows LY (always)
                    "distance": f"{dist_ly:.2f} ly",
                    "jump_dist": dist_ly,          # used for Distance sort in galaxy
                    "fuel_cost": fuel_cost,
                    "x": s.get("x", 0.0),
                    "y": s.get("y", 0.0),
                    "can_reach": True,
                    "icon_path": s.get("icon_path"),
                    # Only current system is green
                    "is_current": (sid == cur_sys_id),
                })

            sorted_obj = self.location_panel.filtered_sorted(rows, player_pos=None)
            try:
                rows_sorted: List[Dict] = list(sorted_obj) if sorted_obj is not None else []
            except TypeError:
                rows_sorted = []
            self.location_panel.populate(rows_sorted, list_font, icon_provider=self._icon_provider)

        else:
            # ----- SYSTEM (star + locations) -----
            if not cur_sys_id:
                self.location_panel.populate([], list_font)
                return

            # Player's AU position: current location coords if available, else star at (0,0)
            cur_x = 0.0
            cur_y = 0.0
            if cur_loc_id:
                try:
                    cur_loc = db.get_location(cur_loc_id) or {}
                    cur_x = float(cur_loc.get("x", 0.0) or 0.0)
                    cur_y = float(cur_loc.get("y", 0.0) or 0.0)
                except Exception:
                    cur_x = 0.0
                    cur_y = 0.0

            # Prefer Solar widget entities (to carry icon_path/x/y if provided)
            entities: List[Dict] = []
            sol = getattr(self._map_view, "solar", None)
            get_entities = getattr(sol, "get_entities", None)
            if callable(get_entities):
                try:
                    entities = _coerce_entities(get_entities())
                except Exception:
                    entities = []

            # Fallback: star + locations from DB
            if not entities:
                try:
                    sysrow = db.get_system(cur_sys_id) or {}
                except Exception:
                    sysrow = {}
                entities.append({
                    "id": STAR_ID_SENTINEL * cur_sys_id,  # negative id marks the star
                    "system_id": cur_sys_id,
                    "name": f"{sysrow.get('name','System')} (Star)",
                    "kind": "star",
                    "icon_path": None,
                    "x": 0.0,
                    "y": 0.0,
                })
                try:
                    for loc in db.get_locations(cur_sys_id):
                        d = dict(loc)
                        # ensure x/y keys exist for distance math
                        d.setdefault("x", 0.0)
                        d.setdefault("y", 0.0)
                        entities.append(d)
                except Exception:
                    pass

            rows = []
            for e in entities:
                eid = int(e.get("id") or 0)
                kind = (e.get("kind") or e.get("location_type") or "location").lower()

                # target coords (fallback to DB if missing)
                ex = e.get("x", None)
                ey = e.get("y", None)
                if ex is None or ey is None:
                    if eid >= 0:
                        locrow = db.get_location(eid) or {}
                        ex = locrow.get("x", 0.0)
                        ey = locrow.get("y", 0.0)
                    else:
                        ex = 0.0
                        ey = 0.0
                try:
                    ex = float(ex or 0.0)
                    ey = float(ey or 0.0)
                except Exception:
                    ex = 0.0
                    ey = 0.0

                # --- Compute AU distance (layered fallbacks) ---
                dist_au = 0.0

                # (1) Try travel module's AU
                try:
                    td = travel.get_travel_display_data(
                        target_id=(cur_sys_id if eid < 0 else eid),
                        is_system_target=(eid < 0)
                    ) or {}
                    v = td.get("dist_au", None)
                    if v is not None:
                        dist_au = float(v)
                except Exception:
                    pass

                # (2) If entity has a baked AU measure
                if not dist_au:
                    for k in ("distance_au", "orbit_radius_au", "au", "orbit_au"):
                        v = e.get(k)
                        if v not in (None, ""):
                            try:
                                dist_au = float(str(v))
                                break
                            except Exception:
                                pass

                # (3) Fallback to geometry: distance from player's AU position
                if not dist_au:
                    dist_au = hypot(ex - cur_x, ey - cur_y)

                # fuel (best-effort from travel module)
                fuel_cost = "—"
                try:
                    fuel_cost = (travel.get_travel_display_data(
                        target_id=(cur_sys_id if eid < 0 else eid),
                        is_system_target=(eid < 0)
                    ) or {}).get("fuel_cost", "—")
                except Exception:
                    pass

                rows.append({
                    "id": eid,
                    "name": e.get("name", "—"),
                    "kind": kind,
                    # System view shows AU (always)
                    "distance": f"{dist_au:.2f} AU",
                    "jump_dist": dist_au,          # use AU for Distance sort within a system
                    "fuel_cost": fuel_cost,
                    "x": ex,
                    "y": ey,
                    "can_reach": True,
                    "icon_path": e.get("icon_path"),
                    # Only player's current location should be green
                    "is_current": (eid == cur_loc_id) if eid >= 0 else False,
                })

            sorted_obj = self.location_panel.filtered_sorted(rows, player_pos=None)
            try:
                rows_sorted = list(sorted_obj) if sorted_obj is not None else []
            except TypeError:
                rows_sorted = []
            self.location_panel.populate(rows_sorted, list_font, icon_provider=self._icon_provider)

    def _icon_provider(self, r: Dict):
        from PySide6.QtGui import QIcon
        p = r.get("icon_path")
        return QIcon(p) if p else None

    def _on_panel_focus(self, entity_id: int) -> None:
        """Single-click: center the relevant map on the item."""
        if not self._map_view:
            return

        if self._using_galaxy():
            show_galaxy = getattr(self._map_view, "show_galaxy", None)
            if callable(show_galaxy):
                try: show_galaxy()
                except Exception: pass
            center_sys = getattr(self._map_view, "center_galaxy_on_system", None)
            if callable(center_sys):
                try: center_sys(int(entity_id))
                except Exception: pass
        else:
            show_solar = getattr(self._map_view, "show_solar", None)
            if callable(show_solar):
                try: show_solar()
                except Exception: pass
            if entity_id < 0:
                player = db.get_player_full() or {}
                sys_id = int(player.get("current_player_system_id") or 0)
                center_sys = getattr(self._map_view, "center_solar_on_system", None)
                if callable(center_sys):
                    try: center_sys(sys_id)
                    except Exception: pass
            else:
                center_loc = getattr(self._map_view, "center_solar_on_location", None)
                if callable(center_loc):
                    try: center_loc(int(entity_id))
                    except Exception: pass

    def _on_panel_open(self, entity_id: int) -> None:
        """Double-click: if in Galaxy view, switch to System tab and load that system."""
        if not self._map_view:
            return

        if self._using_galaxy():
            # 1) switch tab
            show_solar = getattr(self._map_view, "show_solar", None)
            if callable(show_solar):
                try:
                    show_solar()
                except Exception:
                    pass

            # 2) ensure solar is loaded for this system (robust, even if helpers differ)
            try:
                sys_id = int(entity_id)
            except Exception:
                return

            # Preferred: helper that loads+centers
            center_sys = getattr(self._map_view, "center_solar_on_system", None)
            if callable(center_sys):
                try:
                    center_sys(sys_id)
                except Exception:
                    # Fallback: direct load on the Solar widget, then no-op center
                    solar = getattr(self._map_view, "solar", None)
                    load = getattr(solar, "load", None)
                    if callable(load):
                        try:
                            load(sys_id)
                        except Exception:
                            pass
            else:
                # No helper → load directly
                solar = getattr(self._map_view, "solar", None)
                load = getattr(solar, "load", None)
                if callable(load):
                    try:
                        load(sys_id)
                    except Exception:
                        pass

            # 3) right panel now should reflect System list
            self._refresh_location_panel()
        else:
            # In System view: treat double-click like focus
            self._on_panel_focus(entity_id)

    def _on_panel_travel_here(self, entity_id: int) -> None:
        """Context menu 'Travel here'."""
        begin_travel = getattr(self._map_view, "begin_travel", None)
        if self._using_galaxy():
            # entity is a SYSTEM id → travel to its star
            if callable(begin_travel):
                try:
                    begin_travel("star", int(entity_id))
                    return
                except Exception:
                    pass
            self._begin_travel("star", int(entity_id))
            return

        if callable(begin_travel):
            try:
                if entity_id < 0:
                    begin_travel("star", abs(entity_id))
                else:
                    begin_travel("loc", int(entity_id))
                return
            except Exception:
                pass

        if entity_id < 0:
            self._begin_travel("star", abs(entity_id))
        else:
            self._begin_travel("loc", int(entity_id))

    # --- Travel fallback with 10s arrival window ---

    def _begin_travel(self, kind: str, ident: int) -> None:
        try:
            player = db.get_player_full()
            if not player:
                self.append_log("No player loaded.")
                return

            is_system_target = (kind == "star")
            target_id = int(ident or 0)
            td = travel.get_travel_display_data(target_id=target_id, is_system_target=is_system_target)
            if not td:
                self.append_log("No route available.")
                return

            sequence: List[tuple[str, int]] = []
            current_status = ship_state.get_temporary_state() or self._real_ship_status()
            if current_status == "Docked":
                sequence.append(("Un-docking...", 10_000))
            elif current_status == "Orbiting":
                sequence.append(("Leaving Orbit...", 10_000))

            travel_time_ms = int((float(td.get("dist_ly", 0.0)) + float(td.get("dist_au", 0.0))) * 500)
            if travel_time_ms <= 0:
                travel_time_ms = 500
            sequence.append(("Traveling", travel_time_ms))

            if is_system_target:
                sequence.append(("Entering Orbit...", 10_000))
            else:
                target_loc = db.get_location(target_id)
                k = (target_loc.get("kind") or target_loc.get("location_type") or "").lower() if target_loc else ""
                sequence.append(("Docking...", 10_000) if k == "station" else ("Entering Orbit...", 10_000))

            def finalize():
                if is_system_target:
                    # Prefer the explicit system-star travel helper if present, otherwise try common alternatives
                    fn = getattr(travel, "travel_to_system_star", None) or getattr(travel, "travel_to_system", None)
                    if callable(fn):
                        try:
                            fn(target_id)
                        except Exception:
                            pass
                    else:
                        # Fallback: try the generic travel_to_location if no system-specific helper exists
                        try:
                            loc_fn = getattr(travel, "travel_to_location", None)
                            if callable(loc_fn):
                                loc_fn(target_id)
                        except Exception:
                            pass
                else:
                    try:
                        travel.travel_to_location(target_id)
                    except Exception:
                        pass
                self._on_player_moved()

            self._execute_sequence(sequence, finalize)
        except Exception as e:
            self.append_log(f"Travel error: {e!r}")

    def _execute_sequence(self, sequence: List[tuple[str, int]], on_done: Callable[[], None]) -> None:
        if not sequence:
            on_done()
            return
        ship_state.set_temporary_state(sequence[0][0])
        elapsed = 0
        for i, (label, dur) in enumerate(sequence):
            def make_cb(lbl=label, last=(i == len(sequence) - 1), d=dur):
                def cb():
                    ship_state.set_temporary_state(lbl)
                    if last:
                        QTimer.singleShot(d, self._finish_sequence(on_done))
                return cb
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(make_cb())
            t.start(elapsed)
            elapsed += dur

    def _finish_sequence(self, on_done: Callable[[], None]) -> Callable[[], None]:
        def inner():
            ship_state.clear_temporary_state()
            on_done()
            ship_state.clear_temporary_state()
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
        mv_reload = getattr(self._map_view, "reload_all", None)
        if callable(mv_reload):
            try: mv_reload()
            except Exception: pass
        self._refresh_location_panel()

    # ---------- window state ----------

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
            mv_reload = getattr(self._map_view, "reload_all", None)
            if callable(mv_reload):
                try: mv_reload()
                except Exception: pass
        except Exception:
            pass