# /ui/dialogs/station_services_dialog.py

"""
Station Services Dialog

Provides access to various station services including ship renaming,
repairs, upgrades, and other commercial services available at stations.
"""

from __future__ import annotations

import random
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QPushButton, QLabel, QFrame, QMessageBox, QSizePolicy
)

from game_controller.log_config import get_ui_logger
from game import player_status
from data import db

logger = get_ui_logger('station_services')


class StationServicesDialog(QDialog):
    """
    Dialog for accessing various station services.
    Opens when player is docked at a station.
    """
    
    # Signal emitted when ship name is changed
    ship_renamed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Dialog setup
        self.setWindowTitle("Station Services")
        self.setModal(True)
        self.setMinimumSize(600, 400)
        self.setMaximumSize(800, 600)
        
        # State
        self._player_status = None
        self._station_name = "Unknown Station"
        
        # Get current status
        self._update_player_status()
        
        # Setup UI
        self._setup_ui()
        
        # Apply styling
        self._apply_styling()
        
    def _update_player_status(self) -> None:
        """Update player status information"""
        try:
            self._player_status = player_status.get_status_snapshot()
            if self._player_status:
                self._station_name = self._player_status.get('location_name', 'Unknown Station')
        except Exception as e:
            logger.error(f"Error updating player status: {e}")
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI"""
        try:
            layout = QVBoxLayout(self)
            layout.setSpacing(20)
            
            # Header
            self._setup_header(layout)
            
            # Services grid
            self._setup_services_grid(layout)
            
            # Footer buttons
            self._setup_footer_buttons(layout)
        except Exception as e:
            logger.error(f"Error setting up station services UI: {e}")
    
    def _setup_header(self, layout: QVBoxLayout) -> None:
        """Setup dialog header"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QVBoxLayout(header_frame)
        
        # Station name
        station_label = QLabel(f"Welcome to {self._station_name}")
        station_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        station_font = QFont("Arial", 16, QFont.Weight.Bold)
        station_label.setFont(station_font)
        header_layout.addWidget(station_label)
        
        # Services info
        info_label = QLabel("Station Services Available")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_font = QFont("Arial", 11)
        info_label.setFont(info_font)
        header_layout.addWidget(info_label)
        
        layout.addWidget(header_frame)
    
    def _setup_services_grid(self, layout: QVBoxLayout) -> None:
        """Setup services grid"""
        services_frame = QFrame()
        services_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        grid_layout = QGridLayout(services_frame)
        grid_layout.setSpacing(15)
        
        # Ship Registration Service (renaming)
        self._setup_ship_registration_service(grid_layout, 0, 0)
        
        # Other services (placeholder for future expansion)
        self._setup_placeholder_services(grid_layout)
        
        layout.addWidget(services_frame)
    
    def _setup_ship_registration_service(self, grid: QGridLayout, row: int, col: int) -> None:
        """Setup ship registration/renaming service"""
        service_frame = QFrame()
        service_frame.setFrameStyle(QFrame.Shape.Box)
        service_frame.setMinimumHeight(120)
        service_layout = QVBoxLayout(service_frame)
        
        # Service title
        title_label = QLabel("Ship Registration Office")
        title_font = QFont("Arial", 12, QFont.Weight.Bold)
        title_label.setFont(title_font)
        service_layout.addWidget(title_label)
        
        # Service description
        desc_label = QLabel("Register a new name for your vessel.\n"
                           "Official galactic database update included.\n"
                           "Fee: 500 credits")
        desc_label.setWordWrap(True)
        service_layout.addWidget(desc_label)
        
        # Service button
        register_btn = QPushButton("Register New Ship Name")
        register_btn.clicked.connect(self._handle_ship_registration)
        register_btn.setMinimumHeight(35)
        service_layout.addWidget(register_btn)
        
        grid.addWidget(service_frame, row, col)
    
    def _setup_placeholder_services(self, grid: QGridLayout) -> None:
        """Setup placeholder services for future expansion"""
        # Repair Service (placeholder)
        repair_frame = QFrame()
        repair_frame.setFrameStyle(QFrame.Shape.Box)
        repair_frame.setMinimumHeight(120)
        repair_layout = QVBoxLayout(repair_frame)
        
        repair_title = QLabel("Ship Repair Bay")
        repair_font = QFont("Arial", 12, QFont.Weight.Bold)
        repair_title.setFont(repair_font)
        repair_layout.addWidget(repair_title)
        
        repair_desc = QLabel("Hull repairs and system maintenance.\n"
                           "Service currently unavailable.\n"
                           "Check back later.")
        repair_desc.setWordWrap(True)
        repair_layout.addWidget(repair_desc)
        
        repair_btn = QPushButton("Request Repair Service")
        repair_btn.setEnabled(False)
        repair_btn.setMinimumHeight(35)
        repair_layout.addWidget(repair_btn)
        
        grid.addWidget(repair_frame, 0, 1)
        
        # Upgrade Service (placeholder)
        upgrade_frame = QFrame()
        upgrade_frame.setFrameStyle(QFrame.Shape.Box)
        upgrade_frame.setMinimumHeight(120)
        upgrade_layout = QVBoxLayout(upgrade_frame)
        
        upgrade_title = QLabel("Ship Upgrades")
        upgrade_title.setFont(repair_font)
        upgrade_layout.addWidget(upgrade_title)
        
        upgrade_desc = QLabel("Equipment upgrades and modifications.\n"
                             "Service currently unavailable.\n"
                             "Check back later.")
        upgrade_desc.setWordWrap(True)
        upgrade_layout.addWidget(upgrade_desc)
        
        upgrade_btn = QPushButton("Browse Upgrades")
        upgrade_btn.setEnabled(False)
        upgrade_btn.setMinimumHeight(35)
        upgrade_layout.addWidget(upgrade_btn)
        
        grid.addWidget(upgrade_frame, 1, 0)
        
        # Trade Office (placeholder)
        trade_frame = QFrame()
        trade_frame.setFrameStyle(QFrame.Shape.Box)
        trade_frame.setMinimumHeight(120)
        trade_layout = QVBoxLayout(trade_frame)
        
        trade_title = QLabel("Trade Office")
        trade_title.setFont(repair_font)
        trade_layout.addWidget(trade_title)
        
        trade_desc = QLabel("Cargo trading and market information.\n"
                          "Service currently unavailable.\n"
                          "Check back later.")
        trade_desc.setWordWrap(True)
        trade_layout.addWidget(trade_desc)
        
        trade_btn = QPushButton("Access Trade Terminal")
        trade_btn.setEnabled(False)
        trade_btn.setMinimumHeight(35)
        trade_layout.addWidget(trade_btn)
        
        grid.addWidget(trade_frame, 1, 1)
    
    def _setup_footer_buttons(self, layout: QVBoxLayout) -> None:
        """Setup footer buttons"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Leave Station Services")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(200)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _handle_ship_registration(self) -> None:
        """Handle ship registration/renaming request"""
        # Check if player has enough credits
        try:
            # Get current credits (placeholder - would need actual credit system)
            credits = 1000  # Placeholder value
            
            if credits < 500:
                QMessageBox.warning(
                    self,
                    "Insufficient Credits",
                    "You need at least 500 credits to register a new ship name.\n"
                    f"Current credits: {credits}"
                )
                return
            
            # Open ship naming dialog
            from ui.dialogs.ship_naming_dialog import show_ship_naming_dialog
            
            result = show_ship_naming_dialog(self)
            
            if result:
                # Deduct credits (placeholder)
                # This would integrate with the actual credit system when implemented
                
                # Show confirmation
                QMessageBox.information(
                    self,
                    "Registration Complete",
                    f"Ship registration updated successfully!\n\n"
                    f"Service fee: 500 credits\n"
                    f"Your new ship name has been transmitted to the galactic registry.\n"
                    f"All stations will now recognize your vessel by its new designation."
                )
                
                # Emit signal for UI updates
                self.ship_renamed.emit()
                
                # Close services dialog after successful registration
                self.accept()
                
        except Exception as e:
            logger.error(f"Error in ship registration: {e}")
            QMessageBox.critical(
                self,
                "Registration Error",
                "An error occurred during ship registration.\n"
                "Please try again later."
            )
    
    def _apply_styling(self) -> None:
        """Apply dialog styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            
            QFrame {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 10px;
            }
            
            QLabel {
                color: #ffffff;
                padding: 5px;
            }
            
            QPushButton {
                background-color: #4a4a4a;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #777777;
            }
            
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border-color: #444444;
            }
        """)


def show_station_services_dialog(parent=None) -> bool:
    """
    Show the station services dialog.
    Returns True if any services were used, False if dialog was cancelled.
    """
    try:
        # Check if player is actually docked
        status = player_status.get_status_snapshot()
        if not status or status.get('status') != 'Docked':
            QMessageBox.warning(
                parent,
                "Service Unavailable",
                "Station services are only available when docked at a station."
            )
            return False
        
        # Show dialog
        dialog = StationServicesDialog(parent)
        result = dialog.exec()
        
        return result == QDialog.DialogCode.Accepted
        
    except Exception as e:
        logger.error(f"Error showing station services dialog: {e}")
        QMessageBox.critical(
            parent,
            "Service Error",
            "An error occurred accessing station services.\n"
            "Please try again later."
        )
        return False
