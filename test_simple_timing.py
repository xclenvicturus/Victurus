# /test_simple_timing.py

"""
Simple Timing Synchronization Test

Directly tests the TravelStatusOverlay timing synchronization fix.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QTimer

from ui.widgets.travel_status_overlay import TravelStatusOverlay

class SimpleTimingTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Timing Synchronization Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Instructions
        instructions = QLabel(
            "Test the timing synchronization fix:\n"
            "• Status overlay normally updates every 1000ms\n"
            "• During 'travel', it should switch to 100ms updates\n"
            "• Both overlays should show/hide simultaneously"
        )
        layout.addWidget(instructions)
        
        # Test controls
        self.start_btn = QPushButton("Start 'Travel' (Show Progress + Fast Status Updates)")
        self.start_btn.clicked.connect(self.start_travel)
        layout.addWidget(self.start_btn)
        
        self.end_btn = QPushButton("End 'Travel' (Hide Progress + Slow Status Updates)")
        self.end_btn.clicked.connect(self.end_travel)
        layout.addWidget(self.end_btn)
        
        # Status label
        self.status_label = QLabel("Status: Not traveling (1000ms status updates)")
        layout.addWidget(self.status_label)
        
        # Create the unified overlay system
        self.travel_overlay = TravelStatusOverlay(central)
        self.travel_overlay.show()
        
        # Progress simulation data
        self.progress = 0.0
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        
    def start_travel(self):
        """Simulate starting travel"""
        self.status_label.setText("Status: Traveling (100ms status updates, progress visible)")
        
        # Start with travel info - this triggers the synchronization fix
        travel_info = {
            'phase': 'Cruising',
            'progress': 0.0,
            'time_remaining': 30,
            'total_phases': 3,
            'current_phase_index': 1,
            'phases': ['Departing', 'Cruising', 'Arriving']
        }
        
        print("🚀 Calling set_travel_info() - Both overlays should update NOW:")
        print("   • Progress overlay: Shows immediately")
        print("   • Status overlay: Switches to 100ms updates")
        
        self.travel_overlay.set_travel_info(travel_info)
        
        # Start progress simulation
        self.progress = 0.0
        self.progress_timer.start(200)  # Update every 200ms
        
    def end_travel(self):
        """Simulate ending travel"""
        self.status_label.setText("Status: Not traveling (1000ms status updates)")
        
        print("🛑 Calling set_travel_info({}) - Both overlays should update NOW:")
        print("   • Progress overlay: Hides immediately")  
        print("   • Status overlay: Switches back to 1000ms updates")
        
        # End travel - empty dict means no travel
        self.travel_overlay.set_travel_info({})
        
        # Stop progress simulation
        self.progress_timer.stop()
        
    def update_progress(self):
        """Update progress simulation"""
        self.progress += 0.05
        if self.progress >= 1.0:
            # Auto-complete travel
            self.end_travel()
            return
            
        travel_info = {
            'phase': 'Cruising',
            'progress': self.progress,
            'time_remaining': int(30 * (1.0 - self.progress)),
            'total_phases': 3,
            'current_phase_index': 1, 
            'phases': ['Departing', 'Cruising', 'Arriving']
        }
        
        self.travel_overlay.set_travel_info(travel_info)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = SimpleTimingTest()
    window.show()
    
    print("🔧 Simple Timing Synchronization Test")
    print("="*50)
    print("Click 'Start Travel' and watch both overlays:")
    print("• Status overlay should switch from 1000ms to 100ms updates")
    print("• Progress overlay should appear immediately")
    print("• Both should be synchronized during travel")
    print("="*50)
    
    sys.exit(app.exec())
