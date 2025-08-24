# /ui/maps/galaxy.py

"""
GalaxyMapWidget (display-only, GIF-only stars):
- systems shown with a star GIF (no SVGs)
- static background in viewport space (parallax vibe)
- animated starfield overlay (device coords)
- subtle highlight ring (no fill) when needed
- exposes: load(), get_entities(), center_on_entity(), get_entity_viewport_center_and_radius()
- get_entities() includes icon_path so list thumbnails show the correct star
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QPen, QColor, Qt
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from data import db
from .background import BackgroundView
from .icons import make_map_symbol_item, list_gifs

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
GAL_BG_DIR   = ASSETS_ROOT / "galaxy_backgrounds"
STARS_DIR    = ASSETS_ROOT / "stars"


def _deterministic_star_gif(system_id: int, star_gifs: List[Path]) -> Optional[Path]:
    if not star_gifs:
        return None
    idx = (system_id * 9176 + 37) % len(star_gifs)
    return star_gifs[idx]


class GalaxyMapWidget(BackgroundView):
    logMessage = Signal(str)
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._system_items: Dict[int, QGraphicsItem] = {}
        self._player_highlight: Optional[QGraphicsItem] = None

        self.set_unit_scale(10.0)
        self._apply_unit_scale()
        self.enable_starfield(True)
        self.set_background_mode("viewport")

        # Accept both "default.png" and "defaul.png"
        candidates = [GAL_BG_DIR / "default.png", GAL_BG_DIR / "defaul.png"]
        bg_path = next((p for p in candidates if p.exists()), None)
        if bg_path:
            self.set_background_image(str(bg_path))
            self.logMessage.emit(f"Galaxy background: {bg_path}")
        else:
            self.set_background_image(None)
            self.logMessage.emit("Galaxy background: gradient (no image found).")

        self._star_gifs: List[Path] = list_gifs(STARS_DIR)
        if not self._star_gifs:
            self.logMessage.emit("WARNING: No star GIFs found; placeholders will be used.")

        self.load()

    # ---------- Public API ----------
    def load(self) -> None:
        self._scene.clear()
        self._system_items.clear()
        self._player_highlight = None

        systems = [dict(r) for r in db.get_systems()]
        if not systems:
            self._scene.setSceneRect(-50, -50, 100, 100)
            return

        min_x = min(s["x"] for s in systems)
        max_x = max(s["x"] for s in systems)
        min_y = min(s["y"] for s in systems)
        max_y = max(s["y"] for s in systems)
        pad = 5
        self._scene.setSceneRect(min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

        desired_px = 28
        for s in systems:
            star_path = _deterministic_star_gif(s["id"], self._star_gifs) or Path("missing_star.gif")
            x, y = s["x"], s["y"]
            item = make_map_symbol_item(star_path, desired_px, self, salt=s["id"])
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._system_items[s["id"]] = item

        player = db.get_player_full()
        if player and player.get("current_player_system_id") is not None:
            self.refresh_highlight(player["current_player_system_id"])
            self.center_on_system(player["current_player_system_id"])
        else:
            self.centerOn((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        # Galaxy default zoom remains whatever unit*zoom currently is; lists can reset as needed.


    def get_entities(self) -> List[Dict]:
        rows = [dict(r) for r in db.get_systems()]
        for r in rows:
            gid = r.get("id")
            if gid is not None:
                p = _deterministic_star_gif(gid, self._star_gifs)
                r["icon_path"] = str(p) if p is not None else None
            else:
                r["icon_path"] = None
        return rows

    def center_on_entity(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())

    def get_entity_viewport_center_and_radius(self, system_id: int) -> Optional[Tuple[QPoint, float]]:
        it = self._system_items.get(system_id)
        if not it:
            return None
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        center = self.mapFromScene(rect.center())
        radius = max(rect.width(), rect.height()) * 0.5
        return (center, radius)

    # ---------- Helpers ----------
    def refresh_highlight(self, system_id: int) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        r = max(rect.width(), rect.height()) * 0.8


    def center_on_system(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())