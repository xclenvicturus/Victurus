from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from ..event_bus import EventBus
from ..settings import WindowStateManager
from .. import world

class PlayerWindow:
    """Simple readout for player name, current ship, credits."""
    def __init__(self, root, conn: sqlite3.Connection, bus: EventBus, wsm: WindowStateManager, on_close=None):
        self.root = root
        self.conn = conn
        self.bus = bus

        self.win = tk.Toplevel(self.root)
        self.win.title("Player")
        self.win.geometry("360x200")
        wsm.bind(self.win, "player", on_close=on_close)

        frame = ttk.Frame(self.win); frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.v_name = tk.StringVar()
        self.v_ship = tk.StringVar()
        self.v_credits = tk.StringVar()

        def row(i, label, var):
            ttk.Label(frame, text=label + ":", width=12, anchor="w").grid(row=i, column=0, sticky="w", padx=6, pady=4)
            ttk.Label(frame, textvariable=var, anchor="w").grid(row=i, column=1, sticky="w", padx=6, pady=4)

        row(0, "Name", self.v_name)
        row(1, "Ship", self.v_ship)
        row(2, "Credits", self.v_credits)

        self.refresh()
        bus.on("status_changed", lambda *a, **k: self.refresh())

    def refresh(self):
        p = world.get_player(self.conn)
        ship = world.player_ship(self.conn)
        self.v_name.set(p.get("name", "Pilot"))
        self.v_ship.set(ship["name"])
        self.v_credits.set(str(p["credits"]))
