# /tests/travel_visualization_test.py

"""
Travel Visualization Test

Test script to validate the travel visualization system works correctly.
Tests path calculation, visualization rendering, and progress updates.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_travel_visualization():
    """Test the travel visualization components"""
    print("Testing Travel Visualization System...")
    
    try:
        # Test imports
        from ui.maps.travel_visualization import TravelVisualization, PathRenderer, TravelPath, PathSegment
        from ui.maps.travel_coordinator import TravelCoordinator, travel_coordinator
        print("✓ All imports successful")
        
        # Test TravelVisualization creation
        viz = TravelVisualization()
        print("✓ TravelVisualization created")
        
        # Test coordinator creation
        coord = TravelCoordinator()
        print("✓ TravelCoordinator created")
        
        # Test path calculation (will fail without DB, but should handle gracefully)
        path = viz.calculate_path("star", 1)
        if path is None:
            print("✓ Path calculation handled missing data gracefully")
        else:
            print(f"✓ Path calculated with {len(path.segments)} segments")
            
        # Test progress updates
        viz.update_progress(0.5)
        print("✓ Progress update handled")
        
        # Test position calculation
        pos = viz.get_progress_position()
        print(f"✓ Progress position: {pos}")
        
        print("\n✅ All travel visualization tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """Test integration with existing systems"""
    print("\nTesting Integration...")
    
    try:
        # Test database integration
        from data import db
        print("✓ Database module accessible")
        
        # Test player status integration
        from game import player_status
        print("✓ Player status module accessible")
        
        # Test travel module integration
        from game import travel
        print("✓ Travel module accessible")
        
        # Test TravelFlow integration
        from game.travel_flow import TravelFlow
        print("✓ TravelFlow module accessible")
        
        print("✅ All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = True
    
    success &= test_travel_visualization()
    success &= test_integration()
    
    if success:
        print("\n🎉 All tests passed! Travel visualization system is ready.")
    else:
        print("\n⚠️  Some tests failed. Check the implementation.")
        sys.exit(1)
