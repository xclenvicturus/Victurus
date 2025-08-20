"""
GalaxyMapView (QGraphicsView)
- Pan via DragMode.ScrollHandDrag
- Wheel zoom anchored under mouse via ViewportAnchor.AnchorUnderMouse (Qt6)  # SCAFFOLD
"""
from __future__ import annotations
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent, QPainter
from .galaxy_scene import GalaxyScene


class GalaxyMapView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Keep a typed reference to our scene (helps Pylance and call sites)
        self.scene_obj = GalaxyScene(self)
        self.setScene(self.scene_obj)

        # Qt6 scoped enums:
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # pan
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # zoom focal point
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Zoom in/out with mouse wheel
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.scale(factor, factor)
