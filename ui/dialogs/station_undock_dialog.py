# /ui/dialogs/station_undock_dialog.py

"""
Station Undocking Dialog

Handles undocking communication sequences when leaving stations,
showing authentic station controller departure messages and undocking progress.
"""

from __future__ import annotations

import time
import random
from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, 
    QPushButton, QLabel, QFrame, QProgressBar, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QColor

from game_controller.log_config import get_ui_logger
from game import player_status

logger = get_ui_logger('station_undock')


class StationUndockDialog(QDialog):
    """
    Dialog for station undocking sequences when leaving stations.
    Shows realistic station departure controller messages and undocking progress.
    """
    
    # Signals
    undocking_approved = Signal()
    undocking_denied = Signal(str)  # reason
    undocking_complete = Signal()
    
    def __init__(self, station_name: str, station_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.station_name = station_name
        self.station_data = station_data
        self.undocking_phase = "requesting"  # requesting, approved, undocking, complete
        
        self._setup_ui()
        self._start_undocking_sequence()
    
    def _setup_ui(self):
        """Setup the undocking dialog UI"""
        self.setWindowTitle(f"Departure Control - {self.station_name}")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header with station info
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout(header_frame)
        
        station_label = QLabel(f"🚀 {self.station_name} Departure Control")
        station_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FF9800;")
        header_layout.addWidget(station_label)
        
        header_layout.addStretch()
        
        status_label = QLabel("REQUESTING DEPARTURE...")
        status_label.setStyleSheet("color: #FFC107; font-size: 10px;")
        self.status_label = status_label
        header_layout.addWidget(status_label)
        
        layout.addWidget(header_frame)
        
        # Communication log
        self.comm_log = QTextEdit()
        self.comm_log.setReadOnly(True)
        self.comm_log.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FF9800;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #333;
            }
        """)
        layout.addWidget(self.comm_log)
        
        # Progress bar for undocking
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #333;
                border-radius: 5px;
                text-align: center;
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #FF9800;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel Departure")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
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
        button_layout.addWidget(self.cancel_button)
        
        self.proceed_button = QPushButton("Confirm Departure")
        self.proceed_button.setVisible(False)
        self.proceed_button.clicked.connect(self._proceed_undocking)
        self.proceed_button.setStyleSheet("""
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
        button_layout.addWidget(self.proceed_button)
        
        layout.addLayout(button_layout)
        
        # Timers for sequences
        self.comm_timer = QTimer()
        self.comm_timer.timeout.connect(self._advance_communication)
        
        self.undock_timer = QTimer()
        self.undock_timer.timeout.connect(self._advance_undocking)
    
    def _start_undocking_sequence(self):
        """Start the undocking communication sequence with the station"""
        try:
            self.comm_sequence_step = 0
            self.comm_messages = self._generate_undocking_sequence()
            
            # Start with initial delay
            QTimer.singleShot(300, self._advance_communication)
        except Exception as e:
            logger.error(f"Error starting undocking sequence: {e}")
    
    def _generate_undocking_sequence(self) -> List[Dict[str, Any]]:
        """Generate the undocking communication message sequence"""
        # Get station controller name and callsign
        controller_names = [
            "Departure Control Reyes", "Flight Controller Adams", "Harbor Master Kim",
            "Station Departure Delta", "Traffic Control Gamma", "Launch Control Echo"
        ]
        controller = random.choice(controller_names)
        
        # Station callsign based on name
        station_words = self.station_name.split()
        if len(station_words) >= 2:
            callsign = f"{station_words[0][:3].upper()}-{station_words[-1][:3].upper()}"
        else:
            callsign = f"{self.station_name[:6].upper()}"
        
        # Get player info from game state
        from game import player_status
        snapshot = player_status.get_status_snapshot()
        player_name = snapshot.get('player_name', 'Commander')
        ship_name = snapshot.get('ship_name', 'Unknown Vessel')
        
        messages = [
            {
                'sender': 'system',
                'text': f">>> Connecting to {self.station_name} Departure Control...",
                'delay': 600,
                'color': '#FFC107'
            },
            {
                'sender': 'system', 
                'text': f">>> Secure departure channel established.",
                'delay': 500,
                'color': '#FF9800'
            },
            {
                'sender': 'station',
                'text': f"{callsign} Departure Control, this is {controller}. We show you docked at Bay {self._get_docked_bay()}. State your departure intentions, {ship_name}.",
                'delay': 1400,
                'color': '#FF9800'
            },
            {
                'sender': 'player_auto',
                'text': f"{callsign} Departure, this is {ship_name} with Commander {player_name} requesting undocking clearance. We are departing station to resume normal operations.",
                'delay': 1100,
                'color': '#87CEEB'
            },
            {
                'sender': 'station',
                'text': f"Copy {ship_name}. Stand by for departure systems check and bay clearance...",
                'delay': 1300,
                'color': '#FF9800'
            },
            {
                'sender': 'station',
                'text': self._get_departure_clearance_message(callsign, ship_name),
                'delay': 900,
                'color': '#4CAF50'
            }
        ]
        
        return messages
    
    def _get_departure_clearance_message(self, callsign: str, ship_name: str) -> str:
        """Generate departure clearance message"""
        # Random departure vector
        vectors = ["Alpha-3", "Beta-7", "Gamma-2", "Delta-5", "Echo-9"]
        departure_vector = random.choice(vectors)
        
        # Random traffic information
        traffic_info = [
            "No traffic conflicts detected.",
            "Light traffic on departure vector - maintain standard separation.",
            "One vessel inbound on approach vector Charlie - cleared for immediate departure.",
            "Station traffic is nominal - cleared for standard departure."
        ]
        
        base_msg = f"{ship_name}, you are cleared for undocking proceedures. "
        base_msg += f"Use departure vector {departure_vector}. "
        base_msg += random.choice(traffic_info)
        
        # Get station name from player status for personalized farewell
        try:
            status = player_status.get_status_snapshot()
            station_name = status.get('location_name', 'our station') if status else 'our station'
            base_msg += f" Safe travels and thank you for visiting {station_name}."
        except Exception:
            base_msg += " Safe travels and thank you for visiting our station."
        
        return base_msg
    
    def _get_docked_bay(self) -> str:
        """Get the bay number where the player is docked"""
        try:
            from data import db
            bay_number = db.get_docked_bay()
            logger.debug(f"Undocking dialog: retrieved bay number {bay_number} from database")
            
            result = str(bay_number) if bay_number is not None else "Unknown"
            logger.debug(f"Undocking dialog: returning bay text '{result}'")
            
            return result
        except Exception as e:
            logger.error(f"Error getting docked bay: {e}")
            return "Unknown"
    
    def _advance_communication(self):
        """Advance to the next step in the communication sequence"""
        try:
            if self.comm_sequence_step >= len(self.comm_messages):
                # Communication complete, ready to undock
                self.status_label.setText("DEPARTURE CLEARANCE GRANTED")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
                self.proceed_button.setVisible(True)
                self.cancel_button.setText("Cancel")
                return
            
            message = self.comm_messages[self.comm_sequence_step]
            
            # Add message to log
            self._add_comm_message(message['sender'], message['text'], message.get('color', '#FF9800'))
            
            # Update status
            if message['sender'] == 'system':
                self.status_label.setText("ESTABLISHING DEPARTURE LINK...")
            elif message['sender'] == 'station':
                self.status_label.setText("RECEIVING DEPARTURE CONTROL")
            elif message['sender'] == 'player_auto':
                self.status_label.setText("TRANSMITTING DEPARTURE REQUEST")
            
            self.comm_sequence_step += 1
            
            # Schedule next message
            next_delay = message.get('delay', 1000)
            self.comm_timer.singleShot(next_delay, self._advance_communication)
        except Exception as e:
            logger.error(f"Error advancing undocking communication: {e}")
    
    def _add_comm_message(self, sender: str, text: str, color: str = '#FF9800'):
        """Add a message to the communication log"""
        timestamp = time.strftime("%H:%M:%S")
        
        cursor = self.comm_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Format sender prefix
        if sender == 'system':
            prefix = f"[{timestamp}] SYS: "
        elif sender == 'station':
            prefix = f"[{timestamp}] DEP: "  # Departure Control
        elif sender == 'player_auto':
            prefix = f"[{timestamp}] PLR: "
        else:
            prefix = f"[{timestamp}] {sender.upper()}: "
        
        # Insert with formatting - each message on a new line
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        
        # Add newline before message if not first message
        if self.comm_log.toPlainText():
            cursor.insertText("\n")
        
        cursor.insertText(prefix, format)
        cursor.insertText(text)
        
        # Auto-scroll to bottom
        scrollbar = self.comm_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _proceed_undocking(self):
        """Begin the undocking procedure"""
        try:
            self.undocking_phase = "undocking"
            
            # Hide communication elements, show undocking progress
            self.proceed_button.setVisible(False)
            self.cancel_button.setText("Emergency Abort")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self._emergency_abort)
            # Make emergency abort button red
            self.cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
                QPushButton:pressed {
                    background-color: #8d1818;
                }
            """)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Initiating Undocking Sequence...")
            
            self.status_label.setText("UNDOCKING IN PROGRESS")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 10px; font-weight: bold;")
            
            # Add undocking progress messages
            self._add_comm_message('system', ">>> Initiating automated undocking sequence.", '#FFC107')
            self._add_comm_message('system', ">>> Disconnecting station umbilicals.", '#FFC107')
            
            # Start undocking timer
            self.undock_progress = 0
            self.undock_timer.start(100)  # Update every 100ms
        except Exception as e:
            logger.error(f"Error proceeding with undocking: {e}")
    
    def _advance_undocking(self):
        """Advance the undocking progress"""
        try:
            # Similar timing to docking - slow progress for realism
            self.undock_progress += random.uniform(0.6, 1.8)
            
            if self.undock_progress <= 100:
                self.progress_bar.setValue(int(self.undock_progress))
                
                # Update progress messages
                if self.undock_progress < 25:
                    self.progress_bar.setFormat("Retracting docking clamps...")
                elif self.undock_progress < 50:
                    self.progress_bar.setFormat("Sealing airlock systems...")
                elif self.undock_progress < 75:
                    self.progress_bar.setFormat("Backing away from station...")
                else:
                    self.progress_bar.setFormat("Establishing safe distance...")
                
                # Random progress messages
                if random.random() < 0.06:  # 6% chance per tick for more chatter
                    messages = [
                        ">>> Station moorings successfully released.",
                        ">>> All umbilical connections severed.",
                        ">>> Thrusters firing - backing clear of station.",
                        ">>> Navigation systems switching to free flight mode.",
                        ">>> Station magnetic field disengaged.",
                        ">>> Hull integrity verified - all systems nominal.",
                        ">>> Departure vector locked and confirmed.",
                        ">>> Fuel systems isolated from station supply.",
                        ">>> Power systems switching to internal generation.",
                        ">>> Data link transferring to long-range comm array.",
                        ">>> Environmental systems sealing from station.",
                        ">>> Gravity field transition in progress.",
                        ">>> Station tractor beam safely disengaged.",
                        ">>> Micro-thrusters maintaining safe separation.",
                        ">>> Cargo bay access ports sealed and secured.",
                        ">>> Communication switching to independent systems.",
                        ">>> Life support systems fully autonomous.",
                        ">>> Engine pre-flight checks completing.",
                        ">>> Navigation computers calculating departure route.",
                        ">>> Station proximity sensors confirming safe distance."
                    ]
                    self._add_comm_message('system', random.choice(messages), '#FFC107')
            else:
                # Undocking complete
                self.undock_timer.stop()
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("UNDOCKING COMPLETE")
                
                self.status_label.setText("DEPARTED SUCCESSFULLY")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
                
                self._add_comm_message('system', ">>> Undocking complete. Free and clear of station.", '#4CAF50')
                self._add_comm_message('system', ">>> You are now in orbit. Normal flight operations resumed.", '#4CAF50')
                
                # Final button
                self.cancel_button.setText("Close")
                self.cancel_button.clicked.disconnect()
                self.cancel_button.clicked.connect(self._complete_undocking)
                
                # Auto-close after a moment
                QTimer.singleShot(2000, self._complete_undocking)
        except Exception as e:
            logger.error(f"Error advancing undocking progress: {e}")
    
    def _complete_undocking(self):
        """Complete the undocking sequence and close dialog"""
        try:
            # Clear docked bay since we're undocking
            from data import db
            db.clear_docked_bay()
            
            self.undocking_approved.emit()
            self.undocking_complete.emit()
            self.accept()
        except Exception as e:
            logger.error(f"Error completing undocking: {e}")
    
    def _emergency_abort(self):
        """Handle emergency abort during undocking - IMMEDIATE ACTION"""
        try:
            # Emergency stop means STOP NOW - no confirmation dialog
            self._perform_emergency_abort()
        except Exception as e:
            logger.error(f"Error in emergency abort: {e}")
    
    def _perform_emergency_abort(self):
        """Perform the actual emergency abort"""
        try:
            # Stop all timers IMMEDIATELY
            self.undock_timer.stop()
            self.comm_timer.stop()
            
            # Update status to aborted
            self.undocking_phase = "aborted"
            self.status_label.setText("UNDOCKING ABORTED")
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 10px; font-weight: bold;")
            
            # Update progress bar to show abort
            self.progress_bar.setFormat("⚠️ EMERGENCY ABORT ACTIVATED")
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #d32f2f;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #d32f2f;
                    border-radius: 3px;
                }
            """)
            
            # Add abort messages
            self._add_comm_message('system', ">>> EMERGENCY ABORT ACTIVATED!", '#d32f2f')
            self._add_comm_message('system', ">>> Re-engaging docking clamps immediately!", '#d32f2f')
            self._add_comm_message('system', ">>> Warning: Emergency re-docking may cause damage.", '#FF5722')
            self._add_comm_message('system', ">>> Ship secured back to station - undocking cancelled.", '#FF5722')
            
            # Show aftermath dialog AFTER the emergency stop
            QMessageBox.critical(
                self,
                "Undocking Emergency Abort",
                "🚨 EMERGENCY ABORT COMPLETE\n\n"
                "The undocking sequence has been forcibly terminated.\n"
                "Your ship has been emergency re-docked to the station.\n\n"
                "⚠️ WARNING: This emergency procedure may have caused:\n"
                "• Hull stress and potential damage\n"
                "• Docking clamp damage from forced re-engagement\n"
                "• System malfunctions from power surges\n\n"
                "Run a full system diagnostic before attempting to undock again."
            )
            
            # Change button to reset
            self.cancel_button.setText("Try Undocking Again")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self._reset_undocking)
            # Reset button styling to blue
            self.cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #1976d2;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            
        except Exception as e:
            logger.error(f"Error performing emergency abort: {e}")
    
    def _reset_undocking(self):
        """Reset the dialog to allow trying undocking again"""
        try:
            # Reset all states
            self.undocking_phase = "requesting"
            self.undock_progress = 0
            
            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            # Reset progress bar styling
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #333;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #1E1E1E;
                    color: #FF9800;
                }
                QProgressBar::chunk {
                    background-color: #FF9800;
                    border-radius: 3px;
                }
            """)
            
            # Reset status
            self.status_label.setText("DEPARTURE CLEARANCE GRANTED")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
            
            # Clear and add reset message
            self.comm_log.clear()
            self._add_comm_message('system', ">>> Departure communication channel reset.", '#4CAF50')
            self._add_comm_message('system', ">>> Ready for new undocking attempt.", '#4CAF50')
            
            # Show proceed button again
            self.proceed_button.setVisible(True)
            
            # Reset cancel button
            self.cancel_button.setText("Cancel")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self.reject)
            self.cancel_button.setStyleSheet("""
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
            
        except Exception as e:
            logger.error(f"Error resetting undocking: {e}")
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.undocking_phase == "undocking":
            # Don't allow closing during undocking - show emergency abort option
            reply = QMessageBox.question(
                self,
                "Close During Undocking",
                "Undocking is currently in progress. You must either:\n\n"
                "• Wait for undocking to complete, OR\n"
                "• Emergency abort the undocking (immediate stop)\n\n"
                "Do you want to emergency abort and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Immediate emergency abort without additional confirmation
                self._perform_emergency_abort()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
