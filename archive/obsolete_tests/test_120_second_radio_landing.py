# /test_120_second_radio_landing.py

"""
Test the enhanced 120-second planet landing sequence with radio chatter
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QElapsedTimer

# Add the project root to path  
sys.path.insert(0, '.')

def test_120_second_radio_landing():
    """Test the 120-second planet landing sequence with radio chatter"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        
        # Create test dialog
        planet_name = "New Terra Prime"
        planet_data = {"type": "colonial", "atmosphere": "breathable"}
        
        dialog = PlanetLandingDialog(planet_name, planet_data)
        
        # Track timing and messages
        start_timer = QElapsedTimer()
        sequence_started = False
        message_count = 0
        
        # Monitor messages being added
        original_add_message = dialog._add_message
        def track_messages(text, sender, color='#ffffff'):
            nonlocal message_count
            message_count += 1
            elapsed = start_timer.elapsed() / 1000.0 if start_timer.isValid() else 0
            print(f"[{elapsed:5.1f}s] {sender}: {text[:60]}{'...' if len(text) > 60 else ''}")
            return original_add_message(text, sender, color)
        
        dialog._add_message = track_messages
        
        # Connect to signals to track timing
        def on_landing_complete():
            elapsed_ms = start_timer.elapsed()
            elapsed_seconds = elapsed_ms / 1000.0
            print(f"\n🎯 Landing sequence completed!")
            print(f"⏱️  Total elapsed time: {elapsed_seconds:.1f} seconds")
            print(f"🎯 Target was 120 seconds - difference: {elapsed_seconds - 120:.1f}s")
            print(f"📡 Total radio messages: {message_count}")
            print(f"📈 Average messages per minute: {(message_count / elapsed_seconds) * 60:.1f}")
            app.quit()
        
        dialog.landing_approved.connect(on_landing_complete)
        
        # Monitor when landing sequence actually starts
        def check_landing_started():
            if hasattr(dialog, 'landing_phase') and dialog.landing_phase == "landing" and not sequence_started:
                start_timer.start()
                print(f"🚀 Enhanced landing sequence started with radio chatter at: {time.strftime('%H:%M:%S')}")
                print("📡 Radio communications between pilot and ground control:")
                print("-" * 80)
                return True
            return False
        
        # Check periodically for sequence start
        check_timer = QTimer()
        def monitor_sequence():
            global sequence_started
            if check_landing_started():
                sequence_started = True
                check_timer.stop()
        
        check_timer.timeout.connect(monitor_sequence)
        check_timer.start(100)  # Check every 100ms
        
        print(f"🌍 Testing 120-second enhanced landing on {planet_name}")
        print("📡 Features: Ground control communication + Radio chatter during landing")
        print("🚀 Enhanced atmospheric entry with pilot ↔ ground control dialogue")
        print("⏱️  Sequence should take exactly 120 seconds (2 minutes)")
        print("🎭 Multiple voices: Ship Computer, Pilot, Ground Control")
        print()
        
        dialog.show()
        
        # Auto-accept after landing completes (for testing)
        def auto_complete():
            if hasattr(dialog, 'landing_phase') and dialog.landing_phase == "complete":
                print("\n✅ Auto-accepting completed landing dialog")
                dialog.accept()
            else:
                # Check again in 1 second
                QTimer.singleShot(1000, auto_complete)
        
        # Start checking after communication phase
        QTimer.singleShot(12000, auto_complete)  # Start checking after 12 seconds
        
        # Run the application
        app.exec()
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_120_second_radio_landing()
