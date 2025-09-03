# /ui/dialogs/planet_launch_dialog.py

"""
Planet Launch Communication Dialog

Handles communication sequences with ground control during takeoff/launch procedures,
showing authentic atmospheric control messages and launch clearance procedures.
"""

from __future__ import annotations

import time
import random
from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QColor

from game_controller.log_config import get_ui_logger

logger = get_ui_logger('planet_launch')


class PlanetLaunchDialog(QDialog):
    """
    Dialog for planetary ground control communication during launch procedures.
    Shows realistic atmospheric control messages and takeoff clearance.
    """
    
    # Signals
    launch_approved = Signal()
    launch_denied = Signal(str)  # reason
    communication_complete = Signal()
    
    def __init__(self, planet_name: str, planet_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.planet_name = planet_name
        self.planet_data = planet_data
        self.launch_phase = "requesting"  # requesting, approved, launching, complete
        
        # Launch parameters
        self.departure_time = self._get_departure_time()
        self.atmospheric_conditions = self._get_atmospheric_conditions()
        
        # Communication timing
        self._message_queue = []
        self._current_message_index = 0
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._show_next_message)
        
        self._setup_ui()
        self._start_communication_sequence()
    
    def _setup_ui(self):
        """Setup the communication dialog UI"""
        self.setWindowTitle(f"Launch Control - {self.planet_name}")
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
        
        planet_label = QLabel(f"Surface Operations: {self.planet_name}")
        planet_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        planet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        planet_label.setStyleSheet("color: #ff8800; padding: 8px;")
        
        status_label = QLabel("Launch Control Communications")
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
                color: #ffaa00;
                border: 1px solid #333;
                padding: 8px;
            }
        """)
        layout.addWidget(self.comm_log)
        
        # Progress bar for launch sequence
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)  # Initially hidden
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Launch Sequence Progress")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                background-color: #222;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #ff6600;
            }
        """)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_frame)
        
        # Button area
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Proceed/Cancel buttons (initially hidden, shown after radio exchange)
        self.cancel_button = QPushButton("Cancel Launch")
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
        
        self.proceed_button = QPushButton("Proceed with Launch")
        self.proceed_button.setVisible(False)
        self.proceed_button.clicked.connect(self._proceed_launch)
        self.proceed_button.setStyleSheet("""
            QPushButton {
                background-color: #cc4400;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ee6600;
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
                background-color: #cc4400;
            }
            QPushButton:hover:enabled {
                background-color: #ee6600;
            }
        """)
        
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def _get_departure_time(self) -> str:
        """Generate departure window information"""
        windows = [
            "optimal atmospheric window",
            "standard departure slot",
            "priority launch window",
            "next available departure window",
            "emergency departure clearance"
        ]
        return random.choice(windows)
    
    def _get_atmospheric_conditions(self) -> str:
        """Generate atmospheric conditions for launch"""
        conditions = [
            "stable atmospheric pressure with minimal wind shear",
            "calm surface winds with good visibility",
            "acceptable thermal columns for powered ascent",
            "light atmospheric disturbance with safe launch parameters",
            "clear atmospheric conditions with optimal launch vectors",
            "steady pressure gradients suitable for orbital insertion"
        ]
        return random.choice(conditions)
    
    def _start_communication_sequence(self):
        """Initialize the communication sequence"""
        logger.debug(f"Starting planet launch communication for {self.planet_name}")
        
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
                'sender': 'Launch Control',
                'text': self._get_initial_contact_message(callsign, controller_name, ship_name),
                'delay': 1.5,
                'color': '#ffaa00'
            },
            # Player response
            {
                'sender': 'You',
                'text': f"{callsign} Launch Control, this is Commander {player_name}. Our shuttle has completed surface operations and is requesting departure clearance to return to the {ship_name} in orbit.",
                'delay': 2.0,
                'color': '#00aaff'
            },
            # Pre-launch check
            {
                'sender': 'Launch Control',
                'text': self._get_prelaunch_check_message(callsign, ship_name),
                'delay': 2.5,
                'color': '#ffaa00'
            },
            # Launch clearance
            {
                'sender': 'Launch Control',
                'text': self._get_launch_clearance_message(callsign, ship_name),
                'delay': 1.5,
                'color': '#ffaa00'
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
        
        # Add launch control designation
        suffixes = ['LC', 'DC', 'SC', 'FC']  # Launch/Departure/Surface/Flight Control
        return f"{base} {random.choice(suffixes)}"
    
    def _get_controller_name(self) -> str:
        """Get a random controller name"""
        first_names = [
            'Marcus', 'Elena', 'David', 'Sarah', 'Chen', 'Maria', 'James', 'Anna',
            'Viktor', 'Priya', 'Ahmed', 'Keiko', 'Carlos', 'Zara', 'Ivan', 'Yuki'
        ]
        last_names = [
            'Thompson', 'Garcia', 'Kim', 'Anderson', 'Martinez', 'Singh', 'Chen',
            'Rodriguez', 'Nakamura', 'Patel', 'Johnson', 'Wong', 'Williams', 'Lee'
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    def _get_initial_contact_message(self, callsign: str, controller: str, ship_name: str) -> str:
        """Generate initial contact message from launch control"""
        greetings = [
            f"{callsign} Launch Control, this is {controller} on surface operations.",
            f"Surface Control here, {controller} speaking.",
            f"Good cycle, shuttle from {ship_name}. This is {controller} at {callsign}.",
            f"{callsign} Surface Operations, {controller} on duty."
        ]
        
        situations = [
            f"We show your shuttle secure on {self._get_landing_pad_reference()}.",
            f"Your shuttle is confirmed ready for atmospheric departure from surface platform.",
            f"Surface operations complete. Your shuttle is prepared for return to orbit.",
            f"Surface checklist complete. Shuttle ready to return to main vessel in orbit."
        ]
        
        requests = [
            "Please confirm shuttle readiness and orbital rendezvous with main vessel.",
            "Confirm your shuttle's orbital return vector and docking timeline.",
            "State your shuttle's departure intentions and orbital rendezvous requirements.",
            "Please confirm shuttle readiness for atmospheric exit and orbital docking."
        ]
        
        return f"{random.choice(greetings)} {random.choice(situations)} {random.choice(requests)}"
    
    def _get_landing_pad_reference(self) -> str:
        """Get reference to the landing pad we're departing from"""
        pad_types = ['Landing Pad', 'Platform', 'Zone', 'Field', 'Terminal']
        
        if random.choice([True, False]):
            pad_number = random.randint(1, 12)
            pad_type = random.choice(pad_types)
            return f"{pad_type} {pad_number}"
        else:
            prefixes = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Echo', 'Foxtrot']
            prefix = random.choice(prefixes)
            number = random.randint(1, 9)
            return f"{prefix}-{number}"
    
    def _get_prelaunch_check_message(self, callsign: str, ship_name: str) -> str:
        """Generate pre-launch systems check message"""
        return f"Copy shuttle from {ship_name}. Atmospheric conditions are {self.atmospheric_conditions}. " + \
               f"Your {self.departure_time} has been confirmed for shuttle return to orbit. " + \
               random.choice([
                   "Please stand by while we coordinate airspace clearance for your shuttle.",
                   "Hold position while we verify shuttle atmospheric departure corridors.",
                   "Standby for final shuttle systems check and launch sequence authorization.",
                   "Please wait while we clear shuttle orbital return vectors."
               ])
    
    def _get_launch_clearance_message(self, callsign: str, ship_name: str) -> str:
        """Generate final launch clearance message"""
        # Vary the message based on different scenarios
        scenarios = ["standard_launch", "priority_launch", "delayed_launch"]
        scenario = random.choice(scenarios)
        
        if scenario == "priority_launch":
            base_msg = f"Shuttle from {ship_name}, you are cleared for priority atmospheric departure. "
            additional = random.choice([
                "Begin immediate shuttle launch sequence and proceed to orbital rendezvous.",
                "Priority clearance granted - commence shuttle atmospheric exit immediately.",
                "Fast-track departure authorized - begin shuttle launch procedures now."
            ])
        elif scenario == "delayed_launch":
            base_msg = f"Shuttle from {ship_name}, launch clearance approved with brief delay. "
            additional = random.choice([
                "Hold position for 60 seconds due to orbital traffic coordination.",
                "Minor delay while we clear departing traffic from your shuttle vector.",
                "Brief hold required for shuttle atmospheric corridor management."
            ])
        else:  # standard_launch
            base_msg = f"Shuttle from {ship_name}, you are cleared for atmospheric departure. "
            additional = random.choice([
                "Begin standard shuttle launch sequence and orbital rendezvous procedures.",
                "Commence shuttle atmospheric exit sequence at your discretion.",
                "You are go for shuttle launch. Proceed with orbital rendezvous burn.",
                "Shuttle launch sequence authorized. Begin atmospheric departure procedures."
            ])
        
        final_msg = random.choice([
            "Contact orbital control on frequency 156.9 once you reach your main vessel.",
            "Switch to orbital traffic control on 143.2 after shuttle docking.",
            "Report to space traffic control upon achieving orbital rendezvous.",
            "Good flying and safe return to your main vessel."
        ])
        
        return f"{base_msg}{additional} {final_msg}"
    
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
        logger = get_ui_logger('planet_launch')
        logger.debug("Radio exchange complete - showing proceed/cancel options")
        
        # Show proceed/cancel buttons
        self.proceed_button.setVisible(True)
        self.cancel_button.setVisible(True)
        
        # Add message indicating clearance received
        self._add_message(
            "Launch clearance received. Ready to proceed with shuttle atmospheric departure.",
            "Ship Computer", 
            '#888888'
        )
    
    def _proceed_launch(self):
        """User confirmed to proceed with launch - start the launch sequence"""
        from game_controller.log_config import get_ui_logger
        logger = get_ui_logger('planet_launch')
        logger.debug("User confirmed launch - starting launch sequence")
        
        # Hide proceed/cancel buttons
        self.proceed_button.setVisible(False)
        self.cancel_button.setVisible(False)
        
        # Start the actual launch sequence
        self._start_launch_sequence()
    
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
    
    def _start_launch_sequence(self):
        """Start the visual launch progress sequence"""
        logger.debug("Starting launch sequence")
        
        self.launch_phase = "launching"
        self.progress_frame.setVisible(True)
        
        # Add final message
        self._add_message(
            "Shuttle launch sequence initiated. Beginning atmospheric exit procedures to return to main vessel...",
            "Ship Computer",
            '#888888'
        )
        
        # Start progress animation (120 second duration for maximum immersion)
        self._launch_timer = QTimer()
        self._launch_timer.timeout.connect(self._update_launch_progress)
        self._launch_progress = 0
        self._launch_timer.start(1200)  # Update every 1200ms (1.2s) for 120-second sequence
    
    def _get_launch_status_text(self, progress):
        """Get descriptive status text based on launch progress"""
        if progress <= 5:
            return "Pre-Flight Preparation"
        elif progress <= 15:
            return "Engine Ignition"
        elif progress <= 25:
            return "Surface Launch"
        elif progress <= 35:
            return "Lower Atmosphere"
        elif progress <= 45:
            return "Middle Atmosphere"
        elif progress <= 55:
            return "Upper Atmosphere"
        elif progress <= 65:
            return "Exosphere Transit"
        elif progress <= 75:
            return "Orbital Insertion"
        elif progress <= 85:
            return "Docking Approach"
        elif progress <= 95:
            return "Final Docking"
        else:
            return "Launch Complete"

    def _update_launch_progress(self):
        """Update the launch progress bar with detailed phases and radio chatter (120-second sequence)"""
        self._launch_progress += 1  # Exactly 1% per update for precise 120-second timing
        
        if self._launch_progress >= 100:
            self._launch_progress = 100
            self._launch_timer.stop()
            self._complete_launch()
        
        # Set both progress value and descriptive status text
        self.progress_bar.setValue(self._launch_progress)
        status_text = self._get_launch_status_text(self._launch_progress)
        self.progress_bar.setFormat(status_text)
        
        # Enhanced launch sequence with radio chatter between shuttle pilot, launch control, and ship computer
        if self._launch_progress == 2:
            self._add_message("Surface operations complete. Initializing shuttle launch preparation sequence.", "Ship Computer", '#888888')
        elif self._launch_progress == 4:
            self._add_message("Launch Control, this is the shuttle pilot. We're beginning pre-flight checks for return to main vessel.", "Pilot", '#ffaa88')
        elif self._launch_progress == 6:
            self._add_message("Copy shuttle pilot. All surface systems show green. You're cleared for pre-flight.", "Launch Control", '#00aaff')
        elif self._launch_progress == 8:
            self._add_message("Shuttle pre-flight systems check initiated. All systems nominal.", "Ship Computer", '#888888')
        elif self._launch_progress == 10:
            self._add_message("Shuttle pre-flight checks complete. All systems are go for launch.", "Pilot", '#ffaa88')
        elif self._launch_progress == 12:
            self._add_message("Excellent. Surface stabilizers show ready for shuttle disengagement.", "Launch Control", '#00aaff')
        elif self._launch_progress == 14:
            self._add_message("Shuttle atmospheric processors warming up. Surface stabilizers disengaged.", "Ship Computer", '#888888')
        elif self._launch_progress == 16:
            self._add_message("Launch Control, we're warming up the shuttle atmospheric processors now.", "Pilot", '#ffaa88')
        elif self._launch_progress == 18:
            self._add_message("Roger shuttle. Atmospheric conditions remain stable for launch.", "Launch Control", '#00aaff')
        elif self._launch_progress == 20:
            self._add_message("Shuttle launch engines performing systems check. Fuel systems pressurized.", "Ship Computer", '#888888')
        elif self._launch_progress == 22:
            self._add_message("Launch Control, shuttle fuel systems are pressurized and ready.", "Pilot", '#ffaa88')
        elif self._launch_progress == 24:
            self._add_message("Copy shuttle. Your launch window is confirmed. Proceed when ready.", "Launch Control", '#00aaff')
        elif self._launch_progress == 26:
            self._add_message("Shuttle navigation systems updated with orbital rendezvous parameters.", "Ship Computer", '#888888')
        elif self._launch_progress == 28:
            self._add_message("Rendezvous parameters uploaded. Shuttle ready for engine ignition.", "Pilot", '#ffaa88')
        elif self._launch_progress == 30:
            self._add_message("Shuttle cleared for engine ignition. Safe return to your main vessel.", "Launch Control", '#00aaff')
        elif self._launch_progress == 32:
            self._add_message("Beginning shuttle engine ignition sequence. Main engines coming online.", "Ship Computer", '#888888')
        elif self._launch_progress == 34:
            self._add_message("Shuttle engines are firing up. Here we go, Launch Control.", "Pilot", '#ffaa88')
        elif self._launch_progress == 36:
            self._add_message("Looking good on our scopes. Shuttle engine ignition nominal.", "Launch Control", '#00aaff')
        elif self._launch_progress == 38:
            self._add_message("Shuttle launch engines fired. Beginning atmospheric exit burn sequence.", "Ship Computer", '#888888')
        elif self._launch_progress == 40:
            self._add_message("We have shuttle liftoff! Climbing through lower atmosphere.", "Pilot", '#ffaa88')
        elif self._launch_progress == 42:
            self._add_message("Shuttle liftoff confirmed. You're climbing beautifully. Maintain heading.", "Launch Control", '#00aaff')
        elif self._launch_progress == 44:
            self._add_message("Shuttle lift-off achieved. Ascending through lower planetary atmosphere.", "Ship Computer", '#888888')
        elif self._launch_progress == 46:
            self._add_message("Shuttle altitude increasing rapidly. Atmospheric drag decreasing.", "Pilot", '#ffaa88')
        elif self._launch_progress == 48:
            self._add_message("Perfect shuttle ascent profile. You're passing 5,000 meters now.", "Launch Control", '#00aaff')
        elif self._launch_progress == 50:
            self._add_message("Shuttle atmospheric drag decreasing. Altitude 5,000 meters and climbing.", "Ship Computer", '#888888')
        elif self._launch_progress == 52:
            self._add_message("Shuttle lower atmosphere cleared. Engines performing nominally.", "Pilot", '#ffaa88')
        elif self._launch_progress == 54:
            self._add_message("Excellent. Your shuttle is entering the middle atmosphere now.", "Launch Control", '#00aaff')
        elif self._launch_progress == 56:
            self._add_message("Shuttle lower atmosphere cleared. Engines performing nominally.", "Ship Computer", '#888888')
        elif self._launch_progress == 58:
            self._add_message("Launch Control, shuttle is feeling less atmospheric pressure now.", "Pilot", '#ffaa88')
        elif self._launch_progress == 60:
            self._add_message("Copy shuttle. You're transitioning through middle atmosphere layers.", "Launch Control", '#00aaff')
        elif self._launch_progress == 62:
            self._add_message("Shuttle entering middle atmosphere. Atmospheric pressure decreasing.", "Ship Computer", '#888888')
        elif self._launch_progress == 64:
            self._add_message("Shuttle at 25,000 meters and climbing. Atmosphere is thinning out nicely.", "Pilot", '#ffaa88')
        elif self._launch_progress == 66:
            self._add_message("Outstanding. Shuttle maintain current trajectory to upper atmosphere.", "Launch Control", '#00aaff')
        elif self._launch_progress == 68:
            self._add_message("Shuttle passing through middle atmosphere. Altitude 25,000 meters.", "Ship Computer", '#888888')
        elif self._launch_progress == 70:
            self._add_message("Shuttle is approaching the upper atmosphere boundary.", "Pilot", '#ffaa88')
        elif self._launch_progress == 72:
            self._add_message("Roger shuttle. You're almost at the edge of space. Looking great.", "Launch Control", '#00aaff')
        elif self._launch_progress == 74:
            self._add_message("Shuttle upper atmosphere boundary reached. Atmospheric density minimal.", "Ship Computer", '#888888')
        elif self._launch_progress == 76:
            self._add_message("Launch Control, shuttle can see the curve of the planet and our main vessel in orbit.", "Pilot", '#ffaa88')
        elif self._launch_progress == 78:
            self._add_message("Beautiful shuttle. You're at the threshold of space. Prepare for orbital rendezvous burn.", "Launch Control", '#00aaff')
        elif self._launch_progress == 80:
            self._add_message("Shuttle atmospheric exit threshold achieved. Space interface approaching.", "Ship Computer", '#888888')
        elif self._launch_progress == 82:
            self._add_message("Beginning shuttle orbital rendezvous burn. Switching to orbital mode.", "Pilot", '#ffaa88')
        elif self._launch_progress == 84:
            self._add_message("Copy shuttle orbital burn. This will be our last transmission planetside.", "Launch Control", '#00aaff')
        elif self._launch_progress == 86:
            self._add_message("Beginning shuttle orbital rendezvous burn. Adjusting velocity vector.", "Ship Computer", '#888888')
        elif self._launch_progress == 88:
            self._add_message("Shuttle orbital burn is smooth. Velocity increasing for rendezvous.", "Pilot", '#ffaa88')
        elif self._launch_progress == 90:
            self._add_message("Safe shuttle docking with your main vessel. Contact orbital control for routing.", "Launch Control", '#00aaff')
        elif self._launch_progress == 92:
            self._add_message("Shuttle orbital rendezvous sequence active. Fine-tuning docking parameters.", "Ship Computer", '#888888')
        elif self._launch_progress == 94:
            self._add_message("Thank you Launch Control. Shuttle is achieving orbital rendezvous.", "Pilot", '#ffaa88')
        elif self._launch_progress == 96:
            self._add_message("Shuttle achieving stable orbital velocity. Atmospheric exit nearly complete.", "Ship Computer", '#888888')
        elif self._launch_progress == 98:
            self._add_message("Shuttle orbital rendezvous burn successful. Establishing docking trajectory.", "Ship Computer", '#888888')
        elif self._launch_progress == 99:
            self._add_message("Shuttle orbital velocity achieved. Preparing to dock with main vessel.", "Pilot", '#ffaa88')
    
    def _complete_launch(self):
        """Complete the launch sequence"""
        logger.debug("Launch sequence complete")
        
        self.launch_phase = "complete"
        self.progress_label.setText("Launch Complete")
        self.progress_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        
        # Final messages with shuttle docking
        self._add_message("Shuttle orbital rendezvous complete. All spacecraft systems nominal.", "Ship Computer", '#888888')
        self._add_message("Shuttle has achieved stable orbit! Preparing to dock with main vessel.", "Pilot", '#ffaa88')
        self._add_message("Shuttle orbital rendezvous successful. Docking with main vessel initiated.", "Ship Computer", '#888888')
        self._add_message("All shuttle systems nominal. Atmospheric exit complete. Docking in progress.", "Ship Computer", '#888888')
        self._add_message("Shuttle docking sequence complete. Ready for interplanetary operations.", "Ship Computer", '#888888')
        
        # Enable close button and emit signal
        self.close_button.setEnabled(True)
        self.close_button.setText("Resume Orbital Operations")
        
        # Emit launch approved signal
        self.launch_approved.emit()
        
        logger.debug("Launch approved and orbital insertion complete")


def show_planet_launch_dialog(planet_name: str, planet_data: Dict[str, Any], parent=None) -> bool:
    """
    Show planet launch dialog and handle the communication sequence.
    Returns True if launch was approved and completed.
    """
    dialog = PlanetLaunchDialog(planet_name, planet_data, parent)
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted and dialog.launch_phase == "complete":
        return True
    return False
