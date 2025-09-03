# Add sample facilities to stations for testing
from data import db

def add_sample_facilities():
    """Add sample facilities to stations for testing dynamic actions"""
    conn = db.get_connection()
    
    try:
        # Get some station locations
        stations = conn.execute("""
            SELECT location_id, location_name 
            FROM locations 
            WHERE location_type = 'station' 
            LIMIT 10
        """).fetchall()
        
        if not stations:
            print("No stations found in database")
            return
        
        # Sample facility types
        facility_templates = [
            ('Fuel', 'High-grade starship fuel depot'),
            ('Repair', 'Hull and systems maintenance bay'),
            ('Market', 'Commodity trading exchange'),
            ('Missions', 'Mission board and contract center'),
            ('Hangar', 'Ship storage and maintenance'),
            ('Outfitting', 'Equipment and module upgrades'),
            ('Manufacturing', 'Industrial production facility'),
            ('Research', 'Technology development lab'),
            ('Refinery', 'Ore processing and refinement')
        ]
        
        # Add facilities to stations
        for i, station in enumerate(stations):
            location_id = station['location_id']
            location_name = station['location_name']
            
            print(f"Adding facilities to {location_name} (ID: {location_id})")
            
            # Each station gets 3-6 random facilities
            import random
            num_facilities = random.randint(3, 6)
            selected_facilities = random.sample(facility_templates, num_facilities)
            
            for facility_type, notes in selected_facilities:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO facilities (location_id, facility_type, notes)
                        VALUES (?, ?, ?)
                    """, (location_id, facility_type, notes))
                    print(f"  + {facility_type}: {notes}")
                except Exception as e:
                    print(f"  Error adding {facility_type}: {e}")
        
        conn.commit()
        print(f"\\n✅ Added facilities to {len(stations)} stations")
        
        # Show summary
        total_facilities = conn.execute("SELECT COUNT(*) as count FROM facilities").fetchone()
        print(f"Total facilities in database: {total_facilities['count']}")
        
    except Exception as e:
        print(f"Error adding facilities: {e}")
        conn.rollback()

if __name__ == "__main__":
    add_sample_facilities()
    print("\\nFacility setup complete!")
