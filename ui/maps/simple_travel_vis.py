# /ui/maps/simple_travel_vis.py

"""
Simple Travel Status System

Provides travel status information without complex line visualization.
Focuses on progress tracking and phase information.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal

from game_controller.log_config import get_ui_logger
from game import player_status

logger = get_ui_logger('simple_travel_status')


class SimpleTravelStatus(QObject):
    """
    Simple travel status tracker that connects to TravelFlow
    and provides travel progress information.
    """
    
    # Signal emitted when travel status changes
    travel_status_changed = Signal(dict)  # Emits status dict with phase, progress, time_remaining
    
    def __init__(self):
        super().__init__()
        self._travel_flow = None
        self._current_travel_info = None
        
    def set_travel_flow(self, travel_flow) -> None:
        """Connect to TravelFlow for phase monitoring"""
        if self._travel_flow:
            # Disconnect old flow
            try:
                self._travel_flow.progressTick.disconnect(self._on_progress_tick)
            except:
                pass
        
        self._travel_flow = travel_flow
        if travel_flow:
            travel_flow.progressTick.connect(self._on_progress_tick)
    
    def start_travel_tracking(self, dest_type: str, dest_id: int) -> bool:
        """
        Start tracking travel to the given destination.
        
        Args:
            dest_type: "system", "loc", "station", etc.
            dest_id: ID of the destination
            
        Returns:
            True if tracking started successfully
        """
        logger.debug(f"Starting travel tracking to {dest_type} {dest_id}")
        
        self._current_travel_info = {
            'dest_type': dest_type,
            'dest_id': dest_id,
            'phase': 'starting',
            'progress': 0.0,
            'time_remaining': 0
        }
        
        # Emit initial status
        self.travel_status_changed.emit(self._current_travel_info.copy())
        return True
    
    def end_travel_tracking(self) -> None:
        """End current travel tracking"""
        logger.debug("Ending travel tracking")
        self._current_travel_info = None
        
        # Emit empty status to hide travel UI
        self.travel_status_changed.emit({})
    
    def _on_progress_tick(self) -> None:
        """Handle progress ticks from TravelFlow"""
        if not self._travel_flow or not self._current_travel_info:
            return
        
        try:
            # Get current travel phase
            current_phase = getattr(self._travel_flow, '_phase_name', 'unknown')
            
            # Calculate progress
            seq = getattr(self._travel_flow, '_seq', [])
            seq_index = getattr(self._travel_flow, '_seq_index', 0)
            phase_timer = getattr(self._travel_flow, '_phase_timer', None)
            phase_duration_ms = getattr(self._travel_flow, '_phase_duration_ms', 0)
            
            if seq and len(seq) > 0:
                # Get the proper display status from the current phase
                current_phase_data = seq[min(seq_index, len(seq) - 1)] if seq_index < len(seq) else seq[-1]
                display_status = current_phase_data.get('set_state', current_phase)
                
                # Check if we've reached a final destination state - these should not show on travel gauge
                final_states = {'Docked', 'Orbiting', 'Docked at Station', 'Orbiting Planet', 'Orbiting Moon'}
                if display_status in final_states:
                    # Travel is complete - end tracking immediately
                    logger.debug(f"Reached final state '{display_status}' - ending travel tracking")
                    self.end_travel_tracking()
                    return
                
                # Also check if this is the arrive_commit phase (final commit with no duration)
                if current_phase_data.get('name') == 'arrive_commit' or current_phase == 'arrive_commit':
                    logger.debug("Reached arrive_commit phase - ending travel tracking")
                    self.end_travel_tracking()
                    return
                
                # Overall progress based on sequence completion (excluding arrive_commit)
                travel_phases = [p for p in seq if p.get('name') != 'arrive_commit']
                total_phases = len(travel_phases)
                completed_phases = min(seq_index, total_phases - 1)
                
                # Add progress within current phase
                phase_progress = 0.0
                if phase_timer is not None and phase_duration_ms > 0:
                    elapsed = phase_timer.elapsed()
                    phase_progress = min(1.0, elapsed / phase_duration_ms)
                
                # Overall progress
                overall_progress = (completed_phases + phase_progress) / total_phases if total_phases > 0 else 1.0
                
                # Calculate time remaining properly by summing actual phase durations
                remaining_phases = max(0, total_phases - seq_index)
                current_phase_remaining = phase_duration_ms - (phase_timer.elapsed() if phase_timer else 0)
                
                # Sum up the durations of all remaining phases after the current one
                future_phases_time = 0
                if seq_index < len(travel_phases) - 1:  # If there are phases after current
                    for i in range(seq_index + 1, len(travel_phases)):
                        if i < len(seq):
                            future_phase = seq[i]
                            future_phase_duration = future_phase.get('ms', 0)  # Duration is stored in 'ms' field
                            future_phases_time += future_phase_duration
                
                # Total time remaining = current phase remaining + all future phases
                time_remaining = max(0, current_phase_remaining + future_phases_time)
                time_remaining_seconds = int(time_remaining / 1000)
                
                # Update travel info
                self._current_travel_info.update({
                    'phase': display_status or current_phase,  # Use proper display status
                    'progress': overall_progress,
                    'time_remaining': time_remaining_seconds,
                    'total_phases': total_phases,
                    'current_phase_index': seq_index,
                    'phases': [phase.get('set_state', phase.get('name', f'Phase {i}')) 
                              for i, phase in enumerate(travel_phases)]  # Only travel phases
                })
                
                # Emit updated status
                self.travel_status_changed.emit(self._current_travel_info.copy())
                
            # Check if travel is complete
            if seq and seq_index >= len(seq):
                # Travel completed
                logger.debug("Travel completed, ending tracking")
                self.end_travel_tracking()
                
        except Exception as e:
            logger.error(f"Error updating travel progress: {e}")


# Global instance
_simple_travel_status = None

def get_simple_travel_status() -> SimpleTravelStatus:
    """Get the global simple travel status tracker"""
    global _simple_travel_status
    if _simple_travel_status is None:
        _simple_travel_status = SimpleTravelStatus()
    return _simple_travel_status
