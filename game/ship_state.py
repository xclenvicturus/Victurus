# /game/ship_state.py

from __future__ import annotations
from typing import Optional

# This module holds a temporary, visual-only state for the ship status panel.
_temporary_state: Optional[str] = None

def set_temporary_state(state: Optional[str]) -> None:
    """Sets a temporary ship state that overrides the actual state for a short duration."""
    global _temporary_state
    _temporary_state = state

def get_temporary_state() -> Optional[str]:
    """Gets the current temporary ship state."""
    return _temporary_state
