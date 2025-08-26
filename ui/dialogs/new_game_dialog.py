from __future__ import annotations

from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

# pull starting options directly from the database
from data.db import get_connection


class NewGameDialog(QDialog):
    """
    New Game dialog with separate Race and Starting Location selectors.

    - Race combo is populated from `races` (starting_world=1).
    - Starting Location combo depends on the selected race:
        * If an optional table `race_start_locations(race_id, location_id)` exists
          and has rows for the race, those locations are listed.
        * Otherwise, the race's homeworld (home_planet_location_id) is listed.
    - get_selected_start_ids() returns {race_id, system_id, location_id}.

    NOTE: get_values() remains compatible and still returns a 3-tuple:
          (save_name, commander_name, label_str)
          where label_str combines both selections for display.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Game")
        self.setModal(True)

        self.edit_save_name = QLineEdit(self)
        self.edit_commander = QLineEdit(self)
        self.combo_race = QComboBox(self)
        self.combo_start = QComboBox(self)

        # Build the starting lists from the DB
        self._populate_races()
        self.combo_race.currentIndexChanged.connect(self._on_race_changed)
        self._on_race_changed()  # populate starting locations for the initially selected race

        form = QFormLayout()
        form.addRow("Save File Name:", self.edit_save_name)
        form.addRow("Commander Name:", self.edit_commander)
        form.addRow("Race:", self.combo_race)
        form.addRow("Starting Location:", self.combo_start)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        # sensible defaults
        self.edit_save_name.setText("New Save")
        self.edit_commander.setText("Captain")

    # ----- Public API (kept compatible with your existing callers) -----

    def get_values(self):
        """
        Returns:
          (save_name: str, commander_name: str, starting_label: str)

        starting_label combines the race and the chosen start location for display,
        e.g. "Aurelian — New Dawn (System: Solara)".
        """
        race_txt = self.combo_race.currentText()
        start_txt = self.combo_start.currentText()
        label = f"{race_txt} — {start_txt}" if race_txt and start_txt else (race_txt or start_txt or "")
        return (
            self.edit_save_name.text().strip(),
            self.edit_commander.text().strip(),
            label,
        )

    def get_selected_start_ids(self) -> Optional[Dict[str, int]]:
        """
        Returns dict with ids for spawning:
          { 'race_id': int, 'system_id': int, 'location_id': int }
        or None if nothing selected.
        """
        race_data = self.combo_race.currentData()
        start_data = self.combo_start.currentData()
        if not race_data or not start_data:
            return None

        return {
            "race_id": int(race_data["race_id"]),
            "system_id": int(start_data["system_id"]),
            "location_id": int(start_data["location_id"]),
        }

    # ----- Internals -----

    def _populate_races(self) -> None:
        """
        Populate race combo with all races flagged as starting_world.
        Item data payload (per race):
          { 'race_id', 'race_name', 'home_system_id', 'home_system_name',
            'home_location_id', 'home_location_name' }
        """
        conn = get_connection()
        self.combo_race.clear()

        rows = conn.execute(
            """
            SELECT
              r.race_id,
              r.name                    AS race_name,
              s.system_id               AS home_system_id,
              s.system_name             AS home_system_name,
              l.location_id             AS home_location_id,
              l.location_name           AS home_location_name
            FROM races r
            JOIN systems  s ON s.system_id = r.home_system_id
            JOIN locations l ON l.location_id = r.home_planet_location_id
            WHERE COALESCE(r.starting_world, 1) = 1
            ORDER BY r.name COLLATE NOCASE
            """
        ).fetchall()

        if not rows:
            self.combo_race.addItem("(no races found)", None)
            self.combo_race.setEnabled(False)
            self.combo_start.addItem("(no starting locations)", None)
            self.combo_start.setEnabled(False)
            return

        for r in rows:
            label = f"{r['race_name']}"
            payload = {
                "race_id": int(r["race_id"]),
                "race_name": r["race_name"],
                "home_system_id": int(r["home_system_id"]),
                "home_system_name": r["home_system_name"],
                "home_location_id": int(r["home_location_id"]),
                "home_location_name": r["home_location_name"],
            }
            self.combo_race.addItem(label, payload)

    def _on_race_changed(self) -> None:
        """Repopulate the Starting Location combo for the selected race."""
        self.combo_start.clear()
        race_data = self.combo_race.currentData()
        if not race_data:
            self.combo_start.addItem("(no starting locations)", None)
            self.combo_start.setEnabled(False)
            return

        # Try to load multiple start locations if an extension table exists.
        start_rows = self._load_start_locations_for_race(
            race_id=race_data["race_id"],
            fallback_system_id=race_data["home_system_id"],
            fallback_location_id=race_data["home_location_id"],
        )

        if not start_rows:
            self.combo_start.addItem("(no starting locations)", None)
            self.combo_start.setEnabled(False)
            return

        self.combo_start.setEnabled(True)
        for row in start_rows:
            label = f"{row['location_name']} (System: {row['system_name']})"
            payload = {
                "system_id": int(row["system_id"]),
                "location_id": int(row["location_id"]),
            }
            self.combo_start.addItem(label, payload)

    # ---- helpers ----

    def _table_exists(self, conn, name: str) -> bool:
        r = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,)
        ).fetchone()
        return bool(r and r[0] == name)

    def _load_start_locations_for_race(
        self,
        race_id: int,
        fallback_system_id: int,
        fallback_location_id: int,
    ) -> List[Dict]:
        """
        Load start locations for a race.
        If table 'race_start_locations(race_id, location_id)' exists and has rows,
        use those. Otherwise return the homeworld as the single option.
        """
        conn = get_connection()
        rows: List[Dict] = []

        if self._table_exists(conn, "race_start_locations"):
            # Expected minimal schema:
            #   race_start_locations(race_id INTEGER, location_id INTEGER)
            # Join to enrich with names and system info.
            dbrows = conn.execute(
                """
                SELECT
                  l.location_id,
                  l.location_name,
                  s.system_id,
                  s.system_name
                FROM race_start_locations rsl
                JOIN locations l ON l.location_id = rsl.location_id
                JOIN systems   s ON s.system_id   = l.system_id
                WHERE rsl.race_id = ?
                ORDER BY l.location_name COLLATE NOCASE
                """,
                (race_id,),
            ).fetchall()
            for r in dbrows:
                rows.append(
                    {
                        "location_id": int(r["location_id"]),
                        "location_name": r["location_name"],
                        "system_id": int(r["system_id"]),
                        "system_name": r["system_name"],
                    }
                )

        # Fallback to homeworld if no explicit starts were found.
        if not rows and fallback_location_id is not None:
            r = conn.execute(
                """
                SELECT l.location_id, l.location_name, s.system_id, s.system_name
                FROM locations l
                JOIN systems s ON s.system_id = l.system_id
                WHERE l.location_id = ?
                """,
                (fallback_location_id,),
            ).fetchone()
            if r:
                rows.append(
                    {
                        "location_id": int(r["location_id"]),
                        "location_name": r["location_name"],
                        "system_id": int(r["system_id"]),
                        "system_name": r["system_name"],
                    }
                )

        return rows
