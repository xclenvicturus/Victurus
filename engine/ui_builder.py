from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Any

from .app_context import AppContext


class UIBuilder:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._view_menu_atop: Optional[tk.Menu] = None  # set in build_menu()

    # -------- Main menu / layout --------

    def build_menu(
        self,
        new_game: Callable[[], None],
        save_game: Callable[[], None],
        save_game_as: Callable[[], None],
        load_game: Callable[[], None],
        delete_game: Callable[[], None],
        togglers: dict[str, Callable[[], None]],
        bring_all_to_front: Callable[[], None],
        toggle_topmost_menu: Callable[[str], None],
        cheat_credits: Callable[[], None],
        cheat_item: Callable[[], None],
        cheat_ship: Callable[[], None],
        feature_toggle: dict[str, Callable[[], None]],
    ) -> None:
        root = self.ctx.root
        menubar = tk.Menu(root)
        root.config(menu=menubar)

        # Game
        g = tk.Menu(menubar, tearoff=0)
        g.add_command(label="New Game…", command=new_game)
        g.add_separator()
        g.add_command(label="Save Game", command=save_game)
        g.add_command(label="Save Game As…", command=save_game_as)
        g.add_separator()
        g.add_command(label="Load Game…", command=load_game)
        g.add_command(label="Delete Game…", command=delete_game)
        g.add_separator()
        g.add_command(label="Exit", command=root.destroy)
        menubar.add_cascade(label="Game", menu=g)

        # View
        v = tk.Menu(menubar, tearoff=0)
        v.add_command(label="Galaxy Map (M)", command=togglers["galaxy_map"])
        v.add_command(label="Ship Status (S)", command=togglers["status"])
        v.add_command(label="Cargo (C)", command=togglers["cargo"])
        v.add_command(label="Quests (Q)", command=togglers["quests"])
        v.add_command(label="Ship Dealer / Hangar (H)", command=togglers["hangar"])
        v.add_command(label="Market", command=togglers["market"])
        v.add_command(label="Player", command=togglers["player"])
        v.add_separator()
        v.add_command(label="Bring All To Front", command=bring_all_to_front)
        atop = tk.Menu(v, tearoff=0)
        for wid, label in (
            ("galaxy_map", "Galaxy Map"),
            ("status", "Ship Status"),
            ("cargo", "Cargo"),
            ("quests", "Quests"),
            ("hangar", "Hangar"),
            ("market", "Market"),
            ("player", "Player"),
        ):
            atop.add_checkbutton(
                label=f"○ {label}",
                command=lambda wid=wid: toggle_topmost_menu(wid),
            )
        v.add_cascade(label="Always on Top", menu=atop)
        self._view_menu_atop = atop
        menubar.add_cascade(label="View", menu=v)

        # Features
        f = tk.Menu(menubar, tearoff=0)
        f.add_checkbutton(label="Auto-Repair", command=feature_toggle["autorepair"])
        f.add_checkbutton(label="Auto-Refuel", command=feature_toggle["autofuel"])
        f.add_checkbutton(label="Auto-Recharge", command=feature_toggle["autorecharge"])
        menubar.add_cascade(label="Features", menu=f)

        # Cheat
        cheat = tk.Menu(menubar, tearoff=0)
        cheat.add_command(label="Give Credits…", command=cheat_credits)
        cheat.add_command(label="Give Item…", command=cheat_item)
        cheat.add_command(label="Give Ship…", command=cheat_ship)
        menubar.add_cascade(label="Cheat", menu=cheat)

        # Help
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="About", command=lambda: messagebox.showinfo("About", "Space RPG"))
        menubar.add_cascade(label="Help", menu=helpm)

    def build_layout(self) -> None:
        root = self.ctx.root

        left = ttk.Frame(root, padding=6)
        left.pack(side="left", fill="both", expand=True)

        # Lazy import avoids circular refs and Pylance confusion
        from .ui.log_panel import LogPanel as _LogPanel  # type: ignore
        log_panel = _LogPanel(left)
        log_panel.pack(fill="both", expand=True)
        self.ctx.log_panel = log_panel

        right = ttk.Frame(root, padding=6, width=420)
        right.pack(side="right", fill="y")

        title = ttk.Label(right, text="Station", font=("Segoe UI", 12, "bold"))
        title.pack(anchor="w")
        self.ctx.station_title = title

        npc = tk.Listbox(right, height=6)
        npc.pack(fill="x", pady=4)
        self.ctx.npc_list = npc

        self._talk_button = ttk.Button(right, text="Talk to NPC")
        self._talk_button.pack(fill="x")

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(right, text="Actions Available").pack(anchor="w")
        actions_panel = ttk.Frame(right)
        actions_panel.pack(fill="x", pady=(4, 6))
        self.ctx.actions_panel = actions_panel

    def wire_talk_button(self, fn) -> None:
        self._talk_button.config(command=fn)

    # -------- Hotkeys & context menu --------

    def bind_hotkeys(self, togglers: dict[str, Callable[[], None]]) -> None:
        r = self.ctx.root
        r.bind("<m>", lambda _e: togglers["galaxy_map"]())
        r.bind("<q>", lambda _e: togglers["quests"]())
        r.bind("<s>", lambda _e: togglers["status"]())
        r.bind("<c>", lambda _e: togglers["cargo"]())
        r.bind("<h>", lambda _e: togglers["hangar"]())

    def install_log_context_menu(self) -> None:
        """Attach a right-click context menu to the log text widgets, if present."""
        menu = tk.Menu(self.ctx.root, tearoff=0)
        menu.add_command(label="Copy All", command=self.ctx.log_panel.copy_all if self.ctx.log_panel else lambda: None)

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        lp = self.ctx.log_panel
        # Prefer a dedicated binder if the widget exposes one (keeps types simple for Pylance)
        if lp and hasattr(lp, "bind_context_menu"):
            try:
                getattr(lp, "bind_context_menu")(show_menu)  # type: ignore[attr-defined]
                return
            except Exception:
                pass

        # Fallback: iterate known attribute if available, using getattr to keep static types loose
        try:
            widgets: Any = getattr(lp, "text_widgets", {})
            for t in getattr(widgets, "values", lambda: [])():
                try:
                    t.bind("<Button-3>", show_menu)
                except Exception:
                    pass
        except Exception:
            # If the structure isn't what we expect, just skip binding rather than typing errors
            pass

    # -------- Geometry persistence --------

    def restore_main_geometry(self) -> None:
        meta = self.ctx.settings.get_window("main")
        geom = meta.get("geometry")
        if geom:
            try:
                self.ctx.root.geometry(geom)
            except Exception:
                pass

    def persist_main_geometry(self, _evt=None) -> None:
        try:
            self.ctx.settings.set_window("main", geometry=self.ctx.root.geometry())
        except Exception:
            pass

    # -------- Always-on-top submenu utilities --------

    def update_topmost_dot(self, wid: str, dot: str) -> None:
        atop = self._view_menu_atop
        if atop is None:
            return
        entries = [
            ("galaxy_map", "Galaxy Map"),
            ("status", "Ship Status"),
            ("cargo", "Cargo"),
            ("quests", "Quests"),
            ("hangar", "Hangar"),
            ("market", "Market"),
            ("player", "Player"),
        ]
        try:
            idx = next(i for i, (id_, _) in enumerate(entries) if id_ == wid)
            _, label = entries[idx]
            atop.entryconfigure(idx, label=f"{dot} {label}")
        except Exception:
            pass
