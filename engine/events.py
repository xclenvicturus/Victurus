# engine/events.py
from __future__ import annotations
import sqlite3
from typing import Dict, Tuple

# --- lightweight event logging into the save DB ------------------------------

def _ensure_player_events(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL,
            message  TEXT NOT NULL
        )
    """)

def log_event(conn: sqlite3.Connection, category: str, message: str) -> None:
    """
    Safe, local logger (no dependency on save_schema). Creates the table if needed.
    """
    _ensure_player_events(conn)
    conn.execute("INSERT INTO player_events(category, message) VALUES(?,?)",
                 (category, message))
    conn.commit()

# --- very small, deterministic combat core -----------------------------------

def combat_turn(conn: sqlite3.Connection, state: Dict, action: str) -> Tuple[str, bool]:
    """
    Returns (log_line, combat_over).
    Expected state keys (defaults applied if missing):
        - 'player_hp' (int)
        - 'enemy_hp'  (int)
        - 'player_dmg' (int, default 8)
        - 'enemy_dmg'  (int, default 5)
    Actions:
        - 'attack': player damages enemy; if enemy lives, enemy counterattacks.
        - 'brace' : halve incoming damage this turn.
        - 'flee'  : end combat immediately (success).
    """
    player_hp = int(state.get("player_hp", 100))
    enemy_hp  = int(state.get("enemy_hp",  30))
    pdmg      = int(state.get("player_dmg", 8))
    edmg      = int(state.get("enemy_dmg",  5))

    action = (action or "").lower().strip()
    over = False
    log  = ""

    if action == "flee":
        log = "You disengage and flee. Combat ends."
        over = True
        log_event(conn, "combat", log)
        return (log, over)

    if action == "brace":
        # Enemy hits for half
        enemy_hp = max(0, enemy_hp)  # no change to enemy hp
        dmg_in = max(0, edmg // 2)
        player_hp = max(0, player_hp - dmg_in)
        log = f"You brace (+defense). Enemy hits for {dmg_in}. HP: {player_hp}."
        if player_hp <= 0:
            log += " You are defeated."
            over = True
        state["player_hp"] = player_hp
        state["enemy_hp"]  = enemy_hp
        log_event(conn, "combat", log)
        return (log, over)

    # default = 'attack'
    dmg_out = max(0, pdmg)
    enemy_hp = max(0, enemy_hp - dmg_out)
    log_parts = [f"You attack for {dmg_out}. Enemy HP: {enemy_hp}."]
    if enemy_hp <= 0:
        log_parts.append("Enemy defeated.")
        over = True
    else:
        # enemy counterattack
        player_hp = max(0, player_hp - edmg)
        log_parts.append(f"Enemy strikes back for {edmg}. Your HP: {player_hp}.")
        if player_hp <= 0:
            log_parts.append("You are defeated.")
            over = True

    state["player_hp"] = player_hp
    state["enemy_hp"]  = enemy_hp

    log = " ".join(log_parts)
    log_event(conn, "combat", log)
    return (log, over)
