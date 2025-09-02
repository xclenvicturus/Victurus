# Error Handling System Documentation

The Victurus application includes a comprehensive error catching and reporting system that helps capture crashes, exceptions, and silent errors for debugging and user reporting.

## Overview

The error handling system consists of several components:

1. **Global Exception Handler** (`ui/error_handler.py`) - Catches uncaught exceptions
2. **Error Reporter Dialog** (`ui/dialogs/error_reporter_dialog.py`) - User-friendly error display
3. **Error Utilities** (`ui/error_utils.py`) - Decorators and helpers for error handling
4. **Debug Menu** (in View menu) - Tools for accessing logs and testing error handling

## Features

### 🚨 Automatic Error Catching
- **Uncaught Exceptions**: Automatically catches Python exceptions that would crash the app
- **Qt Messages**: Captures Qt framework debug/warning/error messages
- **Silent Errors**: Catches errors in background operations that might otherwise be missed
- **Context Tracking**: Records what the application was doing when errors occurred

### 🖥️ User-Friendly Error Reporting
- **Error Dialog**: Shows detailed error information in a readable format
- **Copy to Clipboard**: Easy copying of error details for bug reports
- **System Information**: Includes relevant system details for debugging
- **Non-Blocking**: Errors don't freeze the application - users can continue working

### 🛠️ Developer Tools
- **Debug Menu**: Access error logs, test error handling, view system info
- **Decorators**: Easy error handling for functions with `@catch_and_log`
- **Context Managers**: Error handling for code blocks with `ErrorContext`
- **Logging Integration**: All errors are logged to files for later analysis

## Usage

### For Users

When an error occurs:
1. An **Error Report** dialog will appear showing the error details
2. Click **"Copy All to Clipboard"** to copy the full error report
3. Click **"Copy Error Only"** to copy just the error details
4. Report the error to developers with the copied information
5. Click **"Close"** to dismiss the dialog - the application will continue running

To access error logs:
1. Go to **View → Debug → Open Log Folder**
2. This opens the `logs/` directory containing error log files

To test error handling:
1. Go to **View → Debug → Test Error Handler**
2. This triggers a test error to verify the system is working

### For Developers

#### Basic Error Handling

```python
from ui.error_utils import catch_and_log, ErrorContext, handle_error

# Use decorator for automatic error handling
@catch_and_log("Loading save game")
def load_save(filename):
    # code that might fail
    with open(filename, 'r') as f:
        return json.load(f)

# Use context manager for code blocks
def process_data():
    with ErrorContext("Processing user data"):
        # code that might fail
        process_complex_operation()

# Manual error handling
try:
    risky_operation()
except Exception as e:
    handle_error(e, "Performing risky operation")
```

#### Error Handler Configuration

The error handler is automatically installed in `main.py` and configured with:
- QApplication instance for Qt integration
- ErrorReporterDialog class for user-friendly error display  
- MainWindow reference for proper dialog parenting

#### Available Decorators

```python
# Catch and show error dialog
@catch_and_log(context="Function description", reraise=False)

# Catch and log silently (no dialog)
@catch_and_log_silent(context="Background operation")

# Treat as warnings instead of errors
@warn_on_exception(context="Non-critical operation")
```

#### Context Manager Usage

```python
# Basic usage
with ErrorContext("Loading configuration"):
    load_config_file()

# Don't show dialog, just log
with ErrorContext("Background sync", show_dialog=False):
    sync_data()

# Re-raise after logging
with ErrorContext("Critical operation", reraise=True):
    critical_system_call()
```

## Error Information Included

When an error is reported, the following information is captured:

### Error Details
- **Exception Type**: The specific type of error (ValueError, RuntimeError, etc.)
- **Error Message**: The descriptive error message
- **Stack Trace**: Full traceback showing where the error occurred
- **Context**: Description of what the application was doing
- **Timestamp**: When the error occurred

### System Information
- **Python Version**: Version of Python interpreter
- **Platform**: Operating system and version details
- **Architecture**: System architecture (x64, x86, etc.)
- **PySide6 Version**: Qt framework version
- **Application Info**: Victurus-specific information

## Configuration

### Logging
Error logs are written to:
- **Location**: `logs/ui_state_debug.log` (and other log files)
- **Level**: INFO and above for general logs, all errors are logged
- **Format**: Timestamp, level, logger name, message

### Error Dialog Limits
- **Maximum Dialogs**: Limited to 3 error dialogs to prevent spam
- **Dialog Behavior**: Non-modal, doesn't block application
- **Auto-cleanup**: Dialogs automatically clean up when closed

### Qt Integration
- **Qt Messages**: Qt framework messages are captured and logged
- **Thread Safety**: Error handling works safely across Qt threads
- **Event Loop**: Uses Qt timers for thread-safe dialog display

## Files in the Error Handling System

### Core Components
- `ui/error_handler.py` - Main error handler class and global exception handling
- `ui/dialogs/error_reporter_dialog.py` - User-friendly error dialog
- `ui/error_utils.py` - Decorators, context managers, and utility functions

### Integration Points  
- `main.py` - Error handler installation and configuration
- `ui/menus/view_menu.py` - Debug menu with error handling tools
- Various modules - Error handling decorators and utilities used throughout

### Log Files
- `logs/ui_state_debug.log` - Main application log including errors
- `logs/` directory - Various other log files created by different components

## Benefits

### For Users
- **Stability**: Application doesn't crash from unexpected errors
- **Transparency**: Clear information about what went wrong
- **Reporting**: Easy copying of error details for bug reports
- **Continuity**: Can continue using the application after errors

### For Developers
- **Debugging**: Detailed error information with context
- **Monitoring**: Comprehensive logging of all application errors  
- **Testing**: Built-in tools for testing error scenarios
- **Maintenance**: Consistent error handling patterns across the codebase

## Best Practices

### When to Use Each Tool

1. **@catch_and_log**: User-facing operations that might fail
2. **@catch_and_log_silent**: Background/automatic operations  
3. **@warn_on_exception**: Optional/non-critical operations
4. **ErrorContext**: Complex operations spanning multiple function calls
5. **handle_error()**: Manual error handling in try/catch blocks

### Error Context Guidelines

- **Be Descriptive**: "Loading save game 'MyGame'" vs "Loading file"
- **Be Specific**: "Parsing JSON configuration" vs "Reading data"
- **Include Relevant Info**: "Connecting to server on port 8080" vs "Network operation"

### When NOT to Use

- **Expected Conditions**: Don't use for normal validation (empty strings, missing optional data)
- **Performance Critical**: Avoid decorators in tight loops or frequent operations
- **Recovery Logic**: When you have specific recovery logic, handle errors manually

The error handling system provides a robust foundation for maintaining application stability while giving both users and developers the information they need when things go wrong.
