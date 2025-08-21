from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from data import db
from data import seed as seed_module
from .paths import get_saves_dir, save_folder_for
from .serializers import write_meta, read_meta
from .models import SaveMetadata

class SaveManager:
    _active_save_dir: Optional[Path] = None

    @classmethod
    def active_save_dir(cls) -> Optional[Path]:
        return cls._active_save_dir

    @classmethod
    def active_db_path(cls) -> Optional[Path]:
        return cls._active_save_dir / "game.db" if cls._active_save_dir else None

    @classmethod
    def set_active_save(cls, save_dir: Path) -> None:
        cls._active_save_dir = save_dir
        db.set_active_db_path(save_dir / "game.db")

    @classmethod
    def list_saves(cls) -> List[Tuple[str, Path]]:
        saves = []
        root = get_saves_dir()
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "game.db").exists():
                saves.append((child.name, child))
        return saves

    @classmethod
    def create_new_save(cls, save_name: str, commander_name: str, starting_location_label: str) -> Path:
        # Create folder
        dest = save_folder_for(save_name)
        dest.mkdir(parents=True, exist_ok=True)

        # Create DB and seed it
        db_path = dest / "game.db"
        conn = sqlite3.connect(db_path)
        try:
            # Apply schema and seed content
            from pathlib import Path as _P
            schema_path = _P(__file__).resolve().parents[1] / "data" / "schema.sql"
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            seed_module.seed(conn)

            # Update player name and starting location
            cur = conn.cursor()
            # Determine system + planet from label (e.g., "Sys-01 • Planet 1")
            # We accept formats "Sys-01 Planet 1" or "Sys-01 • Planet 1"
            label = starting_location_label.replace("•", " ").replace("  ", " ").strip()
            parts = label.split()
            # naive parse: everything up to "Planet" is system name
            try:
                planet_idx = parts.index("Planet")
                system_name = " ".join(parts[:planet_idx]).strip()
                planet_name = "Planet " + parts[planet_idx+1]
            except ValueError:
                system_name = parts[0]
                planet_name = "Planet " + parts[-1]

            # find system id
            cur.execute("SELECT id FROM systems WHERE name = ?;", (system_name,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"System not found for starting location: {system_name}")
            system_id = row[0]

            # find location id by name under system
            cur.execute(
                "SELECT id FROM locations WHERE system_id = ? AND name = ?;",
                (system_id, f"{system_name} {planet_name}"),
            )
            row = cur.fetchone()
            if not row:
                # fallback: first planet in system
                cur.execute(
                    "SELECT id FROM locations WHERE system_id = ? AND parent_location_id IS NULL ORDER BY id LIMIT 1;",
                    (system_id,),
                )
                row = cur.fetchone()
            location_id = row[0]

            # Update player row
            cur.execute(
                "UPDATE player SET name=?, system_id=?, current_location_id=? WHERE id=1;",
                (commander_name, system_id, location_id),
            )
            conn.commit()

        finally:
            conn.close()

        # Write metadata
        now = datetime.utcnow().isoformat()
        meta = SaveMetadata(
            save_name=str(dest.name),
            commander_name=commander_name,
            created_iso=now,
            last_played_iso=now,
        )
        write_meta(dest / "meta.json", meta)

        # Activate this save in the running app
        cls.set_active_save(dest)
        # Ask db module to ensure schema/seed, icons etc are consistent (idempotent)
        dbc = db.get_connection()
        dbc.close()

        return dest

    @classmethod
    def load_save(cls, save_dir: Path) -> None:
        if not (save_dir / "game.db").exists():
            raise FileNotFoundError(f"No game.db in {save_dir}")
        cls.set_active_save(save_dir)
        # Let db module reopen at new path
        dbc = db.get_connection()
        dbc.close()

    @classmethod
    def save_current(cls) -> None:
        # Most data is already persisted to SQLite as the game runs.
        # Provide a hook if transient caches need flushing later.
        conn = db.get_connection()
        conn.commit()

    @classmethod
    def save_as(cls, new_save_name: str) -> Path:
        if not cls._active_save_dir:
            raise RuntimeError("No active save to Save As…")
        src = cls._active_save_dir
        dest = save_folder_for(new_save_name)
        if dest.exists():
            raise FileExistsError(f"Destination save exists: {dest.name}")
        shutil.copytree(src, dest)
        # Activate new save
        cls.set_active_save(dest)
        return dest
