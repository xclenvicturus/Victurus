from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional, Mapping

from ..app_context import AppContext
from .. import world

# UI windows
from .map_window import MapWindow
from .hangar_window import HangarWindow
from .market_window import MarketWindow
from .status_window import StatusWindow
from .cargo_window import CargoWindow
from .player_window import PlayerWindow
from .quests_window import QuestsWindow


def _as_toplevel(obj: Any) -> Optional[tk.Toplevel]:
    """Return the underlying Toplevel whether the object *is* a Toplevel or wraps one."""
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
    """Open/toggle singleton windows and track them in `ctx.windows`."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _toggle_top(self, key: str, opener: Callable[[], object]) -> None:
        existing = self.ctx.windows.get(key) if hasattr(self.ctx, "windows") else None  # type: ignore[attr-defined]
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
        self.ctx.windows[key] = obj  # type: ignore[attr-defined]
        win2 = _as_toplevel(obj)
        if win2 is not None:
            try:
                win2.lift()
                win2.focus_force()
            except Exception:
                pass

    def _current_station_id(self) -> Optional[int]:
        conn = getattr(self.ctx, "conn", None)
        if conn is None:
            return None
        # Prefer world.get_player (abstracts schema); fallback to raw select
        try:
            p: Mapping[str, Any] = world.get_player(conn)  # type: ignore[assignment]
            if p.get("location_type") == "station":
                v = p.get("location_id")
                if isinstance(v, int):
                    return v
                if isinstance(v, str) and v.isdigit():
                    return int(v)
        except Exception:
            pass
        try:
            row = conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
            if row:
                v2 = row["location_id"]
                if isinstance(v2, int):
                    return v2
                if isinstance(v2, str) and v2.isdigit():
                    return int(v2)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Public togglers
    # ------------------------------------------------------------------
    def toggle_map(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        # Build travel controller lazily to avoid heavy imports at module scope.
        if getattr(self.ctx, "travel", None) is None:
            from ..controllers.travel_controller import TravelController
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            self.ctx.travel = TravelController(self.ctx.root, conn, self.ctx.bus, ask_yes_no=self.ctx.ask_yes_no)  # type: ignore[attr-defined]

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return MapWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.travel, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("galaxy_map", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("galaxy_map", _open)

    def toggle_hangar(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return HangarWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("hangar", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("hangar", _open)

    def toggle_market(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return
        station_id = self._current_station_id()
        if station_id is None:
            messagebox.showinfo("Market", "You must be docked at a station to view the market.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return MarketWindow(
                self.ctx.root, conn, self.ctx.bus, station_id, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("market", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("market", _open)

    def toggle_status(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return StatusWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("status", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("status", _open)

    def toggle_cargo(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return CargoWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("cargo", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("cargo", _open)

    def toggle_player(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            return PlayerWindow(
                self.ctx.root, conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("player", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("player", _open)

    def toggle_quests(self) -> None:
        conn_opt = getattr(self.ctx, "conn", None)
        if not _has_world(conn_opt):
            messagebox.showwarning("No Save Open", "Open or start a game first.")
            return

        def _open() -> object:
            conn = getattr(self.ctx, "conn", None)
            assert isinstance(conn, sqlite3.Connection)
            qc = getattr(self.ctx, "qc", None)
            if qc is None:
                from ..controllers.quest_controller import QuestController
                qc = QuestController(conn, self.ctx.bus)
                try:
                    self.ctx.qc = qc  # type: ignore[attr-defined]
                except Exception:
                    pass
            return QuestsWindow(
                self.ctx.root, conn, self.ctx.bus, qc, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("quests", None)  # type: ignore[attr-defined]
            )

        self._toggle_top("quests", _open)

    def bring_all_to_front(self) -> None:
        for obj in list(self.ctx.windows.values()):  # type: ignore[attr-defined]
            win = _as_toplevel(obj)
            if win is None:
                continue
            try:
                if win.winfo_exists():
                    win.lift()
                    win.focus_force()
            except Exception:
                pass
