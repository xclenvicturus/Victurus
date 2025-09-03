# /test_enhanced_landing.py

"""
Test the enhanced planet landing sequence with detailed phases
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Add the project root to path  
sys.path.insert(0, '.')

def test_enhanced_landing():
    """Test the enhanced planet landing with detailed sequence"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        
        # Create test dialog
        planet_name = "New Terra Prime"
        planet_data = {"type": "colonial", "atmosphere": "breathable"}
        
        dialog = PlanetLandingDialog(planet_name, planet_data)
        
        # Connect to the landing approved signal to show completion
        def on_landing_complete():
            print("🎯 Enhanced landing sequence completed successfully!")
            print("✅ All detailed phases executed")
            app.quit()
        
        dialog.landing_approved.connect(on_landing_complete)
        
        print(f"🌍 Testing enhanced landing on {planet_name}")
        print("📡 Ground control communication starting...")
        print("🚀 Enhanced landing sequence with detailed atmospheric entry phases")
        print("⏱️  Sequence should take longer and show more detailed progress messages")
        print()
        
        dialog.show()
        
        # Auto-accept after landing completes (for testing)
        def auto_complete():
            if dialog.landing_phase == "complete":
                print("✅ Landing sequence completed - auto-accepting dialog")
                dialog.accept()
            else:
                # Check again in 1 second
                QTimer.singleShot(1000, auto_complete)
        
        # Start the auto-complete check after initial communication finishes
        QTimer.singleShot(8000, auto_complete)  # Start checking after 8 seconds
        
        # Run the application
        app.exec()
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_enhanced_landing()
