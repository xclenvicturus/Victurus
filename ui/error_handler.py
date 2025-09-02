# /ui/error_handler.py

"""
Global Error Handler for Victurus

Provides comprehensive error catching, logging, and reporting functionality.
Integrates with the existing logging system and shows user-friendly error dialogs.
"""

from __future__ import annotations

import sys
import traceback
import logging
import threading
from typing import Optional, Callable, Any
from pathlib import Path

# Import Qt components with fallback
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QApplication = None
    QMessageBox = None
    QTimer = None


class ErrorHandler:
    """
    Global error handler that captures exceptions, logs them, and shows user dialogs.
    """
    
    _instance: Optional['ErrorHandler'] = None
    _original_excepthook: Optional[Callable] = None
    _qt_message_handler = None
    
    def __init__(self):
        self.logger = logging.getLogger('victurus.errors')
        self._error_dialog_class = None
        self._app_instance = None
        self._main_window = None
        
        # Thread safety
        self._lock = threading.Lock()
        self._error_count = 0
        self._max_error_dialogs = 3  # Prevent dialog spam
    
    @classmethod
    def get_instance(cls) -> 'ErrorHandler':
        """Get or create the singleton error handler instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def install(self):
        """Install the global error handler"""
        with self._lock:
            if self._original_excepthook is None:
                self._original_excepthook = sys.excepthook
                sys.excepthook = self._handle_exception
                self.logger.info("Global exception handler installed")
                
            # Install Qt message handler if available
            if QT_AVAILABLE:
                try:
                    from PySide6.QtCore import qInstallMessageHandler
                    qInstallMessageHandler(self._handle_qt_message)
                    self.logger.info("Qt message handler installed")
                except ImportError:
                    pass
    
    def uninstall(self):
        """Uninstall the global error handler"""
        with self._lock:
            if self._original_excepthook is not None:
                sys.excepthook = self._original_excepthook
                self._original_excepthook = None
                self.logger.info("Global exception handler uninstalled")
    
    def set_error_dialog_class(self, dialog_class):
        """Set the error dialog class to use for displaying errors"""
        self._error_dialog_class = dialog_class
    
    def set_app_instance(self, app):
        """Set the QApplication instance"""
        self._app_instance = app
    
    def set_main_window(self, window):
        """Set the main window instance"""
        self._main_window = window
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        # Don't handle KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            if self._original_excepthook:
                self._original_excepthook(exc_type, exc_value, exc_traceback)
            return
        
        with self._lock:
            self._error_count += 1
        
        # Log the error
        self.logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Show error dialog if we haven't shown too many
        if self._error_count <= self._max_error_dialogs and QT_AVAILABLE:
            try:
                self._show_error_dialog((exc_type, exc_value, exc_traceback), "Uncaught Exception")
            except Exception as e:
                self.logger.error(f"Failed to show error dialog: {e}")
        
        # Call original handler as fallback
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_traceback)
    
    def _handle_qt_message(self, msg_type, context, message):
        """Handle Qt debug/warning/error messages"""
        # Map Qt message types to logging levels
        if hasattr(logging, 'QtCore'):
            qt_logger = logging.getLogger('victurus.qt')
        else:
            qt_logger = self.logger
        
        # Convert Qt message type to logging level
        try:
            from PySide6.QtCore import QtMsgType
            if msg_type == QtMsgType.QtDebugMsg:
                qt_logger.debug(f"Qt: {message}")
            elif msg_type == QtMsgType.QtWarningMsg:
                qt_logger.warning(f"Qt: {message}")
            elif msg_type == QtMsgType.QtCriticalMsg:
                qt_logger.error(f"Qt Critical: {message}")
            elif msg_type == QtMsgType.QtFatalMsg:
                qt_logger.critical(f"Qt Fatal: {message}")
            else:
                qt_logger.info(f"Qt: {message}")
        except ImportError:
            # Fallback if Qt types not available
            self.logger.info(f"Qt Message: {message}")
    
    def _show_error_dialog(self, exception_info: tuple, context: str):
        """Show the error dialog in a thread-safe way"""
        if not QT_AVAILABLE or not self._app_instance:
            return
        
        try:
            # Use QTimer to show dialog on the main thread
            def show_dialog():
                try:
                    if self._error_dialog_class:
                        dialog = self._error_dialog_class(
                            exception_info, 
                            context, 
                            self._main_window
                        )
                        dialog.show()
                    else:
                        # Fallback to simple message box
                        if QMessageBox:
                            exc_type, exc_value, exc_traceback = exception_info
                            QMessageBox.critical(
                                self._main_window,
                                "Victurus Error",
                                f"An error occurred:\n\n{exc_type.__name__}: {exc_value}\n\n"
                                f"Please check the logs for more details."
                            )
                except Exception as e:
                    self.logger.error(f"Failed to show error dialog: {e}")
            
            if QTimer:
                QTimer.singleShot(0, show_dialog)
            else:
                show_dialog()
                
        except Exception as e:
            self.logger.error(f"Error in _show_error_dialog: {e}")
    
    def handle_error(self, exception: Exception, context: str = ""):
        """
        Manually handle an error (for use in try/catch blocks).
        
        Args:
            exception: The exception that occurred
            context: Description of what was happening when the error occurred
        """
        # Log the error
        self.logger.error(f"Error in {context}: {exception}", exc_info=True)
        
        # Show dialog if appropriate
        if self._error_count < self._max_error_dialogs and QT_AVAILABLE:
            try:
                exc_info = (type(exception), exception, exception.__traceback__)
                self._show_error_dialog(exc_info, context)
                with self._lock:
                    self._error_count += 1
            except Exception as e:
                self.logger.error(f"Failed to show error dialog: {e}")
    
    def log_warning(self, message: str, context: str = ""):
        """Log a warning message"""
        full_message = f"{context}: {message}" if context else message
        self.logger.warning(full_message)
    
    def log_info(self, message: str, context: str = ""):
        """Log an info message"""
        full_message = f"{context}: {message}" if context else message
        self.logger.info(full_message)


# Convenience functions for global access
def install_error_handler():
    """Install the global error handler"""
    handler = ErrorHandler.get_instance()
    handler.install()
    return handler


def handle_error(exception: Exception, context: str = ""):
    """Handle an error with the global error handler"""
    handler = ErrorHandler.get_instance()
    handler.handle_error(exception, context)


def log_warning(message: str, context: str = ""):
    """Log a warning with the global error handler"""
    handler = ErrorHandler.get_instance()
    handler.log_warning(message, context)


def log_info(message: str, context: str = ""):
    """Log info with the global error handler"""
    handler = ErrorHandler.get_instance()
    handler.log_info(message, context)
