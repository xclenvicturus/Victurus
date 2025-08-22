"""
Shape helpers for map rendering.
"""

from __future__ import annotations

from math import cos, pi, sin
from PySide6.QtGui import QPainterPath


def make_star_path(cx: float, cy: float, r_outer: float, r_inner: float, points: int = 5) -> QPainterPath:
    path = QPainterPath()
    angle = -pi / 2  # start pointing up
    step = pi / points
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * cos(angle)
        y = cy + r * sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
        angle += step
    path.closeSubpath()
    return path
