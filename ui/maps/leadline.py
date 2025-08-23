from __future__ import annotations
from typing import Optional, Union

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

ColorLike = Union[QColor, str]


class LeadLine(QWidget):
    """
    Transparent overlay that draws the lead line over the map viewport on hover.
    Now supports runtime color/width (and an optional soft glow).
    The line:
      - starts at the list item's right edge point (projected into the map viewport)
      - draws a short horizontal stub into the map
      - then angles to the target symbol edge
    """
    def __init__(self, parent: Optional[QWidget]):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)

        self._active = False
        self._locked = False
        self._anchor = QPoint(0, 0)
        self._target = QPoint(0, 0)
        self._stub = 14  # px

        # Style
        self._color: QColor = QColor(0, 255, 128)   # neon green default
        self._width: int = 2                        # px
        self._glow_enabled: bool = True
        self._glow_extra_px: int = 6
        self._glow_alpha: int = 90                  # 0..255

    # ---------- public API (state) ----------
    def show_temp(self, anchor: QPoint, target_endpoint: QPoint):
        if self._locked:
            return
        self._active = True
        self._anchor = QPoint(anchor)
        self._target = QPoint(target_endpoint)
        self.update()

    def lock_to(self, anchor: QPoint, target_endpoint: QPoint):
        self._locked = True
        self._active = True
        self._anchor = QPoint(anchor)
        self._target = QPoint(target_endpoint)
        self.update()

    def clear(self):
        self._active = False
        self._locked = False
        self.update()

    # ---------- public API (style) ----------
    def set_style(
        self,
        color: Optional[ColorLike] = None,
        width: Optional[int] = None,
        glow_enabled: Optional[bool] = None,
        glow_extra_px: Optional[int] = None,
        glow_alpha: Optional[int] = None,
    ) -> None:
        if color is not None:
            self.set_color(color)
        if width is not None:
            self.set_width(width)
        if glow_enabled is not None:
            self._glow_enabled = bool(glow_enabled)
        if glow_extra_px is not None:
            try:
                self._glow_extra_px = max(0, int(glow_extra_px))
            except Exception:
                pass
        if glow_alpha is not None:
            try:
                self._glow_alpha = max(0, min(255, int(glow_alpha)))
            except Exception:
                pass
        self.update()

    def set_color(self, color: ColorLike) -> None:
        if isinstance(color, QColor):
            self._color = QColor(color)
        else:
            c = QColor(str(color))
            if c.isValid():
                self._color = c
        self.update()

    def set_width(self, width: int) -> None:
        try:
            self._width = max(1, int(width))
            self.update()
        except Exception:
            pass

    # ---------- painting ----------
    def paintEvent(self, _ev):
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        def mkpen(color: QColor, width: int) -> QPen:
            pen = QPen(color)
            pen.setWidth(width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            return pen

        mid = QPoint(max(0, self._anchor.x() - self._stub), self._anchor.y())

        # optional glow underlay
        if self._glow_enabled and self._glow_extra_px > 0 and self._width > 0:
            glow = QColor(self._color)
            glow.setAlpha(self._glow_alpha)
            p.setPen(mkpen(glow, self._width + self._glow_extra_px))
            p.drawLine(self._anchor, mid)
            p.drawLine(mid, self._target)

        # main stroke
        p.setPen(mkpen(self._color, self._width))
        p.drawLine(self._anchor, mid)
        p.drawLine(mid, self._target)
