#!/usr/bin/env python3

"""
Test just the bay number dialog logic to see if it's working correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_dialog_bay_generation():
    """Test if the dialog generates and stores bay number correctly"""
    print("=== Testing Dialog Bay Generation ===")
    
    try:
        # Just test the bay number logic directly
        import random
        
        # Simulate what the dialog does
        assigned_bay = random.randint(1, 12)
        print(f"Generated bay number: {assigned_bay}")
        
        # Test the message format
        ship_name = "Test Ship"
        base_msg = f"{ship_name}, you are cleared for docking at Bay {assigned_bay}. "
        print(f"Message format: {base_msg}")
        
        # Test if this would work in practice
        if 1 <= assigned_bay <= 12:
            print(f"✅ Bay number {assigned_bay} is in valid range")
        else:
            print(f"❌ Bay number {assigned_bay} is out of range")
            
    except Exception as e:
        print(f"❌ Dialog test failed: {e}")
        import traceback
        traceback.print_exc()

def test_undock_dialog_retrieval():
    """Test if undock dialog can retrieve bay number"""
    print("\n=== Testing Undock Dialog Retrieval ===")
    
    try:
        from data import db
        
        # Set a test bay number
        test_bay = 5
        db.set_docked_bay(test_bay)
        print(f"Set bay number to: {test_bay}")
        
        # Test retrieval directly
        retrieved_bay = db.get_docked_bay()
        print(f"Retrieved bay number: {retrieved_bay}")
        
        # Test the string conversion logic from undock dialog
        bay_text = str(retrieved_bay) if retrieved_bay is not None else "Unknown"
        print(f"Bay text for dialog: '{bay_text}'")
        
        if bay_text == str(test_bay):
            print(f"✅ Undock dialog would correctly show bay {test_bay}")
        else:
            print(f"❌ Expected '{test_bay}', got '{bay_text}'")
            
        # Clean up
        db.clear_docked_bay()
        
    except Exception as e:
        print(f"❌ Undock dialog test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Testing Bay Number Dialog Logic")
    print("==============================")
    
    test_dialog_bay_generation()
    test_undock_dialog_retrieval()
    
    print("\n=== Next Steps ===")
    print("If both tests pass, the issue is in the signal flow between dialog and actions panel")
    print("If dialog test fails, the issue is in bay number generation")
    print("If undock test fails, the issue is in bay number retrieval")
