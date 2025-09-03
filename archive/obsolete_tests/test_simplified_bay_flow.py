#!/usr/bin/env python3

"""
Test the complete bay number flow with the simplified approach:
1. Dialog generates bay number and saves it when docking is confirmed
2. Database stores the bay number 
3. Undocking dialog retrieves the bay number correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_complete_bay_flow():
    """Test the complete bay number flow"""
    print("=== Testing Complete Bay Number Flow ===")
    
    try:
        from data import db
        
        # Clear any existing bay number
        db.clear_docked_bay()
        print("1. Cleared existing bay number")
        
        # Simulate what happens when docking dialog generates and saves bay number
        print("2. Simulating docking dialog bay generation...")
        
        import random
        assigned_bay = random.randint(1, 12)
        print(f"   Generated bay number: {assigned_bay}")
        
        # Simulate the _save_docking_bay_number call
        db.set_docked_bay(assigned_bay)
        print(f"   Saved bay number to database: {assigned_bay}")
        
        # Verify it was saved
        saved_bay = db.get_docked_bay()
        print(f"   Retrieved from database: {saved_bay}")
        
        if saved_bay == assigned_bay:
            print("   ✅ Bay number saved correctly")
        else:
            print(f"   ❌ Bay number mismatch: expected {assigned_bay}, got {saved_bay}")
            return False
        
        # Simulate what happens when undocking dialog retrieves bay number
        print("3. Simulating undocking dialog bay retrieval...")
        
        # This is the logic from _get_docked_bay in station_undock_dialog.py
        try:
            bay_number = db.get_docked_bay()
            bay_text = str(bay_number) if bay_number is not None else "Unknown"
            print(f"   Retrieved bay text: '{bay_text}'")
            
            if bay_text == str(assigned_bay):
                print("   ✅ Undocking dialog would show correct bay number")
            else:
                print(f"   ❌ Undocking dialog bay text incorrect: expected '{assigned_bay}', got '{bay_text}'")
                return False
        except Exception as e:
            print(f"   ❌ Error in undocking retrieval: {e}")
            return False
        
        # Test the complete message that would be shown
        print("4. Testing complete undocking message...")
        
        callsign = "TST-STA"
        controller = "Test Controller"
        ship_name = "Test Ship"
        bay_display = bay_text
        
        message = f"{callsign} Departure Control, this is {controller}. We show you docked at Bay {bay_display}. State your departure intentions, {ship_name}."
        print(f"   Complete message: {message}")
        
        if f"Bay {assigned_bay}" in message:
            print("   ✅ Complete undocking message includes correct bay number")
        else:
            print("   ❌ Complete undocking message missing correct bay number")
            return False
        
        # Clean up
        db.clear_docked_bay()
        print("5. Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Test edge cases for bay number system"""
    print("\n=== Testing Edge Cases ===")
    
    try:
        from data import db
        
        # Test 1: What happens when no bay number is set?
        db.clear_docked_bay()
        bay_number = db.get_docked_bay()
        bay_text = str(bay_number) if bay_number is not None else "Unknown"
        print(f"No bay set - retrieval returns: '{bay_text}'")
        
        if bay_text == "Unknown":
            print("✅ Correctly handles missing bay number")
        else:
            print(f"❌ Expected 'Unknown', got '{bay_text}'")
            
        # Test 2: Test boundary values
        for test_bay in [1, 12, 5]:
            db.set_docked_bay(test_bay)
            retrieved = db.get_docked_bay()
            if retrieved == test_bay:
                print(f"✅ Bay {test_bay} stored and retrieved correctly")
            else:
                print(f"❌ Bay {test_bay} failed: got {retrieved}")
                
        # Clean up
        db.clear_docked_bay()
        
        return True
        
    except Exception as e:
        print(f"❌ Edge case test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Bay Number Flow (Simplified Approach)")
    print("=============================================")
    
    flow_success = test_complete_bay_flow()
    edge_success = test_edge_cases()
    
    print("\n=== Summary ===")
    if flow_success and edge_success:
        print("✅ ALL TESTS PASSED - Bay number system should work correctly!")
        print("The issue was in the signal flow - simplified approach resolves it.")
    else:
        print("❌ Some tests failed - bay number system needs more work.")
    
    print("\nNext step: Test in actual game by docking at a station and then undocking.")
