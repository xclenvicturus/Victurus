from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast, Callable

import tkinter as tk
from tkinter import messagebox

# Core infra
from .settings import Settings, WindowStateManager
from .event_bus import EventBus
from .app_context import AppContext

# Modules wired from GameApp
from .save_manager import SaveManager
from .ui_builder import UIBuilder
from .window_togglers import WindowTogglers
from .app_events import AppEvents
from .actions_panel import ActionsPanel
from .cheats import CheatService

# Controllers are built AFTER a DB connection exists
from .controllers.travel_controller import TravelController
from .controllers.quest_controller import QuestController
from .controllers.combat_controller import CombatController


class GameApp:
    """
    Thin composition root:
      - Creates Tk root, Settings/WindowStateManager, EventBus
      - Builds AppContext (signature-adaptive to your local definition)
      - Wires SaveManager/UI/Window togglers/Actions panel/App events/Cheats
      - Builds controllers once a save is opened
    """

    def __init__(self, save_root_dir: str, slot_name: str | None = None):
        # --- Tk root ---
        self.root = tk.Tk()

        # --- Settings / WSM (be tolerant to different Settings signatures) ---
        self.settings = self._make_settings()
        self.wsm = WindowStateManager(self.settings)
        self.bus = EventBus()

        # --- AppContext (signatures vary across your snapshots; try several) ---
        self.ctx = self._make_app_context(save_root_dir)

        # Ensure save root
        self.ctx.save_root.mkdir(parents=True, exist_ok=True)

        # --- Services & UI modules ---
        self.save_manager = SaveManager(self.ctx, on_world_opened=self._on_world_opened)
        self.togglers = WindowTogglers(self.ctx)
        self.actions_panel = ActionsPanel(self.ctx)
        self.cheats = CheatService(self.ctx)
        self.ui = UIBuilder(self.ctx)
        self.events = AppEvents(self.ctx, self.actions_panel, self.togglers)

        # --- UI & hotkeys ---
        self.ui.restore_main_geometry()
        self._build_ui()
        self.root.bind("<Configure>", self.ui.persist_main_geometry)

        # Idle message
        self.bus.emit("log", "system", "No game loaded. Use Game → New Game… or Load Game…")

    # -------------------------------------------------------------------------
    # Helpers to tolerate signature drift (Pylance-friendly with call-arg ignores)
    # -------------------------------------------------------------------------

    def _make_settings(self) -> Settings:
        """
        Your local `Settings` sometimes takes (root, ask_yes_no), sometimes no kwargs.
        Try robustly; prefer no-arg first because you reported 'No parameter named "root"'.
        """
        try:
            return Settings()  # most likely in your tree
        except TypeError:
            # Fallback if your Settings requires context
            return cast(Settings, Settings(root=self.root, ask_yes_no=self._ask_yes_no))  # type: ignore[call-arg]

    def _make_app_context(self, save_root_dir: str) -> AppContext:
        """
        Your local `AppContext.__init__` varied across versions:
          - AppContext(root, settings, wsm, bus, save_root, ask_yes_no)
          - AppContext(conn, root, settings, wsm, bus, save_root, ask_yes_no)  (conn may be None)
          - AppContext(root, settings, wsm, bus)                               (minimal)
        Try a few in order; keep Pylance happy with call-arg ignores on attempted signatures.
        """
        save_root = Path(save_root_dir)
        ctx_any: Any = None
        # Preferred (most complete) signature
        try:
            ctx_any = AppContext(self.root, self.settings, self.wsm, self.bus, save_root, self._ask_yes_no)  # type: ignore[call-arg]
            return cast(AppContext, ctx_any)
        except TypeError:
            pass
        # Variant with conn first
        try:
            ctx_any = AppContext(None, self.root, self.settings, self.wsm, self.bus, save_root, self._ask_yes_no)  # type: ignore[call-arg]
            return cast(AppContext, ctx_any)
        except TypeError:
            pass
        # Minimal fallback
        ctx_any = AppContext(self.root, self.settings, self.wsm, self.bus)  # type: ignore[call-arg]
        # Attach what we can if minimal constructor lacks fields
        try:
            ctx_any.save_root = save_root
        except Exception:
            pass
        try:
            ctx_any.ask_yes_no = self._ask_yes_no
        except Exception:
            pass
        return cast(AppContext, ctx_any)

    # -------------------------------------------------------------------------
    # UI composition
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.ui.build_menu(
            new_game=self.save_manager.open_new_game_dialog,
            save_game=self.save_manager.menu_save,
            save_game_as=self.save_manager.menu_save_as,
            load_game=self.save_manager.menu_open_save_dialog,
            delete_game=self.save_manager.menu_delete_save,
            togglers={
                "galaxy_map": self.togglers.toggle_map,
                "status": self.togglers.toggle_status,
                "cargo": self.togglers.toggle_cargo,
                "quests": self.togglers.toggle_quests,
                "hangar": self.togglers.toggle_hangar,
                "market": self.togglers.toggle_market,
                "player": self.togglers.toggle_player,
            },
            bring_all_to_front=self.togglers.bring_all_to_front,
            toggle_topmost_menu=self._toggle_topmost_menu,
            cheat_credits=self.cheats.give_credits,
            cheat_item=self.cheats.give_item,
            cheat_ship=self.cheats.give_ship,
            feature_toggle={
                "autorepair": lambda: self.actions_panel.toggle_feature("autorepair"),
                "autofuel": lambda: self.actions_panel.toggle_feature("autofuel"),
                "autorecharge": lambda: self.actions_panel.toggle_feature("autorecharge"),
            },
        )
        self.ui.build_layout()
        self.ui.wire_talk_button(self.actions_panel.talk_to_selected_npc)
        self.ui.install_log_context_menu()
        self.ui.bind_hotkeys(
            {
                "galaxy_map": self.togglers.toggle_map,
                "status": self.togglers.toggle_status,
                "cargo": self.togglers.toggle_cargo,
                "quests": self.togglers.toggle_quests,
                "hangar": self.togglers.toggle_hangar,
            }
        )

    # -------------------------------------------------------------------------
    # Callbacks / utilities
    # -------------------------------------------------------------------------

    def _ask_yes_no(self, title: str, question: str) -> bool:
        return messagebox.askyesno(title, question)

    def _toggle_topmost_menu(self, wid: str) -> None:
        meta = self.settings.get_window(wid)
        new_val = not bool(meta.get("always_on_top", False))
        self.settings.set_window(wid, always_on_top=new_val)
        ui_obj = self.ctx.windows.get(wid)
        w = getattr(ui_obj, "win", None)
        if w:
            self.wsm.set_topmost(w, wid, new_val)
        dot = "●" if new_val else "○"
        self.ui.update_topmost_dot(wid, dot)

    # -------------------------------------------------------------------------
    # Controller factory that adapts to multiple __init__ signatures
    # -------------------------------------------------------------------------

    def _build_controller(self, cls: type, conn: sqlite3.Connection, name: str) -> Any:
        """
        Try several common signatures for controllers:
          1) (conn, bus)
          2) (root, conn, bus)
          3) (conn, bus, ask_yes_no)
          4) (root, conn, bus, ask_yes_no)
        """
        attempts: list[Callable[[], Any]] = [
            lambda: cls(conn, self.bus),  # type: ignore[misc]
            lambda: cls(self.root, conn, self.bus),  # type: ignore[misc]
            lambda: cls(conn, self.bus, self._ask_yes_no),  # type: ignore[misc]
            lambda: cls(self.root, conn, self.bus, self._ask_yes_no),  # type: ignore[misc]
        ]
        last_err: Exception | None = None
        for maker in attempts:
            try:
                return maker()
            except TypeError as e:
                last_err = e
                continue
        # If we reach here, raise a clearer message
        raise TypeError(
            f"{name}.__init__ signature not recognized; tried (conn,bus), (root,conn,bus), "
            f"(conn,bus,ask_yes_no), (root,conn,bus,ask_yes_no). Last error: {last_err}"
        )

    # -------------------------------------------------------------------------
    # Post-load bootstrap (controllers, first refresh, ticking)
    # -------------------------------------------------------------------------

    def _on_world_opened(self, save_name: str, conn: sqlite3.Connection) -> None:
        """
        Called by SaveManager once a save DB has been opened/reset and content loaded.
        Build controllers now that we have a real connection.
        """
        self.ctx.travel = self._build_controller(TravelController, conn, "TravelController")  # type: ignore[attr-defined]
        self.ctx.qc = self._build_controller(QuestController, conn, "QuestController")  # type: ignore[attr-defined]
        self.ctx.combat = self._build_controller(CombatController, conn, "CombatController")  # type: ignore[attr-defined]

        # Initial UI refresh & schedule economy ticks
        self.bus.emit("log", "system", f"Save loaded: {save_name}")
        self.actions_panel.refresh()
        self.actions_panel.schedule_tick()

    # -------------------------------------------------------------------------
    # Run loop
    # -------------------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()


__all__ = ["GameApp"]
