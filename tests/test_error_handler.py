#!/usr/bin/env python3
"""
Test the error handling system to make sure it works correctly.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ui.error_handler import install_error_handler, handle_error
from ui.dialogs.error_reporter_dialog import ErrorReporterDialog
from ui.error_utils import catch_and_log, ErrorContext, safe_call


class ErrorTestWidget(QWidget):
    """Simple widget for testing error handling"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Error Handler Test")
        self.resize(300, 200)
        
        layout = QVBoxLayout(self)
        
        # Button to trigger an uncaught exception
        crash_btn = QPushButton("Test Uncaught Exception")
        crash_btn.clicked.connect(self.trigger_crash)
        layout.addWidget(crash_btn)
        
        # Button to trigger a caught exception
        handled_btn = QPushButton("Test Handled Exception")
        handled_btn.clicked.connect(self.trigger_handled_error)
        layout.addWidget(handled_btn)
        
        # Button to test decorator
        decorator_btn = QPushButton("Test Decorator Error")
        decorator_btn.clicked.connect(self.trigger_decorator_error)
        layout.addWidget(decorator_btn)
        
        # Button to test context manager
        context_btn = QPushButton("Test Context Manager Error")
        context_btn.clicked.connect(self.trigger_context_error)
        layout.addWidget(context_btn)
    
    def trigger_crash(self):
        """Trigger an uncaught exception"""
        print("Triggering uncaught exception...")
        raise RuntimeError("This is a test uncaught exception!")
    
    def trigger_handled_error(self):
        """Trigger a handled exception"""
        print("Triggering handled exception...")
        try:
            raise ValueError("This is a test handled exception!")
        except Exception as e:
            handle_error(e, "Test handled exception button")
    
    @catch_and_log("Decorator test function")
    def trigger_decorator_error(self):
        """Function that will trigger an error caught by decorator"""
        print("Triggering decorator error...")
        raise TypeError("This error should be caught by the decorator!")
    
    def trigger_context_error(self):
        """Test the context manager error handling"""
        print("Triggering context manager error...")
        with ErrorContext("Test context manager"):
            raise ConnectionError("This error should be caught by the context manager!")


def main():
    """Test the error handling system"""
    app = QApplication(sys.argv)
    
    # Install error handler
    error_handler = install_error_handler()
    error_handler.set_app_instance(app)
    error_handler.set_error_dialog_class(ErrorReporterDialog)
    
    # Create test widget
    widget = ErrorTestWidget()
    error_handler.set_main_window(widget)
    widget.show()
    
    print("Error handler test application started")
    print("Click buttons to test different error scenarios")
    
    try:
        return app.exec()
    finally:
        error_handler.uninstall()


if __name__ == "__main__":
    main()
