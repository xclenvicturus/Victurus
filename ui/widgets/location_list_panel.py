"""
Reusable right-side panel with:
- category dropdown
- sort dropdown
- live search box
- list view with hover/click/double-click signals
- distance column with color coding
- right-click context menu with "Travel to"
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QPoint, QEvent, Qt, Signal, QPointF
from PySide6.QtGui import QFont, QIcon, QColor, QBrush, QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
)


class LocationListPanel(QWidget):
    hovered = Signal(int)
    clicked = Signal(int)
    doubleClicked = Signal(int)
    leftView = Signal()
    refreshRequested = Signal()
    anchorMoved = Signal()
    travelHere = Signal(int)

    def __init__(self, categories: List[str], sorts: List[str], title: str):
        super().__init__()
        self.category = QComboBox()
        self.category.addItems(categories)

        self.sort = QComboBox()
        self.sort.addItems(sorts)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Name", "Distance"])
        self.tree.setMouseTracking(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        lay.addWidget(QLabel(title))
        lay.addWidget(self.category)
        lay.addWidget(self.sort)
        lay.addWidget(self.search)
        lay.addWidget(self.tree, 1)

        # Signals
        self.tree.itemEntered.connect(self._on_item_entered)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.search.textChanged.connect(self.refreshRequested.emit)
        self.category.currentIndexChanged.connect(self.refreshRequested.emit)
        self.sort.currentIndexChanged.connect(self.refreshRequested.emit)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        self.tree.viewport().installEventFilter(self)
        self.tree.verticalScrollBar().valueChanged.connect(self.anchorMoved.emit)
        self.tree.horizontalScrollBar().valueChanged.connect(self.anchorMoved.emit)

    def _show_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return

        entity_id = int(item.data(0, Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        travel_action = QAction("Travel to", self)
        travel_action.triggered.connect(lambda: self.travelHere.emit(entity_id))
        menu.addAction(travel_action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def eventFilter(self, obj, ev):
        if obj is self.tree.viewport():
            if ev.type() == QEvent.Type.Leave:
                self.leftView.emit()
            elif ev.type() == QEvent.Type.MouseMove:
                it = self.current_hover_item()
                if it:
                    self.hovered.emit(int(it.data(0, Qt.ItemDataRole.UserRole)))
            elif ev.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
                self.anchorMoved.emit()
        return super().eventFilter(obj, ev)

    def _on_item_entered(self, item: QTreeWidgetItem):
        self.hovered.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def _on_item_clicked(self, item: QTreeWidgetItem):
        self.clicked.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def _on_item_double_clicked(self, item: QTreeWidgetItem):
        self.doubleClicked.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def populate(self, rows: List[Dict], list_font: QFont, icon_provider: Optional[Callable[[Dict], Optional[QIcon]]] = None):
        self.tree.clear()
        self.tree.setFont(list_font)
        for r in rows:
            it = QTreeWidgetItem(self.tree, [r["name"], f"{r.get('distance', 0):.2f} {r.get('dist_unit', '')}"])
            it.setData(0, Qt.ItemDataRole.UserRole, r["id"])

            if icon_provider:
                icon = icon_provider(r)
                if icon:
                    it.setIcon(0, icon)

            color = QColor("red")
            if r.get("can_reach"):
                color = QColor("green")
            it.setForeground(1, QBrush(color))

        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

    def filtered_sorted(self, rows_all: List[Dict], player_pos: Optional[QPointF]) -> List[Dict]:
        cat = self.category.currentText()
        rows = [r for r in rows_all if not cat or cat == "All" or r.get("kind", "").lower().startswith(cat.lower())]

        q = self.search.text().strip().lower()
        if q:
            rows = [r for r in rows if q in r["name"].lower()]

        sort_key = self.sort.currentText()
        reverse = sort_key.endswith("Z–A")
        
        if "Name" in sort_key:
            rows.sort(key=lambda r: r["name"].lower(), reverse=reverse)
        elif sort_key == "X" and all('pos' in r for r in rows):
            rows.sort(key=lambda r: r.get("pos", QPointF(0,0)).x())
        elif sort_key == "Y" and all('pos' in r for r in rows):
            rows.sort(key=lambda r: r.get("pos", QPointF(0,0)).y())
        elif "Distance" in sort_key:
            rows.sort(key=lambda r: r.get('distance', float('inf')))
        
        return rows

    def anchor_point_for_item(self, overlay: QWidget, item: QTreeWidgetItem) -> QPoint:
        r = self.tree.visualItemRect(item)
        pt_view = r.center()
        pt_view.setX(r.right())
        p_global = self.tree.viewport().mapToGlobal(pt_view)
        p_overlay = overlay.mapFromGlobal(p_global)
        return QPoint(
            min(max(0, p_overlay.x()), overlay.width() - 1),
            min(max(0, p_overlay.y()), overlay.height() - 1)
        )

    def current_hover_item(self) -> Optional[QTreeWidgetItem]:
        pos = self.tree.viewport().mapFromGlobal(self.cursor().pos())
        return self.tree.itemAt(pos)