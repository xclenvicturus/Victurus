# Victurus/engine/qtui/map/galaxy_scene.py
"""
GalaxyScene (QGraphicsScene)
- Renders systems/sectors as simple demo nodes until wired to DB.  # SCAFFOLD
- Call set_demo_systems() for a placeholder
- Later: add from world_service.get_systems() results (id, x, y, owner, name)
"""
from __future__ import annotations
from typing import Iterable, Mapping
from PySide6.QtWidgets import QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QPen

class GalaxyScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pen = QPen()  # SCAFFOLD: customize pen/brush later

    # SCAFFOLD: quick demo points so you can see pan/zoom working
    def set_demo_systems(self) -> None:
        self.clear()
        pts = [
            (0, 0, "Sol"), (400, 80, "Alpha"), (800, -50, "Beta"),
            (1200, 300, "Gamma"), (1600, -250, "Delta")
        ]
        for x, y, name in pts:
            self._add_star(x, y, name)
        self.setSceneRect(self.itemsBoundingRect())  # important for scrollbars

    # Future: drive from DB or service
    def set_systems(self, systems: Iterable[Mapping]) -> None:
        """
        systems: iterable of dicts with at least {'id','name','x','y'} (universe coords)
        """
        self.clear()
        for s in systems:
            self._add_star(float(s["x"]), float(s["y"]), str(s.get("name", s["id"])))
        self.setSceneRect(self.itemsBoundingRect())

    def _add_star(self, x: float, y: float, name: str) -> None:
        r = 8.0
        node = QGraphicsEllipseItem(QRectF(-r, -r, 2 * r, 2 * r))
        node.setPos(QPointF(x, y))
        node.setPen(self._pen)
        self.addItem(node)

        label = QGraphicsTextItem(name)
        label.setPos(QPointF(x + 10, y - 10))
        self.addItem(label)
