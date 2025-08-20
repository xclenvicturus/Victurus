from __future__ import annotations

import sqlite3
from typing import Optional, cast

from .app_context import AppContext


class AppEvents:
    def __init__(self, ctx: AppContext, actions_panel, togglers) -> None:
        self.ctx = ctx
        self.actions = actions_panel
        self.togglers = togglers
        self._wire_bus()

    def _wire_bus(self) -> None:
        b = self.ctx.bus
        b.on("log", lambda category, message: self._on_log(category, message))
        b.on("status_changed", self._on_status_changed)
        b.on("travel_progress", self._on_travel_progress)
        b.on("open_combat", self._on_open_combat)
        b.on("combat_over", self._on_combat_over)
        b.on("arrived", self._on_arrived)
        b.on("departed", self._on_departed)

    # --- handlers ---

    def _on_log(self, category: str, message: str) -> None:
        if self.ctx.log_panel:
            self.ctx.log_panel.append(category, message)

    def _on_status_changed(self, *_a, **_k) -> None:
        if self.ctx.in_combat:
            self.actions.set_combat_ui(True, None)
        else:
            self.actions.refresh()

    def _on_travel_progress(self, *_a) -> None:
        if self.ctx.in_combat:
            self.actions.set_combat_ui(True, None)
        else:
            self.actions.refresh()

    def _on_open_combat(self, initial_state: dict) -> None:
        self.ctx.in_combat = True
        self.actions.set_combat_ui(True, initial_state)
        if self.ctx.log_panel:
            self.ctx.log_panel.focus_tab("combat")

    def _on_combat_over(self, *_a, **_k) -> None:
        self.ctx.in_combat = False
        self.actions.set_combat_ui(False, None)

    def _on_arrived(self, station_id: int) -> None:
        self.actions.refresh()
        self.actions.maybe_autos(station_id)

    def _on_departed(self, *_a) -> None:
        self.togglers.close_station_scoped_windows()
