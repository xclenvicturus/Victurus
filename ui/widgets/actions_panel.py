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
from data import db

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
        """Create action definitions organized by context and status"""
        self._action_definitions = {
            # Station actions - available when orbiting or docked at stations
            'station_orbiting': [
                {'name': 'dock_at_station', 'label': 'Request Docking', 'description': 'Request permission to dock at station'},
                {'name': 'scan_station', 'label': 'Scan Station', 'description': 'Scan station services and facilities'},
                {'name': 'hail_station', 'label': 'Hail Station', 'description': 'Open communication with station'},
            ],
            'station_docked': [
                # Dynamic actions - will be populated based on actual facilities
                {'name': 'undock', 'label': 'Undock', 'description': 'Leave the station and enter orbit'},
                {'name': 'missions', 'label': 'Mission Board', 'description': 'Access the station mission board'},
                {'name': 'staff', 'label': 'Station Staff', 'description': 'Speak with station personnel'},
                # Facility-specific actions added dynamically in _get_station_docked_actions()
            ],
            
            # Planet actions - available when orbiting planets
            'planet_orbiting': [
                {'name': 'dock_at_planet', 'label': 'Request Landing', 'description': 'Request permission to land on planet surface'},
                {'name': 'surface_scan', 'label': 'Surface Scan', 'description': 'Scan planet surface for resources and settlements'},
                {'name': 'orbital_survey', 'label': 'Orbital Survey', 'description': 'Perform detailed orbital survey'},
            ],
            'planet_docked': [
                {'name': 'launch', 'label': 'Launch', 'description': 'Launch from planet surface to orbit'},
                {'name': 'surface_ops', 'label': 'Surface Operations', 'description': 'Perform surface mining and exploration'},
                {'name': 'settlements', 'label': 'Visit Settlements', 'description': 'Visit planetary settlements and outposts'},
            ],
            
            # Moon actions - available when orbiting moons
            'moon_orbiting': [
                {'name': 'land_on_moon', 'label': 'Land on Moon', 'description': 'Land on the moon surface'},
                {'name': 'moon_survey', 'label': 'Moon Survey', 'description': 'Survey moon for resources'},
            ],
            'moon_docked': [
                {'name': 'launch_from_moon', 'label': 'Launch', 'description': 'Launch from moon surface to orbit'},
                {'name': 'moon_mining', 'label': 'Mining Operations', 'description': 'Conduct mining operations'},
            ],
            
            # Asteroid field actions
            'asteroid_field_orbiting': [
                {'name': 'asteroid_mining', 'label': 'Start Mining', 'description': 'Begin asteroid mining operations'},
                {'name': 'prospect_asteroids', 'label': 'Prospect Asteroids', 'description': 'Survey asteroids for valuable materials'},
            ],
            
            # Gas cloud actions  
            'gas_clouds_orbiting': [
                {'name': 'fuel_scooping', 'label': 'Fuel Scooping', 'description': 'Scoop fuel from gas clouds'},
                {'name': 'gas_harvesting', 'label': 'Gas Harvesting', 'description': 'Harvest rare gases'},
            ],
            
            # Ice field actions
            'ice_field_orbiting': [
                {'name': 'ice_mining', 'label': 'Ice Mining', 'description': 'Mine water ice for fuel and supplies'},
                {'name': 'ice_processing', 'label': 'Process Ice', 'description': 'Process ice into fuel and water'},
            ],
            
            # Crystal vein actions
            'crystal_vein_orbiting': [
                {'name': 'crystal_mining', 'label': 'Crystal Mining', 'description': 'Mine valuable crystals'},
                {'name': 'crystal_analysis', 'label': 'Crystal Analysis', 'description': 'Analyze crystal composition'},
            ],
            
            # Warp gate actions
            'warp_gate_orbiting': [
                {'name': 'use_warp_gate', 'label': 'Use Warp Gate', 'description': 'Travel through the warp gate'},
                {'name': 'gate_diagnostics', 'label': 'Gate Diagnostics', 'description': 'Run diagnostics on warp gate'},
            ],
            
            # Star actions - when near the star
            'star_orbiting': [
                {'name': 'stellar_observation', 'label': 'Stellar Observation', 'description': 'Study stellar phenomena'},
                {'name': 'solar_collection', 'label': 'Solar Energy Collection', 'description': 'Collect solar energy'},
            ],
            
            # Open space actions (when not near any specific location)
            'space_traveling': [
                {'name': 'navigation', 'label': 'Navigation', 'description': 'Open navigation computer'},
                {'name': 'scan_system', 'label': 'System Scan', 'description': 'Perform broad system scan'},
                {'name': 'inventory', 'label': 'Inventory', 'description': 'Manage ship inventory'},
            ],
            
            # Emergency actions (always available)
            'emergency': [
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
        """Determine the current context based on player status and database information"""
        # Get basic status information
        location_id = status.get('location_id')
        system_id = status.get('system_id')
        
        # Use the same location resolution logic as StatusSheet
        location_name = (
            status.get('display_location') or
            status.get('location_name') or  # fallback
            status.get('system_name') or
            'Unknown'
        )
        
        system_name = status.get('system_name', 'Unknown System')
        ship_status = status.get('status', 'Unknown')
        
        context = {
            'location_id': location_id,
            'system_id': system_id,
            'location_name': location_name,
            'system_name': system_name,
            'ship_status': ship_status,
            'type': 'space',  # Default
            'subtype': 'traveling',  # Default subtype
            'location_type': None,
            'current_status': 'traveling',  # orbiting, docked, traveling
            'facilities': [],
            'can_dock': False,
            'can_undock': False,
        }
        
        try:
            # Get current location status from player_status module
            current_status = player_status.get_location_status().lower()
            context['current_status'] = current_status
            
            # If we have a location_id, get detailed location information
            if location_id:
                location_data = db.get_location(location_id)
                if location_data:
                    location_type = location_data.get('location_type', 'unknown')
                    context['location_type'] = location_type
                    context['type'] = location_type
                    
                    # Determine context based on location type and status
                    if location_type == 'station':
                        if current_status == 'docked':
                            context['subtype'] = 'docked'
                            context['can_undock'] = True
                        else:  # orbiting
                            context['subtype'] = 'orbiting'
                            context['can_dock'] = True
                            
                    elif location_type in ['planet', 'moon']:
                        if current_status == 'docked':  # landed
                            context['subtype'] = 'docked'
                            context['can_undock'] = True
                        else:  # orbiting
                            context['subtype'] = 'orbiting'
                            context['can_dock'] = True
                            
                    elif location_type in ['asteroid_field', 'gas_clouds', 'ice_field', 'crystal_vein', 'warp_gate', 'star']:
                        # These locations are typically orbit-only
                        context['subtype'] = 'orbiting'
                        context['can_dock'] = False
                        
                    # Get available facilities at this location
                    try:
                        conn = db.get_connection()
                        facilities = conn.execute("""
                            SELECT facility_type, notes 
                            FROM facilities 
                            WHERE location_id = ?
                        """, (location_id,)).fetchall()
                        
                        context['facilities'] = [
                            {'type': f['facility_type'], 'notes': f.get('notes')} 
                            for f in facilities
                        ]
                    except Exception:
                        # Facilities table might not exist or be accessible
                        context['facilities'] = []
                        
            else:
                # No specific location - we're in open space
                context['type'] = 'space'
                context['subtype'] = 'traveling'
                context['current_status'] = 'traveling'
                
        except Exception as e:
            logger.warning(f"Error determining detailed context: {e}")
            # Fall back to basic string-based detection for compatibility
            ship_status_lower = ship_status.lower()
            location_lower = location_name.lower()
            
            if 'docked' in ship_status_lower:
                context['current_status'] = 'docked'
                context['subtype'] = 'docked'
                context['can_undock'] = True
                
                if 'station' in location_lower:
                    context['type'] = 'station'
                elif 'planet' in location_lower:
                    context['type'] = 'planet'
                elif 'moon' in location_lower:
                    context['type'] = 'moon'
                    
            elif 'orbit' in ship_status_lower:
                context['current_status'] = 'orbiting'
                context['subtype'] = 'orbiting'
                
                if 'station' in location_lower:
                    context['type'] = 'station'
                    context['can_dock'] = True
                elif 'planet' in location_lower:
                    context['type'] = 'planet'
                    context['can_dock'] = True
                elif 'moon' in location_lower:
                    context['type'] = 'moon'
                    context['can_dock'] = True
                    
        return context
    
    def _update_actions(self):
        """Update the displayed actions based on current context"""
        # Clear existing buttons
        self._clear_actions()
        
        # Determine which actions to show based on context
        actions_to_show = []
        context_type = self._current_context.get('type', 'space')
        context_subtype = self._current_context.get('subtype', 'traveling')
        current_status = self._current_context.get('current_status', 'traveling')
        
        # Build the action key based on type and status
        action_key = None
        
        if context_type == 'station':
            if current_status == 'docked':
                action_key = 'station_docked'
            else:  # orbiting
                action_key = 'station_orbiting'
                
        elif context_type == 'planet':
            if current_status == 'docked':  # landed
                action_key = 'planet_docked'
            else:  # orbiting
                action_key = 'planet_orbiting'
                
        elif context_type == 'moon':
            if current_status == 'docked':  # landed
                action_key = 'moon_docked'
            else:  # orbiting
                action_key = 'moon_orbiting'
                
        elif context_type == 'asteroid_field':
            action_key = 'asteroid_field_orbiting'
            
        elif context_type == 'gas_clouds':
            action_key = 'gas_clouds_orbiting'
            
        elif context_type == 'ice_field':
            action_key = 'ice_field_orbiting'
            
        elif context_type == 'crystal_vein':
            action_key = 'crystal_vein_orbiting'
            
        elif context_type == 'warp_gate':
            action_key = 'warp_gate_orbiting'
            
        elif context_type == 'star':
            action_key = 'star_orbiting'
            
        else:  # space or unknown
            action_key = 'space_traveling'
        
        # Get actions for the determined context
        if action_key and action_key in self._action_definitions:
            if action_key == 'station_docked':
                # For docked stations, get dynamic facility-based actions
                actions_to_show.extend(self._get_station_docked_actions())
            else:
                actions_to_show.extend(self._action_definitions[action_key])
                
            logger.debug(f"Showing {action_key} actions: {[a['name'] for a in actions_to_show]}")
        
        # Always add emergency actions at the bottom
        if actions_to_show:  # Add separator if we have other actions
            self._add_separator()
        actions_to_show.extend(self._action_definitions['emergency'][:1])  # Just emergency stop for now
        
        # Create buttons for selected actions
        for action_def in actions_to_show:
            self._create_action_button(action_def)
        
        # Update the layout
        self.actions_layout.addStretch(1)
    
    def _get_station_docked_actions(self) -> List[Dict[str, str]]:
        """Get dynamic actions for when docked at a station based on available services"""
        actions = []
        
        # Always available actions first
        actions.extend(self._action_definitions['station_docked'])
        
        # Get available services at this station
        location_id = self._current_context.get('location_id')
        if location_id:
            available_services = db.get_station_services(location_id)
            logger.debug(f"Station {location_id} has services: {available_services}")
            
            # Add service-specific actions based on actual facility availability
            service_actions = {
                'refuel': {
                    'name': 'refuel', 
                    'label': 'Refuel Ship', 
                    'description': 'Refuel your ship to maximum capacity'
                },
                'repair': {
                    'name': 'repair', 
                    'label': 'Repair Ship', 
                    'description': 'Repair hull and shield damage'
                },
                'market': {
                    'name': 'market', 
                    'label': 'Commodities Market', 
                    'description': 'Buy and sell commodities'
                },
                'outfitting': {
                    'name': 'outfitting', 
                    'label': 'Ship Outfitting', 
                    'description': 'Upgrade ship modules and equipment'
                },
                'storage': {
                    'name': 'storage', 
                    'label': 'Storage Vault', 
                    'description': 'Access personal storage'
                },
                'medical': {
                    'name': 'medical', 
                    'label': 'Medical Bay', 
                    'description': 'Medical and crew services'
                }
            }
            
            # Add available service actions
            for service in available_services:
                if service in service_actions:
                    actions.append(service_actions[service])
            
            # Add production facility actions (existing manufacturing/mining logic)
            facilities = self._current_context.get('facilities', [])
            facility_types = [f.get('type', '').lower() for f in facilities]
            
            # Manufacturing
            if any(ftype in ['factory', 'manufacturing', 'production'] for ftype in facility_types):
                actions.append({
                    'name': 'manufacturing', 
                    'label': 'Manufacturing', 
                    'description': 'Access manufacturing facilities'
                })
            
            # Fabricator access
            if any(ftype == 'fabricator' for ftype in facility_types):
                actions.append({
                    'name': 'fabricator', 
                    'label': 'Fabricator', 
                    'description': 'Custom manufacturing services'
                })
            
            # Mining/Processing
            if any(ftype in ['mine', 'refinery', 'processing'] for ftype in facility_types):
                actions.append({
                    'name': 'processing', 
                    'label': 'Ore Processing', 
                    'description': 'Process raw materials and ores'
                })
            
            # Research
            if any(ftype in ['research', 'lab', 'laboratory'] for ftype in facility_types):
                actions.append({
                    'name': 'research', 
                    'label': 'Research Lab', 
                    'description': 'Access research and development facilities'
                })
            
            # Agricultural
            if any(ftype in ['agridome', 'agriculture', 'farming'] for ftype in facility_types):
                actions.append({
                    'name': 'agriculture', 
                    'label': 'Agricultural Center', 
                    'description': 'Visit agricultural facilities and food production'
                })
        else:
            logger.warning("No location_id available for station service check")
        
        return actions
    
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
            # Get detailed context information
            context_type = self._current_context.get('type', 'unknown')
            context_subtype = self._current_context.get('subtype', 'unknown')
            current_status = self._current_context.get('current_status', 'unknown')
            location_name = self._current_context.get('location_name', 'Unknown')
            location_type = self._current_context.get('location_type')
            facilities = self._current_context.get('facilities', [])
            
            logger.info(f"Action triggered: {action_name} ({action_def['label']}) "
                       f"at {location_name} ({context_type}/{context_subtype}, status: {current_status})")
            
            # Handle specific actions that have immediate game effects
            if action_name == 'dock_at_station' and self._current_context.get('can_dock'):
                self._handle_docking_action()
            elif action_name == 'undock' and self._current_context.get('can_undock'):
                self._handle_undocking_action()
            elif action_name == 'dock_at_planet' and self._current_context.get('can_dock'):
                self._handle_landing_action()
            elif action_name in ['launch', 'launch_from_moon'] and self._current_context.get('can_undock'):
                self._handle_launch_action()
            
            # Emit signal with comprehensive action data
            action_data = {
                'action_name': action_name,
                'action_label': action_def['label'],
                'action_description': action_def['description'],
                'context': self._current_context.copy(),
                'location_type': location_type,
                'facilities': facilities,
                'timestamp': player_status.get_status_snapshot().get('system_time', 'Unknown'),
            }
            
            self.action_triggered.emit(action_name, action_data)
            
            # Enhanced placeholder feedback
            print(f"🎮 ACTION: {action_def['label']} - {action_def['description']}")
            print(f"   Location: {location_name} ({context_type})")
            print(f"   Status: {current_status.title()} → {context_subtype}")
            if location_type:
                print(f"   Location Type: {location_type}")
            if facilities:
                facility_types = [f['type'] for f in facilities]
                print(f"   Available Facilities: {', '.join(facility_types)}")
            print(f"   [Enhanced context-aware action - feature ready for implementation]")
            print()
            
        except Exception as e:
            logger.error(f"Error handling action {action_name}: {e}")
    
    def _handle_docking_action(self):
        """Handle docking at a station with full communication sequence"""
        try:
            location_id = self._current_context.get('location_id')
            location_name = self._current_context.get('location_name', 'Unknown Station')
            
            if not location_id:
                logger.error("No location_id available for docking")
                return
            
            # Get station data including facilities
            station_data = self._get_station_data(location_id)
            
            # Import the communication dialog
            from ui.dialogs.station_comm_dialog import StationCommDialog
            
            # Show communication dialog
            comm_dialog = StationCommDialog(location_name, station_data, self.parent())
            comm_dialog.docking_approved.connect(lambda: self._complete_docking(location_id))
            comm_dialog.docking_denied.connect(lambda reason: self._handle_docking_denied(reason))
            
            comm_dialog.exec()
            
        except Exception as e:
            logger.error(f"Error handling docking: {e}")
    
    def _get_station_data(self, location_id: int) -> Dict[str, Any]:
        """Get comprehensive station data including facilities"""
        try:
            # Get basic location info
            location_data = db.get_location(location_id) or {}
            
            # Get facilities at this location
            conn = db.get_connection()
            facilities = conn.execute("""
                SELECT facility_type, notes 
                FROM facilities 
                WHERE location_id = ?
            """, (location_id,)).fetchall()
            
            facilities_list = [
                {'type': dict(f)['facility_type'], 'notes': dict(f).get('notes', '')} 
                for f in facilities
            ]
            
            return {
                'location_id': location_id,
                'location_data': dict(location_data) if location_data else {},
                'facilities': facilities_list
            }
            
        except Exception as e:
            logger.warning(f"Error getting station data: {e}")
            return {
                'location_id': location_id,
                'location_data': {},
                'facilities': []
            }
    
    def _complete_docking(self, location_id: int):
        """Complete the docking process after communication approval"""
        try:
            player_status.dock_at_location(location_id)
            logger.info(f"Successfully completed docking at station {location_id}")
            
            # Refresh the actions panel to show docked actions
            self.refresh()
            
        except Exception as e:
            logger.error(f"Error completing docking: {e}")
    
    def _handle_docking_denied(self, reason: str):
        """Handle docking denial"""
        logger.info(f"Docking denied: {reason}")
        # Could show a message to the user here
    
    def _handle_undocking_action(self):
        """Handle undocking from a station with full communication sequence"""
        try:
            location_id = self._current_context.get('location_id')
            location_name = self._current_context.get('location_name', 'Unknown Station')
            
            if not location_id:
                logger.error("No location_id available for undocking")
                return
            
            # Get station data including facilities
            station_data = self._get_station_data(location_id)
            
            # Import the undocking dialog
            from ui.dialogs.station_undock_dialog import StationUndockDialog
            
            # Show undocking communication dialog
            undock_dialog = StationUndockDialog(location_name, station_data, self.parent())
            undock_dialog.undocking_approved.connect(lambda: self._complete_undocking(location_id))
            undock_dialog.undocking_denied.connect(lambda reason: self._handle_undocking_denied(reason))
            
            undock_dialog.exec()
            
        except Exception as e:
            logger.error(f"Error handling undocking: {e}")
    
    def _complete_undocking(self, location_id: int):
        """Complete the undocking process after communication approval"""
        try:
            player_status.enter_orbit(location_id)
            logger.info(f"Successfully completed undocking from station {location_id}")
            
            # Refresh the actions panel to show orbiting actions
            self.refresh()
            
        except Exception as e:
            logger.error(f"Error completing undocking: {e}")
    
    def _handle_undocking_denied(self, reason: str):
        """Handle undocking denial"""
        logger.info(f"Undocking denied: {reason}")
        # Could show a message to the user here
    
    def _handle_landing_action(self):
        """Handle landing on a planet with full ground control communication sequence"""
        try:
            location_id = self._current_context.get('location_id')
            location_name = self._current_context.get('location_name', 'Unknown Planet')
            
            if not location_id:
                logger.error("No location_id available for planet landing")
                return
            
            # Get planet data
            planet_data = self._get_planet_data(location_id)
            
            # Import the planet landing dialog
            from ui.dialogs.planet_landing_dialog import PlanetLandingDialog
            
            # Show ground control communication dialog
            landing_dialog = PlanetLandingDialog(location_name, planet_data, self.parent())
            landing_dialog.landing_approved.connect(lambda: self._complete_landing(location_id))
            landing_dialog.landing_denied.connect(lambda reason: self._handle_landing_denied(reason))
            
            landing_dialog.exec()
            
        except Exception as e:
            logger.error(f"Error handling planet landing: {e}")
    
    def _get_planet_data(self, location_id: int) -> Dict[str, Any]:
        """Get comprehensive planet data"""
        try:
            # Get basic location info
            location_data = db.get_location(location_id) or {}
            
            return {
                'location_id': location_id,
                'location_data': dict(location_data) if location_data else {},
            }
            
        except Exception as e:
            logger.warning(f"Error getting planet data: {e}")
            return {
                'location_id': location_id,
                'location_data': {},
            }
    
    def _complete_landing(self, location_id: int):
        """Complete the planet landing process after ground control approval"""
        try:
            player_status.dock_at_location(location_id)  # "docked" means landed for planets
            logger.info(f"Successfully completed landing on planet {location_id}")
            
            # Refresh the actions panel to show landed actions
            self.refresh()
            
        except Exception as e:
            logger.error(f"Error completing planet landing: {e}")
    
    def _handle_landing_denied(self, reason: str):
        """Handle planet landing denial"""
        logger.info(f"Planet landing denied: {reason}")
        # Could show a message to the user here
    
    def _handle_launch_action(self):
        """Handle launching from a planet/moon surface with full launch control communication sequence"""
        try:
            location_id = self._current_context.get('location_id')
            location_name = self._current_context.get('location_name', 'Unknown Planet')
            
            if not location_id:
                logger.error("No location_id available for planet launch")
                return
            
            # Get planet data
            planet_data = self._get_planet_data(location_id)
            
            # Import the planet launch dialog
            from ui.dialogs.planet_launch_dialog import PlanetLaunchDialog
            
            # Show launch control communication dialog
            launch_dialog = PlanetLaunchDialog(location_name, planet_data, self.parent())
            launch_dialog.launch_approved.connect(lambda: self._complete_launch(location_id))
            launch_dialog.launch_denied.connect(lambda reason: self._handle_launch_denied(reason))
            
            launch_dialog.exec()
            
        except Exception as e:
            logger.error(f"Error handling planet launch: {e}")
    
    def _complete_launch(self, location_id: int):
        """Complete the planet launch process after launch control approval"""
        try:
            player_status.enter_orbit(location_id)
            logger.info(f"Successfully completed launch from planet {location_id}")
            
            # Refresh the actions panel to show orbiting actions
            self.refresh()
            
        except Exception as e:
            logger.error(f"Error completing planet launch: {e}")
    
    def _handle_launch_denied(self, reason: str):
        """Handle planet launch denial"""
        logger.info(f"Planet launch denied: {reason}")
        # Could show a message to the user here
    
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
