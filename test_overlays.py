# Test script for new overlay system
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import QTimer

from ui.widgets.travel_status_overlay import ShipStatusOverlay, TravelProgressOverlay

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Test button
        self.test_btn = QPushButton("Test Travel Progress")
        self.test_btn.clicked.connect(self.test_progress)
        layout.addWidget(self.test_btn)
        
        # Create overlays
        self.status_overlay = ShipStatusOverlay(central)
        self.progress_overlay = TravelProgressOverlay(central)
        
        # Show status overlay
        self.status_overlay.show()
        
        # Test progress data
        self.test_travel_info = {
            'phase': 'Cruising to destination',
            'progress': 0.0,
            'time_remaining': 30,
            'total_phases': 4,
            'current_phase_index': 2,
            'phases': ['Departing', 'Entering warp', 'Warping', 'Arriving']
        }
        
    def test_progress(self):
        """Test the progress overlay"""
        self.progress_overlay.set_travel_info(self.test_travel_info)
        
        # Simulate progress
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(100)  # Update every 100ms
        
    def update_progress(self):
        """Update progress for testing"""
        progress = self.test_travel_info.get('progress', 0.0)
        progress += 0.01  # Increment by 1%
        
        if progress >= 1.0:
            # End travel
            self.progress_timer.stop()
            self.progress_overlay.set_travel_info({})  # Clear travel info
        else:
            self.test_travel_info['progress'] = progress
            self.test_travel_info['time_remaining'] = int(30 * (1.0 - progress))
            self.progress_overlay.set_travel_info(self.test_travel_info)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())
