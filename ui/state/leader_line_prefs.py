# /ui/state/leader_line_prefs.py

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QInputDialog

class LeaderLinePrefs:
    def __init__(self, color: str = "#00FF80", width: int = 2, glow: bool = True):
        self.color = QColor(color)
        self.width = int(width)
        self.glow  = bool(glow)

    def apply_to(self, lead) -> None:
        if lead:
            try:
                lead.set_line_style(color=self.color, width=self.width, glow_enabled=self.glow)
            except Exception:
                pass

    # UI helpers wired in the menu
    def pick_color(self, parent) -> None:
        c = QColorDialog.getColor(self.color, parent, "Choose Leader Line Color")
        if c.isValid():
            self.color = c
            self.apply_to(getattr(parent, "lead", None))

    def pick_width(self, parent) -> None:
        w, ok = QInputDialog.getInt(parent, "Set Leader Line Width", "Width (px):", self.width, 1, 12)
        if ok:
            self.width = int(w)
            self.apply_to(getattr(parent, "lead", None))

    def set_glow(self, enabled: bool, parent) -> None:
        self.glow = bool(enabled)
        self.apply_to(getattr(parent, "lead", None))
