"""
MapView tabs + side panels + hover overlay.

Galaxy list now shows each system's assigned star icon from DB (systems.star_icon_path).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSplitter, QTabWidget, QVBoxLayout, QWidget

from data import db
from .galaxy import GalaxyMapWidget
from .solar import SolarMapWidget
from .overlays import HoverLineOverlay
from .panels import SidePanel
from .icons import icon_from_path_or_kind


class MapView(QTabWidget):
    playerMoved = Signal()

    def __init__(self, log_fn) -> None:
        super().__init__()
        self._log = log_fn

        # Galaxy tab
        self.galaxy = GalaxyMapWidget(log_fn=self._log, parent=self)
        self._gal_overlay = HoverLineOverlay(self.galaxy.viewport())
        self._gal_overlay.setGeometry(self.galaxy.viewport().rect())
        self.galaxy.viewport().installEventFilter(self)

        self._gal_panel = SidePanel(
            categories=["All", "Systems"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Galaxy",
        )
        self._gal_panel.refreshRequested.connect(self.update_lists)
        self._gal_panel.anchorMoved.connect(lambda: self._refresh_overlay("galaxy"))

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

        # Solar tab
        self.solar = SolarMapWidget(log_fn=self._log, parent=self)
        self._sol_overlay = HoverLineOverlay(self.solar.viewport())
        self._sol_overlay.setGeometry(self.solar.viewport().rect())
        self.solar.viewport().installEventFilter(self)

        self._sol_panel = SidePanel(
            categories=["All", "Planet", "Station"],
            sorts=["Name A–Z", "Name Z–A", "X", "Y", "Distance to player"],
            title="Solar",
        )
        self._sol_panel.refreshRequested.connect(self.update_lists)
        self._sol_panel.anchorMoved.connect(lambda: self._refresh_overlay("solar"))

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

        # Add tabs
        self.addTab(galaxy_tab, "Galaxy (pc)")
        self.addTab(solar_tab, "Solar (AU)")

        # State for overlay locking
        self._gal_locked_id: Optional[int] = None
        self._sol_locked_id: Optional[int] = None

        # Galaxy list: double-click → open system tab
        self._gal_panel.doubleClicked.connect(self._open_system_in_solar)

        self._list_font = QFont()
        self._list_font.setPointSize(14)

        self.currentChanged.connect(lambda _i: self._refresh_overlay("galaxy" if self.currentIndex() == 0 else "solar"))

        self.reload_all()

        # Hook side panel events (for hover line)
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
        self._refresh_overlay("galaxy")
        self._refresh_overlay("solar")

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
        rows_all = self.solar.get_entities()  # includes kind + pos + icon_path
        ppos = QPointF(0.0, 0.0)
        rows = self._sol_panel.filtered_sorted(rows_all, ppos)
        self._sol_panel.populate(
            rows,
            self._list_font,
            icon_provider=lambda r: icon_from_path_or_kind(r.get("icon_path"), r.get("kind")),
        )

    # ----- Hover/click connector line -----
    def _on_hover(self, which: str, eid: int) -> None:
        if which == "galaxy":
            if self._gal_locked_id is not None:
                return
            self._draw_hover_line(which, eid)
        else:
            if self._sol_locked_id is not None:
                return
            self._draw_hover_line(which, eid)

    def _on_click(self, which: str, eid: int) -> None:
        if which == "galaxy":
            self.galaxy.center_on_entity(eid)
            self._gal_locked_id = eid
            self._draw_hover_line(which, eid, lock=True)
        else:
            self.solar.center_on_entity(eid)
            self._sol_locked_id = eid
            self._draw_hover_line(which, eid, lock=True)

    def _on_leave_list(self, which: str) -> None:
        if which == "galaxy":
            if self._gal_locked_id is None:
                self._gal_overlay.clear()
        else:
            if self._sol_locked_id is None:
                self._sol_overlay.clear()

    def _refresh_overlay(self, which: str) -> None:
        if which == "galaxy":
            eid = self._gal_locked_id
            item = None
            if eid is None:
                item = self._gal_panel.current_hover_item()
                if item is None:
                    return
                eid = int(item.data(Qt.ItemDataRole.UserRole))
            else:
                item = self._find_item_by_id(self._gal_panel.list, eid)
                if item is None:
                    return
            self._draw_hover_line("galaxy", eid, item=item, lock=self._gal_locked_id is not None)
        else:
            eid = self._sol_locked_id
            item = None
            if eid is None:
                item = self._sol_panel.current_hover_item()
                if item is None:
                    return
                eid = int(item.data(Qt.ItemDataRole.UserRole))
            else:
                item = self._find_item_by_id(self._sol_panel.list, eid)
                if item is None:
                    return
            self._draw_hover_line("solar", eid, item=item, lock=self._sol_locked_id is not None)

    def _edge_endpoint(self, mid: QPoint, center: QPoint, radius_px: float) -> QPoint:
        dx = center.x() - mid.x()
        dy = center.y() - mid.y()
        dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
        ux, uy = dx / dist, dy / dist
        return QPoint(int(round(center.x() - ux * radius_px)), int(round(center.y() - uy * radius_px)))

    def _draw_hover_line(self, which: str, eid: int, item: Optional[QListWidgetItem] = None, lock: bool = False) -> None:
        if which == "galaxy":
            info = self.galaxy.get_entity_viewport_center_and_radius(eid)
            if not info:
                return
            center, radius = info
            it = item or self._find_item_by_id(self._gal_panel.list, eid)
            if it is None:
                return
            anchor = self._gal_panel.anchor_point_for_item(self._gal_overlay, it)
            mid = QPoint(max(0, anchor.x() - self._gal_overlay._stub), anchor.y())
            endpoint = self._edge_endpoint(mid, center, radius)
            if lock:
                self._gal_overlay.lock_to(anchor, endpoint)
            else:
                self._gal_overlay.show_temp(anchor, endpoint)
        else:
            info = self.solar.get_entity_viewport_center_and_radius(eid)
            if not info:
                return
            center, radius = info
            it = item or self._find_item_by_id(self._sol_panel.list, eid)
            if it is None:
                return
            anchor = self._sol_panel.anchor_point_for_item(self._sol_overlay, it)
            mid = QPoint(max(0, anchor.x() - self._sol_overlay._stub), anchor.y())
            endpoint = self._edge_endpoint(mid, center, radius)
            if lock:
                self._sol_overlay.lock_to(anchor, endpoint)
            else:
                self._sol_overlay.show_temp(anchor, endpoint)

    @staticmethod
    def _find_item_by_id(listw: QListWidget, eid: int) -> Optional[QListWidgetItem]:
        for i in range(listw.count()):
            it = listw.item(i)
            if int(it.data(Qt.ItemDataRole.UserRole)) == int(eid):
                return it
        return None

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize:
            if hasattr(self, "galaxy") and obj is self.galaxy.viewport():
                self._gal_overlay.setGeometry(self.galaxy.viewport().rect())
            if hasattr(self, "solar") and obj is self.solar.viewport():
                self._sol_overlay.setGeometry(self.solar.viewport().rect())
        return super().eventFilter(obj, ev)

    def _open_system_in_solar(self, system_id: int) -> None:
        self.setCurrentIndex(1)
        self.solar.load(system_id=system_id)
        self._populate_solar_list()
        self.solar.center_on_system(system_id)
        self._log(f"Opened Solar view for system id {system_id}.")
