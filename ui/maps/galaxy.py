from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPixmapItem,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from data import db
from .background_view import BackgroundView
from .icons import list_gifs, pm_from_path_or_kind, randomized_px
from game_controller.sim_loop import universe_sim

ASSETS_ROOT  = Path(__file__).resolve().parents[2] / "assets"
GAL_BG_DIR   = ASSETS_ROOT / "galaxy_backgrounds"
STARS_DIR    = ASSETS_ROOT / "stars"


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _as_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _norm_system_row(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize a systems row to {id, x, y, name, star_icon_path}.
    Accepts multiple schema variants: id/system_id, x/system_x, y/system_y, name/system_name, icon_path/star_icon_path.
    Returns None if id/x/y are missing.
    """
    sid = r.get("id", r.get("system_id", r.get("sys_id")))
    x   = r.get("x", r.get("system_x", r.get("sx")))
    y   = r.get("y", r.get("system_y", r.get("sy")))
    if sid is None or x is None or y is None:
        return None

    name = r.get("name", r.get("system_name"))
    icon = r.get("star_icon_path", r.get("icon_path"))
    return {
        "id":  _as_int(sid),
        "x":   _as_float(x),
        "y":   _as_float(y),
        "name": name if isinstance(name, str) else None,
        "star_icon_path": icon if isinstance(icon, str) else None,
    }


def _deterministic_star_gif(system_id: int, star_gifs: List[Path]) -> Optional[Path]:
    """Stable, per-system pick used only as a fallback when DB has no star_icon_path."""
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

        # --- perf: viewport & scene tuning ---
        try:
            self.setViewport(QOpenGLWidget())  # GPU-accelerated when available
        except Exception:
            pass
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        # Keep pixmaps crisp (we pre-scale to final size; this avoids blocky zoom artifacts)
        hints = self.renderHints()
        hints |= QPainter.RenderHint.SmoothPixmapTransform
        # Antialiasing not needed for these icons
        hints &= ~QPainter.RenderHint.Antialiasing
        self.setRenderHints(hints)

        try:
            self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        except Exception:
            pass

        self._system_items: Dict[int, QGraphicsItem] = {}
        self._player_highlight: Optional[QGraphicsItem] = None

        self.set_unit_scale(10.0)
        self._apply_unit_scale()
        self.enable_starfield(True)
        self.set_background_mode("viewport")

        # Background (accept both spellings)
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
            self.logMessage.emit("WARNING: No star GIFs found in /assets/stars; using placeholders.")

        # Keep ALL systems ticking while Galaxy is visible
        universe_sim.ensure_running()
        universe_sim.set_visible_system(None)

        self.load()

    # ---------- Public API ----------
    def load(self) -> None:
        self._scene.clear()
        self._system_items.clear()
        self._player_highlight = None

        # Normalize rows so we can tolerate schema differences
        raw = []
        try:
            raw = [dict(r) for r in db.get_systems()]
        except Exception:
            raw = []

        systems: List[Dict[str, Any]] = []
        for r in raw:
            n = _norm_system_row(r)
            if n is not None:
                systems.append(n)

        if not systems:
            self._scene.setSceneRect(-50, -50, 100, 100)
            self.logMessage.emit("Galaxy: no systems to display (check DB.get_systems()).")
            return

        min_x = min(s["x"] for s in systems)
        max_x = max(s["x"] for s in systems)
        min_y = min(s["y"] for s in systems)
        max_y = max(s["y"] for s in systems)
        pad = 5
        self._scene.setSceneRect(min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

        desired_px = 20  # smaller default icon; randomized slightly

        for s in systems:
            sid = int(s["id"])
            db_icon = s.get("star_icon_path")
            if db_icon:
                star_path: Path | str = db_icon
            else:
                star_path = _deterministic_star_gif(sid, self._star_gifs) or Path("missing_star.gif")

            x, y = float(s["x"]), float(s["y"])
            final_px = randomized_px(desired_px, salt=sid)

            # Pre-scale to the final size; no further view scaling applied
            pm = pm_from_path_or_kind(str(star_path), "star", final_px)
            item = QGraphicsPixmapItem(pm)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

            # Keep constant on-screen size regardless of view scale
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

            # Cache in device coords to avoid re-raster on minor moves/hover
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass

            # Center the pixmap at (x, y) (HiDPI-aware)
            try:
                dpr = pm.devicePixelRatio() if hasattr(pm, "devicePixelRatio") else 1.0
            except Exception:
                dpr = 1.0
            item.setOffset(-(pm.width() / dpr) / 2.0, -(pm.height() / dpr) / 2.0)

            self._scene.addItem(item)
            self._system_items[sid] = item

        # Center on player system if available
        player = {}
        try:
            player = db.get_player_full() or {}
        except Exception:
            player = {}
        sid = player.get("current_player_system_id")
        if isinstance(sid, int):
            self.refresh_highlight(sid)
            self.center_on_system(sid)
        else:
            self.centerOn((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def get_entities(self) -> List[Dict]:
        """
        Return systems for list panes, including the icon_path used to render each star.
        Prefers DB systems.star_icon_path; falls back to deterministic choice when missing.
        """
        rows = []
        try:
            rows = [dict(r) for r in db.get_systems()]
        except Exception:
            rows = []

        out: List[Dict[str, Any]] = []
        for r in rows:
            n = _norm_system_row(r)
            if n is None:
                continue
            sid = int(n["id"])
            db_icon = n.get("star_icon_path")
            if isinstance(db_icon, str) and db_icon:
                icon = db_icon
            else:
                p = _deterministic_star_gif(sid, self._star_gifs)
                icon = str(p) if p else None
            out.append({
                "id": sid,
                "name": n.get("name") or r.get("name") or r.get("system_name") or f"System {sid}",
                "x": n["x"],
                "y": n["y"],
                "icon_path": icon,
                "kind": "system",
            })
        return out

    def center_on_entity(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())
        universe_sim.set_visible_system(None)

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
        # Ring highlight can be added here if desired.

    def center_on_system(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())
        universe_sim.set_visible_system(None)
