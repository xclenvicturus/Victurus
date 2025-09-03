# /test_planet_communications.py

"""
Comprehensive test for both planet landing and launch communication dialogs.
This demonstrates the complete planetary surface operations workflow.
"""

import sys
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLabel

# Add the project root to path
sys.path.insert(0, '.')

from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('test_planet_comms')


class PlanetCommunicationsTestWindow(QWidget):
    """Test window for both landing and launch communication sequences"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planet Communications System Test")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🚀 Planet Communications System Test")
        title.setStyleSheet("font-size: 16px; font-weight: bold; text-align: center; margin: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Test the complete planetary surface operations workflow:\n"
            "1. Request landing clearance from Ground Control\n"
            "2. Experience atmospheric entry and landing sequence\n"
            "3. Request launch clearance from Launch Control\n"
            "4. Experience orbital insertion and departure sequence"
        )
        instructions.setStyleSheet("color: #888; margin: 10px; line-height: 20px;")
        layout.addWidget(instructions)
        
        # Test planets with different characteristics
        test_planets = [
            ("New Terra Prime", {"type": "colonial", "atmosphere": "breathable"}),
            ("Kepler-442b", {"type": "terrestrial", "atmosphere": "thick"}),
            ("Proxima Centauri b", {"type": "tidally_locked", "atmosphere": "thin"}),
            ("HD 40307 g", {"type": "super_earth", "atmosphere": "dense"}),
            ("Ross 128 b", {"type": "temperate", "atmosphere": "moderate"}),
        ]
        
        for planet_name, planet_data in test_planets:
            planet_layout = QHBoxLayout()
            
            planet_label = QLabel(f"{planet_name}:")
            planet_label.setMinimumWidth(150)
            planet_label.setStyleSheet("font-weight: bold;")
            
            land_button = QPushButton("🌍 Land")
            land_button.clicked.connect(lambda checked, name=planet_name, data=planet_data: 
                                      self.test_landing_sequence(name, data))
            
            launch_button = QPushButton("🚀 Launch")
            launch_button.clicked.connect(lambda checked, name=planet_name, data=planet_data: 
                                        self.test_launch_sequence(name, data))
            
            both_button = QPushButton("🔄 Full Cycle")
            both_button.clicked.connect(lambda checked, name=planet_name, data=planet_data: 
                                      self.test_full_cycle(name, data))
            
            planet_layout.addWidget(planet_label)
            planet_layout.addWidget(land_button)
            planet_layout.addWidget(launch_button)
            planet_layout.addWidget(both_button)
            
            layout.addLayout(planet_layout)
    
    def test_landing_sequence(self, planet_name: str, planet_data: dict):
        """Test just the landing communication sequence"""
        logger.info(f"Testing landing sequence for {planet_name}")
        print(f"\n🌍 Testing landing on {planet_name}...")
        
        try:
            dialog = PlanetLandingDialog(planet_name, planet_data, self)
            result = dialog.exec()
            
            if result and dialog.landing_phase == "complete":
                print(f"✅ Successfully landed on {planet_name}")
            else:
                print(f"❌ Landing cancelled for {planet_name}")
                
        except Exception as e:
            logger.error(f"Error testing landing: {e}")
            print(f"💥 Error testing landing: {e}")
    
    def test_launch_sequence(self, planet_name: str, planet_data: dict):
        """Test just the launch communication sequence"""
        logger.info(f"Testing launch sequence for {planet_name}")
        print(f"\n🚀 Testing launch from {planet_name}...")
        
        try:
            dialog = PlanetLaunchDialog(planet_name, planet_data, self)
            result = dialog.exec()
            
            if result and dialog.launch_phase == "complete":
                print(f"✅ Successfully launched from {planet_name}")
            else:
                print(f"❌ Launch cancelled for {planet_name}")
                
        except Exception as e:
            logger.error(f"Error testing launch: {e}")
            print(f"💥 Error testing launch: {e}")
    
    def test_full_cycle(self, planet_name: str, planet_data: dict):
        """Test the complete landing -> launch cycle"""
        logger.info(f"Testing full cycle for {planet_name}")
        print(f"\n🔄 Testing full cycle for {planet_name}...")
        
        # First do landing
        try:
            print(f"Phase 1: Landing on {planet_name}")
            landing_dialog = PlanetLandingDialog(planet_name, planet_data, self)
            landing_result = landing_dialog.exec()
            
            if landing_result and landing_dialog.landing_phase == "complete":
                print(f"✅ Landing phase complete")
                
                # Brief pause between operations
                import time
                time.sleep(1)
                
                # Now do launch
                print(f"Phase 2: Launching from {planet_name}")
                launch_dialog = PlanetLaunchDialog(planet_name, planet_data, self)
                launch_result = launch_dialog.exec()
                
                if launch_result and launch_dialog.launch_phase == "complete":
                    print(f"✅ Full cycle complete for {planet_name}")
                    print("🎯 Planetary surface operations workflow successful!")
                else:
                    print(f"❌ Launch phase cancelled")
            else:
                print(f"❌ Landing phase cancelled")
                
        except Exception as e:
            logger.error(f"Error testing full cycle: {e}")
            print(f"💥 Error testing full cycle: {e}")


def main():
    """Main test function"""
    app = QApplication(sys.argv)
    
    # Set a space-themed dark style
    app.setStyleSheet("""
        QWidget {
            background-color: #1a1a2e;
            color: #ffffff;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QLabel {
            padding: 4px;
        }
        QPushButton {
            background-color: #16213e;
            border: 2px solid #0f3460;
            border-radius: 6px;
            padding: 8px 12px;
            margin: 2px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #0f3460;
            border-color: #e94560;
        }
        QPushButton:pressed {
            background-color: #0a2647;
        }
    """)
    
    # Create and show test window
    test_window = PlanetCommunicationsTestWindow()
    test_window.show()
    
    print("🌌 Planet Communications System Test")
    print("====================================")
    print("This tests the complete planetary operations workflow:")
    print("• Ground Control landing communication")
    print("• Atmospheric entry and landing sequences")
    print("• Launch Control departure communication") 
    print("• Orbital insertion and launch sequences")
    print()
    print("Choose a planet and test scenario from the UI")
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
