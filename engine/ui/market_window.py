from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3

class MarketWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk, conn: sqlite3.Connection, bus, station_id: int, wsm, on_close):
        super().__init__(root)
        self.conn = conn; self.bus = bus; self.station_id = int(station_id); self.wsm = wsm; self._on_close = on_close
        self.title("Market")
        geom = getattr(wsm, "get_geometry", lambda *_: "720x420")("market", "720x420")
        self.geometry(geom)

        self.tree = ttk.Treeview(self, columns=("name","mqty","pqty","price","buy","sell"), show="headings")
        for i,(hdr,w) in enumerate((("Item",220),("Market Qty",90),("Your Qty",80),("Price",70),("Buy",60),("Sell",60))):
            self.tree.heading(i, text=hdr); self.tree.column(i, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._ensure_tables()
        self._refresh()

    def _handle_close(self) -> None:
        geom = self.geometry()
        if hasattr(self.wsm, "save_geometry"):
            self.wsm.save_geometry("market", geom)
        if callable(self._on_close): self._on_close()

    def _ensure_tables(self) -> None:
        # minimal safety so window doesn't explode on new saves
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS market_prices(
                station_id INTEGER NOT NULL,
                item_id    INTEGER NOT NULL,
                quantity   INTEGER NOT NULL DEFAULT 0,
                price      INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (station_id, item_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS player_cargo(
                item_id INTEGER PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.conn.commit()

    def _refresh(self) -> None:
        for iid in self.tree.get_children(): self.tree.delete(iid)
        rows = self.conn.execute("""
            SELECT i.id, i.name,
                   COALESCE(mp.quantity,0) AS mqty,
                   COALESCE(pc.quantity,0) AS pqty,
                   COALESCE(mp.price,1)    AS price
            FROM items i
            LEFT JOIN market_prices mp
              ON mp.item_id=i.id AND mp.station_id=?
            LEFT JOIN player_cargo pc
              ON pc.item_id=i.id
            ORDER BY i.name
        """, (self.station_id,)).fetchall()
        for r in rows:
            self.tree.insert("", "end",
                             iid=str(r["id"]),
                             values=(r["name"], r["mqty"], r["pqty"], r["price"], "Buy", "Sell"))
