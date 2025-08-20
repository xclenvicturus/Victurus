from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from .. import world
from ..settings import WindowStateManager
from ..event_bus import EventBus

class CargoWindow:
    """
    Live, filter-as-you-type cargo view.
    - Shows only items with quantity > 0
    - Columns: Name, Quantity
    """
    def __init__(self, root, conn: sqlite3.Connection, bus: EventBus, wsm: WindowStateManager, on_close=None):
        self.root = root
        self.conn = conn
        self.bus = bus

        self.win = tk.Toplevel(self.root)
        self.win.title("Cargo")
        self.win.geometry("520x420")
        wsm.bind(self.win, "cargo", on_close=on_close)

        top = ttk.Frame(self.win); top.pack(fill="x", padx=8, pady=6)
        self.search_var = tk.StringVar()
        ttk.Label(top, text="Search:").pack(side="left")
        e = ttk.Entry(top, textvariable=self.search_var)
        e.pack(side="left", fill="x", expand=True, padx=(6,6))
        self.search_var.trace_add("write", lambda *_: self._refresh())

        self.category = tk.StringVar(value="All")
        cat_cb = ttk.Combobox(top, textvariable=self.category, state="readonly",
                     values=["All","Commodity","Consumable","Fuel","Quest"], width=14)
        cat_cb.pack(side="left")
        cat_cb.bind("<<ComboboxSelected>>", lambda *_: self._refresh())

        self.tree = ttk.Treeview(self.win, columns=("name","qty"), show="headings", selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.heading("qty", text="Quantity")
        self.tree.column("name", width=300, anchor="w")
        self.tree.column("qty", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        self._refresh()

        # live updates
        bus.on("status_changed", lambda *a, **k: self._refresh())

    def _refresh(self):
        q = self.search_var.get().strip().lower()
        cat = self.category.get()
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = world.player_cargo(self.conn)
        for r in rows:
            if int(r["quantity"]) <= 0:
                continue
            name = str(r["name"])
            if q and q not in name.lower():
                continue
            # category filter placeholder; if you have categories in DB, check here.
            if cat != "All":
                pass
            self.tree.insert("", "end", iid=str(r["item_id"]), values=(name, r["quantity"]))
