# engine/window_togglers.py
from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional, Mapping

from .app_context import AppContext
from .event_bus import EventBus
from . import world

# UI windows
from .ui.map_window import MapWindow
from .ui.hangar_window import HangarWindow
from .ui.market_window import MarketWindow
from .ui.status_window import StatusWindow
from .ui.cargo_window import CargoWindow
from .ui.player_window import PlayerWindow
from .ui.quests_window import QuestsWindow

# NOTE: Do not import controllers at module scope; import lazily inside functions if needed.


def _as_toplevel(obj: Any) -> Optional[tk.Toplevel]:
    """Return a Tk Toplevel for objects that *are* a Toplevel or that wrap one."""
    if isinstance(obj, tk.Toplevel):
        return obj
    for attr in ("win", "top", "window", "toplevel"):
        w = getattr(obj, attr, None)
        if isinstance(w, tk.Toplevel):
            return w
    return None


def _has_world(conn: Optional[sqlite3.Connection]) -> bool:
    return conn is not None


class WindowTogglers:
    """Opens/toggles single-instance windows and tracks them in `ctx.windows`.
    Handles Optional[sqlite3.Connection] and wrapper windows robustly.
    """

    def __init__(self, ctx: AppContext, bus: EventBus):
        self.ctx = ctx
        self.bus = bus

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _toggle_top(self, key: str, opener: Callable[[], object]) -> None:
        existing = self.ctx.windows.get(key)
        win = _as_toplevel(existing) if existing is not None else None
        if win is not None and win.winfo_exists():
            try:
                win.deiconify()
                win.lift()
                win.focus_force()
            except Exception:
                pass
            return

        obj = opener()
        self.ctx.windows[key] = obj
        win2 = _as_toplevel(obj)
        if win2 is not None:
            try:
                win2.lift()
                win2.focus_force()
            except Exception:
                pass

    def _current_station_id(self) -> Optional[int]:
        conn = self.ctx.conn
        if conn is None:
            return None
        try:
            p: Mapping[str, Any] = world.get_player(conn)
            if p.get("location_type") == "station":
                v = p.get("location_id")
                if isinstance(v, int):
                    return v
                if isinstance(v, str) and v.isdigit():
                    return int(v)
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # Public togglers
    # ------------------------------------------------------------------
    def toggle_map(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return MapWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("map", None)
            )

        self._toggle_top("map", _open)

    def toggle_hangar(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return HangarWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("hangar", None)
            )

        self._toggle_top("hangar", _open)

    def toggle_market(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return
        station_id = self._current_station_id()
        if station_id is None:
            messagebox.showinfo("Market", "You must be docked at a station to view the market.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return MarketWindow(
                self.ctx.root, conn, self.ctx.bus, station_id, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("market", None)
            )

        self._toggle_top("market", _open)

    def toggle_status(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return StatusWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("status", None)
            )

        self._toggle_top("status", _open)

    def toggle_cargo(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return CargoWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("cargo", None)
            )

        self._toggle_top("cargo", _open)

    def toggle_player(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            return PlayerWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("player", None)
            )

        self._toggle_top("player", _open)

    def toggle_quests(self) -> None:
        if not _has_world(self.ctx.conn):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = self.ctx.conn
            assert conn is not None
            qc = getattr(self.ctx, "qc", None)
            if qc is None:
                from .controllers.quest_controller import QuestController  # local import to avoid cycles
                qc = QuestController(conn, self.ctx.bus)
                try:
                    self.ctx.qc = qc  # type: ignore[attr-defined]
                except Exception:
                    pass
            return QuestsWindow(
                self.ctx.root, conn, self.ctx.bus, qc, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("quests", None)
            )

        self._toggle_top("quests", _open)

    def bring_all_to_front(self) -> None:
        # View → Bring All to Front
        for obj in list(self.ctx.windows.values()):
            win = _as_toplevel(obj)
            if win is None:
                continue
            try:
                if win.winfo_exists():
                    win.lift()
                    win.focus_force()
            except Exception:
                pass
