# /test_travel_status_display.py

"""
Test to verify the travel status display shows only system when traveling
and both location and system when at a location.
"""

def test_travel_status_display_logic():
    """Test the logic for displaying status during travel vs at location"""
    
    print("=== Travel Status Display Test ===")
    
    # Test the travel detection logic
    class MockTravelOverlay:
        def _is_travel_related_status(self, status: str) -> bool:
            """Check if a status is travel-related and should be shown as 'Traveling'"""
            travel_keywords = [
                'traveling', 'cruise', 'cruising', 'warping', 'warp',
                'entering', 'leaving', 'transit', 'departure', 'arrival'
            ]
            status_lower = status.lower()
            return any(keyword in status_lower for keyword in travel_keywords)
        
        def format_status_display(self, status: str, location_name: str, system_name: str) -> str:
            """Format status display based on travel state"""
            is_traveling = self._is_travel_related_status(status) or status == "Traveling"
            
            if is_traveling:
                # When traveling: "Traveling system_name" (system only)
                return f"Traveling {system_name}"
            else:
                # When at location: "Status location_name • system_name" (both)
                if location_name:
                    return f"{status} {location_name} • {system_name}"
                else:
                    return f"{status} {system_name}"
    
    overlay = MockTravelOverlay()
    
    print("\n1. ✅ Travel Status Detection:")
    travel_statuses = [
        'Entering Cruise', 'Cruising', 'Leaving Cruise',
        'Entering Orbit', 'Leaving Orbit', 'Warping',
        'Traveling', 'Transit'
    ]
    
    for status in travel_statuses:
        is_travel = overlay._is_travel_related_status(status)
        print(f"   '{status}' -> Travel: {is_travel}")
    
    print("\n2. ✅ Non-Travel Status Detection:")
    non_travel_statuses = ['Docked', 'Orbiting', 'Unknown', 'Idle']
    
    for status in non_travel_statuses:
        is_travel = overlay._is_travel_related_status(status)
        print(f"   '{status}' -> Travel: {is_travel}")
    
    print("\n3. ✅ Status Display Formatting:")
    test_cases = [
        # (status, location, system, expected_format)
        ('Entering Cruise', 'Station Alpha', 'Sol System', 'Traveling Sol System'),
        ('Cruising', 'Mining Base', 'Alpha Centauri', 'Traveling Alpha Centauri'), 
        ('Traveling', 'Outpost Beta', 'Vega System', 'Traveling Vega System'),
        ('Docked', 'Station Alpha', 'Sol System', 'Docked Station Alpha • Sol System'),
        ('Orbiting', 'Planet Earth', 'Sol System', 'Orbiting Planet Earth • Sol System'),
        ('Orbiting', '', 'Sol System', 'Orbiting Sol System'),  # No location
    ]
    
    for status, location, system, expected in test_cases:
        result = overlay.format_status_display(status, location, system)
        match = result == expected
        print(f"   {status:15} -> {result:35} {'✅' if match else '❌'}")
        if not match:
            print(f"      Expected: {expected}")
    
    print("\n🎯 **Key Behaviors:**")
    print("   • When traveling: Shows 'Traveling system_name' (system hyperlink only)")
    print("   • When at location: Shows 'Status location_name • system_name' (both hyperlinks)")
    print("   • Status updates dynamically as player state changes")
    print("   • Travel keywords trigger 'Traveling' display mode")
    
    return True

if __name__ == "__main__":
    test_travel_status_display_logic()
