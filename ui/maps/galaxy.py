"""
GalaxyMapWidget (display-only):
- integer pc coordinates
- systems shown with their assigned star icon (DB: systems.star_icon_path)
- static background (image or gradient)
- animated starfield (twinkling) behind items
- GIF icons supported on the map (via AnimatedGifItem) and static in lists
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from data import db
from .panzoom_view import PanZoomView
from .icons import pm_star_from_path, make_map_symbol_item

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
GAL_BG_DIR = ASSETS_ROOT / "galaxy_backgrounds"


class GalaxyMapWidget(PanZoomView):
    def __init__(self, log_fn: Callable[[str], None], parent=None) -> None:
        super().__init__(parent)
        self._log = log_fn
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._system_items: Dict[int, QGraphicsItem] = {}
        self._player_highlight: Optional[QGraphicsItem] = None

        self.set_unit_scale(10.0)  # 1 pc base ~ 10 px
        self.enable_starfield(True)  # twinkling stars

        # Galaxy background (optional, STATIC)
        default_bg = GAL_BG_DIR / "default.png"
        if default_bg.exists():
            self.set_background_image(str(default_bg))
            self._log(f"Galaxy background: {default_bg}")
        else:
            self.set_background_image(None)
            self._log("Galaxy background: procedural gradient (assets/galaxy_backgrounds/default.png not found).")

    # ---- Public helpers used by MapView ----
    def get_entities(self) -> List[Dict]:
        systems = db.get_systems()  # includes star_icon_path
        out: List[Dict] = []
        for s in systems:
            out.append({
                "id": s["id"],
                "name": s["name"],
                "kind": "system",
                "pos": QPointF(s["x"], s["y"]),
                "icon_path": s["star_icon_path"],
            })
        return out

    def center_on_entity(self, entity_id: int) -> None:
        self.center_on_system(entity_id)

    def map_entity_to_viewport(self, entity_id: int) -> Optional[QPoint]:
        info = self.get_entity_viewport_center_and_radius(entity_id)
        return info[0] if info else None

    def get_entity_viewport_center_and_radius(self, entity_id: int) -> Optional[Tuple[QPoint, float]]:
        item = self._system_items.get(entity_id)
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
    def load(self) -> None:
        self._scene.clear()
        self._system_items.clear()
        self._player_highlight = None

        systems = db.get_systems()
        if not systems:
            self._scene.setSceneRect(-5, -5, 10, 10)
            return

        min_x = min(s["x"] for s in systems)
        max_x = max(s["x"] for s in systems)
        min_y = min(s["y"] for s in systems)
        max_y = max(s["y"] for s in systems)
        pad = 5
        self._scene.setSceneRect(min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

        # Add icons (supports GIF via make_map_symbol_item)
        desired_px = 28
        for s in systems:
            x, y = s["x"], s["y"]
            item = make_map_symbol_item(s["star_icon_path"], "star", desired_px, self)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._system_items[s["id"]] = item

        # Player highlight
        player = db.get_player_full()
        if player.get("system_id") is not None:
            self.refresh_highlight(player["system_id"])
            self.center_on_system(player["system_id"])
        else:
            self.centerOn((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def refresh_highlight(self, system_id: int) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None

        item = self._system_items.get(system_id)
        if not item:
            return

        rect = item.mapToScene(item.boundingRect()).boundingRect()
        cx, cy = rect.center().x(), rect.center().y()
        r = max(rect.width(), rect.height()) * 0.7
        ring = self._scene.addEllipse(cx - r, cy - r, r * 2, r * 2)
        pen = ring.pen()
        pen.setWidthF(0.08)
        ring.setPen(pen)
        self._player_highlight = ring

    def center_on_system(self, system_id: int) -> None:
        item = self._system_items.get(system_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        self.centerOn(rect.center())
