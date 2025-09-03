# /ui/widgets/travel_status_overlay.py

"""
Travel Status Overlay Widgets

Separate widgets for ship status and travel progress display.
• ShipStatusOverlay: Always visible, shows current ship status and location
• TravelProgressOverlay: Only visible during travel, shows progress bar and countdown
• Both overlays dynamically center on parent widget resize
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, QTimer, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QCursor
from PySide6.QtWidgets import QWidget

from game_controller.log_config import get_ui_logger
from game import player_status

logger = get_ui_logger('travel_overlay')


class ShipStatusOverlay(QWidget):
    """
    Always-visible overlay showing current ship status and location with clickable hyperlinks.
    Dynamically centers itself on parent resize.
    """
    
    # Signals for hyperlink clicks
    system_clicked = Signal(int)  # system_id
    location_clicked = Signal(int)  # location_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Widget setup - IMPORTANT: Don't make transparent to mouse events since we need clicks
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True) 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # State
        self._ship_status = ""
        self._is_traveling = False
        self._current_system_id = None
        self._current_location_id = None
        self._current_system_name = ""
        self._current_location_name = ""
        
        # Click regions (updated during paint)
        self._system_click_rect = QRect()
        self._location_click_rect = QRect()
        
        # UI configuration
        self._overlay_width = 800  # Increased width for hyperlinks
        self._overlay_height = 35
        
        # Colors
        self._bg_color = QColor(20, 20, 30, 180)  # Semi-transparent dark blue
        self._text_color = QColor(255, 255, 255)
        self._link_color = QColor(100, 200, 255)  # Light blue for hyperlinks
        self._link_hover_color = QColor(150, 220, 255)  # Lighter blue for hover
        
        # Hover state
        self._hover_system = False
        self._hover_location = False
        
        # Update timer (slower when not traveling)
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_ship_status)
        self._update_timer.start(1000)  # Update every second by default
        
    def set_travel_active(self, is_traveling: bool) -> None:
        """Set travel state and adjust update frequency accordingly"""
        if self._is_traveling != is_traveling:
            self._is_traveling = is_traveling
            if is_traveling:
                # Update more frequently during travel for better sync
                self._update_timer.setInterval(200)  # 200ms during travel
            else:
                # Return to normal update frequency when travel ends
                self._update_timer.setInterval(1000)  # 1s when not traveling
                
            # Force immediate update when travel state changes
            self._update_ship_status()
    
    def _return_to_normal_frequency(self) -> None:
        """Return update frequency to normal rate after travel ends"""
        if not self._is_traveling:
            self._update_timer.setInterval(1000)  # 1s when not traveling
    
    def _update_ship_status(self) -> None:
        """Update ship status information with location context"""
        try:
            status = player_status.get_status_snapshot()
            if status:
                current_status = status.get('status', 'Unknown')
                system_name = status.get('system_name', 'Unknown System')
                display_location = status.get('display_location', '')
                system_id = status.get('system_id')
                
                # Debug log system changes
                if system_id != self._current_system_id and system_id is not None:
                    logger.debug(f"System changed from {self._current_system_id} to {system_id}: {self._current_system_name} -> {system_name}")
                
                # Store current data for click handling
                self._current_system_id = system_id
                self._current_location_id = status.get('location_id')
                
                # For travel states, display_location contains the proper text ("The Warp" or system name)
                if self._is_travel_related_status(current_status):
                    self._current_system_name = display_location  # Show "The Warp" or system name as appropriate
                    self._current_location_name = display_location
                    location_name = display_location  # For status formatting logic
                else:
                    # For non-travel states, use actual system and location names
                    self._current_system_name = system_name
                    location_name = status.get('location_name', '')
                    self._current_location_name = location_name if location_name else display_location
                
                # Format status with location context
                if current_status == 'Docked' and location_name:
                    self._ship_status = f"Docked"
                elif current_status == 'Orbiting' and location_name:
                    self._ship_status = f"Orbiting"
                elif self._is_travel_related_status(current_status):
                    # All travel-related states show as "Traveling"
                    self._ship_status = "Traveling"
                else:
                    # Fallback for other statuses
                    self._ship_status = current_status
                    
            else:
                self._ship_status = "Status Unknown"
                self._current_system_id = None
                self._current_location_id = None
                self._current_system_name = ""
                self._current_location_name = ""
        except Exception as e:
            logger.error(f"Error updating ship status: {e}")
            self._ship_status = "Status Error"
        
        self.update()
    
    def _is_travel_related_status(self, status: str) -> bool:
        """Check if a status is travel-related and should be shown as 'Traveling'"""
        travel_keywords = [
            'traveling', 'cruise', 'cruising', 'warping', 'warp',
            'entering', 'leaving', 'transit', 'departure', 'arrival'
        ]
        status_lower = status.lower()
        return any(keyword in status_lower for keyword in travel_keywords)
    
    def _position_overlay(self) -> None:
        """Position overlay at top center of parent"""
        parent_widget = self.parent()
        if parent_widget and isinstance(parent_widget, QWidget):
            parent_rect = parent_widget.rect()
            x = (parent_rect.width() - self._overlay_width) // 2
            y = 10  # Small margin from top
            
            self.setGeometry(x, y, self._overlay_width, self._overlay_height)
    
    def paintEvent(self, event) -> None:
        """Paint the status overlay with clickable hyperlinks"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Draw background
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
        
        # Set up font
        font = QFont("Arial", 10)
        painter.setFont(font)
        
        # Calculate text layout
        status_rect = QRect(rect.x() + 10, rect.y() + 8, rect.width() - 20, rect.height() - 16)
        
        # Build display text components
        status_text = self._ship_status
        location_text = self._current_location_name
        system_text = self._current_system_name
        
        if not system_text:
            # Fallback to simple display if no system data
            painter.setPen(self._text_color)
            painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status_text)
            return
        
        # Calculate text layout based on status
        fm = QFontMetrics(font)
        
        # When traveling, only show system; when at location, show both
        is_traveling = self._ship_status == "Traveling"
        
        if is_traveling:
            # Format: "Traveling system_name" (system as hyperlink)
            status_prefix = "Traveling "
            status_width = fm.horizontalAdvance(status_prefix)
            system_width = fm.horizontalAdvance(system_text)
            total_width = status_width + system_width
            
            # Center the text
            start_x = status_rect.center().x() - (total_width // 2)
            text_y = status_rect.center().y() + (fm.height() // 4)
            
            # Draw "Traveling " (normal color)
            painter.setPen(self._text_color)
            painter.drawText(start_x, text_y, status_prefix)
            
            # Draw system hyperlink
            system_color = self._link_hover_color if self._hover_system else self._link_color
            painter.setPen(system_color)
            system_x = start_x + status_width
            self._system_click_rect = QRect(system_x, text_y - fm.height() + fm.descent(), system_width, fm.height())
            painter.drawText(system_x, text_y, system_text)
            
            # Clear location click rect since we don't show location when traveling
            self._location_click_rect = QRect()
            
        else:
            # Format: "Status location_name • system_name" (both as hyperlinks)
            if not location_text:
                # If no location, just show status and system
                status_prefix = f"{status_text} "
                status_width = fm.horizontalAdvance(status_prefix)
                system_width = fm.horizontalAdvance(system_text)
                total_width = status_width + system_width
                
                # Center the text
                start_x = status_rect.center().x() - (total_width // 2)
                text_y = status_rect.center().y() + (fm.height() // 4)
                
                # Draw status (normal color)
                painter.setPen(self._text_color)
                painter.drawText(start_x, text_y, status_prefix)
                
                # Draw system hyperlink
                system_color = self._link_hover_color if self._hover_system else self._link_color
                painter.setPen(system_color)
                system_x = start_x + status_width
                self._system_click_rect = QRect(system_x, text_y - fm.height() + fm.descent(), system_width, fm.height())
                painter.drawText(system_x, text_y, system_text)
                
                # Clear location click rect
                self._location_click_rect = QRect()
            else:
                # Full format with both location and system
                status_width = fm.horizontalAdvance(status_text + " ")
                location_width = fm.horizontalAdvance(location_text)
                separator_width = fm.horizontalAdvance(" • ")
                system_width = fm.horizontalAdvance(system_text)
                
                total_width = status_width + location_width + separator_width + system_width
                
                # Center the entire text block
                start_x = status_rect.center().x() - (total_width // 2)
                text_y = status_rect.center().y() + (fm.height() // 4)
                
                current_x = start_x
                
                # Draw status text (normal color)
                painter.setPen(self._text_color)
                painter.drawText(current_x, text_y, status_text + " ")
                current_x += status_width
                
                # Draw location hyperlink
                location_color = self._link_hover_color if self._hover_location else self._link_color
                painter.setPen(location_color)
                self._location_click_rect = QRect(current_x, text_y - fm.height() + fm.descent(), location_width, fm.height())
                painter.drawText(current_x, text_y, location_text)
                current_x += location_width
                
                # Draw separator
                painter.setPen(self._text_color)
                painter.drawText(current_x, text_y, " • ")
                current_x += separator_width
                
                # Draw system hyperlink
                system_color = self._link_hover_color if self._hover_system else self._link_color
                painter.setPen(system_color)
                self._system_click_rect = QRect(current_x, text_y - fm.height() + fm.descent(), system_width, fm.height())
                painter.drawText(current_x, text_y, system_text)
    
    def resizeEvent(self, event) -> None:
        """Handle parent resize to keep overlay centered"""
        super().resizeEvent(event)
        self._position_overlay()
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse clicks on hyperlinks"""
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = event.pos()
            
            # Check if click is on location hyperlink
            if self._location_click_rect.contains(click_pos) and self._current_location_id:
                logger.debug(f"Location hyperlink clicked: {self._current_location_name} (ID: {self._current_location_id})")
                self.location_clicked.emit(self._current_location_id)
                return
            
            # Check if click is on system hyperlink
            if self._system_click_rect.contains(click_pos) and self._current_system_id:
                logger.debug(f"System hyperlink clicked: {self._current_system_name} (ID: {self._current_system_id})")
                self.system_clicked.emit(self._current_system_id)
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse movement for hover effects"""
        mouse_pos = event.pos()
        
        # Check hover state for location link
        hover_location = self._location_click_rect.contains(mouse_pos)
        hover_system = self._system_click_rect.contains(mouse_pos)
        
        # Update hover state and cursor
        if hover_location or hover_system:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        # Trigger repaint if hover state changed
        if hover_location != self._hover_location or hover_system != self._hover_system:
            self._hover_location = hover_location
            self._hover_system = hover_system
            self.update()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event) -> None:
        """Handle mouse leave - clear hover state"""
        if self._hover_location or self._hover_system:
            self._hover_location = False
            self._hover_system = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()
        super().leaveEvent(event)
    
    def showEvent(self, event) -> None:
        """Handle widget show"""
        super().showEvent(event)
        self._position_overlay()


class DestinationOverlay(QWidget):
    """
    Overlay showing destination system and location name.
    Positioned between status and travel progress overlays.
    Shows origin → destination with clickable hyperlinks.
    """
    
    # Signals for hyperlink clicks
    system_clicked = Signal(int)  # system_id
    location_clicked = Signal(int)  # location_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Widget setup - Enable mouse events for hyperlinks
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True) 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # State
        self._destination_text = ""
        self._travel_route = {}
        
        # Click regions (updated during paint)
        self._origin_location_rect = QRect()
        self._origin_system_rect = QRect()
        self._dest_location_rect = QRect()
        self._dest_system_rect = QRect()
        
        # Hover state
        self._hover_origin_location = False
        self._hover_origin_system = False
        self._hover_dest_location = False
        self._hover_dest_system = False
        
        # UI configuration
        self._overlay_width = 800  # Increased width for current → destination format
        self._overlay_height = 35
        
        # Colors
        self._bg_color = QColor(20, 40, 20, 180)  # Semi-transparent dark green
        self._text_color = QColor(200, 255, 200)  # Light green text
        self._link_color = QColor(150, 255, 150)  # Light green for hyperlinks
        self._link_hover_color = QColor(200, 255, 200)  # Lighter green for hover
        
        # Update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_destination)
        self._update_timer.start(1000)  # Update every second
        
        # Start hidden - only show when traveling
        self.hide()
    
    def set_travel_flow(self, travel_flow):
        """Set the travel flow to get route information from"""
        self._travel_flow = travel_flow
        
    def _update_destination(self) -> None:
        """Update destination information with origin → destination and hyperlinks"""
        try:
            status = player_status.get_status_snapshot()
            if status:
                current_status = status.get('status', 'Unknown')
                logger.debug(f"DestinationOverlay: current_status = {current_status}")
                
                # Show destination overlay during any travel state (not just "Traveling")
                # Travel states include: "Leaving Orbit", "Entering Orbit", "Leaving Cruise", "Warping", etc.
                is_traveling = current_status not in ['Docked', 'Orbiting'] and current_status != 'Unknown'
                
                if is_traveling:
                    logger.debug(f"DestinationOverlay: Travel state detected ({current_status}), checking travel_flow")
                    
                    if hasattr(self, '_travel_flow') and self._travel_flow:
                        logger.debug(f"DestinationOverlay: Travel flow available")
                        # Get travel route information from TravelFlow
                        try:
                            self._travel_route = self._travel_flow.get_travel_route()
                            logger.debug(f"DestinationOverlay: Got travel route: {self._travel_route}")
                            
                            origin_location = self._travel_route.get('origin_location_name', '')
                            origin_system = self._travel_route.get('origin_system_name', '')
                            dest_location = self._travel_route.get('dest_location_name', '')
                            dest_system = self._travel_route.get('dest_system_name', '')
                            
                            # Build origin and destination descriptions
                            if origin_location and origin_system and not origin_location.endswith('(Star)'):
                                origin_desc = f"{origin_location} • {origin_system}"
                            else:
                                origin_desc = origin_system
                                
                            if dest_location and dest_system and not dest_location.endswith('(Star)'):
                                dest_desc = f"{dest_location} • {dest_system}"
                            else:
                                dest_desc = dest_system
                            
                            # Show origin → destination format
                            self._destination_text = f"{origin_desc} → {dest_desc}"
                            logger.debug(f"DestinationOverlay: Set destination text: {self._destination_text}")
                            
                            # Store for painting and clicking
                            self._travel_route = {
                                'origin_location_name': origin_location,
                                'origin_system_name': origin_system,
                                'origin_location_id': self._travel_route.get('origin_location_id'),
                                'origin_system_id': self._travel_route.get('origin_system_id'),
                                'dest_location_name': dest_location,
                                'dest_system_name': dest_system,
                                'dest_location_id': self._travel_route.get('dest_location_id'),
                                'dest_system_id': self._travel_route.get('dest_system_id'),
                            }
                            
                        except Exception as e:
                            logger.error(f"Error getting travel route: {e}")
                            self._destination_text = "Travel Route Unknown"
                            self._travel_route = {}
                    else:
                        logger.debug(f"DestinationOverlay: No travel flow available (hasattr: {hasattr(self, '_travel_flow')}, value: {getattr(self, '_travel_flow', None)})")
                        self._destination_text = ""
                        self._travel_route = {}
                else:
                    logger.debug(f"DestinationOverlay: Not traveling, hiding overlay")
                    # When not traveling, hide the overlay
                    self._destination_text = ""
                    self._travel_route = {}
                        
                if self._destination_text and not self.isVisible():
                    logger.debug(f"DestinationOverlay: Showing overlay with text: {self._destination_text}")
                    self.show()
                    self._position_overlay()
                elif not self._destination_text and self.isVisible():
                    logger.debug(f"DestinationOverlay: Hiding overlay")
                    self.hide()
            else:
                self._destination_text = ""
                if self.isVisible():
                    self.hide()
        except Exception as e:
            logger.error(f"Error updating destination: {e}")
            self._destination_text = "Location: Error"
        
        self.update()
    
    def _position_overlay(self) -> None:
        """Position overlay between status and travel progress overlays"""
        parent_widget = self.parent()
        if parent_widget and isinstance(parent_widget, QWidget):
            parent_rect = parent_widget.rect()
            x = (parent_rect.width() - self._overlay_width) // 2
            y = 55  # Below status overlay (10 + 35 + 10 margin)
            
            self.setGeometry(x, y, self._overlay_width, self._overlay_height)
    
    def paintEvent(self, event) -> None:
        """Paint the destination overlay with clickable hyperlinks"""
        if not self._destination_text or not self._travel_route:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Draw background
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(100, 150, 100), 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
        
        # Set up font
        font = QFont("Arial", 10)
        painter.setFont(font)
        fm = QFontMetrics(font)
        
        # Get route information
        origin_location = self._travel_route.get('origin_location_name', '')
        origin_system = self._travel_route.get('origin_system_name', '')
        dest_location = self._travel_route.get('dest_location_name', '')
        dest_system = self._travel_route.get('dest_system_name', '')
        
        # Build text components
        origin_has_location = origin_location and not origin_location.endswith('(Star)')
        dest_has_location = dest_location and not dest_location.endswith('(Star)')
        
        # Calculate text layout
        text_y = rect.center().y() + (fm.height() // 4)
        total_width = 0
        
        # Calculate component widths
        origin_location_width = fm.horizontalAdvance(origin_location) if origin_has_location else 0
        origin_system_width = fm.horizontalAdvance(origin_system)
        arrow_width = fm.horizontalAdvance(" → ")
        dest_location_width = fm.horizontalAdvance(dest_location) if dest_has_location else 0
        dest_system_width = fm.horizontalAdvance(dest_system)
        separator_width = fm.horizontalAdvance(" • ")
        
        if origin_has_location:
            total_width += origin_location_width + separator_width + origin_system_width
        else:
            total_width += origin_system_width
            
        total_width += arrow_width
        
        if dest_has_location:
            total_width += dest_location_width + separator_width + dest_system_width
        else:
            total_width += dest_system_width
        
        # Center the entire text block
        current_x = rect.center().x() - (total_width // 2)
        
        # Clear all click regions
        self._origin_location_rect = QRect()
        self._origin_system_rect = QRect()
        self._dest_location_rect = QRect()
        self._dest_system_rect = QRect()
        
        # Draw origin
        if origin_has_location:
            # Draw origin location hyperlink
            location_color = self._link_hover_color if self._hover_origin_location else self._link_color
            painter.setPen(location_color)
            self._origin_location_rect = QRect(current_x, text_y - fm.height() + fm.descent(), origin_location_width, fm.height())
            painter.drawText(current_x, text_y, origin_location)
            current_x += origin_location_width
            
            # Draw separator
            painter.setPen(self._text_color)
            painter.drawText(current_x, text_y, " • ")
            current_x += separator_width
        
        # Draw origin system hyperlink
        system_color = self._link_hover_color if self._hover_origin_system else self._link_color
        painter.setPen(system_color)
        self._origin_system_rect = QRect(current_x, text_y - fm.height() + fm.descent(), origin_system_width, fm.height())
        painter.drawText(current_x, text_y, origin_system)
        current_x += origin_system_width
        
        # Draw arrow
        painter.setPen(self._text_color)
        painter.drawText(current_x, text_y, " → ")
        current_x += arrow_width
        
        # Draw destination
        if dest_has_location:
            # Draw dest location hyperlink
            location_color = self._link_hover_color if self._hover_dest_location else self._link_color
            painter.setPen(location_color)
            self._dest_location_rect = QRect(current_x, text_y - fm.height() + fm.descent(), dest_location_width, fm.height())
            painter.drawText(current_x, text_y, dest_location)
            current_x += dest_location_width
            
            # Draw separator
            painter.setPen(self._text_color)
            painter.drawText(current_x, text_y, " • ")
            current_x += separator_width
        
        # Draw dest system hyperlink
        system_color = self._link_hover_color if self._hover_dest_system else self._link_color
        painter.setPen(system_color)
        self._dest_system_rect = QRect(current_x, text_y - fm.height() + fm.descent(), dest_system_width, fm.height())
        painter.drawText(current_x, text_y, dest_system)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse clicks on hyperlinks"""
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = event.pos()
            
            # Check origin location click
            if self._origin_location_rect.contains(click_pos):
                origin_loc_id = self._travel_route.get('origin_location_id')
                if origin_loc_id:
                    logger.debug(f"Origin location hyperlink clicked: {self._travel_route.get('origin_location_name')} (ID: {origin_loc_id})")
                    self.location_clicked.emit(origin_loc_id)
                return
            
            # Check origin system click
            if self._origin_system_rect.contains(click_pos):
                origin_sys_id = self._travel_route.get('origin_system_id')
                if origin_sys_id:
                    logger.debug(f"Origin system hyperlink clicked: {self._travel_route.get('origin_system_name')} (ID: {origin_sys_id})")
                    self.system_clicked.emit(origin_sys_id)
                return
            
            # Check dest location click
            if self._dest_location_rect.contains(click_pos):
                dest_loc_id = self._travel_route.get('dest_location_id')
                if dest_loc_id:
                    logger.debug(f"Dest location hyperlink clicked: {self._travel_route.get('dest_location_name')} (ID: {dest_loc_id})")
                    self.location_clicked.emit(dest_loc_id)
                return
            
            # Check dest system click
            if self._dest_system_rect.contains(click_pos):
                dest_sys_id = self._travel_route.get('dest_system_id')
                if dest_sys_id:
                    logger.debug(f"Dest system hyperlink clicked: {self._travel_route.get('dest_system_name')} (ID: {dest_sys_id})")
                    self.system_clicked.emit(dest_sys_id)
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse movement for hover effects"""
        mouse_pos = event.pos()
        
        # Check hover state for all hyperlinks
        hover_origin_location = self._origin_location_rect.contains(mouse_pos)
        hover_origin_system = self._origin_system_rect.contains(mouse_pos)
        hover_dest_location = self._dest_location_rect.contains(mouse_pos)
        hover_dest_system = self._dest_system_rect.contains(mouse_pos)
        
        # Update cursor
        if hover_origin_location or hover_origin_system or hover_dest_location or hover_dest_system:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        # Trigger repaint if hover state changed
        if (hover_origin_location != self._hover_origin_location or 
            hover_origin_system != self._hover_origin_system or
            hover_dest_location != self._hover_dest_location or
            hover_dest_system != self._hover_dest_system):
            
            self._hover_origin_location = hover_origin_location
            self._hover_origin_system = hover_origin_system
            self._hover_dest_location = hover_dest_location
            self._hover_dest_system = hover_dest_system
            self.update()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event) -> None:
        """Handle mouse leave - clear hover state"""
        self._hover_origin_location = False
        self._hover_origin_system = False
        self._hover_dest_location = False
        self._hover_dest_system = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()
        super().leaveEvent(event)
    
    def resizeEvent(self, event) -> None:
        """Handle parent resize to keep overlay centered"""
        super().resizeEvent(event)
        self._position_overlay()
    
    def showEvent(self, event) -> None:
        """Handle widget show"""
        super().showEvent(event)
        self._position_overlay()


class TravelProgressOverlay(QWidget):
    """
    Travel progress overlay that appears during travel.
    Shows progress bar, countdown timer, and phase information.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Widget setup
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True) 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # State
        self._travel_info = {}
        self._is_traveling = False
        
        # UI configuration 
        self._overlay_width = 800  # Match other overlays width
        self._overlay_height = 80  # Increased height to prevent text cutoff
        self._bar_width = 600  # Longer bar to better fill the wider overlay
        self._bar_height = 20
        
        # Colors - restored to original blue theme
        self._bg_color = QColor(30, 30, 50, 220)  # Semi-transparent dark blue
        self._bar_bg_color = QColor(50, 50, 70, 180)
        self._bar_fill_color = QColor(80, 150, 255, 220)  # Bright blue
        self._text_color = QColor(255, 255, 255)
        self._phase_marker_color = QColor(180, 180, 180)
        
        # Start hidden
        self.hide()
    
    def set_travel_info(self, travel_info: Dict) -> None:
        """Update travel information and show/hide overlay as needed"""
        self._travel_info = travel_info
        self._is_traveling = bool(travel_info)
        
        if self._is_traveling:
            time_remaining = travel_info.get('time_remaining', 0)
            progress = travel_info.get('progress', 0.0)
            phase = travel_info.get('phase', 'traveling')
            logger.debug(f"Travel progress: {phase} - {progress:.1%} - {time_remaining}s remaining")
            self.show()
            self._position_overlay()
        else:
            logger.debug("Travel ended - hiding progress overlay")
            self.hide()
        
        self.update()  # Trigger repaint
    
    def _position_overlay(self) -> None:
        """Position overlay at top under the destination overlay"""
        parent_widget = self.parent()
        if parent_widget and isinstance(parent_widget, QWidget):
            parent_rect = parent_widget.rect()
            x = (parent_rect.width() - self._overlay_width) // 2
            y = 100  # Below destination overlay (10 + 35 + 10 + 35 + 10 margin)
            
            self.setGeometry(x, y, self._overlay_width, self._overlay_height)
    
    def paintEvent(self, event) -> None:
        """Paint the progress overlay"""
        if not self._is_traveling or not self._travel_info:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Draw background with border
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(120, 120, 140), 2))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
        
        self._draw_travel_progress(painter, rect)
    
    def _draw_travel_progress(self, painter: QPainter, rect: QRect) -> None:
        """Draw travel progress bar and information"""
        # Get travel info
        progress = self._travel_info.get('progress', 0.0)
        time_remaining = self._travel_info.get('time_remaining', 0)
        current_phase = self._travel_info.get('phase', 'Traveling')
        phases = self._travel_info.get('phases', [])
        current_phase_index = self._travel_info.get('current_phase_index', 0)
        
        # Calculate bar position (centered in overlay)
        bar_x = (rect.width() - self._bar_width) // 2
        bar_y = rect.y() + 35  # Center the bar vertically in the 80px overlay
        
        # Draw progress bar background
        bar_rect = QRect(bar_x, bar_y, self._bar_width, self._bar_height)
        painter.setBrush(QBrush(self._bar_bg_color))
        painter.setPen(QPen(QColor(100, 100, 120), 1))
        painter.drawRoundedRect(bar_rect, 4, 4)
        
        # Draw progress bar fill
        if progress > 0:
            fill_width = max(1, int(self._bar_width * progress))
            fill_rect = QRect(bar_x, bar_y, fill_width, self._bar_height)
            painter.setBrush(QBrush(self._bar_fill_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_rect, 4, 4)
        
        # Draw phase markers (tick bars)
        if phases and len(phases) > 1:
            self._draw_phase_markers(painter, bar_rect, phases, current_phase_index)
        
        # Draw time remaining in center of progress bar (instead of percentage)
        if time_remaining > 0:
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            timer_text = self._format_time(time_remaining)
            painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, timer_text)
        
        # Draw current phase text above progress bar
        painter.setPen(self._text_color)
        painter.setFont(QFont("Arial", 10))
        phase_rect = QRect(bar_x, bar_y - 20, self._bar_width, 18)  # Adjusted position for better centering
        painter.drawText(phase_rect, Qt.AlignmentFlag.AlignCenter, current_phase)
    
    def _draw_phase_markers(self, painter: QPainter, bar_rect: QRect, phases: list, current_phase_index: int) -> None:
        """Draw tick marks on progress bar to show phase transitions"""
        if not phases or len(phases) <= 1:
            return
        
        # Set up pen for markers
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        
        # Calculate phase positions along the progress bar
        for i in range(1, len(phases)):  # Skip first phase (start)
            # Calculate position as fraction of total progress
            phase_position = i / len(phases)
            tick_x = bar_rect.x() + int(bar_rect.width() * phase_position)
            
            # Draw tick mark
            tick_top = bar_rect.y() - 2
            tick_bottom = bar_rect.y() + bar_rect.height() + 2
            painter.drawLine(tick_x, tick_top, tick_x, tick_bottom)
            
            # Highlight current phase marker
            if i == current_phase_index:
                painter.setPen(QPen(QColor(255, 255, 100), 3))
                painter.drawLine(tick_x, tick_top, tick_x, tick_bottom)
                painter.setPen(QPen(QColor(200, 200, 200), 2))  # Reset pen

    def _format_time(self, seconds: int) -> str:
        """Format time in MM:SS format"""
        if seconds <= 0:
            return "0:00"
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}:{remaining_seconds:02d}"
    
    def resizeEvent(self, event) -> None:
        """Handle parent resize to keep overlay centered"""
        super().resizeEvent(event)
        self._position_overlay()
    
    def showEvent(self, event) -> None:
        """Handle widget show"""
        super().showEvent(event)
        self._position_overlay()


# Legacy class for backward compatibility - now delegates to separate overlays
class TravelStatusOverlay(QWidget):
    """
    Legacy wrapper that creates and manages both status and progress overlays.
    Maintained for backward compatibility with existing code.
    """
    
    # Navigation signals for hyperlink clicks
    system_clicked = Signal(int)  # system_id  
    location_clicked = Signal(int)  # location_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create the three separate overlays
        self._status_overlay = ShipStatusOverlay(parent)
        self._destination_overlay = DestinationOverlay(parent)
        self._progress_overlay = TravelProgressOverlay(parent)
        
        # Connect hyperlink signals from status overlay
        self._status_overlay.system_clicked.connect(self.system_clicked)
        self._status_overlay.location_clicked.connect(self.location_clicked)
        
        # Connect hyperlink signals from destination overlay
        self._destination_overlay.system_clicked.connect(self.system_clicked)
        self._destination_overlay.location_clicked.connect(self.location_clicked)
        
        # Connect the parent resize event to all overlays
        if parent:
            parent.installEventFilter(self)
    
    def set_travel_info(self, travel_info: Dict) -> None:
        """Update travel information - delegates to progress overlay and notifies status overlay"""
        # Update progress overlay (existing functionality)
        self._progress_overlay.set_travel_info(travel_info)
        
        # Notify status overlay of travel state changes for better timing synchronization
        is_traveling = bool(travel_info)
        self._status_overlay.set_travel_active(is_traveling)
    
    def set_travel_flow(self, travel_flow) -> None:
        """Set the travel flow for destination overlay to get route information"""
        self._destination_overlay.set_travel_flow(travel_flow)
    
    def eventFilter(self, obj, event) -> bool:
        """Handle parent resize events to reposition overlays"""
        if event.type() == event.Type.Resize:
            QTimer.singleShot(0, self._reposition_overlays)
        return super().eventFilter(obj, event)
    
    def _reposition_overlays(self) -> None:
        """Reposition all overlays after parent resize"""
        self._status_overlay._position_overlay()
        self._destination_overlay._position_overlay()
        if self._progress_overlay.isVisible():
            self._progress_overlay._position_overlay()
    
    def show(self) -> None:
        """Show status overlay and conditionally show destination/progress overlays"""
        self._status_overlay.show()
        # Destination and progress overlays show themselves based on travel state
    
    def hide(self) -> None:
        """Hide all overlays"""
        self._status_overlay.hide()
        self._destination_overlay.hide()
        self._progress_overlay.hide()
    
    def raise_(self) -> None:
        """Raise all overlays"""
        self._status_overlay.raise_()
        self._destination_overlay.raise_()
        self._progress_overlay.raise_()
