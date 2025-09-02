"""
Error Reporter Dialog for Victurus

Provides a user-friendly dialog to display crashes and errors with copy functionality.
"""

from __future__ import annotations

import sys
import traceback
import platform
import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QDialogButtonBox, QMessageBox, QScrollArea, QWidget,
    QSplitter, QTreeWidget, QTreeWidgetItem, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QClipboard

from game_controller.log_config import get_system_logger

logger = get_system_logger('error_dialog')

class ErrorReporterDialog(QDialog):
    """
    Dialog for displaying detailed error information with copy functionality.
    Shows exception details, system info, and allows easy copying for bug reports.
    """
    
    def __init__(self, exception_info: tuple, context: str = "", parent=None):
        super().__init__(parent)
        self.exception_info = exception_info
        self.context = context
        
        self.setWindowTitle("Victurus - Error Report")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        # Make dialog modal but not blocking
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        
        self._setup_ui()
        self._populate_error_info()
    
    def _setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Header with error summary
        header_label = QLabel("An error has occurred in Victurus")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #d32f2f; padding: 10px;")
        layout.addWidget(header_label)
        
        # Instructions
        instructions = QLabel(
            "Please copy the error details below and report this issue. "
            "The application will continue running, but some features may not work correctly."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(instructions)
        
        # Splitter for error details and system info
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Error details section
        error_widget = QWidget()
        error_layout = QVBoxLayout(error_widget)
        error_layout.setContentsMargins(0, 0, 0, 0)
        
        error_label = QLabel("Error Details:")
        error_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        error_layout.addWidget(error_label)
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setFont(QFont("Consolas", 9))
        self.error_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 8px;
            }
        """)
        error_layout.addWidget(self.error_text)
        
        splitter.addWidget(error_widget)
        
        # System info section
        system_widget = QWidget()
        system_layout = QVBoxLayout(system_widget)
        system_layout.setContentsMargins(0, 0, 0, 0)
        
        system_label = QLabel("System Information:")
        system_label.setStyleSheet("font-weight: bold; padding: 5px 0;")
        system_layout.addWidget(system_label)
        
        self.system_text = QTextEdit()
        self.system_text.setReadOnly(True)
        self.system_text.setFont(QFont("Consolas", 8))
        self.system_text.setMaximumHeight(150)
        self.system_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ccc;
                padding: 8px;
            }
        """)
        system_layout.addWidget(self.system_text)
        
        splitter.addWidget(system_widget)
        
        # Set splitter proportions (error details get more space)
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.copy_all_btn = QPushButton("Copy All to Clipboard")
        self.copy_all_btn.clicked.connect(self._copy_all)
        self.copy_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        button_layout.addWidget(self.copy_all_btn)
        
        self.copy_error_btn = QPushButton("Copy Error Only")
        self.copy_error_btn.clicked.connect(self._copy_error_only)
        button_layout.addWidget(self.copy_error_btn)
        
        button_layout.addStretch()
        
        # Standard dialog buttons
        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.dialog_buttons.rejected.connect(self.accept)  # Close dialog
        button_layout.addWidget(self.dialog_buttons)
        
        layout.addLayout(button_layout)
    
    def _populate_error_info(self):
        """Populate the dialog with error and system information"""
        # Format error details
        exc_type, exc_value, exc_traceback = self.exception_info
        
        error_report = []
        error_report.append("=" * 60)
        error_report.append("VICTURUS ERROR REPORT")
        error_report.append("=" * 60)
        error_report.append(f"Timestamp: {datetime.datetime.now().isoformat()}")
        error_report.append(f"Context: {self.context}")
        error_report.append("")
        
        # Exception information
        error_report.append("EXCEPTION:")
        error_report.append("-" * 40)
        error_report.append(f"Type: {exc_type.__name__}")
        error_report.append(f"Message: {str(exc_value)}")
        error_report.append("")
        
        # Full traceback
        error_report.append("TRACEBACK:")
        error_report.append("-" * 40)
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for line in tb_lines:
            error_report.append(line.rstrip())
        
        self.error_text.setPlainText("\n".join(error_report))
        
        # System information
        system_info = []
        system_info.append(f"Python Version: {sys.version}")
        system_info.append(f"Platform: {platform.platform()}")
        system_info.append(f"System: {platform.system()} {platform.release()}")
        system_info.append(f"Architecture: {platform.architecture()[0]}")
        system_info.append(f"Machine: {platform.machine()}")
        system_info.append(f"Processor: {platform.processor()}")
        
        # Add Qt/PySide version info
        try:
            from PySide6 import __version__ as pyside_version
            system_info.append(f"PySide6 Version: {pyside_version}")
        except ImportError:
            pass
        
        # Add application info
        try:
            import main
            system_info.append(f"Application: Victurus")
        except ImportError:
            pass
        
        self.system_text.setPlainText("\n".join(system_info))
        
        # Store full report for copying
        self.full_report = "\n".join(error_report + ["", "SYSTEM INFORMATION:", "-" * 40] + system_info)
    
    def _copy_all(self):
        """Copy all error and system information to clipboard"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.full_report)
            
            # Show confirmation
            self.copy_all_btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_all_btn.setText("Copy All to Clipboard"))
        except Exception:
            # Fallback if clipboard access fails
            self.copy_all_btn.setText("Copy Failed")
            QTimer.singleShot(2000, lambda: self.copy_all_btn.setText("Copy All to Clipboard"))
    
    def _copy_error_only(self):
        """Copy only the error details to clipboard"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.error_text.toPlainText())
            
            # Show confirmation
            self.copy_error_btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_error_btn.setText("Copy Error Only"))
        except Exception:
            # Fallback if clipboard access fails
            self.copy_error_btn.setText("Copy Failed")
            QTimer.singleShot(2000, lambda: self.copy_error_btn.setText("Copy Error Only"))


def show_error_dialog(exception_info: tuple, context: str = "", parent=None):
    """
    Convenience function to show an error dialog.
    
    Args:
        exception_info: Tuple from sys.exc_info()
        context: Additional context about when/where the error occurred
        parent: Parent widget (optional)
    """
    try:
        dialog = ErrorReporterDialog(exception_info, context, parent)
        dialog.show()  # Non-blocking show
        return dialog
    except Exception as e:
        # Fallback if the error dialog itself fails - use logger as backup
        logger.error(f"Error showing error dialog: {e}", exc_info=True)
        logger.error(f"Original error: {exception_info[1]}")
        return None
