# /ui/state/ui_state_manager.py

"""
Victurus UI State Management System

Manages persistent UI state across application sessions:
- Automatic state tracking and serialization
- Debounced writes to prevent excessive I/O
- Integration with save system for per-save UI preferences
- Main window geometry, dock positions, and user preferences
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QApplication

from save.paths import get_ui_state_path
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('ui_state_manager')


class UIStateManager(QObject):
    """
    Simplified UI state manager that ensures:
    1. Check for ui_state.json on startup
    2. Create with defaults if missing
    3. Load and apply settings
    4. Save changes immediately when users modify UI
    """
    
    stateLoaded = Signal()
    stateSaved = Signal()
    
    def __init__(self):
        super().__init__()
        self._config_path = get_ui_state_path()
        self._state: Dict[str, Any] = {}
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_to_disk)
        self._save_timer.setInterval(500)  # Increased delay to reduce saves during drag operations
        self._loading = False
        self._suspended = False  # Track if saves are suspended
        self._drag_timer = QTimer()  # Timer to detect end of drag operations
        self._drag_timer.setSingleShot(True)
        self._drag_timer.timeout.connect(self._on_drag_finished)
        self._drag_timer.setInterval(250)  # Wait 250ms after last movement to save
        self._pending_save = False
        
    def suspend_saves(self) -> None:
        """Suspend saving to prevent programmatic changes from being persisted"""
        self._suspended = True
        self._save_timer.stop()  # Cancel any pending saves
        
    def resume_saves(self) -> None:
        """Resume saving after programmatic operations complete"""
        self._suspended = False
        
    def is_save_suspended(self) -> bool:
        """Check if saves are currently suspended"""
        return self._suspended or self._loading
    
    def _on_drag_finished(self) -> None:
        """Called when drag operation appears to be finished (no movement for 250ms)"""
        if self._pending_save and not self.is_save_suspended():
            self._save_timer.start()
            self._pending_save = False
        
    def get_default_state(self) -> Dict[str, Any]:
        """Default UI state when no config file exists"""
        return {
            "MainWindow": {
                "main_geometry": {
                    "x": 100,
                    "y": 100, 
                    "w": 1200,
                    "h": 800,
                    "maximized": False
                },
                "dock_visibility": {
                    "dock_Status": True,
                    "dock_Log_All": True,
                    "dock_Log_Combat": True,
                    "dock_Log_Trade": True,
                    "dock_Log_Dialogue": True,
                    "dock_Log_Reputation": True,
                    "dock_Log_Loot": True,
                    "dock_Log_Quest": True,
                    "dock_Panel_Galaxy": True,
                    "dock_Panel_System": True
                },
                "dock_layout": {},
                "central_splitter_sizes": [400],
                "map_tab_index": 0,
                "galaxy_col_widths": [200, 100, 80, 80],
                "system_col_widths": [200, 100, 80, 80, 80],
                "galaxy_category_index": 0,
                "system_category_index": 0,
                "galaxy_sort_text": "Name A–Z",
                "system_sort_text": "Default View",
                "galaxy_search": "",
                "system_search": "",
                "galaxy_leader_color": "#00FF80",
                "galaxy_leader_width": 2,
                "galaxy_leader_glow": True,
                "system_leader_color": "#00FF80", 
                "system_leader_width": 2,
                "system_leader_glow": True
            }
        }
    
    def initialize(self) -> bool:
        """
        Initialize the UI state system:
        1. Check if config file exists
        2. Create with defaults if missing  
        3. Load the configuration
        
        Returns True if file existed, False if created new
        """
        file_existed = self._config_path.exists()
        
        if not file_existed:
            logger.info("UI state file not found, creating with defaults: %s", self._config_path)
            self._create_default_config()
        
        self._load_from_disk()
        
        logger.info("UI state initialized from: %s (existed: %s)", self._config_path, file_existed)
        return file_existed
    
    def _create_default_config(self) -> None:
        """Create the config file with default values"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            default_state = self.get_default_state()
            
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(default_state, f, indent=2)
            
            self._state = default_state
            logger.info("Created default UI state configuration")
            
        except Exception as e:
            logger.error("Failed to create default UI state config: %s", e)
            self._state = self.get_default_state()
    
    def _load_from_disk(self) -> None:
        """Load UI state from disk"""
        try:
            self._loading = True
            
            if not self._config_path.exists():
                self._state = self.get_default_state()
                return
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
            
            if not isinstance(loaded_state, dict):
                logger.warning("Invalid UI state format, using defaults")
                self._state = self.get_default_state()
                return
            
            # Merge with defaults to ensure all required keys exist
            default_state = self.get_default_state()
            self._state = self._merge_with_defaults(loaded_state, default_state)
            
            self.stateLoaded.emit()
            
        except Exception as e:
            logger.error("Failed to load UI state, using defaults: %s", e)
            self._state = self.get_default_state()
        finally:
            self._loading = False
    
    def _merge_with_defaults(self, loaded: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded state with defaults to ensure all keys exist"""
        result = defaults.copy()
        
        if not isinstance(loaded, dict):
            return result
            
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                result[key] = value
        
        return result
    
    def _save_to_disk(self) -> None:
        """Save current state to disk"""
        if self.is_save_suspended():
            return
            
        # Collect fresh state from the UI provider before saving
        try:
            from save.ui_config import _UI_STATE_PROVIDER
            if _UI_STATE_PROVIDER:
                fresh_state = _UI_STATE_PROVIDER()
                if fresh_state and isinstance(fresh_state, dict):
                    self.update_main_window_state(fresh_state)
        except Exception as e:
            # Log but don't fail the save
            pass
            
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata
            save_data = self._state.copy()
            save_data["_metadata"] = {
                "last_saved": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            
            # Atomic write
            temp_path = self._config_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
            
            temp_path.replace(self._config_path)
            
            self.stateSaved.emit()
            
        except Exception as e:
            logger.error("Failed to save UI state: %s", e)
    
    def get_window_state(self, window_id: str) -> Dict[str, Any]:
        """Get state for a specific window/panel"""
        return self._state.get(window_id, {})
    
    def update_window_state(self, window_id: str, state: Dict[str, Any]) -> None:
        """Update state for a specific window/panel and trigger save"""
        if self.is_save_suspended():
            return
            
        if window_id not in self._state:
            self._state[window_id] = {}
            
        self._state[window_id].update(state)
        
        # Use drag detection for geometry changes, immediate save for other changes
        if any(key in state for key in ['x', 'y', 'w', 'h', 'floating']):
            # This looks like a geometry change - use drag detection
            self._pending_save = True
            self._drag_timer.start()  # Reset the drag timer
        else:
            # Non-geometry change - save immediately with debouncing
            self._save_timer.start()
    
    def update_window_state_silent(self, window_id: str, state: Dict[str, Any]) -> None:
        """Update state without triggering a save (for programmatic changes)"""
        if window_id not in self._state:
            self._state[window_id] = {}
            
        self._state[window_id].update(state)
    
    def get_main_window_state(self) -> Dict[str, Any]:
        """Get MainWindow specific state"""
        return self.get_window_state("MainWindow")
    
    def update_main_window_state(self, state: Dict[str, Any]) -> None:
        """Update MainWindow specific state"""
        self.update_window_state("MainWindow", state)
    
    def set_dock_visible(self, dock_name: str, visible: bool) -> None:
        """Update dock visibility and save immediately"""
        if self.is_save_suspended():
            return
            
        main_state = self.get_main_window_state()
        if "dock_visibility" not in main_state:
            main_state["dock_visibility"] = {}
        
        # Check if value has actually changed
        current_visible = main_state["dock_visibility"].get(dock_name)
        if current_visible == visible:
            return  # No change, skip update
        
        main_state["dock_visibility"][dock_name] = visible
        self.update_main_window_state({"dock_visibility": main_state["dock_visibility"]})
    
    def is_dock_visible(self, dock_name: str, default: bool = True) -> bool:
        """Check if a dock should be visible"""
        main_state = self.get_main_window_state()
        dock_vis = main_state.get("dock_visibility", {})
        return dock_vis.get(dock_name, default)
    
    def set_dock_geometry(self, dock_name: str, x: int, y: int, width: int, height: int, 
                         floating: bool = False, visible: bool = True) -> None:
        """Update dock geometry and save after drag finishes"""
        if self.is_save_suspended():
            return
            
        main_state = self.get_main_window_state()
        if "dock_layout" not in main_state:
            main_state["dock_layout"] = {}
            
        # Check if values have actually changed
        current_dock_data = main_state["dock_layout"].get(dock_name, {})
        new_dock_data = {
            "x": x,
            "y": y, 
            "w": width,
            "h": height,
            "floating": floating,
            "open": visible
        }
        
        # Only update if something actually changed
        if current_dock_data == new_dock_data:
            return  # No changes, skip update
        
        # Update the state data directly
        main_state["dock_layout"][dock_name] = new_dock_data
        if "MainWindow" not in self._state:
            self._state["MainWindow"] = {}
        self._state["MainWindow"].update({"dock_layout": main_state["dock_layout"]})
        
        # Use drag detection for dock moves/resizes - don't save immediately
        self._pending_save = True
        self._drag_timer.start()
    
    def get_dock_geometry(self, dock_name: str) -> Optional[Dict[str, Any]]:
        """Get dock geometry settings"""
        main_state = self.get_main_window_state()
        dock_layout = main_state.get("dock_layout", {})
        return dock_layout.get(dock_name)
    
    def force_save(self) -> None:
        """Force immediate save to disk"""        
        self._save_timer.stop()
        self._save_to_disk()


# Global instance
_ui_state_manager: Optional[UIStateManager] = None

def get_ui_state_manager() -> UIStateManager:
    """Get the global UI state manager instance"""
    global _ui_state_manager
    if _ui_state_manager is None:
        _ui_state_manager = UIStateManager()
    return _ui_state_manager

def initialize_ui_state() -> bool:
    """Initialize the UI state system - call this at app startup"""
    manager = get_ui_state_manager()
    return manager.initialize()
