from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import ttk
from typing import Optional, Any, Mapping

from ..controllers.quest_controller import QuestController
from .. import world


class QuestsWindow(tk.Toplevel):
    def __init__(
        self,
        root: tk.Tk,
        conn: sqlite3.Connection,
        bus,
        qc: QuestController,
        wsm,
        on_close,
    ) -> None:
        super().__init__(root)
        self.conn = conn
        self.bus = bus
        self.qc = qc
        self.wsm = wsm
        self._on_close = on_close

        self.title("Quests")
        geom = getattr(wsm, "get_geometry", lambda *_: "620x400")("quests", "620x400")
        self.geometry(geom)

        # Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        ttk.Label(self, text="Quests", anchor="w").grid(row=0, column=0, sticky="we", padx=6, pady=6)

        # Notebook with Available / Active / Completed
        self.nb = ttk.Notebook(self)
        self.nb.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.tree_av = self._make_tree(self.nb, ("name", "description"), (200, 360), ("Name", "Description"), "available")
        self.tree_ac = self._make_tree(self.nb, ("name", "description"), (200, 360), ("Name", "Description"), "active")
        self.tree_co = self._make_tree(self.nb, ("name", "description"), (200, 360), ("Name", "Description"), "completed")

        # Close handling
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Subscribe for external changes
        try:
            bus.on("quests_changed", lambda *a, **k: self.refresh())
        except Exception:
            pass

        self.refresh()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _make_tree(self, parent, cols, widths, headers, tab_name: str):
        frame = ttk.Frame(parent)
        parent.add(frame, text=tab_name.capitalize())
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for (c, w, h) in zip(cols, widths, headers):
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def _handle_close(self) -> None:
        geom = self.geometry()
        if hasattr(self.wsm, "save_geometry"):
            try:
                self.wsm.save_geometry("quests", geom)
            except Exception:
                pass
        if callable(self._on_close):
            try:
                self._on_close()
            except Exception:
                pass
        self.destroy()

    # ------------------------------------------------------------------
    # Data / refresh
    # ------------------------------------------------------------------
    def _current_location_id(self) -> Optional[int]:
        try:
            p: Mapping[str, Any] = world.get_player(self.conn)  # type: ignore[assignment]
            if p.get("location_type") == "station":
                v = p.get("location_id")
                if isinstance(v, int):
                    return v
                if isinstance(v, str) and v.isdigit():
                    return int(v)
        except Exception:
            pass
        # Legacy fallback to player table if schema differs
        try:
            row = self.conn.execute("SELECT location_id FROM player WHERE id=1").fetchone()
            if row:
                v2 = row["location_id"]
                if isinstance(v2, int):
                    return v2
                if isinstance(v2, str) and v2.isdigit():
                    return int(v2)
        except Exception:
            pass
        return None

    def refresh(self) -> None:
        loc: Optional[int] = self._current_location_id()

        # Clear current rows
        for tree in (self.tree_av, self.tree_ac, self.tree_co):
            for iid in tree.get_children():
                tree.delete(iid)

        # Available quests require a concrete location_id (int)
        available = []
        if isinstance(loc, int):
            try:
                available = list(self.qc.get_available_quests(loc))
            except Exception:
                available = []

        for q in available:
            self.tree_av.insert("", "end", values=(q.get("name", ""), q.get("description", "")))

        try:
            for q in self.qc.get_active_quests():
                self.tree_ac.insert("", "end", values=(q.get("name", ""), q.get("description", "")))
        except Exception:
            pass

        try:
            for q in self.qc.get_completed_quests():
                self.tree_co.insert("", "end", values=(q.get("name", ""), q.get("description", "")))
        except Exception:
            pass
