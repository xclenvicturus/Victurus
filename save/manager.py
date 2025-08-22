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
        if dest.exists():
            raise FileExistsError(f"Save folder '{dest.name}' already exists.")
        dest.mkdir(parents=True)

        # Create DB and seed it
        db_path = dest / "game.db"
        conn = sqlite3.connect(db_path)
        try:
            # Apply schema and seed content
            schema_path = Path(__file__).resolve().parents[1] / "data" / "schema.sql"
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            seed_module.seed(conn)
            conn.commit()

            # Update player name and starting location
            cur = conn.cursor()
            label = starting_location_label.replace("•", "").strip()
            parts = label.split()
            try:
                planet_idx = parts.index("Planet")
                system_name = " ".join(parts[:planet_idx])
                planet_name = " ".join(parts[planet_idx:])
            except ValueError:
                system_name = parts[0]
                planet_name = " ".join(parts[1:]) if len(parts) > 1 else "Planet 1"

            cur.execute("SELECT id FROM systems WHERE name = ?;", (system_name,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"System '{system_name}' not found for starting location.")
            system_id = row[0]

            cur.execute(
                "SELECT id FROM locations WHERE system_id = ? AND name = ?;",
                (system_id, f"{system_name} {planet_name}"),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "SELECT id FROM locations WHERE system_id = ? AND kind='planet' ORDER BY id LIMIT 1;",
                    (system_id,)
                )
                row = cur.fetchone()
            
            if not row:
                raise RuntimeError(f"Could not find a starting planet in system '{system_name}'.")
            location_id = row[0]

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
            save_name=dest.name,
            commander_name=commander_name,
            created_iso=now,
            last_played_iso=now,
        )
        write_meta(dest / "meta.json", meta)

        cls.set_active_save(dest)
        db.get_connection()  # This will handle schema checks and icon assignments
        return dest

    @classmethod
    def load_save(cls, save_dir: Path) -> None:
        db_path = save_dir / "game.db"
        if not db_path.exists():
            raise FileNotFoundError(f"Save database not found: {db_path}")
        cls.set_active_save(save_dir)
        db.get_connection()

    @classmethod
    def save_current(cls) -> None:
        if not cls._active_save_dir:
            return
        conn = db.get_connection()
        conn.commit()
        
        meta_path = cls._active_save_dir / "meta.json"
        meta = read_meta(meta_path)
        if meta:
            meta.last_played_iso = datetime.utcnow().isoformat()
            write_meta(meta_path, meta)

    @classmethod
    def save_as(cls, new_save_name: str) -> Path:
        if not cls._active_save_dir:
            raise RuntimeError("No active save to use for 'Save As'.")
        
        dest = save_folder_for(new_save_name)
        if dest.exists():
            raise FileExistsError(f"Destination save folder '{dest.name}' already exists.")
        
        shutil.copytree(cls._active_save_dir, dest)
        
        cls.set_active_save(dest)
        
        meta_path = dest / "meta.json"
        meta = read_meta(meta_path)
        if meta:
            meta.save_name = dest.name
            meta.last_played_iso = datetime.utcnow().isoformat()
            write_meta(meta_path, meta)
            
        return dest