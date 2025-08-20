"""
NpcPanel (right dock)
- QListView bound to NpcListModel
- Exposes helper to get currently selected npc_id  # SCAFFOLD
"""
from __future__ import annotations
from typing import Iterable, Mapping, Optional, Any, Sequence

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListView, QPushButton, QAbstractItemView

from ..models.npc_model import NpcListModel

class NpcPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = NpcListModel(self)
        self.view = QListView(self)
        self.view.setModel(self.model)
        # Qt6: selection mode under QAbstractItemView.SelectionMode
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.btn_select = QPushButton("Select")
        lay = QVBoxLayout(self)
        lay.addWidget(self.view)
        lay.addWidget(self.btn_select)

    def set_npcs(self, npcs: Sequence[Mapping[str, Any]]) -> None:
        """Replace the list content.  # SCAFFOLD"""
        self.model.set_items(npcs)

    def selected_npc_id(self) -> Optional[int]:
        idxs = self.view.selectedIndexes()
        if not idxs:
            return None
        idx: QModelIndex = idxs[0]
        val = self.model.data(idx, self.model.IdRole)
        return int(val) if val is not None else None
