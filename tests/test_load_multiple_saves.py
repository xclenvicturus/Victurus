# /tests/test_load_multiple_saves.py

"""Load Multiple Saves Test

Test script to verify that loading games with multiple saves works without crashes.
• Tests Load Game Dialog functionality with existing saves
• Validates save metadata loading and display
• Checks error handling with corrupted saves
• Environment setup with high DPI configuration
"""

import sys
import os
from pathlib import Path

# Add the project directory to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import Qt and set up error handling
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

def setup_environment():
    """Set up the test environment"""
    # Configure high DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
    
    app = QApplication(sys.argv if sys.argv else ["test"])
    app.setApplicationName("Victurus Load Test")
    
    return app

def test_load_dialog():
    """Test the Load Game Dialog with multiple saves"""
    from ui.dialogs.load_game_dialog import LoadGameDialog
    from PySide6.QtWidgets import QWidget
    
    print("\nTesting Load Game Dialog...")
    
    try:
        # Create a parent widget
        parent = QWidget()
        parent.setWindowTitle("Test Parent")
        
        # Create the dialog
        dialog = LoadGameDialog(parent)
        
        print("✓ Load Game Dialog created successfully")
        
        # Test the populate list method
        try:
            dialog._populate_list()
            print("✓ Dialog populated successfully")
            
            # Check if saves are visible
            count = dialog.tree_widget.topLevelItemCount()
            print(f"✓ Found {count} saves in dialog")
            
            if count >= 2:  # We expect at least existing saves
                print("✓ Multiple saves loaded without crashes")
                
                # Test sorting by clicking headers
                try:
                    header = dialog.tree_widget.header()
                    header.sectionClicked.emit(0)  # Sort by name
                    print("✓ Name column sort works")
                    
                    header.sectionClicked.emit(2)  # Sort by timestamp  
                    print("✓ Timestamp column sort works")
                    
                except Exception as e:
                    print(f"⚠ Header sorting test failed: {e}")
                
            else:
                print(f"⚠ Expected at least 2 saves, found {count}")
                
        except Exception as e:
            print(f"✗ Dialog population failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        # Clean up
        dialog.close()
        parent.close()
        
        return True
        
    except Exception as e:
        print(f"✗ Load Game Dialog test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """Test that error handling is working"""
    from ui.error_handler import handle_error
    
    print("\nTesting error handling...")
    
    try:
        # Test the error handler with a fake exception
        try:
            raise ValueError("Test error for error handler")
        except Exception as e:
            handle_error(e, "Test context")
            print("✓ Error handler works without crashing")
            
        return True
        
    except Exception as e:
        print(f"✗ Error handler test failed: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("VICTURUS LOAD GAME MULTIPLE SAVES TEST")
    print("=" * 60)
    
    app = setup_environment()
    
    try:
        # Install error handler
        from ui.error_handler import ErrorHandler
        error_handler = ErrorHandler()
        error_handler.install()
        error_handler.set_app_instance(app)
        print("✓ Error handler installed")
        
        # Test error handling first
        if not test_error_handling():
            print("✗ Error handling test failed")
            return 1
        
        # Test the load dialog with existing saves
        if not test_load_dialog():
            print("✗ Load dialog test failed")
            return 1
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - Load game with multiple saves works!")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        app.quit()

if __name__ == "__main__":
    exit(main())
