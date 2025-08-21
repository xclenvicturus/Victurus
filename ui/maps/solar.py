"""
SolarMapWidget (display-only):
- "solar-ish" layout:
    * central star at (0,0) using the system's assigned star icon
    * planets on static orbit rings (deterministic angles)
    * stations on interleaved rings (offset angles)
- background image per system if present:
    assets/solar_backgrounds/system_bg_<system_id>.png -> default.png
- background drawn in viewport coords (STATIC)
- planets/stations shown with their assigned icons (locations.icon_path)
"""

from __future__ import annotations

from math import radians, sin, cos
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QBrush, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene

from data import db
from .panzoom_view import PanZoomView
from .icons import pm_from_path_or_kind, pm_star_from_path

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
SOL_BG_DIR = ASSETS_ROOT / "solar_backgrounds"


class SolarMapWidget(PanZoomView):
    def __init__(self, log_fn: Callable[[str], None], parent=None) -> None:
        super().__init__(parent)
        self._log = log_fn
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._items: Dict[int, QGraphicsItem] = {}         # location_id -> item
        self._drawpos: Dict[int, Tuple[float, float]] = {}  # scene coords
        self._player_highlight: Optional[QGraphicsItem] = None
        self._system_id: Optional[int] = None
        self._locs_cache: List[Dict] = []

        self._spread = 8.0          # AU visual multiplier (orbit radii are in AU * spread)
        self.set_unit_scale(12.0)   # 1 AU base ~ 12 px

    # ---- Public helpers used by MapView ----
    def get_entities(self) -> List[Dict]:
        # include icon_path for list icons
        res: List[Dict] = []
        for l in self._locs_cache:
            sx, sy = self._drawpos.get(l["id"], (0.0, 0.0))
            res.append({
                "id": l["id"],
                "name": l["name"],
                "kind": l["kind"],
                "pos": QPointF(sx, sy),
                "icon_path": l["icon_path"],
            })
        return res

    def center_on_entity(self, entity_id: int) -> None:
        self.center_on_location(entity_id)

    def map_entity_to_viewport(self, entity_id: int) -> Optional[QPoint]:
        info = self.get_entity_viewport_center_and_radius(entity_id)
        return info[0] if info else None

    def get_entity_viewport_center_and_radius(self, entity_id: int) -> Optional[Tuple[QPoint, float]]:
        item = self._items.get(entity_id)
        if not item:
            return None
        scene_rect = item.mapToScene(item.boundingRect()).boundingRect()
        c_scene = scene_rect.center()
        c_vp = self.mapFromScene(c_scene)
        tl = self.mapFromScene(scene_rect.topLeft())
        br = self.mapFromScene(scene_rect.bottomRight())
        radius = max(abs(br.x() - tl.x()), abs(br.y() - tl.y())) / 2.0
        return c_vp, float(radius)

    # ---- Loading / drawing ----
    def load(self, system_id: int) -> None:
        self._system_id = system_id
        self._scene.clear()
        self._items.clear()
        self._drawpos.clear()
        self._player_highlight = None

        # Convert DB rows to plain dicts for type safety
        self._locs_cache = [dict(r) for r in db.get_locations(system_id)]

        # Background per system (optional, STATIC)
        bg_path = SOL_BG_DIR / f"system_bg_{system_id}.png"
        if not bg_path.exists():
            bg_path = SOL_BG_DIR / "default.png"
        if bg_path.exists():
            self.set_background_image(str(bg_path))
            self._log(f"Solar background (system {system_id}): {bg_path}")
        else:
            self.set_background_image(None)
            self._log(f"Solar background (system {system_id}): procedural gradient (no image found).")

        # Layout ingredients
        planets = [l for l in self._locs_cache if l["kind"] == "planet"]
        stations = [l for l in self._locs_cache if l["kind"] == "station"]

        # Scene rect: pick a radius that fits all rings comfortably
        n_rings = max(1, len(planets) + max(0, len(stations) // max(1, len(planets))) + 2)
        ring_gap_au = 1.2
        base_au = 1.5
        max_r_au = base_au + (n_rings + 1) * ring_gap_au
        pad = 2.0
        R = (max_r_au + pad) * self._spread
        self._scene.setSceneRect(-R, -R, 2 * R, 2 * R)

        # Determine current view scale for stable on-screen sizes
        view_scale = self.transform().m11() or 1.0

        # ---- Draw orbit rings (under everything else) ----
        pen = QPen()
        pen.setWidthF(0.03)  # thin
        for i in range(len(planets)):
            r = (base_au + i * ring_gap_au) * self._spread
            ring = self._scene.addEllipse(-r, -r, 2 * r, 2 * r, pen)
            ring.setZValue(-9)

        # ---- Draw star at center using the system's assigned star icon ----
        sys_row = db.get_system(system_id)
        star_icon_path = sys_row["star_icon_path"] if sys_row else None
        desired_px_star = 40
        pm_star = pm_star_from_path(star_icon_path, desired_px_star)
        star_item = QGraphicsPixmapItem(pm_star)
        w = pm_star.width()
        star_scale = (desired_px_star / (w * view_scale)) if w > 0 else 1.0
        star_item.setScale(star_scale)
        star_item.setOffset(-w * star_scale / 2.0, -pm_star.height() * star_scale / 2.0)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)  # above rings, below planets/stations
        self._scene.addItem(star_item)

        # ---- Place planets (even angles, deterministic) ----
        desired_px_planet = 24
        for i, l in enumerate(sorted(planets, key=lambda x: x["id"])):
            ring_r = (base_au + i * ring_gap_au) * self._spread
            angle_deg = (l["id"] * 137.50776) % 360.0   # golden angle for de-clumping
            a = radians(angle_deg)
            x = ring_r * cos(a)
            y = ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            pm = pm_from_path_or_kind(l.get("icon_path"), "planet", desired_px_planet)
            item = QGraphicsPixmapItem(pm)
            w = pm.width()
            scale = (desired_px_planet / (w * view_scale)) if w > 0 else 1.0
            item.setScale(scale)
            item.setOffset(-w * scale / 2.0, -pm.height() * scale / 2.0)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item

        # ---- Place stations (between rings, offset angles) ----
        desired_px_station = 24
        for j, l in enumerate(sorted(stations, key=lambda x: x["id"])):
            ring_index = min(len(planets) - 1, j % max(1, len(planets)))
            ring_r = (base_au + ring_index * ring_gap_au + ring_gap_au * 0.5) * self._spread
            angle_deg = ((l["id"] * 137.50776) + 40.0) % 360.0
            a = radians(angle_deg)
            x = ring_r * cos(a)
            y = ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            pm = pm_from_path_or_kind(l.get("icon_path"), "station", desired_px_station)
            item = QGraphicsPixmapItem(pm)
            w = pm.width()
            scale = (desired_px_station / (w * view_scale)) if w > 0 else 1.0
            item.setScale(scale)
            item.setOffset(-w * scale / 2.0, -pm.height() * scale / 2.0)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item

        # Highlight player location if present
        player = db.get_player_full()
        if player.get("current_location_id"):
            self.refresh_highlight(player["current_location_id"])

    def refresh_highlight(self, location_id: Optional[int]) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None
        if location_id is None:
            return
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        cx, cy = rect.center().x(), rect.center().y()
        r = max(rect.width(), rect.height()) * 1.2
        ring = self._scene.addEllipse(cx - r, cy - r, r * 2, r * 2)
        pen = ring.pen()
        pen.setWidthF(0.02)
        ring.setPen(pen)
        self._player_highlight = ring

    def center_on_system(self, system_id: int) -> None:
        self.centerOn(0.0, 0.0)

    def center_on_location(self, location_id: int) -> None:
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        self.centerOn(rect.center())
