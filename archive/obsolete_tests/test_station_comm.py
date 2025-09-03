# Test script for Station Communication Dialog
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from ui.dialogs.station_comm_dialog import StationCommDialog

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Station Communication Test")
        self.resize(400, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        label = QLabel("Test Station Communication Dialog")
        layout.addWidget(label)
        
        # Test with sample station data
        test_button = QPushButton("Test Docking Communication")
        test_button.clicked.connect(self.test_communication)
        layout.addWidget(test_button)
        
        self.result_label = QLabel("Click button to test...")
        layout.addWidget(self.result_label)
        
    def test_communication(self):
        """Test the station communication dialog"""
        sample_station_data = {
            'location_id': 123,
            'facilities': [
                {'type': 'Fuel', 'notes': 'High-grade starship fuel'},
                {'type': 'Repair', 'notes': 'Hull and systems maintenance'},
                {'type': 'Market', 'notes': 'Commodity trading hub'},
                {'type': 'Missions', 'notes': 'Mission board available'}
            ]
        }
        
        dialog = StationCommDialog("Frontier Station Alpha", sample_station_data, self)
        dialog.docking_approved.connect(lambda: self.result_label.setText("✅ Docking Approved!"))
        dialog.docking_denied.connect(lambda reason: self.result_label.setText(f"❌ Docking Denied: {reason}"))
        dialog.communication_complete.connect(lambda: print("Communication sequence complete"))
        
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("Station Communication Dialog Test")
    print("Click the button to test the docking sequence")
    
    app.exec()
