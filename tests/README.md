# Tests Directory

This directory contains all test files and test utilities for the Victurus project.

## Test File Naming Convention

All test files MUST follow these naming conventions for easy identification and organization:

### Unit Tests
- **Format:** `test_<component_name>.py`
- **Purpose:** Test specific components, modules, or classes
- **Examples:** 
  - `test_error_handler.py` - Tests error handling system
  - `test_save_manager.py` - Tests save/load functionality
  - `test_travel_system.py` - Tests travel mechanics
  - `test_ui_widgets.py` - Tests UI widget functionality

### Integration Tests
- **Format:** `integration_test_<system_name>.py`
- **Purpose:** Test interactions between multiple components
- **Examples:**
  - `integration_test_travel_flow.py` - Tests complete travel workflow
  - `integration_test_save_load_cycle.py` - Tests full save/load cycle
  - `integration_test_ui_coordination.py` - Tests UI component interactions

### Performance Tests
- **Format:** `performance_test_<feature_name>.py`
- **Purpose:** Test performance characteristics of systems
- **Examples:**
  - `performance_test_map_rendering.py` - Tests map rendering performance
  - `performance_test_database_queries.py` - Tests database query performance

### Safety/Crash Tests
- **Format:** `safety_test_<system_name>.py`
- **Purpose:** Test error handling, crash resistance, and recovery
- **Examples:**
  - `safety_test_widget_lifecycle.py` - Tests Qt widget cleanup
  - `safety_test_database_corruption.py` - Tests database error recovery

### Debug Utilities (Development Only)
- **Format:** `debug_<issue_description>.py`
- **Purpose:** Temporary debugging scripts for specific issues
- **Examples:**
  - `debug_crash_reproduction.py` - Reproduces specific crashes
  - `debug_memory_leak.py` - Debug memory usage issues
- **Note:** Debug files should be moved to `archive/debug_scripts/` when no longer needed

## File Organization Rules

### ✅ REQUIRED Location
- **ALL test files** MUST be created in the `tests/` directory
- **NO test files** should be created in the project root
- **NO temporary test files** should remain in the project root after development

### ✅ File Structure
```
tests/
├── README.md                           # This file
├── test_<component>.py                 # Unit tests
├── integration_test_<system>.py        # Integration tests  
├── performance_test_<feature>.py       # Performance tests
├── safety_test_<system>.py             # Safety/crash tests
└── debug_<issue>.py                    # Temporary debug utilities
```

### ❌ FORBIDDEN Locations
- Root directory test files (move to `tests/`)
- Test files mixed with production code
- Temporary test files left in project root

## Current Test Files

### Active Tests
- **`test_error_handler.py`** - Global error handling system tests
- **`test_load_multiple_saves.py`** - Save/load dialog functionality tests  
- **`travel_visualization_test.py`** - Travel visualization component tests
- **`travel_visualization_safety_test.py`** - Travel system crash resistance tests

## Running Tests

### Individual Tests
Run test files directly from the project root:
```bash
# Unit tests
python tests/test_error_handler.py
python tests/test_load_multiple_saves.py

# System tests  
python tests/travel_visualization_test.py
python tests/travel_visualization_safety_test.py
```

### All Tests
```bash
# Run all tests in the directory
python -m pytest tests/

# Or manually run each test file
for file in tests/test_*.py; do python "$file"; done
```

## Adding New Tests

### 1. Choose Correct Naming Convention
- Use appropriate prefix based on test type
- Use descriptive component/system names
- Follow snake_case naming

### 2. Required File Header
All test files MUST start with:
```python
# /tests/test_<component_name>.py

"""
Brief description of what this test file covers.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
```

### 3. Follow Test Structure
```python
def test_specific_functionality():
    """Test a specific piece of functionality"""
    # Arrange - Set up test conditions
    # Act - Execute the code being tested  
    # Assert - Verify expected results
    pass

if __name__ == "__main__":
    # Run tests when file is executed directly
    test_specific_functionality()
    print("✅ All tests passed")
```

### 4. Use Proper Imports
```python
# Use centralized logging in tests
from game_controller.log_config import get_system_logger
logger = get_system_logger('test_component_name')

# Import production code from project root
from ui.widgets.example_widget import ExampleWidget
from game.travel_flow import TravelFlow
```

## Test Guidelines

### ✅ Best Practices
- **Descriptive names** - Test names should clearly indicate what is being tested
- **Isolated tests** - Each test should be independent and not rely on others
- **Clean up** - Tests should clean up any resources they create
- **Error handling** - Tests should handle and report errors clearly
- **Documentation** - Include docstrings explaining test purpose

### ❌ Avoid
- **Temporary test files** in project root
- **Print statements** (use logger instead)  
- **Hardcoded paths** (use Path objects)
- **Tests that modify production data** without cleanup
- **Tests that require manual intervention**

## Cleanup Policy

- **Development test files** that are no longer needed should be moved to `archive/obsolete_tests/`
- **Debug utilities** should be moved to `archive/debug_scripts/` when issues are resolved
- **Temporary files** should never be committed to the repository
- **Test data files** should be cleaned up after test completion

This naming convention ensures all tests are easily identifiable, properly organized, and maintainable.
