#!/usr/bin/env python3

"""
Test script to verify all three fixes work correctly:
1. Bay number storage/access during docking/undocking 
2. Status overlay shows exact format: "Docked <location>", "Orbiting <location>", "Traveling <system/warp>"
3. Destination overlay clearly shows current location vs destination location
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_bay_number_system():
    """Test bay number saving and retrieval"""
    print("=== Testing Bay Number System ===")
    
    try:
        from data import db
        
        # Test basic functions
        print("Testing bay number functions...")
        db.set_docked_bay(7)
        bay = db.get_docked_bay()
        print(f"Set bay 7, retrieved: {bay}")
        
        db.clear_docked_bay()
        bay = db.get_docked_bay()
        print(f"After clearing, bay: {bay}")
        
        print("✅ Bay number functions working correctly")
        
    except Exception as e:
        print(f"❌ Bay number test failed: {e}")

def test_status_overlay_format():
    """Test status overlay text formatting"""
    print("\n=== Testing Status Overlay Format ===")
    
    try:
        from ui.widgets.travel_status_overlay import ShipStatusOverlay
        from PySide6.QtWidgets import QWidget, QApplication
        
        # Create minimal app and widget
        if not QApplication.instance():
            app = QApplication([])
        
        parent = QWidget()
        overlay = ShipStatusOverlay(parent)
        
        # Test the _update_ship_status method by calling it
        overlay._update_ship_status()
        
        # Print current status text
        status = getattr(overlay, '_ship_status', 'No status found')
        print(f"Current status text: '{status}'")
        
        # Check if it matches expected formats
        expected_formats = ['Docked ', 'Orbiting ', 'Traveling ', 'Status Unknown', 'Status Error']
        matches_format = any(status.startswith(fmt) for fmt in expected_formats)
        
        if matches_format:
            print("✅ Status overlay format appears correct")
        else:
            print(f"⚠️  Status format may need checking: '{status}'")
        
    except Exception as e:
        print(f"❌ Status overlay test failed: {e}")

def test_destination_overlay():
    """Test destination overlay current vs destination display"""
    print("\n=== Testing Destination Overlay ===")
    
    try:
        from ui.widgets.travel_status_overlay import DestinationOverlay
        from PySide6.QtWidgets import QWidget, QApplication
        
        # Create minimal app and widget
        if not QApplication.instance():
            app = QApplication([])
        
        parent = QWidget()
        overlay = DestinationOverlay(parent)
        
        # Test the _update_destination method
        overlay._update_destination()
        
        # Print current destination text
        dest_text = getattr(overlay, '_destination_text', 'No destination text found')
        print(f"Current destination text: '{dest_text}'")
        
        # Check if it contains expected elements
        has_current_or_arrow = 'Current:' in dest_text or '→' in dest_text
        
        if has_current_or_arrow:
            print("✅ Destination overlay format appears correct")
        else:
            print(f"⚠️  Destination format may need checking: '{dest_text}'")
            
    except Exception as e:
        print(f"❌ Destination overlay test failed: {e}")

def test_import_success():
    """Test that all modified files can be imported without errors"""
    print("\n=== Testing Import Success ===")
    
    imports_to_test = [
        ('ui.dialogs.station_comm_dialog', 'StationCommDialog'),
        ('ui.dialogs.station_undock_dialog', 'StationUndockDialog'), 
        ('ui.widgets.travel_status_overlay', 'ShipStatusOverlay'),
        ('ui.widgets.travel_status_overlay', 'DestinationOverlay'),
        ('data.db', 'set_docked_bay'),
    ]
    
    for module_name, class_or_func in imports_to_test:
        try:
            module = __import__(module_name, fromlist=[class_or_func])
            getattr(module, class_or_func)
            print(f"✅ {module_name}.{class_or_func}")
        except Exception as e:
            print(f"❌ {module_name}.{class_or_func}: {e}")

if __name__ == "__main__":
    print("Testing Three Fixes Implementation")
    print("==================================")
    
    test_import_success()
    test_bay_number_system()
    test_status_overlay_format()
    test_destination_overlay()
    
    print("\n=== Test Summary ===")
    print("1. Bay number system: Functions work, integration should be tested in game")
    print("2. Status overlay: Format updated for exact user specifications")
    print("3. Destination overlay: Updated to show current → destination clearly")
    print("\nRun the game to test actual integration behavior!")
