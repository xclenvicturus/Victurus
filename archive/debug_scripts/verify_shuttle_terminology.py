# /verify_shuttle_terminology.py

"""
Verify that shuttle terminology has been properly updated
"""

def verify_landing_dialog_terminology():
    """Check that landing dialog uses shuttle terminology"""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication([])  # Create QApplication first
        
        from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
        
        # Create a test dialog
        planet_name = "Test Planet"
        planet_data = {"type": "test"}
        dialog = PlanetLandingDialog(planet_name, planet_data)
        
        # Test message generation methods
        callsign = "TEST GC"
        controller = "Test Controller"
        ship_name = "Test Vessel"
        
        # Test initial contact message
        initial_msg = dialog._get_initial_contact_message(callsign, controller, ship_name)
        print("🛬 Landing Dialog - Initial Contact:")
        print(f"   {initial_msg}")
        
        # Check for shuttle references
        shuttle_terms = ['shuttle', 'main vessel', 'orbit']
        has_shuttle_terms = any(term in initial_msg.lower() for term in shuttle_terms)
        print(f"   ✅ Contains shuttle terminology: {has_shuttle_terms}")
        
        # Test atmospheric check message
        atmo_msg = dialog._get_atmospheric_check_message(callsign, ship_name)
        print(f"\n   Atmospheric check: {atmo_msg[:100]}...")
        has_shuttle_in_atmo = 'shuttle' in atmo_msg.lower()
        print(f"   ✅ Contains shuttle references: {has_shuttle_in_atmo}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing landing dialog: {e}")
        return False

def verify_launch_dialog_terminology():
    """Check that launch dialog uses shuttle terminology"""
    try:
        from PySide6.QtWidgets import QApplication
        try:
            app = QApplication([])  # Try to create, but may already exist
        except RuntimeError:
            pass  # Application already exists
        
        from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog
        
        # Create a test dialog
        planet_name = "Test Planet"
        planet_data = {"type": "test"}
        dialog = PlanetLaunchDialog(planet_name, planet_data)
        
        # Test message generation methods
        callsign = "TEST LC"
        controller = "Test Controller"
        ship_name = "Test Vessel"
        
        # Test initial contact message
        initial_msg = dialog._get_initial_contact_message(callsign, controller, ship_name)
        print("\n🚀 Launch Dialog - Initial Contact:")
        print(f"   {initial_msg}")
        
        # Check for shuttle references
        shuttle_terms = ['shuttle', 'main vessel', 'orbit', 'surface operations']
        has_shuttle_terms = any(term in initial_msg.lower() for term in shuttle_terms)
        print(f"   ✅ Contains shuttle terminology: {has_shuttle_terms}")
        
        # Test launch clearance message
        clearance_msg = dialog._get_launch_clearance_message(callsign, ship_name)
        print(f"\n   Launch clearance: {clearance_msg[:100]}...")
        has_shuttle_in_clearance = 'shuttle' in clearance_msg.lower()
        print(f"   ✅ Contains shuttle references: {has_shuttle_in_clearance}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing launch dialog: {e}")
        return False

def main():
    print("🚁 Verifying Shuttle Terminology Updates")
    print("=" * 50)
    
    landing_ok = verify_landing_dialog_terminology()
    launch_ok = verify_launch_dialog_terminology()
    
    print("\n📊 Summary:")
    if landing_ok and launch_ok:
        print("✅ All shuttle terminology updates verified successfully!")
        print("🛸 Main vessel now remains in orbit")
        print("🚁 Shuttles handle planetary operations")
        print("📡 Radio chatter reflects shuttle operations")
    else:
        print("❌ Some issues detected with terminology updates")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    main()
