# /ui/dialogs/planet_landing_dialog.py

"""
Planet Landing Communication Dialog

Handles communication sequences with planetary ground control during landing requests,
showing authentic atmospheric control messages and landing clearance procedures.
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

logger = get_ui_logger('planet_landing')


class PlanetLandingDialog(QDialog):
    """
    Dialog for planetary ground control communication during landing procedures.
    Shows realistic atmospheric control messages and landing clearance.
    """
    
    # Signals
    landing_approved = Signal()  # No parameters - keep it simple
    landing_denied = Signal(str)  # reason
    communication_complete = Signal()
    
    def __init__(self, planet_name: str, planet_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.planet_name = planet_name
        self.planet_data = planet_data
        self.landing_phase = "requesting"  # requesting, approved, landing, complete
        
        # Landing pad assignment
        self.assigned_pad = self._assign_landing_pad()
        
        # Communication timing
        self._message_queue = []
        self._current_message_index = 0
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._show_next_message)
        
        self._setup_ui()
        self._start_communication_sequence()
    
    def _setup_ui(self):
        """Setup the communication dialog UI"""
        self.setWindowTitle(f"Planetary Approach - {self.planet_name}")
        self.setModal(True)
        self.resize(650, 450)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header with planet info
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_frame.setStyleSheet("QFrame { background-color: #1a1a2e; border: 1px solid #444; }")
        header_layout = QVBoxLayout(header_frame)
        
        planet_label = QLabel(f"Planetary Approach: {self.planet_name}")
        planet_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        planet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        planet_label.setStyleSheet("color: #00ff88; padding: 8px;")
        
        status_label = QLabel("Atmospheric Control Communications")
        status_label.setFont(QFont("Arial", 10))
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet("color: #aaaaaa; padding: 4px;")
        
        header_layout.addWidget(planet_label)
        header_layout.addWidget(status_label)
        layout.addWidget(header_frame)
        
        # Communication log
        self.comm_log = QTextEdit()
        self.comm_log.setReadOnly(True)
        self.comm_log.setFont(QFont("Consolas", 9))
        self.comm_log.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid #333;
                padding: 8px;
            }
        """)
        layout.addWidget(self.comm_log)
        
        # Progress bar for landing sequence
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)  # Initially hidden
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Landing Sequence Progress")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                background-color: #222;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00aa44;
            }
        """)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_frame)
        
        # Button area
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Proceed/Cancel buttons (initially hidden, shown after radio exchange)
        self.cancel_button = QPushButton("Cancel Landing")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.reject)
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
                background-color: #f44336;
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        self.proceed_button = QPushButton("Proceed with Landing")
        self.proceed_button.setVisible(False)
        self.proceed_button.clicked.connect(self._proceed_landing)
        self.proceed_button.setStyleSheet("""
            QPushButton {
                background-color: #006600;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #008800;
            }
        """)
        button_layout.addWidget(self.proceed_button)

        self.close_button = QPushButton("Close Communications")
        self.close_button.setEnabled(False)  # Enable when sequence complete
        self.close_button.clicked.connect(self.accept)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:enabled {
                background-color: #006600;
            }
            QPushButton:hover:enabled {
                background-color: #008800;
            }
        """)
        
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def _assign_landing_pad(self) -> str:
        """Assign a landing pad with atmospheric variations"""
        # Different pad naming conventions based on planet characteristics
        pad_prefixes = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel']
        pad_types = ['Landing Pad', 'Platform', 'Zone', 'Field', 'Terminal']
        
        # Some planets use numeric systems
        if random.choice([True, False]):
            pad_number = random.randint(1, 12)
            pad_type = random.choice(pad_types)
            return f"{pad_type} {pad_number}"
        else:
            # Others use military phonetic + numbers
            prefix = random.choice(pad_prefixes)
            number = random.randint(1, 9)
            return f"{prefix}-{number}"
    
    def _start_communication_sequence(self):
        """Initialize the communication sequence"""
        logger.debug(f"Starting planet landing communication for {self.planet_name}")
        
        # Build the message sequence
        self._build_message_sequence()
        
        # Start showing messages
        self._show_next_message()
    
    def _build_message_sequence(self):
        """Build the sequence of communication messages"""
        # Get callsign for the planet
        callsign = self._get_planet_callsign()
        controller_name = self._get_controller_name()
        
        # Get player and ship info
        from game import player_status
        status = player_status.get_status_snapshot()
        player_name = status.get('player_name', 'Commander')
        ship_name = status.get('ship_name', 'Unknown Vessel')
        
        # Build message sequence with delays
        self._message_queue = [
            # Initial contact
            {
                'sender': 'Ground Control',
                'text': self._get_initial_contact_message(callsign, controller_name, ship_name),
                'delay': 1.5,
                'color': '#00aaff'
            },
            # Player response
            {
                'sender': 'You',
                'text': f"{callsign} Ground Control, this is Commander {player_name} aboard the {ship_name}. We're deploying a shuttle for planetary surface operations and request landing clearance.",
                'delay': 2.0,
                'color': '#ffaa00'
            },
            # Weather/atmospheric check
            {
                'sender': 'Ground Control',
                'text': self._get_atmospheric_check_message(callsign, ship_name),
                'delay': 2.5,
                'color': '#00aaff'
            },
            # Landing clearance
            {
                'sender': 'Ground Control',
                'text': self._get_landing_clearance_message(callsign, ship_name),
                'delay': 1.5,
                'color': '#00aaff'
            }
        ]
    
    def _get_planet_callsign(self) -> str:
        """Generate a planet callsign based on planet name"""
        # Remove common planet suffixes and create callsign
        name = self.planet_name.replace(' Prime', '').replace(' Station', '').replace(' Colony', '')
        
        # Use first few letters + random suffix
        if len(name) >= 4:
            base = name[:4].upper()
        else:
            base = name.upper()
        
        # Add atmospheric control designation
        suffixes = ['GC', 'AC', 'TC', 'CC']  # Ground/Atmospheric/Tower/Control
        return f"{base} {random.choice(suffixes)}"
    
    def _get_controller_name(self) -> str:
        """Get a random controller name"""
        first_names = [
            'Sarah', 'Michael', 'Elena', 'David', 'Maria', 'James', 'Anna', 'Robert',
            'Chen', 'Yuki', 'Ahmed', 'Priya', 'Carlos', 'Zara', 'Ivan', 'Keiko'
        ]
        last_names = [
            'Rodriguez', 'Chen', 'Patel', 'Johnson', 'Nakamura', 'Singh', 'Williams',
            'Garcia', 'Kim', 'Anderson', 'Martinez', 'Wong', 'Thompson', 'Lee'
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    def _get_initial_contact_message(self, callsign: str, controller: str, ship_name: str) -> str:
        """Generate initial contact message from ground control"""
        greetings = [
            f"{callsign}, this is {controller} on approach vector control.",
            f"{callsign} here, {controller} speaking.",
            f"Good cycle, {ship_name}. This is {controller} at {callsign}.",
            f"{callsign} Approach Control, {controller} on duty."
        ]
        
        situations = [
            f"We have your main vessel on orbital sensors and detect shuttle deployment.",
            f"Tracking your shuttle's atmospheric entry from orbit.",
            f"We show your shuttle inbound from your orbiting vessel.",
            f"Atmospheric sensors have detected your shuttle launch from orbit."
        ]
        
        requests = [
            "State your shuttle's landing intentions and requested services.",
            "Please confirm shuttle pilot and surface operations requirements.",
            "What brings your shuttle to our surface today?",
            "State your shuttle's business and requested landing clearance type."
        ]
        
        return f"{random.choice(greetings)} {random.choice(situations)} {random.choice(requests)}"
    
    def _get_atmospheric_check_message(self, callsign: str, ship_name: str) -> str:
        """Generate atmospheric conditions check message"""
        weather_conditions = [
            "clear atmospheric conditions with light surface winds",
            "stable weather patterns with minimal thermal activity",
            "good visibility with standard atmospheric pressure",
            "calm surface conditions with optimal landing parameters",
            "light atmospheric disturbance with acceptable landing conditions",
            "clear skies with moderate surface winds from the northwest"
        ]
        
        instructions = [
            "Stand by for shuttle landing pad assignment and final approach vectors.",
            "Please maintain your shuttle's current altitude while we coordinate landing approach.",
            "Hold shuttle position for traffic coordination and pad availability check.",
            "Standby while we verify shuttle landing pad status and surface operations."
        ]
        
        return f"Copy {ship_name}, atmospheric conditions are {random.choice(weather_conditions)}. {random.choice(instructions)}"
    
    def _get_landing_clearance_message(self, callsign: str, ship_name: str) -> str:
        """Generate final landing clearance message"""
        # Vary the message based on different scenarios
        scenarios = [
            "standard_clearance",
            "priority_clearance", 
            "delayed_clearance"
        ]
        
        scenario = random.choice(scenarios)
        
        if scenario == "priority_clearance":
            base_msg = f"{ship_name}, your shuttle is cleared for priority landing at {self.assigned_pad}. "
            additional = random.choice([
                "Express your shuttle to the surface and proceed directly to landing operations.",
                "Fast-track approach authorized - proceed immediately to final landing sequence.",
                "Priority status granted - cleared for immediate atmospheric entry and shuttle landing."
            ])
        elif scenario == "delayed_clearance":
            base_msg = f"{ship_name}, shuttle landing clearance approved for {self.assigned_pad} with slight delay. "
            additional = random.choice([
                "Please hold your shuttle at 50km altitude for 2 minutes due to surface traffic.",
                "Hold shuttle current position briefly while we clear the landing zone.",
                "Minor delay due to surface operations - expect shuttle clearance in 90 seconds."
            ])
        else:  # standard_clearance
            base_msg = f"{ship_name}, your shuttle is cleared for landing at {self.assigned_pad}. "
            additional = random.choice([
                "Deploy your shuttle and proceed with standard atmospheric entry.",
                "Begin shuttle atmospheric entry sequence and landing procedures.",
                "Commence shuttle descent and surface approach procedures.",
                "You are go for shuttle atmospheric entry and surface operations."
            ])
        
        safety_msg = random.choice([
            "Contact surface operations on frequency 127.3 once landed.",
            "Switch to ground control on 142.7 after touchdown.",
            "Report to surface operations upon landing completion.",
            "Ground services will meet you at the landing zone."
        ])
        
        return f"{base_msg}{additional} {safety_msg}"
    
    def _show_next_message(self):
        """Show the next message in the sequence"""
        if self._current_message_index >= len(self._message_queue):
            # Sequence complete - show proceed/cancel options
            self._show_proceed_options()
            return
        
        message = self._message_queue[self._current_message_index]
        self._add_message(message['text'], message['sender'], message['color'])
        
        self._current_message_index += 1
        
        # Schedule next message if there are more
        if self._current_message_index < len(self._message_queue):
            QTimer.singleShot(int(message['delay'] * 1000), self._show_next_message)
        else:
            # Last message shown, show proceed/cancel options after a brief pause
            QTimer.singleShot(2000, self._show_proceed_options)
    
    def _show_proceed_options(self):
        """Show proceed and cancel buttons after radio exchange is complete"""
        from game_controller.log_config import get_ui_logger
        logger = get_ui_logger('planet_landing')
        logger.debug("Radio exchange complete - showing proceed/cancel options")
        
        # Show proceed/cancel buttons
        self.proceed_button.setVisible(True)
        self.cancel_button.setVisible(True)
        
        # Add message indicating clearance received
        self._add_message(
            "Landing clearance received. Ready to proceed with shuttle atmospheric entry.",
            "Ship Computer", 
            '#888888'
        )
    
    def _proceed_landing(self):
        """User confirmed to proceed with landing - start the landing sequence"""
        from game_controller.log_config import get_ui_logger
        logger = get_ui_logger('planet_landing')
        logger.debug("User confirmed landing - starting landing sequence")
        
        # Hide proceed/cancel buttons
        self.proceed_button.setVisible(False)
        self.cancel_button.setVisible(False)
        
        # Start the actual landing sequence
        self._start_landing_sequence()
    
    def _add_message(self, text: str, sender: str, color: str = '#ffffff'):
        """Add a message to the communication log"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Format message
        formatted_msg = f"[{timestamp}] {sender}: {text}\n"
        
        # Set color and add to log
        cursor = self.comm_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Set text color
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))
        cursor.setCharFormat(char_format)
        
        cursor.insertText(formatted_msg)
        
        # Scroll to bottom
        self.comm_log.ensureCursorVisible()
        
        logger.debug(f"Added message from {sender}: {text[:50]}...")
    
    def _start_landing_sequence(self):
        """Start the visual landing progress sequence"""
        logger.debug("Starting landing sequence")
        
        self.landing_phase = "landing"
        self.progress_frame.setVisible(True)
        
        # Add final message
        self._add_message(
            f"Landing sequence initiated. Deploying shuttle to {self.assigned_pad}...",
            "Ship Computer",
            '#888888'
        )
        
        # Start progress animation (120 second duration for maximum immersion)
        self._landing_timer = QTimer()
        self._landing_timer.timeout.connect(self._update_landing_progress)
        self._landing_progress = 0
        self._landing_timer.start(1200)  # Update every 1200ms (1.2s) for 120-second sequence
    
    def _get_landing_status_text(self, progress):
        """Get descriptive status text based on landing progress"""
        if progress <= 5:
            return "Shuttle Launch Preparation"
        elif progress <= 15:
            return "Atmospheric Entry"
        elif progress <= 25:
            return "Heat Shield Phase"
        elif progress <= 35:
            return "Middle Atmosphere"
        elif progress <= 45:
            return "Wind Shear Correction"
        elif progress <= 55:
            return "Lower Atmosphere"
        elif progress <= 65:
            return "Terminal Descent"
        elif progress <= 75:
            return "Landing Approach"
        elif progress <= 85:
            return "Final Approach"
        elif progress <= 95:
            return "Touchdown Sequence"
        else:
            return "Landing Complete"

    def _update_landing_progress(self):
        """Update the landing progress bar with detailed phases and radio chatter (120-second sequence)"""
        self._landing_progress += 1  # Exactly 1% per update for precise 120-second timing
        
        if self._landing_progress >= 100:
            self._landing_progress = 100
            self._landing_timer.stop()
            self._complete_landing()
        
        # Set both progress value and descriptive status text
        self.progress_bar.setValue(self._landing_progress)
        status_text = self._get_landing_status_text(self._landing_progress)
        self.progress_bar.setFormat(status_text)
        
        # Enhanced landing sequence with radio chatter between shuttle and ground control
        if self._landing_progress == 2:
            self._add_message("Main vessel maintaining stable orbit. Preparing shuttle for launch.", "Ship Computer", '#888888')
        elif self._landing_progress == 4:
            self._add_message("Ground Control, this is shuttle pilot preparing for atmospheric entry.", "Pilot", '#ffaa88')
        elif self._landing_progress == 6:
            self._add_message("Copy shuttle. Atmospheric conditions are stable. You're cleared for launch from orbit.", "Ground Control", '#00aaff')
        elif self._landing_progress == 8:
            self._add_message("Shuttle launch sequence initiated. Deploying from main vessel's shuttle bay.", "Ship Computer", '#888888')
        elif self._landing_progress == 10:
            self._add_message("Shuttle away from main ship. Beginning atmospheric interface.", "Pilot", '#ffaa88')
        elif self._landing_progress == 12:
            self._add_message("We have your shuttle on radar. Entry angle looks good.", "Ground Control", '#00aaff')
        elif self._landing_progress == 15:
            self._add_message("Shuttle upper atmosphere breached. Experiencing initial atmospheric drag.", "Ship Computer", '#888888')
        elif self._landing_progress == 17:
            self._add_message("Ground Control, shuttle atmospheric drag is nominal. All systems green.", "Pilot", '#ffaa88')
        elif self._landing_progress == 19:
            self._add_message("Roger shuttle. Maintain current trajectory. You're right on the glide path.", "Ground Control", '#00aaff')
        elif self._landing_progress == 22:
            self._add_message("Shuttle heat shield temperature nominal. Atmospheric density increasing.", "Ship Computer", '#888888')
        elif self._landing_progress == 24:
            self._add_message("Shuttle heat shield temps looking good from here. Proceed with descent.", "Ground Control", '#00aaff')
        elif self._landing_progress == 26:
            self._add_message("Shuttle entering middle atmosphere. Initiating attitude control systems.", "Ship Computer", '#888888')
        elif self._landing_progress == 28:
            self._add_message("Shuttle attitude control is active. Maintaining descent vector.", "Pilot", '#ffaa88')
        elif self._landing_progress == 30:
            self._add_message("Copy shuttle. Adjust heading 2 degrees starboard to compensate for wind shear.", "Ground Control", '#00aaff')
        elif self._landing_progress == 32:
            self._add_message("Shuttle atmospheric friction slowing descent. Heat shields performing nominally.", "Ship Computer", '#888888')
        elif self._landing_progress == 34:
            self._add_message("Adjusting shuttle heading as requested. Two degrees starboard.", "Pilot", '#ffaa88')
        elif self._landing_progress == 36:
            self._add_message("Perfect. That puts your shuttle right on target for the assigned landing zone.", "Ground Control", '#00aaff')
        elif self._landing_progress == 38:
            self._add_message("Shuttle powered descent protocol engaged. Preparing main engines.", "Ship Computer", '#888888')
        elif self._landing_progress == 40:
            self._add_message("Ground Control, shuttle is ready for powered descent to surface.", "Pilot", '#ffaa88')
        elif self._landing_progress == 42:
            self._add_message(f"Shuttle cleared for powered descent to {self.assigned_pad}.", "Ground Control", '#00aaff')
        elif self._landing_progress == 44:
            self._add_message("Shuttle descent engines online. Beginning powered descent to surface.", "Ship Computer", '#888888')
        elif self._landing_progress == 46:
            self._add_message("Shuttle descent initiated. Beginning independent approach to surface.", "Pilot", '#ffaa88')
        elif self._landing_progress == 48:
            self._add_message("We have your shuttle on approach radar. Looking good.", "Ground Control", '#00aaff')
        elif self._landing_progress == 50:
            self._add_message("Shuttle beginning powered descent phase. Main engines online.", "Ship Computer", '#888888')
        elif self._landing_progress == 52:
            self._add_message("Shuttle engines are lit. Beginning powered descent burn.", "Pilot", '#ffaa88')
        elif self._landing_progress == 54:
            self._add_message("Shuttle descent burn looks nominal. Maintain current rate of descent.", "Ground Control", '#00aaff')
        elif self._landing_progress == 56:
            self._add_message("Shuttle descent engines firing. Reducing atmospheric entry velocity.", "Ship Computer", '#888888')
        elif self._landing_progress == 58:
            self._add_message("Shuttle velocity reduction proceeding as planned. All systems nominal.", "Pilot", '#ffaa88')
        elif self._landing_progress == 60:
            self._add_message("Shuttle passing through 10,000 meters altitude. Descent rate is perfect.", "Ground Control", '#00aaff')
        elif self._landing_progress == 62:
            self._add_message("Shuttle lower atmosphere reached. Surface terrain scanning initiated.", "Ship Computer", '#888888')
        elif self._landing_progress == 64:
            self._add_message("Shuttle surface scans are active. Terrain mapping in progress.", "Pilot", '#ffaa88')
        elif self._landing_progress == 66:
            self._add_message(f"We're painting {self.assigned_pad} on the surface scope. Shuttle vector looks good.", "Ground Control", '#00aaff')
        elif self._landing_progress == 68:
            self._add_message(f"Shuttle landing zone {self.assigned_pad} acquired on sensors. Adjusting approach vector.", "Ship Computer", '#888888')
        elif self._landing_progress == 70:
            self._add_message(f"Shuttle pilot has visual on {self.assigned_pad}. Adjusting approach accordingly.", "Pilot", '#ffaa88')
        elif self._landing_progress == 72:
            self._add_message("Excellent. Your shuttle is lined up perfectly on the approach corridor.", "Ground Control", '#00aaff')
        elif self._landing_progress == 74:
            self._add_message("Shuttle navigation thrusters engaged. Fine-tuning descent trajectory.", "Ship Computer", '#888888')
        elif self._landing_progress == 76:
            self._add_message("Fine-tuning shuttle approach. Nav thrusters responding well.", "Pilot", '#ffaa88')
        elif self._landing_progress == 78:
            self._add_message("Looking good. Your shuttle is at 2,000 meters and descending steadily.", "Ground Control", '#00aaff')
        elif self._landing_progress == 80:
            self._add_message("Shuttle atmospheric conditions stable. Beginning final approach sequence.", "Ship Computer", '#888888')
        elif self._landing_progress == 82:
            self._add_message("Shuttle beginning final approach. All pre-landing checks complete.", "Pilot", '#ffaa88')
        elif self._landing_progress == 84:
            self._add_message("Copy shuttle final approach. Landing beacon is active to guide you in.", "Ground Control", '#00aaff')
        elif self._landing_progress == 86:
            self._add_message("Shuttle landing zone visual confirmed. Deploying landing gear and stabilizers.", "Ship Computer", '#888888')
        elif self._landing_progress == 88:
            self._add_message("Shuttle landing gear deployed. I can see the landing pad clearly now.", "Pilot", '#ffaa88')
        elif self._landing_progress == 90:
            self._add_message("Shuttle landing gear deployment confirmed. You're at 500 meters.", "Ground Control", '#00aaff')
        elif self._landing_progress == 92:
            self._add_message("Shuttle landing gear deployed and locked. Descent engines at 60% power.", "Ship Computer", '#888888')
        elif self._landing_progress == 94:
            self._add_message("Reducing shuttle engine power for final approach. Almost there.", "Pilot", '#ffaa88')
        elif self._landing_progress == 96:
            self._add_message("Your shuttle is looking perfect. 100 meters and closing. Maintain current approach.", "Ground Control", '#00aaff')
        elif self._landing_progress == 97:
            self._add_message("Shuttle final approach commenced. Altitude 50 meters and decreasing.", "Ship Computer", '#888888')
        elif self._landing_progress == 98:
            self._add_message("Shuttle almost down. Landing thrusters engaged for final positioning.", "Pilot", '#ffaa88')
        elif self._landing_progress == 99:
            self._add_message(f"Perfect shuttle approach. You're right over {self.assigned_pad}. Prepare for touchdown.", "Ground Control", '#00aaff')
        elif self._landing_progress == 100:
            self._add_message("Shuttle landing contact detected. Engaging surface stabilization systems.", "Ship Computer", '#888888')
    
    def _complete_landing(self):
        """Complete the landing sequence"""
        logger.debug("Landing sequence complete")
        
        self.landing_phase = "complete"
        self.progress_label.setText("Landing Complete")
        self.progress_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        
        # Final messages
        self._add_message(f"Shuttle touchdown confirmed at {self.assigned_pad}. Landing sequence complete.", "Ship Computer", '#888888')
        self._add_message("All shuttle systems nominal. Landing stabilizers engaged. Shuttle secured.", "Ship Computer", '#888888')
        self._add_message("Shuttle atmospheric processors cycling down. Surface operations ready.", "Ship Computer", '#888888')
        self._add_message("Welcome shuttle to planetary surface operations. Ground services available.", "Ground Control", '#00aaff')
        
        # Enable close button and emit signal
        self.close_button.setEnabled(True)
        self.close_button.setText("Enter Surface Terminal")
        
        # Emit landing approved signal
        self.landing_approved.emit()
        
        logger.debug(f"Landing approved at {self.assigned_pad}")


def show_planet_landing_dialog(planet_name: str, planet_data: Dict[str, Any], parent=None) -> bool:
    """
    Show planet landing dialog and handle the communication sequence.
    Returns True if landing was approved and completed.
    """
    dialog = PlanetLandingDialog(planet_name, planet_data, parent)
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted and dialog.landing_phase == "complete":
        return True
    return False
