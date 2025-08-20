# engine/window_togglers.py
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from .ui.map_window import MapWindow
from .ui.hangar_window import HangarWindow
from .ui.market_window import MarketWindow
from .ui.quests_window import QuestsWindow
from .ui.status_window import StatusWindow
from .ui.cargo_window import CargoWindow
from .ui.player_window import PlayerWindow

from . import world  # for current location/station id


class WindowTogglers:
    """
    Centralized helpers to open/toggle singletons of each window.
    Ensures only one instance of a given window is open at a time.
    ctx must provide: root, conn, bus, travel, qc, wsm, windows (dict[str, tk.Toplevel])
    """

    def __init__(self, ctx):
        self.ctx = ctx

    # -- internals -------------------------------------------------------------

    def _normalize_top(self, obj) -> tk.Toplevel:
        """
        Some UI classes subclass Toplevel; others wrap and expose .win.
        Always return the concrete tk.Toplevel so we store a consistent handle.
        """
        if isinstance(obj, tk.Toplevel):
            return obj
        win = getattr(obj, "win", None)
        if isinstance(win, tk.Toplevel):
            return win
        # last resort (won't happen in our code, but stay safe)
        raise TypeError("Window object did not provide a tk.Toplevel or .win")

    def _open_or_toggle(self, win_id: str, opener: Callable[[], tk.Toplevel]) -> None:
        existing = self.ctx.windows.get(win_id)
        if existing is not None and existing.winfo_exists():
            # Toggle visibility
            try:
                state = str(existing.state())
                if state == "withdrawn" or state == "iconic":
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                else:
                    existing.withdraw()
            except Exception:
                try:
                    existing.lift()
                    existing.focus_force()
                except Exception:
                    pass
            return

        # Open new
        top = opener()
        self.ctx.windows[win_id] = top

    # -- helpers so Pylance knows return is Toplevel ---------------------------

    def _open_status(self) -> tk.Toplevel:
        obj = StatusWindow(
            self.ctx.root,
            self.ctx.conn,
            self.ctx.bus,
            self.ctx.wsm,
            on_close=lambda: self.ctx.windows.pop("status", None),
        )
        return self._normalize_top(obj)

    def _open_cargo(self) -> tk.Toplevel:
        obj = CargoWindow(
            self.ctx.root,
            self.ctx.conn,
            self.ctx.bus,
            self.ctx.wsm,
            on_close=lambda: self.ctx.windows.pop("cargo", None),
        )
        return self._normalize_top(obj)

    def _open_player(self) -> tk.Toplevel:
        obj = PlayerWindow(
            self.ctx.root,
            self.ctx.conn,
            self.ctx.bus,
            self.ctx.wsm,
            on_close=lambda: self.ctx.windows.pop("player", None),
        )
        return self._normalize_top(obj)

    # -- toggles ---------------------------------------------------------------

    def toggle_map(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Map", "Open or create a game first.")
            return
        travel = self.ctx.travel
        self._open_or_toggle(
            "galaxy_map",
            lambda: MapWindow(
                self.ctx.root,
                self.ctx.conn,
                self.ctx.bus,
                travel,
                self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("galaxy_map", None),
            ),
        )

    def toggle_hangar(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Hangar", "Open or create a game first.")
            return
        self._open_or_toggle(
            "hangar",
            lambda: HangarWindow(
                self.ctx.root,
                self.ctx.conn,
                self.ctx.bus,
                self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("hangar", None),
            ),
        )

    def toggle_market(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Market", "Open or create a game first.")
            return
        p = world.get_player(self.ctx.conn)
        if p["location_type"] != "station":
            messagebox.showinfo("Market", "You must be docked at a station to open the market.")
            return
        station_id = int(p["location_id"])
        self._open_or_toggle(
            "market",
            lambda: MarketWindow(
                self.ctx.root,
                self.ctx.conn,
                self.ctx.bus,
                self.ctx.wsm,
                station_id,  # <- required by MarketWindow
                on_close=lambda: self.ctx.windows.pop("market", None),
            ),
        )

    def toggle_quests(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Quests", "Open or create a game first.")
            return
        qc = self.ctx.qc  # QuestController
        # QuestsWindow signature: (root, conn, bus, wsm, qc, on_close)
        # See ui/quests_window.py for details. :contentReference[oaicite:2]{index=2}
        self._open_or_toggle(
            "quests",
            lambda: QuestsWindow(
                self.ctx.root,
                self.ctx.conn,
                self.ctx.bus,
                self.ctx.wsm,
                qc,
                on_close=lambda: self.ctx.windows.pop("quests", None),
            ),
        )

    def toggle_status(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Status", "Open or create a game first.")
            return
        self._open_or_toggle("status", self._open_status)

    def toggle_cargo(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Cargo", "Open or create a game first.")
            return
        self._open_or_toggle("cargo", self._open_cargo)

    def toggle_player(self) -> None:
        if not self.ctx.conn:
            messagebox.showinfo("Commander", "Open or create a game first.")
            return
        self._open_or_toggle("player", self._open_player)

    # -- utilities used elsewhere ---------------------------------------------

    def close_station_scoped_windows(self) -> None:
        """
        Close windows that should not stay open while traveling.
        """
        for wid in ("market", "hangar"):
            w = self.ctx.windows.pop(wid, None)
            if w:
                try:
                    w.destroy()
                except Exception:
                    pass

    def bring_all_to_front(self) -> None:
        """
        Lift all open windows to the top.
        """
        for w in list(self.ctx.windows.values()):
            try:
                w.deiconify()
                w.lift()
            except Exception:
                pass
