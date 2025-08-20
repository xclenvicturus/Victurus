from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from .. import world
from ..settings import WindowStateManager
from ..event_bus import EventBus

BAR_W = 220
BAR_H = 16

class StatusWindow:
    def __init__(self, root, conn: sqlite3.Connection, bus: EventBus, wsm: WindowStateManager, on_close=None):
        self.root = root
        self.conn = conn
        self.bus = bus

        self.win = tk.Toplevel(self.root)
        self.win.title("Ship Status")
        self.win.geometry("440x260")
        wsm.bind(self.win, "status", on_close=on_close)

        frame = ttk.Frame(self.win); frame.pack(fill="both", expand=True, padx=10, pady=10)
        row = 0

        def label(text):
            nonlocal row
            ttk.Label(frame, text=text+":", width=16, anchor="w").grid(row=row, column=0, sticky="w", padx=6, pady=6)

        def make_bar():
            c = tk.Canvas(frame, width=BAR_W, height=BAR_H, highlightthickness=1, highlightbackground="#666", bg="#222")
            c.grid(row=row, column=1, sticky="w")
            return c

        self.lbl_ship = ttk.Label(frame, text="")
        ttk.Label(frame, text="Ship:", width=16, anchor="w").grid(row=row, column=0, sticky="w", padx=6, pady=6)
        self.lbl_ship.grid(row=row, column=1, sticky="w"); row += 1

        label("Hull");      self.bar_hull = make_bar(); row += 1
        label("Shields");   self.bar_sh   = make_bar(); row += 1
        label("Energy");    self.bar_en   = make_bar(); row += 1
        label("Cargo");     self.bar_cg   = make_bar(); row += 1
        label("Fuel");      self.bar_fuel = make_bar(); row += 1

        self.refresh()
        bus.on("status_changed", lambda *a, **k: self.refresh())

    def _draw_bar(self, canvas: tk.Canvas, cur: int, mx: int):
        canvas.delete("all")
        mx = max(1, int(mx))
        cur = max(0, min(int(cur), mx))
        frac = cur / mx
        fill_w = int(BAR_W * frac)
        # background
        canvas.create_rectangle(0, 0, BAR_W, BAR_H, fill="#1a1f29", outline="")
        # fill
        canvas.create_rectangle(0, 0, fill_w, BAR_H, fill="#4aa3ff", outline="")
        # overlay text
        canvas.create_text(BAR_W//2, BAR_H//2, text=f"{cur}/{mx}", fill="#eef", font=("Segoe UI", 9))

    def refresh(self):
        ship = world.player_ship(self.conn)
        p = world.get_player(self.conn)
        # Assumptions: shields and cargo usage are computed as below; adapt to your world.py if needed
        shields = int(ship.get("shields", 0))
        max_shields = max(1, shields)
        cargo_cap = int(ship["cargo_capacity"])
        cargo_used = sum(int(r["quantity"]) for r in world.player_cargo(self.conn))
        max_energy = 10
        fuel_cap = int(ship["fuel_capacity"])

        self.lbl_ship.config(text=ship["name"])
        self._draw_bar(self.bar_hull, int(p["hp"]), 100)
        self._draw_bar(self.bar_sh, shields, max_shields)
        self._draw_bar(self.bar_en, int(p["energy"]), max_energy)
        self._draw_bar(self.bar_cg, cargo_used, cargo_cap)
        self._draw_bar(self.bar_fuel, int(p["fuel"]), fuel_cap)
