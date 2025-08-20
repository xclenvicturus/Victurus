from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QMenuBar, QWidget, QMessageBox
)

from .map.galaxy_view import GalaxyMapView
from .panels.actions_panel import ActionsPanel
from .panels.npc_panel import NpcPanel
from .panels.log_panel import LogPanel


class MainWindow(QMainWindow):
    """Host dock panes (Actions/NPC/Log) and central map view.  # SCAFFOLD"""

    def __init__(self, ctx=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Victurus (Qt)")

        # Context (SCAFFOLD): your Settings/EventBus/services can be attached here later
        self.ctx = ctx

        # Central map view -----------------------------------------------------
        self.map_view = GalaxyMapView(parent=self)
        self.setCentralWidget(self.map_view)

        # Dock panes -----------------------------------------------------------
        self.actions_dock = QDockWidget("Actions", self)
        self.actions_dock.setObjectName("dock_actions")
        self.npc_dock = QDockWidget("NPCs", self)
        self.npc_dock.setObjectName("dock_npcs")
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("dock_log")

        self.actions_panel = ActionsPanel(parent=self)
        self.npc_panel = NpcPanel(parent=self)
        self.log_panel = LogPanel(parent=self)

        self.actions_dock.setWidget(self.actions_panel)
        self.npc_dock.setWidget(self.npc_panel)
        self.log_dock.setWidget(self.log_panel)

        # Qt6: Dock areas are under Qt.DockWidgetArea.*
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.actions_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.npc_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.setDockNestingEnabled(True)  # allow multi-row/column docking

        # Menus & actions ------------------------------------------------------
        menubar: QMenuBar = self.menuBar()
        self._build_menus(menubar)

        # Status bar -----------------------------------------------------------
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("No game loaded (Qt shell scaffold)")

        # Signal wiring (SCAFFOLD) --------------------------------------------
        self.actions_panel.tradeRequested.connect(self._on_trade)
        self.actions_panel.dockRequested.connect(self._on_dock)
        self.actions_panel.featureToggled.connect(self._on_feature_toggle)
        self.actions_panel.talkRequested.connect(self._on_talk)

        # Example: seed NPC panel list (SCAFFOLD demo)
        self.npc_panel.set_npcs([
            {"id": 1, "name": "Station Clerk", "role": "Trader", "faction": "Civ"},
            {"id": 2, "name": "Harbor Master", "role": "Dock", "faction": "Civ"},
        ])

        # Example: seed map (SCAFFOLD demo)
        # Access our typed scene via GalaxyMapView.scene_obj (not the base .scene()).
        self.map_view.scene_obj.set_demo_systems()

    # --- Menus ---------------------------------------------------------------

    def _build_menus(self, menubar: QMenuBar) -> None:
        game = menubar.addMenu("&Game")
        windows = menubar.addMenu("&Windows")
        cheats = menubar.addMenu("&Cheats")
        helpm = menubar.addMenu("&Help")

        act_new = QAction("New Game", self);  act_new.setShortcut("Ctrl+N")
        act_load = QAction("Load…", self);    act_load.setShortcut("Ctrl+L")
        act_save = QAction("Save", self);     act_save.setShortcut("Ctrl+S")
        act_quit = QAction("Quit", self);     act_quit.setShortcut("Ctrl+Q")

        act_new.triggered.connect(self._on_new_game)    # SCAFFOLD: integrate SaveManager later
        act_load.triggered.connect(self._on_load_game)  # SCAFFOLD
        act_save.triggered.connect(self._on_save_game)  # SCAFFOLD
        act_quit.triggered.connect(self.close)

        game.addAction(act_new); game.addAction(act_load); game.addAction(act_save)
        game.addSeparator(); game.addAction(act_quit)

        # Windows menu: simple togglers for docks (SCAFFOLD)
        for title, dock in [("Actions", self.actions_dock),
                            ("NPCs", self.npc_dock),
                            ("Log", self.log_dock)]:
            act = QAction(f"Toggle {title}", self, checkable=True, checked=True)
            act.toggled.connect(lambda v, d=dock: d.setVisible(v))
            windows.addAction(act)

        # Cheats (SCAFFOLD): example action
        give_credits = QAction("Give Credits", self)
        give_credits.triggered.connect(lambda: self.log_panel.append_log("cheat", "credits", "Gave 1000 cr"))
        cheats.addAction(give_credits)

        # Help
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.information(self, "About", "Victurus Qt shell scaffold"))
        helpm.addAction(about)

    # --- Actions (SCAFFOLD handlers) ----------------------------------------

    def _on_new_game(self) -> None:
        self.log_panel.append_log("system", "game", "New Game requested (SCAFFOLD).")

    def _on_load_game(self) -> None:
        self.log_panel.append_log("system", "game", "Load Game requested (SCAFFOLD).")

    def _on_save_game(self) -> None:
        self.log_panel.append_log("system", "game", "Save requested (SCAFFOLD).")

    def _on_trade(self) -> None:
        self.log_panel.append_log("ui", "action", "Trade requested (SCAFFOLD).")

    def _on_dock(self) -> None:
        self.log_panel.append_log("ui", "action", "Dock/Undock requested (SCAFFOLD).")

    def _on_feature_toggle(self, name: str, enabled: bool) -> None:
        self.log_panel.append_log("ui", "feature", f"Feature {name} -> {enabled} (SCAFFOLD).")

    def _on_talk(self, npc_id: int) -> None:
        self.log_panel.append_log("ui", "talk", f"Talk to NPC id={npc_id} (SCAFFOLD).")
