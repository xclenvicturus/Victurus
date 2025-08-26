# /ui/maps/panzoom_view.py

"""
BackgroundView
- background image; can be drawn in viewport ("screen") or scene space
- Tiled starfield layers (optional, cached & DPR-aware for performance)
"""

from __future__ import annotations

import math
import random
from typing import List, Optional

from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class BackgroundView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Global animations toggle (GIFs, orbits in subclasses). Starfield is now cached & doesn't need a timer.
        self._animations_enabled = True

        # Base scene setup
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Try to accelerate painting using GPU via OpenGL viewport
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            self.setViewport(QOpenGLWidget())
        except Exception:
            pass

        # Keep scrollbars hidden and disable interactions (we navigate via lists)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)

        # Cheaper update policy is fine now that starfield is cached (no per-frame re-draw loop).
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        # Unit scale: logical unit -> pixels (used by children when laying out)
        self._unit_px = 10.0

        # Background image cache and mode
        self._bg_pixmap: Optional[QPixmap] = None
        # "viewport" (fixed to screen) or "scene" (locked to scene coordinates)
        self._bg_mode: str = "scene"

        # Starfield (tiled, cached)
        self._star_enabled = False
        self._star_timer: Optional[QTimer] = None  # kept for API compatibility; unused now
        self._star_time = 0.0  # kept for API compatibility

        # Cached starfield tiles & parameters
        self._sf_layers: List[QPixmap] = []                 # one pixmap per parallax layer
        self._sf_tile_px: int = 512                         # logical tile size (px)
        self._sf_parallax: List[float] = [0.20, 0.45, 0.85] # slow -> fast layer factors
        self._sf_density: List[int] = [140, 90, 55]         # stars-per-tile per layer
        try:
            self._sf_dpr: float = float(self.devicePixelRatioF())
        except Exception:
            self._sf_dpr = 1.0

        # Composition modes (handle PySide runtime + type-checkers)
        self._cm_plus = self._resolve_composition_mode("CompositionMode_Plus", "Plus")
        self._cm_src_over = self._resolve_composition_mode("CompositionMode_SourceOver", "SourceOver")

    # ---------- Background ----------
    def set_background_mode(self, mode: str) -> None:
        self._bg_mode = "scene" if str(mode).lower() == "scene" else "viewport"
        self.viewport().update()

    def set_background_image(self, path: Optional[str]) -> None:
        """Set a background image. For gradients, pass None."""
        if not path:
            self._bg_pixmap = None
            self.viewport().update()
            return
        img = QImage(path)
        if img.isNull():
            self._bg_pixmap = None
        else:
            self._bg_pixmap = QPixmap.fromImage(img)
        self.viewport().update()

    # ---------- Unit scale ----------
    def set_unit_scale(self, scale: float) -> None:
        """Set logical-to-pixel unit multiplier."""
        self._unit_px = float(scale)

    def _apply_unit_scale(self) -> None:
        self.resetTransform()
        self.scale(self._unit_px, self._unit_px)

    # ---------- Starfield (tiled) ----------
    def enable_starfield(self, enabled: bool) -> None:
        """Toggle starfield overlay (tiled & cached). No timer required."""
        self._star_enabled = bool(enabled)
        if self._star_enabled:
            self._regen_starfield_tiles()
            # Stop/remove any legacy timer
            if self._star_timer is not None:
                try:
                    self._star_timer.stop()
                    self._star_timer.deleteLater()
                except Exception:
                    pass
            self._star_timer = None
        else:
            self._sf_layers.clear()
        self.viewport().update()

    # Legacy method kept (unused) for compatibility with older call sites.
    def _ensure_star_timer(self) -> None:
        pass

    def _tick_starfield(self) -> None:
        # Kept for API compatibility; no-op since starfield is cached.
        self._star_time += 0.016
        self.viewport().update()

    def _regen_starfield_tiles(self) -> None:
        """Create small tiled pixmaps once per DPR. Each layer is a 512x512 (logical)
        pixmap pre-filled with random stars. We then tile & parallax these quickly."""
        self._sf_layers.clear()
        tile_w = max(1, int(self._sf_tile_px * self._sf_dpr))
        tile_h = max(1, int(self._sf_tile_px * self._sf_dpr))
        fmt = QImage.Format.Format_ARGB32_Premultiplied

        base_seed = 1234567

        for li, density in enumerate(self._sf_density):
            img = QImage(tile_w, tile_h, fmt)
            img.fill(0)  # transparent
            p = QPainter(img)
            try:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                rnd = random.Random(base_seed + li * 10007)

                # Batch by brightness to minimize state switches
                for brightness, ratio in ((255, 0.55), (190, 0.30), (120, 0.15)):
                    count = int(density * ratio)
                    color = QColor(255, 255, 255, brightness)
                    p.setPen(color)
                    for _ in range(count):
                        x = rnd.randrange(tile_w)
                        y = rnd.randrange(tile_h)
                        p.drawPoint(x, y)
            finally:
                p.end()

            pm = QPixmap.fromImage(img)
            try:
                pm.setDevicePixelRatio(self._sf_dpr)
            except Exception:
                pass
            self._sf_layers.append(pm)

    # ---------- Painting ----------
    def drawBackground(self, painter: QPainter, rect) -> None:
        # Background image
        if self._bg_pixmap:
            if self._bg_mode == "scene":
                # Draw in scene coordinates, centered over sceneRect
                srect = self.sceneRect()
                pm = self._bg_pixmap
                pw, ph = pm.width(), pm.height()
                if pw > 0 and ph > 0:
                    sw, sh = srect.width(), srect.height()
                    sx = sw / pw
                    sy = sh / ph
                    s = max(sx, sy)
                    tw, th = pw * s, ph * s
                    tlx = srect.center().x() - tw / 2.0
                    tly = srect.center().y() - th / 2.0
                    painter.drawPixmap(int(tlx), int(tly), int(tw), int(th), pm)
            else:
                # Viewport mode: draw in device (screen) coords
                painter.save()
                painter.resetTransform()
                vp = self.viewport().rect()
                painter.drawPixmap(vp, self._bg_pixmap, self._bg_pixmap.rect())
                painter.restore()
        else:
            # Gradient fallback in device coords
            painter.save()
            painter.resetTransform()
            vp = self.viewport().rect()
            grad = QLinearGradient(0, 0, 0, vp.height())
            grad.setColorAt(0.0, QColor(5, 8, 20))
            grad.setColorAt(1.0, QColor(10, 14, 30))
            painter.fillRect(vp, QBrush(grad))
            painter.restore()

        # Starfield overlay — draw tiled cached layers in device coords, with parallax
        if self._star_enabled and self._sf_layers:
            painter.save()
            painter.resetTransform()

            # Stable parallax based on scene position of the viewport's top-left
            tl_scene = self.mapToScene(self.viewport().rect().topLeft())
            base_x = float(tl_scene.x())
            base_y = float(tl_scene.y())

            vis = self.viewport().rect()
            tw = self._sf_tile_px
            th = self._sf_tile_px

            for pm, factor in zip(self._sf_layers, self._sf_parallax):
                ox = int((base_x * factor)) % tw
                oy = int((base_y * factor)) % th
                painter.drawTiledPixmap(vis, pm, QPoint(-ox, -oy))

            painter.restore()

    # ---------- Events ----------
    def resizeEvent(self, ev) -> None:
        self._apply_unit_scale()
        # Regenerate tiles if DPR changed (HiDPI scale factor change)
        try:
            new_dpr = float(self.devicePixelRatioF())
        except Exception:
            new_dpr = 1.0
        if abs(new_dpr - self._sf_dpr) > 1e-3:
            self._sf_dpr = new_dpr
            if self._star_enabled:
                self._regen_starfield_tiles()
        super().resizeEvent(ev)

    def mousePressEvent(self, ev) -> None: ev.ignore()
    def mouseMoveEvent(self, ev) -> None: ev.ignore()
    def mouseReleaseEvent(self, ev) -> None: ev.ignore()
    def wheelEvent(self, ev) -> None: ev.ignore()

    # ---------- Toggle animations ----------
    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = bool(enabled)
        # (No starfield timer anymore)
        # Pause/resume GIF items
        try:
            from .icons import AnimatedGifItem
            if self.scene():
                for it in self.scene().items():
                    try:
                        if isinstance(it, AnimatedGifItem):
                            it.set_playing(self._animations_enabled)
                    except Exception:
                        continue
        except Exception:
            pass
        self.viewport().update()

    # ---------- Helpers ----------
    @staticmethod
    def _resolve_composition_mode(attr_top: str, attr_nested: str):
        try:
            val = getattr(QPainter, attr_top)
            return val
        except Exception:
            pass
        try:
            CM = getattr(QPainter, "CompositionMode")
            return getattr(CM, attr_nested)
        except Exception:
            return None
