"""
SolarMapWidget (display-only):
- "solar-ish" layout:
    * central star at (0,0) using the system's assigned star icon (supports GIF)
    * planets on static orbit rings (deterministic angles)
    * stations on interleaved rings (offset angles)
- static background per system (image or gradient)
- animated starfield (twinkling) behind items
- planets/stations use their DB-assigned icons (supports GIF)
- star is included in the entity list (click to center)
"""

from __future__ import annotations

from math import radians, sin, cos
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from data import db
from .panzoom_view import PanZoomView
from .icons import pm_from_path_or_kind, pm_star_from_path, make_map_symbol_item

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
SOL_BG_DIR = ASSETS_ROOT / "solar_backgrounds"


class SolarMapWidget(PanZoomView):
    def __init__(self, log_fn: Callable[[str], None], parent=None) -> None:
        super().__init__(parent)
        self._log = log_fn
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._items: Dict[int, QGraphicsItem] = {}         # location_id -> item (not star)
        self._drawpos: Dict[int, Tuple[float, float]] = {}  # scene coords
        self._player_highlight: Optional[QGraphicsItem] = None
        self._system_id: Optional[int] = None
        self._locs_cache: List[Dict] = []

        self._star_item: Optional[QGraphicsItem] = None
        self._star_entity_id: Optional[int] = None          # synthetic id = -system_id
        self._star_radius_px: float = 20.0                  # for overlay line endpoint calculations

        self._spread = 8.0          # AU visual multiplier (orbit radii are in AU * spread)
        self.set_unit_scale(12.0)   # 1 AU base ~ 12 px
        self.enable_starfield(True)  # twinkling stars

    # ---- Public helpers used by MapView ----
    def get_entities(self) -> List[Dict]:
        # include star as an entity at (0,0)
        res: List[Dict] = []
        if self._system_id is not None:
            sysrow = db.get_system(self._system_id)
            if sysrow:
                self._star_entity_id = -int(sysrow["id"])
                res.append({
                    "id": self._star_entity_id,
                    "name": f"{sysrow['name']} Star",
                    "kind": "star",
                    "pos": QPointF(0.0, 0.0),
                    "icon_path": sysrow["star_icon_path"],
                })

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
        # special-case star
        if self._star_entity_id is not None and int(entity_id) == int(self._star_entity_id):
            self.center_on_system(self._system_id or 0)
            return
        self.center_on_location(entity_id)

    def map_entity_to_viewport(self, entity_id: int) -> Optional[QPoint]:
        info = self.get_entity_viewport_center_and_radius(entity_id)
        return info[0] if info else None

    def get_entity_viewport_center_and_radius(self, entity_id: int) -> Optional[Tuple[QPoint, float]]:
        # star?
        if self._star_entity_id is not None and int(entity_id) == int(self._star_entity_id):
            c_vp = self.mapFromScene(QPointF(0.0, 0.0))
            return c_vp, float(self._star_radius_px)

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
        self._star_item = None
        self._star_entity_id = None

        # Convert DB rows to plain dicts
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

        # Scene rect fits all rings comfortably
        n_rings = max(1, len(planets) + max(0, len(stations) // max(1, len(planets))) + 2)
        ring_gap_au = 1.2
        base_au = 1.5
        max_r_au = base_au + (n_rings + 1) * ring_gap_au
        pad = 2.0
        R = (max_r_au + pad) * self._spread
        self._scene.setSceneRect(-R, -R, 2 * R, 2 * R)

        # ---- Orbit rings (under everything) ----
        from PySide6.QtGui import QPen
        pen = QPen()
        pen.setWidthF(0.03)
        for i in range(len(planets)):
            r = (base_au + i * ring_gap_au) * self._spread
            ring = self._scene.addEllipse(-r, -r, 2 * r, 2 * r, pen)
            ring.setZValue(-9)

        # ---- Central star (supports GIF) ----
        sys_row = db.get_system(system_id)
        star_icon_path = sys_row["star_icon_path"] if sys_row else None
        desired_px_star = 40
        star_item = make_map_symbol_item(star_icon_path, "star", desired_px_star, self)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)
        self._scene.addItem(star_item)
        self._star_item = star_item
        # Use desired px for overlay radius (stable)
        self._star_radius_px = desired_px_star / 2.0

        # ---- Planets (even angles) ----
        desired_px_planet = 24
        for i, l in enumerate(sorted(planets, key=lambda x: x["id"])):
            ring_r = (base_au + i * ring_gap_au) * self._spread
            angle_deg = (l["id"] * 137.50776) % 360.0
            a = radians(angle_deg)
            x = ring_r * cos(a)
            y = ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            item = make_map_symbol_item(l.get("icon_path"), "planet", desired_px_planet, self)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item

        # ---- Stations (between rings, offset angles) ----
        desired_px_station = 24
        for j, l in enumerate(sorted(stations, key=lambda x: x["id"])):
            ring_index = min(len(planets) - 1, j % max(1, len(planets)))
            ring_r = (base_au + ring_index * ring_gap_au + ring_gap_au * 0.5) * self._spread
            angle_deg = ((l["id"] * 137.50776) + 40.0) % 360.0
            a = radians(angle_deg)
            x = ring_r * cos(a)
            y = ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            item = make_map_symbol_item(l.get("icon_path"), "station", desired_px_station, self)
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

    def center_on_system(self, system_id: int | None) -> None:
        self.centerOn(0.0, 0.0)

    def center_on_location(self, location_id: int) -> None:
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        self.centerOn(rect.center())
