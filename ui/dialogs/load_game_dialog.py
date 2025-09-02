# /ui/dialogs/load_game_dialog.py

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialogButtonBox, QMessageBox, QLineEdit, QInputDialog,
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from datetime import datetime
from typing import List, Tuple, Optional

from save.save_manager import SaveManager
from save.serializers import read_meta
from ui.dialogs.new_game_dialog import NewGameDialog


class SortableTreeWidgetItem(QTreeWidgetItem):
    """Custom tree widget item that handles proper sorting for timestamp columns"""
    
    def __lt__(self, other):
        if not isinstance(other, QTreeWidgetItem):
            return False
        
        tree_widget = self.treeWidget()
        if not tree_widget:
            # Fallback to text comparison if tree widget not available
            self_text = self.text(0) or ""
            other_text = other.text(0) or ""
            return self_text < other_text
            
        column = tree_widget.sortColumn()
        
        # For the timestamp column (column 2), sort by the stored ISO string
        if column == 2:
            self_iso = self.data(2, Qt.ItemDataRole.UserRole + 1) or ""
            other_iso = other.data(2, Qt.ItemDataRole.UserRole + 1) or ""
            if self_iso != other_iso:
                return self_iso < other_iso
            else:
                # If timestamps are the same, fall back to name comparison
                self_name = self.text(0) or ""
                other_name = other.text(0) or ""
                return self_name < other_name
        
        # For other columns, use text comparison directly to avoid recursion
        self_text = self.text(column) or ""
        other_text = other.text(column) or ""
        if self_text != other_text:
            return self_text < other_text
        else:
            # If column text is the same, use name as tiebreaker
            self_name = self.text(0) or ""
            other_name = other.text(0) or ""
            return self_name < other_name


class LoadGameDialog(QDialog):
    """
    Load Game dialog with integrated 'New Game…' flow.

    - Lists existing saves with timestamps; allows rename/delete/open.
    - Provides sorting by name (A-Z, Z-A) or by last played date
    - 'New Game…' opens NewGameDialog, creates a save via SaveManager,
      selects it, and auto-accepts so the caller can load it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setMinimumSize(600, 400)

        self.selected_save: Optional[Path] = None

        layout = QVBoxLayout(self)

        # Create tree widget with sortable columns
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Save Name", "Commander", "Last Played"])
        self.tree_widget.setRootIsDecorated(False)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSortingEnabled(True)
        self.tree_widget.itemDoubleClicked.connect(self.accept)
        self.tree_widget.currentItemChanged.connect(self._on_selection_changed)
        
        # Set column widths
        header = self.tree_widget.header()
        header.resizeSection(0, 200)  # Save Name
        header.resizeSection(1, 150)  # Commander  
        header.resizeSection(2, 200)  # Last Played
        header.setStretchLastSection(True)
        
        layout.addWidget(self.tree_widget)

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
        """Populate the tree widget with save game data"""
        try:
            self.tree_widget.clear()
            
            # Disable sorting temporarily to avoid issues during population
            self.tree_widget.setSortingEnabled(False)
            
            # Collect and display save data
            saves_list = SaveManager.list_saves()
            
            for name, path in saves_list:
                try:
                    meta = read_meta(path / "meta.json")
                    commander_name = meta.commander_name if meta else "Unknown"
                    last_played_iso = meta.last_played_iso if meta else ""
                    
                    # Format last played time for display
                    last_played_display = self._format_timestamp(last_played_iso)
                    
                    item = SortableTreeWidgetItem([name, commander_name, last_played_display])
                    item.setData(0, Qt.ItemDataRole.UserRole, path)
                    
                    # Store the ISO timestamp for proper sorting (invisible to user)
                    item.setData(2, Qt.ItemDataRole.UserRole + 1, last_played_iso)
                    
                    self.tree_widget.addTopLevelItem(item)
                    
                except Exception as e:
                    # If there's an error with this save, log it but continue with others
                    from ui.error_handler import log_warning
                    log_warning(f"Error loading save metadata for {name}: {e}", "Load Game Dialog")
                    
                    # Add a basic entry without metadata
                    item = SortableTreeWidgetItem([name, "Unknown", "Unknown"])
                    item.setData(0, Qt.ItemDataRole.UserRole, path)
                    item.setData(2, Qt.ItemDataRole.UserRole + 1, "")
                    self.tree_widget.addTopLevelItem(item)
            
            # Re-enable sorting after population is complete
            self.tree_widget.setSortingEnabled(True)
            
            # Sort by "Last Played" column (newest first) by default
            try:
                self.tree_widget.sortItems(2, Qt.SortOrder.DescendingOrder)
            except Exception as e:
                # If sorting fails, log but don't crash
                from ui.error_handler import log_warning
                log_warning(f"Error sorting save list: {e}", "Load Game Dialog")
                
        except Exception as e:
            # If the entire population fails, handle gracefully
            from ui.error_handler import handle_error
            handle_error(e, "Populating save game list")

    def _format_timestamp(self, iso_string: str) -> str:
        """Format ISO timestamp for user-friendly display"""
        if not iso_string:
            return "Never"
        
        try:
            # Handle various timestamp formats
            if iso_string.endswith('Z'):
                dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(iso_string)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError, TypeError) as e:
            # Log the error but return a safe fallback
            from ui.error_handler import log_warning
            log_warning(f"Error parsing timestamp '{iso_string}': {e}", "Load Game Dialog")
            return "Invalid date"

    def _on_selection_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current:
            self.selected_save = current.data(0, Qt.ItemDataRole.UserRole)
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

        # Find and select the newly created save
        found_item: Optional[QTreeWidgetItem] = None
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item and item.text(0) == new_path.name:
                found_item = item
                break

        # Fallback: match by path
        if not found_item:
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                if item and item.data(0, Qt.ItemDataRole.UserRole) == new_path:
                    found_item = item
                    break

        if found_item:
            self.tree_widget.setCurrentItem(found_item)
            self.selected_save = found_item.data(0, Qt.ItemDataRole.UserRole)
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
