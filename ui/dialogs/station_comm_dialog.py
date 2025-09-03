# /ui/dialogs/station_comm_dialog.py

"""
Station Communication Dialog

Handles communication sequences with stations during docking requests,
showing authentic space station controller messages and responses.
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

logger = get_ui_logger('station_comm')


class StationCommDialog(QDialog):
    """
    Dialog for station communication sequences during docking procedures.
    Shows realistic station controller messages and docking progress.
    """
    
    # Signals
    docking_approved = Signal()  # No parameters - keep it simple
    docking_denied = Signal(str)  # reason
    communication_complete = Signal()
    
    def __init__(self, station_name: str, station_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.station_name = station_name
        self.station_data = station_data
        self.docking_phase = "requesting"  # requesting, approved, docking, complete
        
        self._setup_ui()
        self._start_communication_sequence()
    
    def _setup_ui(self):
        """Setup the communication dialog UI"""
        self.setWindowTitle(f"Station Communication - {self.station_name}")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header with station info
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout(header_frame)
        
        station_label = QLabel(f"📡 {self.station_name}")
        station_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        header_layout.addWidget(station_label)
        
        header_layout.addStretch()
        
        status_label = QLabel("ESTABLISHING COMMUNICATION...")
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
                color: #00FF00;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #333;
            }
        """)
        layout.addWidget(self.comm_log)
        
        # Progress bar for docking
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
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Response input (for player responses)
        response_layout = QHBoxLayout()
        
        self.response_input = QLineEdit()
        self.response_input.setPlaceholderText("Type response...")
        self.response_input.setVisible(False)
        self.response_input.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D;
                border: 1px solid #555;
                padding: 5px;
                color: #00FF00;
                font-family: 'Courier New', monospace;
            }
        """)
        response_layout.addWidget(self.response_input)
        
        self.send_button = QPushButton("Send")
        self.send_button.setVisible(False)
        response_layout.addWidget(self.send_button)
        
        layout.addLayout(response_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel Docking Request")
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
        
        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.setVisible(False)
        self.proceed_button.clicked.connect(self._proceed_docking)
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
        
        self.dock_timer = QTimer()
        self.dock_timer.timeout.connect(self._advance_docking)
    
    def _start_communication_sequence(self):
        """Start the communication sequence with the station"""
        try:
            self.comm_sequence_step = 0
            self.comm_messages = self._generate_comm_sequence()
            
            # Start with initial delay
            QTimer.singleShot(500, self._advance_communication)
        except Exception as e:
            logger.error(f"Error starting communication sequence: {e}")
    
    def _generate_comm_sequence(self) -> List[Dict[str, Any]]:
        """Generate the communication message sequence"""
        # Get station controller name and callsign
        controller_names = [
            "Control Officer Martinez", "Flight Controller Chen", "Dock Master Johnson",
            "Station Control Alpha", "Harbor Master Singh", "Traffic Control Beta"
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
                'text': f">>> Establishing secure channel with {self.station_name}...",
                'delay': 800,
                'color': '#FFC107'
            },
            {
                'sender': 'system', 
                'text': f">>> Quantum encryption handshake complete.",
                'delay': 600,
                'color': '#4CAF50'
            },
            {
                'sender': 'station',
                'text': f"{callsign} Station Control, this is {controller}. We have you on approach vector, {ship_name}. State your business.",
                'delay': 1200,
                'color': '#00FF00'
            },
            {
                'sender': 'player_auto',
                'text': f"{callsign} Control, this is Commander {player_name} aboard the {ship_name} requesting docking clearance. We are seeking station services.",
                'delay': 1000,
                'color': '#87CEEB'
            },
            {
                'sender': 'station',
                'text': f"Copy that, {ship_name}. Stand by for docking bay assignment...",
                'delay': 1500,
                'color': '#00FF00'
            },
            {
                'sender': 'station',
                'text': self._get_docking_approval_message(callsign, ship_name),
                'delay': 800,
                'color': '#4CAF50'
            }
        ]
        
        return messages
    
    def _get_docking_approval_message(self, callsign: str, ship_name: str) -> str:
        """Generate docking approval message based on station facilities"""
        facilities = self.station_data.get('facilities', [])
        facility_types = [f.get('type', '') for f in facilities]
        
        # Generate bay number but don't save it yet - save it when docking is confirmed
        self.assigned_bay = random.randint(1, 12)
        
        base_msg = f"{ship_name}, you are cleared for docking at Bay {self.assigned_bay}. "
        
        # Add facility-specific information
        services = []
        if 'Fuel' in facility_types or 'Refinery' in facility_types:
            services.append("fuel services")
        if 'Repair' in facility_types or 'Maintenance' in facility_types:
            services.append("repair facilities") 
        if 'Market' in facility_types or 'Trading' in facility_types:
            services.append("commodity exchange")
        if 'Missions' in facility_types:
            services.append("mission board")
        
        if services:
            base_msg += f"Available services: {', '.join(services)}. "
        
        base_msg += "Follow approach vector Gamma-7. Welcome to the station."
        
        return base_msg
    
    def _save_docking_bay_number(self, bay_number: int) -> None:
        """Save docking bay number for use in undocking dialog"""
        try:
            from data import db
            
            # Get fresh connection and explicit transaction
            conn = db.get_connection()
            conn.execute("UPDATE player SET docked_bay = ? WHERE id = 1", (bay_number,))
            conn.commit()
            logger.debug(f"Saved docking bay number: {bay_number} with explicit commit")
            
            # Verify with fresh connection 
            verification_conn = db.get_connection()
            result = verification_conn.execute("SELECT docked_bay FROM player WHERE id = 1").fetchone()
            verification = result[0] if result and result[0] is not None else None
            logger.debug(f"Verification: bay number now reads as {verification}")
            
            if verification != bay_number:
                logger.error(f"CRITICAL: Bay number verification failed! Set {bay_number}, got {verification}")
            
        except Exception as e:
            logger.error(f"Error saving docking bay number: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def _advance_communication(self):
        """Advance to the next step in the communication sequence"""
        try:
            if self.comm_sequence_step >= len(self.comm_messages):
                # Communication complete, ready to dock
                self.status_label.setText("DOCKING CLEARANCE GRANTED")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
                self.proceed_button.setVisible(True)
                self.cancel_button.setText("Cancel")
                return
            
            message = self.comm_messages[self.comm_sequence_step]
            
            # Add message to log
            self._add_comm_message(message['sender'], message['text'], message.get('color', '#00FF00'))
            
            # Update status
            if message['sender'] == 'system':
                self.status_label.setText("ESTABLISHING LINK...")
            elif message['sender'] == 'station':
                self.status_label.setText("RECEIVING TRANSMISSION")
            elif message['sender'] == 'player_auto':
                self.status_label.setText("TRANSMITTING RESPONSE")
            
            self.comm_sequence_step += 1
            
            # Schedule next message
            next_delay = message.get('delay', 1000)
            self.comm_timer.singleShot(next_delay, self._advance_communication)
        except Exception as e:
            logger.error(f"Error advancing communication: {e}")
    
    def _add_comm_message(self, sender: str, text: str, color: str = '#00FF00'):
        """Add a message to the communication log"""
        timestamp = time.strftime("%H:%M:%S")
        
        cursor = self.comm_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Format sender prefix
        if sender == 'system':
            prefix = f"[{timestamp}] SYS: "
        elif sender == 'station':
            prefix = f"[{timestamp}] STC: "
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
    
    def _proceed_docking(self):
        """Begin the docking procedure"""
        try:
            self.docking_phase = "docking"
            
            # Hide communication elements, show docking progress
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
            self.progress_bar.setFormat("Initiating Docking Sequence...")
            
            self.status_label.setText("DOCKING IN PROGRESS")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 10px; font-weight: bold;")
            
            # Add docking progress messages
            self._add_comm_message('system', ">>> Engaging autopilot docking sequence.", '#FFC107')
            self._add_comm_message('system', ">>> Adjusting approach vector to station coordinates.", '#FFC107')
            
            # Start docking timer
            self.dock_progress = 0
            self.dock_timer.start(100)  # Update every 100ms
        except Exception as e:
            logger.error(f"Error proceeding with docking: {e}")
    
    def _advance_docking(self):
        """Advance the docking progress"""
        try:
            # Slower progress - was 1-3, now 0.5-1.5 (about 5 seconds longer)
            self.dock_progress += random.uniform(0.5, 1.5)
            
            if self.dock_progress <= 100:
                self.progress_bar.setValue(int(self.dock_progress))
                
                # Update progress messages
                if self.dock_progress < 25:
                    self.progress_bar.setFormat("Aligning with docking port...")
                elif self.dock_progress < 50:
                    self.progress_bar.setFormat("Extending docking clamps...")
                elif self.dock_progress < 75:
                    self.progress_bar.setFormat("Securing airlock seal...")
                else:
                    self.progress_bar.setFormat("Finalizing docking procedures...")
                
                # More frequent progress messages for longer sequence
                if random.random() < 0.06:  # 6% chance per tick for more chatter
                    messages = [
                        ">>> Docking computer adjusting thrust vectors.",
                        ">>> Station magnetic field detected and compensated.",
                        ">>> Hull stress within normal parameters.",
                        ">>> Airlock systems preparing for connection.",
                        ">>> Atmospheric pressure equalizing.",
                        ">>> Structural integrity check in progress.",
                        ">>> Navigation beacon locked.",
                        ">>> Final approach vector confirmed.",
                        ">>> Docking clamps extending to secure position.",
                        ">>> Fuel lines connecting for station services.",
                        ">>> Power umbilical establishing connection.",
                        ">>> Data link synchronization in progress.",
                        ">>> Environmental systems bridging with station.",
                        ">>> Gravity field harmonization complete.",
                        ">>> Station tractor beam assisting alignment.",
                        ">>> Micro-thrusters fine-tuning position.",
                        ">>> Hull resonance dampeners activated.",
                        ">>> Cargo bay pressure seals engaging.",
                        ">>> Communication array switching to station relay.",
                        ">>> Backup life support systems on standby."
                    ]
                    self._add_comm_message('system', random.choice(messages), '#FFC107')
            else:
                # Docking complete
                self.dock_timer.stop()
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("DOCKING COMPLETE")
                
                self.status_label.setText("DOCKED SUCCESSFULLY")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
                
                self._add_comm_message('system', ">>> Docking complete. All systems nominal.", '#4CAF50')
                self._add_comm_message('system', ">>> Welcome aboard. Station services are now available.", '#4CAF50')
                
                # Final button
                self.cancel_button.setText("Close")
                self.cancel_button.clicked.disconnect()
                self.cancel_button.clicked.connect(self._complete_docking)
                
                # Auto-close after a moment
                QTimer.singleShot(2000, self._complete_docking)
        except Exception as e:
            logger.error(f"Error advancing docking progress: {e}")
    
    def _complete_docking(self):
        """Complete the docking sequence and close dialog"""
        try:
            # Save bay number to database when docking is confirmed
            if hasattr(self, 'assigned_bay'):
                self._save_docking_bay_number(self.assigned_bay)
                logger.debug(f"Saved bay number {self.assigned_bay} to database")
                
            self.docking_approved.emit()
            self.communication_complete.emit()
            self.accept()
        except Exception as e:
            logger.error(f"Error completing docking: {e}")
    
    def _emergency_abort(self):
        """Handle emergency abort during docking - IMMEDIATE ACTION"""
        try:
            # Emergency stop means STOP NOW - no confirmation dialog
            self._perform_emergency_abort()
        except Exception as e:
            logger.error(f"Error in emergency abort: {e}")
    
    def _perform_emergency_abort(self):
        """Perform the actual emergency abort"""
        try:
            # Stop all timers IMMEDIATELY
            self.dock_timer.stop()
            self.comm_timer.stop()
            
            # Update status to aborted
            self.docking_phase = "aborted"
            self.status_label.setText("DOCKING ABORTED")
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
            self._add_comm_message('system', ">>> All docking systems immediately disengaged.", '#d32f2f')
            self._add_comm_message('system', ">>> Warning: Ship systems may have been damaged.", '#FF5722')
            self._add_comm_message('system', ">>> Emergency thrusters fired - backing away from station.", '#FF5722')
            
            # Show aftermath dialog AFTER the emergency stop
            QMessageBox.critical(
                self,
                "Docking Emergency Abort",
                "🚨 EMERGENCY ABORT COMPLETE\n\n"
                "The docking sequence has been forcibly terminated.\n"
                "Your ship has backed away from the station using emergency thrusters.\n\n"
                "⚠️ WARNING: This emergency procedure may have caused:\n"
                "• Hull stress and potential damage\n"
                "• System malfunctions requiring repair\n"
                "• Fuel loss from emergency maneuvers\n\n"
                "Run a full system diagnostic before attempting another docking."
            )
            
            # Change button to reset
            self.cancel_button.setText("Try Docking Again")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self._reset_docking)
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
    
    def _reset_docking(self):
        """Reset the dialog to allow trying docking again"""
        try:
            # Reset all states
            self.docking_phase = "requesting"
            self.dock_progress = 0
            
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
                    color: #00FF00;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                    border-radius: 3px;
                }
            """)
            
            # Reset status
            self.status_label.setText("DOCKING CLEARANCE GRANTED")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
            
            # Clear and add reset message
            self.comm_log.clear()
            self._add_comm_message('system', ">>> Communication channel reset.", '#4CAF50')
            self._add_comm_message('system', ">>> Ready for new docking attempt.", '#4CAF50')
            
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
            logger.error(f"Error resetting docking: {e}")
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.docking_phase == "docking":
            # Don't allow closing during docking - show emergency abort option
            reply = QMessageBox.question(
                self,
                "Close During Docking",
                "Docking is currently in progress. You must either:\n\n"
                "• Wait for docking to complete, OR\n"
                "• Emergency abort the docking (immediate stop)\n\n"
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
