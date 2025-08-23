from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase

from game import player_status


class TextGauge(QLabel):
    def __init__(self, total_chars: int = 28, parent=None) -> None:
        super().__init__(parent)
        self.total_chars = total_chars
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.setFont(mono_font)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_values(self, value: int, maximum: int) -> None:
        maximum = max(1, int(maximum))
        value = max(0, min(int(value), maximum))
        fill_chars = int(round((value / maximum) * self.total_chars))
        bar = "|" * fill_chars + " " * (self.total_chars - fill_chars)
        text = f"{value}/{maximum}"
        start = (self.total_chars - len(text)) // 2
        bar_list = list(bar)
        for i, char in enumerate(text):
            if start + i < self.total_chars:
                bar_list[start + i] = char
        self.setText(f"({ ''.join(bar_list) })")


class StatusSheet(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusSheet")
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel("Commander Status")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(self.lbl_title)

        self.lbl_player = QLabel("Name: —")
        self.lbl_location = QLabel("Location: —")
        self.lbl_credits = QLabel("Credits: —")
        layout.addWidget(self.lbl_player)
        layout.addWidget(self.lbl_location)
        layout.addWidget(self.lbl_credits)

        self.lbl_ship = QLabel("Active Ship: —")
        self.lbl_ship_status = QLabel("Ship Status: —")
        layout.addWidget(self.lbl_ship)
        layout.addWidget(self.lbl_ship_status)

        bars_layout = QGridLayout()
        self.g_hull = self._add_gauge(bars_layout, 0, "Hull")
        self.g_shield = self._add_gauge(bars_layout, 1, "Shield")
        self.g_fuel = self._add_gauge(bars_layout, 2, "Fuel")
        self.g_energy = self._add_gauge(bars_layout, 3, "Energy")
        self.g_cargo = self._add_gauge(bars_layout, 4, "Cargo")
        layout.addLayout(bars_layout)

        self.lbl_jump = QLabel("Jump: base — ly | current — ly")
        layout.addWidget(self.lbl_jump)
        layout.addStretch(1)
        self.refresh()

    def _add_gauge(self, layout, row, name):
        label = QLabel(f"{name}:")
        gauge = TextGauge(total_chars=28, parent=self)
        layout.addWidget(label, row, 0)
        layout.addWidget(gauge, row, 1)
        return gauge

    def refresh(self) -> None:
        snapshot = player_status.get_status_snapshot()
        self.lbl_player.setText(f"Name: {snapshot.get('player_name','—')}")
        self.lbl_location.setText(f"Location: {snapshot.get('location_name') or snapshot.get('system_name') or '—'}")
        self.lbl_credits.setText(f"Credits: {snapshot.get('credits','—'):,}")
        self.lbl_ship.setText(f"Active Ship: {snapshot.get('ship_name','—')}")
        self.lbl_ship_status.setText(f"Ship Status: {snapshot.get('ship_state','—')}")
        self.g_hull.set_values(snapshot.get("hull", 0), snapshot.get("hull_max", 1))
        self.g_shield.set_values(snapshot.get("shield", 0), snapshot.get("shield_max", 1))
        self.g_fuel.set_values(snapshot.get("fuel", 0), snapshot.get("fuel_max", 1))
        self.g_energy.set_values(snapshot.get("energy", 0), snapshot.get("energy_max", 1))
        self.g_cargo.set_values(snapshot.get("cargo", 0), snapshot.get("cargo_max", 1))
        self.lbl_jump.setText(f"Jump: base {snapshot.get('base_jump_distance', 0.0):.1f} ly | current {snapshot.get('current_jump_distance', 0.0):.1f} ly")