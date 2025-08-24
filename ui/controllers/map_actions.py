# /ui/map_actions.py

from __future__ import annotations

from typing import Callable, Optional

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

    # -------- public API --------

    def focus(self, entity_id: int) -> None:
        if self._using_galaxy():
            center_sys = getattr(self._tabs, "center_galaxy_on_system", None)
            if callable(center_sys):
                try:
                    center_sys(int(entity_id))
                except Exception:
                    pass
        else:
            if entity_id < 0:
                # star for the viewed system
                sys_id = int(getattr(self._tabs, "solar", None)._system_id or 0)  # type: ignore[attr-defined]
                center_sys = getattr(self._tabs, "center_solar_on_system", None)
                if callable(center_sys):
                    try:
                        center_sys(sys_id)
                    except Exception:
                        pass
            else:
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
                sys_id = int(entity_id)
            except Exception:
                return

            # 1) Load the Solar widget with the target system *before* tab switch
            solar = getattr(self._tabs, "solar", None)
            load = getattr(solar, "load", None)
            if callable(load):
                try:
                    load(sys_id)
                except Exception:
                    # fall back to MapTabs-level center if load isn't available
                    pass

            # 2) Switch to Solar tab
            tw = self._tab_widget()
            if tw is not None:
                try:
                    tw.setCurrentIndex(1)  # 0=Galaxy, 1=Solar
                except Exception:
                    pass

            # 3) Center on that system (no-ops if already centered)
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
            self._begin_travel_cb("star", int(entity_id))
        else:
            if entity_id < 0:
                self._begin_travel_cb("star", abs(int(entity_id)))
            else:
                self._begin_travel_cb("loc", int(entity_id))

    # -------- internals --------

    def _tab_widget(self) -> Optional[QTabWidget]:
        """Return the inner QTabWidget from MapTabs if present and typed."""
        tw = getattr(self._tabs, "tabs", None)
        return tw if isinstance(tw, QTabWidget) else None

    def _using_galaxy(self) -> bool:
        tw = self._tab_widget()
        if tw is not None:
            try:
                return tw.currentIndex() == 0
            except Exception:
                pass
        # default to galaxy if uncertain
        return True
