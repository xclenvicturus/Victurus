from __future__ import annotations

import sqlite3
from typing import Optional, Tuple, Dict, Any

from ..event_bus import EventBus


class CombatController:
    """Thin controller that owns a simple, slow/meaningful combat loop.
    It logs to the bus and signals 'combat_over' when done.
    """

    def __init__(self, conn: sqlite3.Connection, bus: EventBus):
        self.conn = conn
        self.bus = bus
        self.state: Optional[Dict[str, Any]] = None

    def start(self, initial_state: Dict[str, Any]) -> None:
        """Begin a combat with a provided state dict.

        Expected keys (with defaults if missing):
          - enemy_name: str = "Enemy"
          - enemy_hp: int = 10
          - enemy_dmg: int = 2
          - player_name: str = "You"
          - player_hp: int = 100
          - player_dmg: int = 3
        """
        self.state = dict(initial_state)
        self.bus.emit("log", "combat", "Combat engaged.")

    def act(self, action: str) -> Tuple[str, bool]:
        """Perform one player action and resolve the enemy response.

        Returns:
            (log_line, over) where:
              - log_line: textual summary of the turn
              - over: True if combat ended this turn
        """
        if self.state is None:
            return ("Combat not initialized.", True)

        log, over = self._resolve_action(action)

        # Always log what happened
        self.bus.emit("log", "combat", log)

        if over:
            self.bus.emit("combat_over")

        return (log, over)

    # ---------------------------------------------------------------------
    # Internal resolution
    # ---------------------------------------------------------------------

    def _resolve_action(self, action: str) -> Tuple[str, bool]:
        """Pure resolution of one turn. Mutates self.state."""
        s = self.state
        assert s is not None

        enemy_name = str(s.get("enemy_name", "Enemy"))
        player_name = str(s.get("player_name", "You"))

        enemy_hp = int(s.get("enemy_hp", 10))
        player_hp = int(s.get("player_hp", 100))
        player_dmg = int(s.get("player_dmg", 3))
        enemy_dmg = int(s.get("enemy_dmg", 2))

        log_parts: list[str] = []

        # --- Player action ---
        if action == "attack":
            dmg = max(0, player_dmg)
            enemy_hp = max(0, enemy_hp - dmg)
            s["enemy_hp"] = enemy_hp
            log_parts.append(f"{player_name} hits {enemy_name} for {dmg}. ({enemy_hp} HP left)")
        elif action == "brace":
            s["braced"] = True
            log_parts.append(f"{player_name} braces for impact.")
        elif action == "flee":
            s["fled"] = True
            log_parts.append(f"{player_name} flees from {enemy_name}.")
            return (" ".join(log_parts), True)
        else:
            log_parts.append(f"{player_name} hesitates...")

        # Check enemy defeated before they act
        if enemy_hp <= 0:
            log_parts.append(f"{enemy_name} is destroyed.")
            return (" ".join(log_parts), True)

        # --- Enemy action ---
        if not s.get("fled"):
            incoming = max(0, enemy_dmg)
            if s.get("braced"):
                # Bracing blunts a bit of damage once
                incoming = max(0, incoming - 1)
                s["braced"] = False

            player_hp = max(0, player_hp - incoming)
            s["player_hp"] = player_hp
            log_parts.append(f"{enemy_name} strikes back for {incoming}. ({player_hp} HP left)")

        # End checks
        if player_hp <= 0:
            log_parts.append("Your ship is destroyed.")
            return (" ".join(log_parts), True)

        # Otherwise still going
        return (" ".join(log_parts), False)
