from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import tkinter as tk
from tkinter import ttk

from .event_bus import EventBus
from .settings import Settings, WindowStateManager

# Forward declarations for type hints (avoid import cycles by using Any)
# travel/quest/combat controllers and ui widgets are kept as Any


@dataclass
class AppContext:
    # Core
    root: tk.Tk
    settings: Settings
    wsm: WindowStateManager
    bus: EventBus
    save_root: Path

    # DB / world
    conn: Optional[sqlite3.Connection] = None
    current_save: Optional[str] = None

    # Game controllers (set after a save is opened)
    travel: Any = None
    qc: Any = None
    combat: Any = None

    # UI shared widgets
    station_title: Optional[ttk.Label] = None
    npc_list: Optional[tk.Listbox] = None
    actions_panel: Optional[ttk.Frame] = None
    log_panel: Any = None  # LogPanel

    # Misc
    ask_yes_no: Callable[[str, str], bool] = lambda _t, _q: False
    in_combat: bool = False

    # Shared single-instance windows registry
    windows: dict[str, Any] = field(default_factory=dict)
