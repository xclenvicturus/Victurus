# /tests/final_service_system_test.py

"""
Final comprehensive test of the service facility system
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import db

def test_service_system_comprehensive():
    """Comprehensive test of the service system."""
    print("=== COMPREHENSIVE SERVICE SYSTEM TEST ===")
    
    # Test 1: Check service facility distribution
    print("\n1. SERVICE FACILITY DISTRIBUTION:")
    conn = db.get_connection()
    service_facilities = conn.execute("""
        SELECT facility_type, COUNT(*) as count
        FROM facilities
        WHERE facility_type IN ('Repair Bay', 'Fuel Depot', 'Trading Post', 
                               'Mission Board', 'Ship Outfitter', 'Storage Vault')
        GROUP BY facility_type
        ORDER BY facility_type
    """).fetchall()
    
    total_services = 0
    for row in service_facilities:
        count = row['count']
        total_services += count
        print(f"  {row['facility_type']}: {count}")
    
    print(f"  TOTAL SERVICE FACILITIES: {total_services}")
    
    # Test 2: Sample station service analysis
    print("\n2. STATION SERVICE ANALYSIS (20 stations):")
    stations = conn.execute("""
        SELECT location_id, location_name
        FROM locations 
        WHERE location_type = 'station'
        ORDER BY location_id
        LIMIT 20
    """).fetchall()
    
    stations_with_services = 0
    service_distribution = {}
    
    for station in stations:
        location_id = station['location_id']
        location_name = station['location_name']
        
        services = db.get_station_services(location_id)
        
        if services:
            stations_with_services += 1
            print(f"  {location_name}: {', '.join(services)}")
            
            for service in services:
                service_distribution[service] = service_distribution.get(service, 0) + 1
        else:
            print(f"  {location_name}: NO SERVICES")
    
    print(f"\n  STATIONS WITH SERVICES: {stations_with_services}/{len(stations)}")
    print(f"  SERVICE DISTRIBUTION:")
    for service, count in sorted(service_distribution.items()):
        percentage = (count / len(stations)) * 100
        print(f"    {service}: {count}/{len(stations)} ({percentage:.1f}%)")
    
    # Test 3: Database function tests
    print("\n3. DATABASE FUNCTION TESTS:")
    
    # Test get_location_facilities
    test_location_id = stations[0]['location_id']
    facilities = db.get_location_facilities(test_location_id)
    print(f"  get_location_facilities({test_location_id}): {len(facilities)} facilities")
    
    # Test get_station_services
    services = db.get_station_services(test_location_id)
    print(f"  get_station_services({test_location_id}): {services}")
    
    # Test 4: Economy readiness assessment
    print("\n4. ECONOMY SYSTEM READINESS:")
    
    total_stations = conn.execute("SELECT COUNT(*) as count FROM locations WHERE location_type = 'station'").fetchone()['count']
    
    # Get actual service coverage across all stations
    all_service_counts = conn.execute("""
        SELECT 
            COUNT(CASE WHEN f.facility_type = 'Fuel Depot' THEN 1 END) as fuel_stations,
            COUNT(CASE WHEN f.facility_type = 'Repair Bay' THEN 1 END) as repair_stations,
            COUNT(CASE WHEN f.facility_type = 'Trading Post' THEN 1 END) as market_stations
        FROM locations l
        LEFT JOIN facilities f ON l.location_id = f.location_id 
        WHERE l.location_type = 'station'
        AND f.facility_type IN ('Fuel Depot', 'Repair Bay', 'Trading Post')
    """).fetchone()
    
    stations_with_refuel = all_service_counts['fuel_stations'] or 0
    stations_with_repair = all_service_counts['repair_stations'] or 0 
    stations_with_market = all_service_counts['market_stations'] or 0
    
    refuel_coverage = (stations_with_refuel / total_stations) * 100
    repair_coverage = (stations_with_repair / total_stations) * 100
    market_coverage = (stations_with_market / total_stations) * 100
    
    print(f"  Total stations in database: {total_stations}")
    print(f"  Refuel service coverage: {refuel_coverage:.1f}%")
    print(f"  Repair service coverage: {repair_coverage:.1f}%")
    print(f"  Market service coverage: {market_coverage:.1f}%")
    
    if refuel_coverage >= 70 and repair_coverage >= 50 and market_coverage >= 40:
        print("  ✅ ECONOMY SYSTEM READY - Good service distribution")
    else:
        print("  ⚠️  ECONOMY SYSTEM NEEDS IMPROVEMENT - Service coverage too low")
    
    # Test 5: Actions Panel compatibility
    print("\n5. ACTIONS PANEL COMPATIBILITY:")
    
    # Test if Actions Panel service mapping works
    sample_station = stations[0]
    services = db.get_station_services(sample_station['location_id'])
    
    print(f"  Sample station: {sample_station['location_name']}")
    print(f"  Detected services: {services}")
    print(f"  Actions Panel would show:")
    
    if 'refuel' in services:
        print("    - Refuel Ship button")
    if 'repair' in services:
        print("    - Repair Ship button")
    if 'market' in services:
        print("    - Commodities Market button")
    if 'outfitting' in services:
        print("    - Ship Outfitting button")
    if 'storage' in services:
        print("    - Storage Vault button")
    if 'medical' in services:
        print("    - Medical Bay button")
    
    if not services:
        print("    - No service buttons (only missions, staff, undock)")
    
    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    test_service_system_comprehensive()
