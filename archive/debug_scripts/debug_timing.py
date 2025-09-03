#!/usr/bin/env python3

"""
Debug the bay number timing issue by simulating the exact docking/undocking sequence
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_exact_sequence():
    """Test the exact sequence that happens during dock/undock"""
    print("=== Testing Exact Dock/Undock Sequence ===")
    
    try:
        from data import db
        
        # Start clean
        db.clear_docked_bay()
        print("1. Started with clean state (no bay number)")
        
        # Simulate docking - set bay number like the dialog would
        test_bay = 8
        db.set_docked_bay(test_bay)
        print(f"2. Simulated docking - saved bay number {test_bay}")
        
        # Verify bay is saved
        saved_bay = db.get_docked_bay()
        print(f"3. Verified bay saved: {saved_bay}")
        
        # Now simulate the critical moment - undocking dialog opens
        print("4. Simulating undocking dialog opening...")
        
        # This is what _get_docked_bay() does in the undocking dialog
        try:
            bay_number = db.get_docked_bay()
            bay_text = str(bay_number) if bay_number is not None else "Unknown"
            print(f"   _get_docked_bay() would return: '{bay_text}'")
            
            if bay_text != "Unknown":
                print(f"   ✅ SUCCESS: Bay number {bay_text} would be shown in message")
                
                # Simulate the message that would be generated
                test_message = f"Station Control, this is Controller. We show you docked at Bay {bay_text}. State your departure intentions."
                print(f"   Generated message: '{test_message}'")
                
            else:
                print(f"   ❌ FAILURE: Bay shows as 'Unknown'")
                return False
                
        except Exception as e:
            print(f"   ❌ ERROR in bay retrieval: {e}")
            return False
        
        # Simulate completion of undocking (this should clear bay)
        print("5. Simulating undocking completion (clearing bay)...")
        db.clear_docked_bay()
        
        # Verify bay is cleared
        final_bay = db.get_docked_bay() 
        print(f"6. After undocking, bay number: {final_bay}")
        
        if final_bay is None:
            print("   ✅ Bay correctly cleared after undocking")
        else:
            print(f"   ⚠️  Bay not cleared: {final_bay}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_current_game_state():
    """Test what the current game state shows"""
    print("\n=== Testing Current Game State ===")
    
    try:
        from data import db
        from game import player_status
        
        # Check current status
        status = player_status.get_status_snapshot()
        current_status = status.get('status', 'Unknown') if status else 'Unknown'
        current_bay = db.get_docked_bay()
        
        print(f"Current player status: {current_status}")
        print(f"Current bay number: {current_bay}")
        
        if current_status == 'Docked':
            print("Player is currently docked!")
            if current_bay is not None:
                print(f"✅ Bay number {current_bay} is available - undocking should work correctly")
                
                # Test what undocking dialog would see
                bay_text = str(current_bay) if current_bay is not None else "Unknown"
                message = f"We show you docked at Bay {bay_text}."
                print(f"Undocking message would be: '{message}'")
                
            else:
                print("❌ Player is docked but no bay number - this is the problem!")
        elif current_status == 'Orbiting':
            print("Player is orbiting (not docked) - need to dock first to test bay numbers")
        else:
            print(f"Player status is {current_status}")
        
    except Exception as e:
        print(f"❌ Current state test failed: {e}")

if __name__ == "__main__":
    print("Bay Number Timing Debug")
    print("======================")
    
    success = test_exact_sequence()
    test_current_game_state()
    
    print("\n=== Analysis ===")
    if success:
        print("✅ The sequence logic is sound - bay numbers should work")
        print("The issue might be:")
        print("1. Bay number isn't being saved during actual docking")
        print("2. Bay number is being cleared before undocking dialog opens")
        print("3. There's some other timing issue in the real game flow")
    else:
        print("❌ There's a fundamental issue with the sequence")
    
    print("\nNext: Test in real game by docking at a station")
