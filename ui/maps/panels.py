"""
Reusable right-side panel with:
- category dropdown
- sort dropdown
- live search box
- list view with hover/click/double-click signals
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QPoint, QEvent, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SidePanel(QWidget):
    hovered = Signal(int)        # entity_id
    clicked = Signal(int)        # entity_id
    doubleClicked = Signal(int)  # entity_id
    leftView = Signal()          # mouse left the list viewport
    refreshRequested = Signal()  # search/category/sort changed
    anchorMoved = Signal()       # list scrolled/resized → recompute anchor

    def __init__(self, categories: List[str], sorts: List[str], title: str):
        super().__init__()
        self.category = QComboBox()
        self.category.addItems(categories)

        self.sort = QComboBox()
        self.sort.addItems(sorts)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")

        self.list = QListWidget()
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        lay.addWidget(QLabel(title))
        lay.addWidget(self.category)
        lay.addWidget(self.sort)
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)

        # Signals
        self.list.itemEntered.connect(self._on_item_entered)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.search.textChanged.connect(lambda _t: self.refreshRequested.emit())
        self.category.currentIndexChanged.connect(lambda _i: self.refreshRequested.emit())
        self.sort.currentIndexChanged.connect(lambda _i: self.refreshRequested.emit())

        # Event filters + scrollbars drive anchor recompute
        self.list.viewport().installEventFilter(self)
        self.list.verticalScrollBar().valueChanged.connect(lambda _v: self.anchorMoved.emit())
        self.list.horizontalScrollBar().valueChanged.connect(lambda _v: self.anchorMoved.emit())

    def eventFilter(self, obj, ev):
        if obj is self.list.viewport():
            if ev.type() == QEvent.Type.Leave:
                self.leftView.emit()
            elif ev.type() == QEvent.Type.MouseMove:
                it = self.current_hover_item()
                if it is not None:
                    self.hovered.emit(int(it.data(Qt.ItemDataRole.UserRole)))
            elif ev.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
                self.anchorMoved.emit()
        return super().eventFilter(obj, ev)

    def _on_item_entered(self, item: QListWidgetItem):
        self.hovered.emit(int(item.data(Qt.ItemDataRole.UserRole)))

    def _on_item_clicked(self, item: QListWidgetItem):
        self.clicked.emit(int(item.data(Qt.ItemDataRole.UserRole)))

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self.doubleClicked.emit(int(item.data(Qt.ItemDataRole.UserRole)))

    def populate(self, rows: List[Dict], list_font: QFont, icon_provider: Optional[Callable[[Dict], Optional[QIcon]]] = None):
        self.list.clear()
        self.list.setFont(list_font)
        for r in rows:
            it = QListWidgetItem(r["name"])
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            if icon_provider:
                icon = icon_provider(r)
                if icon is not None:
                    it.setIcon(icon)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.list.addItem(it)
        self.list.setMouseTracking(True)
        self.list.setViewMode(QListWidget.ViewMode.ListMode)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    def filtered_sorted(self, rows_all: List[Dict], player_pos) -> List[Dict]:
        cat = self.category.currentText()
        if cat and cat != "All":
            rows = [r for r in rows_all if r.get("kind", "").lower().startswith(cat.lower())]
        else:
            rows = list(rows_all)

        q = self.search.text().strip().lower()
        if q:
            rows = [r for r in rows if q in r["name"].lower()]

        key = self.sort.currentText()
        if key == "Name A–Z":
            rows.sort(key=lambda r: r["name"].lower())
        elif key == "Name Z–A":
            rows.sort(key=lambda r: r["name"].lower(), reverse=True)
        elif key == "X":
            rows.sort(key=lambda r: r["pos"].x())
        elif key == "Y":
            rows.sort(key=lambda r: r["pos"].y())
        elif key == "Distance to player" and player_pos is not None:
            rows.sort(key=lambda r: (r["pos"] - player_pos).manhattanLength())
        else:
            rows.sort(key=lambda r: r["name"].lower())
        return rows

    def anchor_point_for_item(self, overlay: QWidget, item: QListWidgetItem) -> QPoint:
        r = self.list.visualItemRect(item)  # viewport coords
        pt_view = r.center()
        pt_view.setX(r.right())
        p_global = self.list.viewport().mapToGlobal(pt_view)
        p_overlay = overlay.mapFromGlobal(p_global)
        x = min(max(0, p_overlay.x()), overlay.width() - 1)
        y = min(max(0, p_overlay.y()), overlay.height() - 1)
        return QPoint(x, y)

    def current_hover_item(self) -> Optional[QListWidgetItem]:
        pos = self.list.viewport().mapFromGlobal(self.cursor().pos())
        return self.list.itemAt(pos)
