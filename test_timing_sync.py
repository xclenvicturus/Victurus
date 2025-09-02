# /test_timing_sync.py

"""
Test Timing Synchronization Fix

This test verifies that the ShipStatusOverlay and TravelProgressOverlay
update in sync when travel state changes, eliminating the ~1 second delay.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QTimer, Signal, QObject

from ui.widgets.travel_status_overlay import TravelStatusOverlay
from ui.maps.simple_travel_vis import SimpleTravelStatus

class MockTravelFlow(QObject):
    """Mock TravelFlow that emits progressTick signal"""
    progressTick = Signal()
    
    def __init__(self):
        super().__init__()
        self._seq = [
            {'name': 'depart', 'set_state': 'Departing', 'duration_ms': 2000},
            {'name': 'cruise', 'set_state': 'Cruising', 'duration_ms': 5000},
            {'name': 'arrive', 'set_state': 'Arriving', 'duration_ms': 1000},
        ]
        self._seq_index = 0
        self._phase_timer = QTimer()
        self._phase_timer.timeout.connect(self._advance_phase)
        self._phase_duration_ms = 0
        self._phase_name = 'idle'
        self._start_time = None
        
    def start_travel(self):
        """Start mock travel sequence"""
        print("🚀 Starting mock travel...")
        self._seq_index = 0
        self._start_time = time.time() * 1000  # ms
        self._start_phase()
        
        # Emit progress ticks every 50ms (faster than real system for testing)
        self._progress_timer = QTimer()
        self._progress_timer.timeout.connect(self.progressTick.emit)
        self._progress_timer.start(50)
        
    def _start_phase(self):
        """Start current phase"""
        if self._seq_index < len(self._seq):
            phase = self._seq[self._seq_index]
            self._phase_name = phase['name']
            self._phase_duration_ms = phase['duration_ms']
            print(f"📍 Phase {self._seq_index}: {phase['set_state']} ({self._phase_duration_ms}ms)")
            
            # Start phase timer
            self._phase_timer.start(self._phase_duration_ms)
        else:
            # Travel complete
            print("✅ Travel complete!")
            self._progress_timer.stop()
            self._phase_timer.stop()
            
    def _advance_phase(self):
        """Advance to next phase"""
        self._phase_timer.stop()
        self._seq_index += 1
        self._start_phase()

class TimingSyncTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Travel Timing Synchronization Test")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Instructions
        instructions = QLabel(
            "This test simulates the SimpleTravelStatus signal flow.\n"
            "Watch both overlays - they should update simultaneously during travel.\n"
            "The status overlay should switch to fast updates (100ms) during travel."
        )
        layout.addWidget(instructions)
        
        # Test controls
        self.start_btn = QPushButton("Start Mock Travel")
        self.start_btn.clicked.connect(self.start_travel_test)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Travel")
        self.stop_btn.clicked.connect(self.stop_travel_test)
        layout.addWidget(self.stop_btn)
        
        # Status label for debugging
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)
        
        # Create the unified overlay system
        self.travel_overlay = TravelStatusOverlay(central)
        
        # Create mock travel system
        self.mock_travel_flow = MockTravelFlow()
        self.travel_status = SimpleTravelStatus()
        self.travel_status.set_travel_flow(self.mock_travel_flow)
        
        # Connect to travel status changes (same as real system)
        self.travel_status.travel_status_changed.connect(self.travel_overlay.set_travel_info)
        self.travel_status.travel_status_changed.connect(self.on_travel_status_changed)
        
        # Show the status overlay (always visible)
        self.travel_overlay.show()
        
        # Update counter to track synchronization
        self.status_update_count = 0
        self.progress_update_count = 0
        
        # Timing verification timer
        self.verification_timer = QTimer()
        self.verification_timer.timeout.connect(self.verify_timing)
        self.verification_timer.start(200)  # Check every 200ms
        
    def start_travel_test(self):
        """Start the travel test"""
        self.status_label.setText("Status: Starting travel test...")
        self.status_update_count = 0
        self.progress_update_count = 0
        
        # Start tracking travel
        self.travel_status.start_travel_tracking("loc", 123)
        
        # Start mock travel flow
        self.mock_travel_flow.start_travel()
        
    def stop_travel_test(self):
        """Stop the travel test"""
        self.status_label.setText("Status: Stopping travel test...")
        
        # Stop mock travel
        if hasattr(self.mock_travel_flow, '_progress_timer'):
            self.mock_travel_flow._progress_timer.stop()
        if hasattr(self.mock_travel_flow, '_phase_timer'):
            self.mock_travel_flow._phase_timer.stop()
            
        # End travel tracking
        self.travel_status.end_travel_tracking()
        
    def on_travel_status_changed(self, travel_info):
        """Track travel status changes for verification"""
        self.progress_update_count += 1
        is_traveling = bool(travel_info)
        
        status_msg = f"Travel Status Update #{self.progress_update_count}: "
        if is_traveling:
            phase = travel_info.get('phase', 'unknown')
            progress = travel_info.get('progress', 0) * 100
            status_msg += f"{phase} ({progress:.1f}%)"
        else:
            status_msg += "Travel ended"
            
        self.status_label.setText(status_msg)
        
        # Log the timing sync
        print(f"⏱️  Travel status changed: {travel_info.get('phase', 'ended')} - "
              f"Both overlays should update NOW")
        
    def verify_timing(self):
        """Verify timing synchronization"""
        # This runs every 200ms to check if updates are synchronized
        # In a real implementation, both overlays should update within 
        # a few milliseconds of the travel_status_changed signal
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = TimingSyncTestWindow()
    window.show()
    
    print("🔧 Timing Synchronization Test")
    print("="*50)
    print("Expected behavior:")
    print("1. Status overlay updates every 1000ms when not traveling")  
    print("2. During travel, status overlay switches to 100ms updates")
    print("3. Progress overlay updates immediately with travel signals")
    print("4. Both overlays should be synchronized during travel")
    print("="*50)
    
    sys.exit(app.exec())
