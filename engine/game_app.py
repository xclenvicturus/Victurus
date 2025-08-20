from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Callable, Any, cast

import tkinter as tk
from tkinter import messagebox

# Core infra
from .settings import Settings, WindowStateManager
from .event_bus import EventBus
from .app_context import AppContext

# Modules wired from GameApp
from .save_manager import SaveManager
from .ui.ui_builder import UIBuilder
from .ui.window_manager import WindowTogglers
from .ui.actions_panel import ActionsPanel


class GameApp:
    """Composition root for Victurus."""

    def __init__(self, save_root_dir: str, slot_name: Optional[str] = None) -> None:
        # --- Tk root ---
        self.root = tk.Tk()
        self.root.title("Victurus")

        # --- Settings & window-state manager ---
        self.settings = Settings()
        self.wsm = WindowStateManager(self.settings)

        # --- Event bus ---
        self.bus = EventBus()

        # --- App context (be tolerant of different __init__ signatures) ---
        self.ctx = self._make_app_context(Path(save_root_dir))
        # Ensure expected context attributes exist
        if not hasattr(self.ctx, "windows"):
            self.ctx.windows = {}  # type: ignore[attr-defined]
        if not hasattr(self.ctx, "ask_yes_no"):
            self.ctx.ask_yes_no = self._ask_yes_no  # type: ignore[attr-defined]

        # --- Services & UI modules ---
        self.save_manager = self._make_save_manager(self.ctx)
        self.togglers = WindowTogglers(self.ctx)
        self.ui = UIBuilder(self.ctx)
        self.actions_panel = ActionsPanel(self.ctx)

        # --- Build UI ---
        self.ui.restore_main_geometry()
        self._build_menu()
        self.actions_panel.refresh()

    # -------------------------------------------------------------------------
    # Context & services
    # -------------------------------------------------------------------------
    def _make_app_context(self, save_root: Path) -> AppContext:
        """Construct AppContext, attempting a few common signatures."""
        # Try (root, settings, wsm, bus, save_root, ask_yes_no)
        try:
            return AppContext(self.root, self.settings, self.wsm, self.bus, save_root, self._ask_yes_no)  # type: ignore[arg-type]
        except TypeError:
            pass
        # Try (root, settings, wsm, bus)
        try:
            ctx = AppContext(self.root, self.settings, self.wsm, self.bus)  # type: ignore[arg-type]
            # attach save_root & ask_yes_no if not present
            ctx.save_root = save_root  # type: ignore[attr-defined]
            ctx.ask_yes_no = self._ask_yes_no  # type: ignore[attr-defined]
            return ctx
        except TypeError:
            pass
        # Try (conn, root, settings, wsm, bus, save_root, ask_yes_no)
        try:
            return AppContext(None, self.root, self.settings, self.wsm, self.bus, save_root, self._ask_yes_no)  # type: ignore[arg-type]
        except TypeError:
            # Last-resort minimal shim
            ctx = AppContext()  # type: ignore[call-arg]
            ctx.root = self.root  # type: ignore[attr-defined]
            ctx.settings = self.settings  # type: ignore[attr-defined]
            ctx.wsm = self.wsm  # type: ignore[attr-defined]
            ctx.bus = self.bus  # type: ignore[attr-defined]
            ctx.conn = None  # type: ignore[attr-defined]
            ctx.save_root = save_root  # type: ignore[attr-defined]
            ctx.ask_yes_no = self._ask_yes_no  # type: ignore[attr-defined]
            return ctx

    def _make_save_manager(self, ctx: AppContext) -> SaveManager:
        """Construct SaveManager, adapting to constructor variants."""
        try:
            return SaveManager(ctx, on_world_opened=self._on_world_opened)  # type: ignore[arg-type]
        except TypeError:
            # Fallback to (ctx,)
            sm = SaveManager(ctx)  # type: ignore[call-arg]
            # If it exposes a callback setter, wire it
            if hasattr(sm, "set_on_world_opened"):
                sm.set_on_world_opened(self._on_world_opened)  # type: ignore[attr-defined]
            return sm

    # -------------------------------------------------------------------------
    # Menu / commands
    # -------------------------------------------------------------------------
    def _build_menu(self) -> None:
        togglers: Dict[str, Callable[[], None]] = {
            "Map": self.togglers.toggle_map,
            "Status": self.togglers.toggle_status,
            "Player": self.togglers.toggle_player,
            "Cargo": self.togglers.toggle_cargo,
            "Hangar": self.togglers.toggle_hangar,
            "Market": self.togglers.toggle_market,
            "Quests": self.togglers.toggle_quests,
        }
        self.ui.build_menu(
            new_game=self._new_game,
            save_game=self._save_game,
            save_game_as=self._save_game_as,
            load_game=self._load_game,
            delete_game=self._delete_game,
            togglers=togglers,
            bring_all_to_front=self.togglers.bring_all_to_front,
            toggle_topmost_menu=self._toggle_topmost_menu,
        )

    def _new_game(self) -> None:
        if hasattr(self.save_manager, "do_clone"):
            getattr(self.save_manager, "do_clone")()  # type: ignore[misc]
        elif hasattr(self.save_manager, "new_game"):
            getattr(self.save_manager, "new_game")()
        else:
            messagebox.showinfo("New Game", "New game not available in this build.")

    def _save_game(self) -> None:
        if hasattr(self.save_manager, "save"):
            getattr(self.save_manager, "save")()
        else:
            messagebox.showinfo("Save", "Save not available in this build.")

    def _save_game_as(self) -> None:
        if hasattr(self.save_manager, "save_as"):
            getattr(self.save_manager, "save_as")()
        else:
            messagebox.showinfo("Save As", "Save As not available in this build.")

    def _load_game(self) -> None:
        if hasattr(self.save_manager, "do_open"):
            getattr(self.save_manager, "do_open")()
        elif hasattr(self.save_manager, "open"):
            getattr(self.save_manager, "open")()
        else:
            messagebox.showinfo("Open", "Open not available in this build.")

    def _delete_game(self) -> None:
        if hasattr(self.save_manager, "do_delete"):
            getattr(self.save_manager, "do_delete")()
        elif hasattr(self.save_manager, "delete"):
            getattr(self.save_manager, "delete")()
        else:
            messagebox.showinfo("Delete", "Delete not available in this build.")

    def _toggle_topmost_menu(self, wid: str) -> None:
        # Use Any at the call site to satisfy differing stubs/signatures across builds.
        settings_any = cast(Any, self.settings)
        meta = settings_any.get_window(wid)
        new_val = not bool(meta.get("always_on_top", False))
        # Some builds accept (wid, payload); some accept a single dict. Try both.
        try:
            settings_any.set_window(wid, {"always_on_top": new_val})
        except TypeError:
            settings_any.set_window({"id": wid, "always_on_top": new_val})
        # Update the "dot" in the Window menu entry
        self.ui.update_topmost_dot(wid, "•" if new_val else "")

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------
    def _on_world_opened(self, conn: sqlite3.Connection, save_name: str) -> None:
        # Expose connection on context for windows/controllers
        self.ctx.conn = conn  # type: ignore[attr-defined]
        self.bus.emit("log", "system", f"Save loaded: {save_name}")
        # Refresh panels/windows that depend on world
        self.actions_panel.refresh()

    def _ask_yes_no(self, title: str, question: str) -> bool:
        return messagebox.askyesno(title, question)

    # -------------------------------------------------------------------------
    # Run loop
    # -------------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


__all__ = ["GameApp"]
