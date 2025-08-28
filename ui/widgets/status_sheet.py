
# /ui/widgets/status_sheet.py

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


class _GaugeRow(QWidget):
    """
    A label centered above a progress bar.
    Supports fractional rendering by scaling the bar's range/value.
    """
    def __init__(self, title: str, decimals: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._decimals = max(0, int(decimals))
        # scale 100 -> 0.01 precision on the bar for smoother motion
        self._scale = 100 if self._decimals > 0 else 1

        self.label = QLabel(f"{title}: —")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.bar = QProgressBar(self)
        self.bar.setTextVisible(False)  # we show text above instead
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        # keep consistent heights so none look shorter
        self.bar.setMinimumHeight(14)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.bar)

    def set_values(self, current: float, maximum: float) -> None:
        m = float(max(0.0, maximum))
        v = float(current)
        if m <= 0.0:
            # avoid zero-range bars; still show text
            self.bar.setRange(0, 1)
            self.bar.setValue(0)
            self._update_label(0.0, 0.0)
            return

        if v < 0.0:
            v = 0.0
        if v > m:
            v = m

        max_scaled = int(round(m * self._scale))
        val_scaled = int(round(v * self._scale))
        if max_scaled < 1:
            max_scaled = 1
        if val_scaled > max_scaled:
            val_scaled = max_scaled

        self.bar.setRange(0, max_scaled)
        self.bar.setValue(val_scaled)
        self._update_label(v, m)

    def _update_label(self, v: float, m: float) -> None:
        if self._decimals > 0:
            fmt = f"{self._title}: {v:.{self._decimals}f} / {m:.{self._decimals}f}"
        else:
            fmt = f"{self._title}: {int(v)} / {int(m)}"
        self.label.setText(fmt)


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

        # Gauges (decimals: fuel/energy 2dp; others integer)
        self.g_hull = _GaugeRow("Hull", decimals=0, parent=self)
        self.g_shield = _GaugeRow("Shield", decimals=0, parent=self)
        self.g_fuel = _GaugeRow("Fuel", decimals=2, parent=self)
        self.g_energy = _GaugeRow("Energy", decimals=2, parent=self)
        self.g_cargo = _GaugeRow("Cargo", decimals=0, parent=self)

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

        # Gauges block (labels already centered in each _GaugeRow)
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
        # Name (keep old behavior; fallback if not provided)
        self.lbl_player.setText(f"Name: {snapshot.get('player_name','—')}")

        # Location: prefer new key 'display_location', keep legacy fallbacks
        loc = (
            snapshot.get('display_location') or
            snapshot.get('location_name') or
            snapshot.get('system_name') or
            '—'
        )
        self.lbl_location.setText(f"Location: {loc}")

        # Credits: format with thousands separator, but only if numeric-ish
        val = snapshot.get('credits', None)
        if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('_', '').replace(',', '').isdigit()):
            try:
                self.lbl_credits.setText(f"Credits: {int(float(val)):,}")
            except Exception:
                self.lbl_credits.setText(f"Credits: {val}")
        else:
            self.lbl_credits.setText(f"Credits: {str(val) if val is not None else '—'}")

        # Ship name (legacy key retained; safe if missing)
        self.lbl_ship.setText(f"Active Ship: {snapshot.get('ship_name','—')}")

        # Ship status: prefer new 'status', then legacy 'ship_state'
        ship_status = snapshot.get('status') or snapshot.get('ship_state') or '—'
        self.lbl_ship_status.setText(f"Ship Status: {ship_status}")

        # Gauges (use floats for fuel/energy to keep smooth)
        self.g_hull.set_values(_as_int(snapshot.get("hull", 0)), _as_int(snapshot.get("hull_max", 1), 1))
        self.g_shield.set_values(_as_int(snapshot.get("shield", 0)), _as_int(snapshot.get("shield_max", 1), 1))

        fuel = _as_float(snapshot.get("fuel", 0.0))
        fuel_max = _as_float(snapshot.get("fuel_max", 1.0), 1.0)
        self.g_fuel.set_values(fuel, fuel_max)

        energy = _as_float(snapshot.get("energy", 0.0))
        energy_max = _as_float(snapshot.get("energy_max", 1.0), 1.0)
        self.g_energy.set_values(energy, energy_max)

        self.g_cargo.set_values(_as_int(snapshot.get("cargo", 0)), _as_int(snapshot.get("cargo_max", 1), 1))

        # Jump distance label — keep legacy keys if present
        curr = _as_float(snapshot.get('current_jump_distance', snapshot.get('jump_distance', 0.0)))
        self.lbl_jump.setText(f"Jump Range: {curr:.1f} ly")
