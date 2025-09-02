# Victurus Logging System

## Overview
The Victurus game now uses a comprehensive logging system that organizes different types of messages into appropriate log files for better debugging and monitoring.

## Log Files

### 📁 logs/travel_debug.log
- **Purpose**: Travel system, path calculation, and visualization messages
- **Components**: 
  - Travel visualization and path calculation
  - Travel coordinator events
  - System map travel debugging
  - Path rendering and curve calculations
- **Usage**: `get_travel_logger('component_name')`

### 📁 logs/ui_debug.log  
- **Purpose**: UI state, widget interactions, and interface events
- **Components**: 
  - Widget state changes
  - User interface events
  - Window management
  - Menu and dialog interactions
- **Usage**: `get_ui_logger('component_name')`

### 📁 logs/ui_state_debug.log
- **Purpose**: Legacy UI state debugging (maintained for backward compatibility)
- **Components**: 
  - UI state manager events
  - State persistence and restoration
- **Usage**: Automatically used by UI state components

### 📁 logs/game_debug.log
- **Purpose**: Game logic, simulation, and player actions
- **Components**: 
  - Game simulation events
  - Player actions and state changes
  - Universe generation and management
  - Economy and trading systems
- **Usage**: `get_game_logger('component_name')`

### 📁 logs/system_debug.log
- **Purpose**: System-level messages and general debugging
- **Components**: 
  - Database operations
  - Configuration management
  - Application startup/shutdown
  - System diagnostics
- **Usage**: `get_system_logger('component_name')`

### 📁 logs/error.log
- **Purpose**: All error messages across the entire application
- **Components**: Automatically captures all ERROR level messages from any component
- **Features**: 
  - Centralized error tracking
  - Exception details and stack traces
  - Critical system failures

### 📁 logs/warning.log
- **Purpose**: All warning messages across the entire application
- **Components**: Automatically captures all WARNING level messages from any component
- **Features**: 
  - Performance warnings
  - Resource usage alerts
  - Non-critical issues

## Usage Examples

```python
# Travel system logging
from game_controller.log_config import get_travel_logger
logger = get_travel_logger('path_calculation')
logger.info("Calculating curved path around obstacles")
logger.debug("Found 3 obstacles in system")
logger.error("Failed to generate waypoints")

# UI system logging
from game_controller.log_config import get_ui_logger
logger = get_ui_logger('system_map')
logger.info("System map loaded successfully")
logger.warning("Large number of objects may affect performance")

# Game system logging
from game_controller.log_config import get_game_logger
logger = get_game_logger('simulation')
logger.info("Universe simulation started")
logger.debug("Processing 1500 star systems")
```

## Log Features

- **Rotating Files**: Each log file rotates when it reaches 5MB, keeping 3 backup files
- **Structured Format**: Consistent timestamp, log level, component name, and message format
- **UTF-8 Encoding**: Full Unicode support for international characters
- **Automatic Filtering**: Error and warning logs automatically capture messages from all components
- **Performance Optimized**: Minimal overhead during normal operation

## Configuration

The logging system is automatically configured during application startup in `main.py`. No manual configuration is required for normal use.

## Monitoring and Debugging

1. **Travel Issues**: Check `travel_debug.log` for path calculation and visualization problems
2. **UI Issues**: Check `ui_debug.log` for interface and widget problems  
3. **Game Logic Issues**: Check `game_debug.log` for simulation and player action problems
4. **System Issues**: Check `system_debug.log` for database and configuration problems
5. **Critical Issues**: Check `error.log` for all errors across the application
6. **Performance Issues**: Check `warning.log` for performance warnings and resource alerts

## Benefits

- **Organized Debugging**: Different types of issues are separated into appropriate log files
- **Centralized Error Tracking**: All errors are collected in one place regardless of component
- **Historical Data**: Rotating logs preserve historical debugging information
- **Performance Monitoring**: Warning logs help identify performance bottlenecks
- **Development Efficiency**: Developers can focus on specific subsystem logs when debugging
