
# /ui/dialogs/save_as_dialog.py

"""Save As Dialog

Simple dialog for getting a new save name from the user.
• Text input with 30 character limit
• Form layout for clean presentation
• Dialog button box with OK/Cancel
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox
from PySide6.QtCore import Qt

class SaveAsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save As")
        self.setMinimumWidth(350)

        self.input_save_name = QLineEdit()
        self.input_save_name.setMaxLength(30)

        # Use QFormLayout for consistency and better alignment
        form_layout = QFormLayout()
        form_layout.addRow("New Save Name:", self.input_save_name)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # Main layout to hold the form and buttons
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.buttons)

    def get_save_name(self) -> Optional[str]:
        name = self.input_save_name.text().strip()
        return name if name else None
