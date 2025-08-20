# Victurus/engine/qtui/panels/actions_panel.py
"""
ActionsPanel (left dock)
- Buttons for travel/dock/trade and feature toggles
- Emits signals for controllers to handle  # SCAFFOLD
"""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QCheckBox, QGroupBox, QHBoxLayout, QSpinBox, QLabel

class ActionsPanel(QWidget):
    # Signals other layers can connect to
    travelRequested = Signal(int)             # target_id  # SCAFFOLD
    dockRequested = Signal()                  # dock/undock
    tradeRequested = Signal()                 # open market
    featureToggled = Signal(str, bool)        # e.g., ("autorepair", True)
    talkRequested = Signal(int)               # npc_id

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)

        # Primary actions
        self.btn_travel = QPushButton("Travel…")
        self.btn_dock = QPushButton("Dock / Undock")
        self.btn_trade = QPushButton("Trade")

        # Example target chooser (SCAFFOLD demo)
        tgt_box = QGroupBox("Travel Target (id)")  # SCAFFOLD
        tgt_lay = QHBoxLayout(tgt_box)
        self.spin_target = QSpinBox(); self.spin_target.setRange(0, 10_000)
        tgt_lay.addWidget(QLabel("System ID:")); tgt_lay.addWidget(self.spin_target)

        # Feature toggles
        self.chk_autorepair = QCheckBox("Auto-repair")
        self.chk_autofuel = QCheckBox("Auto-fuel")
        self.chk_autorecharge = QCheckBox("Auto-recharge")

        # Wire signals (SCAFFOLD)
        self.btn_travel.clicked.connect(lambda: self.travelRequested.emit(self.spin_target.value()))
        self.btn_dock.clicked.connect(self.dockRequested)
        self.btn_trade.clicked.connect(self.tradeRequested)
        self.chk_autorepair.toggled.connect(lambda v: self.featureToggled.emit("autorepair", v))
        self.chk_autofuel.toggled.connect(lambda v: self.featureToggled.emit("autofuel", v))
        self.chk_autorecharge.toggled.connect(lambda v: self.featureToggled.emit("autorecharge", v))

        # Talk action (works with NpcPanel selection)
        self.btn_talk = QPushButton("Talk to Selected NPC")
        # SCAFFOLD: the npc_id is provided by NpcPanel via a callback; MainWindow wires it.

        # Layout
        root.addWidget(self.btn_travel)
        root.addWidget(tgt_box)
        root.addWidget(self.btn_dock)
        root.addWidget(self.btn_trade)
        root.addSpacing(8)
        root.addWidget(self.chk_autorepair)
        root.addWidget(self.chk_autofuel)
        root.addWidget(self.chk_autorecharge)
        root.addSpacing(8)
        root.addWidget(self.btn_talk)
        root.addStretch(1)
