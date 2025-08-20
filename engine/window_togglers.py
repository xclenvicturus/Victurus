# engine/window_togglers.py
from __future__ import annotations
import sqlite3
import tkinter as tk
from typing import Callable, Dict, Optional

from .app_context import AppContext
from .event_bus import EventBus
# UI windows
from .ui.map_window import MapWindow
from .ui.hangar_window import HangarWindow
from .ui.market_window import MarketWindow
from .ui.status_window import StatusWindow
from .ui.cargo_window import CargoWindow
from .ui.player_window import PlayerWindow
from .ui.quests_window import QuestsWindow

# controllers
from .controllers.quest_controller import QuestController
from .route_controller import TravelController


def _has_world(conn: Optional[sqlite3.Connection]) -> bool:
    return conn is not None


class WindowTogglers:
    """
    Centralized open/toggle logic. Ensures only one instance of each window id.
    Stores/retrieves the *actual* tk.Toplevel in ctx.windows[win_id].
    """
    def __init__(self, ctx: AppContext):
        self.ctx = ctx  # has .root, .conn, .bus, .wsm, .windows, .travel, .qc

    # ---- helpers -------------------------------------------------------------

    def _toggle_top(self, win_id: str, opener: Callable[[], tk.Toplevel]) -> None:
        """
        Toggle a specific window. If open => close. If closed => open and register in ctx.
        Always guarantees ctx.windows[win_id] is accurate.
        """
        existing: Optional[tk.Toplevel] = self.ctx.windows.get(win_id)
        if existing and isinstance(existing, tk.Toplevel) and existing.winfo_exists():
            try:
                existing.destroy()
            finally:
                self.ctx.windows.pop(win_id, None)
            return

        top = opener()
        # safety: ensure we remove from registry when user closes via [X]
        def on_close(wid=win_id, t=top):
            try:
                t.destroy()
            finally:
                self.ctx.windows.pop(wid, None)

        top.protocol("WM_DELETE_WINDOW", on_close)
        self.ctx.windows[win_id] = top

    def _current_station_id(self) -> Optional[int]:
        conn = self.ctx.conn
        if not _has_world(conn):
            return None
        try:
            row = conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
            return int(row["location_id"]) if row and row["location_id"] is not None else None
        except Exception:
            return None

    # ---- public toggles ------------------------------------------------------

    def toggle_map(self) -> None:
        if not _has_world(self.ctx.conn):
            return
        if self.ctx.travel is None:
            # Build a travel controller on-demand
            self.ctx.travel = TravelController(self.ctx.root, self.ctx.conn, self.ctx.bus, ask_yes_no=self.ctx.ask_yes_no)

        def _open() -> tk.Toplevel:
            return MapWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.travel, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("galaxy_map", None)
            )

        self._toggle_top("galaxy_map", _open)

    def toggle_hangar(self) -> None:
        if not _has_world(self.ctx.conn):
            return

        def _open() -> tk.Toplevel:
            return HangarWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("hangar", None)
            )

        self._toggle_top("hangar", _open)

    def toggle_market(self) -> None:
        if not _has_world(self.ctx.conn):
            return
        station_id = self._current_station_id()
        if station_id is None:
            return

        def _open() -> tk.Toplevel:
            return MarketWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, station_id, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("market", None)
            )

        self._toggle_top("market", _open)

    def toggle_status(self) -> None:
        if not _has_world(self.ctx.conn):
            return

        def _open() -> tk.Toplevel:
            return StatusWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("status", None)
            )

        self._toggle_top("status", _open)

    def toggle_cargo(self) -> None:
        if not _has_world(self.ctx.conn):
            return

        def _open() -> tk.Toplevel:
            return CargoWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("cargo", None)
            )

        self._toggle_top("cargo", _open)

    def toggle_player(self) -> None:
        if not _has_world(self.ctx.conn):
            return

        def _open() -> tk.Toplevel:
            return PlayerWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("player", None)
            )

        self._toggle_top("player", _open)

    def toggle_quests(self) -> None:
        if not _has_world(self.ctx.conn):
            return
        # ensure quest controller exists
        if self.ctx.qc is None:
            self.ctx.qc = QuestController(self.ctx.conn, self.ctx.bus)

        def _open() -> tk.Toplevel:
            return QuestsWindow(
                self.ctx.root, self.ctx.conn, self.ctx.bus, self.ctx.qc, self.ctx.wsm,
                on_close=lambda: self.ctx.windows.pop("quests", None)
            )

        self._toggle_top("quests", _open)

    def bring_all_to_front(self) -> None:
        # “View → Bring All to Front”
        for t in list(self.ctx.windows.values()):
            try:
                if isinstance(t, tk.Toplevel) and t.winfo_exists():
                    t.lift()
                    t.focus_force()
            except Exception:
                pass
