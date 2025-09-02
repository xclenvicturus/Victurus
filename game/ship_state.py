# /game/ship_state.py
"""
Ship State Management

This module holds a temporary, visual-only state for the ship status panel.
The UI reads this to override the stable DB-derived status during short phases
like "Docking", "Entering Cruise", "Warping", etc.
"""

from __future__ import annotations
from typing import Optional, Iterator
from contextlib import contextmanager
import threading

# This module holds a temporary, visual-only state for the ship status panel.
# The UI reads this to override the stable DB-derived status during short phases
# like "Docking", "Entering Cruise", "Warping", etc.

__all__ = [
    "set_temporary_state",
    "get_temporary_state",
    "clear_temporary_state",
    "temporary_state",
]

# Guard access in case game logic and UI poll from different threads.
_LOCK = threading.RLock()
_temporary_state: Optional[str] = None


def set_temporary_state(state: Optional[str]) -> None:
    """
    Set a temporary ship state that overrides the actual/stable state.

    Examples:
      set_temporary_state("Docking")
      set_temporary_state("Warping")
      set_temporary_state(None)  # clear
    """
    global _temporary_state
    with _LOCK:
        _temporary_state = (state.strip() if isinstance(state, str) else None)


def get_temporary_state() -> Optional[str]:
    """Return the current temporary ship state, or None if not set."""
    with _LOCK:
        return _temporary_state


def clear_temporary_state() -> None:
    """Clear any temporary ship state override."""
    set_temporary_state(None)


@contextmanager
def temporary_state(state: Optional[str]) -> Iterator[None]:
    """
    Context manager to set a temporary state for the duration of a block, then restore.

    Example:
        with temporary_state("Docking"):
            # perform docking sequence...
            ...
    """
    with _LOCK:
        prev = _temporary_state
        set_temporary_state(state)
    try:
        yield
    finally:
        with _LOCK:
            # Restore previous value (may be None)
            set_temporary_state(prev)
