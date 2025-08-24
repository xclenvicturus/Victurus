# /ui/maps/tabs.py

"""
ui/maps/tabs.py
This module only owns the two map views.

MapTabs:
- A QTabWidget with:
    • "Galaxy"  -> GalaxyMapWidget
    • "System"  -> SolarMapWidget
- Convenience methods to center/refresh.
- Auto-loads SolarMapWidget for the player's current system.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from data import db
from ui.maps.galaxy import GalaxyMapWidget
from ui.maps.solar import SolarMapWidget


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
        self.solar = SolarMapWidget(self.tabs)

        self.tabs.addTab(self.galaxy, "Galaxy")
        self.tabs.addTab(self.solar, "System")

        lay.addWidget(self.tabs, 1)

        # Ensure solar is loaded for the current player's system on construction
        self._ensure_solar_loaded_from_player()

    # ---- Simple helpers the main window can call ----
    def setCurrentIndex(self, idx: int) -> None:
        self.tabs.setCurrentIndex(max(0, min(1, idx)))

    def show_galaxy(self) -> None:
        self.setCurrentIndex(0)

    def show_solar(self) -> None:
        self.setCurrentIndex(1)

    def _ensure_solar_loaded_from_player(self) -> None:
        """Load the SolarMapWidget with the player's current system if needed."""
        try:
            p = db.get_player_full() or {}
            sys_id = int(p.get("current_player_system_id") or 0)
            if sys_id and getattr(self.solar, "_system_id", None) != sys_id:
                self.solar.load(sys_id)
        except Exception:
            pass

    def center_galaxy_on_system(self, system_id: int) -> None:
        try:
            self.galaxy.center_on_system(int(system_id))
        except Exception:
            pass

    def center_solar_on_system(self, system_id: int) -> None:
        try:
            if getattr(self.solar, "_system_id", None) != int(system_id):
                self.solar.load(int(system_id))
            self.solar.center_on_system(int(system_id))
        except Exception:
            pass

    def center_solar_on_location(self, location_id: int) -> None:
        try:
            # Ensure solar is loaded for current player context
            self._ensure_solar_loaded_from_player()
            self.solar.center_on_location(int(location_id))
        except Exception:
            pass

    def reload_all(self) -> None:
        """Reloads all map data, ensuring the solar view is synchronized with the player's current system."""
        try:
            self.galaxy.load()
        except Exception:
            pass
        
        # Always ensure the solar map is showing the player's actual current system from the database.
        # This corrects the bug where the view would not update after a new game or load.
        try:
            self._ensure_solar_loaded_from_player()
        except Exception:
            pass