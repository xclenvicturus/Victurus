#!/usr/bin/env python3

from data import db

def check_resources():
    """Debug resource nodes in the database"""
    
    # Check a few systems for their locations
    for system_id in range(1, 6):  # Check first 5 systems
        print(f"\n=== SYSTEM {system_id} ===")
        
        locations = db.get_locations(system_id)
        print(f"Total locations: {len(locations)}")
        
        # Group by location type
        type_counts = {}
        for loc in locations:
            loc_type = loc.get('location_type', 'unknown')
            type_counts[loc_type] = type_counts.get(loc_type, 0) + 1
            
            # Print resource nodes specifically
            if loc_type in ['asteroid_field', 'gas_clouds', 'ice_field', 'crystal_vein']:
                print(f"  RESOURCE: {loc.get('location_name', 'Unknown')} ({loc_type})")
        
        print("Type counts:", type_counts)
        
        # Also check the resource_nodes query
        try:
            resource_nodes = db.get_resource_nodes(system_id)
            print(f"get_resource_nodes() returned: {len(resource_nodes)} nodes")
        except Exception as e:
            print(f"get_resource_nodes() error: {e}")

if __name__ == "__main__":
    check_resources()
