# /ui/dialogs/ship_naming_dialog.py

"""
Ship Naming Dialog

Allows the player to set a custom name for their current ship.
"""

from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFrame, QFormLayout
)
from PySide6.QtCore import Qt

from data import db
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('ship_naming')


class ShipNamingDialog(QDialog):
    """Dialog for setting custom ship names"""
    
    def __init__(self, current_ship_name: str, custom_ship_name: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.current_ship_name = current_ship_name
        self.custom_ship_name = custom_ship_name
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the ship naming dialog UI"""
        self.setWindowTitle("Ship Naming")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header_label = QLabel("Customize Your Ship Name")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        layout.addWidget(header_label)
        
        # Info frame
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.Box)
        info_layout = QVBoxLayout(info_frame)
        
        # Current ship info
        ship_info = QLabel(f"Current Ship Class: {self.current_ship_name}")
        ship_info.setStyleSheet("color: #666; font-size: 11px;")
        info_layout.addWidget(ship_info)
        
        if self.custom_ship_name:
            current_custom = QLabel(f"Current Custom Name: {self.custom_ship_name}")
            current_custom.setStyleSheet("color: #4CAF50; font-weight: bold;")
            info_layout.addWidget(current_custom)
        
        layout.addWidget(info_frame)
        
        # Form
        form = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter custom ship name (leave blank to use ship class name)")
        if self.custom_ship_name:
            self.name_input.setText(self.custom_ship_name)
        
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        
        form.addRow("Ship Name:", self.name_input)
        layout.addLayout(form)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Clear button
        clear_btn = QPushButton("Use Default Name")
        clear_btn.clicked.connect(self._clear_name)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: black;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB300;
            }
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: black;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB300;
            }
        """)
        button_layout.addWidget(cancel_btn)
        
        # Apply button
        apply_btn = QPushButton("Apply Name")
        apply_btn.clicked.connect(self._apply_name)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        # Focus the input
        self.name_input.setFocus()
        self.name_input.selectAll()
    
    def _clear_name(self):
        """Clear the custom name and use default ship name"""
        try:
            db.clear_custom_ship_name()
            logger.info("Cleared custom ship name")
            self.accept()
        except Exception as e:
            logger.error(f"Error clearing custom ship name: {e}")
    
    def _apply_name(self):
        """Apply the custom ship name"""
        try:
            new_name = self.name_input.text().strip()
            if new_name:
                # Set custom name
                db.set_custom_ship_name(new_name)
                logger.info(f"Set custom ship name to: {new_name}")
            else:
                # Clear custom name if input is empty
                db.clear_custom_ship_name()
                logger.info("Cleared custom ship name (empty input)")
            
            self.accept()
        except Exception as e:
            logger.error(f"Error applying custom ship name: {e}")
    
    def get_custom_name(self) -> Optional[str]:
        """Get the entered custom name"""
        return self.name_input.text().strip() or None


def show_ship_naming_dialog(parent=None) -> bool:
    """Show the ship naming dialog and return True if changes were made"""
    try:
        # Get current ship info
        from game import player_status
        snapshot = player_status.get_status_snapshot()
        
        # Get the base ship name (without custom name)
        from data import db as data_db
        ship = data_db.get_player_ship()
        base_ship_name = ship.get('name', 'Unknown Ship') if ship else 'Unknown Ship'
        
        # Get current custom name
        current_custom = data_db.get_custom_ship_name()
        
        dialog = ShipNamingDialog(base_ship_name, current_custom, parent)
        result = dialog.exec()
        
        return result == QDialog.DialogCode.Accepted
    except Exception as e:
        logger.error(f"Error showing ship naming dialog: {e}")
        return False
