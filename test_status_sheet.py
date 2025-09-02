# /test_status_sheet.py

"""
Test Status Sheet Widget

Quick test to verify the status sheet still works after removing ship status display.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ui.widgets.status_sheet import StatusSheet

class TestStatusSheet(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Status Sheet Test (Ship Status Removed)")
        self.setGeometry(100, 100, 400, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Create status sheet
        self.status_sheet = StatusSheet()
        layout.addWidget(self.status_sheet)
        
        # Refresh periodically to show it works
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.status_sheet.refresh)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = TestStatusSheet()
    window.show()
    
    print("🧪 Status Sheet Test")
    print("="*40)
    print("Testing status sheet with ship status display removed")
    print("Should show:")
    print("• Player Name")
    print("• Location") 
    print("• Credits")
    print("• Active Ship")
    print("• Jump Range")
    print("• Hull/Shield/Fuel/Energy/Cargo gauges")
    print()
    print("Should NOT show:")
    print("• Ship Status (removed)")
    print("="*40)
    
    sys.exit(app.exec())
