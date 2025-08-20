from __future__ import annotations

import random
import sqlite3
from typing import Optional, cast

from tkinter import ttk, messagebox

from .app_context import AppContext
from . import world, actions, sim


class ActionsPanel:
    """
    Owns the 'Actions Available' area + auto-features + periodic economy ticks.
    Also wires the Talk button and NPC list behavior.
    """

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.auto_flags = {"autorepair": False, "autofuel": False, "autorecharge": False}

    # ----- public wiring -----

    def wire_talk(self, button) -> None:
        button.config(command=self.talk_to_selected_npc)

    # ----- helpers -----

    def clear(self) -> None:
        panel = self.ctx.actions_panel
        if not panel:
            return
        for w in panel.winfo_children():
            w.destroy()

    def refresh(self) -> None:
        if not (self.ctx.conn and self.ctx.actions_panel and self.ctx.station_title):
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)

        p = world.get_player(conn)
        self.clear()
        if p["location_type"] != "station":
            self.ctx.station_title.config(text="In Transit...")
            if self.ctx.npc_list:
                self.ctx.npc_list.delete(0, "end")
            return

        detail = world.station_detail(conn, int(p["location_id"]))
        self.ctx.station_title.config(
            text=f"{detail['station']['name']} ({detail['station']['planet_name']}) [{detail['station']['faction_name']}]"
        )

        # NPCs
        if self.ctx.npc_list:
            self.ctx.npc_list.delete(0, "end")
            for n in detail["npcs"]:
                self.ctx.npc_list.insert("end", f"#{n['id']} {n['name']} ({n['role']})")

        # Actions – Refuel/Repair/Recharge at top (only if needed)
        ship = world.player_ship(conn)
        fuel_cap = int(ship["fuel_capacity"])
        p_fuel = int(p["fuel"])
        hp = int(p["hp"])
        max_energy = 10
        energy = int(p["energy"])

        svc = actions.current_service_prices(conn, int(p["location_id"]))

        def add_btn(text, fn):
            ttk.Button(self.ctx.actions_panel, text=text, command=fn).pack(fill="x", pady=2)

        if p_fuel < fuel_cap:
            need = fuel_cap - p_fuel
            total = need * svc["fuel"]
            add_btn(f"Refuel ({total} cr)", self._do_refuel)

        if hp < 100:
            missing = 100 - hp
            total = missing * svc["repair"]
            add_btn(f"Repair ({total} cr)", self._do_repair)

        if energy < max_energy:
            need = max_energy - energy
            total = need * svc["energy"]
            add_btn(f"Recharge ({total} cr)", self._do_recharge)

        # Station utilities
        if detail["market"]:
            add_btn("Market", self._toggle_market)
        add_btn("Hangar", self._toggle_hangar)
        add_btn("Repair Ship", self._do_repair)

        if self.ctx.in_combat:
            self.set_combat_ui(True, None)

    # ----- actions -----

    def _do_refuel(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        p = world.get_player(conn)
        ship = world.player_ship(conn)
        need = max(0, int(ship["fuel_capacity"]) - int(p["fuel"]))
        if need <= 0:
            return
        msg = actions.refuel(conn, int(p["location_id"]), need)
        self.ctx.bus.emit("log", "trade", msg)
        self.ctx.bus.emit("status_changed")

    def _do_repair(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        p = world.get_player(conn)
        if int(p["hp"]) >= 100:
            return
        msg = actions.repair_full(conn, int(p["location_id"]))
        if "Not enough credits" in msg:
            messagebox.showerror("Repair", msg)
        else:
            self.ctx.bus.emit("log", "trade", msg)
            self.ctx.bus.emit("status_changed")

    def _do_recharge(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        p = world.get_player(conn)
        if int(p["energy"]) >= 10:
            return
        msg = actions.recharge_full(conn, int(p["location_id"]), 10)
        if "Not enough credits" in msg:
            messagebox.showerror("Recharge", msg)
        else:
            self.ctx.bus.emit("log", "trade", msg)
            self.ctx.bus.emit("status_changed")

    def _toggle_market(self):
        from .window_togglers import WindowTogglers  # local import to avoid cycles
        WindowTogglers(self.ctx).toggle_market()

    def _toggle_hangar(self):
        from .window_togglers import WindowTogglers
        WindowTogglers(self.ctx).toggle_hangar()

    def talk_to_selected_npc(self) -> None:
        if not (self.ctx.conn and self.ctx.npc_list):
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)

        sel = self.ctx.npc_list.curselection()
        if not sel:
            self.ctx.bus.emit("log", "dialogue", "Select an NPC first.")
            return
        text = self.ctx.npc_list.get(sel[0])
        npc_id = int(text.split()[0].strip("#"))
        row = conn.execute("SELECT * FROM npcs WHERE id=?", (npc_id,)).fetchone()
        if not row:
            self.ctx.bus.emit("log", "dialogue", "No one answers.")
            return
        self.ctx.bus.emit("log", "dialogue", f"{row['name']} ({row['role']}): \"{row['dialog']}\"")

        if self.ctx.qc:
            self.ctx.qc.add_player_event(f"talk_to_npc:{npc_id}")

        # Open Quests if not already open; refresh & focus Dialogue tab
        qwin = self.ctx.windows.get("quests")
        if not qwin:
            from .window_togglers import WindowTogglers
            WindowTogglers(self.ctx).toggle_quests()
            qwin = self.ctx.windows.get("quests")
        try:
            if qwin and hasattr(qwin, "refresh_all"):
                qwin.refresh_all()
        except Exception:
            pass
        if self.ctx.log_panel:
            self.ctx.log_panel.focus_tab("dialogue")

    # ----- features & ticks -----

    def toggle_feature(self, key: str) -> None:
        self.auto_flags[key] = not self.auto_flags.get(key, False)
        state = "ON" if self.auto_flags[key] else "OFF"
        self.ctx.bus.emit("log", "system", f"{key.capitalize()} {state}")

    def maybe_autos(self, station_id: int) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        p = world.get_player(conn)
        ship = world.player_ship(conn)
        changed = False
        if self.auto_flags["autofuel"] and int(p["fuel"]) < int(ship["fuel_capacity"]):
            msg = actions.refuel(conn, station_id, int(ship["fuel_capacity"]) - int(p["fuel"]))
            self.ctx.bus.emit("log", "trade", f"[Auto] {msg}")
            changed = True
        if self.auto_flags["autorepair"] and int(p["hp"]) < 100:
            msg = actions.repair_full(conn, station_id)
            self.ctx.bus.emit("log", "trade", f"[Auto] {msg}")
            changed = True
        if self.auto_flags["autorecharge"] and int(p["energy"]) < 10:
            msg = actions.recharge_full(conn, station_id, 10)
            self.ctx.bus.emit("log", "trade", f"[Auto] {msg}")
            changed = True
        if changed:
            self.ctx.bus.emit("status_changed")

    def schedule_tick(self) -> None:
        if not self.ctx.conn:
            return
        conn = cast(sqlite3.Connection, self.ctx.conn)
        sim.economy_tick(conn)
        sim.faction_skirmish_tick(conn)
        sim.wars_tick(conn)
        self.refresh()
        self.ctx.root.after(5000, self.schedule_tick)

    # ----- combat inline -----

    def set_combat_ui(self, enabled: bool, initial_state: Optional[dict]) -> None:
        self.clear()
        if enabled:
            self.ctx.in_combat = True
            if self.ctx.combat and initial_state:
                self.ctx.combat.start(initial_state)
            cframe = ttk.Frame(self.ctx.actions_panel)
            cframe.pack(fill="x")
            ttk.Button(cframe, text="Fire (F)", command=lambda: self._combat_act("fire")).pack(fill="x", pady=2)
            ttk.Button(cframe, text="Brace (B)", command=lambda: self._combat_act("brace")).pack(fill="x", pady=2)
            ttk.Button(cframe, text="Flee (L)", command=lambda: self._combat_act("flee")).pack(fill="x", pady=2)
            ttk.Button(cframe, text="Repair (R)", command=lambda: self._combat_act("repair")).pack(fill="x", pady=2)
        else:
            self.ctx.in_combat = False
            self.refresh()

    def _combat_act(self, action: str) -> None:
        if not self.ctx.combat:
            return
        _log, over = self.ctx.combat.act(action)
        if over:
            self.ctx.in_combat = False
            self.set_combat_ui(False, None)
        self.ctx.bus.emit("status_changed")
