# /test_both_landing_launch_proceed_cancel.py

"""
Comprehensive test script for both planet landing and launch dialogs 
with proceed/cancel functionality after radio exchange.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer

from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog


class TestPlanetOperationsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Planet Operations Proceed/Cancel")
        self.setGeometry(100, 100, 400, 300)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Planet Operations Dialog Tests")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Test the proceed/cancel functionality:\n"
            "1. Click a test button below\n"
            "2. Wait for the radio exchange to complete\n"
            "3. Verify proceed/cancel buttons appear\n"
            "4. Test both proceed and cancel options"
        )
        instructions.setStyleSheet("margin-bottom: 20px;")
        layout.addWidget(instructions)
        
        # Test buttons
        button_layout = QHBoxLayout()
        
        landing_button = QPushButton("Test Landing Dialog")
        landing_button.clicked.connect(self.show_landing_dialog)
        landing_button.setStyleSheet("padding: 10px; margin: 5px;")
        button_layout.addWidget(landing_button)
        
        launch_button = QPushButton("Test Launch Dialog")
        launch_button.clicked.connect(self.show_launch_dialog)
        launch_button.setStyleSheet("padding: 10px; margin: 5px;")
        button_layout.addWidget(launch_button)
        
        layout.addLayout(button_layout)
        
        # Status display
        self.status_label = QLabel("Ready to test...")
        self.status_label.setStyleSheet("margin-top: 20px; padding: 10px; background-color: #404040; border-radius: 4px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def show_landing_dialog(self):
        """Show the planet landing dialog for testing"""
        self.status_label.setText("Testing landing dialog... Wait for radio exchange, then check for proceed/cancel buttons.")
        
        dialog = PlanetLandingDialog("Test Planet Alpha", {"name": "Test Planet Alpha"}, self)
        result = dialog.exec()
        
        if result == 1:  # QDialog.Accepted
            self.status_label.setText("✅ Landing dialog completed successfully - Landing sequence finished")
        else:
            self.status_label.setText("❌ Landing dialog cancelled - User chose to cancel landing")
    
    def show_launch_dialog(self):
        """Show the planet launch dialog for testing"""
        self.status_label.setText("Testing launch dialog... Wait for radio exchange, then check for proceed/cancel buttons.")
        
        dialog = PlanetLaunchDialog("Test Planet Beta", {"name": "Test Planet Beta"}, self)
        result = dialog.exec()
        
        if result == 1:  # QDialog.Accepted
            self.status_label.setText("✅ Launch dialog completed successfully - Launch sequence finished")
        else:
            self.status_label.setText("❌ Launch dialog cancelled - User chose to cancel launch")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set up styling to match the game
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
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #505050;
        }
        QLabel {
            color: #ffffff;
        }
    """)
    
    window = TestPlanetOperationsWindow()
    window.show()
    
    sys.exit(app.exec())
