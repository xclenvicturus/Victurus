# /test_planet_landing_dialog.py

"""
Test script for the planet landing dialog system.
This tests the ground control communication sequence and landing procedures.
"""

import sys
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

# Add the project root to path
sys.path.insert(0, '.')

from ui.dialogs.planet_landing_dialog import PlanetLandingDialog, show_planet_landing_dialog
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('test_planet_landing')


class PlanetLandingTestWindow(QWidget):
    """Simple test window for testing planet landing dialogs"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planet Landing Dialog Test")
        self.resize(300, 200)
        
        layout = QVBoxLayout(self)
        
        # Test different planets
        test_planets = [
            ("Kepler-442b", {"type": "terrestrial", "atmosphere": "thick"}),
            ("New Terra Prime", {"type": "colonial", "atmosphere": "breathable"}),
            ("Proxima Centauri b", {"type": "tidally_locked", "atmosphere": "thin"}),
            ("HD 40307 g", {"type": "super_earth", "atmosphere": "dense"}),
        ]
        
        for planet_name, planet_data in test_planets:
            button = QPushButton(f"Land on {planet_name}")
            button.clicked.connect(lambda checked, name=planet_name, data=planet_data: 
                                 self.test_planet_landing(name, data))
            layout.addWidget(button)
    
    def test_planet_landing(self, planet_name: str, planet_data: dict):
        """Test planet landing dialog"""
        logger.info(f"Testing planet landing dialog for {planet_name}")
        
        try:
            # Show the planet landing dialog
            landing_approved = show_planet_landing_dialog(planet_name, planet_data, self)
            
            if landing_approved:
                logger.info(f"Landing approved for {planet_name}")
                print(f"✅ Successfully landed on {planet_name}")
            else:
                logger.info(f"Landing cancelled/denied for {planet_name}")
                print(f"❌ Landing cancelled for {planet_name}")
                
        except Exception as e:
            logger.error(f"Error testing planet landing: {e}")
            print(f"💥 Error testing planet landing: {e}")


def main():
    """Main test function"""
    app = QApplication(sys.argv)
    
    # Set a dark theme for testing
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #555555;
            padding: 8px;
            margin: 2px;
        }
        QPushButton:hover {
            background-color: #505050;
        }
    """)
    
    # Create and show test window
    test_window = PlanetLandingTestWindow()
    test_window.show()
    
    print("🚀 Planet Landing Dialog Test")
    print("Click buttons to test different planet landing scenarios")
    print("Watch for ground control communication sequences")
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
