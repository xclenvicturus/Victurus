from __future__ import annotations
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, List, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

from .db_manager import DBManager, SCHEMA_FILES  # <-- SCHEMA_FILES imported here
from .save_schema import initialize as init_save_db
from .models import StartStation

class SaveManager:
    """
    Owns: New Game dialog, loading existing saves, Save/Save As/Delete.
    Uses template DBs under engine/assets_templates to seed <slot>/Database on new game.
    """

    def __init__(self, ctx, on_world_opened: Callable[[str, sqlite3.Connection], None]):
        self.ctx = ctx
        self.on_world_opened = on_world_opened
        # Template DB root inside repo
        self.templates_root = Path(__file__).resolve().parent / "assets_templates"
        self.new_dialog: Optional[tk.Toplevel] = None

    # ----------------- menu wiring -----------------

    def open_new_game_dialog(self) -> None:
        if self.new_dialog and tk.Toplevel.winfo_exists(self.new_dialog):
            self.new_dialog.lift()
            return

        root = self.ctx.root
        dlg = tk.Toplevel(root)
        dlg.title("New Game")
        dlg.transient(root)
        dlg.grab_set()
        dlg.resizable(False, False)
        self.new_dialog = dlg

        # form frame
        frm = ttk.Frame(dlg, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Save Name:").grid(row=0, column=0, sticky="w")
        ent_save = ttk.Entry(frm, width=28)
        ent_save.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ent_save.insert(0, "SaveGame")           # <-- default text
        ent_save.focus_set()

        ttk.Label(frm, text="Commander Name:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ent_player = ttk.Entry(frm, width=28)
        ent_player.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        ent_player.insert(0, "Commander")        # <-- default text

        ttk.Label(frm, text="Starting Station:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        stations = self._stations_from_templates()
        combo = ttk.Combobox(frm, state="readonly", width=42)
        combo["values"] = [f"{s.id}:{s.label}" for s in stations]
        if stations:
            combo.current(0)
        combo.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        # buttons
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, pady=(12, 0), sticky="e")

        def on_accept() -> None:
            save_name = ent_save.get().strip()[:30]
            player_name = ent_player.get().strip()[:30]
            if not save_name or not player_name:
                messagebox.showerror("New Game", "Save Name and Commander Name are required.")
                return
            if not stations:
                messagebox.showerror("New Game", "No starting stations found in templates.")
                return
            chosen = combo.get()
            if ":" in chosen:
                sid = int(chosen.split(":", 1)[0])
            else:
                sid = stations[0].id
            try:
                self._create_new_game(save_name, player_name, sid)
                dlg.destroy()
                self.new_dialog = None
            except Exception as e:
                messagebox.showerror("New Game", f"Failed to create new game:\n{e}")

        ttk.Button(btns, text="Create", command=on_accept).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=lambda: (dlg.destroy(), setattr(self, "new_dialog", None))).grid(row=0, column=1)

        # allow Enter/Esc
        dlg.bind("<Return>", lambda _e: on_accept())
        dlg.bind("<Escape>", lambda _e: (dlg.destroy(), setattr(self, "new_dialog", None)))

    def menu_open_save_dialog(self) -> None:
        root = self.ctx.root
        dlg = tk.Toplevel(root)
        dlg.title("Load Game")
        dlg.transient(root)
        dlg.resizable(False, False)

        saves = self._list_saves()
        lb = tk.Listbox(dlg, width=42, height=min(12, max(3, len(saves))))
        for s in saves:
            lb.insert("end", s)
        lb.grid(row=0, column=0, padx=12, pady=12)

        def do_open():
            idx = lb.curselection()
            if not idx:
                return
            self._open_save(saves[idx[0]])
            dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Open", command=do_open).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=dlg.destroy).grid(row=0, column=1)

        lb.bind("<Double-1>", lambda _e: do_open())

    def menu_save(self) -> None:
        try:
            if self.ctx.conn:
                self.ctx.conn.commit()
                self._log("system", "Game saved.")
        except Exception:
            pass

    def menu_save_as(self) -> None:
        # Simple duplicate of the entire save folder to a new name
        root = self.ctx.root
        dlg = tk.Toplevel(root)
        dlg.title("Save Game As")
        dlg.transient(root)
        dlg.resizable(False, False)

        ttk.Label(dlg, text="New Save Name (max 30):").grid(row=0, column=0, padx=12, pady=12, sticky="w")
        ent = ttk.Entry(dlg, width=36)
        ent.grid(row=0, column=1, padx=(0, 12), pady=12)
        ent.focus_set()

        def do_clone():
            new_name = ent.get().strip()[:30]
            if not new_name:
                return
            src = self._current_slot_dir()
            if not src.exists():
                messagebox.showerror("Save As", "No current save loaded to clone.")
                return
            dst = self._save_dir(new_name)
            if dst.exists():
                messagebox.showerror("Save As", "A save with that name already exists.")
                return
            shutil.copytree(src, dst)
            self._log("system", f"Cloned save to '{new_name}'.")
            dlg.destroy()

        ttk.Button(dlg, text="Save", command=do_clone).grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")
        ttk.Button(dlg, text="Cancel", command=dlg.destroy).grid(row=1, column=1, padx=12, pady=(0, 12), sticky="e")
        dlg.bind("<Return>", lambda _e: do_clone())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

    def menu_delete_save(self) -> None:
        saves = self._list_saves()
        if not saves:
            messagebox.showinfo("Delete Save", "No saves found.")
            return
        root = self.ctx.root
        dlg = tk.Toplevel(root)
        dlg.title("Delete Save")
        dlg.transient(root)
        dlg.resizable(False, False)

        lb = tk.Listbox(dlg, width=42, height=min(12, max(3, len(saves))))
        for s in saves:
            lb.insert("end", s)
        lb.grid(row=0, column=0, padx=12, pady=12)

        def do_delete():
            idx = lb.curselection()
            if not idx:
                return
            name = saves[idx[0]]
            if not messagebox.askyesno("Delete Save", f"Delete '{name}' permanently?"):
                return
            shutil.rmtree(self._save_dir(name), ignore_errors=True)
            self._log("system", f"Deleted save '{name}'.")
            dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Delete", command=do_delete).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=dlg.destroy).grid(row=0, column=1)

        lb.bind("<Delete>", lambda _e: do_delete())

    # ----------------- creation / opening -----------------

    def _create_new_game(self, save_name: str, player_name: str, start_station_id: int) -> None:
        slot = self._save_dir(save_name)
        if slot.exists():
            raise RuntimeError("A save with that name already exists.")
        (slot / "Database").mkdir(parents=True, exist_ok=True)

        # 1) Initialize save.db (save-state only)
        save_db = slot / "save.db"
        init_save_db(str(save_db))

        # 2) Copy template DBs to <slot>/Database
        self._copy_templates(slot / "Database")

        # 3) Open via DBManager (attaches templates, creates views, migrations)
        dbm = DBManager(slot)
        conn = dbm.open()

        # 4) Seed initial player + hangar + cargo
        starter_ship_id = self._choose_starter_ship(conn)
        hp, energy, fuel = self._initial_stats_for(conn, starter_ship_id)
        credits = 2000

        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO player
                    (id, name, credits, ship_id, location_type, location_id, hp, energy, fuel)
                VALUES (1,?,?,?,?,?,?,?,?)
            """, (player_name, credits, starter_ship_id, "station", start_station_id, hp, energy, fuel))
            conn.execute("INSERT OR IGNORE INTO hangar_ships(ship_id, acquired_price, is_active) VALUES (?,?,1)",
                         (starter_ship_id, 0))

            # initialize cargo rows for all items
            for row in conn.execute("SELECT id FROM items;").fetchall():
                conn.execute("INSERT OR IGNORE INTO player_cargo(item_id, quantity) VALUES (?,0)", (row["id"],))

        # track current slot dir on context for Save As
        self.ctx.current_slot = slot

        # 5) hand control to the app
        self.ctx.conn = conn
        self.on_world_opened(save_name, conn)

    def _open_save(self, save_name: str) -> None:
        slot = self._save_dir(save_name)
        if not (slot / "save.db").exists():
            messagebox.showerror("Load Game", "Missing save.db in this save.")
            return
        dbm = DBManager(slot)
        conn = dbm.open()

        # track current slot
        self.ctx.current_slot = slot

        self.ctx.conn = conn
        self.on_world_opened(save_name, conn)

    # ----------------- utilities -----------------

    def _stations_from_templates(self) -> List[StartStation]:
        """
        Read starting stations from templates/world.db.
        If 'has_hangar' column doesn't exist, assume 1 (true).
        """
        wdb = self.templates_root / "world.db"
        if not wdb.exists():
            return []

        conn = sqlite3.connect(str(wdb))
        conn.row_factory = sqlite3.Row
        stations: List[StartStation] = []
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(stations);").fetchall()]
            has_hangar_col = "has_hangar" in cols
            if has_hangar_col:
                q = """
                SELECT s.id, s.name AS station, p.name AS planet, sys.name AS system, s.has_hangar
                FROM stations s
                JOIN planets p ON s.planet_id=p.id
                JOIN systems sys ON p.system_id=sys.id
                """
            else:
                q = """
                SELECT s.id, s.name AS station, p.name AS planet, sys.name AS system, 1 AS has_hangar
                FROM stations s
                JOIN planets p ON s.planet_id=p.id
                JOIN systems sys ON p.system_id=sys.id
                """
            for row in conn.execute(q).fetchall():
                label = f"{row['station']} — {row['planet']} ({row['system']})"
                stations.append(StartStation(int(row["id"]), label, int(row["has_hangar"])))
        finally:
            conn.close()

        # Only stations with hangar
        return [s for s in stations if s.has_hangar]

    def _copy_templates(self, dst_dir: Path) -> None:
        if not self.templates_root.exists():
            raise RuntimeError(f"Missing templates directory: {self.templates_root}")
        for _schema, fname in SCHEMA_FILES.items():
            src = self.templates_root / fname
            if not src.exists():
                raise RuntimeError(f"Missing template DB: {src}")
            shutil.copy2(src, dst_dir / fname)

    def _choose_starter_ship(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT id FROM ships ORDER BY base_price ASC LIMIT 1;").fetchone()
        return int(row["id"] if row else 1)

    def _initial_stats_for(self, conn: sqlite3.Connection, ship_id: int) -> Tuple[int, int, int]:
        r = conn.execute("""
            SELECT hull AS hp, energy_capacity AS energy, fuel_capacity AS fuel
            FROM ships WHERE id=?;
        """, (ship_id,)).fetchone()
        if not r:
            return (100, 10, 50)
        return (int(r["hp"]), int(r["energy"]), int(r["fuel"]))

    def _list_saves(self) -> List[str]:
        root = self.ctx.save_root
        if not root.exists():
            return []
        return sorted([p.name for p in root.iterdir() if p.is_dir() and (p / "save.db").exists()])

    def _save_dir(self, save_name: str) -> Path:
        return self.ctx.save_root / save_name

    def _current_slot_dir(self) -> Path:
        return getattr(self.ctx, "current_slot", self.ctx.save_root / "_CURRENT_MISSING_")

    def _log(self, category: str, text: str) -> None:
        self.ctx.bus.emit("log", category, text)
