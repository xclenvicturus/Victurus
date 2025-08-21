"""
MapView tabs + side panels + hover leader line (via PanZoomView).

- Galaxy list shows each system's assigned star icon.
- Solar list includes the central Star entity (click to center on it).
- Hovering list rows shows a glowing green leader line from the list anchor
  to the entity on the map, using PanZoomView.set_leader_from_viewport_to_getter.
- Clicking a row "locks" the line; clicking the SAME row again UNLOCKS it.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSplitter, QTabWidget, QVBoxLayout, QWidget

from data import db
from .galaxy import GalaxyMapWidget
from .solar import SolarMapWidget
from .panels import SidePanel
from .icons import icon_from_path_or_kind


class MapView(QTabWidget):
    playerMoved = Signal()

    def __init__(self, log_fn) -> None:
        super().__init__()
        self._log = log_fn

        # -------- Galaxy tab --------
        self.galaxy = GalaxyMapWidget(log_fn=self._log, parent=self)

        self._gal_panel = SidePanel(
            categories=["All", "Systems"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Galaxy",
        )
        self._gal_panel.refreshRequested.connect(self.update_lists)
        # When the panel's anchor shifts (resize/scroll), reattach the leader line.
        self._gal_panel.anchorMoved.connect(lambda: self._refresh_leader("galaxy"))

        galaxy_split = QSplitter(Qt.Orientation.Horizontal)
        galaxy_split.addWidget(self.galaxy)
        galaxy_split.addWidget(self._gal_panel)
        galaxy_split.setStretchFactor(0, 1)
        galaxy_split.setStretchFactor(1, 0)
        galaxy_split.setSizes([900, 260])

        galaxy_tab = QWidget()
        glay = QVBoxLayout(galaxy_tab)
        glay.setContentsMargins(0, 0, 0, 0)
        glay.addWidget(galaxy_split)

        # -------- Solar tab --------
        self.solar = SolarMapWidget(log_fn=self._log, parent=self)

        # Include Star so the system's central star shows up & is filterable
        self._sol_panel = SidePanel(
            categories=["All", "Star", "Planet", "Station"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Solar",
        )
        self._sol_panel.refreshRequested.connect(self.update_lists)
        self._sol_panel.anchorMoved.connect(lambda: self._refresh_leader("solar"))

        solar_split = QSplitter(Qt.Orientation.Horizontal)
        solar_split.addWidget(self.solar)
        solar_split.addWidget(self._sol_panel)
        solar_split.setStretchFactor(0, 1)
        solar_split.setStretchFactor(1, 0)
        solar_split.setSizes([900, 260])

        solar_tab = QWidget()
        slay = QVBoxLayout(solar_tab)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.addWidget(solar_split)

        # -------- Add tabs --------
        self.addTab(galaxy_tab, "Galaxy (pc)")
        self.addTab(solar_tab, "Solar (AU)")

        # Sticky leader-line after click (one per tab)
        self._gal_locked_id: Optional[int] = None
        self._sol_locked_id: Optional[int] = None

        # Galaxy list: double-click → open system in Solar tab
        self._gal_panel.doubleClicked.connect(self._open_system_in_solar)

        # Font for list rows
        self._list_font = QFont()
        self._list_font.setPointSize(14)

        # When switching tabs, refresh leader so the line reattaches
        self.currentChanged.connect(lambda _i: self._refresh_leader("galaxy" if self.currentIndex() == 0 else "solar"))

        # Initial load
        self.reload_all()

        # Hook side panel events (hover/click for leader line)
        self._gal_panel.hovered.connect(lambda eid: self._on_hover("galaxy", eid))
        self._gal_panel.clicked.connect(lambda eid: self._on_click("galaxy", eid))
        self._gal_panel.leftView.connect(lambda: self._on_leave_list("galaxy"))

        self._sol_panel.hovered.connect(lambda eid: self._on_hover("solar", eid))
        self._sol_panel.clicked.connect(lambda eid: self._on_click("solar", eid))
        self._sol_panel.leftView.connect(lambda: self._on_leave_list("solar"))

    # ----- Public API -----
    def reload_all(self) -> None:
        player = db.get_player_full()
        self.galaxy.load()
        self._populate_galaxy_list()

        sys_id = player.get("system_id") if isinstance(player, dict) else None
        if sys_id is not None:
            self.solar.load(system_id=sys_id)
            self._populate_solar_list()
            self.galaxy.center_on_system(sys_id)
            if player.get("current_location_id"):
                self.solar.center_on_location(player["current_location_id"])
            else:
                self.solar.center_on_system(sys_id)

    def center_camera_on_player(self) -> None:
        player = db.get_player_full()
        sys_id = player.get("system_id")
        if self.currentIndex() == 0:
            if sys_id is not None:
                self.galaxy.center_on_system(sys_id)
        else:
            if player.get("current_location_id"):
                self.solar.center_on_location(player["current_location_id"])
            elif sys_id is not None:
                self.solar.center_on_system(sys_id)

    def set_list_font_point_size(self, pt: int) -> None:
        self._list_font.setPointSize(max(10, min(30, int(pt))))
        self.update_lists()

    def get_list_font_point_size(self) -> int:
        return self._list_font.pointSize()

    # ----- List population & filtering -----
    def update_lists(self) -> None:
        self._populate_galaxy_list()
        self._populate_solar_list()
        self._refresh_leader("galaxy")
        self._refresh_leader("solar")

    def _populate_galaxy_list(self) -> None:
        rows_all = self.galaxy.get_entities()
        player = db.get_player_full()
        ppos = None
        if player.get("system_id") is not None:
            sys_row = db.get_system(player["system_id"])
            if sys_row:
                ppos = QPointF(sys_row["x"], sys_row["y"])
        rows = self._gal_panel.filtered_sorted(rows_all, ppos)
        self._gal_panel.populate(
            rows,
            self._list_font,
            icon_provider=lambda r: icon_from_path_or_kind(r.get("icon_path"), "star"),
        )

    def _populate_solar_list(self) -> None:
        # includes the Star entity (synthetic), plus planets and stations
        rows_all = self.solar.get_entities()
        ppos = QPointF(0.0, 0.0)  # player's reference in Solar view (center)
        rows = self._sol_panel.filtered_sorted(rows_all, ppos)
        self._sol_panel.populate(
            rows,
            self._list_font,
            icon_provider=lambda r: icon_from_path_or_kind(r.get("icon_path"), r.get("kind") or ""),
        )

    # ----- Hover/click leader line -----
    def _on_hover(self, which: str, eid: int) -> None:
        if which == "galaxy":
            if self._gal_locked_id is not None:
                return
            self._attach_leader(which, eid)
        else:
            if self._sol_locked_id is not None:
                return
            self._attach_leader(which, eid)

    def _on_click(self, which: str, eid: int) -> None:
        """Click toggles lock: first click locks; clicking the same item again unlocks."""
        if which == "galaxy":
            # Toggle
            if self._gal_locked_id == eid:
                self._unlock("galaxy")
                return
            # Lock to new selection
            self.galaxy.center_on_entity(eid)
            self._gal_locked_id = eid
            self._attach_leader(which, eid)
        else:
            if self._sol_locked_id == eid:
                self._unlock("solar")
                return
            self.solar.center_on_entity(eid)
            self._sol_locked_id = eid
            self._attach_leader(which, eid)

    def _unlock(self, which: str) -> None:
        """Clear lock, hide leader line, and unselect the list item."""
        if which == "galaxy":
            self._gal_locked_id = None
            self.galaxy.set_leader_from_viewport_to_getter(None, None)
            try:
                self._gal_panel.list.clearSelection()
                self._gal_panel.list.setCurrentRow(-1)
            except Exception:
                pass
        else:
            self._sol_locked_id = None
            self.solar.set_leader_from_viewport_to_getter(None, None)
            try:
                self._sol_panel.list.clearSelection()
                self._sol_panel.list.setCurrentRow(-1)
            except Exception:
                pass

    def _on_leave_list(self, which: str) -> None:
        # If not locked, hide the leader line
        if which == "galaxy":
            if self._gal_locked_id is None:
                self.galaxy.set_leader_from_viewport_to_getter(None, None)
        else:
            if self._sol_locked_id is None:
                self.solar.set_leader_from_viewport_to_getter(None, None)

    def _refresh_leader(self, which: str) -> None:
        """Re-attach the leader after resize/scroll/tab change so the anchor keeps up."""
        if which == "galaxy":
            eid = self._gal_locked_id
            if eid is None:
                it = self._gal_panel.current_hover_item()
                if it is None:
                    return
                eid = int(it.data(Qt.ItemDataRole.UserRole))
            self._attach_leader("galaxy", eid)
        else:
            eid = self._sol_locked_id
            if eid is None:
                it = self._sol_panel.current_hover_item()
                if it is None:
                    return
                eid = int(it.data(Qt.ItemDataRole.UserRole))
            self._attach_leader("solar", eid)

    # ---- Core attach: computes the source anchor (in viewport coords),
    # ---- and gives PanZoomView a getter that returns the (moving) endpoint.
    def _attach_leader(self, which: str, eid: int) -> None:
        if which == "galaxy":
            view = self.galaxy
            panel = self._gal_panel
            item = self._find_item_by_id(panel.list, eid)
            if item is None:
                view.set_leader_from_viewport_to_getter(None, None)
                return
            anchor = panel.anchor_point_for_item(view.viewport(), item)  # viewport coords
            dst_getter = self._make_dst_getter(view, anchor, eid)
            view.set_leader_from_viewport_to_getter(anchor, dst_getter)
        else:
            view = self.solar
            panel = self._sol_panel
            item = self._find_item_by_id(panel.list, eid)
            if item is None:
                view.set_leader_from_viewport_to_getter(None, None)
                return
            anchor = panel.anchor_point_for_item(view.viewport(), item)
            dst_getter = self._make_dst_getter(view, anchor, eid)
            view.set_leader_from_viewport_to_getter(anchor, dst_getter)

    def _make_dst_getter(self, view, anchor: QPoint, eid: int):
        """Factory for the destination getter used by the leader line."""
        def _dst():
            info = view.get_entity_viewport_center_and_radius(eid)
            if not info:
                return None
            center, radius = info
            # Trim the line so it touches the icon's edge, not the center.
            dx = center.x() - anchor.x()
            dy = center.y() - anchor.y()
            dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
            ux, uy = dx / dist, dy / dist
            return QPoint(int(round(center.x() - ux * radius)), int(round(center.y() - uy * radius)))
        return _dst

    @staticmethod
    def _find_item_by_id(listw: QListWidget, eid: int) -> Optional[QListWidgetItem]:
        for i in range(listw.count()):
            it = listw.item(i)
            if int(it.data(Qt.ItemDataRole.UserRole)) == int(eid):
                return it
        return None

    def _open_system_in_solar(self, system_id: int) -> None:
        self.setCurrentIndex(1)
        self.solar.load(system_id=system_id)
        self._populate_solar_list()
        self.solar.center_on_system(system_id)
        self._log(f"Opened Solar view for system id {system_id}.")
