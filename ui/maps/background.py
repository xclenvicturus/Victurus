# /ui/maps/panzoom_view.py

"""
BackgroundView
- background image; can be drawn in viewport ("screen") or scene space
- Animated starfield layers (optional)
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Callable

from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPixmap, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class BackgroundView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Global animations toggle (starfield, GIFs, orbits in subclasses)
        self._animations_enabled = True

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

        # Unit scale: logical unit -> pixels (used by children when laying out)
        self._unit_px = 10.0

        # Background image cache and mode
        self._bg_pixmap: Optional[QPixmap] = None
        # "viewport" (fixed to screen) or "scene" (locked to scene coordinates)
        self._bg_mode: str = "scene"

        # Starfield
        self._star_enabled = False
        self._star_timer: Optional[QTimer] = None
        self._star_time = 0.0
        self._star_layers: List[dict] = []

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

    # ---------- Starfield ----------
    def enable_starfield(self, enabled: bool) -> None:
        """Toggle the animated starfield (screen-fixed overlay)."""
        self._star_enabled = bool(enabled)
        if self._star_enabled:
            self._regen_starfield()
            self._ensure_star_timer()
        else:
            if self._star_timer is not None:
                self._star_timer.stop()
                self._star_timer.deleteLater()
            self._star_timer = None
            self._star_layers.clear()
            self.viewport().update()

    def _ensure_star_timer(self) -> None:
        if self._star_timer is None and self._animations_enabled and self._star_enabled:
            self._star_timer = QTimer(self)
            self._star_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._star_timer.setInterval(16)                 # <-- ~60 FPS
            self._star_timer.timeout.connect(self._tick_starfield)
            self._star_timer.start()
            self._star_time = 0.0

    def _tick_starfield(self) -> None:
        self._star_time += 0.016  # keep ≈1.0 “time units” per second at 60 FPS
        self.viewport().update()

    def _regen_starfield(self) -> None:
        """Generate stars anchored to the viewport size (screen coords)."""
        if not self._star_enabled:
            return
        w = max(1, self.viewport().width())
        h = max(1, self.viewport().height())
        area = w * h

        def clamp(n: int, mn: int, mx: int) -> int:
            return max(mn, min(mx, n))

        # Determine star counts for each layer based on viewport area.
        # We use integer division of area by a heuristic divisor to scale count with size,
        # then clamp to a sensible min/max so small/huge viewports still look good.
        # The names indicate visual role: "far" are many tiny faint stars, "near" are fewer larger/brighter ones,
        # "spark" are rarer bright twinkles, and color-named layers add accent hues.
        cnt_far     = clamp(area // 9000,   80, 300)   # distant, tiny pale-blue stars (highest density)
        cnt_mid     = clamp(area // 13000,  60, 240)   # mid-distance slightly larger stars (medium density)
        cnt_near    = clamp(area // 18000,  40, 180)   # near, larger white stars (lower density)
        cnt_spark   = clamp(area // 24000,  30, 140)   # occasional bright sparkles (animated twinkles)
        cnt_red     = clamp(area // 22000,  20, 120)   # colored accent layer (pink/salmon)
        cnt_green   = clamp(area // 21000,  20, 120)   # colored accent layer (mint/green)
        cnt_amber   = clamp(area // 17000,  12, 100)   # amber / orange-yellow accents
        cnt_cyan    = clamp(area // 25000,   8,  80)   # cyan / turquoise accents
        cnt_magenta = clamp(area // 26000,   6,  70)   # magenta / purple-pink accents
        cnt_orange  = clamp(area // 19500,  10,  90)   # orange accents
        cnt_teal    = clamp(area // 23000,   8,  80)   # teal / sea green accents
        cnt_violet  = clamp(area // 24000,   7,  70)   # violet / lavender accents
        cnt_ice     = clamp(area // 30000,   4,  50)   # very sparse pale-cyan "ice" accents
        cnt_gold    = clamp(area // 20000,  10,  80)   # warm gold/yellow accents
        cnt_indigo  = clamp(area // 22000,   8,  70)   # indigo / bluish accents
        cnt_silver  = clamp(area // 28000,   5,  60)   # sparse silver / light gray-blue accents
        cnt_blush   = clamp(area // 24000,   6,  70)   # soft blush/pink
        cnt_lilac   = clamp(area // 26000,   5,  60)   # lilac
        cnt_mint    = clamp(area // 25000,   6,  60)   # mint
        cnt_peach   = clamp(area // 23000,   6,  65)   # peach
        cnt_azure   = clamp(area // 27000,   5,  60)   # azure
        cnt_lemon   = clamp(area // 22000,   6,  65)   # lemon
        cnt_rose    = clamp(area // 21000,   7,  70)   # rose
        cnt_slate   = clamp(area // 30000,   4,  55)   # slate/steel
        cnt_emerald = clamp(area // 20000,   6,  65)   # emerald green
        cnt_cobalt  = clamp(area // 28000,   4,  60)   # cobalt blue

        rng = random.Random(1337 + w * 31 + h * 17)

        def make_layer(count: int, size_px: int, color: QColor, spd: float, amp: float, base_alpha: int) -> dict:
            pos = [(rng.uniform(0, w), rng.uniform(0, h)) for _ in range(count)]
            phase = [rng.uniform(0, math.tau) for _ in range(count)]
            return {"pos": pos, "phase": phase, "size": size_px, "color": color, "spd": spd, "amp": amp, "base": base_alpha}

        far_layer     = make_layer(cnt_far,     1, QColor(180, 200, 255), spd=0.9, amp=75.0,  base_alpha=130)
        mid_layer     = make_layer(cnt_mid,     2, QColor(220, 235, 255), spd=1.2, amp=90.0,  base_alpha=160)
        near_layer    = make_layer(cnt_near,    3, QColor(255, 255, 255), spd=1.6, amp=105.0, base_alpha=180)
        spark_layer   = make_layer(cnt_spark,   2, QColor(255, 250, 225), spd=3.2, amp=140.0, base_alpha=150)
        red_layer     = make_layer(cnt_red,     2, QColor(255, 100, 110), spd=2.0, amp=120.0, base_alpha=140)
        green_layer   = make_layer(cnt_green,   3, QColor(100, 255, 140), spd=2.2, amp=120.0, base_alpha=140)
        amber_layer   = make_layer(cnt_amber,   2, QColor(255, 180,  90), spd=1.8, amp=100.0, base_alpha=140)
        cyan_layer    = make_layer(cnt_cyan,    2, QColor( 80, 220, 230), spd=2.5, amp=110.0, base_alpha=130)
        magenta_layer = make_layer(cnt_magenta, 2, QColor(230, 100, 230), spd=2.8, amp=120.0, base_alpha=130)
        orange_layer  = make_layer(cnt_orange,  3, QColor(255, 140,  80), spd=1.9, amp=110.0, base_alpha=140)
        teal_layer    = make_layer(cnt_teal,    2, QColor( 80, 200, 160), spd=2.1, amp=115.0, base_alpha=135)
        violet_layer  = make_layer(cnt_violet,  3, QColor(180, 120, 255), spd=2.4, amp=125.0, base_alpha=140)
        ice_layer     = make_layer(cnt_ice,     1, QColor(200, 230, 255), spd=3.6, amp=150.0, base_alpha=120)
        gold_layer    = make_layer(cnt_gold,    3, QColor(255, 220, 120), spd=1.4, amp= 95.0, base_alpha=150)
        indigo_layer  = make_layer(cnt_indigo,  2, QColor(120, 140, 255), spd=1.7, amp=105.0, base_alpha=130)
        silver_layer  = make_layer(cnt_silver,  1, QColor(210, 210, 220), spd=3.0, amp= 90.0, base_alpha=110)
        blush_layer   = make_layer(cnt_blush,   2, QColor(255, 180, 190), spd=2.6, amp=110.0, base_alpha=130)
        lilac_layer   = make_layer(cnt_lilac,   2, QColor(210, 170, 240), spd=2.7, amp=115.0, base_alpha=125)
        mint_layer    = make_layer(cnt_mint,    2, QColor(180, 255, 220), spd=2.4, amp=105.0, base_alpha=130)
        peach_layer   = make_layer(cnt_peach,   2, QColor(255, 200, 170), spd=2.0, amp=100.0, base_alpha=130)
        azure_layer   = make_layer(cnt_azure,   2, QColor(140, 200, 255), spd=1.9, amp=100.0, base_alpha=140)
        lemon_layer   = make_layer(cnt_lemon,   2, QColor(250, 245, 150), spd=2.1, amp=105.0, base_alpha=130)
        rose_layer    = make_layer(cnt_rose,    2, QColor(240, 120, 140), spd=2.3, amp=110.0, base_alpha=130)
        slate_layer   = make_layer(cnt_slate,   1, QColor(150, 170, 190), spd=3.1, amp= 85.0, base_alpha=110)
        emerald_layer = make_layer(cnt_emerald, 2, QColor(80, 200, 140),  spd=2.2, amp=110.0, base_alpha=135)
        cobalt_layer  = make_layer(cnt_cobalt,  2, QColor(100, 140, 220), spd=2.5, amp=115.0, base_alpha=125)

        self._star_layers = [
            far_layer, mid_layer, near_layer, spark_layer,
            red_layer, green_layer,
            amber_layer, cyan_layer, magenta_layer, orange_layer, teal_layer,
            violet_layer, ice_layer, gold_layer, indigo_layer, silver_layer,
            # appended extras
            blush_layer, lilac_layer, mint_layer, peach_layer, azure_layer,
            lemon_layer, rose_layer, slate_layer, emerald_layer, cobalt_layer
        ]
        self.viewport().update()

    # ---------- Painting ----------
    def drawBackground(self, painter: QPainter, rect) -> None:
        # Background
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

        # Starfield overlay — always draw in device coords so it shows reliably
        if self._star_enabled and self._star_layers:
            painter.save()
            painter.resetTransform()
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
                    a = base + math.sin(self._star_time * spd + ph) * amp if getattr(self, '_animations_enabled', True) else base
                    a = max(0.0, min(255.0, a))
                    c = QColor(color)
                    c.setAlpha(int(a))
                    painter.setBrush(c)
                    r = size_px * 0.5
                    painter.drawEllipse(int(x - r), int(y - r), int(size_px), int(size_px))
            if self._cm_src_over is not None:
                painter.setCompositionMode(self._cm_src_over)
            painter.restore()


    # ---------- Events ----------
    def resizeEvent(self, ev) -> None:
        self._apply_unit_scale()
        if self._star_enabled:
            self._regen_starfield()
            self._ensure_star_timer()
        super().resizeEvent(ev)

    def mousePressEvent(self, ev) -> None: ev.ignore()
    def mouseMoveEvent(self, ev) -> None: ev.ignore()
    def mouseReleaseEvent(self, ev) -> None: ev.ignore()
    def wheelEvent(self, ev) -> None: ev.ignore()

    # ---------- Toggle animations ----------
    def set_animations_enabled(self, enabled: bool) -> None:
        self._animations_enabled = bool(enabled)
        # Starfield timer
        if self._star_enabled:
            if self._animations_enabled:
                self._ensure_star_timer()
            else:
                if self._star_timer is not None and self._star_timer.isActive():
                    self._star_timer.stop()
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