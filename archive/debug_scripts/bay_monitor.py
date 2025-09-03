#!/usr/bin/env python3

"""
Bay Number Monitor - Run this while testing docking/undocking in the game
to see if bay numbers are being saved and retrieved correctly
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def monitor_bay_status():
    """Monitor bay number and player status in real-time"""
    print("Bay Number Monitor - Press Ctrl+C to stop")
    print("=========================================")
    print("Monitor the bay number while you dock and undock in the game")
    print()
    
    try:
        from data import db
        from game import player_status
        
        previous_status = None
        previous_bay = None
        
        while True:
            try:
                # Get current status
                status = player_status.get_status_snapshot()
                current_status = status.get('status', 'Unknown') if status else 'Unknown'
                current_bay = db.get_docked_bay()
                
                # Only print when something changes
                if current_status != previous_status or current_bay != previous_bay:
                    timestamp = time.strftime('%H:%M:%S')
                    print(f"[{timestamp}] Status: {current_status:10} | Bay: {current_bay}")
                    
                    if current_status == 'Docked' and current_bay is not None:
                        print(f"           ✅ DOCKED with bay number {current_bay} saved!")
                    elif current_status == 'Docked' and current_bay is None:
                        print(f"           ❌ DOCKED but no bay number saved!")
                    elif current_status == 'Orbiting' and previous_status == 'Docked':
                        if previous_bay is not None:
                            print(f"           📡 UNDOCKED - previous bay was {previous_bay}")
                        else:
                            print(f"           📡 UNDOCKED - no bay number was available")
                    
                    previous_status = current_status
                    previous_bay = current_bay
                
                time.sleep(1)  # Check every second
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error during monitoring: {e}")
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except Exception as e:
        print(f"Monitor failed: {e}")

if __name__ == "__main__":
    print("🔍 Bay Number Real-Time Monitor")
    print("Instructions:")
    print("1. Start this monitor")
    print("2. In the game, dock at a station") 
    print("3. Look for '✅ DOCKED with bay number X saved!'")
    print("4. Undock from the station")
    print("5. Check if bay number was preserved")
    print()
    
    monitor_bay_status()
