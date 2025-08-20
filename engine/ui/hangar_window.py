# engine/ui/hangar_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from typing import Optional


def _table_has_col(conn: sqlite3.Connection, table: str, col: str) -> bool:
    try:
        info = conn.execute(f"PRAGMA table_info({table});").fetchall()
        return any(r[1] == col for r in info)
    except Exception:
        return False


class HangarWindow(tk.Toplevel):
    """
    Shows ships in player's hangar. Lets you set active ship, inspect, or sell.
    Robust to missing columns like ships.shield or ships.price by falling back.
    """

    def __init__(self, root: tk.Misc, conn: sqlite3.Connection, bus, wsm, on_close=None):
        super().__init__(root)
        self.title("Hangar")
        self.conn = conn
        self.bus = bus
        self.wsm = wsm
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.geometry(self.wsm.get_geometry("hangar", "700x420"))

        # Top buttons
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=6)

        ttk.Button(top, text="Inspect", command=self._inspect_hangar).pack(side="left")
        ttk.Button(top, text="Set Active", command=self._set_active_sel).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Sell", command=self._sell_sel).pack(side="left", padx=(6, 0))

        # Table
        cols = ("name", "active", "jump", "fuel", "cargo")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        self.tree.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree.heading("name", text="Name")
        self.tree.heading("active", text="Active")
        self.tree.heading("jump", text="Jump Range")
        self.tree.heading("fuel", text="Fuel Cap.")
        self.tree.heading("cargo", text="Cargo Cap.")

        self.tree.column("name", width=240, anchor="w")
        self.tree.column("active", width=70, anchor="center")
        self.tree.column("jump", width=90, anchor="e")
        self.tree.column("fuel", width=90, anchor="e")
        self.tree.column("cargo", width=90, anchor="e")

        self._refresh()

    def _close(self):
        # persist geometry
        try:
            self.wsm.set_geometry("hangar", self.geometry())
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()

    # ---------- actions ----------

    def _sel_ship_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])  # we'll store id in "iid", safer to store separately
        except Exception:
            # we actually store id in iid, so use that:
            try:
                return int(sel[0])
            except Exception:
                return None

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())

        # active column comes from hangar_ships.is_active
        rows = self.conn.execute("""
            SELECT h.ship_id AS id, s.name,
                   COALESCE(s.jump_range, 0)     AS jump_range,
                   COALESCE(s.fuel_capacity, 0)  AS fuel_capacity,
                   COALESCE(s.cargo_capacity, 0) AS cargo_capacity,
                   CASE WHEN h.is_active=1 THEN 1 ELSE 0 END AS active
            FROM hangar_ships h
            JOIN ships s ON s.id = h.ship_id
            ORDER BY active DESC, s.name
        """).fetchall()

        for r in rows:
            iid = str(int(r["id"]))
            active_txt = "Yes" if int(r["active"]) == 1 else ""
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    r["name"],           # name
                    active_txt,          # active
                    r["jump_range"],     # jump
                    r["fuel_capacity"],  # fuel
                    r["cargo_capacity"], # cargo
                ),
            )

    def _inspect_hangar(self):
        sid = self._sel_ship_id()
        if sid is None:
            messagebox.showinfo("Hangar", "Select a ship first.")
            return
        self._show_inspect(sid, source="hangar")

    def _set_active_sel(self):
        sid = self._sel_ship_id()
        if sid is None:
            messagebox.showinfo("Hangar", "Select a ship first.")
            return
        self.conn.execute("UPDATE hangar_ships SET is_active=0")
        self.conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (sid,))
        self.conn.commit()
        try:
            self.bus.emit("status_changed", {})
        except Exception:
            pass
        self._refresh()

    def _sell_sel(self):
        sid = self._sel_ship_id()
        if sid is None:
            messagebox.showinfo("Hangar", "Select a ship first.")
            return

        # Confirm
        row = self.conn.execute("SELECT name FROM ships WHERE id=?", (sid,)).fetchone()
        name = row["name"] if row else f"Ship #{sid}"

        # Determine approximate value:
        # Prefer a market price (min across stations) -> 50% as sell value.
        price_row = self.conn.execute(
            "SELECT MIN(price) AS p FROM ship_market WHERE ship_id=?", (sid,)
        ).fetchone()
        base = int(price_row["p"]) if price_row and price_row["p"] is not None else 1000
        value = max(1, base // 2)

        if not messagebox.askyesno("Sell Ship", f"Sell {name} for {value} credits?"):
            return

        # If selling the active ship, we’ll activate another if one exists.
        self.conn.execute("DELETE FROM hangar_ships WHERE ship_id=?", (sid,))
        self.conn.execute("UPDATE player SET credits=credits+? WHERE id=1", (value,))
        # ensure some ship is active if any remain
        another = self.conn.execute("SELECT ship_id FROM hangar_ships LIMIT 1").fetchone()
        if another:
            self.conn.execute("UPDATE hangar_ships SET is_active=1 WHERE ship_id=?", (another["ship_id"],))
        self.conn.commit()

        try:
            self.bus.emit("status_changed", {})
        except Exception:
            pass

        self._refresh()

    # ---------- inspect ----------

    def _show_inspect(self, ship_id: int, source: str = "hangar"):
        row = self.conn.execute("SELECT * FROM ships WHERE id=?", (ship_id,)).fetchone()
        if not row:
            messagebox.showerror("Inspect", "Ship not found.")
            return

        # Column availability
        has_shields = _table_has_col(self.conn, "ships", "shields")
        has_hpmax   = _table_has_col(self.conn, "ships", "hull_max")
        has_price   = _table_has_col(self.conn, "ships", "price")  # optional (usually not present)

        dlg = tk.Toplevel(self)
        dlg.title(f"Inspect: {row['name']}")
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        def r(i, label, value):
            ttk.Label(frm, text=label + ":").grid(row=i, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(frm, text=str(value)).grid(row=i, column=1, sticky="w", pady=2)

        r(0, "Name", row["name"])
        r(1, "Jump Range", row["jump_range"] if "jump_range" in row.keys() else "N/A")
        r(2, "Fuel Capacity", row["fuel_capacity"] if "fuel_capacity" in row.keys() else "N/A")
        r(3, "Cargo Capacity", row["cargo_capacity"] if "cargo_capacity" in row.keys() else "N/A")
        r(4, "Shields", row["shields"] if has_shields and row["shields"] is not None else 0)
        r(5, "Hull Max", row["hull_max"] if has_hpmax and row["hull_max"] is not None else 100)

        # Show a price if the column exists; otherwise show an estimate
        if has_price and row["price"] is not None:
            price = int(row["price"])
        else:
            pr = self.conn.execute(
                "SELECT MIN(price) AS p FROM ship_market WHERE ship_id=?", (ship_id,)
            ).fetchone()
            price = int(pr["p"]) if pr and pr["p"] is not None else 1000
        r(6, "Typical Price", price)

        btn = ttk.Button(frm, text="Close", command=dlg.destroy)
        btn.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        btn.focus_set()
