"""
Display-only QGraphicsView:
- No user zoom, panning, or scrolling (wheel/trackpad/keys blocked)
- Scrollbars hidden; view non-focusable
- Programmatic centering via centerOn still works (used by list actions)
- Background image is a STATIC viewport-layer image (never moves with camera)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal, QEvent
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsView


class PanZoomView(QGraphicsView):
    viewChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Display-only
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # CRITICAL: disable background caching; do full viewport repaints
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Hide scrollbars and prevent the view from taking keyboard focus
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Fixed unit scale (no user zoom)
        self._unit_scale = 1.0

        # Background image (drawn in viewport coords, never tied to scene)
        self._bg_pixmap: Optional[QPixmap] = None
        self._bg_cache_size: Optional[QSize] = None
        self._bg_scaled: Optional[QPixmap] = None  # scaled to cover viewport

    # ---- Background ----
    def set_background_image(self, path: Optional[str]) -> None:
        """Set a PNG/JPG path or None for no image (procedural gradient fallback)."""
        if path is None:
            self._bg_pixmap = None
            self._bg_scaled = None
            self._bg_cache_size = None
            self.viewport().update()
            return

        pm = QPixmap(path)
        if pm.isNull():
            self._bg_pixmap = None
            self._bg_scaled = None
            self._bg_cache_size = None
        else:
            self._bg_pixmap = pm
            self._bg_scaled = None
            self._bg_cache_size = None
        self.viewport().update()

    def _ensure_bg_scaled(self) -> None:
        if self._bg_pixmap is None:
            return
        if self._bg_cache_size == self.viewport().size() and self._bg_scaled is not None:
            return
        # Fit (cover) the viewport; then we center-crop when drawing
        self._bg_scaled = self._bg_pixmap.scaled(
            self.viewport().size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._bg_cache_size = self.viewport().size()

    def drawBackground(self, painter: QPainter, rect) -> None:
        # DO NOT call super().drawBackground to avoid any internal caching artifacts.
        painter.save()
        painter.resetTransform()  # draw strictly in viewport coords

        w, h = self.viewport().width(), self.viewport().height()

        # Clear the viewport first (prevents any smearing/overlap)
        if self._bg_pixmap is None:
            # Procedural gradient fallback
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(6, 8, 15))
            grad.setColorAt(1.0, QColor(12, 15, 28))
            painter.fillRect(0, 0, w, h, grad)
            painter.restore()
            return

        self._ensure_bg_scaled()
        if self._bg_scaled is None:
            painter.fillRect(0, 0, w, h, QColor(6, 8, 15))
            painter.restore()
            return

        # Center-crop from the scaled pixmap (STATIC: independent of scene/camera)
        sx = max(0, (self._bg_scaled.width() - w) // 2)
        sy = max(0, (self._bg_scaled.height() - h) // 2)

        painter.drawPixmap(0, 0, self._bg_scaled, sx, sy, w, h)
        painter.restore()

    # ---- Fixed unit scale ----
    def set_unit_scale(self, s: float) -> None:
        """Apply a fixed scale once; no user zoom."""
        self._unit_scale = float(s)
        self._apply_fixed_scale()

    def _apply_fixed_scale(self) -> None:
        super().resetTransform()
        self.scale(self._unit_scale, self._unit_scale)
        self.viewChanged.emit()
        self.viewport().update()

    # ---- Hard block all user scrolling/zooming/gesture inputs ----
    def wheelEvent(self, event) -> None:
        event.accept()

    def keyPressEvent(self, event) -> None:
        event.accept()

    def keyReleaseEvent(self, event) -> None:
        event.accept()

    def event(self, ev) -> bool:
        if ev.type() == QEvent.Type.NativeGesture:
            ev.accept()
            return True
        return super().event(ev)

    # Keep overlays in sync on programmatic moves
    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._bg_cache_size = None
        self.viewport().update()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        # Called by programmatic centerOn(); keep it so centering works,
        # but emit signal so overlays update.
        super().scrollContentsBy(dx, dy)
        self.viewChanged.emit()
        self.viewport().update()
