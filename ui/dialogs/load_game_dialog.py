# /ui/dialogs/load_game_dialog.py

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialogButtonBox, QMessageBox, QLineEdit, QInputDialog
)
from PySide6.QtCore import Qt

from save.save_manager import SaveManager
from ui.dialogs.new_game_dialog import NewGameDialog


class LoadGameDialog(QDialog):
    """
    Load Game dialog with integrated 'New Game…' flow.

    - Lists existing saves; allows rename/delete/open.
    - 'New Game…' opens NewGameDialog, creates a save via SaveManager,
      selects it, and auto-accepts so the caller can load it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setMinimumSize(450, 300)

        self.selected_save: Optional[Path] = None

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.accept)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()

        # New Game button
        self.new_btn = QPushButton("New Game…")
        button_layout.addWidget(self.new_btn)

        self.rename_btn = QPushButton("Rename")
        self.delete_btn = QPushButton("Delete")
        button_layout.addWidget(self.rename_btn)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(self.dialog_buttons)

        # Wire actions
        self.new_btn.clicked.connect(self._on_new_game)
        self.rename_btn.clicked.connect(self._on_rename)
        self.delete_btn.clicked.connect(self._on_delete)

        self._populate_list()
        self._update_button_states()

    # ----- core list management -----

    def _populate_list(self):
        self.list_widget.clear()
        for name, path in SaveManager.list_saves():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            self.selected_save = current.data(Qt.ItemDataRole.UserRole)
        else:
            self.selected_save = None
        self._update_button_states()

    def _update_button_states(self):
        has_selection = self.selected_save is not None
        self.rename_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.dialog_buttons.button(QDialogButtonBox.StandardButton.Open).setEnabled(has_selection)

    # ----- new game flow (in this dialog) -----

    def _on_new_game(self):
        """
        Open the New Game dialog, create the save via SaveManager, then select and open it.
        """
        dlg = NewGameDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        save_name, commander, label = dlg.get_values()
        start_ids = dlg.get_selected_start_ids()  # {'race_id','system_id','location_id'} or None

        try:
            # SaveManager handles DB creation, seeding, and initial spawn.
            new_path = SaveManager.create_new_save(
                save_name=save_name,
                commander_name=commander,
                starting_location_label=label,   # legacy text, kept for logs/UI
                start_ids=start_ids,             # explicit IDs drive the actual placement
            )
        except Exception as e:
            QMessageBox.critical(self, "New Game Failed", str(e))
            return

        # Refresh list and select the newly created save
        self._populate_list()

        # Prefer an exact name match
        found_item: Optional[QListWidgetItem] = None
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() == new_path.name:
                found_item = item
                break

        # Fallback: match by path
        if not found_item:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_path:
                    found_item = item
                    break

        if found_item:
            self.list_widget.setCurrentItem(found_item)
            self.selected_save = found_item.data(Qt.ItemDataRole.UserRole)
            # Immediately accept so the caller loads this new save
            self.accept()
        else:
            QMessageBox.information(
                self, "New Game",
                "New save was created, but it wasn't found in the list. "
                "Select it manually and click Open."
            )

    # ----- rename/delete -----

    def _on_rename(self):
        if not self.selected_save:
            return

        current_name = self.selected_save.name
        new_name, ok = QInputDialog.getText(
            self, "Rename Save", "Enter new name:",
            QLineEdit.EchoMode.Normal, current_name
        )

        if ok and new_name and new_name != current_name:
            try:
                SaveManager.rename_save(self.selected_save, new_name)
                self._populate_list()
            except Exception as e:
                QMessageBox.critical(self, "Rename Failed", str(e))

    def _on_delete(self):
        if not self.selected_save:
            return

        reply = QMessageBox.question(
            self,
            "Delete Save",
            f"Are you sure you want to permanently delete '{self.selected_save.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                SaveManager.delete_save(self.selected_save)
                self._populate_list()
            except Exception as e:
                QMessageBox.critical(self, "Delete Failed", str(e))

    # ----- result accessor -----

    def get_selected_save_path(self) -> Optional[Path]:
        return self.selected_save
