from __future__ import annotations

import sqlite3
from typing import cast

from tkinter import simpledialog, messagebox

from .app_context import AppContext


class CheatService:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    def give_credits(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        amt = simpledialog.askinteger("Give Credits", "Amount:", parent=self.ctx.root, minvalue=1, initialvalue=1000)
        if not amt:
            return
        try:
            conn.execute("UPDATE player SET credits = credits + ? WHERE id=1", (int(amt),))
            conn.commit()
            self.ctx.bus.emit("log", "system", f"Cheat: +{amt} credits")
            self.ctx.bus.emit("status_changed")
        except Exception as e:
            messagebox.showerror("Cheat", f"Failed: {e}")

    def give_item(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        item_id = simpledialog.askinteger("Give Item", "Item ID:", parent=self.ctx.root, minvalue=1, initialvalue=1)
        if not item_id:
            return
        qty = simpledialog.askinteger("Give Item", "Quantity:", parent=self.ctx.root, minvalue=1, initialvalue=10)
        if not qty:
            return
        try:
            conn.execute(
                """
                INSERT INTO player_cargo(item_id, quantity) VALUES(?, ?)
                ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + excluded.quantity
                """,
                (int(item_id), int(qty)),
            )
            conn.commit()
            self.ctx.bus.emit("log", "system", f"Cheat: Added item #{item_id} x{qty}")
            self.ctx.bus.emit("status_changed")
        except Exception as e:
            messagebox.showerror("Cheat", f"Failed: {e}")

    def give_ship(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        ship_id = simpledialog.askinteger("Give Ship", "Ship ID:", parent=self.ctx.root, minvalue=1, initialvalue=1)
        if not ship_id:
            return
        try:
            conn.execute("INSERT INTO hangar_ships(ship_id, is_active) VALUES(?, 0)", (int(ship_id),))
            conn.commit()
            self.ctx.bus.emit("log", "system", f"Cheat: Added ship #{ship_id} to hangar")
            self.ctx.bus.emit("status_changed")
        except Exception as e:
            messagebox.showerror("Cheat", f"Failed: {e}")
