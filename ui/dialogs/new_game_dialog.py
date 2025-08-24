# /ui/dialogs/new_game_dialog.py

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from game.starter_locations import list_starting_locations


class NewGameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Game")
        self.setModal(True)

        self.edit_save_name = QLineEdit(self)
        self.edit_commander = QLineEdit(self)
        self.combo_location = QComboBox(self)
        self.combo_location.addItems(list_starting_locations())

        form = QFormLayout()
        form.addRow("Save File Name:", self.edit_save_name)
        form.addRow("Commander Name:", self.edit_commander)
        form.addRow("Starting Location:", self.combo_location)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        # sensible defaults
        self.edit_save_name.setText("New Save")
        self.edit_commander.setText("Captain")

    def get_values(self):
        return (
            self.edit_save_name.text().strip(),
            self.edit_commander.text().strip(),
            self.combo_location.currentText(),
        )
