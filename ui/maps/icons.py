# /ui/maps/icons.py

"""
GIF-only icon utilities for map visuals.

- Planet/star/station map items are GIFs via QMovie.
- Deterministic size variance support (up to +50% by default).
- Provides icon_from_path_or_kind and pm_from_path_or_kind (GIF-first) so
  existing callers (e.g., tabs.py) continue to work without SVGs.

Smoothness fixes:
- Each frame is painted onto a fixed-size transparent canvas (movie.frameRect()) to
  eliminate per-frame crop/offset jitter from trimmed GIFs.
- Scaled size and item offset are constant across frames.
- Uses ItemCoordinateCache (avoids device-pixel snapping).
- No ItemIgnoresTransformations; instead we apply an inverse view-scale so icons keep
  a constant on-screen size without rounding artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QImage, QMovie, QPixmap, QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsView, QGraphicsItem

import hashlib

# Max growth as a fraction of the base size (0.50 = up to +50% bigger)
ICON_SIZE_VARIANCE_MAX = 0.50


def randomized_px(base_px: int, *, salt: Optional[object] = None, variance: float = ICON_SIZE_VARIANCE_MAX) -> int:
    """Return base_px grown by [0 .. variance], deterministically from salt."""
    try:
        variance = float(variance)
    except Exception:
        variance = ICON_SIZE_VARIANCE_MAX
    if variance <= 0:
        return int(base_px)
    h = hashlib.sha1()
    h.update(str(base_px).encode('utf-8'))
    if salt is not None:
        h.update(str(salt).encode('utf-8'))
    r = (int(h.hexdigest(), 16) % 10000) / 10000.0
    scale = 1.0 + r * float(variance)
    return max(1, int(round(base_px * scale)))


def list_gifs(folder: str | Path) -> List[Path]:
    p = Path(folder)
    if not p.exists():
        return []
    return sorted([pp for pp in p.iterdir() if pp.suffix.lower() == ".gif"])


# ---------- Small helpers for list icons / pixmaps (GIF-first) ----------

def _first_frame_from_gif(path: Path) -> Optional[QPixmap]:
    """Extract first frame from GIF for static usage (e.g., list icons)."""
    mv = QMovie(str(path))
    if not mv.isValid():
        return None
    mv.jumpToFrame(0)
    pm = mv.currentPixmap()
    return pm if not pm.isNull() else None


def pm_from_path_or_kind(path_or_none: Optional[str | Path], kind: str, desired_px: int = 24) -> QPixmap:
    """
    GIF-only: return a QPixmap from the first frame of the GIF at path_or_none.
    If the path is missing/invalid/non-GIF, return a tiny red placeholder.
    `kind` is ignored (kept for compatibility).
    """
    if path_or_none:
        p = Path(path_or_none)
        if p.exists() and p.suffix.lower() == ".gif":
            pm = _first_frame_from_gif(p)
            if pm is not None and not pm.isNull():
                # scale to desired size for crisp icons
                return pm.scaled(desired_px, desired_px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    # fallback tiny red pixel
    ph = QPixmap(2, 2)
    ph.fill(Qt.GlobalColor.red)
    return ph


def icon_from_path_or_kind(path_or_none: Optional[str | Path], kind: str) -> QIcon:
    """
    GIF-only: build a QIcon from the first frame of the GIF.
    If invalid/missing, returns a small red square icon.
    `kind` is ignored (kept for compatibility).
    """
    pm = pm_from_path_or_kind(path_or_none, kind, desired_px=24)
    return QIcon(pm)


# ---------- Animated map items (GIF-only) ----------

class AnimatedGifItem(QGraphicsPixmapItem):
    """
    QGraphicsPixmapItem that plays an animated GIF via QMovie and keeps a stable
    on-screen size (desired_px), with minimal jitter.

    - Uses a fixed logical canvas based on movie.frameRect().
    - Scales the canvas once to a constant target size; offset stays constant.
    - ItemCoordinateCache avoids device rounding artifacts.
    - Applies inverse view scale so icons remain constant size on screen.
    """
    def __init__(self, gif_path: str | Path, desired_px: int, view: QGraphicsView, parent=None):
        super().__init__(parent)
        self._desired_px = int(desired_px)
        self._view = view

        self._movie = QMovie(str(gif_path))
        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)

        # Fixed canvas & scaled size computed on first valid frame
        self._canvas_size: Optional[QSize] = None
        self._scaled_w: Optional[int] = None
        self._scaled_h: Optional[int] = None
        self._const_offset: Optional[Tuple[float, float]] = None

        # Cache in item coordinates to avoid device-pixel snapping
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)

        self._movie.frameChanged.connect(self._on_frame)
        self._movie.start()

    def _ensure_geometry(self, pm_native: QPixmap) -> None:
        """Compute constant canvas size, scaled size, and offset once."""
        if self._canvas_size is not None:
            return

        # Use the movie's logical frame rect as a stable canvas.
        base_rect = self._movie.frameRect()
        base_size = base_rect.size()
        if not base_size.isValid() or base_size.width() <= 0 or base_size.height() <= 0:
            base_size = pm_native.size()
        w0 = max(1, base_size.width())
        h0 = max(1, base_size.height())
        self._canvas_size = QSize(w0, h0)

        # Compute final scaled size (keep aspect) to approx desired_px box
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

        # Constant offset so the item is centered about its position
        self._const_offset = (-sw / 2.0, -sh / 2.0)

    def _on_frame(self, _frame_idx: int) -> None:
        pm_native = self._movie.currentPixmap()
        if pm_native.isNull():
            return

        self._ensure_geometry(pm_native)

        # ---- FIX: build QImage via (w, h, format) to avoid Optional[QSize] complaints ----
        size = self._canvas_size or pm_native.size()
        canvas = QImage(
            int(size.width()),
            int(size.height()),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        canvas.fill(Qt.GlobalColor.transparent)

        # Draw at the movie's logical top-left so trimmed frames align consistently
        base_rect = self._movie.frameRect()
        tl = base_rect.topLeft()
        p = QPainter(canvas)
        p.drawPixmap(QPoint(tl.x(), tl.y()), pm_native)
        p.end()

        # Scale to the constant final size (smooth)
        pm_canvas = QPixmap.fromImage(canvas)
        pm_scaled = pm_canvas.scaled(
            int(self._scaled_w or pm_canvas.width()),
            int(self._scaled_h or pm_canvas.height()),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.setPixmap(pm_scaled)

        # Constant offset (centered)
        if self._const_offset is not None:
            self.setOffset(self._const_offset[0], self._const_offset[1])

        # Keep size constant on screen by inverting current view scale
        self._apply_scale()

    def _apply_scale(self) -> None:
        tr = self._view.transform()
        sx = tr.m11()
        sy = tr.m22()
        if sx == 0 or sy == 0:
            return
        # Use uniform inverse scale to avoid anisotropic jitter if pixels are non-square
        inv = 1.0 / max(abs(sx), abs(sy))
        if self.scale() != inv:
            self.setScale(inv)

    def set_playing(self, playing: bool) -> None:
        if playing and self._movie.state() != QMovie.MovieState.Running:
            self._movie.start()
        elif not playing and self._movie.state() == QMovie.MovieState.Running:
            self._movie.stop()


def make_map_symbol_item(
    gif_path: str | Path,
    desired_px: int,
    view: QGraphicsView,
    *,
    salt: Optional[object] = None,
    variance: Optional[float] = None,
) -> QGraphicsPixmapItem:
    """
    Create a GIF-only graphics item for the map.

    - Path MUST be a .gif that exists.
    - Size is randomized by up to `variance` (default ICON_SIZE_VARIANCE_MAX) using `salt`.
    """
    p = Path(gif_path)
    var = ICON_SIZE_VARIANCE_MAX if variance is None else float(variance)
    final_px = randomized_px(int(desired_px), salt=salt, variance=var)

    if p.suffix.lower() == ".gif" and p.exists():
        return AnimatedGifItem(p, final_px, view)

    # Tiny red placeholder rather than crashing; visible but harmless.
    pm = QPixmap(2, 2)
    pm.fill(Qt.GlobalColor.red)
    item = QGraphicsPixmapItem(pm)
    item.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
    item.setOffset(-pm.width() / 2.0, -pm.height() / 2.0)
    return item
