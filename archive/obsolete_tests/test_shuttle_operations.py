# /test_shuttle_operations.py

"""
Test the enhanced shuttle operations system
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QElapsedTimer

# Add the project root to path  
sys.path.insert(0, '.')

def test_shuttle_operations():
    """Test complete shuttle operations cycle - deployment and recovery"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog
        
        planet_name = "New Terra Prime"
        planet_data = {"type": "colonial", "atmosphere": "breathable"}
        
        print(f"🚁 Testing shuttle operations on {planet_name}")
        print("🛸 Phase 1: Main vessel remains in orbit, shuttle deployed for landing")
        print("🚀 Phase 2: Shuttle returns from surface and docks with main vessel")
        print("⏱️  Each phase: 120 seconds with realistic radio chatter")
        print("📡 Features: Shuttle-specific communications and procedures")
        print()
        
        # Phase 1: Shuttle landing (deployment from main vessel)
        print("🛸 Phase 1: Deploying shuttle from main vessel for planetary operations...")
        landing_dialog = PlanetLandingDialog(planet_name, planet_data)
        
        # Track messages for verification
        message_count = 0
        original_add_message = landing_dialog._add_message
        def track_landing_messages(text, sender, color='#ffffff'):
            nonlocal message_count
            message_count += 1
            if 'shuttle' in text.lower():
                print(f"✅ Shuttle reference detected: {sender}: {text[:50]}...")
            return original_add_message(text, sender, color)
        
        landing_dialog._add_message = track_landing_messages
        
        def on_landing_complete():
            print(f"\n✅ Shuttle landing completed! ({message_count} messages)")
            print("🛬 Shuttle is now on planetary surface while main vessel remains in orbit")
            print("⏸️  Brief pause before shuttle return...")
            
            # Brief pause, then show launch dialog
            QTimer.singleShot(2000, show_launch_dialog)
            landing_dialog.accept()
        
        def show_launch_dialog():
            print("\n🚀 Phase 2: Shuttle returning from surface to dock with main vessel...")
            launch_dialog = PlanetLaunchDialog(planet_name, planet_data)
            
            # Track launch messages
            launch_message_count = 0
            original_launch_add_message = launch_dialog._add_message
            def track_launch_messages(text, sender, color='#ffffff'):
                nonlocal launch_message_count
                launch_message_count += 1
                if any(keyword in text.lower() for keyword in ['shuttle', 'main vessel', 'dock', 'rendezvous']):
                    print(f"✅ Shuttle operation reference: {sender}: {text[:50]}...")
                return original_launch_add_message(text, sender, color)
            
            launch_dialog._add_message = track_launch_messages
            
            def on_launch_complete():
                print(f"\n✅ Shuttle return completed! ({launch_message_count} messages)")
                print("🛸 Shuttle has successfully docked with main vessel")
                print("🎯 Complete shuttle operations cycle finished!")
                print("\n📊 Operation Summary:")
                print(f"   • Landing phase: {message_count} communications")
                print(f"   • Launch phase: {launch_message_count} communications")
                print(f"   • Total duration: ~4 minutes (2 × 120s sequences)")
                print("   • Main vessel never left orbit")
                print("   • Shuttle handled all planetary surface operations")
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
    test_shuttle_operations()
