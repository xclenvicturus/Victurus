# engine/controllers/quest_controller.py
from __future__ import annotations
import sqlite3
from typing import List, Dict


class QuestController:
    def __init__(self, conn: sqlite3.Connection, bus):
        self.conn = conn
        self.bus = bus
        self._ensure_tables()

    def _ensure_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS quest_state(
                    quest_id   INTEGER PRIMARY KEY,
                    status     TEXT NOT NULL DEFAULT 'locked',   -- locked|available|active|completed|failed
                    progress   INTEGER NOT NULL DEFAULT 0
                )
            """)

    # ---------- unlock logic ----------

    def unlock_by_npc(self, npc_id: int) -> int:
        """
        Unlocks quests whose prerequisite is 'talk_to_npc_id == npc_id'.
        Content DB should have quests.talk_to_npc_id (optional).
        """
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(quests);").fetchall()}
        if "talk_to_npc_id" not in cols:
            return 0
        qids = [int(r["id"]) for r in self.conn.execute(
            "SELECT id FROM quests WHERE talk_to_npc_id=?", (int(npc_id),)
        ).fetchall()]
        if not qids:
            return 0
        changed = 0
        with self.conn:
            for qid in qids:
                st = self.conn.execute("SELECT status FROM quest_state WHERE quest_id=?", (qid,)).fetchone()
                if not st:
                    self.conn.execute("INSERT INTO quest_state(quest_id, status) VALUES(?, 'available')", (qid,))
                    changed += 1
                elif st["status"] == "locked":
                    self.conn.execute("UPDATE quest_state SET status='available' WHERE quest_id=?", (qid,))
                    changed += 1
        if changed:
            try:
                self.bus.emit("quests_changed")
            except Exception:
                pass
        return changed

    # ---------- query helpers ----------

    def get_available_quests(self, location_id: int) -> List[Dict]:
        """
        Return quests for this location whose state is 'available' and not accepted yet.
        Content DB should have quests.origin_station_id or origin_npc_id in this location.
        We try to filter by station if column exists.
        """
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(quests);").fetchall()}
        if "origin_station_id" in cols:
            rows = self.conn.execute("""
                SELECT q.id, q.name, q.description
                FROM quests q
                JOIN quest_state qs ON qs.quest_id=q.id AND qs.status='available'
                WHERE q.origin_station_id=?
                ORDER BY q.name
            """, (int(location_id),)).fetchall()
        else:
            # Fallback: show all available
            rows = self.conn.execute("""
                SELECT q.id, q.name, q.description
                FROM quests q
                JOIN quest_state qs ON qs.quest_id=q.id AND qs.status='available'
                ORDER BY q.name
            """).fetchall()
        return [{"id": int(r["id"]), "name": r["name"], "desc": r["description"]} for r in rows]

    def get_active_quests(self) -> List[Dict]:
        rows = self.conn.execute("""
            SELECT q.id, q.name, q.description
            FROM quests q
            JOIN quest_state qs ON qs.quest_id=q.id AND qs.status='active'
            ORDER BY q.name
        """).fetchall()
        return [{"id": int(r["id"]), "name": r["name"], "desc": r["description"]} for r in rows]

    def get_completed_quests(self) -> List[Dict]:
        rows = self.conn.execute("""
            SELECT q.id, q.name, q.description
            FROM quests q
            JOIN quest_state qs ON qs.quest_id=q.id AND qs.status='completed'
            ORDER BY q.name
        """).fetchall()
        return [{"id": int(r["id"]), "name": r["name"], "desc": r["description"]} for r in rows]

    # ---------- state changes ----------

    def accept(self, quest_id: int):
        with self.conn:
            self.conn.execute("""
                INSERT INTO quest_state(quest_id, status) VALUES(?, 'active')
                ON CONFLICT(quest_id) DO UPDATE SET status='active'
            """, (int(quest_id),))
        try:
            self.bus.emit("quests_changed")
        except Exception:
            pass

    def abandon(self, quest_id: int):
        with self.conn:
            self.conn.execute("""
                UPDATE quest_state SET status='available' WHERE quest_id=?
            """, (int(quest_id),))
        try:
            self.bus.emit("quests_changed")
        except Exception:
            pass
