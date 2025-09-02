"""
View Menu Show All/Hide All Fix Verification

This document explains the fix applied to the View menu Show All/Hide All functionality.

## Problem
The "Show All" and "Hide All" buttons in View → Panels menu were not working with log panels.
They only affected:
- Status dock
- Location panel galaxy
- Location panel system  
- Legacy location panel

But they completely ignored all the log docks (All, Combat, Trade, Dialogue, etc.).

## Root Cause
The original Show All/Hide All actions used simple lambda functions that only called the _toggle()
function for the main panels, but did not include any logic for the log categories.

## Solution
Updated the Show All and Hide All actions to:

1. **Show/Hide main panels** (existing functionality)
   - Status dock
   - Location panels
   
2. **Show/Hide all log docks** (new functionality)  
   - Iterate through all log category actions stored in `win._act_log_categories`
   - Trigger the toggle signal for each log category action
   - This reuses the existing individual toggle logic for consistency

## Technical Implementation

### Before (broken):
```python
act_show_all.triggered.connect(lambda: [
    _toggle(lambda: getattr(win, "status_dock", None))(True),
    _toggle(lambda: getattr(win, "location_panel_galaxy", None))(True),
    _toggle(lambda: getattr(win, "location_panel_system", None))(True),
    _toggle(lambda: getattr(win, "location_panel", None))(True),
    # Log docks were completely missing!
])
```

### After (fixed):
```python
def _show_all():
    # Show main panels (existing)
    _toggle(lambda: getattr(win, "status_dock", None))(True)
    _toggle(lambda: getattr(win, "location_panel_galaxy", None))(True)
    _toggle(lambda: getattr(win, "location_panel_system", None))(True)
    _toggle(lambda: getattr(win, "location_panel", None))(True)
    
    # Show all log docks (new)
    try:
        act_log_map = getattr(win, "_act_log_categories", {})
        for cat, action in act_log_map.items():
            if isinstance(action, QAction) and action.isCheckable():
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
                action.toggled.emit(True)  # Triggers the individual toggle logic
    except Exception:
        pass

act_show_all.triggered.connect(_show_all)
```

## Benefits

1. **Consistency**: Reuses the existing individual log toggle logic instead of duplicating it
2. **Completeness**: Now affects ALL panels/docks in the UI, not just some of them  
3. **Persistence**: Log dock visibility is properly saved to config (handled by individual toggles)
4. **Error Safety**: Wrapped in try-catch to prevent crashes if log system isn't initialized
5. **Signal Handling**: Properly blocks/unblocks signals to prevent unnecessary events

## Testing
The fix can be tested by:
1. Loading the game with multiple log panels visible
2. Using View → Panels → Hide All - all panels including logs should hide
3. Using View → Panels → Show All - all panels including logs should show  
4. Individual log toggles should still work normally
5. Panel visibility should persist across game sessions

## Files Modified
- `ui/menus/view_menu.py` - Updated Show All and Hide All action implementations
