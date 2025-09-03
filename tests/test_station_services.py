# /tests/test_station_services.py

"""
Test script to verify station service system is working correctly
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from game_controller.log_config import get_system_logger
from data import db

logger = get_system_logger('test_station_services')

def test_station_services():
    """Test the new station service system."""
    logger.info("Testing station service system")
    
    # Get all stations
    conn = db.get_connection()
    stations = conn.execute("""
        SELECT location_id, location_name, system_id 
        FROM locations 
        WHERE location_type = 'Station'
        ORDER BY location_id
        LIMIT 20
    """).fetchall()
    
    logger.info(f"Testing services for {len(stations)} stations")
    
    stations_with_services = 0
    service_counts = {}
    
    for station in stations:
        location_id = station['location_id']
        location_name = station['location_name']
        
        # Get services using new function
        services = db.get_station_services(location_id)
        
        if services:
            stations_with_services += 1
            logger.info(f"Station {location_name} (ID {location_id}): {', '.join(services)}")
            
            for service in services:
                service_counts[service] = service_counts.get(service, 0) + 1
        else:
            logger.info(f"Station {location_name} (ID {location_id}): No services")
    
    logger.info(f"\nService Distribution:")
    logger.info(f"Stations with services: {stations_with_services}/{len(stations)}")
    
    for service, count in sorted(service_counts.items()):
        logger.info(f"  {service}: {count} stations")

def test_facility_types():
    """Check what facility types exist in the database."""
    logger.info("Checking facility types in database")
    
    conn = db.get_connection()
    facility_types = conn.execute("""
        SELECT facility_type, COUNT(*) as count
        FROM facilities
        GROUP BY facility_type
        ORDER BY facility_type
    """).fetchall()
    
    logger.info("Facility types and counts:")
    for row in facility_types:
        logger.info(f"  {row['facility_type']}: {row['count']}")

if __name__ == "__main__":
    test_facility_types()
    print("\n" + "="*50 + "\n")
    test_station_services()
