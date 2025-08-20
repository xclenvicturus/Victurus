from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Optional, Any, cast

from ..app_context import AppContext


class UIBuilder:
    """Main menu and top-level window geometry helpers."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._view_menu: Optional[tk.Menu] = None
        self._window_menu: Optional[tk.Menu] = None
        self._window_idx: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------
    def build_menu(
        self,
        new_game: Callable[[], None],
        save_game: Callable[[], None],
        save_game_as: Callable[[], None],
        load_game: Callable[[], None],
        delete_game: Callable[[], None],
        togglers: Dict[str, Callable[[], None]],
        bring_all_to_front: Callable[[], None],
        toggle_topmost_menu: Callable[[str], None],
    ) -> tk.Menu:
        root = self.ctx.root
        mbar = tk.Menu(root)

        # File
        m_file = tk.Menu(mbar, tearoff=False)
        m_file.add_command(label="New Game", command=new_game)
        m_file.add_command(label="Save", command=save_game)
        m_file.add_command(label="Save As…", command=save_game_as)
        m_file.add_separator()
        m_file.add_command(label="Open…", command=load_game)
        m_file.add_command(label="Delete Save…", command=delete_game)
        m_file.add_separator()
        m_file.add_command(label="Exit", command=root.destroy)
        mbar.add_cascade(label="File", menu=m_file)

        # View
        m_view = tk.Menu(mbar, tearoff=False)
        for name, fn in togglers.items():
            m_view.add_command(label=name, command=fn)
        m_view.add_separator()
        m_view.add_command(label="Bring All to Front", command=bring_all_to_front)
        mbar.add_cascade(label="View", menu=m_view)
        self._view_menu = m_view

        # Window (Always on Top toggles)
        m_win = tk.Menu(mbar, tearoff=False)
        self._window_idx.clear()
        for idx, wid in enumerate(("map", "status", "player", "cargo", "hangar", "market", "quests")):
            # Compute dot; use Any to avoid false positives from differing Settings stubs
            settings_any = cast(Any, self.ctx.settings)
            dot = "•" if bool(settings_any.get_window(wid).get("always_on_top", False)) else ""
            m_win.add_command(label=f"{dot} Always on Top: {wid}", command=lambda w=wid: toggle_topmost_menu(w))
            self._window_idx[wid] = idx
        mbar.add_cascade(label="Window", menu=m_win)
        self._window_menu = m_win

        root.config(menu=mbar)
        return mbar

    def update_topmost_dot(self, wid: str, dot: Optional[str] = None) -> None:
        """
        Refresh the dot prefix for a given window-id entry in the Window menu.
        If `dot` is None, compute it from current Settings.
        """
        if self._window_menu is None:
            return
        idx = self._window_idx.get(wid)
        if idx is None:
            return
        if dot is None:
            settings_any = cast(Any, self.ctx.settings)
            dot = "•" if bool(settings_any.get_window(wid).get("always_on_top", False)) else ""
        label = f"{dot} Always on Top: {wid}"
        try:
            # Update the existing menu item label in place.
            self._window_menu.entryconfigure(idx, label=label)
        except Exception:
            # Ignore UI update errors; menu will refresh on next rebuild.
            pass

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def restore_main_geometry(self) -> None:
        settings_any = cast(Any, self.ctx.settings)
        geom = settings_any.get_window("main").get("geometry")
        if isinstance(geom, str) and geom:
            try:
                self.ctx.root.geometry(geom)
            except Exception:
                pass

    def persist_main_geometry(self, _evt=None) -> None:
        try:
            geom = self.ctx.root.geometry()
            # Accept both (wid, payload) and (payload) styles without tripping static checks
            settings_any = cast(Any, self.ctx.settings)
            try:
                settings_any.set_window("main", {"geometry": geom})
            except TypeError:
                try:
                    settings_any.set_window({"id": "main", "geometry": geom})
                except TypeError:
                    if hasattr(settings_any, "set_main_geometry"):
                        settings_any.set_main_geometry(geom)
        except Exception:
            pass
