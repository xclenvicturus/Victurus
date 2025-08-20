from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from typing import Optional, Tuple, List

class MapWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk, conn: sqlite3.Connection, bus, travel, wsm, on_close):
        super().__init__(root)
        self.conn = conn; self.bus = bus; self.travel = travel; self.wsm = wsm; self._on_close = on_close
        self.title("Galaxy Map")
        geom = getattr(wsm, "get_geometry", lambda *_: "900x600")("galaxy_map", "900x600")
        self.geometry(geom)

        self.canvas = tk.Canvas(self, bg="#0c0f14")
        self.canvas.pack(fill="both", expand=True)

        self._stations = self._load_stations()
        self._links    = self._load_links()  # tolerates missing table

        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._draw()

    def _handle_close(self) -> None:
        geom = self.geometry()
        if hasattr(self.wsm, "save_geometry"):
            self.wsm.save_geometry("galaxy_map", geom)
        if callable(self._on_close): self._on_close()

    def _load_stations(self):
        try:
            return self.conn.execute("SELECT id, name, x, y FROM stations").fetchall()
        except Exception:
            # minimal fallback if coords are not there
            return self.conn.execute("SELECT id, name, 0 AS x, 0 AS y FROM stations").fetchall()

    def _load_links(self) -> List[Tuple[int,int,Optional[float]]]:
        try:
            rows = self.conn.execute("SELECT a, b, distance FROM links").fetchall()
            return [(int(r["a"]), int(r["b"]), r["distance"]) for r in rows]
        except Exception:
            return []

    def _draw(self) -> None:
        self.canvas.delete("all")
        # draw links
        xy = {r["id"]: (float(r["x"]), float(r["y"])) for r in self._stations}
        for a,b,dist in self._links:
            if a in xy and b in xy:
                x1,y1 = xy[a]; x2,y2 = xy[b]
                self.canvas.create_line(x1, y1, x2, y2, fill="#445")
        # draw stations
        for r in self._stations:
            x,y = float(r["x"]), float(r["y"])
            self.canvas.create_oval(x-3, y-3, x+3, y+3, outline="#8cf", fill="#8cf")
            self.canvas.create_text(x+6, y, text=r["name"], anchor="w", fill="#cdd")
