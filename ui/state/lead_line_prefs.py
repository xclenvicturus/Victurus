# /ui/state/leader_line_prefs.py

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QInputDialog


class GalaxyLeaderLinePrefs:
    """
    Preferences for the Galaxy list → Galaxy map leader line.
    Applies only to the parent's `lead_galaxy` controller.
    """
    def __init__(self, color: str = "#00FF80", width: int = 2, glow: bool = True):
        self.color = QColor(color)
        self.width = int(width)
        self.glow = bool(glow)

    def apply_to(self, lead) -> None:
        if lead:
            try:
                lead.set_line_style(color=self.color, width=self.width, glow_enabled=self.glow)
            except Exception:
                pass

    def apply_to_parent(self, parent) -> None:
        # Apply ONLY to the galaxy leader-line controller
        lead = getattr(parent, "lead_galaxy", None)
        if lead:
            try:
                lead.set_line_style(color=self.color, width=self.width, glow_enabled=self.glow)
            except Exception:
                pass

    def pick_color(self, parent) -> None:
        c = QColorDialog.getColor(self.color, parent, "Choose Leader Line Color")
        if c.isValid():
            self.color = c
            self.apply_to_parent(parent)

    def pick_width(self, parent) -> None:
        w, ok = QInputDialog.getInt(parent, "Set Leader Line Width", "Width (px):", self.width, 1, 12)
        if ok:
            self.width = int(w)
            self.apply_to_parent(parent)

    def set_glow(self, enabled: bool, parent) -> None:
        self.glow = bool(enabled)
        self.apply_to_parent(parent)


class SystemLeaderLinePrefs:
    """
    Preferences for the System list → System/Solar map leader line.
    Applies only to the parent's `lead` (system) controller.
    """
    def __init__(self, color: str = "#00FF80", width: int = 2, glow: bool = True):
        self.color = QColor(color)
        self.width = int(width)
        self.glow = bool(glow)

    def apply_to(self, lead) -> None:
        if lead:
            try:
                lead.set_line_style(color=self.color, width=self.width, glow_enabled=self.glow)
            except Exception:
                pass

    def apply_to_parent(self, parent) -> None:
        # Apply ONLY to the system/solar leader-line controller
        lead = getattr(parent, "lead", None)
        if lead:
            try:
                lead.set_line_style(color=self.color, width=self.width, glow_enabled=self.glow)
            except Exception:
                pass

    def pick_color(self, parent) -> None:
        c = QColorDialog.getColor(self.color, parent, "Choose Leader Line Color")
        if c.isValid():
            self.color = c
            self.apply_to_parent(parent)

    def pick_width(self, parent) -> None:
        w, ok = QInputDialog.getInt(parent, "Set Leader Line Width", "Width (px):", self.width, 1, 12)
        if ok:
            self.width = int(w)
            self.apply_to_parent(parent)

    def set_glow(self, enabled: bool, parent) -> None:
        self.glow = bool(enabled)
        self.apply_to_parent(parent)
