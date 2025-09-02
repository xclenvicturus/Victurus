# /ui/error_utils.py
"""
Error handling decorators and utilities for Victurus

Provides decorators and utility functions for graceful error handling throughout the application.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable, Any, Optional

from ui.error_handler import handle_error, log_warning


def catch_and_log(context: str = "", reraise: bool = False, default_return: Any = None):
    """
    Decorator that catches exceptions, logs them, and optionally shows error dialogs.
    
    Args:
        context: Description of what the function does (for error reporting)
        reraise: If True, re-raises the exception after logging
        default_return: Value to return if an exception occurs and reraise=False
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_context = context or f"{func.__module__}.{func.__name__}"
                handle_error(e, func_context)
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def catch_and_log_silent(context: str = "", default_return: Any = None):
    """
    Decorator that catches exceptions and logs them without showing error dialogs.
    Useful for background operations that shouldn't interrupt the user.
    
    Args:
        context: Description of what the function does
        default_return: Value to return if an exception occurs
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_context = context or f"{func.__module__}.{func.__name__}"
                logger = logging.getLogger('victurus.errors')
                logger.error(f"Error in {func_context}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator


def warn_on_exception(context: str = "", default_return: Any = None):
    """
    Decorator that catches exceptions and logs them as warnings instead of errors.
    Useful for non-critical operations.
    
    Args:
        context: Description of what the function does
        default_return: Value to return if an exception occurs
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_context = context or f"{func.__module__}.{func.__name__}"
                log_warning(str(e), func_context)
                return default_return
        return wrapper
    return decorator


class ErrorContext:
    """
    Context manager for handling errors in code blocks.
    
    Usage:
        with ErrorContext("Loading save game"):
            # code that might fail
            load_save_file()
    """
    
    def __init__(self, context: str, reraise: bool = False, show_dialog: bool = True):
        self.context = context
        self.reraise = reraise
        self.show_dialog = show_dialog
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            if self.show_dialog:
                handle_error(exc_value, self.context)
            else:
                logger = logging.getLogger('victurus.errors')
                logger.error(f"Error in {self.context}: {exc_value}", exc_info=True)
            
            if not self.reraise:
                # Suppress the exception
                return True
        return False


def safe_call(func: Callable, *args, context: str = "", default_return: Any = None, **kwargs) -> Any:
    """
    Safely call a function with error handling.
    
    Args:
        func: Function to call
        *args: Positional arguments for the function
        context: Description for error reporting
        default_return: Value to return if an error occurs
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or default_return if an error occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        func_context = context or f"{func.__module__}.{func.__name__}"
        handle_error(e, func_context)
        return default_return


# Example usage for common patterns:

def safe_file_operation(operation: Callable, filepath: str, default_return: Any = None) -> Any:
    """Safely perform file operations with proper error context"""
    return safe_call(
        operation,
        context=f"File operation on {filepath}",
        default_return=default_return
    )


def safe_ui_operation(operation: Callable, widget_name: str = "", default_return: Any = None) -> Any:
    """Safely perform UI operations with proper error context"""
    context = f"UI operation on {widget_name}" if widget_name else "UI operation"
    return safe_call(
        operation,
        context=context,
        default_return=default_return
    )
