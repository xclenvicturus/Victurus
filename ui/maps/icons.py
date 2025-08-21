"""
Icon & pixmap utilities for map visuals.

- Static & SVG support (fallback icons for star/planet/station)
- Optional animated GIF support for map items (QMovie)
- List icons always static; GIFs use their first frame
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImage, QMovie, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsView


ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
ICONS_DIR = ASSETS_ROOT / "icons"

# Default/fallback icons (SVGs recommended)
FALLBACKS = {
    "star": ICONS_DIR / "star.svg",
    "planet": ICONS_DIR / "planet.svg",
    "station": ICONS_DIR / "station.svg",
}


def _existing_path_or_none(p: Optional[str | Path]) -> Optional[Path]:
    if not p:
        return None
    pp = Path(p)
    return pp if pp.exists() else None


def _fallback_for_kind(kind: str) -> Path:
    return FALLBACKS.get(kind, FALLBACKS["planet"])


def _first_frame_from_gif(path: Path) -> Optional[QPixmap]:
    """Extract first frame from GIF for static usage (e.g., list icons)."""
    try:
        mv = QMovie(str(path))
        if not mv.isValid():
            return None
        # Jump to first frame and grab pixmap
        mv.jumpToFrame(0)
        pm = mv.currentPixmap()
        return pm if not pm.isNull() else None
    except Exception:
        return None


def _pixmap_from_path(path: Path, desired_px: int) -> QPixmap:
    """Load a QPixmap from an image path (SVG/PNG/JPG/GIF-first-frame)."""
    low = path.suffix.lower()
    if low == ".gif":
        pm = _first_frame_from_gif(path)
        if pm and not pm.isNull():
            return pm.scaled(desired_px, desired_px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        # fall through to generic loader if GIF failed
    if low == ".svg":
        # Let QIcon rasterize the SVG cleanly to desired size
        ic = QIcon(str(path))
        pm = ic.pixmap(QSize(desired_px, desired_px))
        if not pm.isNull():
            return pm
    # Generic raster load
    img = QImage(str(path))
    if not img.isNull():
        pm = QPixmap.fromImage(img)
        if not pm.isNull():
            return pm.scaled(desired_px, desired_px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    # If everything fails, return empty pixmap (caller should handle fallback)
    return QPixmap()


def pm_from_path_or_kind(path_or_none: Optional[str | Path], kind: str, desired_px: int) -> QPixmap:
    """
    Return a QPixmap for use on map items (static).
    If path is a GIF, returns its first frame (for static contexts).
    """
    p = _existing_path_or_none(path_or_none)
    if p is None:
        p = _fallback_for_kind(kind)
    pm = _pixmap_from_path(p, desired_px)
    if pm.isNull():
        # Final safety: try fallback kind icon
        pm = _pixmap_from_path(_fallback_for_kind(kind), desired_px)
    return pm


def pm_star_from_path(path_or_none: Optional[str | Path], desired_px: int) -> QPixmap:
    return pm_from_path_or_kind(path_or_none, "star", desired_px)


def icon_from_path_or_kind(path_or_none: Optional[str | Path], kind: str) -> QIcon:
    """
    Return a QIcon for list usage. If path is a GIF, uses its first frame.
    """
    p = _existing_path_or_none(path_or_none)
    if p is None:
        p = _fallback_for_kind(kind)

    if p.suffix.lower() == ".gif":
        pm = _first_frame_from_gif(p)
        if pm and not pm.isNull():
            return QIcon(pm)
        # else fall through

    if p.suffix.lower() == ".svg":
        return QIcon(str(p))

    img = QImage(str(p))
    if not img.isNull():
        return QIcon(QPixmap.fromImage(img))

    # Fallback to hardcoded kind icon if load failed
    fp = _fallback_for_kind(kind)
    return QIcon(str(fp))


# ---------- Animated map items ----------

class AnimatedGifItem(QGraphicsPixmapItem):
    """
    QGraphicsPixmapItem that plays an animated GIF via QMovie
    and keeps a stable on-screen size (desired_px) irrespective of view scale.
    """
    def __init__(self, gif_path: str | Path, desired_px: int, view: QGraphicsView, parent=None):
        super().__init__(parent)
        self._movie = QMovie(str(gif_path))
        self._desired_px = int(desired_px)
        self._view = view

        # Configure and start
        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
        # Leave default speed (100%) unless you want to tweak: self._movie.setSpeed(100)
        self._movie.frameChanged.connect(self._on_frame)
        self._movie.start()

    def _on_frame(self, _frame_index: int) -> None:
        pm = self._movie.currentPixmap()
        if pm.isNull():
            return
        # Compute scale so the on-screen size ~ desired_px no matter the view's base transform
        w = pm.width()
        view_scale = self._view.transform().m11() or 1.0
        scale = (self._desired_px / (w * view_scale)) if w > 0 else 1.0
        self.setScale(scale)
        self.setPixmap(pm)
        # Offset must be in UN-SCALED coords to remain centered
        self.setOffset(-pm.width() / 2.0, -pm.height() / 2.0)


def make_map_symbol_item(path_or_none: Optional[str | Path], kind: str, desired_px: int, view: QGraphicsView) -> QGraphicsPixmapItem:
    """
    Create a graphics item for the map:
      - If the path is a GIF, return an AnimatedGifItem
      - Else return a static QGraphicsPixmapItem with proper scale/offset
    """
    p = _existing_path_or_none(path_or_none)

    if p is not None and p.suffix.lower() == ".gif":
        return AnimatedGifItem(p, desired_px, view)

    pm = pm_from_path_or_kind(p, kind, desired_px)
    item = QGraphicsPixmapItem(pm)
    w = pm.width()
    view_scale = view.transform().m11() or 1.0
    item_scale = (desired_px / (w * view_scale)) if w > 0 else 1.0
    item.setScale(item_scale)
    # Offset must be UN-SCALED coords to stay centered
    item.setOffset(-pm.width() / 2.0, -pm.height() / 2.0)
    return item
