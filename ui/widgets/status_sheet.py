from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
)

from game import player_status


def _as_int(val: Any, default: int = 0) -> int:
    """Robust int conversion that keeps Pylance happy."""
    try:
        if isinstance(val, bool):
            return int(val)
        if val is None:
            return default
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        # str or other -> try float then int to accept "123.0"
        return int(float(str(val)))
    except Exception:
        return default


def _as_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val))
    except Exception:
        return default


class _Gauge(QProgressBar):
    """
    Minimal wrapper around QProgressBar that exposes set_values(current, max).
    """
    def __init__(self, text: str, parent: Optional[WIDGET] = None) -> None:  # type: ignore[name-defined]
        super().__init__(parent)
        self.setTextVisible(True)
        self.setFormat(text + ": %v / %m")
        self.setRange(0, 1)
        self.setValue(0)

    def set_values(self, current: int, maximum: int) -> None:
        m = _as_int(maximum, 1)
        if m < 1:
            m = 1
        v = _as_int(current, 0)
        if v < 0:
            v = 0
        if v > m:
            v = m
        self.setRange(0, m)
        self.setValue(v)


class StatusSheet(QWidget):
    """
    Dockable status panel with player/ship info and resource gauges.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Top labels
        self.lbl_player = QLabel("Name: —")
        self.lbl_location = QLabel("Location: —")
        self.lbl_credits = QLabel("Credits: —")
        self.lbl_ship = QLabel("Active Ship: —")
        self.lbl_ship_status = QLabel("Ship Status: —")
        self.lbl_jump = QLabel("Jump Range: 0.0 ly")

        # Gauges
        self.g_hull = _Gauge("Hull", self)
        self.g_shield = _Gauge("Shield", self)
        self.g_fuel = _Gauge("Fuel", self)
        self.g_energy = _Gauge("Energy", self)
        self.g_cargo = _Gauge("Cargo", self)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        top = QGridLayout()
        top.setHorizontalSpacing(10)
        top.setVerticalSpacing(4)

        row = 0
        top.addWidget(self.lbl_player, row, 0, 1, 2); row += 1
        top.addWidget(self.lbl_location, row, 0, 1, 2); row += 1
        top.addWidget(self.lbl_credits, row, 0, 1, 2); row += 1
        top.addWidget(self.lbl_ship, row, 0, 1, 2); row += 1
        top.addWidget(self.lbl_ship_status, row, 0, 1, 2); row += 1
        top.addWidget(self.lbl_jump, row, 0, 1, 2); row += 1

        root.addLayout(top)

        # Separator
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # Gauges block
        root.addWidget(self.g_hull)
        root.addWidget(self.g_shield)
        root.addWidget(self.g_fuel)
        root.addWidget(self.g_energy)
        root.addWidget(self.g_cargo)
        root.addStretch(1)

        # Initial fill
        self.refresh()

    # ---------- Public API ----------

    def refresh(self) -> None:
        """
        Pull a fresh snapshot and update labels + gauges.
        Defensive against type mismatches so the UI never throws.
        """
        snapshot = player_status.get_status_snapshot() or {}

        # Basic strings
        self.lbl_player.setText(f"Name: {snapshot.get('player_name','—')}")
        self.lbl_location.setText(
            f"Location: {snapshot.get('location_name') or snapshot.get('system_name') or '—'}"
        )

        # Credits: format with thousands separator, but only if numeric
        val = snapshot.get('credits', None)
        if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('_', '').replace(',', '').isdigit()):
            self.lbl_credits.setText(f"Credits: {_as_int(val):,}")
        else:
            self.lbl_credits.setText(f"Credits: {str(val) if val is not None else '—'}")

        self.lbl_ship.setText(f"Active Ship: {snapshot.get('ship_name','—')}")
        self.lbl_ship_status.setText(f"Ship Status: {snapshot.get('ship_state','—')}")

        # Gauges (use helpers to coerce)
        self.g_hull.set_values(_as_int(snapshot.get("hull", 0)), _as_int(snapshot.get("hull_max", 1), 1))
        self.g_shield.set_values(_as_int(snapshot.get("shield", 0)), _as_int(snapshot.get("shield_max", 1), 1))
        self.g_fuel.set_values(_as_int(snapshot.get("fuel", 0)), _as_int(snapshot.get("fuel_max", 1), 1))
        self.g_energy.set_values(_as_int(snapshot.get("energy", 0)), _as_int(snapshot.get("energy_max", 1), 1))
        self.g_cargo.set_values(_as_int(snapshot.get("cargo", 0)), _as_int(snapshot.get("cargo_max", 1), 1))

        # Jump distance label simplified
        curr = _as_float(snapshot.get('current_jump_distance', 0.0))
        self.lbl_jump.setText(f"Jump Range: {curr:.1f} ly")
