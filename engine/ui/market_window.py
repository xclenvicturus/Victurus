# engine/ui/market_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import sqlite3

from engine import actions


class MarketWindow(tk.Toplevel):
    def __init__(self, root: tk.Misc, conn: sqlite3.Connection, bus, wsm, station_id: int, on_close=None):
        super().__init__(root)
        self.title("Market")
        self.conn = conn
        self.bus = bus
        self.wsm = wsm
        self.station_id = int(station_id)
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.geometry("820x520")

        # Search + category (category optional in DB; kept for future)
        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill="x")

        ttk.Label(top, text="Search:").pack(side="left")
        self.ent_search = ttk.Entry(top, width=28)
        self.ent_search.pack(side="left", padx=(4, 8))
        self.ent_search.bind("<KeyRelease>", lambda _e: self._refresh())

        # Tree
        cols = ("name", "market_qty", "player_qty", "price", "buy", "sell")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        hdrs = [("name", "Name", 240), ("market_qty", "Market Qty", 100),
                ("player_qty", "You", 80), ("price", "Price", 80),
                ("buy", "Buy", 80), ("sell", "Sell", 80)]
        for key, text, w in hdrs:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree.bind("<Button-1>", self._on_click_button)

        self._refresh()

    def _close(self):
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()

    def _refresh(self):
        q = (self.ent_search.get() or "").strip().lower()
        for i in self.tree.get_children():
            self.tree.delete(i)

        rows = self.conn.execute("""
            SELECT i.id, i.name,
                   COALESCE(m.quantity,0) AS market_qty,
                   COALESCE(m.price,1)    AS price,
                   COALESCE(pc.quantity,0) AS player_qty
            FROM items i
            LEFT JOIN market_prices m ON m.item_id=i.id AND m.station_id=?
            LEFT JOIN player_cargo pc ON pc.item_id=i.id
            ORDER BY i.name
        """, (self.station_id,)).fetchall()

        for r in rows:
            name = str(r["name"])
            if q and q not in name.lower():
                continue
            iid = f"item:{r['id']}"
            self.tree.insert("", "end", iid=iid, values=(
                name, int(r["market_qty"]), int(r["player_qty"]), int(r["price"]), "Buy", "Sell"
            ))

    def _on_click_button(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        vals = self.tree.item(row_id, "values")
        if not vals:
            return

        item_id = int(row_id.split(":", 1)[1])
        col_index = int(col_id.replace("#", "")) - 1  # 0-based

        # columns: 0 name, 1 market_qty, 2 player_qty, 3 price, 4 buy, 5 sell
        if col_index == 4:
            self._buy_flow(item_id, vals)
        elif col_index == 5:
            self._sell_flow(item_id, vals)

    def _buy_flow(self, item_id: int, row_vals):
        market_qty = int(row_vals[1])
        player_qty = int(row_vals[2])
        price = int(row_vals[3])

        # compute caps
        cap_row = self.conn.execute("""
            SELECT s.cargo_capacity
            FROM hangar_ships h JOIN ships s ON s.id=h.ship_id
            WHERE h.is_active=1
        """).fetchone()
        cap = int(cap_row["cargo_capacity"]) if cap_row else 0
        used = int(self.conn.execute("SELECT COALESCE(SUM(quantity),0) FROM player_cargo").fetchone()[0])
        cargo_left = max(0, cap - used)
        credits = int(self.conn.execute("SELECT credits FROM player WHERE id=1").fetchone()[0])

        max_by_stock = market_qty
        max_by_cargo = cargo_left
        max_by_money = credits // max(price, 1)
        default_qty = max(0, min(max_by_stock, max_by_cargo, max_by_money))

        if default_qty <= 0:
            messagebox.showinfo("Market", "You cannot buy this right now.")
            return

        qty = simpledialog.askinteger("Buy", f"Buy how many? (max {default_qty})", minvalue=1, maxvalue=default_qty,
                                      initialvalue=default_qty, parent=self)
        if not qty:
            return
        msg = actions.buy_item(self.conn, self.station_id, item_id, qty)
        self._refresh()
        try:
            self.bus.emit("log", {"category": "trade", "message": msg})
            self.bus.emit("status_changed")
        except Exception:
            pass

    def _sell_flow(self, item_id: int, row_vals):
        player_qty = int(row_vals[2])
        if player_qty <= 0:
            messagebox.showinfo("Market", "You don't have any to sell.")
            return
        qty = simpledialog.askinteger("Sell", f"Sell how many? (max {player_qty})", minvalue=1, maxvalue=player_qty,
                                      initialvalue=player_qty, parent=self)
        if not qty:
            return
        msg = actions.sell_item(self.conn, self.station_id, item_id, qty)
        self._refresh()
        try:
            self.bus.emit("log", {"category": "trade", "message": msg})
            self.bus.emit("status_changed")
        except Exception:
            pass
