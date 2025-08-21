from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase

from data import db


class TextGauge(QLabel):
    """
    Monospace text gauge like:
      (||||||||  30/100        )
    The numeric text is centered within the bar.
    """
    def __init__(self, total_chars: int = 28, parent=None) -> None:
        super().__init__(parent)
        self.total_chars = max(10, int(total_chars))
        # Monospace font for even spacing
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f = QFont(mono)
        self.setFont(f)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(22)
        self._value = 0
        self._max = 1
        self._render()

    def set_values(self, value: int, maximum: int) -> None:
        maximum = max(1, int(maximum))
        value = max(0, min(int(value), maximum))
        if value == self._value and maximum == self._max:
            return
        self._value = value
        self._max = maximum
        self._render()

    def _render(self) -> None:
        inner = self.total_chars
        filled = int(round((self._value / float(self._max)) * inner))
        filled = max(0, min(filled, inner))
        buf = [" "] * inner
        for i in range(filled):
            buf[i] = "|"
        txt = f"{self._value}/{self._max}"
        start = max(0, (inner - len(txt)) // 2)
        for i, ch in enumerate(txt):
            j = start + i
            if 0 <= j < inner:
                buf[j] = ch
        gauge = "(" + "".join(buf) + ")"
        self.setText(gauge)


class StatusSheet(QWidget):
    """
    Dockable status panel showing:
      - Player: name, current location, credits
      - Active ship + ship status (Docked/Traveling/Combat/…)
      - Ship gauges: Hull, Shield, Fuel, Energy, Cargo (current/max)
      - Jump distances: base vs current (with fuel)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusSheet")

        self.lbl_title = QLabel("Commander Status", self)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px;")

        # top info
        self.lbl_player = QLabel("Name: —", self)
        self.lbl_location = QLabel("Location: —", self)
        self.lbl_credits = QLabel("Credits: —", self)

        # ship info
        self.lbl_ship = QLabel("Active Ship: —", self)
        self.lbl_ship_status = QLabel("Ship Status: —", self)

        # text gauges
        self.g_hull = TextGauge(total_chars=28, parent=self)
        self.g_shield = TextGauge(total_chars=28, parent=self)
        self.g_fuel = TextGauge(total_chars=28, parent=self)
        self.g_energy = TextGauge(total_chars=28, parent=self)
        self.g_cargo = TextGauge(total_chars=28, parent=self)

        bars = QGridLayout()
        bars.setContentsMargins(0, 4, 0, 0)
        bars.setHorizontalSpacing(8)
        bars.setVerticalSpacing(6)

        row = 0
        bars.addWidget(QLabel("Hull:"), row, 0)
        bars.addWidget(self.g_hull, row, 1)
        row += 1
        bars.addWidget(QLabel("Shield:"), row, 0)
        bars.addWidget(self.g_shield, row, 1)
        row += 1
        bars.addWidget(QLabel("Fuel:"), row, 0)
        bars.addWidget(self.g_fuel, row, 1)
        row += 1
        bars.addWidget(QLabel("Energy:"), row, 0)
        bars.addWidget(self.g_energy, row, 1)
        row += 1
        bars.addWidget(QLabel("Cargo:"), row, 0)
        bars.addWidget(self.g_cargo, row, 1)

        # jump range
        self.lbl_jump = QLabel("Jump: base — ly | current — ly", self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_player)
        lay.addWidget(self.lbl_location)
        lay.addWidget(self.lbl_credits)
        lay.addSpacing(2)
        lay.addWidget(self.lbl_ship)
        lay.addWidget(self.lbl_ship_status)
        lay.addLayout(bars)
        lay.addSpacing(4)
        lay.addWidget(self.lbl_jump)
        lay.addStretch(1)

        # initial state
        self.g_hull.set_values(0, 1)
        self.g_shield.set_values(0, 1)
        self.g_fuel.set_values(0, 1)
        self.g_energy.set_values(0, 1)
        self.g_cargo.set_values(0, 1)

    def refresh(self) -> None:
        """Pull a snapshot from db and update labels/bars."""
        snapshot: Dict = db.get_status_snapshot()

        # Labels
        self.lbl_player.setText(f"Name: {snapshot.get('player_name','—')}")
        loc_name = snapshot.get("location_name") or snapshot.get("system_name") or "—"
        self.lbl_location.setText(f"Location: {loc_name}")
        self.lbl_credits.setText(f"Credits: {snapshot.get('credits','—'):,}")
        self.lbl_ship.setText(f"Active Ship: {snapshot.get('ship_name','—')}")
        self.lbl_ship_status.setText(f"Ship Status: {snapshot.get('ship_state','—')}")

        # Gauges
        self.g_hull.set_values(snapshot.get("hull", 0), snapshot.get("hull_max", 1))
        self.g_shield.set_values(snapshot.get("shield", 0), snapshot.get("shield_max", 1))
        self.g_fuel.set_values(snapshot.get("fuel", 0), snapshot.get("fuel_max", 1))
        self.g_energy.set_values(snapshot.get("energy", 0), snapshot.get("energy_max", 1))
        self.g_cargo.set_values(snapshot.get("cargo", 0), snapshot.get("cargo_max", 1))

        # Jump
        base_jump = snapshot.get("base_jump_distance", 0.0)
        curr_jump = snapshot.get("current_jump_distance", 0.0)
        self.lbl_jump.setText(f"Jump: base {base_jump:.1f} ly | current {curr_jump:.1f} ly")
