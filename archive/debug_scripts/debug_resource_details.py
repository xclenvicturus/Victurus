#!/usr/bin/env python3

from data import db

def check_resource_details():
    """Check what resource nodes contain"""
    
    # Check systems that have resources
    for system_id in [3, 4]:  # Systems with resources
        print(f"\n=== SYSTEM {system_id} RESOURCES ===")
        
        resource_nodes = db.get_resource_nodes(system_id)
        print(f"Resource nodes: {len(resource_nodes)}")
        
        for i, node in enumerate(resource_nodes):
            print(f"  Node {i+1}:")
            for key, value in node.items():
                print(f"    {key}: {value}")
        
        # Also check locations with type 'resource'
        locations = db.get_locations(system_id)
        resource_locs = [loc for loc in locations if loc.get('location_type') == 'resource']
        print(f"\nResource locations: {len(resource_locs)}")
        
        for i, loc in enumerate(resource_locs):
            print(f"  Resource Location {i+1}:")
            for key, value in loc.items():
                print(f"    {key}: {value}")

if __name__ == "__main__":
    check_resource_details()
