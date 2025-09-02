# /ui/maps/tabs.py

"""
ui/maps/tabs.py
This module only owns the two map views.

MapTabs:
- A QTabWidget with:
    • "Galaxy"  -> GalaxyMapWidget
    • "System"  -> SystemMapWidget
- Convenience methods to center/refresh.
- Auto-loads SystemMapWidget for the player's current system.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import QTimer

from data import db
from ui.maps.galaxy import GalaxyMapWidget
from ui.maps.system import SystemMapWidget
from game_controller.sim_loop import universe_sim


class MapTabs(QWidget):
    """Contains only the map tabs. No side panels, no status, no travel."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.galaxy = GalaxyMapWidget(self.tabs)
        self.system = SystemMapWidget(self.tabs)

        self.tabs.addTab(self.galaxy, "Galaxy")
        self.tabs.addTab(self.system, "System")

        lay.addWidget(self.tabs, 1)

        # Ensure system view is loaded for the current player's system on construction
        self._ensure_system_loaded_from_player()

        # Keep simulator in sync with which map is visible
        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
            # Initialize visible-system state for the default tab
            self._on_tab_changed(self.tabs.currentIndex())
        except Exception:
            pass

    def _on_tab_changed(self, idx: int) -> None:
        """Set simulator's visible system: None on Galaxy so all systems tick;
        current system on System tab."""
        try:
            if idx == self.tabs.indexOf(self.galaxy):
                universe_sim.set_visible_system(None)
            elif idx == self.tabs.indexOf(self.system):
                sid = getattr(self.system, "_system_id", None)
                if sid is not None:
                    universe_sim.set_visible_system(int(sid))
        except Exception:
            pass

    # ---- Simple helpers the main window can call ----
    def setCurrentIndex(self, idx: int) -> None:
        try:
            idx = max(0, min(self.tabs.count() - 1, int(idx)))
            self.tabs.setCurrentIndex(idx)
        except Exception:
            pass

    def show_galaxy(self) -> None:
        self.setCurrentIndex(self.tabs.indexOf(self.galaxy))

    def show_system(self) -> None:
        self.setCurrentIndex(self.tabs.indexOf(self.system))

    def _ensure_system_loaded_from_player(self) -> None:
        """Load the SystemMapWidget with the player's current system if needed."""
        try:
            p = db.get_player_full() or {}
            sys_id = int(p.get("current_player_system_id") or 0)
            if sys_id and getattr(self.system, "_system_id", None) != sys_id:
                self.system.load(sys_id)
        except Exception:
            pass

    def center_galaxy_on_system(self, system_id: int) -> None:
        try:
            self.galaxy.center_on_system(int(system_id))
        except Exception:
            pass

    def center_system_on_system(self, system_id: int) -> None:
        try:
            if getattr(self.system, "_system_id", None) != int(system_id):
                self.system.load(int(system_id))
            # If the user is actively interacting with the map, the System
            # widget may be suppressing external centering. Defer the center
            # call slightly so the user's zoom/pan isn't overridden.
            try:
                def _deferred_center_sys(sid: int) -> None:
                    try:
                        sys_widget = getattr(self, "system", None)
                        if sys_widget is not None and hasattr(sys_widget, "is_suppressing_auto_center") and sys_widget.is_suppressing_auto_center():
                            # retry shortly until suppression clears
                            QTimer.singleShot(100, lambda: _deferred_center_sys(sid))
                            return
                        # perform the real center
                        try:
                            self.system.center_on_system(int(sid), force=True)
                        except Exception:
                            pass
                    except Exception:
                        try:
                            self.system.center_on_system(int(sid))
                        except Exception:
                            pass

                _deferred_center_sys(int(system_id))
            except Exception:
                try:
                    self.system.center_on_system(int(system_id))
                except Exception:
                    pass
        except Exception:
            pass

    def center_system_on_location(self, location_id: int) -> None:
        try:
            # IMPORTANT: do NOT reload to player's system here.
            # We are already viewing a specific system in the System view; just center there.
            # Call the System widget immediately (force) so the System list behaves like the
            # Galaxy list which centers immediately on user clicks.
            try:
                self.system.center_on_location(int(location_id), force=True)
            except Exception:
                try:
                    self.system.center_on_location(int(location_id))
                except Exception:
                    pass
        except Exception:
            pass

    def reload_all(self) -> None:
        """Reloads all map data, ensuring the system view is synchronized with the player's current system."""
        try:
            self.galaxy.load()
        except Exception:
            pass

        # Always ensure the system map is showing the player's actual current system from the database.
        # This corrects the bug where the view would not update after a new game or load.
        try:
            self._ensure_system_loaded_from_player()
        except Exception:
            pass
