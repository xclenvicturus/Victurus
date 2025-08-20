# engine/ui/quests_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from typing import Optional
from ..controllers.quest_controller import QuestController

class QuestsWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk, conn: sqlite3.Connection, bus, qc: QuestController, wsm, on_close):
        super().__init__(root)
        self.conn = conn; self.bus = bus; self.qc = qc; self.wsm = wsm; self._on_close = on_close
        self.title("Quests")
        geom = getattr(wsm, "get_geometry", lambda *_: "620x400")("quests", "620x400")
        self.geometry(geom)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.frm_av = ttk.Frame(self.tabs); self.tabs.add(self.frm_av, text="Available")
        self.frm_ac = ttk.Frame(self.tabs); self.tabs.add(self.frm_ac, text="Active")
        self.frm_co = ttk.Frame(self.tabs); self.tabs.add(self.frm_co, text="Completed")

        self.tree_av = ttk.Treeview(self.frm_av, columns=("name","desc"), show="headings")
        for i,(hdr,w) in enumerate((("Name",200),("Description",360))):
            self.tree_av.heading(i, text=hdr); self.tree_av.column(i, width=w, anchor="w")
        self.tree_av.pack(fill="both", expand=True, padx=6, pady=6)

        self.tree_ac = ttk.Treeview(self.frm_ac, columns=("name","desc"), show="headings")
        self.tree_ac.heading(0, text="Name"); self.tree_ac.heading(1, text="Description")
        self.tree_ac.column(0, width=200, anchor="w"); self.tree_ac.column(1, width=360, anchor="w")
        self.tree_ac.pack(fill="both", expand=True, padx=6, pady=6)

        self.tree_co = ttk.Treeview(self.frm_co, columns=("name","desc"), show="headings")
        self.tree_co.heading(0, text="Name"); self.tree_co.heading(1, text="Description")
        self.tree_co.column(0, width=200, anchor="w"); self.tree_co.column(1, width=360, anchor="w")
        self.tree_co.pack(fill="both", expand=True, padx=6, pady=6)

        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.refresh()

    def _handle_close(self) -> None:
        geom = self.geometry()
        if hasattr(self.wsm, "save_geometry"):
            self.wsm.save_geometry("quests", geom)
        if callable(self._on_close): self._on_close()

    def refresh(self) -> None:
        loc = None
        try:
            row = self.conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
            if row: loc = row["location_id"]
        except Exception:
            pass

        for tree in (self.tree_av, self.tree_ac, self.tree_co):
            for iid in tree.get_children():
                tree.delete(iid)

        for q in self.qc.get_available_quests(loc):
            self.tree_av.insert("", "end", values=(q["name"], q["description"]))
        for q in self.qc.get_active_quests():
            self.tree_ac.insert("", "end", values=(q["name"], q["description"]))
        for q in self.qc.get_completed_quests():
            self.tree_co.insert("", "end", values=(q["name"], q["description"]))
