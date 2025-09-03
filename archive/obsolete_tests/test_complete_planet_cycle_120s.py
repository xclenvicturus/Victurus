# /test_complete_planet_cycle_120s.py

"""
Test complete planet landing and launch cycle with 120-second sequences
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Add the project root to path  
sys.path.insert(0, '.')

def test_complete_planet_cycle():
    """Test both landing and launch sequences back to back"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog
        
        planet_name = "New Terra Prime"
        planet_data = {"type": "colonial", "atmosphere": "breathable"}
        
        print(f"🌍 Testing complete planet operation cycle on {planet_name}")
        print("📡 Features: 120-second sequences with radio chatter")
        print("🛬 Phase 1: Landing sequence (120s)")
        print("🚀 Phase 2: Launch sequence (120s)")
        print("⏱️  Total expected time: ~4 minutes + communication delays")
        print()
        
        # Start with landing dialog
        landing_dialog = PlanetLandingDialog(planet_name, planet_data)
        
        def on_landing_complete():
            print("\n✅ Landing sequence completed!")
            print("⏸️  Brief pause before launch...")
            
            # Brief pause, then show launch dialog
            QTimer.singleShot(2000, show_launch_dialog)
            landing_dialog.accept()
        
        def show_launch_dialog():
            print("\n🚀 Starting launch sequence...")
            launch_dialog = PlanetLaunchDialog(planet_name, planet_data)
            
            def on_launch_complete():
                print("\n✅ Launch sequence completed!")
                print("🎯 Complete planet operation cycle finished!")
                app.quit()
            
            launch_dialog.launch_approved.connect(on_launch_complete)
            launch_dialog.show()
        
        landing_dialog.landing_approved.connect(on_landing_complete)
        landing_dialog.show()
        
        # Run the application
        app.exec()
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_planet_cycle()
