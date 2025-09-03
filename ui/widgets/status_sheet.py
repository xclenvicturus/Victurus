# /ui/widgets/status_sheet.py

"""
Player Status Sheet Widget

Displays player ship status, location, resources, and inventory information
in a formatted grid layout within a dock widget.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
)
from PySide6.QtGui import QCursor

from game import player_status


class ClickableLabel(QLabel):
    """A clickable QLabel that emits a clicked signal"""
    clicked = Signal()
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                text-decoration: underline;
            }
            QLabel:hover {
                color: #45A049;
            }
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


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
        self.lbl_ship = ClickableLabel("Active Ship: — (click to rename)")
        self.lbl_ship.clicked.connect(self._on_ship_name_clicked)
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
        top.addWidget(self.lbl_jump, row, 0, 1, 2); row += 1

        root.addLayout(top)

        # Separator - REMOVED since all top labels are now hidden
        # sep = QFrame(self)
        # sep.setFrameShape(QFrame.Shape.HLine)
        # sep.setFrameShadow(QFrame.Shadow.Sunken)
        # root.addWidget(sep)

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

        # Basic strings - HIDDEN per user request
        # Name (keep old behavior; fallback if not provided)
        # self.lbl_player.setText(f"Name: {snapshot.get('player_name','—')}")
        self.lbl_player.hide()

        # Location: prefer new key 'display_location', keep legacy fallbacks
        # loc = (
        #     snapshot.get('display_location') or
        #     snapshot.get('location_name') or
        #     snapshot.get('system_name') or
        #     '—'
        # )
        # self.lbl_location.setText(f"Location: {loc}")
        self.lbl_location.hide()

        # Credits: format with thousands separator, but only if numeric-ish
        # val = snapshot.get('credits', None)
        # if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('_', '').replace(',', '').isdigit()):
        #     try:
        #         self.lbl_credits.setText(f"Credits: {int(float(val)):,}")
        #     except Exception:
        #         self.lbl_credits.setText(f"Credits: {val}")
        # else:
        #     self.lbl_credits.setText(f"Credits: {str(val) if val is not None else '—'}")
        self.lbl_credits.hide()

        # Ship name (legacy key retained; safe if missing) - clickable for station services
        # ship_name = snapshot.get('ship_name','—')
        # current_status = snapshot.get('status', 'Unknown')
        # if current_status == 'Docked':
        #     self.lbl_ship.setText(f"Active Ship: {ship_name} (click for station services)")
        # else:
        #     self.lbl_ship.setText(f"Active Ship: {ship_name}")
        self.lbl_ship.hide()

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

        # Jump distance label — keep legacy keys if present - HIDDEN per user request
        # curr = _as_float(snapshot.get('current_jump_distance', snapshot.get('jump_distance', 0.0)))
        # self.lbl_jump.setText(f"Jump Range: {curr:.1f} ly")
        self.lbl_jump.hide()
    
    def _on_ship_name_clicked(self):
        """Handle ship name click to open station services or show info"""
        try:
            from game import player_status
            
            # Get current status
            status = player_status.get_status_snapshot()
            current_status = status.get('status', 'Unknown') if status else 'Unknown'
            
            if current_status == 'Docked':
                # Open station services dialog
                from ui.dialogs.station_services_dialog import show_station_services_dialog
                if show_station_services_dialog(self):
                    # Refresh the display if changes were made
                    self.refresh()
            else:
                # Show info that station services are only available when docked
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Station Services",
                    "Station services (including ship renaming) are only available when docked at a station.\n\n"
                    f"Current status: {current_status}"
                )
        except Exception as e:
            # Simple fallback error handling
            print(f"Error handling ship name click: {e}")
