"""
Overlay widgets used on top of map viewports.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class HoverLineOverlay(QWidget):
    """
    Transparent overlay that draws the hover/lock line over the map viewport.
    The line:
      - starts at the list item's right edge point (projected into the map viewport)
      - draws a short horizontal stub into the map
      - then angles to the target symbol edge
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._active = False
        self._locked = False
        self._anchor = QPoint(0, 0)
        self._target = QPoint(0, 0)
        self._stub = 14  # px

    def show_temp(self, anchor: QPoint, target_endpoint: QPoint):
        if self._locked:
            return
        self._active = True
        self._anchor = anchor
        self._target = target_endpoint
        self.update()

    def lock_to(self, anchor: QPoint, target_endpoint: QPoint):
        self._locked = True
        self._active = True
        self._anchor = anchor
        self._target = target_endpoint
        self.update()

    def clear(self):
        self._active = False
        self._locked = False
        self.update()

    def paintEvent(self, _ev):
        if not self._active:
            return
        p = QPainter(self)
        pen = QPen()
        pen.setWidth(2)
        p.setPen(pen)
        mid = QPoint(max(0, self._anchor.x() - self._stub), self._anchor.y())
        p.drawLine(self._anchor, mid)
        p.drawLine(mid, self._target)
