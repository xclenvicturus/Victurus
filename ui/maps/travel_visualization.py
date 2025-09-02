# /ui/maps/travel_visualization.py
"""
Travel Path Visualization System

Handles visual representation of travel paths and progress on galaxy and system maps.
Calculates routes, renders path lines, and shows real-time travel progress indicators.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QTimer, Signal, QObject, QRectF
from PySide6.QtGui import QPen, QColor, QPainter, QBrush
from PySide6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPathItem
from PySide6.QtGui import QPainterPath

from data import db
from game import player_status, travel
from game_controller.log_config import get_travel_logger

# Set up travel system logger
logger = get_travel_logger('travel_visualization')


@dataclass
@dataclass
@dataclass
class PathSegment:
    """Represents a segment of a travel path"""
    from_pos: QPointF
    to_pos: QPointF
    segment_type: str  # "cruise" (within system) or "warp" (between systems)
    distance: float  # in AU for cruise, LY for warp
    fuel_cost: float
    time_estimate: float  # in milliseconds
    waypoints: Optional[List[QPointF]] = None  # For curved paths
    coordinate_system: str = "system"  # "system" (relative to system center) or "galaxy" (absolute positions)


@dataclass 
class TravelPath:
    """Complete travel path with multiple segments"""
    segments: List[PathSegment]
    total_distance: float
    total_fuel: float
    total_time: float
    destination_type: str  # "star" or "loc"
    destination_id: int


class TravelVisualization(QObject):
    """Manages travel path visualization and progress indicators"""
    
    # Signals
    pathChanged = Signal()  # Emitted when travel path changes
    progressChanged = Signal(float)  # Emitted with progress percentage (0.0-1.0)
    
    def __init__(self):
        super().__init__()
        self._current_path: Optional[TravelPath] = None
        self._current_progress: float = 0.0  # 0.0 to 1.0
        self._path_graphics: List[QGraphicsItem] = []
        self._progress_indicator: Optional[QGraphicsItem] = None
        
        # Visual styling - Make paths highly visible for testing
        self._path_pen = QPen(QColor(255, 0, 0, 255), 5.0)  # Bright red, fully opaque, thick
        self._path_pen.setCosmetic(True)  # Don't scale with zoom
        
        self._warp_pen = QPen(QColor(255, 0, 255, 255), 6.0)  # Bright magenta for warp jumps
        self._warp_pen.setCosmetic(True)
        
        self._progress_brush = QBrush(QColor(0, 255, 0, 255))  # Bright green progress indicator
        
        # Position update timer for orbital tracking (using lead line approach)
        self._position_update_timer = QTimer()
        self._position_update_timer.timeout.connect(self._update_path_positions)
        self._position_update_timer.setInterval(16)  # 60 FPS like lead lines for smooth tracking
        self._position_update_timer.setSingleShot(False)
        self._position_update_enabled = True  # Enable with lead line tracking method
        
        # Store destination info for position updates
        self._current_dest_type: Optional[str] = None
        self._current_dest_id: Optional[int] = None
        
    def _update_path_positions(self) -> None:
        """Update path positions to track orbital movement using lead line approach"""
        # Multiple safety checks
        if not self._current_path or not self._current_dest_type or self._current_dest_id is None:
            return
            
        # Prevent re-entrant calls
        if hasattr(self, '_updating_positions') and self._updating_positions:
            return
            
        try:
            self._updating_positions = True
            
            # Get current positions using live tracking like lead lines
            try:
                current_system_id, current_location_id = self._get_current_position()
                if current_system_id is None:
                    return
                    
                dest_system_id, dest_location_id = self._resolve_destination(self._current_dest_type, self._current_dest_id)
                if dest_system_id is None:
                    return
                    
                # Only update within same system
                if current_system_id != dest_system_id:
                    return
                    
            except Exception:
                return
                
            # Get live positions directly for both endpoints
            try:
                # Get live start position
                start_pos = None
                if current_location_id is not None:
                    start_pos = self._get_live_position(current_location_id)
                else:
                    # Star position - use negative system id like lead lines
                    start_pos = self._get_live_position(-current_system_id)
                    
                # Get live end position  
                end_pos = None
                if dest_location_id is not None:
                    end_pos = self._get_live_position(dest_location_id)
                else:
                    # Star position - use negative system id like lead lines
                    end_pos = self._get_live_position(-dest_system_id)
                
                # Only update if we got valid positions
                if start_pos is not None and end_pos is not None:
                    # For curved paths with orbital mechanics, we need to completely recalculate
                    # the waypoints because the orbital positions change
                    if (self._current_path.segments and 
                        len(self._current_path.segments) > 0):
                        
                        # Check if this is a curved segment that needs full recalculation
                        has_curved_segment = False
                        for segment in self._current_path.segments:
                            if hasattr(segment, 'waypoints') and segment.waypoints and len(segment.waypoints) > 2:
                                has_curved_segment = True
                                break
                        
                        if has_curved_segment:
                            # Recalculate the entire curved path with current positions
                            logger.debug(f"Recalculating curved path due to orbital movement")
                            
                            # Recalculate curved waypoints using current positions
                            new_waypoints = self._calculate_curved_path(
                                current_system_id, start_pos, end_pos,
                                current_location_id, dest_location_id
                            )
                            
                            # Update the segment with new waypoints
                            for segment in self._current_path.segments:
                                if hasattr(segment, 'waypoints') and segment.waypoints and len(segment.waypoints) > 2:
                                    segment.waypoints = new_waypoints
                                    segment.from_pos = start_pos
                                    segment.to_pos = end_pos
                                    break
                        else:
                            # Simple path - just update endpoints
                            self._update_segment_endpoints(start_pos, end_pos)
                        
                        # Emit path changed signal to trigger redraw
                        logger.debug(f"Emitting pathChanged signal for position update")
                        self.pathChanged.emit()
                        
            except Exception:
                return
                
        except Exception:
            pass
        finally:
            self._updating_positions = False
        
    def _update_segment_endpoints(self, start_pos: QPointF, end_pos: QPointF) -> None:
        """Update segment endpoints for simple paths"""
        if not self._current_path or not self._current_path.segments:
            return
            
        # Update first segment from_pos
        self._current_path.segments[0].from_pos = start_pos
        
        # Update last segment to_pos  
        self._current_path.segments[-1].to_pos = end_pos
        
        # Update waypoints for curved segments (just endpoints)
        for segment in self._current_path.segments:
            if hasattr(segment, 'waypoints') and segment.waypoints:
                if segment == self._current_path.segments[0]:
                    segment.waypoints[0] = start_pos
                if segment == self._current_path.segments[-1]:
                    segment.waypoints[-1] = end_pos
        
        # For multi-segment paths, update intermediate connections
        if len(self._current_path.segments) > 1:
            for i in range(1, len(self._current_path.segments)):
                # Previous segment end becomes current segment start
                self._current_path.segments[i].from_pos = self._current_path.segments[i-1].to_pos
        
    def calculate_path(self, dest_type: str, dest_id: int) -> Optional[TravelPath]:
        """
        Calculate travel path from current location to destination.
        
        Args:
            dest_type: "star" for system star, "loc" for location
            dest_id: System ID or Location ID
            
        Returns:
            TravelPath object with calculated route, or None if no path possible
        """
        try:
            # Get current player position
            current_system_id, current_location_id = self._get_current_position()
            if current_system_id is None:
                logger.warning("Could not get current player position")
                return None
            
            logger.debug(f"Current position: system_id={current_system_id}, location_id={current_location_id}")
                
            # Get destination position
            dest_system_id, dest_location_id = self._resolve_destination(dest_type, dest_id)
            if dest_system_id is None:
                logger.warning(f"Could not resolve destination {dest_type} {dest_id}")
                return None
            
            logger.debug(f"Destination: system_id={dest_system_id}, location_id={dest_location_id}")
                
            segments = []
            
            # Case 1: Travel within same system
            if current_system_id == dest_system_id:
                logger.info("Travel within same system - calculating cruise segment")
                segment = self._calculate_cruise_segment(
                    current_system_id, current_location_id, dest_location_id, dest_type
                )
                if segment:
                    segment.coordinate_system = "system"  # Mark as system coordinates
                    segments.append(segment)
                    logger.debug(f"Added cruise segment: {len(segment.waypoints) if hasattr(segment, 'waypoints') and segment.waypoints else 0} waypoints")
                else:
                    logger.warning("Failed to calculate cruise segment")
                    
            # Case 2: Travel to different system (requires warp through gates)
            else:
                logger.info("Travel between different systems - routing through warp gates")
                
                # Step 1: Cruise from current location to source system's warp gate (if not already there)
                if current_location_id is not None:
                    # Get warp gate info for current system
                    source_warp_gate = db.get_warp_gate(current_system_id)
                    if source_warp_gate:
                        warp_gate_id = source_warp_gate.get("id")
                        if warp_gate_id and current_location_id != warp_gate_id:
                            # Need to cruise to warp gate first
                            cruise_to_gate = self._calculate_cruise_segment(
                                current_system_id, current_location_id, warp_gate_id, "loc"
                            )
                            if cruise_to_gate:
                                cruise_to_gate.coordinate_system = "system"  # Mark as system coordinates
                                segments.append(cruise_to_gate)
                                logger.debug("Added cruise segment to source warp gate")
                
                # Step 2: Warp jump from source gate to destination gate
                warp_segment = self._calculate_warp_segment(current_system_id, dest_system_id)
                if warp_segment:
                    warp_segment.coordinate_system = "galaxy"  # Mark as galaxy coordinates
                    segments.append(warp_segment)
                    logger.debug("Added warp segment between systems")
                    
                # Step 3: Cruise from destination warp gate to final destination (if not the gate)
                if dest_type == "loc":
                    dest_warp_gate = db.get_warp_gate(dest_system_id)
                    if dest_warp_gate:
                        warp_gate_id = dest_warp_gate.get("id")
                        if warp_gate_id and dest_location_id != warp_gate_id:
                            # Need to cruise from warp gate to final destination
                            cruise_from_gate = self._calculate_cruise_segment(
                                dest_system_id, warp_gate_id, dest_location_id, "loc"
                            )
                            if cruise_from_gate:
                                cruise_from_gate.coordinate_system = "system"  # Mark as system coordinates
                                segments.append(cruise_from_gate)
                                logger.debug("Added cruise segment from destination warp gate")
                        
            if not segments:
                logger.error("No segments calculated for travel path")
                return None
                
            # Calculate totals
            total_distance = sum(seg.distance for seg in segments)
            total_fuel = sum(seg.fuel_cost for seg in segments)
            total_time = sum(seg.time_estimate for seg in segments)
            
            path = TravelPath(
                segments=segments,
                total_distance=total_distance,
                total_fuel=total_fuel,
                total_time=total_time,
                destination_type=dest_type,
                destination_id=dest_id
            )
            
            logger.info(f"Travel path calculated successfully: {len(segments)} segments, {total_distance:.2f} total distance")
            return path
            
        except Exception as e:
            logger.error(f"Error calculating travel path: {e}", exc_info=True)
            return None
            
    def set_travel_path(self, path: Optional[TravelPath]) -> None:
        """Set the current travel path for visualization"""
        logger.debug(f"set_travel_path called with path: {'None' if path is None else f'{len(path.segments)} segments'}")
        self._current_path = path
        self._current_progress = 0.0
        
        # Store destination info and start/stop orbital tracking
        if path:
            self._current_dest_type = path.destination_type
            self._current_dest_id = path.destination_id
            # Only start timer if orbital tracking is enabled
            if self._position_update_enabled and not self._position_update_timer.isActive():
                self._position_update_timer.start()
        else:
            self._current_dest_type = None
            self._current_dest_id = None
            # Stop timer when no active path
            if self._position_update_timer.isActive():
                self._position_update_timer.stop()
        
        logger.debug(f"Emitting pathChanged signal - clearing path")
        try:
            self.pathChanged.emit()
            logger.debug(f"pathChanged.emit() completed successfully")
        except Exception as e:
            logger.error(f"Error emitting pathChanged signal: {e}", exc_info=True)
        
    def update_progress(self, progress: float) -> None:
        """Update travel progress (0.0 to 1.0)"""
        old_progress = self._current_progress
        self._current_progress = max(0.0, min(1.0, progress))
        self.progressChanged.emit(self._current_progress)
        
        # Debug logging to see if progress is updating
        if abs(old_progress - self._current_progress) > 0.01:  # Only log significant changes
            logger.debug(f"Travel progress updated: {old_progress:.3f} -> {self._current_progress:.3f}")
        
        # Emit pathChanged to trigger re-render for line eating effect
        logger.debug(f"Emitting pathChanged signal for progress update: {self._current_progress:.3f}")
        self.pathChanged.emit()
        
    def get_current_path(self) -> Optional[TravelPath]:
        """Get the current travel path"""
        return self._current_path
        
    def get_progress_position(self) -> Optional[QPointF]:
        """Get the current position along the path based on progress"""
        if not self._current_path or not self._current_path.segments:
            return None
            
        # Find which segment we're currently in
        total_distance = self._current_path.total_distance
        current_distance = total_distance * self._current_progress
        
        distance_so_far = 0.0
        for segment in self._current_path.segments:
            if distance_so_far + segment.distance >= current_distance:
                # We're in this segment
                segment_progress = (current_distance - distance_so_far) / segment.distance
                return self._interpolate_position(segment, segment_progress)
            distance_so_far += segment.distance
            
        # If we're at the very end
        if self._current_path.segments:
            return self._current_path.segments[-1].to_pos
            
        return None
        
    def _get_current_position(self) -> Tuple[Optional[int], Optional[int]]:
        """Get current system and location IDs"""
        try:
            status = player_status.get_status_snapshot()
            system_id = status.get("system_id")
            location_id = status.get("location_id")  # None if at system star
            return system_id, location_id
        except Exception:
            return None, None
            
    def _resolve_destination(self, dest_type: str, dest_id: int) -> Tuple[Optional[int], Optional[int]]:
        """Resolve destination to system_id and location_id"""
        try:
            if dest_type == "star":
                return dest_id, None
            elif dest_type == "loc":
                # Get system_id for this location
                location = db.get_location(dest_id)
                if location:
                    return location.get("system_id"), dest_id
        except Exception:
            pass
        return None, None
        
    def _calculate_cruise_segment(self, system_id: int, from_loc_id: Optional[int], 
                                to_loc_id: Optional[int], to_type: str) -> Optional[PathSegment]:
        """Calculate cruise segment within a system with intelligent path routing"""
        try:
            logger.debug(f"=== Calculating cruise segment: from_loc={from_loc_id}, to_loc={to_loc_id}, to_type={to_type} ===")
            
            from_pos = self._get_system_position(system_id, from_loc_id)
            to_pos = self._get_system_position(system_id, to_loc_id)
            
            if from_pos is None or to_pos is None:
                logger.warning(f"Could not get positions: from_pos={from_pos}, to_pos={to_pos}")
                return None
            
            logger.debug(f"Positions: from=({from_pos.x():.1f}, {from_pos.y():.1f}), to=({to_pos.x():.1f}, {to_pos.y():.1f})")
            
            # Calculate curved path that avoids obstacles
            waypoints = self._calculate_curved_path(system_id, from_pos, to_pos, from_loc_id, to_loc_id)
            
            if not waypoints or len(waypoints) < 2:
                # Fallback to direct path if curve calculation fails
                logger.warning("Curved path calculation failed, using direct path")
                waypoints = [from_pos, to_pos]
            else:
                logger.info(f"Curved path calculation returned {len(waypoints)} waypoints")
            
            # For now, return a single segment with the final destination
            # TODO: Later we can split this into multiple segments for complex curves
            final_from = waypoints[0]
            final_to = waypoints[-1]
            
            # Calculate total distance following the waypoints
            total_distance_px = 0.0
            for i in range(len(waypoints) - 1):
                dx = waypoints[i + 1].x() - waypoints[i].x()
                dy = waypoints[i + 1].y() - waypoints[i].y()
                total_distance_px += math.sqrt(dx*dx + dy*dy)
            
            distance_au = total_distance_px / 100.0  # Convert pixels to AU
            
            # Calculate fuel and time using travel system
            fuel_cost = distance_au * travel.FUEL_PER_AU
            time_ms = distance_au * 500  # Rough estimate, 500ms per AU
            
            # Store waypoints in the segment for rendering
            segment = PathSegment(
                from_pos=final_from,
                to_pos=final_to,
                segment_type="cruise",
                distance=distance_au,
                fuel_cost=fuel_cost,
                time_estimate=time_ms
            )
            
            # Add waypoints as custom attribute for curved rendering
            segment.waypoints = waypoints
            logger.debug(f"Stored {len(waypoints)} waypoints in segment")
            
            return segment
            
        except Exception as e:
            logger.error(f"Exception in _calculate_cruise_segment: {e}", exc_info=True)
            return None
            
    def _calculate_warp_segment(self, from_system_id: int, to_system_id: int) -> Optional[PathSegment]:
        """Calculate warp segment between system warp gates"""
        try:
            # Get warp gate positions instead of system centers
            from_pos = self._get_warp_gate_position(from_system_id)
            to_pos = self._get_warp_gate_position(to_system_id)
            
            if from_pos is None or to_pos is None:
                # Fallback to system centers if warp gates not found
                from_pos = self._get_galaxy_position(from_system_id)
                to_pos = self._get_galaxy_position(to_system_id)
                
            if from_pos is None or to_pos is None:
                return None
                
            # Calculate distance in light years
            dx = to_pos.x() - from_pos.x()
            dy = to_pos.y() - from_pos.y()
            distance_ly = math.sqrt(dx*dx + dy*dy) / 50.0  # Convert pixels to LY (rough)
            
            # Calculate fuel and time using travel system
            fuel_cost = distance_ly * travel.WARP_FUEL_PER_LY * travel.WARP_FUEL_WEIGHT
            time_ms = distance_ly * 500  # Rough estimate, 500ms per LY
            
            return PathSegment(
                from_pos=from_pos,
                to_pos=to_pos,
                segment_type="warp",
                distance=distance_ly,
                fuel_cost=fuel_cost,
                time_estimate=time_ms
            )
            
        except Exception:
            return None
    
    def _calculate_curved_path(self, system_id: int, start_pos: QPointF, end_pos: QPointF, 
                             start_loc_id: Optional[int], end_loc_id: Optional[int]) -> List[QPointF]:
        """Calculate orbital transfer path - follow orbit in reverse, then transfer to destination"""
        try:
            logger.debug(f"ORBITAL TRANSFER: start=({start_pos.x():.1f}, {start_pos.y():.1f}), end=({end_pos.x():.1f}, {end_pos.y():.1f})")
            
            # Calculate direct distance
            dx = end_pos.x() - start_pos.x()
            dy = end_pos.y() - start_pos.y()
            direct_distance = math.sqrt(dx*dx + dy*dy)
            
            # For very short distances, use direct path
            if direct_distance < 150:  # Less than 150 pixels
                logger.debug("Short distance, using direct path")
                return [start_pos, end_pos]
            
            # Create orbital transfer path
            return self._create_orbital_transfer(start_pos, end_pos)
                
        except Exception as e:
            logger.error(f"Exception in _calculate_curved_path: {e}")
            return [start_pos, end_pos]
            
    def _create_orbital_transfer(self, start_pos: QPointF, end_pos: QPointF) -> List[QPointF]:
        """Create realistic orbital transfer - follow orbit in reverse, then transfer"""
        try:
            star_center = QPointF(0.0, 0.0)  # Star at system center
            
            # Calculate orbital parameters for start position
            start_distance = math.sqrt((start_pos.x() - star_center.x())**2 + (start_pos.y() - star_center.y())**2)
            start_angle = math.atan2(start_pos.y() - star_center.y(), start_pos.x() - star_center.x())
            
            # Calculate end position parameters
            end_distance = math.sqrt((end_pos.x() - star_center.x())**2 + (end_pos.y() - star_center.y())**2)
            end_angle = math.atan2(end_pos.y() - star_center.y(), end_pos.x() - star_center.x())
            
            # Normalize angles to 0-2π
            if start_angle < 0:
                start_angle += 2 * math.pi
            if end_angle < 0:
                end_angle += 2 * math.pi
                
            logger.debug(f"Start: distance={start_distance:.1f}, angle={math.degrees(start_angle):.1f}°")
            logger.debug(f"End: distance={end_distance:.1f}, angle={math.degrees(end_angle):.1f}°")
            
            waypoints = [start_pos]
            
            # Phase 1: Follow orbit in reverse (counter-clockwise) to find transfer point
            transfer_angle = self._find_optimal_transfer_angle(start_angle, end_angle, end_pos, star_center, start_distance)
            logger.debug(f"Transfer angle: {math.degrees(transfer_angle):.1f}°")
            
            # Generate waypoints along the orbital path (counter-clockwise)
            current_angle = start_angle
            orbital_radius = start_distance
            
            # Calculate how far to travel along orbit
            angle_diff = transfer_angle - start_angle
            if angle_diff > 0:
                angle_diff = angle_diff - 2 * math.pi  # Go the long way counter-clockwise
            
            # Start curving sooner by reducing the orbital phase
            # Instead of going all the way to optimal transfer, start curving earlier
            early_curve_factor = 0.7  # Start transfer at 70% of the way to optimal point
            reduced_angle_diff = angle_diff * early_curve_factor
            
            # Travel counter-clockwise along orbit (but not as far)
            step_size = -0.15  # ~8.6 degrees counter-clockwise
            steps_needed = int(abs(reduced_angle_diff) / abs(step_size))
            
            logger.debug(f"Orbital phase: {steps_needed} steps along orbit (early curve at {early_curve_factor*100:.0f}%)")
            
            for i in range(1, min(steps_needed + 1, 15)):  # Reduced max steps to 15
                current_angle += step_size
                if current_angle < 0:
                    current_angle += 2 * math.pi
                    
                # Calculate position on orbit
                orbit_x = star_center.x() + orbital_radius * math.cos(current_angle)
                orbit_y = star_center.y() + orbital_radius * math.sin(current_angle)
                waypoints.append(QPointF(orbit_x, orbit_y))
            
            # Phase 2: Transfer from orbit to destination
            transfer_start = waypoints[-1]  # Last orbital waypoint
            logger.debug(f"Transfer from: ({transfer_start.x():.1f}, {transfer_start.y():.1f}) to destination")
            
            # Create smooth transfer curve using Bezier curve
            transfer_waypoints = self._create_transfer_curve(transfer_start, end_pos)
            waypoints.extend(transfer_waypoints[1:])  # Skip first point (already in waypoints)
            
            logger.debug(f"Total waypoints: {len(waypoints)} (orbital: {steps_needed}, transfer: {len(transfer_waypoints)-1})")
            return waypoints
            
        except Exception as e:
            logger.error(f"Exception in _create_orbital_transfer: {e}")
            return [start_pos, end_pos]
    
    def _find_optimal_transfer_angle(self, start_angle: float, end_angle: float, end_pos: QPointF, star_center: QPointF, start_distance: float) -> float:
        """Find the optimal angle to start transfer to destination"""
        try:
            # Simple approach: find angle that creates the shortest transfer path
            # This simulates finding the Hohmann transfer window
            
            # Try different transfer angles and find the one with shortest transfer distance
            best_angle = start_angle
            shortest_distance = float('inf')
            
            # Test angles along counter-clockwise orbit path
            test_angle = start_angle
            for _ in range(36):  # Test every 10 degrees
                test_angle -= 0.174  # ~10 degrees counter-clockwise
                if test_angle < 0:
                    test_angle += 2 * math.pi
                
                # Calculate distance from this orbital position to destination
                test_x = star_center.x() + start_distance * math.cos(test_angle)
                test_y = star_center.y() + start_distance * math.sin(test_angle)
                
                transfer_distance = math.sqrt((end_pos.x() - test_x)**2 + (end_pos.y() - test_y)**2)
                
                if transfer_distance < shortest_distance:
                    shortest_distance = transfer_distance
                    best_angle = test_angle
            
            return best_angle
            
        except Exception:
            # Fallback: travel 60 degrees counter-clockwise
            transfer_angle = start_angle - math.pi/3  # 60 degrees
            if transfer_angle < 0:
                transfer_angle += 2 * math.pi
            return transfer_angle
    
    def _create_transfer_curve(self, transfer_start: QPointF, end_pos: QPointF) -> List[QPointF]:
        """Create smooth transfer curve from orbital position to destination"""
        try:
            # Create a gentle curve using quadratic Bezier
            # Control point is offset perpendicular to the transfer line
            
            dx = end_pos.x() - transfer_start.x()
            dy = end_pos.y() - transfer_start.y()
            
            # Midpoint
            mid_x = (transfer_start.x() + end_pos.x()) / 2.0
            mid_y = (transfer_start.y() + end_pos.y()) / 2.0
            
            # Perpendicular offset (gentler, longer curve)
            transfer_distance = math.sqrt(dx*dx + dy*dy)
            curve_offset = min(transfer_distance * 0.3, 150.0)  # 30% offset, max 150 pixels (increased)
            
            # Perpendicular vector (90 degrees counter-clockwise)
            perp_x = -dy / transfer_distance * curve_offset
            perp_y = dx / transfer_distance * curve_offset
            
            control_point = QPointF(mid_x + perp_x, mid_y + perp_y)
            
            # Generate more Bezier curve waypoints for smoother transfer
            waypoints = [transfer_start]
            
            for i in range(1, 6):  # 5 intermediate points (more gradual)
                t = i / 6.0
                
                # Quadratic Bezier: (1-t)²P0 + 2(1-t)tP1 + t²P2
                bezier_x = ((1-t)**2 * transfer_start.x() + 
                           2*(1-t)*t * control_point.x() + 
                           t**2 * end_pos.x())
                bezier_y = ((1-t)**2 * transfer_start.y() + 
                           2*(1-t)*t * control_point.y() + 
                           t**2 * end_pos.y())
                
                waypoints.append(QPointF(bezier_x, bezier_y))
            
            waypoints.append(end_pos)
            return waypoints
            
        except Exception:
            return [transfer_start, end_pos]
    
    def _get_system_obstacles(self, system_id: int, exclude_start: Optional[int], exclude_end: Optional[int]) -> List[dict]:
        """Get list of obstacles in the system using actual image boundaries"""
        obstacles = []
        
        try:
            from data import db
            
            # Get access to the system map to get actual item boundaries
            from ui.main_window import MainWindow
            import gc
            for obj in gc.get_objects():
                if isinstance(obj, MainWindow):
                    main_window = obj
                    break
            else:
                return obstacles
                
            travel_coordinator = getattr(main_window, '_travel_coordinator', None)
            if not travel_coordinator:
                return obstacles
                
            system_map = getattr(travel_coordinator, '_system_map', None)
            if not system_map:
                return obstacles
            
            # Get the items dictionary from system map
            items = getattr(system_map, '_items', {})
            
            # Always add the star as an obstacle (star has ID < 0, but we check for star at center)
            star_radius_px = getattr(system_map, '_star_radius_px', 75.0)
            obstacles.append({
                'pos': QPointF(0.0, 0.0),  # Star is always at center
                'rect': QRectF(-star_radius_px, -star_radius_px, star_radius_px * 2, star_radius_px * 2),
                'type': 'star',
                'id': -system_id
            })
            
            # Add other locations using their actual image boundaries
            system_locations = db.get_locations(system_id)
            for location in system_locations:
                loc_id = location['id']
                
                # Skip start and end locations
                if loc_id == exclude_start or loc_id == exclude_end:
                    continue
                
                # Get the actual graphics item for this location
                item = items.get(loc_id)
                if item is not None:
                    try:
                        # Get the actual scene boundary rectangle of the image
                        scene_rect = item.mapToScene(item.boundingRect()).boundingRect()
                        
                        obstacles.append({
                            'pos': scene_rect.center(),
                            'rect': scene_rect,
                            'type': 'location',
                            'id': loc_id
                        })
                        
                    except Exception:
                        # If we can't get the boundary, skip this obstacle
                        continue
            
        except Exception:
            pass
            
        return obstacles
    
    def _is_path_clear(self, start: QPointF, end: QPointF, obstacles: List[dict]) -> bool:
        """Check if direct path intersects any obstacles using actual image boundaries"""
        try:
            for obstacle in obstacles:
                if self._line_intersects_rect(start, end, obstacle['rect']):
                    return False
            return True
        except Exception:
            return False
    
    def _line_intersects_rect(self, start: QPointF, end: QPointF, rect: QRectF) -> bool:
        """Check if line segment intersects with rectangle"""
        try:
            # Check if either endpoint is inside the rectangle
            if rect.contains(start) or rect.contains(end):
                return True
            
            # Check if line intersects any of the four rectangle edges
            rect_lines = [
                (rect.topLeft(), rect.topRight()),      # Top edge
                (rect.topRight(), rect.bottomRight()),  # Right edge  
                (rect.bottomRight(), rect.bottomLeft()), # Bottom edge
                (rect.bottomLeft(), rect.topLeft())     # Left edge
            ]
            
            for rect_start, rect_end in rect_lines:
                if self._lines_intersect(start, end, rect_start, rect_end):
                    return True
                    
            return False
            
        except Exception:
            return False
    
    def _lines_intersect(self, p1: QPointF, p2: QPointF, p3: QPointF, p4: QPointF) -> bool:
        """Check if two line segments intersect"""
        try:
            # Line 1: p1 to p2, Line 2: p3 to p4
            denom = (p1.x() - p2.x()) * (p3.y() - p4.y()) - (p1.y() - p2.y()) * (p3.x() - p4.x())
            
            if abs(denom) < 1e-6:  # Lines are parallel
                return False
                
            t = ((p1.x() - p3.x()) * (p3.y() - p4.y()) - (p1.y() - p3.y()) * (p3.x() - p4.x())) / denom
            u = -((p1.x() - p2.x()) * (p1.y() - p3.y()) - (p1.y() - p2.y()) * (p1.x() - p3.x())) / denom
            
            # Check if intersection point lies within both line segments
            return 0 <= t <= 1 and 0 <= u <= 1
            
        except Exception:
            return False
    
    def _find_curved_waypoints(self, start: QPointF, end: QPointF, obstacles: List[dict]) -> List[QPointF]:
        """Find waypoints that create an orbital-mechanics-based curved path around obstacles"""
        try:
            # Use orbital mechanics logic: always go counter-clockwise around the star
            # since orbits are clockwise, ships meet orbital objects rather than chase them
            
            star_center = QPointF(0.0, 0.0)  # Star is always at center
            
            # Calculate orbital path that goes counter-clockwise around the star
            waypoints = self._calculate_orbital_curve(start, end, star_center, obstacles)
            
            if waypoints and len(waypoints) >= 2:
                logger.debug(f"Generated orbital curve with {len(waypoints)} waypoints")
                return waypoints
            else:
                logger.warning("Failed to generate orbital curve, using direct path")
                return [start, end]
                
        except Exception as e:
            logger.error(f"Exception in _find_curved_waypoints: {e}")
            return [start, end]
    
    def _calculate_rect_curve(self, start: QPointF, end: QPointF, rect: QRectF, center: QPointF) -> List[QPointF]:
        """Calculate curved path around a rectangular obstacle"""
        try:
            # Determine which side of the rectangle to go around
            start_to_center = QPointF(center.x() - start.x(), center.y() - start.y())
            end_to_center = QPointF(center.x() - end.x(), end.y() - end.y())
            
            # Choose path around rectangle based on which corners are closer to start/end
            corners = [
                rect.topLeft(), rect.topRight(),
                rect.bottomRight(), rect.bottomLeft()
            ]
            
            # Find the path that goes around the "outside" of the obstacle
            # by picking waypoints on the rectangle perimeter
            
            # Simple approach: go around the rectangle via two corners
            waypoints = [start]
            
            # Determine which corners to use based on start/end positions
            if start.x() < center.x() and end.x() > center.x():
                # Going left to right, curve around top or bottom
                if start.y() < center.y():
                    # Go around top
                    waypoints.extend([rect.topLeft(), rect.topRight()])
                else:
                    # Go around bottom
                    waypoints.extend([rect.bottomLeft(), rect.bottomRight()])
            elif start.x() > center.x() and end.x() < center.x():
                # Going right to left, curve around top or bottom
                if start.y() < center.y():
                    # Go around top
                    waypoints.extend([rect.topRight(), rect.topLeft()])
                else:
                    # Go around bottom
                    waypoints.extend([rect.bottomRight(), rect.bottomLeft()])
            elif start.y() < center.y() and end.y() > center.y():
                # Going top to bottom, curve around left or right
                if start.x() < center.x():
                    # Go around left
                    waypoints.extend([rect.topLeft(), rect.bottomLeft()])
                else:
                    # Go around right
                    waypoints.extend([rect.topRight(), rect.bottomRight()])
            elif start.y() > center.y() and end.y() < center.y():
                # Going bottom to top, curve around left or right
                if start.x() < center.x():
                    # Go around left
                    waypoints.extend([rect.bottomLeft(), rect.topLeft()])
                else:
                    # Go around right
                    waypoints.extend([rect.bottomRight(), rect.topRight()])
            else:
                # Default: pick the two closest corners
                start_distances = [(i, (corner - start).manhattanLength()) for i, corner in enumerate(corners)]
                end_distances = [(i, (corner - end).manhattanLength()) for i, corner in enumerate(corners)]
                
                start_distances.sort(key=lambda x: x[1])
                end_distances.sort(key=lambda x: x[1])
                
                # Use the two closest corners
                waypoints.append(corners[start_distances[0][0]])
                waypoints.append(corners[end_distances[0][0]])
            
            waypoints.append(end)
            return waypoints
            
        except Exception:
            return [start, end]
            
    def _calculate_orbital_curve(self, start: QPointF, end: QPointF, star_center: QPointF, obstacles: List[dict]) -> List[QPointF]:
        """Calculate curved path using orbital mechanics - always counter-clockwise around star"""
        try:
            # Calculate distances from star center
            start_distance = math.sqrt((start.x() - star_center.x())**2 + (start.y() - star_center.y())**2)
            end_distance = math.sqrt((end.x() - star_center.x())**2 + (end.y() - star_center.y())**2)
            
            # Calculate angles from star center (0 degrees = positive X axis)
            start_angle = math.atan2(start.y() - star_center.y(), start.x() - star_center.x())
            end_angle = math.atan2(end.y() - star_center.y(), end.x() - star_center.x())
            
            # Normalize angles to 0-2π range
            if start_angle < 0:
                start_angle += 2 * math.pi
            if end_angle < 0:
                end_angle += 2 * math.pi
                
            logger.debug(f"Start angle: {math.degrees(start_angle):.1f}°, End angle: {math.degrees(end_angle):.1f}°")
            
            # Determine counter-clockwise path (decreasing angle direction)
            # If we need to go more than 180° counter-clockwise, it's shorter to go clockwise
            angle_diff = start_angle - end_angle
            if angle_diff < 0:
                angle_diff += 2 * math.pi
                
            # Use a larger orbital radius to avoid obstacles
            orbital_radius = max(start_distance, end_distance, self._get_safe_orbital_radius(obstacles)) * 1.2
            
            waypoints = [start]
            
            # If angle difference is small (< 30°), might be able to go direct
            if angle_diff < math.pi / 6:  # 30 degrees
                # Check if direct path clears all obstacles
                if self._is_path_clear(start, end, obstacles):
                    logger.debug("Small angle difference and path clear - using direct path")
                    return [start, end]
            
            # Generate waypoints along counter-clockwise orbital arc
            if angle_diff > math.pi:
                # Shorter to go clockwise (opposite direction)
                logger.debug("Going clockwise (shorter arc)")
                current_angle = start_angle
                target_angle = end_angle
                
                # Go clockwise (increasing angle)
                while abs(current_angle - target_angle) > 0.1:  # ~6 degrees
                    current_angle += 0.2  # ~11 degree steps
                    if current_angle > 2 * math.pi:
                        current_angle -= 2 * math.pi
                        
                    # Calculate waypoint position on orbital circle
                    x = star_center.x() + orbital_radius * math.cos(current_angle)
                    y = star_center.y() + orbital_radius * math.sin(current_angle)
                    waypoints.append(QPointF(x, y))
                    
                    # Stop if we've passed the target
                    if target_angle > start_angle:  # Normal case
                        if current_angle >= target_angle:
                            break
                    else:  # Wrapped around case
                        if current_angle >= target_angle and current_angle > start_angle:
                            break
            else:
                # Go counter-clockwise (decreasing angle) - the preferred direction
                logger.debug("Going counter-clockwise (preferred direction)")
                current_angle = start_angle
                target_angle = end_angle
                
                # Go counter-clockwise (decreasing angle)
                while abs(current_angle - target_angle) > 0.1:  # ~6 degrees
                    current_angle -= 0.2  # ~11 degree steps  
                    if current_angle < 0:
                        current_angle += 2 * math.pi
                        
                    # Calculate waypoint position on orbital circle
                    x = star_center.x() + orbital_radius * math.cos(current_angle)
                    y = star_center.y() + orbital_radius * math.sin(current_angle)
                    waypoints.append(QPointF(x, y))
                    
                    # Stop if we've passed the target
                    if target_angle < start_angle:  # Normal case
                        if current_angle <= target_angle:
                            break
                    else:  # Wrapped around case  
                        if current_angle <= target_angle and current_angle < start_angle:
                            break
            
            waypoints.append(end)
            
            logger.debug(f"Generated {len(waypoints)} waypoints for orbital curve")
            return waypoints
            
        except Exception as e:
            logger.error(f"Exception in _calculate_orbital_curve: {e}")
            return [start, end]
    
    def _get_safe_orbital_radius(self, obstacles: List[dict]) -> float:
        """Get a safe orbital radius that clears all obstacles"""
        max_radius = 100.0  # Default minimum safe radius
        
        try:
            star_center = QPointF(0.0, 0.0)
            
            for obstacle in obstacles:
                if obstacle['type'] == 'star':
                    # For the star, use its radius plus margin
                    star_radius = obstacle['rect'].width() / 2.0
                    max_radius = max(max_radius, star_radius + 50.0)
                else:
                    # For other obstacles, calculate distance from star center to furthest edge
                    obstacle_rect = obstacle['rect']
                    corners = [
                        obstacle_rect.topLeft(), obstacle_rect.topRight(),
                        obstacle_rect.bottomLeft(), obstacle_rect.bottomRight()
                    ]
                    
                    for corner in corners:
                        distance = math.sqrt((corner.x() - star_center.x())**2 + (corner.y() - star_center.y())**2)
                        max_radius = max(max_radius, distance + 30.0)  # 30px margin
        
        except Exception:
            pass
            
        logger.debug(f"Safe orbital radius: {max_radius:.1f}")
        return max_radius
            
    def _get_system_position(self, system_id: int, location_id: Optional[int]) -> Optional[QPointF]:
        """Get position within system map coordinates using the same method as lead lines"""
        try:
            if location_id is None:
                # Star position (center) - use negative system_id as lead lines do
                return self._get_live_position(-system_id)
            else:
                # Location position - get live position from system map
                return self._get_live_position(location_id)
        except Exception:
            pass
        return None
        
    def _get_live_position(self, entity_id: int) -> Optional[QPointF]:
        """Get live position of entity using scene coordinates (not viewport coordinates)"""
        try:
            # Import here to avoid circular imports
            from ui.main_window import MainWindow
            
            # Try to get the main window instance
            import gc
            for obj in gc.get_objects():
                if isinstance(obj, MainWindow):
                    main_window = obj
                    break
            else:
                return None
                
            # Get the travel coordinator
            travel_coordinator = getattr(main_window, '_travel_coordinator', None)
            if not travel_coordinator:
                return None
                
            # Get the system map widget
            system_map = getattr(travel_coordinator, '_system_map', None)
            if not system_map:
                return None
            
            # For stars (negative entity_id), return scene center (0, 0)
            if entity_id < 0:
                logger.debug(f"Getting live position for star entity_id={entity_id}, returning scene center (0, 0)")
                return QPointF(0.0, 0.0)
                
            # For locations, get the item's scene position directly
            items = getattr(system_map, '_items', {})
            item = items.get(entity_id)
            if not item:
                logger.warning(f"Live position: entity_id={entity_id}, item not found")
                return None
                
            # Get the item's scene coordinates (world coordinates, not viewport coordinates)
            rect = item.mapToScene(item.boundingRect()).boundingRect()
            scene_center = rect.center()
            
            logger.debug(f"Live position: entity_id={entity_id}, scene_center=({scene_center.x():.1f}, {scene_center.y():.1f})")
            
            return scene_center
            
        except Exception as e:
            logger.error(f"Live position: entity_id={entity_id}, exception: {e}")
            return None
        
    def _get_warp_gate_position(self, system_id: int) -> Optional[QPointF]:
        """Get warp gate position in galaxy map coordinates"""
        try:
            # Get the warp gate for this system
            warp_gate = db.get_warp_gate(system_id)
            if not warp_gate:
                # Fallback to system center if no warp gate
                return self._get_galaxy_position(system_id)
                
            # Get system coordinates
            system = db.get_system(system_id)
            if not system:
                return None
                
            # Warp gates are positioned at the edge of systems
            # For galaxy map visualization, place them at system coordinates
            # since we represent the system as a point on the galaxy map
            system_x = float(system["x"])
            system_y = float(system["y"])
            
            return QPointF(system_x, system_y)
        except Exception:
            pass
        return None
    
    def _get_warp_gate_system_position(self, system_id: int) -> Optional[QPointF]:
        """Get warp gate position in system map coordinates (relative to system center)"""
        try:
            # Get the warp gate for this system
            warp_gate = db.get_warp_gate(system_id)
            if not warp_gate:
                return None
                
            # Get the actual warp gate location data
            warp_gate_id = warp_gate.get("id")
            if warp_gate_id:
                location = db.get_location(warp_gate_id)
                if location:
                    # Use actual warp gate position in system coordinates
                    x = float(location.get("x", 0.0))
                    y = float(location.get("y", 0.0))
                    return QPointF(x, y)
            
            # Fallback: place warp gate at edge of system (arbitrary but consistent)
            return QPointF(400.0, 0.0)  # Right side of system center
        except Exception:
            pass
        return None
        
    def _get_galaxy_position(self, system_id: int) -> Optional[QPointF]:
        """Get system position in galaxy map coordinates"""
        try:
            system = db.get_system(system_id)
            if system:
                return QPointF(float(system["x"]), float(system["y"]))
        except Exception:
            pass
        return None
        
    def _interpolate_position(self, segment: PathSegment, progress: float) -> QPointF:
        """Interpolate position along a path segment"""
        from_pos = segment.from_pos
        to_pos = segment.to_pos
        
        x = from_pos.x() + (to_pos.x() - from_pos.x()) * progress
        y = from_pos.y() + (to_pos.y() - from_pos.y()) * progress
        
        return QPointF(x, y)


class PathRenderer(QObject):
    """Renders travel paths on graphics scenes"""
    
    def __init__(self, visualization: TravelVisualization, show_progress_dot: bool = True, coordinate_system: str = "system"):
        super().__init__()
        self._visualization = visualization
        self._path_items: List[QGraphicsItem] = []
        self._progress_item: Optional[QGraphicsEllipseItem] = None
        self._scene = None
        self._show_progress_dot = show_progress_dot  # Control whether to show green progress dot
        self._coordinate_system = coordinate_system  # "system" or "galaxy" - only render matching segments
        
        # Connect to visualization signals
        self._visualization.pathChanged.connect(self._update_path_graphics)
        if self._show_progress_dot:  # Only connect progress signal if we show the dot
            self._visualization.progressChanged.connect(self._update_progress_indicator)
        
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self._clear_graphics()
        except Exception:
            pass
            
    def disconnect_signals(self) -> None:
        """Disconnect from visualization signals to prevent updates"""
        try:
            self._visualization.pathChanged.disconnect(self._update_path_graphics)
            if self._show_progress_dot:
                self._visualization.progressChanged.disconnect(self._update_progress_indicator)
        except Exception:
            pass
        
    def set_scene(self, scene) -> None:
        """Set the graphics scene to render on"""
        # Clear graphics from old scene first
        if self._scene != scene:
            self._clear_graphics()
        
        self._scene = scene
        # Only update graphics if we have a valid scene
        if scene and self._is_scene_valid():
            self._update_path_graphics()
        
    def _update_path_graphics(self) -> None:
        """Update path graphics when path changes"""
        logger.debug(f"PathRenderer({self._coordinate_system}): _update_path_graphics called")
        if not self._scene:
            logger.debug(f"PathRenderer({self._coordinate_system}): No scene, returning early")
            return
            
        # Check if scene is still valid
        try:
            if not self._is_scene_valid():
                logger.debug(f"PathRenderer({self._coordinate_system}): Scene not valid, returning early")
                self._scene = None
                return
        except Exception as e:
            logger.debug(f"PathRenderer({self._coordinate_system}): Exception checking scene validity: {e}")
            self._scene = None
            return
            
        path = self._visualization.get_current_path()
        if not path:
            # Clear graphics if no path
            logger.debug(f"PathRenderer({self._coordinate_system}): No current path, clearing graphics")
            self._clear_graphics()
            return
            
        logger.debug(f"PathRenderer({self._coordinate_system}): Got path with {len(path.segments)} segments, proceeding...")
        
        # CRITICAL FIX: Create a snapshot of segment coordinate systems to prevent mutation issues
        # This ensures we get a stable view of coordinates that won't change mid-processing
        segment_coords = [(seg, getattr(seg, 'coordinate_system', 'MISSING')) for seg in path.segments]
        logger.debug(f"PathRenderer({self._coordinate_system}): Segment coordinates: {[coord for _, coord in segment_coords]}")
            
        # If we have existing path items, try to update positions instead of recreating
        if self._path_items and len(self._path_items) == len(path.segments):
            # For curved segments, we need to recreate because the waypoints changed
            # Simple optimization doesn't work for complex curved paths
            has_curved_segments = any(
                hasattr(segment, 'waypoints') and segment.waypoints and len(segment.waypoints) > 2 
                for segment in path.segments
            )
            
            if not has_curved_segments:
                # Only try to update simple line items for straight paths
                update_success = True
                for i, (line_item, segment) in enumerate(zip(self._path_items, path.segments)):
                    try:
                        if self._is_item_valid(line_item) and isinstance(line_item, QGraphicsLineItem):
                            line_item.setLine(
                                segment.from_pos.x(), segment.from_pos.y(),
                                segment.to_pos.x(), segment.to_pos.y()
                            )
                        else:
                            update_success = False
                            break
                    except Exception:
                        update_success = False
                        break
                        
                if update_success:
                    # Successfully updated all positions, update progress indicator too
                    if self._progress_item:
                        self._update_progress_indicator(self._visualization._current_progress)
                    return
        
        # Clear existing graphics and recreate (fallback or initial creation)
        self._clear_graphics()
        
        logger.debug(f"PathRenderer({self._coordinate_system}): Starting coordinate filtering...")
        
        # Filter segments by coordinate system using stable snapshot - only render segments matching our renderer type
        matching_segments = [seg for seg, coord_sys in segment_coords if coord_sys == self._coordinate_system]
        
        logger.debug(f"PathRenderer({self._coordinate_system}): Total segments: {len(path.segments)}, matching segments: {len(matching_segments)}")
        for i, (seg, coord_sys) in enumerate(segment_coords):
            logger.debug(f"  Segment {i}: coordinate_system='{coord_sys}', type={type(seg).__name__}")
        
        if not matching_segments:
            # No segments match our coordinate system, nothing to render
            logger.debug(f"PathRenderer({self._coordinate_system}): No matching segments, nothing to render")
            return
            
        # Render path segments with proper sequential progress
        total_segments = len(path.segments)  # Total segments for progress calculation
        current_progress = self._visualization._current_progress
        
        # Calculate which segments should be visible and their individual progress
        for segment_idx, segment in enumerate(path.segments):
            # Only process segments that match our coordinate system
            if segment.coordinate_system != self._coordinate_system:
                logger.debug(f"PathRenderer({self._coordinate_system}): Skipping segment {segment_idx} with coordinate_system='{segment.coordinate_system}'")
                continue
                
            try:
                if segment.segment_type == "cruise":
                    pen = self._visualization._path_pen
                else:  # warp
                    pen = self._visualization._warp_pen
                
                # Calculate segment-specific progress for multi-segment journeys
                segment_start_progress = segment_idx / total_segments
                segment_end_progress = (segment_idx + 1) / total_segments
                segment_progress = 0.0
                
                if current_progress <= segment_start_progress:
                    # Haven't reached this segment yet - show full line
                    segment_progress = 0.0
                elif current_progress >= segment_end_progress:
                    # Completed this segment - don't show line (fully eaten)
                    continue
                else:
                    # Currently in this segment - calculate progress within segment
                    segment_progress = (current_progress - segment_start_progress) / (segment_end_progress - segment_start_progress)
                
                # Check if this segment has waypoints for curved path
                if hasattr(segment, 'waypoints') and segment.waypoints and len(segment.waypoints) > 2:
                    # Render curved path using waypoints
                    logger.debug(f"Rendering curved segment {segment_idx} with {len(segment.waypoints)} waypoints, progress: {segment_progress:.2f}")
                    self._render_curved_segment(segment, pen, segment_progress)
                else:
                    # Render simple straight line with segment-specific progress eating
                    start_x = segment.from_pos.x()
                    start_y = segment.from_pos.y()
                    end_x = segment.to_pos.x()
                    end_y = segment.to_pos.y()
                    
                    # Calculate new start position based on segment progress (line gets eaten from start)
                    new_start_x = start_x + (end_x - start_x) * segment_progress
                    new_start_y = start_y + (end_y - start_y) * segment_progress
                    
                    logger.debug(f"Rendering straight segment {segment_idx} from ({new_start_x:.1f}, {new_start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) [segment progress: {segment_progress:.2f}]")
                    line_item = QGraphicsLineItem(new_start_x, new_start_y, end_x, end_y)
                    line_item.setPen(pen)
                    line_item.setZValue(10)  # Above other items
                    
                    if self._is_scene_valid():
                        self._scene.addItem(line_item)
                        self._path_items.append(line_item)
                    else:
                        # Scene became invalid, stop creating items
                        break
                        
            except Exception:
                # Failed to create or add item, continue with others
                continue
            
        # Create progress indicator only if enabled (system maps only, not galaxy maps)
        if path.segments and self._is_scene_valid() and self._show_progress_dot:
            try:
                # Make progress indicator smaller and less prominent since line eating shows progress
                self._progress_item = QGraphicsEllipseItem(-3, -3, 6, 6)
                self._progress_item.setBrush(self._visualization._progress_brush)
                self._progress_item.setPen(QPen(QColor(255, 255, 255), 1))
                self._progress_item.setZValue(25)  # Above path
                self._progress_item.setOpacity(0.7)  # Slightly transparent
                self._scene.addItem(self._progress_item)
                self._update_progress_indicator(self._visualization._current_progress)
            except Exception:
                # Failed to create progress indicator
                self._progress_item = None
            
    def _update_progress_indicator(self, progress: float) -> None:
        """Update progress indicator position"""
        if not self._progress_item:
            return
            
        # Check if the item is still valid before using it
        try:
            if not self._is_item_valid(self._progress_item):
                self._progress_item = None
                return
        except Exception:
            self._progress_item = None
            return
            
        pos = self._visualization.get_progress_position()
        if pos:
            try:
                self._progress_item.setPos(pos)
                self._progress_item.setVisible(True)
            except (RuntimeError, AttributeError):
                # Item was deleted, clear our reference
                self._progress_item = None
        else:
            try:
                self._progress_item.setVisible(False)
            except (RuntimeError, AttributeError):
                # Item was deleted, clear our reference
                self._progress_item = None
    
    def _render_curved_segment(self, segment, pen, segment_progress: float = 0.0) -> None:
        """Render a straight line segment with line eating effect"""
        try:
            waypoints = segment.waypoints
            if not waypoints or len(waypoints) < 2:
                return
                
            logger.debug(f"Rendering straight line segment from {waypoints[0]} to {waypoints[-1]} with progress {segment_progress}")
                
            # Simple straight line from first to last waypoint
            start_pos = waypoints[0]
            end_pos = waypoints[-1]
            
            # Apply line eating: as progress increases, move the start position forward
            if segment_progress > 0.0:
                logger.debug(f"Applying line eating with segment progress {segment_progress}")
                # Calculate new start position based on segment progress
                new_start_x = start_pos.x() + (end_pos.x() - start_pos.x()) * segment_progress
                new_start_y = start_pos.y() + (end_pos.y() - start_pos.y()) * segment_progress
                start_pos = QPointF(new_start_x, new_start_y)
                logger.debug(f"New start position after line eating: {start_pos}")
            
            # Create straight line
            line_item = QGraphicsLineItem(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())
            line_item.setPen(pen)
            line_item.setZValue(10)
            
            if self._is_scene_valid() and self._scene:
                self._scene.addItem(line_item)
                self._path_items.append(line_item)
                logger.debug(f"Added straight line to scene from ({start_pos.x():.1f}, {start_pos.y():.1f}) to ({end_pos.x():.1f}, {end_pos.y():.1f})")
                    
        except Exception as e:
            logger.error(f"Error rendering straight line segment: {e}")
            # Simple fallback
            if len(segment.waypoints) >= 2:
                start_pos = segment.waypoints[0]
                end_pos = segment.waypoints[-1]
                
                line_item = QGraphicsLineItem(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())
                line_item.setPen(pen)
                line_item.setZValue(10)
                
                if self._is_scene_valid() and self._scene:
                    self._scene.addItem(line_item)
                    self._path_items.append(line_item)
            
    def _clear_graphics(self) -> None:
        """Clear all path graphics safely"""
        if self._scene:
            # Safely remove path items
            items_to_clear = []
            for item in self._path_items:
                try:
                    if self._is_item_valid(item):
                        self._scene.removeItem(item)
                except Exception:
                    # Item was already deleted, ignore
                    pass
                items_to_clear.append(item)
                
            # Safely remove progress item
            if self._progress_item:
                try:
                    if self._is_item_valid(self._progress_item):
                        self._scene.removeItem(self._progress_item)
                except Exception:
                    # Item was already deleted, ignore
                    pass
                self._progress_item = None
                
        self._path_items.clear()
        
    def _is_item_valid(self, item) -> bool:
        """Check if a QGraphicsItem is still valid and not deleted"""
        try:
            # Try to access a simple property to check if the C++ object is still valid
            _ = item.scene()
            return True
        except (RuntimeError, AttributeError):
            # C++ object was deleted
            return False
            
    def _is_scene_valid(self) -> bool:
        """Check if the QGraphicsScene is still valid and not deleted"""
        try:
            # Try to access a simple property to check if the C++ object is still valid
            if self._scene is None:
                return False
            _ = self._scene.items()
            return True
        except (RuntimeError, AttributeError):
            # C++ object was deleted
            return False
