# /test_actions_widget.py

"""
Test script to verify the Actions Widget is working correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from ui.widgets.actions_panel import ActionsPanel


def test_actions_widget():
    """Test that the actions panel creates and updates correctly"""
    print("Testing Actions Panel Widget...")
    
    app = QApplication(sys.argv)
    
    # Create a test window
    window = QWidget()
    window.setWindowTitle("Actions Panel Test")
    window.resize(300, 500)
    
    layout = QVBoxLayout(window)
    
    # Create the actions panel
    actions_panel = ActionsPanel(window)
    layout.addWidget(actions_panel)
    
    # Test the refresh and context updates
    print(f"Available actions: {actions_panel.get_available_actions()}")
    print(f"Current context: {actions_panel._current_context}")
    
    # Connect the signal to test button presses
    def on_action_triggered(action_name, action_data):
        print(f"✅ ACTION TRIGGERED: {action_name}")
        print(f"   Data: {action_data}")
        print()
    
    actions_panel.action_triggered.connect(on_action_triggered)
    
    window.show()
    
    print("Actions Panel Test Window created successfully!")
    print("Try clicking the buttons to test the functionality.")
    print("Close the window when finished testing.")
    
    return app.exec()


if __name__ == "__main__":
    test_actions_widget()
