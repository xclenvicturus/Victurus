"""
MapView tabs + side panels + hover leader line (via PanZoomView).
- Galaxy list shows each system's assigned star icon.
- Solar list includes the central Star entity (click to center on it).
- Hovering list rows shows a glowing green leader line from the list anchor
  to the entity on the map, using PanZoomView.set_leader_from_viewport_to_getter.
- Clicking a row "locks" the line; clicking the SAME row again UNLOCKS it.
- Right-clicking a location allows traveling to it.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QSplitter, QTabWidget, QVBoxLayout, QWidget, QMessageBox

from data import db
from game.travel import travel_to_location
from .galaxy import GalaxyMapWidget
from .solar import SolarMapWidget
from ..widgets.location_list_panel import LocationListPanel
from .icons import icon_from_path_or_kind


class MapView(QTabWidget):
    playerMoved = Signal()

    def __init__(self, log_fn) -> None:
        super().__init__()
        self._log = log_fn

        # -------- Galaxy tab --------
        self.galaxy = GalaxyMapWidget(log_fn=self._log, parent=self)
        self._gal_panel = LocationListPanel(
            categories=["All", "Systems"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Galaxy",
        )
        self._setup_panel(self._gal_panel, self.galaxy, "galaxy")

        galaxy_split = QSplitter(Qt.Orientation.Horizontal)
        galaxy_split.addWidget(self.galaxy)
        galaxy_split.addWidget(self._gal_panel)
        galaxy_split.setStretchFactor(0, 1)
        galaxy_split.setSizes([900, 260])

        galaxy_tab = QWidget()
        QVBoxLayout(galaxy_tab).addWidget(galaxy_split)

        # -------- Solar tab --------
        self.solar = SolarMapWidget(log_fn=self._log, parent=self)
        self._sol_panel = LocationListPanel(
            categories=["All", "Star", "Planet", "Station"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Solar",
        )
        self._setup_panel(self._sol_panel, self.solar, "solar")
        
        solar_split = QSplitter(Qt.Orientation.Horizontal)
        solar_split.addWidget(self.solar)
        solar_split.addWidget(self._sol_panel)
        solar_split.setStretchFactor(0, 1)
        solar_split.setSizes([900, 260])
        
        solar_tab = QWidget()
        QVBoxLayout(solar_tab).addWidget(solar_split)

        # -------- Add tabs --------
        self.addTab(galaxy_tab, "Galaxy (pc)")
        self.addTab(solar_tab, "Solar (AU)")

        self._gal_locked_id: Optional[int] = None
        self._sol_locked_id: Optional[int] = None
        self._list_font = QFont("SansSerif", 14)

        self.currentChanged.connect(lambda: self._refresh_leader(self.current_map_type()))
        self.reload_all()

    def _setup_panel(self, panel, view, map_type):
        panel.refreshRequested.connect(self.update_lists)
        panel.anchorMoved.connect(lambda: self._refresh_leader(map_type))
        panel.hovered.connect(lambda eid: self._on_hover(map_type, eid))
        panel.clicked.connect(lambda eid: self._on_click(map_type, eid))
        panel.doubleClicked.connect(self._open_system_in_solar if map_type == "galaxy" else lambda _: None)
        panel.travelHere.connect(self._on_travel_request)
        panel.leftView.connect(lambda: self._on_leave_list(map_type))

    def current_map_type(self):
        return "galaxy" if self.currentIndex() == 0 else "solar"

    def _on_travel_request(self, entity_id: int):
        if entity_id < 0: # It's a star
            self._log("Cannot travel to a star directly.")
            return

        result = travel_to_location(entity_id)
        self._log(result)
        if "Traveled" in result:
            self.playerMoved.emit()
            self.reload_all()
        else:
            QMessageBox.warning(self, "Travel Failed", result)

    def reload_all(self) -> None:
        self.galaxy.load()
        self.update_lists()
        player = db.get_player_full()
        if player:
            sys_id = player.get("system_id")
            if sys_id:
                self.solar.load(system_id=sys_id)
                self.galaxy.center_on_system(sys_id)
                loc_id = player.get("current_location_id")
                if loc_id:
                    self.solar.center_on_location(loc_id)
                else:
                    self.solar.center_on_system(sys_id)

    def update_lists(self) -> None:
        self._populate_galaxy_list()
        self._populate_solar_list()
        self._refresh_leader("galaxy")
        self._refresh_leader("solar")

    def _populate_galaxy_list(self) -> None:
        rows_all = self.galaxy.get_entities()
        player = db.get_player_full()
        player_pos = None
        if player and player.get("system_id"):
            current_system = db.get_system(player["system_id"])
            if current_system:
                player_pos = QPointF(current_system["x"], current_system["y"])
                for r in rows_all:
                    r['distance'] = db.get_distance((current_system['x'], current_system['y']), (r['x'], r['y']))
                    r['can_reach'] = db.can_reach(r['distance'])
                    r['dist_unit'] = 'pc'
        
        rows = self._gal_panel.filtered_sorted(rows_all, player_pos)
        self._gal_panel.populate(rows, self._list_font, icon_provider=lambda r: icon_from_path_or_kind(r.get("icon_path"), "star"))

    def _populate_solar_list(self) -> None:
        rows_all = self.solar.get_entities()
        player = db.get_player_full()
        player_loc = None
        if player and player.get("current_location_id"):
            loc = db.get_location(player["current_location_id"])
            if loc:
                player_loc = (loc['local_x_au'], loc['local_y_au'])
                for r in rows_all:
                    r['distance'] = db.get_distance(player_loc, (r.get('local_x_au', 0.0), r.get('local_y_au', 0.0)))
                    r['can_reach'] = True # Intra-system travel is always possible for now
                    r['dist_unit'] = 'AU'

        rows = self._sol_panel.filtered_sorted(rows_all, QPointF(*player_loc) if player_loc else QPointF())
        self._sol_panel.populate(rows, self._list_font, icon_provider=lambda r: icon_from_path_or_kind(r.get("icon_path"), r.get("kind") or ""))

    def _on_hover(self, which: str, eid: int):
        locked_id = self._gal_locked_id if which == "galaxy" else self._sol_locked_id
        if locked_id is None:
            self._attach_leader(which, eid)

    def _on_click(self, which: str, eid: int):
        locked_id = self._gal_locked_id if which == "galaxy" else self._sol_locked_id
        if locked_id == eid:
            self._unlock(which)
        else:
            self._lock(which, eid)

    def _lock(self, which: str, eid: int):
        view = self.galaxy if which == "galaxy" else self.solar
        if which == "galaxy":
            self._gal_locked_id = eid
        else:
            self._sol_locked_id = eid
        view.center_on_entity(eid)
        self._attach_leader(which, eid)

    def _unlock(self, which: str):
        view = self.galaxy if which == "galaxy" else self.solar
        panel = self._gal_panel if which == "galaxy" else self._sol_panel
        if which == "galaxy":
            self._gal_locked_id = None
        else:
            self._sol_locked_id = None
        view.set_leader_from_viewport_to_getter(None, None)
        panel.tree.clearSelection()

    def _on_leave_list(self, which: str):
        locked_id = self._gal_locked_id if which == "galaxy" else self._sol_locked_id
        if locked_id is None:
            view = self.galaxy if which == "galaxy" else self.solar
            view.set_leader_from_viewport_to_getter(None, None)

    def _refresh_leader(self, which: str):
        locked_id = self._gal_locked_id if which == "galaxy" else self._sol_locked_id
        eid = locked_id
        if eid is None:
            panel = self._gal_panel if which == "galaxy" else self._sol_panel
            item = panel.current_hover_item()
            if not item: return
            eid = int(item.data(0, Qt.ItemDataRole.UserRole)) if item else 0
        self._attach_leader(which, eid)

    def _attach_leader(self, which: str, eid: int):
        view = self.galaxy if which == "galaxy" else self.solar
        panel = self._gal_panel if which == "galaxy" else self._sol_panel
        
        item = None
        for i in range(panel.tree.topLevelItemCount()):
            it = panel.tree.topLevelItem(i)
            if it and int(it.data(0, Qt.ItemDataRole.UserRole)) == eid:
                item = it
                break
        
        if not item:
            view.set_leader_from_viewport_to_getter(None, None)
            return

        anchor = panel.anchor_point_for_item(view.viewport(), item)
        dst_getter = self._make_dst_getter(view, anchor, eid)
        view.set_leader_from_viewport_to_getter(anchor, dst_getter)

    def _make_dst_getter(self, view, anchor: QPoint, eid: int):
        def _dst():
            info = view.get_entity_viewport_center_and_radius(eid)
            if not info: return None
            center, radius = info
            v = center - anchor
            length = v.manhattanLength()
            if length == 0: return center
            return center - QPoint(v.x() * radius / length, v.y() * radius / length)
        return _dst
        
    def _open_system_in_solar(self, system_id: int):
        self.setCurrentIndex(1)
        self.solar.load(system_id=system_id)
        self.update_lists()
        self.solar.center_on_system(system_id)
        self._log(f"Opened Solar view for system {system_id}.")