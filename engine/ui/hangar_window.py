# engine/ui/hangar_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

class HangarWindow(tk.Toplevel):
    def __init__(self, root: tk.Tk, conn: sqlite3.Connection, bus, wsm, on_close):
        super().__init__(root)
        self.conn = conn; self.bus = bus; self.wsm = wsm; self._on_close = on_close
        self.title("Hangar")
        geom = getattr(wsm, "get_geometry", lambda *_: "700x420")("hangar", "700x420")
        self.geometry(geom)

        self.tree = ttk.Treeview(self, columns=("name","fuel","jump","cargo","active"), show="headings")
        for i,(hdr,w) in enumerate((("Name",200),("Fuel",70),("Jump",70),("Cargo",80),("Active",60))):
            self.tree.heading(i, text=hdr); self.tree.column(i, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        btns = ttk.Frame(self); btns.pack(anchor="e", padx=6, pady=(0,6))
        ttk.Button(btns, text="Inspect", command=self._inspect_sel).pack(side="left", padx=4)
        ttk.Button(btns, text="Set Active", command=self._activate_sel).pack(side="left", padx=4)
        ttk.Button(btns, text="Sell", command=self._sell_sel).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._refresh()

    def _handle_close(self) -> None:
        geom = self.geometry()
        if hasattr(self.wsm, "save_geometry"):
            self.wsm.save_geometry("hangar", geom)
        if callable(self._on_close): self._on_close()

    def _refresh(self) -> None:
        for iid in self.tree.get_children(): self.tree.delete(iid)
        try:
            rows = self.conn.execute("""
                SELECT h.ship_id AS id, s.name,
                       COALESCE(s.fuel_capacity,0)  AS fuel_capacity,
                       COALESCE(s.jump_range,0)     AS jump_range,
                       COALESCE(s.cargo_capacity,0) AS cargo_capacity,
                       h.is_active
                FROM hangar_ships h
                JOIN ships s ON s.id = h.ship_id
                ORDER BY h.is_active DESC, s.name
            """).fetchall()
        except sqlite3.OperationalError:
            rows = []
        for r in rows:
            self.tree.insert("", "end", iid=str(r["id"]),
                             values=(r["name"], r["fuel_capacity"], r["jump_range"], r["cargo_capacity"],
                                     "Yes" if r["is_active"] else "No"))

    def _sel_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel: return None
        return int(sel[0])

    def _inspect_sel(self) -> None:
        sid = self._sel_id()
        if sid is None: return
        self._show_inspect(sid)

    def _show_inspect(self, ship_id: int, source: str="hangar") -> None:
        row = self.conn.execute("SELECT * FROM ships WHERE id=?", (ship_id,)).fetchone()
        if not row:
            messagebox.showerror("Inspect", "Ship not found.")
            return
        # shields/price may not exist in schema; guard by keys
        keys = set(row.keys())
        shields = row["shields"] if "shields" in keys else 0
        damage  = row["damage"]  if "damage"  in keys else 0
        value   = row["price"]   if "price"   in keys else (row["base_value"] if "base_value" in keys else 100)

        dlg = tk.Toplevel(self); dlg.title("Ship Details"); dlg.transient(self); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10); frm.grid(sticky="nsew")
        def r(i, label, val):
            ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="e", padx=(0,8), pady=2)
            ttk.Label(frm, text=str(val)).grid(row=i, column=1, sticky="w", pady=2)
        i=0
        r(i, "Name", row["name"]); i+=1
        r(i, "Damage", damage); i+=1
        r(i, "Shields", shields); i+=1
        r(i, "Fuel Cap.", row["fuel_capacity"]); i+=1
        r(i, "Jump Range", row["jump_range"]); i+=1
        r(i, "Cargo Cap.", row["cargo_capacity"]); i+=1
        r(i, "Value", value); i+=1
        ttk.Button(frm, text="Close", command=dlg.destroy).grid(row=i, column=0, columnspan=2, pady=(8,0))

    def _activate_sel(self) -> None:
        sid = self._sel_id()
        if sid is None: return
        self.conn.execute("UPDATE hangar_ships SET is_active=0")
        self.conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (sid,))
        self.conn.commit()
        self._refresh()

    def _sell_sel(self) -> None:
        sid = self._sel_id()
        if sid is None: return
        # value is half of price/base_value if available, else 100
        row = self.conn.execute("SELECT * FROM ships WHERE id=?", (sid,)).fetchone()
        keys = set(row.keys()) if row else set()
        price = row["price"] if row and "price" in keys else (row["base_value"] if row and "base_value" in keys else 200)
        value = int(price) // 2
        self.conn.execute("DELETE FROM hangar_ships WHERE ship_id=?", (sid,))
        self.conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (value,))
        # activate some other ship if any
        other = self.conn.execute("SELECT ship_id FROM hangar_ships LIMIT 1").fetchone()
        if other:
            self.conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (other["ship_id"],))
        self.conn.commit()
        self._refresh()
