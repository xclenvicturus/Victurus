# /ui/widgets/actions_panel.py

"""
Actions Panel Widget

Displays contextual action buttons based on player's current location and situation.
Shows different actions like Refuel, Repair, Market, Missions, etc. when docked at stations,
or other relevant actions based on current context.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from game_controller.log_config import get_ui_logger
from game import player_status

logger = get_ui_logger('actions_panel')


class ActionsPanel(QWidget):
    """
    Contextual actions panel that shows relevant buttons based on player location and status.
    Docked on the left side under the status sheet.
    """
    
    # Signal emitted when an action button is pressed
    action_triggered = Signal(str, dict)  # action_name, context_data
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Current context state
        self._current_context = {}
        self._current_actions = []
        
        self._setup_ui()
        self._create_default_actions()
        self.refresh()
    
    def _setup_ui(self):
        """Setup the UI layout and components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Title
        title_label = QLabel("Actions")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # Scroll area for buttons (in case we have many actions)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Container widget for buttons
        self.actions_container = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(4, 4, 4, 4)
        self.actions_layout.setSpacing(4)
        
        self.scroll_area.setWidget(self.actions_container)
        main_layout.addWidget(self.scroll_area)
        
        # Add stretch to push everything to the top
        main_layout.addStretch(1)
        
        # Store buttons for easy access
        self._action_buttons = {}
    
    def _create_default_actions(self):
        """Create default placeholder actions for testing"""
        self._action_definitions = {
            # Station actions (when docked at a station)
            'station_actions': [
                {'name': 'refuel', 'label': 'Refuel Ship', 'description': 'Refuel your ship to maximum capacity'},
                {'name': 'repair', 'label': 'Repair Ship', 'description': 'Repair hull and shield damage'},
                {'name': 'market', 'label': 'Commodities Market', 'description': 'Buy and sell commodities'},
                {'name': 'missions', 'label': 'Mission Board', 'description': 'Accept new missions'},
                {'name': 'hangar', 'label': 'Hangar Services', 'description': 'Manage ships and equipment'},
                {'name': 'outfitting', 'label': 'Outfitting', 'description': 'Upgrade ship modules'},
            ],
            
            # Planet actions (when orbiting a planet)
            'planet_actions': [
                {'name': 'scan_surface', 'label': 'Surface Scan', 'description': 'Scan planet surface for resources'},
                {'name': 'deploy_srv', 'label': 'Deploy SRV', 'description': 'Deploy surface reconnaissance vehicle'},
                {'name': 'land', 'label': 'Request Landing', 'description': 'Request permission to land'},
            ],
            
            # Space actions (when in open space)
            'space_actions': [
                {'name': 'scan_system', 'label': 'System Scan', 'description': 'Perform detailed system scan'},
                {'name': 'navigation', 'label': 'Navigation', 'description': 'Open navigation computer'},
                {'name': 'inventory', 'label': 'Inventory', 'description': 'Manage ship inventory'},
            ],
            
            # Emergency actions (always available)
            'emergency_actions': [
                {'name': 'emergency_stop', 'label': 'Emergency Stop', 'description': 'Emergency stop all ship systems'},
                {'name': 'distress_call', 'label': 'Distress Call', 'description': 'Send distress signal'},
            ],
        }
    
    def refresh(self):
        """Refresh the actions panel based on current player context"""
        try:
            # Get current player status
            status = player_status.get_status_snapshot() or {}
            
            # Determine current context
            new_context = self._determine_context(status)
            
            # Only update if context changed
            if new_context != self._current_context:
                self._current_context = new_context
                self._update_actions()
                
                logger.debug(f"Actions panel context updated: {new_context.get('type', 'unknown')}")
        
        except Exception as e:
            logger.error(f"Error refreshing actions panel: {e}")
    
    def _determine_context(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the current context based on player status"""
        # Use the same location resolution logic as StatusSheet
        location = (
            status.get('display_location') or
            status.get('location_name') or  # fallback
            status.get('system_name') or
            'Unknown'
        )
        
        context = {
            'type': 'space',  # Default context
            'location_name': location,
            'system_name': status.get('system_name', 'Unknown System'),
            'ship_status': status.get('status', 'Unknown'),
        }
        
        # Determine context type based on location and status
        ship_status = status.get('status', '').lower()
        location_lower = location.lower()
        
        if 'docked' in ship_status or 'station' in location_lower:
            context['type'] = 'station'
            context['station_name'] = location
        elif 'orbit' in ship_status and 'planet' in location_lower:
            context['type'] = 'planet'
            context['planet_name'] = location
        elif 'orbit' in ship_status and 'moon' in location_lower:
            context['type'] = 'moon'
            context['moon_name'] = location
        else:
            context['type'] = 'space'
        
        return context
    
    def _update_actions(self):
        """Update the displayed actions based on current context"""
        # Clear existing buttons
        self._clear_actions()
        
        # Determine which actions to show
        actions_to_show = []
        context_type = self._current_context.get('type', 'space')
        
        if context_type == 'station':
            actions_to_show.extend(self._action_definitions['station_actions'])
        elif context_type in ['planet', 'moon']:
            actions_to_show.extend(self._action_definitions['planet_actions'])
        else:
            actions_to_show.extend(self._action_definitions['space_actions'])
        
        # Always add some emergency actions at the bottom
        if actions_to_show:  # Add separator if we have other actions
            self._add_separator()
        actions_to_show.extend(self._action_definitions['emergency_actions'][:1])  # Just emergency stop for now
        
        # Create buttons for selected actions
        for action_def in actions_to_show:
            self._create_action_button(action_def)
        
        # Update the layout
        self.actions_layout.addStretch(1)
    
    def _clear_actions(self):
        """Clear all current action buttons"""
        # Remove all widgets from layout except the last stretch
        while self.actions_layout.count() > 0:
            child = self.actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self._action_buttons.clear()
    
    def _add_separator(self):
        """Add a separator line between action groups"""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setMaximumHeight(2)
        self.actions_layout.addWidget(separator)
    
    def _create_action_button(self, action_def: Dict[str, str]):
        """Create a button for the given action definition"""
        button = QPushButton(action_def['label'])
        button.setToolTip(action_def['description'])
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(32)
        
        # Connect button to action handler
        action_name = action_def['name']
        button.clicked.connect(lambda: self._on_action_triggered(action_name, action_def))
        
        # Store button reference
        self._action_buttons[action_name] = button
        
        # Add to layout
        self.actions_layout.addWidget(button)
    
    def _on_action_triggered(self, action_name: str, action_def: Dict[str, str]):
        """Handle when an action button is clicked"""
        try:
            # Log the action for now (placeholder functionality)
            context_type = self._current_context.get('type', 'unknown')
            location = self._current_context.get('location_name', 'Unknown')
            
            logger.info(f"Action triggered: {action_name} ({action_def['label']}) "
                       f"in {context_type} context at {location}")
            
            # Emit signal with action data
            action_data = {
                'action_name': action_name,
                'action_label': action_def['label'],
                'action_description': action_def['description'],
                'context': self._current_context.copy()
            }
            
            self.action_triggered.emit(action_name, action_data)
            
            # For now, just show a placeholder message
            print(f"🎮 ACTION: {action_def['label']} - {action_def['description']}")
            print(f"   Context: {context_type.title()} at {location}")
            print(f"   [This is a placeholder - feature will be implemented later]")
            print()
            
        except Exception as e:
            logger.error(f"Error handling action {action_name}: {e}")
    
    def get_available_actions(self) -> List[str]:
        """Get list of currently available action names"""
        return list(self._action_buttons.keys())
    
    def trigger_action(self, action_name: str) -> bool:
        """Programmatically trigger an action by name"""
        if action_name in self._action_buttons:
            button = self._action_buttons[action_name]
            button.click()
            return True
        return False
