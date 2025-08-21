# ui/maps/panzoom_view.py
"""
PanZoomView
- Static background image drawn in viewport coordinates (no camera coupling)
- Animated starfield (four layers) behind scene items, drawn OVER the background:
    * far, mid, near (subtle twinkle)
    * spark (fast twinkle)
- No mouse panning or wheel zoom (navigation is via lists)
"""

from __future__ import annotations

import math
import random
from typing import List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class PanZoomView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Base scene setup
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Keep scrollbars hidden and disable interactions (we navigate via lists)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)

        # Ensure full repaints so our animated background always shows
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        # Anchor behavior (centers on target coordinates nicely)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Unit scale: world-to-pixel base ratio helper (used by maps)
        self._unit_scale: float = 1.0
        self._apply_unit_scale()  # start with identity

        # Background image (viewport static)
        self._bg_pixmap: Optional[QPixmap] = None

        # -------- Starfield (animated, viewport static) --------
        self._star_enabled: bool = False
        # each layer: {"pos": List[tuple], "phase": List[float], "size": int, "color": QColor, "spd": float, "amp": float, "base": int}
        self._star_layers: List[dict] = []
        self._star_time: float = 0.0
        self._star_timer: Optional[QTimer] = None

        # Resolve composition modes in a Pylance-friendly way (no direct enum refs)
        self._cm_plus = self._resolve_composition_mode("CompositionMode_Plus", "Plus")
        self._cm_src_over = self._resolve_composition_mode("CompositionMode_SourceOver", "SourceOver")

    # ---------------- Public API ----------------
    def set_unit_scale(self, scale: float) -> None:
        """Apply a constant base zoom to the view (no user zoom)."""
        self._unit_scale = float(scale)
        self._apply_unit_scale()

    def _apply_unit_scale(self) -> None:
        t = QTransform()
        t.scale(self._unit_scale, self._unit_scale)
        self.setTransform(t)

    def set_background_image(self, path: Optional[str]) -> None:
        """Set a static background image (PNG/JPG). Drawn in viewport coords."""
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

    def enable_starfield(self, enabled: bool) -> None:
        """Toggle the animated starfield (viewport static)."""
        if self._star_enabled == enabled:
            return
        self._star_enabled = enabled
        if enabled:
            self._ensure_star_timer()
            self._regen_starfield()
        else:
            if self._star_timer:
                self._star_timer.stop()
                self._star_timer.deleteLater()
            self._star_timer = None
            self._star_layers.clear()
            self.viewport().update()

    # ---------------- Internals: starfield ----------------
    def _ensure_star_timer(self) -> None:
        if self._star_timer is None:
            self._star_timer = QTimer(self)
            self._star_timer.setInterval(60)  # gentle ~16–17 FPS
            self._star_timer.timeout.connect(self._tick_starfield)
            self._star_timer.start()
            self._star_time = 0.0

    def _tick_starfield(self) -> None:
        self._star_time += 0.06
        # Paint only the background; scene will draw on top
        self.viewport().update()

    def _regen_starfield(self) -> None:
        """Generate stars anchored to the viewport size."""
        if not self._star_enabled:
            return
        w = max(1, self.viewport().width())
        h = max(1, self.viewport().height())
        area = w * h

        def clamp(n: int, mn: int, mx: int) -> int:
            return max(mn, min(mx, n))

        # Scale counts with area; keep a cap for perf
        cnt_far   = clamp(area // 9000,   80, 300)  # smallest/most distant
        cnt_mid   = clamp(area // 13000,  60, 240)
        cnt_near  = clamp(area // 18000,  40, 180)
        cnt_spark = clamp(area // 24000,  30, 140)  # NEW: fewer, fast twinkles

        rng = random.Random(1337 + w * 31 + h * 17)  # stable per-size seed

        def make_layer(count: int, size_px: int, color: QColor, spd: float, amp: float, base_alpha: int) -> dict:
            pos = [(rng.uniform(0, w), rng.uniform(0, h)) for _ in range(count)]
            phase = [rng.uniform(0, math.tau) for _ in range(count)]
            return {"pos": pos, "phase": phase, "size": size_px, "color": color, "spd": spd, "amp": amp, "base": base_alpha}

        # Slightly higher alphas so they pop over bright backgrounds
        far_layer   = make_layer(cnt_far,   1, QColor(180, 200, 255), spd=0.9, amp=75.0,  base_alpha=130)
        mid_layer   = make_layer(cnt_mid,   2, QColor(220, 235, 255), spd=1.2, amp=90.0,  base_alpha=160)
        near_layer  = make_layer(cnt_near,  3, QColor(255, 255, 255), spd=1.6, amp=105.0, base_alpha=180)
        spark_layer = make_layer(cnt_spark, 2, QColor(255, 250, 225), spd=3.2, amp=140.0, base_alpha=150)  # NEW fast twinkles

        # Draw order: far → mid → near → spark (spark on top)
        self._star_layers = [far_layer, mid_layer, near_layer, spark_layer]
        self.viewport().update()

    # ---------------- QGraphicsView overrides ----------------
    def drawBackground(self, painter: QPainter, rect) -> None:
        # Draw in viewport coordinates (static) THEN let the scene draw items over it
        painter.save()
        painter.resetTransform()
        vp = self.viewport().rect()

        # Background image or a soft gradient if none
        if self._bg_pixmap:
            painter.drawPixmap(vp, self._bg_pixmap, self._bg_pixmap.rect())
        else:
            grad = QLinearGradient(0, 0, 0, vp.height())
            grad.setColorAt(0.0, QColor(5, 8, 20))
            grad.setColorAt(1.0, QColor(10, 14, 30))
            painter.fillRect(vp, QBrush(grad))

        # Starfield drawn OVER the background (additive) but UNDER scene items
        if self._star_enabled and self._star_layers:
            if self._cm_plus is not None:
                painter.setCompositionMode(self._cm_plus)
            painter.setPen(Qt.PenStyle.NoPen)
            for layer in self._star_layers:
                size_px = layer["size"]
                color: QColor = layer["color"]
                spd = layer["spd"]
                amp = layer["amp"]
                base = layer["base"]
                for (x, y), ph in zip(layer["pos"], layer["phase"]):
                    a = base + math.sin(self._star_time * spd + ph) * amp
                    a = max(0.0, min(255.0, a))
                    c = QColor(color)
                    c.setAlpha(int(a))
                    painter.setBrush(c)
                    r = size_px * 0.5
                    painter.drawEllipse(int(x - r), int(y - r), int(size_px), int(size_px))
            if self._cm_src_over is not None:
                painter.setCompositionMode(self._cm_src_over)

        painter.restore()

    def resizeEvent(self, ev) -> None:
        # Regenerate star positions to fit new viewport size
        if self._star_enabled:
            self._regen_starfield()
            self._ensure_star_timer()
        super().resizeEvent(ev)

    # Disable mouse-based navigation
    def mousePressEvent(self, ev) -> None:
        ev.ignore()

    def mouseMoveEvent(self, ev) -> None:
        ev.ignore()

    def mouseReleaseEvent(self, ev) -> None:
        ev.ignore()

    def wheelEvent(self, ev) -> None:
        ev.ignore()

    # ---------------- Utilities ----------------
    @staticmethod
    def _resolve_composition_mode(attr_top: str, attr_nested: str):
        """
        Resolve QPainter composition modes in a way that satisfies both PySide6 runtime
        and Pylance static analysis (no direct enum attribute access).
        Tries QPainter.<attr_top> then QPainter.CompositionMode.<attr_nested>.
        Returns the enum value or None if unavailable.
        """
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
