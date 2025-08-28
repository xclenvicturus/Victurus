# /ui/controllers/map_actions.py

from __future__ import annotations

from typing import Callable, Optional, Tuple, cast

from PySide6.QtWidgets import QWidget, QTabWidget

from ..maps.tabs import MapTabs


class MapActions:
    """
    High-level actions invoked by the LocationList:
      - focus (single-click)
      - open (double-click in Galaxy switches to System)
      - travel_here (context menu)
    """

    def __init__(self, tabs: MapTabs, begin_travel_cb: Optional[Callable[[str, int], None]] = None) -> None:
        self._tabs = tabs
        self._begin_travel_cb = begin_travel_cb

    # -------- helpers --------

    def _tab_widget(self) -> Optional[QTabWidget]:
        tw = getattr(self._tabs, "tabs", None)
        return tw if isinstance(tw, QTabWidget) else None

    def _using_galaxy(self) -> bool:
        tw = self._tab_widget()
        if tw is not None:
            try:
                return tw.currentIndex() == 0
            except Exception:
                pass
        return True

    def _solar(self):
        return getattr(self._tabs, "solar", None)

    def _resolve_virtual(self, entity_id: int) -> Optional[Tuple[str, int]]:
        """
        Ask the Solar widget to resolve virtual ids (moons or star).
        Returns ('loc', location_id) or ('star', system_id) or None.
        """
        solar = self._solar()
        resolver = getattr(solar, "resolve_entity", None)
        if callable(resolver):
            try:
                typed_resolver = cast(Callable[[int], Optional[Tuple[str, int]]], resolver)
                return typed_resolver(int(entity_id))
            except Exception:
                return None
        return None

    # -------- public API --------

    def focus(self, entity_id: int) -> None:
        if self._using_galaxy():
            center_sys = getattr(self._tabs, "center_galaxy_on_system", None)
            if callable(center_sys):
                try:
                    # entity_id is -system_id in the lists
                    center_sys(int(-entity_id) if entity_id < 0 else int(entity_id))
                except Exception:
                    pass
        else:
            # We can center on the virtual item directly (moons are real items in scene)
            if entity_id < 0:
                # Try resolver first; fall back to sentinel semantics (star/system)
                vr = self._resolve_virtual(entity_id)
                if vr and vr[0] == "star":
                    center_sys = getattr(self._tabs, "center_solar_on_system", None)
                    if callable(center_sys):
                        try:
                            center_sys(int(vr[1]))
                            return
                        except Exception:
                            pass
                else:
                    # Fallback: negative id encodes system id of the star
                    center_sys = getattr(self._tabs, "center_solar_on_system", None)
                    if callable(center_sys):
                        try:
                            center_sys(int(-entity_id))
                            return
                        except Exception:
                            pass

            center_loc = getattr(self._tabs, "center_solar_on_location", None)
            if callable(center_loc):
                try:
                    center_loc(int(entity_id))
                except Exception:
                    pass

    def open(self, entity_id: int) -> None:
        """
        In Galaxy: synchronously load the chosen system into the Solar view,
        then switch to the Solar tab, then center on it.
        In System: same as focus.
        """
        if self._using_galaxy():
            try:
                # entity_id is -system_id in the lists
                sys_id = int(-entity_id) if entity_id < 0 else int(entity_id)
            except Exception:
                return

            # 1) Load Solar with the target system *before* switching tabs
            solar = self._solar()
            load = getattr(solar, "load", None)
            if callable(load):
                try:
                    load(sys_id)
                except Exception:
                    pass

            # 2) Switch to Solar tab
            tw = self._tab_widget()
            if tw is not None:
                try:
                    tw.setCurrentIndex(1)  # 0=Galaxy, 1=Solar
                except Exception:
                    pass

            # 3) Center on that system
            center_sys = getattr(self._tabs, "center_solar_on_system", None)
            if callable(center_sys):
                try:
                    center_sys(sys_id)
                except Exception:
                    pass
        else:
            self.focus(entity_id)

    def travel_here(self, entity_id: int) -> None:
        """Context menu action."""
        if self._begin_travel_cb is None:
            return

        if self._using_galaxy():
            # entity_id is -system_id in the lists
            try:
                sys_id = int(-entity_id) if entity_id < 0 else int(entity_id)
            except Exception:
                return
            self._begin_travel_cb("star", sys_id)
            return

        # System view: support star sentinel and virtual ids
        if entity_id < 0:
            vr = self._resolve_virtual(entity_id)
            if vr:
                kind, ident = vr
                if kind == "star":
                    self._begin_travel_cb("star", int(ident))
                    return
                if kind == "loc":
                    self._begin_travel_cb("loc", int(ident))
                    return
            # Fallback if resolver not present: negative means system/star
            try:
                self._begin_travel_cb("star", int(-entity_id))
            except Exception:
                pass
            return

        # Otherwise it's a real location id
        try:
            self._begin_travel_cb("loc", int(entity_id))
        except Exception:
            pass
