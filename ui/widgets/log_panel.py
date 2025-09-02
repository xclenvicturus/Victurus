# /ui/widgets/log_panel.py
"""
Log Panel Widget

A small log panel with search and copy controls for displaying categorized game logs.
"""

from __future__ import annotations

from typing import List, Tuple, Optional
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QPlainTextEdit

from ui.error_utils import warn_on_exception


class LogPanel(QWidget):
    """A small log panel with search and copy controls.

    Keeps an internal list of entries (timestamp, category, text) and
    updates the visible text when the search filter changes.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: List[Tuple[str, str, str]] = []  # (iso-ts, category, text)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._on_search_changed)

        self._copy_btn = QPushButton("Copy All", self)
        self._copy_btn.clicked.connect(self.copy_all)

        self._clear_btn = QPushButton("Clear", self)
        self._clear_btn.clicked.connect(self.clear)

        ctrl = QHBoxLayout()
        ctrl.addWidget(self._search)
        ctrl.addWidget(self._copy_btn)
        ctrl.addWidget(self._clear_btn)

        self._view = QPlainTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(ctrl)
        layout.addWidget(self._view)

    def append_entry(self, ts_iso: str, category: str, text: str) -> None:
        try:
            entry = (ts_iso, category, text)
            self._entries.append(entry)
            # Only add visible if matches current filter
            q = self._search.text().strip().lower()
            joined = f"[{ts_iso}][{category}] {text}"
            if not q or q in joined.lower():
                self._view.appendPlainText(joined)
                # scroll to bottom
                self._view.verticalScrollBar().setValue(self._view.verticalScrollBar().maximum())
        except Exception:
            pass

    def load_entries(self, entries: List[Tuple[str, str, str]]) -> None:
        self._entries = []
        self._view.clear()
        for ts_iso, cat, txt in entries:
            self.append_entry(ts_iso, cat, txt)

    def _on_search_changed(self, _text: str) -> None:
        try:
            q = self._search.text().strip().lower()
            self._view.clear()
            if not q:
                for ts_iso, cat, txt in self._entries:
                    self._view.appendPlainText(f"[{ts_iso}][{cat}] {txt}")
                return
            for ts_iso, cat, txt in self._entries:
                joined = f"[{ts_iso}][{cat}] {txt}"
                if q in joined.lower():
                    self._view.appendPlainText(joined)
        except Exception:
            pass

    @warn_on_exception("Log panel copy all")
    def copy_all(self) -> None:
        try:
            from PySide6.QtWidgets import QApplication

            cb = QApplication.clipboard()
            cb.setText(self._view.toPlainText())
        except Exception:
            pass

    @warn_on_exception("Log panel clear")
    def clear(self) -> None:
        try:
            self._entries = []
            self._view.clear()
        except Exception:
            pass
