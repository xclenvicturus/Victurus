# Victurus AI Coding Instructions

## Architecture Overview

**Victurus** is a PySide6/Qt-based space trading game with SQLite persistence, dockable UI panels, and real-time travel visualization.

### Core Data Flow
- **`data/db.py`**: Thread-local SQLite connections with WAL mode, foreign keys enabled
- **`save/save_manager.py`**: Debounced save system with UI state persistence 
- **`game/player_status.py`**: Aggregates player/ship/system snapshots for UI consumption
- **`ui/main_window.py`**: Central hub connecting maps, panels, menus via Qt signals/slots

### Component Boundaries
- **`ui/`**: Pure Qt widgets with no direct database access
- **`game/`**: Business logic and travel calculations  
- **`data/`**: Database layer with thread-safe connection management
- **`save/`**: Save/load orchestration with metadata and UI state

## MANDATORY Logging & Error Handling

### 🚨 CRITICAL: Logging System Requirements (ZERO EXCEPTIONS)

**NEVER use print() statements - ALWAYS use centralized logging:**

```python
from game_controller.log_config import get_travel_logger, get_ui_logger, get_game_logger, get_system_logger

# REQUIRED: Choose appropriate logger for component type:
logger = get_travel_logger('module_name')     # Routes to travel_debug.log
logger = get_ui_logger('widget_name')         # Routes to ui_debug.log  
logger = get_game_logger('component_name')    # Routes to game_debug.log
logger = get_system_logger('service_name')    # Routes to system_debug.log

# Log levels automatically route to error.log and warning.log
logger.debug("Debug information")    # For development debugging
logger.info("Important events")      # For tracking system behavior
logger.warning("Non-critical issues") # Auto-routes to warning.log
logger.error("Critical errors")      # Auto-routes to error.log
```

### 🛡️ REQUIRED: Error Handling Patterns

**Every Qt slot and critical function MUST have error protection:**

```python
from ui.error_handler import catch_and_log, warn_on_exception, ErrorContext

# FOR CRITICAL FUNCTIONS (travel, save, database operations):
@catch_and_log("Travel system")
def initiate_travel(self, destination):
    # Function implementation
    pass

# FOR UI SLOTS (non-critical operations):
@warn_on_exception("UI update")
def on_button_clicked(self):
    # Function implementation  
    pass

# FOR COMPLEX ERROR SCENARIOS:
with ErrorContext("Complex operation description"):
    # Multi-step operation
    pass
```

### 📋 Logger Selection Rules (STRICTLY ENFORCED)

| Component Type | Logger Function | Log File | Use For |
|---|---|---|---|
| **Travel/Navigation** | `get_travel_logger()` | `travel_debug.log` | Path calculation, fuel, obstacles |
| **UI Widgets** | `get_ui_logger()` | `ui_debug.log` | Widget updates, user interactions |
| **Game Logic** | `get_game_logger()` | `game_debug.log` | Business rules, player state |
| **System/Database** | `get_system_logger()` | `system_debug.log` | DB operations, saves, configuration |

### ❌ FORBIDDEN PRACTICES
- `print()` statements (use logger instead)
- `logging.getLogger()` (use centralized system)
- Unprotected Qt slots (add error decorators)
- Silent exception swallowing (log all errors)

## Key Patterns

### File Headers
Every file starts with path comment: `# /relative/path/to/file.py`

### Database Access
```python
from data import db
# Thread-safe, automatic connection management
systems = db.get_systems()
db.execute("UPDATE players SET location_id = ?", (loc_id,))
```

### UI State Persistence  
```python
from save.ui_config import install_ui_state_provider
# MainWindow automatically persists dock layouts, window geometry
install_ui_state_provider(lambda: self.get_ui_state_dict())
```

### Asset Loading
```python
from ui.maps.icons import list_images, make_map_symbol_item
# Deterministic asset selection based on entity IDs
planet_imgs = list_images(PLANETS_DIR)
icon_path = planet_imgs[entity_id % len(planet_imgs)]
```

### Map Coordinate Systems
- **Galaxy maps**: Use scene coordinates for positioning
- **System maps**: Use `_drawpos` dictionary for orbital tracking
- **Travel visualization**: Scene coordinates for graphics items, viewport coordinates for overlays

### Error Handling & Logging Integration
```python
# REQUIRED: Install global error handler in main_window.py
from ui.error_handler import install_error_handler
install_error_handler()

# MANDATORY: Add error decorators to ALL Qt slots
from ui.error_handler import catch_and_log, warn_on_exception

@catch_and_log("Critical operation name")
def critical_function(self):
    """For functions that MUST complete (travel, save, database)"""
    pass

@warn_on_exception("UI operation name") 
def ui_slot_function(self):
    """For UI updates that can fail gracefully"""
    pass

# REQUIRED: Use ErrorContext for complex operations
from ui.error_handler import ErrorContext
with ErrorContext("Multi-step operation description"):
    # Complex operation with multiple failure points
    pass
```

## Development Workflows

### Running the Game
```bash
python main.py  # Logs go to logs/ directory automatically
```

### Testing Components
```bash
python tests/test_error_handler.py
python tests/test_load_multiple_saves.py
```

### Database Reset
```python
# In code - triggers fresh seed from universe_seed.json
from data import db
db.set_active_db_path("database/test.db")  # or delete game.db
```

## Integration Points

### Travel System
- **`game/travel_flow.py`**: Multi-phase travel with fuel consumption
- **`ui/maps/travel_coordinator.py`**: Coordinates visualization across maps
- **`ui/maps/travel_visualization.py`**: Renders curved paths avoiding obstacles

### Save System
- **`save/save_manager.py`**: Manages save slots with debounced writes
- **`save/icon_paths.py`**: Deterministic asset baking per save
- **UI state auto-persists**: Window geometry, dock layouts, panel visibility

### Map System  
- **`ui/maps/system.py`**: Orbital mechanics with `_tick_orbits()` every 16ms
- **`ui/maps/*_leadline.py`**: Hover overlays using viewport coordinates
- **Asset determinism**: Same entity ID always gets same visual asset

## Common Gotchas

- **Threading**: Database uses thread-local connections, UI operations must stay on main thread
- **Coordinates**: Maps use different coordinate systems (scene vs viewport)
- **Save timing**: SaveManager debounces writes - immediate saves need `flush_pending_writes()`
- **Asset paths**: Use `list_images()` helper, not direct file access
- **Qt lifecycle**: Always check widget validity before accessing in timers/callbacks

## File Organization Significance

- **Plural asset directories**: `assets/planets/` not `assets/planet/` (matches `resource_type` enum)
- **Controller pattern**: `ui/controllers/` mediates between widgets and game state
- **State separation**: `ui/state/` handles persistence, `game/` handles business logic
- **Dataclass models**: `save/models.py` defines serializable state structures
