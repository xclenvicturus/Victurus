# /ui/widgets/travel_status_overlay.py

"""
Travel Status Overlay Widget

Shows ship status and travel progress with a visual progress bar when traveling.
Displays travel phases and countdown timer during travel sequences.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

from game_controller.log_config import get_ui_logger
from game import player_status

logger = get_ui_logger('travel_overlay')


class TravelStatusOverlay(QWidget):
    """
    Overlay widget that shows ship status and travel progress.
    Positioned at top center of parent widget.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Widget setup
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True) 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # State
        self._ship_status = ""
        self._travel_info = {}
        self._is_traveling = False
        
        # UI configuration
        self._overlay_height = 80
        self._bar_width = 600
        self._bar_height = 20
        self._phase_marker_height = 30
        
        # Colors
        self._bg_color = QColor(20, 20, 30, 200)  # Semi-transparent dark blue
        self._bar_bg_color = QColor(40, 40, 50, 180)
        self._bar_fill_color = QColor(100, 200, 255, 200)  # Light blue
        self._text_color = QColor(255, 255, 255)
        self._phase_marker_color = QColor(150, 150, 150)
        
        # Update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_ship_status)
        self._update_timer.start(1000)  # Update every second
    
    def set_travel_info(self, travel_info: Dict) -> None:
        """Update travel information"""
        self._travel_info = travel_info
        self._is_traveling = bool(travel_info)
        
        if self._is_traveling:
            logger.debug(f"Travel info updated: {travel_info.get('phase', 'unknown')} - {travel_info.get('progress', 0):.1%}")
        else:
            logger.debug("Travel ended")
        
        self.update()  # Trigger repaint
    
    def _update_ship_status(self) -> None:
        """Update ship status information"""
        try:
            status = player_status.get_status_snapshot()
            if status:
                current_status = status.get('status', 'Unknown')
                system_name = status.get('system_name', 'Unknown System')
                location_name = status.get('location_name', '')
                
                if location_name:
                    self._ship_status = f"{current_status} • {location_name} • {system_name}"
                else:
                    self._ship_status = f"{current_status} • {system_name}"
            else:
                self._ship_status = "Status Unknown"
        except Exception as e:
            logger.error(f"Error updating ship status: {e}")
            self._ship_status = "Status Error"
        
        self.update()
    
    def _position_overlay(self) -> None:
        """Position overlay at top center of parent"""
        parent_widget = self.parent()
        if parent_widget and isinstance(parent_widget, QWidget):
            parent_rect = parent_widget.rect()
            overlay_width = self._bar_width + 40  # Extra padding
            x = (parent_rect.width() - overlay_width) // 2
            y = 10  # Small margin from top
            
            self.setGeometry(x, y, overlay_width, self._overlay_height)
    
    def paintEvent(self, event) -> None:
        """Paint the overlay"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Draw background
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 8, 8)
        
        # Set up font
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.setPen(self._text_color)
        
        # Draw ship status at top
        status_rect = QRect(rect.x() + 10, rect.y() + 10, rect.width() - 20, 20)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self._ship_status)
        
        # Draw travel progress if traveling and not at 100% completion
        if self._is_traveling and self._travel_info:
            progress = self._travel_info.get('progress', 0.0)
            # Hide progress bar when travel reaches 100% (final states like "Docked", "Orbiting")
            if progress < 1.0:
                self._draw_travel_progress(painter, rect)
    
    def _draw_travel_progress(self, painter: QPainter, rect: QRect) -> None:
        """Draw travel progress bar and information"""
        # Get travel info
        progress = self._travel_info.get('progress', 0.0)
        time_remaining = self._travel_info.get('time_remaining', 0)
        current_phase = self._travel_info.get('phase', 'traveling')
        phases = self._travel_info.get('phases', [])
        current_phase_index = self._travel_info.get('current_phase_index', 0)
        
        # Calculate bar position
        bar_x = (rect.width() - self._bar_width) // 2
        bar_y = rect.y() + 35
        
        # Draw progress bar background
        bar_rect = QRect(bar_x, bar_y, self._bar_width, self._bar_height)
        painter.setBrush(QBrush(self._bar_bg_color))
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRoundedRect(bar_rect, 3, 3)
        
        # Draw progress bar fill (fills from left to right 0% to 100%)
        if progress > 0:
            fill_width = int(self._bar_width * progress)
            if fill_width > 0:
                fill_rect = QRect(bar_x, bar_y, fill_width, self._bar_height)
                painter.setBrush(QBrush(self._bar_fill_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(fill_rect, 3, 3)
        
        # Draw phase markers
        if phases and len(phases) > 1:
            self._draw_phase_markers(painter, bar_rect, phases, current_phase_index)
        
        # Draw countdown timer in center of bar
        if time_remaining > 0:
            timer_text = self._format_time(time_remaining)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, timer_text)
        
        # Draw current phase text below bar
        painter.setPen(self._text_color)
        painter.setFont(QFont("Arial", 9))
        phase_text = current_phase  # Use the phase name as-is (already properly formatted)
        phase_rect = QRect(bar_x, bar_y + self._bar_height + 5, self._bar_width, 15)
        painter.drawText(phase_rect, Qt.AlignmentFlag.AlignCenter, phase_text)
    
    def _draw_phase_markers(self, painter: QPainter, bar_rect: QRect, phases: List[str], current_index: int) -> None:
        """Draw vertical lines marking phase boundaries"""
        if len(phases) <= 1:
            return
        
        painter.setPen(QPen(self._phase_marker_color, 1))
        
        # Draw markers at phase boundaries
        phase_width = bar_rect.width() / len(phases)
        
        for i in range(1, len(phases)):  # Skip first (start) and draw markers between phases
            marker_x = bar_rect.x() + int(i * phase_width)
            
            # Make current phase marker more prominent
            if i == current_index:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
            else:
                painter.setPen(QPen(self._phase_marker_color, 1))
            
            painter.drawLine(marker_x, bar_rect.y() - 5, marker_x, bar_rect.bottom() + 5)
    
    def _format_time(self, seconds: int) -> str:
        """Format time in MM:SS format"""
        if seconds <= 0:
            return "0:00"
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}:{remaining_seconds:02d}"
    
    def showEvent(self, event) -> None:
        """Handle widget show"""
        super().showEvent(event)
        self._position_overlay()
