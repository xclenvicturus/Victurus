# engine/db_manager.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Optional


# Mapping of logical schema name => filename inside <slot>/Database
SCHEMA_FILES: Dict[str, str] = {
    "world":    "world.db",     # systems, planets, stations (has_hangar, fuel_price_base, repair_price_base, energy_price_base)
    "items":    "items.db",     # items, item_categories, markets
    "ships":    "ships.db",     # ships (hull, shield, energy_capacity, fuel_capacity, cargo_capacity, jump_range, base_price)
    "npcs":     "npcs.db",      # npcs
    "quests":   "quests.db",    # quests, quest_stages
    "factions": "factions.db",  # factions, faction_relations
}


class DBManager:
    """
    Opens save.db (main), attaches category DBs under <slot>/Database, and ensures MAIN has
    real tables (not cross-db views) seeded from those templates. Also runs light migrations:
      - Add missing columns that exist in templates
      - Add compatibility columns in stations: fuel_price, repair_price, energy_price
        (initialized from *_price_base) so older code keeps working
    """

    def __init__(self, slot_dir: Path):
        self.slot_dir = Path(slot_dir)
        self.save_db_path = self.slot_dir / "save.db"
        self.db_root = self.slot_dir / "Database"

    # ---- public -------------------------------------------------------------

    def open(self) -> sqlite3.Connection:
        self._ensure_paths()
        conn = sqlite3.connect(str(self.save_db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        self._attach_all(conn)
        self._seed_main_from_attached(conn)
        self._post_migrations(conn)
        return conn

    # ---- internal helpers ---------------------------------------------------

    def _ensure_paths(self) -> None:
        if not self.save_db_path.exists():
            self.save_db_path.touch()
        if not self.db_root.exists():
            raise RuntimeError(
                f"Missing Database directory: {self.db_root}. "
                f"New-game creation should have copied template DBs here."
            )
        missing = [fn for fn in SCHEMA_FILES.values() if not (self.db_root / fn).exists()]
        if missing:
            raise RuntimeError(f"Missing template DBs in {self.db_root}: {', '.join(missing)}")

    def _attach_all(self, conn: sqlite3.Connection) -> None:
        try:
            for schema in SCHEMA_FILES.keys():
                conn.execute(f"DETACH DATABASE {schema};")
        except Exception:
            pass
        for schema, filename in SCHEMA_FILES.items():
            path = self.db_root / filename
            conn.execute(f"ATTACH DATABASE ? AS {schema};", (str(path),))

    def _attached_tables(self, conn: sqlite3.Connection) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for schema in SCHEMA_FILES.keys():
            rows = conn.execute(
                f"SELECT name FROM {schema}.sqlite_master WHERE type='table';"
            ).fetchall()
            out[schema] = [str(r["name"]) for r in rows]
        return out

    def _main_object_type(self, conn: sqlite3.Connection, name: str) -> Optional[str]:
        row = conn.execute("SELECT type FROM sqlite_master WHERE name=?;", (name,)).fetchone()
        return (str(row["type"]) if row else None)

    def _main_columns(self, conn: sqlite3.Connection, table: str) -> Dict[str, str]:
        cols: Dict[str, str] = {}
        for r in conn.execute(f"PRAGMA table_info({table});").fetchall():
            n = str(r["name"])
            t = str(r["type"]) if r["type"] is not None else ""
            cols[n] = t
        return cols

    def _attached_columns(self, conn: sqlite3.Connection, schema: str, table: str) -> Dict[str, str]:
        cols: Dict[str, str] = {}
        for r in conn.execute(f"PRAGMA {schema}.table_info({table});").fetchall():
            n = str(r["name"])
            t = str(r["type"]) if r["type"] is not None else ""
            cols[n] = t
        return cols

    def _drop_conflicting_view(self, conn: sqlite3.Connection, name: str) -> None:
        if self._main_object_type(conn, name) == "view":
            conn.execute(f"DROP VIEW IF EXISTS {name};")

    def _ensure_main_table_exists(self, conn: sqlite3.Connection, schema: str, table: str) -> None:
        typ = self._main_object_type(conn, table)
        if typ is None:
            # Create empty table with same columns (0-row CTAS)
            conn.execute(f"CREATE TABLE {table} AS SELECT * FROM {schema}.{table} WHERE 0;")
        elif typ == "table":
            main_cols = self._main_columns(conn, table)
            src_cols = self._attached_columns(conn, schema, table)
            for col, coltype in src_cols.items():
                if col not in main_cols:
                    if coltype:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype};")
                    else:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col};")

    def _seed_if_empty(self, conn: sqlite3.Connection, schema: str, table: str) -> None:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table};").fetchone()
        if row and int(row["n"]) == 0:
            conn.execute(f"INSERT INTO {table} SELECT * FROM {schema}.{table};")

    def _seed_main_from_attached(self, conn: sqlite3.Connection) -> None:
        attached = self._attached_tables(conn)
        with conn:
            for schema, tables in attached.items():
                for t in tables:
                    self._drop_conflicting_view(conn, t)
                    self._ensure_main_table_exists(conn, schema, t)
                    self._seed_if_empty(conn, schema, t)

    def _post_migrations(self, conn: sqlite3.Connection) -> None:
        """Compatibility tweaks for legacy code paths."""
        with conn:
            # Ensure stations has both base and legacy price columns
            typ = self._main_object_type(conn, "stations")
            if typ == "table":
                cols = self._main_columns(conn, "stations")

                # Ensure base columns exist (in case an older template is used)
                if "fuel_price_base" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN fuel_price_base REAL DEFAULT 1.0;")
                if "repair_price_base" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN repair_price_base REAL DEFAULT 1.0;")
                if "energy_price_base" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN energy_price_base REAL DEFAULT 1.0;")
                if "has_hangar" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN has_hangar INTEGER DEFAULT 1;")

                # Add legacy compatibility columns if missing
                cols = self._main_columns(conn, "stations")  # refresh
                added = False
                if "fuel_price" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN fuel_price REAL;")
                    added = True
                if "repair_price" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN repair_price REAL;")
                    added = True
                if "energy_price" not in cols:
                    conn.execute("ALTER TABLE stations ADD COLUMN energy_price REAL;")
                    added = True

                # Initialize legacy columns from *_base where null
                if added:
                    conn.execute("""
                        UPDATE stations
                        SET
                          fuel_price   = COALESCE(fuel_price,   fuel_price_base),
                          repair_price = COALESCE(repair_price, repair_price_base),
                          energy_price = COALESCE(energy_price, energy_price_base)
                    """)
