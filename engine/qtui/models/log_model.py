"""
Optional LogModel scaffold (unused by LogPanel which uses QPlainTextEdit).
Left here for future switch to Model/View if desired.  # SCAFFOLD
"""
from __future__ import annotations
from typing import List, Tuple, Any
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Tuple[str, str, str]] = []  # (channel, kind, msg)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        ch, kind, msg = self._rows[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return f"[{ch}:{kind}] {msg}"
        return None

    def append(self, channel: str, kind: str, msg: str) -> None:
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append((channel, kind, msg))
        self.endInsertRows()
