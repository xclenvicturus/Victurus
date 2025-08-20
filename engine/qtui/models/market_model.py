"""
MarketTableModel (QAbstractTableModel) scaffold.
Columns: Item, Qty, Desired, Buy, Sell, Delta, Station  # SCAFFOLD
"""
from __future__ import annotations
from typing import List, Dict, Any
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class MarketTableModel(QAbstractTableModel):
    HEADERS = ["Item", "Qty", "Desired", "Buy", "Sell", "Δ", "Station"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self.HEADERS[index.column()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            mapping = {
                "Item": "item_name",
                "Qty": "qty",
                "Desired": "desired",
                "Buy": "buy_price",
                "Sell": "sell_price",
                "Δ": "delta",
                "Station": "station_name",
            }
            return row.get(mapping[key], "")
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # type: ignore[override]
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return section + 1

    # Public API --------------------------------------------------------------
    def set_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
