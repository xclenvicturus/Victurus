"""
NpcListModel (QAbstractListModel)
- Minimal roles: Id, Name, Role, Faction
- set_items(Sequence[Mapping[str, Any]]) to refresh  # SCAFFOLD
"""
from __future__ import annotations
from typing import List, Dict, Any, Mapping, Sequence

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QByteArray

class NpcListModel(QAbstractListModel):
    # Qt6: roles live under Qt.ItemDataRole; keep our own ints for roleNames()
    _USER_BASE = int(Qt.ItemDataRole.UserRole)
    IdRole = _USER_BASE + 1
    NameRole = _USER_BASE + 2
    RoleRole = _USER_BASE + 3
    FactionRole = _USER_BASE + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[Dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        item = self._items[index.row()]
        if role in (int(Qt.ItemDataRole.DisplayRole), self.NameRole):
            return item.get("name", "")
        if role == self.IdRole:
            return item.get("id")
        if role == self.RoleRole:
            return item.get("role", "")
        if role == self.FactionRole:
            return item.get("faction", "")
        return None

    def roleNames(self):  # type: ignore[override]
        return {
            int(Qt.ItemDataRole.DisplayRole): QByteArray(b"display"),
            int(self.IdRole): QByteArray(b"id"),
            int(self.NameRole): QByteArray(b"name"),
            int(self.RoleRole): QByteArray(b"role"),
            int(self.FactionRole): QByteArray(b"faction"),
        }

    # Public API --------------------------------------------------------------
    def set_items(self, items: Sequence[Mapping[str, Any]]) -> None:
        self.beginResetModel()
        # normalize to real dicts for internal storage
        self._items = [dict(x) for x in items]
        self.endResetModel()
