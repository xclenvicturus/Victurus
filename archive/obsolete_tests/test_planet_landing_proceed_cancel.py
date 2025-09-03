# /test_planet_landing_proceed_cancel.py

"""
Test script for the planet landing dialog proceed/cancel functionality.
Verifies that the dialog shows proceed/cancel buttons after radio exchange.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PySide6.QtCore import QTimer

from ui.dialogs.planet_landing_dialog import PlanetLandingDialog


class TestLandingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Planet Landing Proceed/Cancel")
        self.setGeometry(100, 100, 300, 200)
        
        layout = QVBoxLayout()
        
        # Test button
        test_button = QPushButton("Test Landing Dialog")
        test_button.clicked.connect(self.show_landing_dialog)
        layout.addWidget(test_button)
        
        self.setLayout(layout)
    
    def show_landing_dialog(self):
        """Show the planet landing dialog for testing"""
        dialog = PlanetLandingDialog("Test Planet", {"name": "Test Planet"}, self)
        result = dialog.exec()
        print(f"Dialog result: {result}")
        if result == 1:  # QDialog.Accepted
            print("Landing was completed successfully")
        else:
            print("Landing was cancelled")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set up basic styling
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: Arial, sans-serif;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #666;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #505050;
        }
    """)
    
    window = TestLandingWindow()
    window.show()
    
    sys.exit(app.exec())
