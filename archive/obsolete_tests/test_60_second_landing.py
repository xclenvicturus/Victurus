# /test_60_second_landing.py

"""
Test the 60-second planet landing sequence timing
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QElapsedTimer

# Add the project root to path  
sys.path.insert(0, '.')

def test_60_second_landing():
    """Test the 60-second planet landing sequence"""
    app = QApplication(sys.argv)
    
    try:
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        
        # Create test dialog
        planet_name = "Kepler-442b Enhanced"
        planet_data = {"type": "terrestrial", "atmosphere": "thick"}
        
        dialog = PlanetLandingDialog(planet_name, planet_data)
        
        # Track timing
        start_timer = QElapsedTimer()
        sequence_started = False
        
        # Connect to signals to track timing
        def on_landing_complete():
            elapsed_ms = start_timer.elapsed()
            elapsed_seconds = elapsed_ms / 1000.0
            print(f"🎯 Landing sequence completed!")
            print(f"⏱️  Total elapsed time: {elapsed_seconds:.1f} seconds")
            print(f"🎯 Target was 60 seconds - difference: {elapsed_seconds - 60:.1f}s")
            app.quit()
        
        dialog.landing_approved.connect(on_landing_complete)
        
        # Monitor when landing sequence actually starts
        def check_landing_started():
            if hasattr(dialog, 'landing_phase') and dialog.landing_phase == "landing" and not sequence_started:
                start_timer.start()
                print(f"🚀 Landing sequence started at: {time.strftime('%H:%M:%S')}")
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
        
        print(f"🌍 Testing 60-second landing sequence on {planet_name}")
        print("📡 Ground control communication will start first...")
        print("🚀 Then atmospheric entry sequence (should take exactly 60 seconds)")
        print("⏱️  Timer will start when landing progress begins")
        print()
        
        dialog.show()
        
        # Auto-accept after landing completes (for testing)
        def auto_complete():
            if hasattr(dialog, 'landing_phase') and dialog.landing_phase == "complete":
                print("✅ Auto-accepting completed landing dialog")
                dialog.accept()
            else:
                # Check again in 1 second
                QTimer.singleShot(1000, auto_complete)
        
        # Start checking after communication phase
        QTimer.singleShot(10000, auto_complete)  # Start checking after 10 seconds
        
        # Run the application
        app.exec()
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_60_second_landing()
