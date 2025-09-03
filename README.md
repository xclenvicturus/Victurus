# Victurus

A space exploration and trading game built with Python and PySide6/Qt.

## Project Overview

Victurus is a space trading simulation game featuring:
- **Galaxy exploration** with multiple star systems and planets
- **Contextual actions interface** that adapts to your location (Station/Planet/Space)
- **Resource management** including mining and trading
- **Ship status tracking** with fuel, cargo, and location management  
- **Save/load game system** with multiple save slot support
- **Dynamic UI** with dockable panels and customizable layout
- **Real-time simulation** background processing
- **Travel visualization** with overlay-based progress tracking
- **Complete game state management** with proper cleanup and restoration

## Requirements

- Python 3.9+
- PySide6 6.9.1+

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Victurus
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the game:
   ```bash
   python main.py
   ```

## Project Structure

See `docs/structure.md` for detailed information about the codebase organization.

### Key Directories

- **`ui/`** - User interface components (PySide6/Qt widgets)
- **`game/`** - Game logic (player status, travel system, ship state)
- **`data/`** - Database layer and universe data
- **`save/`** - Save game management and serialization
- **`game_controller/`** - Background simulation and game orchestration
- **`assets/`** - Game art assets (GIFs, PNGs) for planets, stations, etc.
- **`tests/`** - Essential test files and utilities
- **`docs/`** - Project documentation

## Features

### Implemented
- ✅ **Galaxy/System Maps** - Visual navigation interface with travel visualization
- ✅ **Travel System** - Multi-phase travel with progress overlay and realistic timing
- ✅ **Actions Panel** - Context-aware action buttons that adapt to player location
- ✅ **Save/Load System** - Multiple save slots with metadata
- ✅ **UI State Persistence** - Window layouts and panel configurations
- ✅ **Close Game Functionality** - Complete cleanup and state restoration
- ✅ **Error Handling** - Comprehensive crash reporting and recovery
- ✅ **Widget Lifecycle Management** - Qt object protection against crashes
- ✅ **Resource Management** - Asteroid fields, gas clouds, ice fields, crystal veins
- ✅ **Dynamic Asset System** - Unique visual assets per system/location
- ✅ **Logging System** - Centralized logging with component-specific debug files

### Menu System
- ✅ **File Menu** - New Game, Load Game, Save Game, Save As, Close Game
- ✅ **View Menu** - Panel visibility controls with Show All/Hide All functionality

### UI Components  
- ✅ **Dockable Panels** - Status, logs, location lists, contextual actions
- ✅ **Travel Overlay** - Real-time progress tracking with status display
- ✅ **Actions Panel** - Location-aware buttons (Repair/Refuel at stations, Land/Mine on planets, Travel/Jump in space)
- ✅ **Log System** - Categorized game logs (Combat, Trade, Dialogue, etc.)
- ✅ **Location Lists** - Filterable/sortable galaxy and system views
- ✅ **Game State Management** - Proper transitions between game loaded/no game states

## Development

### Running Tests
```bash
# Run core test suite
python tests/test_error_handler.py
python tests/test_load_multiple_saves.py
python tests/travel_visualization_test.py
python tests/travel_visualization_safety_test.py
```

**Note:** Development test scripts have been moved to `archive/obsolete_tests/` to keep the project root clean.

### Database
The game uses SQLite for data storage with WAL mode and foreign key constraints enabled. The database is automatically created and seeded on first run.

### Logging
The project uses a centralized logging system with component-specific log files:
- `logs/travel_debug.log` - Travel system debug information
- `logs/ui_debug.log` - UI component debug information
- `logs/game_debug.log` - Game logic debug information
- `logs/system_debug.log` - System-level debug information
- `logs/error.log` - Error messages
- `logs/warning.log` - Warning messages

## Configuration

Game behavior can be tuned via `settings/system_config.py`:
- Travel timing (cruise speed, warp speed)
- Visual spacing and scaling
- Orbit mechanics parameters
- UI interaction settings

## Documentation

- **`docs/structure.md`** - Detailed project structure and module descriptions
- **`docs/project_status.md`** - Development status and feature progress
- **`docs/ui_state_management.md`** - UI persistence system documentation  
- **`docs/error_handling.md`** - Error handling system documentation
- **`docs/travel_visualization.md`** - Travel system architecture documentation
- **`docs/logging_system.md`** - Centralized logging system documentation

## Development Standards

### 🚨 MANDATORY: Logging and Error Handling

**All code MUST use the centralized logging system:**

```python
from game_controller.log_config import get_travel_logger, get_ui_logger, get_game_logger, get_system_logger

# Use appropriate logger for component type:
logger = get_travel_logger('module_name')     # travel_debug.log
logger = get_ui_logger('widget_name')         # ui_debug.log  
logger = get_game_logger('component_name')    # game_debug.log
logger = get_system_logger('service_name')    # system_debug.log
```

**All Qt slots MUST have error protection:**

```python
from ui.error_utils import catch_and_log, warn_on_exception

@catch_and_log("Critical operation")
def critical_function(self):
    pass

@warn_on_exception("UI update")  
def ui_slot_function(self):
    pass
```

### ❌ FORBIDDEN:
- `print()` statements (use logger instead)
- `logging.getLogger()` (use centralized system)
- Unprotected Qt slots (add error decorators)
- Silent exception swallowing (log all errors)

## Project Cleanup

**September 3, 2025**: Project has been cleaned up and organized:
- **25+ obsolete test files** moved to `archive/obsolete_tests/`
- **7+ debug/utility scripts** moved to `archive/debug_scripts/`  
- **5+ redundant documentation files** moved to `archive/obsolete_docs/`
- **Project root** now contains only essential files
- **Development history** fully preserved in `archive/` directory

If you need to reference any archived files for development, they're available in the `archive/` directory with a detailed cleanup summary.

## Contributing

1. Follow the existing code structure and naming conventions
2. Add proper file headers with path and description
3. **STRICTLY FOLLOW** logging and error handling standards above
4. Update documentation when adding new features
5. Test changes with multiple save files and UI configurations

## License

[Add license information here]
