# /tests/check_system_tags.py

"""
Check system economic tags structure
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import db

def check_system_tags_structure():
    """Check the structure of system_econ_tags table."""
    print("Checking system_econ_tags table structure")
    
    conn = db.get_connection()
    
    # Check table structure
    columns = conn.execute("PRAGMA table_info(system_econ_tags)").fetchall()
    print("system_econ_tags columns:", [col['name'] for col in columns])
    
    # Sample some data
    sample_data = conn.execute("SELECT * FROM system_econ_tags LIMIT 5").fetchall()
    print("Sample data:")
    for row in sample_data:
        print(f"  {dict(row)}")

if __name__ == "__main__":
    check_system_tags_structure()
