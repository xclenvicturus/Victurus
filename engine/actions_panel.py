# engine/actions_panel.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .app_context import AppContext
from .event_bus import EventBus
from .window_togglers import WindowTogglers


def add_btn(parent: tk.Misc, text: str, cmd: Callable[[], None]) -> ttk.Button:
    """Small helper retained for compatibility with existing imports."""
    btn = ttk.Button(parent, text=text, command=cmd)
    btn.pack(side=tk.TOP, fill=tk.X, padx=6, pady=3)
    return btn


class ActionsPanel(ttk.Frame):
    """
    Lightweight action launcher. We intentionally *do not* instantiate windows
    here. Instead, we delegate to WindowTogglers so constructor signatures stay
    consistent and type-safe (avoids 'missing parameter "bus"' issues).
    """

    def __init__(
        self,
        root: tk.Tk,
        ctx: AppContext,
        togglers: WindowTogglers,
        bus: Optional[EventBus] = None,  # made optional to satisfy existing call sites
    ) -> None:
        super().__init__(root)
        self.ctx = ctx
        self.togglers = togglers
        # Prefer explicitly-passed bus; fall back to context if available.
        self.bus: EventBus = bus if bus is not None else ctx.bus  # type: ignore[attr-defined]

        # Layout
        self.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(self, text="Actions", anchor="w").pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 3))

        # Window toggles
        add_btn(self, "Map", self.togglers.toggle_map)
        add_btn(self, "Status", self.togglers.toggle_status)
        add_btn(self, "Player", self.togglers.toggle_player)
        add_btn(self, "Cargo", self.togglers.toggle_cargo)
        add_btn(self, "Hangar", self.togglers.toggle_hangar)
        add_btn(self, "Market", self.togglers.toggle_market)
        add_btn(self, "Quests", self.togglers.toggle_quests)

        # Utility
        add_btn(self, "Bring All to Front", self.togglers.bring_all_to_front)
