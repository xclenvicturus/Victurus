# UI State Management

The game now has a robust UI state management system that automatically saves and restores window positions, panel settings, and UI configuration **only when users make actual changes** - not during programmatic initialization.

## Key Features

### 🔄 Smart Save Logic
- **User Changes Only**: Saves occur only when users actually modify the UI
- **No Startup Spam**: Programmatic changes during initialization are ignored
- **Debounced Saves**: Multiple rapid changes are combined into a single save operation
- **Atomic Writes**: Configuration files are written safely to prevent corruption

### 🚫 Problem Solved: Excessive Saving
The previous issue where the system constantly overwrote the UI settings file during startup and loading has been fixed:

- **Suspension System**: UI saves are suspended during initialization and game loading
- **User Detection**: Only actual user interactions trigger saves
- **Proper Timing**: Saves resume only after all UI components are fully initialized

## How It Works

### Startup Process
1. **Check for Configuration**: When the game starts, it checks for the UI state configuration file at:
   - Windows: `~/Documents/Victurus_game/Config/ui_state.json`
   - Other platforms: `~/Documents/Victurus_game/Config/ui_state.json`

2. **Create Defaults if Missing**: If the file doesn't exist, the system creates it with sensible default values for:
   - Main window size and position (1200x800, centered)
   - Dock panel visibility (Status, Galaxy, System visible by default)
   - Panel layout and column widths
   - Map tab selection
   - Leader line colors and styles

3. **Load Existing Configuration**: If the file exists, the system loads all saved UI settings and applies them to restore the last known state.

### Real-time Saving
The system automatically saves changes **only when users actually interact with the UI**:
- **Move or resize** the main window ✅ User action → Save
- **Open or close** dock panels (Status, Logs, Galaxy, System) ✅ User action → Save
- **Move or resize** floating dock panels ✅ User action → Save
- **Adjust splitter positions** between map view and panels ✅ User action → Save
- **Change panel settings** (category filters, sort options, search text) ✅ User action → Save
- **Resize column widths** in Galaxy and System lists ✅ User action → Save
- **Switch map tabs** between Galaxy and System views ✅ User action → Save
- **Modify leader line settings** (colors, width, glow effects) ✅ User action → Save

**Ignored (No Save)**:
- ❌ Window restoration during startup 
- ❌ Panel creation and initialization
- ❌ Loading saved games
- ❌ Creating new games
- ❌ Programmatic UI updates

### Configuration File Structure
The `ui_state.json` file contains:

```json
{
  "MainWindow": {
    "main_geometry": {
      "x": 100, "y": 100, "w": 1200, "h": 800,
      "maximized": false
    },
    "dock_visibility": {
      "dock_Status": true,
      "dock_Panel_Galaxy": true,
      "dock_Panel_System": true,
      "dock_Log_All": true,
      "dock_Log_Combat": false
    },
    "dock_layout": {
      "dock_Status": {
        "open": true, "floating": false,
        "x": 0, "y": 0, "w": 300, "h": 400
      }
    },
    "central_splitter_sizes": [800, 400],
    "galaxy_col_widths": [200, 100, 80, 80],
    "system_col_widths": [200, 100, 80, 80, 80],
    "map_tab_index": 0,
    "galaxy_category_index": 0,
    "system_category_index": 0,
    "galaxy_sort_text": "Name A–Z",
    "system_sort_text": "Default View",
    "galaxy_search": "",
    "system_search": "",
    "galaxy_leader_color": "#00FF80",
    "galaxy_leader_width": 2,
    "galaxy_leader_glow": true,
    "system_leader_color": "#00FF80",
    "system_leader_width": 2,
    "system_leader_glow": true
  }
}
```

## Technical Implementation

### Dual State Management + Suspension System
The system uses:
1. **New UI State Manager** (`ui/state/ui_state_manager.py`) - Simplified, reliable system with suspension support
2. **Legacy State System** (`ui/state/window_state.py`) - Maintains compatibility

### Save Suspension During Initialization

#### MainWindow Initialization
1. **Constructor**: `suspend_saves()` called immediately
2. **UI Restoration**: Saved state applied without triggering saves
3. **Resume**: `resume_saves()` called after 100ms delay

#### Game Loading (start_game_ui)
1. **Method Start**: `suspend_saves()` called
2. **UI Creation**: All panels, docks, splitters created
3. **State Restoration**: Panel settings, positions restored
4. **Resume**: `resume_saves()` called after 200ms delay

### Key Components

#### UIStateManager Class
- **Suspension Control**: `suspend_saves()` / `resume_saves()` methods
- **Save Prevention**: `is_save_suspended()` checks before any save operation
- **Initialization**: Checks for config file, creates defaults if missing
- **Loading**: Merges saved state with defaults to ensure all keys exist
- **Saving**: Debounced writes (100ms delay) with atomic file operations
- **State Access**: Methods to get/set window and dock state

#### MainWindow Integration
- **Startup Suspension**: Saves suspended during constructor and start_game_ui
- **Event Handlers**: Check suspension state before saving
- **Panel Restoration**: Restores filter settings, column widths, etc. without saves
- **Timed Resume**: Uses QTimer to resume saves after initialization completes

### Benefits

1. **Persistent UI Experience**: Users' layout preferences are maintained between sessions
2. **Reliable Defaults**: New installations get sensible default layouts  
3. **Smart Saving**: Only saves on actual user changes, not during initialization
4. **No Save Spam**: Prevents constant overwriting during startup/loading
5. **Immediate Persistence**: Real user changes are saved within 100ms
6. **Human-Readable Config**: JSON format allows manual editing if needed
7. **Graceful Fallbacks**: System continues working even if config is corrupted
8. **Proper Game Loading**: Saved games and new games load with correct UI state

### Usage Examples

#### For Developers
```python
from ui.state.ui_state_manager import get_ui_state_manager

# Get the global UI state manager
ui_state = get_ui_state_manager()

# Update main window state
ui_state.update_main_window_state({
    "some_setting": "value"
})

# Check if a dock should be visible
if ui_state.is_dock_visible("dock_Status"):
    status_dock.show()

# Set dock geometry
ui_state.set_dock_geometry("dock_MyPanel", x=100, y=100, width=300, height=400)
```

#### For Users
- Simply use the application normally
- Move, resize, and arrange windows as desired
- All changes are saved automatically
- Next time you start the game, everything will be exactly as you left it

## File Location

The configuration file is stored at:
- **Windows**: `C:\\Users\\[username]\\Documents\\Victurus_game\\Config\\ui_state.json`
- **macOS**: `~/Documents/Victurus_game/Config/ui_state.json`
- **Linux**: `~/Documents/Victurus_game/Config/ui_state.json`

This location ensures the configuration persists across game updates and is backed up with user documents.
