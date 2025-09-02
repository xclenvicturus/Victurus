
# /ui/maps/background_view.py

"""Background View for Maps

Renders background images and animated starfields for map displays.
• Background image rendering in viewport or scene space
• Multi-layer animated starfield with random movement
• DPR-aware caching for performance optimization
• Smooth parallax effects and color customization
"""

from __future__ import annotations

import math
import random
from typing import List, Optional

from PySide6.QtCore import QTimer, Qt, QPoint
from settings import system_config as cfg
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

        # Keep scrollbars hidden. Allow interactions so users can pan the view.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Use ScrollHandDrag so click-dragging pans the view (hand tool).
        # Use getattr/hasattr to avoid static-analysis warnings about enum attributes
        try:
            dm = getattr(QGraphicsView, "DragMode", None)
            if dm is not None and hasattr(dm, "ScrollHandDrag"):
                self.setDragMode(getattr(dm, "ScrollHandDrag"))
            else:
                # Older runtimes may expose the enum directly on the class
                mode = getattr(QGraphicsView, "ScrollHandDrag", None)
                if mode is not None:
                    self.setDragMode(mode)
        except Exception:
            pass
        # Allow item/view interaction (needed for panning and event delivery)
        self.setInteractive(True)

        # Ensure the default cursor is inherited (arrow) while hovering;
        # unset any explicit cursors on the view and viewport so the widget
        # can inherit the platform default. Dragging will switch to a closed-hand.
        try:
            try:
                self.unsetCursor()
            except Exception:
                pass
            try:
                vp = self.viewport()
                if vp is not None:
                    try:
                        vp.unsetCursor()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

        # Use AnchorUnderMouse so incremental scale() calls keep the point
        # under the cursor fixed. We apply scale changes incrementally in
        # `_apply_unit_scale` so the anchor is effective for user-driven zooms.
        try:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        except Exception:
            pass

        # Cheaper update policy is fine now that starfield is cached (no per-frame re-draw loop).
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        # Unit scale: logical unit -> pixels (used by children when laying out)
        try:
            self._unit_px = float(getattr(cfg, "VIEW_UNIT_PX", 10.0))
        except Exception:
            self._unit_px = 10.0

        # Background image cache and mode
        self._bg_pixmap: Optional[QPixmap] = None
        # "viewport" (fixed to screen) or "scene" (locked to scene coordinates)
        self._bg_mode: str = "scene"

        # Starfield (tiled, cached)
        self._star_enabled = False
        self._star_timer: Optional[QTimer] = None  # kept for API compatibility; unused now
        self._star_time = 0.0  # kept for API compatibility

        # Cached starfield tiles & parameters (configurable)
        self._sf_layers: List[QPixmap] = []
        try:
            self._sf_tile_px: int = int(getattr(cfg, "STARFIELD_TILE_PX", 512))
        except Exception:
            self._sf_tile_px = 512
        try:
            self._sf_parallax: List[float] = list(getattr(cfg, "STARFIELD_PARALLAX", [0.20, 0.45, 0.85]))
        except Exception:
            self._sf_parallax = [0.20, 0.45, 0.85]
        try:
            self._sf_density: List[int] = list(getattr(cfg, "STARFIELD_DENSITY", [140, 90, 55]))
        except Exception:
            self._sf_density = [140, 90, 55]
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
        # Apply an incremental scale so the final scale equals _unit_px while
        # allowing the view's transformation anchor (AnchorUnderMouse) to
        # take effect. Compute current uniform scale from the transform and
        # scale by the ratio.
        try:
            tr = self.transform()
            cur = float(tr.m11()) if tr is not None else 1.0
            # Avoid degenerate current scale
            if abs(cur) < 1e-12:
                cur = 1.0
            factor = float(self._unit_px) / cur
            # If factor is effectively 1, do nothing
            if abs(factor - 1.0) < 1e-9:
                return
            # Use scale() so the transformation anchor is respected
            self.scale(factor, factor)
        except Exception:
            # Fallback to previous behavior if transform inspection fails
            try:
                self.resetTransform()
                self.scale(self._unit_px, self._unit_px)
            except Exception:
                pass

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

    def mousePressEvent(self, ev) -> None:
        # Forward to base so drag/pan behavior works
        try:
            # When the user presses to begin a potential pan, show the
            # grab/closed-hand cursor to indicate dragging. Default hover
            # stays as the normal pointer until press.
            try:
                left_btn = getattr(Qt, "LeftButton", None)
                closed_cur = getattr(Qt, "ClosedHandCursor", None)
                if left_btn is not None and ev.button() == left_btn and closed_cur is not None:
                    try:
                        self.setCursor(closed_cur)
                    except Exception:
                        pass
            except Exception:
                pass
            super().mousePressEvent(ev)
        except Exception:
            try:
                ev.ignore()
            except Exception:
                pass

    def mouseMoveEvent(self, ev) -> None:
        try:
            # If the user is holding a button while moving, keep the
            # closed-hand cursor; otherwise ensure the normal arrow cursor
            # is shown while hovering.
            try:
                buttons = getattr(ev, "buttons", lambda: 0)()
                closed_cur = getattr(Qt, "ClosedHandCursor", None)
                if buttons:
                    # button held -> dragging (cursor kept as closed hand)
                    if closed_cur is not None:
                        try:
                            self.setCursor(closed_cur)
                        except Exception:
                            pass
                        try:
                            vp = self.viewport()
                            if vp is not None:
                                vp.setCursor(closed_cur)
                        except Exception:
                            pass
                else:
                    # No buttons -> restore default/inherited cursor so the
                    # hand doesn't stick after a pan.
                    try:
                        self.unsetCursor()
                    except Exception:
                        pass
                    try:
                        vp = self.viewport()
                        if vp is not None:
                            try:
                                vp.unsetCursor()
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
            super().mouseMoveEvent(ev)
        except Exception:
            try:
                ev.ignore()
            except Exception:
                pass

    def mouseReleaseEvent(self, ev) -> None:
        try:
            # Restore normal pointer on release
            try:
                try:
                    self.unsetCursor()
                except Exception:
                    pass
                try:
                    vp = self.viewport()
                    if vp is not None:
                        try:
                            vp.unsetCursor()
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
            super().mouseReleaseEvent(ev)
        except Exception:
            try:
                ev.ignore()
            except Exception:
                pass

    def enterEvent(self, ev) -> None:
        """Ensure the arrow cursor is shown when the mouse enters the view."""
        try:
            try:
                self.unsetCursor()
            except Exception:
                pass
            try:
                vp = self.viewport()
                if vp is not None:
                    try:
                        vp.unsetCursor()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass
        try:
            super().enterEvent(ev)
        except Exception:
            pass

    def wheelEvent(self, ev) -> None:
        # Keep zoom disabled per recent UX decision
        ev.ignore()

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
