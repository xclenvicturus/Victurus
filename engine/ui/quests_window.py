# engine/ui/quests_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

from engine.controllers.quest_controller import QuestController


class QuestsWindow(tk.Toplevel):
    def __init__(self, root: tk.Misc, conn: sqlite3.Connection, bus, wsm, qc: QuestController, on_close=None):
        super().__init__(root)
        self.title("Quests")
        self.conn = conn
        self.bus = bus
        self.wsm = wsm
        self.qc = qc
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.geometry("740x520")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.frm_avail = ttk.Frame(self.nb, padding=8)
        self.frm_active = ttk.Frame(self.nb, padding=8)
        self.frm_done = ttk.Frame(self.nb, padding=8)
        self.nb.add(self.frm_avail, text="Available")
        self.nb.add(self.frm_active, text="Active")
        self.nb.add(self.frm_done, text="Completed")

        self.av_tree = self._make_tree(self.frm_avail)
        self.ac_tree = self._make_tree(self.frm_active)
        self.co_tree = self._make_tree(self.frm_done, allow_accept=False)

        # Buttons in Available
        af = ttk.Frame(self.frm_avail)
        af.pack(fill="x", pady=(6, 0))
        ttk.Button(af, text="Accept", command=self._accept).pack(side="left")
        ttk.Button(af, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        # Buttons in Active
        bf = ttk.Frame(self.frm_active)
        bf.pack(fill="x", pady=(6, 0))
        ttk.Button(bf, text="Abandon", command=self._abandon).pack(side="left")
        ttk.Button(bf, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        # Listen to bus
        try:
            self.bus.on("quests_changed", lambda *_a, **_k: self.refresh())
        except Exception:
            pass

        self.refresh()

    def _close(self):
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()

    def _make_tree(self, parent, allow_accept=True):
        cols = ("id", "name", "desc")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=12, selectmode="browse")
        for key, txt, w in [("id", "ID", 60), ("name", "Name", 220), ("desc", "Details", 360)]:
            tree.heading(key, text=txt)
            tree.column(key, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def _clear(self, tree: ttk.Treeview):
        for i in tree.get_children():
            tree.delete(i)

    def refresh(self):
        self._clear(self.av_tree)
        self._clear(self.ac_tree)
        self._clear(self.co_tree)

        # Location for available filter
        pr = self.conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
        loc = int(pr["location_id"]) if pr and pr["location_id"] is not None else 0

        for q in self.qc.get_available_quests(loc):
            self.av_tree.insert("", "end", iid=f"q:{q['id']}", values=(q["id"], q["name"], q["desc"]))
        for q in self.qc.get_active_quests():
            self.ac_tree.insert("", "end", iid=f"a:{q['id']}", values=(q["id"], q["name"], q["desc"]))
        for q in self.qc.get_completed_quests():
            self.co_tree.insert("", "end", iid=f"c:{q['id']}", values=(q["id"], q["name"], q["desc"]))

    def _selected_id(self, tree: ttk.Treeview) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        try:
            iid = sel[0]
            return int(iid.split(":", 1)[1])
        except Exception:
            return None

    def _accept(self):
        qid = self._selected_id(self.av_tree)
        if qid is None:
            messagebox.showinfo("Quests", "Select an available quest.")
            return
        self.qc.accept(qid)
        self.refresh()

    def _abandon(self):
        qid = self._selected_id(self.ac_tree)
        if qid is None:
            messagebox.showinfo("Quests", "Select an active quest.")
            return
        # Optional penalty could be applied here
        self.qc.abandon(qid)
        self.refresh()
