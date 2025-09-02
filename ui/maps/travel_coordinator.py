# /ui/maps/travel_coordinator.py

"""
Travel Visualization Coordinator

Coordinates between the TravelFlow system and map visualizations to show
real-time travel paths and progress indicators on both galaxy and system maps.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal

from game.travel_flow import TravelFlow
from game import player_status
import logging
from game_controller.log_config import get_travel_logger

if TYPE_CHECKING:
    from .galaxy import GalaxyMapWidget
    from .system import SystemMapWidget

logger = get_travel_logger('travel_coordinator')


class TravelCoordinator(QObject):
    """
    Coordinates travel visualization across galaxy and system maps.
    
    Connects to TravelFlow signals and updates map visualizations with
    travel paths and progress in real-time.
    """
    
    # Signals for external components
    travelStarted = Signal(str, int)  # dest_type, dest_id
    travelCompleted = Signal()
    pathCalculated = Signal(bool)  # True if path was successfully calculated
    
    def __init__(self):
        super().__init__()
        self._galaxy_map: Optional[GalaxyMapWidget] = None
        self._system_map: Optional[SystemMapWidget] = None
        self._travel_flow: Optional[TravelFlow] = None
        
        # Current travel state
        self._active_travel = False
        self._dest_type: Optional[str] = None
        self._dest_id: Optional[int] = None
        
        # Progress tracking
        self._travel_start_time: Optional[float] = None
        self._total_travel_time: Optional[float] = None
        
    def set_galaxy_map(self, galaxy_map: GalaxyMapWidget) -> None:
        """Set the galaxy map widget to receive travel visualizations"""
        self._galaxy_map = galaxy_map
        logger.info(f"Galaxy map connected to travel coordinator: {galaxy_map}")
        
    def set_system_map(self, system_map: SystemMapWidget) -> None:
        """Set the system map widget to receive travel visualizations"""
        self._system_map = system_map
        logger.info(f"System map connected to travel coordinator: {system_map}")
        
    def set_travel_flow(self, travel_flow: TravelFlow) -> None:
        """
        Set the TravelFlow instance to monitor for travel events.
        Connects to its progress signals.
        """
        logger.debug(f"set_travel_flow called with: {travel_flow}")
        logger.debug(f"TravelCoordinator: Setting travel flow to {travel_flow}")
        
        if self._travel_flow:
            # Disconnect from previous TravelFlow
            try:
                logger.debug(f"Disconnecting from previous travel flow: {self._travel_flow}")
                self._travel_flow.progressTick.disconnect(self._on_progress_tick)
            except Exception:
                pass
                
        self._travel_flow = travel_flow
        logger.debug(f"Set _travel_flow to: {self._travel_flow}")
        
        if travel_flow:
            # Connect to progress signals
            logger.debug(f"Connecting TravelFlow progress tick signal")
            logger.debug(f"Connecting progressTick signal from: {travel_flow}")
            try:
                travel_flow.progressTick.connect(self._on_progress_tick)
                logger.debug(f"Successfully connected to progressTick signal")
            except Exception as e:
                logger.error(f"Failed to connect progressTick signal: {e}")
        else:
            logger.warning(f"travel_flow is None!")
            
    def begin_travel_visualization(self, dest_type: str, dest_id: int) -> bool:
        """
        Start travel visualization for a destination.
        
        Args:
            dest_type: "star" for system star, "loc" for location
            dest_id: System ID or Location ID
            
        Returns:
            True if visualization was successfully started
        """
        logger.debug(f"begin_travel_visualization({dest_type}, {dest_id}) called")
        logger.debug(f"TravelCoordinator: begin_travel_visualization({dest_type}, {dest_id})")
        logger.debug(f"TravelCoordinator.begin_travel_visualization({dest_type}, {dest_id})")
        try:
            self._dest_type = dest_type
            self._dest_id = dest_id
            
            # Calculate paths on both maps but show only on appropriate map initially
            path_calculated = False
            
            # Calculate paths for both maps
            try:
                if self._galaxy_map:
                    logger.debug(f"Calling galaxy_map.show_travel_path")
                    if self._galaxy_map.show_travel_path(dest_type, dest_id):
                        path_calculated = True
                        logger.debug(f"Galaxy map path calculated successfully")
            except Exception as e:
                logger.error(f"Error calculating galaxy travel path: {e}")
                    
            try:
                if self._system_map:
                    logger.debug(f"Calling system_map.show_travel_path")
                    if self._system_map.show_travel_path(dest_type, dest_id):
                        path_calculated = True
                        logger.debug(f"System map path calculated successfully")
            except Exception as e:
                logger.error(f"Error calculating system travel path: {e}")
                
            # Initially hide paths and let progress ticks control visibility based on stage
            if path_calculated:
                # Determine initial stage and hide the non-active map
                initial_stage = self._get_current_travel_stage()
                logger.debug(f"Initial travel stage: {initial_stage}")
                if initial_stage == "cruise":
                    # Hide galaxy map for initial cruise stage
                    try:
                        if self._galaxy_map:
                            logger.debug(f"Hiding galaxy map for cruise stage")
                            self._galaxy_map.hide_travel_path()
                    except Exception as e:
                        logger.error(f"Error hiding initial galaxy path: {e}")
                elif initial_stage == "warp":
                    # Hide system map for initial warp stage  
                    try:
                        if self._system_map:
                            logger.debug(f"Hiding system map for warp stage")
                            self._system_map.hide_travel_path()
                    except Exception as e:
                        logger.error(f"Error hiding initial system path: {e}")
                        
            if path_calculated:
                logger.debug(f"Setting _active_travel = True - instance id: {id(self)}")
                self._active_travel = True
                self._travel_start_time = None  # Will be set on first progress tick
                logger.debug(f"Travel visualization started for {dest_type} {dest_id}")
                logger.debug(f"Travel visualization started successfully")
                
                # Get estimated travel time from one of the visualizations
                try:
                    if self._galaxy_map:
                        viz = self._galaxy_map.get_travel_visualization()
                        if viz:
                            path = viz.get_current_path()
                            if path:
                                self._total_travel_time = path.total_time
                except Exception as e:
                    logger.warning(f"Could not get travel time estimate: {e}")
                        
                self.travelStarted.emit(dest_type, dest_id)
                self.pathCalculated.emit(True)
                logger.info(f"Travel visualization started to {dest_type} {dest_id}")
                return True
            else:
                self.pathCalculated.emit(False)
                logger.warning(f"Could not calculate path to {dest_type} {dest_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting travel visualization: {e}")
            self.pathCalculated.emit(False)
            return False
            
    def end_travel_visualization(self) -> None:
        """End current travel visualization and clear paths from maps"""
        try:
            # Try to hide paths on galaxy map
            try:
                if self._galaxy_map:
                    self._galaxy_map.hide_travel_path()
            except Exception as e:
                logger.error(f"Error hiding galaxy travel path: {e}")
                
            # Try to hide paths on system map
            try:
                if self._system_map:
                    self._system_map.hide_travel_path()
            except Exception as e:
                logger.error(f"Error hiding system travel path: {e}")
                
            self._active_travel = False
            self._dest_type = None
            self._dest_id = None
            self._travel_start_time = None
            self._total_travel_time = None
            
            self.travelCompleted.emit()
            logger.info("Travel visualization completed")
            
        except Exception as e:
            logger.error(f"Error ending travel visualization: {e}")
            # Even if there are errors, mark travel as inactive
            self._active_travel = False
            
    def is_travel_active(self) -> bool:
        """Check if travel visualization is currently active"""
        return self._active_travel
        
    def get_current_destination(self) -> Optional[tuple[str, int]]:
        """Get current travel destination as (dest_type, dest_id) or None"""
        if self._active_travel and self._dest_type is not None and self._dest_id is not None:
            return (self._dest_type, self._dest_id)
        return None
        
    def _on_progress_tick(self) -> None:
        """Handle progress tick from TravelFlow"""
        if not self._active_travel or not self._travel_flow:
            return
            
        try:
            # Calculate progress based on travel flow state
            progress = self._calculate_travel_progress()
            current_stage = self._get_current_travel_stage()
            logger.debug(f"TravelCoordinator progress tick: {progress:.3f}, stage: {current_stage}")
            
            # Update maps based on current travel stage
            if current_stage == "warp":
                # Show progress on galaxy map only (line eating)
                # Re-show path if it was hidden
                try:
                    if self._galaxy_map and self._dest_type and self._dest_id:
                        # Make sure path is visible before updating progress
                        logger.debug(f"Warp stage - showing galaxy map path and updating progress")
                        self._galaxy_map.show_travel_path(self._dest_type, self._dest_id)
                        self._galaxy_map.update_travel_progress(progress)
                except Exception as e:
                    logger.error(f"Error updating galaxy map progress: {e}")
                    
                # Hide path on system map during warp
                try:
                    if self._system_map:
                        logger.debug(f"Warp stage - hiding system map")
                        self._system_map.hide_travel_path()
                except Exception as e:
                    logger.error(f"Error hiding system map path during warp: {e}")
                    
            elif current_stage == "cruise":
                # Show progress on system map only (line eating)
                # Re-show path if it was hidden
                try:
                    if self._system_map and self._dest_type and self._dest_id:
                        # Make sure path is visible before updating progress
                        logger.debug(f"Cruise stage - showing system map path and updating progress")
                        self._system_map.show_travel_path(self._dest_type, self._dest_id)
                        self._system_map.update_travel_progress(progress)
                except Exception as e:
                    logger.error(f"Error updating system map progress: {e}")
                    
                # Hide path on galaxy map during cruise
                try:
                    if self._galaxy_map:
                        logger.debug(f"Cruise stage - hiding galaxy map")
                        self._galaxy_map.hide_travel_path()
                except Exception as e:
                    logger.error(f"Error hiding galaxy map path during cruise: {e}")
                    
            else:
                # Transition phases - update both maps for smooth handoff
                try:
                    if self._galaxy_map:
                        self._galaxy_map.update_travel_progress(progress)
                except Exception as e:
                    logger.error(f"Error updating galaxy map progress: {e}")
                    
                try:
                    if self._system_map:
                        self._system_map.update_travel_progress(progress)
                except Exception as e:
                    logger.error(f"Error updating system map progress: {e}")
                
        except Exception as e:
            logger.error(f"Error updating travel progress: {e}")
            # Don't end visualization on progress errors, just log them
            
    def _get_current_travel_stage(self) -> str:
        """
        Determine current travel stage based on TravelFlow phase.
        
        Returns:
            "warp" - Currently in warp travel (galaxy map visualization)
            "cruise" - Currently in cruise travel (system map visualization) 
            "transition" - Transition phases (both maps)
        """
        try:
            if not self._travel_flow:
                logger.debug("No travel_flow, returning 'transition'")
                return "transition"
                
            # Get current phase name from TravelFlow
            current_phase = getattr(self._travel_flow, '_phase_name', '')
            logger.debug(f"TravelFlow phase: '{current_phase}'")
            logger.debug(f"TravelCoordinator: _get_current_travel_stage - phase='{current_phase}'")
            
            # Map phase names to visualization stages
            if current_phase in ['init_warp', 'warping', 'exit_warp']:
                logger.debug(f"Phase '{current_phase}' -> 'warp' stage")
                return "warp"
            elif current_phase in ['cruise_only', 'cruising', 'cruise_to_gate', 'cruise_from_gate', 
                                   'entering_cruise', 'entering_cruise_src', 'entering_cruise_dst']:
                logger.debug(f"Phase '{current_phase}' -> 'cruise' stage") 
                return "cruise"
            else:
                # Phase transitions that need both maps visible
                logger.debug(f"Phase '{current_phase}' -> 'transition' stage")
                return "transition"
                
        except Exception as e:
            logger.error(f"Error determining travel stage: {e}")
            logger.error(f"Exception in _get_current_travel_stage: {e}")
            return "transition"
            
    def _calculate_travel_progress(self) -> float:
        """Calculate current travel progress from 0.0 to 1.0"""
        try:
            if not self._travel_flow:
                return 0.0
                
            # Check if main window is providing manual progress updates
            # Look for main window with persistent travel progress
            if hasattr(self, '_manual_progress_override'):
                return self._manual_progress_override
                
            # Get actual progress from TravelFlow
            try:
                seq = getattr(self._travel_flow, '_seq', [])
                seq_index = getattr(self._travel_flow, '_seq_index', 0)
                phase_timer = getattr(self._travel_flow, '_phase_timer', None)
                phase_duration_ms = getattr(self._travel_flow, '_phase_duration_ms', 0)
                
                if seq and len(seq) > 0:
                    # Calculate overall progress based on sequence completion
                    total_phases = len(seq)
                    completed_phases = min(seq_index, total_phases - 1)
                    
                    # Add progress within current phase
                    phase_progress = 0.0
                    if phase_timer is not None and phase_duration_ms > 0:
                        elapsed = phase_timer.elapsed()
                        phase_progress = min(1.0, elapsed / phase_duration_ms)
                    
                    # Overall progress combines completed phases + current phase progress
                    overall_progress = (completed_phases + phase_progress) / total_phases
                    return max(0.0, min(1.0, overall_progress))
            except Exception as e:
                logger.debug(f"Error getting TravelFlow progress, falling back: {e}")
            
            # Fallback: Try to get progress information from the player status
            from game import player_status
            status = player_status.get_status_snapshot()
            ship_state = status.get("status", "").lower()
            
            # Rough progress estimation based on travel phase
            if "departing" in ship_state or "entering cruise" in ship_state:
                return 0.1
            elif "cruising" in ship_state:
                return 0.4
            elif "leaving cruise" in ship_state or "warping" in ship_state:
                return 0.7
            elif "arriving" in ship_state or "docking" in ship_state:
                return 0.9
            else:
                # Use time-based fallback if we have timing info
                if self._travel_start_time is not None and self._total_travel_time:
                    import time
                    elapsed = (time.time() * 1000) - self._travel_start_time
                    progress = min(1.0, elapsed / self._total_travel_time)
                    return progress
                
                # Return a reasonable default only as last resort
                return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating travel progress: {e}")
            return 0.0
            
    def force_update_progress(self, progress: float) -> None:
        """
        Manually update travel progress (useful for testing or external coordination).
        
        Args:
            progress: Progress from 0.0 to 1.0
        """
        logger.debug(f"force_update_progress({progress:.1%}) - active={self._active_travel} - instance id: {id(self)}")
        if not self._active_travel:
            logger.debug("force_update_progress called but no active travel")
            logger.debug("No active travel, returning")
            return
            
        try:
            progress = max(0.0, min(1.0, progress))
            logger.debug(f"TravelCoordinator: force_update_progress({progress:.1%})")
            logger.debug(f"Processing progress {progress:.1%}")
            
            # Set manual progress override to prevent automatic calculation from interfering
            self._manual_progress_override = progress
            
            # Let each map's PathRenderer handle coordinate system filtering
            # Rather than complex stage detection, just update both maps
            # and let their coordinate_system parameter filter which segments to show
            logger.debug(f"Updating both maps with progress {progress:.1%} - coordinate filtering handles visibility")
            
            if self._galaxy_map:
                self._galaxy_map.update_travel_progress(progress)
            if self._system_map:
                self._system_map.update_travel_progress(progress)
                
        except Exception as e:
            logger.error(f"Error manually updating travel progress: {e}")
            logger.error(f"Exception: {e}")
            
    def clear_manual_progress_override(self) -> None:
        """Clear manual progress override to resume automatic progress calculation"""
        if hasattr(self, '_manual_progress_override'):
            delattr(self, '_manual_progress_override')


# Global instance for coordinating travel visualization
travel_coordinator = TravelCoordinator()
