from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, cast

from ..app_context import AppContext


class ActionsPanel:
    """Minimal, reliable actions sidebar that delegates to WindowTogglers."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        # Create a left-side panel if not already present on context
        if getattr(ctx, "actions_panel", None) is None:
            created = ttk.Frame(ctx.root)
            created.pack(side=tk.LEFT, fill=tk.Y)
            self.panel: tk.Misc = cast(tk.Misc, created)
            try:
                ctx.actions_panel = created  # type: ignore[attr-defined]
            except Exception:
                pass
        else:
            self.panel = cast(tk.Misc, ctx.actions_panel)  # type: ignore[assignment]

        ttk.Label(self.panel, text="Actions", anchor="w").pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 4))

        # after/after_cancel identifiers are strings per Tk/Typeshed
        self._tick_job: Optional[str] = None

    def _btn(self, text: str, cmd: Callable[[], None]) -> None:
        ttk.Button(self.panel, text=text, command=cmd).pack(side=tk.TOP, fill=tk.X, padx=6, pady=3)

    def refresh(self) -> None:
        # Clear only buttons; keep the header label
        for w in list(self.panel.winfo_children()):
            if isinstance(w, ttk.Button):
                w.destroy()

        # Wire up buttons via WindowTogglers (import locally to avoid cycles)
        from .window_manager import WindowTogglers

        wt = WindowTogglers(self.ctx)
        self._btn("Map", wt.toggle_map)
        self._btn("Status", wt.toggle_status)
        self._btn("Player", wt.toggle_player)
        self._btn("Cargo", wt.toggle_cargo)
        self._btn("Hangar", wt.toggle_hangar)
        self._btn("Market", wt.toggle_market)
        self._btn("Quests", wt.toggle_quests)
        self._btn("Bring All to Front", wt.bring_all_to_front)

    def schedule_tick(self, ms: int = 1000) -> None:
        """Optional periodic UI tick hook (can be used for autos, logs, etc.)."""
        if self._tick_job is not None:
            try:
                self.panel.after_cancel(self._tick_job)
            except Exception:
                pass
            finally:
                self._tick_job = None

        def _tick() -> None:
            # Placeholder: if you later add periodic updates, put them here.
            self._tick_job = self.panel.after(ms, _tick)

        self._tick_job = self.panel.after(ms, _tick)
