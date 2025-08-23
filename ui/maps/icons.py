"""
GIF-only icon utilities for map visuals.

- Planet/star/station map items are GIFs via QMovie.
- Deterministic size variance support (up to +50% by default).
- Provides icon_from_path_or_kind and pm_from_path_or_kind (GIF-first) so
  existing callers (e.g., tabs.py) continue to work without SVGs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImage, QMovie, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsView

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
    on-screen size (desired_px) irrespective of view scale.
    """
    def __init__(self, gif_path: str | Path, desired_px: int, view: QGraphicsView, parent=None):
        super().__init__(parent)
        self._desired_px = int(desired_px)
        self._view = view
        self._playing = True

        self._movie = QMovie(str(gif_path))
        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)

        self._movie.frameChanged.connect(self._on_frame)
        self._movie.start()

    def _on_frame(self, _frame_index: int) -> None:
        pm_native = self._movie.currentPixmap()
        if not pm_native.isNull():
            pm_scaled = pm_native.scaled(
                self._desired_px, 
                self._desired_px, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(pm_scaled)
            self._apply_scale()

    def _apply_scale(self) -> None:
        pm = self.pixmap()
        if pm.isNull():
            return
        
        view_scale = self._view.transform().m11() or 1.0
        if view_scale == 0: return

        scale = 1.0 / view_scale
        self.setScale(scale)
        
        self.setOffset(-pm.width() / 2.0, -pm.height() / 2.0)

    def set_playing(self, playing: bool) -> None:
        playing = bool(playing)
        if self._playing == playing:
            return
        self._playing = playing
        if playing:
            self._movie.start()
        else:
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
    if p.suffix.lower() != ".gif" or not p.exists():
        # Tiny red placeholder rather than crashing; visible but harmless.
        pm = QPixmap(2, 2)
        pm.fill(Qt.GlobalColor.red)
        return QGraphicsPixmapItem(pm)

    var = ICON_SIZE_VARIANCE_MAX if variance is None else float(variance)
    final_px = randomized_px(int(desired_px), salt=salt, variance=var)
    return AnimatedGifItem(p, final_px, view)