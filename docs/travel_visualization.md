# Travel Visualization System

## Overview

The Travel Visualization System adds real-time visual feedback to the Victurus travel system, showing travel paths and progress indicators on both galaxy and system maps. When a player selects a destination to travel to, the system displays the calculated route and updates a progress indicator showing the player's current position along the path.

## Components

### Core Components

1. **TravelVisualization** (`ui/maps/travel_visualization.py`)
   - Calculates travel paths between locations
   - Manages progress tracking (0.0 to 1.0)
   - Provides position interpolation along paths
   - Handles both intra-system (cruise) and inter-system (warp) travel

2. **PathRenderer** (`ui/maps/travel_visualization.py`)
   - Renders travel paths on Qt Graphics scenes
   - Creates visual path lines (blue for cruise, pink for warp)
   - Displays animated progress indicators
   - Manages path graphics lifecycle

3. **TravelCoordinator** (`ui/maps/travel_coordinator.py`)
   - Coordinates between TravelFlow and map visualizations
   - Connects to TravelFlow progress signals
   - Updates both galaxy and system maps simultaneously
   - Manages travel visualization lifecycle

### Integration Components

4. **Map Extensions** (`ui/maps/galaxy.py`, `ui/maps/system.py`)
   - Added travel visualization methods to both map widgets
   - `show_travel_path(dest_type, dest_id)` - Display path to destination
   - `hide_travel_path()` - Clear current path
   - `update_travel_progress(progress)` - Update progress indicator
   - `get_travel_visualization()` - Access visualization instance

5. **Presenter Integration** (`ui/controllers/galaxy_location_presenter.py`, `ui/controllers/system_location_presenter.py`)
   - Modified `travel_here()` methods to trigger visualization
   - Starts visualization before beginning actual travel
   - Coordinates with TravelFlow for seamless experience

6. **Main Window Integration** (`ui/main_window.py`)
   - Setup travel coordinator with map widgets
   - Connects TravelFlow to coordinator for progress updates
   - Automatically ends visualization when travel completes

## Features

### Path Visualization
- **Cruise Paths**: Blue lines within systems (planets, stations, etc.)
- **Warp Paths**: Pink lines between star systems
- **Multi-segment Routes**: Complex paths with cruise + warp + cruise segments
- **Automatic Path Calculation**: Based on current position and fuel costs

### Progress Indicators
- **Real-time Updates**: Progress indicator moves along path during travel
- **Phase-aware Progress**: Different progress rates for different travel phases
- **Visual Feedback**: Yellow progress dot with white border
- **Smooth Animation**: Interpolated movement between path points

### User Experience
- **Automatic Display**: Paths appear when selecting travel destinations
- **Auto-cleanup**: Paths automatically disappear when travel completes
- **Multi-map Support**: Works on both galaxy and system views
- **Non-intrusive**: Visualization layers don't interfere with normal map interaction

## Usage

### For Players
1. **Right-click** on any destination in the location lists
2. **Select "Travel Here"** from the context menu
3. **Watch the path appear** on the map showing your route
4. **See progress indicator** move along the path as you travel
5. **Path disappears** automatically when you arrive

### For Developers

#### Adding New Map Types
```python
# In your new map widget class:
from .travel_visualization import TravelVisualization, PathRenderer

class NewMapWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        # ... existing setup ...
        
        # Add travel visualization
        self._travel_viz = TravelVisualization()
        self._path_renderer = PathRenderer(self._travel_viz)
        self._path_renderer.set_scene(self._scene)
        
    def show_travel_path(self, dest_type: str, dest_id: int) -> bool:
        path = self._travel_viz.calculate_path(dest_type, dest_id)
        if path:
            self._travel_viz.set_travel_path(path)
            return True
        return False
```

#### Custom Progress Calculation
```python
# Override progress calculation in TravelCoordinator subclass:
class CustomTravelCoordinator(TravelCoordinator):
    def _calculate_travel_progress(self) -> float:
        # Your custom progress logic here
        return custom_progress
```

#### Manual Control
```python
# Direct control of visualization:
from ui.maps.travel_coordinator import travel_coordinator

# Start visualization manually
travel_coordinator.begin_travel_visualization("star", system_id)

# Update progress manually  
travel_coordinator.force_update_progress(0.75)

# End visualization
travel_coordinator.end_travel_visualization()
```

## Technical Details

### Path Calculation Algorithm
1. **Get Current Position**: From player status (system_id, location_id)
2. **Resolve Destination**: Convert destination to coordinates
3. **Calculate Segments**:
   - Same system: Single cruise segment
   - Different system: Cruise to star → Warp to destination → Cruise to final location (if needed)
4. **Apply Physics**: Use existing travel.py fuel/time calculations
5. **Return Path**: Multi-segment path with total costs

### Coordinate Systems
- **Galaxy Map**: Uses system x,y coordinates from database
- **System Map**: Uses orbit-based positioning (radius + angle)
- **Conversion**: 1 AU ≈ 5 pixels (configurable scaling factor)

### Performance Considerations
- **Lazy Rendering**: Path graphics created only when needed
- **Efficient Updates**: Progress updates use scene item position changes
- **Memory Management**: Graphics items automatically cleaned up
- **Non-blocking**: Path calculation doesn't block UI thread

### Visual Styling
```python
# Path styling (customizable):
_path_pen = QPen(QColor(100, 200, 255, 180), 2.0)      # Cruise paths
_warp_pen = QPen(QColor(255, 100, 200, 200), 3.0)      # Warp paths  
_progress_brush = QBrush(QColor(255, 255, 0, 220))     # Progress indicator
```

## Configuration

### System Configuration (`settings/system_config.py`)
- `BASE_ORBIT_AU`: Base orbit radius for system positioning
- `RING_GAP_AU`: Distance between orbit rings
- `SPREAD_PX_PER_AU`: Pixel scaling factor for distances

### Travel Configuration (`game/travel.py`)
- `FUEL_PER_AU`: Fuel cost per AU for cruise travel
- `WARP_FUEL_PER_LY`: Fuel cost per light-year for warp travel
- `WARP_FUEL_WEIGHT`: Multiplier for warp fuel calculations

## Future Enhancements

### Planned Features
- **Route Optimization**: Show alternative paths with different fuel costs
- **Hazard Visualization**: Highlight dangerous routes or areas
- **Fleet Visualization**: Show multiple ship paths simultaneously
- **Historical Paths**: Show recently traveled routes
- **Waypoint System**: Allow players to set intermediate destinations

### Technical Improvements  
- **GPU Acceleration**: Use OpenGL shaders for smooth path rendering
- **LOD System**: Level-of-detail for complex multi-system routes
- **Caching**: Cache calculated paths for frequently traveled routes
- **Predictive Loading**: Pre-calculate paths for likely destinations

## Troubleshooting

### Common Issues
1. **Paths not appearing**: Check database connectivity and current position
2. **Progress not updating**: Verify TravelFlow connection to coordinator  
3. **Visual glitches**: Ensure proper graphics scene setup
4. **Performance issues**: Check path complexity and rendering settings

### Debug Tools
```python
# Enable debug logging:
import logging
logging.getLogger('ui.maps.travel_visualization').setLevel(logging.DEBUG)

# Test path calculation:
from ui.maps.travel_visualization import TravelVisualization
viz = TravelVisualization()
path = viz.calculate_path("star", system_id)
print(f"Path segments: {len(path.segments) if path else 0}")
```

### Log Messages
- `"Travel visualization started to {dest_type} {dest_id}"`
- `"Travel visualization completed"`
- `"Error calculating travel path: {error}"`
- `"Could not calculate path to {dest_type} {dest_id}"`
