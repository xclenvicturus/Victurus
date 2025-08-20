"""
LogPanel (bottom dock)
- Simple log area with context menu (copy/clear)  # SCAFFOLD
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit

class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        # Qt6: context menu policy moved under Qt.ContextMenuPolicy.*
        self.text.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        act_copy_all = QAction("Copy All", self)
        act_copy_all.triggered.connect(self._copy_all)
        act_clear = QAction("Clear", self)
        act_clear.triggered.connect(self.text.clear)

        self.text.addAction(act_copy_all)
        self.text.addAction(act_clear)

        lay = QVBoxLayout(self)
        lay.addWidget(self.text)

    def append_log(self, channel: str, kind: str, msg: str) -> None:
        self.text.appendPlainText(f"[{channel}:{kind}] {msg}")

    def _copy_all(self) -> None:
        self.text.selectAll()
        self.text.copy()
        # Qt6: move operation is scoped under QTextCursor.MoveOperation
        cur = self.text.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self.text.setTextCursor(cur)
