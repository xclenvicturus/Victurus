# /ui/maps/icons.py

"""
Image utilities for map visuals (GIF + PNG/JPG/SVG + Qt resources).

- Works with filesystem paths *and* Qt resource paths (":/..." or "qrc:/...").
- Falls back to searching your ./assets/* folders if a relative path is provided.
- Provides pm_from_path_or_kind (for list thumbnails) and make_map_symbol_item (map items).
- Animated GIFs via QMovie; static images via QPixmap or SVG renderer.

Jitter fixes:
- GIFs: each frame is drawn into a fixed canvas from movie.frameRect() and then scaled,
  so trimmed GIFs don't "swim".
- Static: ItemIgnoresTransformations keeps a constant on-screen size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QImage, QMovie, QPixmap, QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsView, QGraphicsItem

# Optional SVG
try:
    from PySide6.QtSvg import QSvgRenderer  # type: ignore
except Exception:  # pragma: no cover
    QSvgRenderer = None  # type: ignore

import hashlib

# ---------- constants ----------

ICON_SIZE_VARIANCE_MAX = 0.50

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
GIF_EXTS    = {".gif"}
SVG_EXTS    = {".svg", ".svgz"}

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
_ASSET_SUBFOLDERS = [
    "stars", "planets", "moons", "stations", "warp_gates",
    "asteroid_fields", "gas_clouds", "ice_fields", "crystal_veins",
    "system_backgrounds", "galaxy_backgrounds", "icons",
]

# ---------- helpers ----------

def randomized_px(base_px: int, *, salt: Optional[object] = None, variance: float = ICON_SIZE_VARIANCE_MAX) -> int:
    try:
        variance = float(variance)
    except Exception:
        variance = ICON_SIZE_VARIANCE_MAX
    if variance <= 0:
        return int(base_px)
    h = hashlib.sha1()
    h.update(str(base_px).encode("utf-8"))
    if salt is not None:
        h.update(str(salt).encode("utf-8"))
    r = (int(h.hexdigest(), 16) % 10000) / 10000.0
    return max(1, int(round(base_px * (1.0 + r * variance))))

def list_gifs(folder: str | Path) -> List[Path]:
    p = Path(folder)
    if not p.exists():
        return []
    return sorted([pp for pp in p.iterdir() if pp.suffix.lower() in GIF_EXTS])

def list_images(folder: str | Path) -> List[Path]:
    """Return common image files in folder (gif/png/jpg/jpeg/webp/svg/svgz), sorted."""
    p = Path(folder)
    if not p.exists():
        return []
    allowed = RASTER_EXTS | GIF_EXTS | SVG_EXTS
    return sorted([pp for pp in p.iterdir() if pp.suffix.lower() in allowed])

def _is_qt_resource(path_str: str) -> bool:
    # QRC paths typically start with ":" (":/folder/file.png") or "qrc:/"
    return path_str.startswith(":") or path_str.startswith("qrc:/")

def _candidate_paths(path_str: str) -> List[str]:
    """
    Build a list of candidate strings to try loading:
      1) as given (handles absolute, relative, and qrc)
      2) assets/<path_str>  (if relative)
      3) assets/<subdir>/<basename>
    """
    cands: List[str] = [path_str]
    p = Path(path_str)

    # If it's a qrc path, nothing else to try
    if _is_qt_resource(path_str):
        return cands

    # Try under assets root if relative or not found
    rel = Path(str(p).lstrip("/\\"))
    cand2 = ASSETS_ROOT / rel
    cands.append(str(cand2))

    # Try basename in common asset subfolders
    name = p.name
    if name:
        for sub in _ASSET_SUBFOLDERS:
            cands.append(str(ASSETS_ROOT / sub / name))

    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for s in cands:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq

# ---------- thumbnail pixmaps ----------

def _first_frame_from_gif_any(path_str: str) -> Optional[QPixmap]:
    for cand in _candidate_paths(path_str):
        mv = QMovie(cand)
        if mv.isValid():
            mv.jumpToFrame(0)
            pm = mv.currentPixmap()
            if not pm.isNull():
                return pm
    return None

def _pm_from_svg_any(path_str: str, desired_px: int) -> Optional[QPixmap]:
    if QSvgRenderer is None:
        return None
    for cand in _candidate_paths(path_str):
        try:
            r = QSvgRenderer(cand)
            if not r.isValid():
                continue
            img = QImage(desired_px, desired_px, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            try:
                r.render(p)
            finally:
                p.end()
            pm = QPixmap.fromImage(img)
            if not pm.isNull():
                return pm
        except Exception:
            continue
    return None

def _pm_from_raster_any(path_str: str) -> Optional[QPixmap]:
    for cand in _candidate_paths(path_str):
        pm = QPixmap(cand)
        if not pm.isNull():
            return pm
    return None

def _scaled(pm: QPixmap, desired_px: int) -> QPixmap:
    return pm.scaled(
        desired_px, desired_px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

def pm_from_path_or_kind(path_or_none: Optional[str | Path], kind: str, desired_px: int = 24) -> QPixmap:
    """
    Build a QPixmap preview for list thumbnails.
    Supports filesystem + Qt resource paths. Accepts GIF/PNG/JPG/SVG.
    """
    if path_or_none:
        s = str(path_or_none)
        ext = Path(s).suffix.lower()
        pm: Optional[QPixmap] = None
        if ext in GIF_EXTS:
            pm = _first_frame_from_gif_any(s)
        elif ext in RASTER_EXTS:
            pm = _pm_from_raster_any(s)
        elif ext in SVG_EXTS:
            pm = _pm_from_svg_any(s, desired_px)
        else:
            # Unknown ext: try raster first, then GIF as static fallback
            pm = _pm_from_raster_any(s) or _first_frame_from_gif_any(s)
        if pm is not None and not pm.isNull():
            return _scaled(pm, desired_px)

    # tiny red pixel placeholder
    ph = QPixmap(6, 6)
    ph.fill(Qt.GlobalColor.red)
    return ph

def icon_from_path_or_kind(path_or_none: Optional[str | Path], kind: str) -> QIcon:
    return QIcon(pm_from_path_or_kind(path_or_none, kind, desired_px=24))

# ---------- map items ----------

class AnimatedGifItem(QGraphicsPixmapItem):
    def __init__(self, gif_path: str, desired_px: int, view: QGraphicsView, parent=None):
        super().__init__(parent)
        self._desired_px = int(desired_px)
        self._view = view
        self._movie: Optional[QMovie] = None
        self._canvas_size: Optional[QSize] = None
        self._scaled_w: Optional[int] = None
        self._scaled_h: Optional[int] = None
        self._const_offset: Optional[Tuple[float, float]] = None
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)

        # Try all candidate paths for a valid movie
        for cand in _candidate_paths(gif_path):
            mv = QMovie(cand)
            if mv.isValid():
                self._movie = mv
                break

        if self._movie is None:
            # degrade to a tiny placeholder
            ph = QPixmap(6, 6)
            ph.fill(Qt.GlobalColor.red)
            self.setPixmap(ph)
            self.setOffset(-3, -3)
            return

        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self._movie.frameChanged.connect(self._on_frame)
        self._movie.start()

    def _ensure_geometry(self, pm_native: QPixmap) -> None:
        if self._canvas_size is not None:
            return
        base_rect = self._movie.frameRect() if self._movie else None
        base_size = base_rect.size() if base_rect is not None else pm_native.size()
        w0 = max(1, base_size.width())
        h0 = max(1, base_size.height())
        self._canvas_size = QSize(w0, h0)
        if w0 >= h0:
            scale = self._desired_px / float(w0)
            sw = self._desired_px
            sh = max(1, int(round(h0 * scale)))
        else:
            scale = self._desired_px / float(h0)
            sh = self._desired_px
            sw = max(1, int(round(w0 * scale)))
        self._scaled_w = sw
        self._scaled_h = sh
        self._const_offset = (-sw / 2.0, -sh / 2.0)

    def _on_frame(self, _frame_idx: int) -> None:
        if self._movie is None:
            return
        pm_native = self._movie.currentPixmap()
        if pm_native.isNull():
            return

        self._ensure_geometry(pm_native)

        size = self._canvas_size or pm_native.size()
        canvas = QImage(int(size.width()), int(size.height()), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)

        base_rect = self._movie.frameRect()
        tl = base_rect.topLeft()
        p = QPainter(canvas)
        p.drawPixmap(QPoint(tl.x(), tl.y()), pm_native)
        p.end()

        pm_canvas = QPixmap.fromImage(canvas)
        pm_scaled = pm_canvas.scaled(
            int(self._scaled_w or pm_canvas.width()),
            int(self._scaled_h or pm_canvas.height()),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.setPixmap(pm_scaled)
        if self._const_offset is not None:
            self.setOffset(self._const_offset[0], self._const_offset[1])
        self._apply_scale()

    def _apply_scale(self) -> None:
        tr = self._view.transform()
        sx = tr.m11()
        sy = tr.m22()
        if sx == 0 or sy == 0:
            return
        inv = 1.0 / max(abs(sx), abs(sy))
        if self.scale() != inv:
            self.setScale(inv)

    def set_playing(self, playing: bool) -> None:
        if self._movie is None:
            return
        if playing and self._movie.state() != QMovie.MovieState.Running:
            self._movie.start()
        elif not playing and self._movie.state() == QMovie.MovieState.Running:
            self._movie.stop()

class StaticImageItem(QGraphicsPixmapItem):
    def __init__(self, pm: QPixmap, desired_px: int, parent=None):
        super().__init__(parent)
        pm_scaled = pm.scaled(
            int(desired_px), int(desired_px),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pm_scaled)
        self.setOffset(-pm_scaled.width() / 2.0, -pm_scaled.height() / 2.0)
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

def make_map_symbol_item(
    img_path: str | Path,
    desired_px: int,
    view: QGraphicsView,
    *,
    salt: Optional[object] = None,
    variance: Optional[float] = None,
) -> QGraphicsPixmapItem:
    """
    Create a graphics item for the map.

    - GIFs -> AnimatedGifItem (tries resource and assets paths)
    - PNG/JPG/SVG -> StaticImageItem
    - On failure: small red placeholder (constant size)
    """
    var = ICON_SIZE_VARIANCE_MAX if variance is None else float(variance)
    final_px = randomized_px(int(desired_px), salt=salt, variance=var)

    s = str(img_path) if img_path is not None else ""
    if not s:
        # placeholder
        ph = QPixmap(6, 6)
        ph.fill(Qt.GlobalColor.red)
        item = QGraphicsPixmapItem(ph)
        item.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
        item.setOffset(-ph.width() / 2.0, -ph.height() / 2.0)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        return item

    ext = Path(s).suffix.lower()

    if ext in GIF_EXTS:
        return AnimatedGifItem(s, final_px, view)

    pm: Optional[QPixmap] = None
    if ext in RASTER_EXTS:
        pm = _pm_from_raster_any(s)
    elif ext in SVG_EXTS:
        pm = _pm_from_svg_any(s, final_px) if QSvgRenderer is not None else None
    else:
        # unknown ext: try raster then gif first frame as a static fallback
        pm = _pm_from_raster_any(s) or _first_frame_from_gif_any(s)

    if pm is not None and not pm.isNull():
        return StaticImageItem(pm, final_px)

    # placeholder
    ph = QPixmap(6, 6)
    ph.fill(Qt.GlobalColor.red)
    item = QGraphicsPixmapItem(ph)
    item.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
    item.setOffset(-ph.width() / 2.0, -ph.height() / 2.0)
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    return item
