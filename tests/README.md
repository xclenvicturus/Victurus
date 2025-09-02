# Tests Directory

This directory contains test files and debug utilities for the Victurus project.

## Files

- **debug_crash.py** - Debug script to reproduce crashes when loading games with multiple saves
- **debug_dialog_step_by_step.py** - Step-by-step debug tool for LoadGameDialog creation issues
- **test_error_handler.py** - Test suite for the global error handling system
- **test_load_multiple_saves.py** - Test script to verify Load Game Dialog functionality with existing saves

## Usage

Run test files directly from the project root:
```bash
python tests/test_error_handler.py
python tests/test_load_multiple_saves.py
```

Debug files can be run to reproduce specific issues:
```bash
python tests/debug_crash.py
python tests/debug_dialog_step_by_step.py
```
