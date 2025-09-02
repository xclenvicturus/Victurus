# /game_controller/log_config.py
"""
Victurus Comprehensive Logging Configuration

Organizes different types of log messages into appropriate files:
- travel_debug.log: Travel system, path calculation, and visualization messages
- ui_debug.log: UI state, widget interactions, and interface events
- game_debug.log: Game logic, simulation, and player actions
- error.log: Errors and exceptions
- warning.log: Warning messages
- system_debug.log: System-level messages and general debugging
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from datetime import datetime


class VicturusLogConfig:
    """Centralized logging configuration for Victurus"""
    
    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._configured = False
    
    def setup_logging(self) -> None:
        """Set up all log handlers and loggers"""
        if self._configured:
            return
            
        # Create custom formatter
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Create specialized loggers and handlers
        self._setup_travel_logging(formatter)
        self._setup_ui_logging(formatter)
        self._setup_game_logging(formatter)
        self._setup_error_logging(formatter)
        self._setup_warning_logging(formatter)
        self._setup_system_logging(formatter)
        
        # Set up third-party logger levels
        logging.getLogger('PySide6').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        self._configured = True
    
    def _create_rotating_handler(self, filename: str, formatter: logging.Formatter, 
                               level: int = logging.DEBUG) -> logging.handlers.RotatingFileHandler:
        """Create a rotating file handler"""
        handler = logging.handlers.RotatingFileHandler(
            self.logs_dir / filename,
            maxBytes=5_000_000,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
    
    def _setup_travel_logging(self, formatter: logging.Formatter) -> None:
        """Set up travel system logging"""
        travel_logger = logging.getLogger('travel')
        travel_logger.setLevel(logging.DEBUG)
        travel_handler = self._create_rotating_handler('travel_debug.log', formatter)
        travel_logger.addHandler(travel_handler)
        travel_logger.propagate = False
        
        # Add specific loggers for travel components
        for component in ['travel_visualization', 'travel_coordinator', 'pathfinding']:
            component_logger = logging.getLogger(f'travel.{component}')
            component_logger.addHandler(travel_handler)
            component_logger.propagate = False
    
    def _setup_ui_logging(self, formatter: logging.Formatter) -> None:
        """Set up UI system logging"""
        ui_logger = logging.getLogger('ui')
        ui_logger.setLevel(logging.DEBUG)
        ui_handler = self._create_rotating_handler('ui_debug.log', formatter)
        ui_logger.addHandler(ui_handler)
        ui_logger.propagate = False
        
        # Keep the original ui_state_debug.log for backward compatibility
        ui_state_handler = self._create_rotating_handler('ui_state_debug.log', formatter)
        ui_state_logger = logging.getLogger('ui.state')
        ui_state_logger.addHandler(ui_state_handler)
        ui_state_logger.propagate = False
    
    def _setup_game_logging(self, formatter: logging.Formatter) -> None:
        """Set up game logic logging"""
        game_logger = logging.getLogger('game')
        game_logger.setLevel(logging.DEBUG)
        game_handler = self._create_rotating_handler('game_debug.log', formatter)
        game_logger.addHandler(game_handler)
        game_logger.propagate = False
        
        # Add specific loggers for game components
        for component in ['simulation', 'player', 'universe', 'economy']:
            component_logger = logging.getLogger(f'game.{component}')
            component_logger.addHandler(game_handler)
            component_logger.propagate = False
    
    def _setup_error_logging(self, formatter: logging.Formatter) -> None:
        """Set up error logging"""
        error_handler = self._create_rotating_handler('error.log', formatter, logging.ERROR)
        
        # Create error filter
        class ErrorFilter(logging.Filter):
            def filter(self, record):
                return record.levelno >= logging.ERROR
        
        error_handler.addFilter(ErrorFilter())
        
        # Add to root logger so all errors are captured
        root_logger = logging.getLogger()
        root_logger.addHandler(error_handler)
    
    def _setup_warning_logging(self, formatter: logging.Formatter) -> None:
        """Set up warning logging"""
        warning_handler = self._create_rotating_handler('warning.log', formatter, logging.WARNING)
        
        # Create warning filter
        class WarningFilter(logging.Filter):
            def filter(self, record):
                return record.levelno == logging.WARNING
        
        warning_handler.addFilter(WarningFilter())
        
        # Add to root logger so all warnings are captured
        root_logger = logging.getLogger()
        root_logger.addHandler(warning_handler)
    
    def _setup_system_logging(self, formatter: logging.Formatter) -> None:
        """Set up system-level logging"""
        system_logger = logging.getLogger('system')
        system_logger.setLevel(logging.DEBUG)
        system_handler = self._create_rotating_handler('system_debug.log', formatter)
        system_logger.addHandler(system_handler)
        system_logger.propagate = False
        
        # Add specific loggers for system components
        for component in ['database', 'config', 'startup', 'shutdown']:
            component_logger = logging.getLogger(f'system.{component}')
            component_logger.addHandler(system_handler)
            component_logger.propagate = False


def setup_victurus_logging(logs_dir: Path) -> VicturusLogConfig:
    """Set up comprehensive logging for Victurus"""
    config = VicturusLogConfig(logs_dir)
    config.setup_logging()
    return config


def get_travel_logger(name: str = 'travel') -> logging.Logger:
    """Get a logger for travel system components"""
    return logging.getLogger(f'travel.{name}' if not name.startswith('travel') else name)


def get_ui_logger(name: str = 'ui') -> logging.Logger:
    """Get a logger for UI components"""
    return logging.getLogger(f'ui.{name}' if not name.startswith('ui') else name)


def get_game_logger(name: str = 'game') -> logging.Logger:
    """Get a logger for game logic components"""
    return logging.getLogger(f'game.{name}' if not name.startswith('game') else name)


def get_system_logger(name: str = 'system') -> logging.Logger:
    """Get a logger for system components"""
    return logging.getLogger(f'system.{name}' if not name.startswith('system') else name)
