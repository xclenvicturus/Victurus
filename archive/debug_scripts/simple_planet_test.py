# /simple_planet_test.py

"""
Simple test for planet landing dialog without complex dependencies
"""

import sys
from PySide6.QtWidgets import QApplication

# Add the project root to path  
sys.path.insert(0, '.')

def test_planet_dialog():
    """Simple test of planet landing dialog"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        
        # Create test dialog
        planet_name = "Kepler-442b"
        planet_data = {"type": "terrestrial", "atmosphere": "thick"}
        
        dialog = PlanetLandingDialog(planet_name, planet_data)
        dialog.show()
        
        print(f"✅ Created planet landing dialog for {planet_name}")
        print("Ground control communication should start automatically...")
        
        # Run the dialog
        result = dialog.exec()
        
        if result and dialog.landing_phase == "complete":
            print("✅ Landing sequence completed successfully")
        else:
            print("❌ Landing was cancelled or failed")
            
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_planet_dialog()
