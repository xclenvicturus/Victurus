# /save/manager.py

from __future__ import annotations

import shutil
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Dict, Any

from data import db
from data import seed as seed_module
from .paths import get_saves_dir, save_folder_for, sanitize_save_name
from .serializers import write_meta, read_meta
from .models import SaveMetadata


class SaveManager:
    _active_save_dir: Optional[Path] = None

    # --- NEW: UI state hook ---
    _UI_STATE_PROVIDER: Optional[Callable[[], Dict[str, Any]]] = None

    @classmethod
    def install_ui_state_provider(cls, fn: Callable[[], Dict[str, Any]]) -> None:
        """Register a callback that returns a JSON-serializable dict of the current UI/layout."""
        global _UI_STATE_PROVIDER
        _UI_STATE_PROVIDER = fn

    # --- NEW: UI state helpers ---
    @classmethod
    def _ui_state_path(cls, save_dir: Path) -> Path:
        return save_dir / "ui_state.json"

    @classmethod
    def write_ui_state(cls, save_dir: Optional[Path] = None) -> None:
        """Call the provider (if any) and persist ui_state.json next to game.db."""
        global _UI_STATE_PROVIDER
        if _UI_STATE_PROVIDER is None:
            return
        target = save_dir or cls._active_save_dir
        if not target:
            return
        try:
            data = _UI_STATE_PROVIDER() or {}
            p = cls._ui_state_path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Don't let UI-state persistence break saves
            pass

    @classmethod
    def read_ui_state_for_active(cls) -> Optional[Dict[str, Any]]:
        """Convenience: return the ui_state.json dict for the active save, if present."""
        if not cls._active_save_dir:
            return None
        p = cls._ui_state_path(cls._active_save_dir)
        if not p.exists():
            return None
        try:
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

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
        if not root.exists(): return []
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "game.db").exists():
                saves.append((child.name, child))
        return saves

    @classmethod
    def create_new_save(cls, save_name: str, commander_name: str, starting_location_label: str) -> Path:
        # Close any existing connection to ensure we start fresh.
        db.close_active_connection()

        dest = save_folder_for(save_name)
        if dest.exists():
            raise FileExistsError(f"Save folder '{dest.name}' already exists.")
        dest.mkdir(parents=True)

        db_path = dest / "game.db"
        conn = sqlite3.connect(db_path)
        try:
            schema_path = Path(__file__).resolve().parents[1] / "data" / "schema.sql"
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            seed_module.seed(conn)
            conn.commit()

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

            cur.execute("SELECT system_id FROM systems WHERE system_name = ?;", (system_name,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"System '{system_name}' not found for starting location.")
            system_id = row[0]

            cur.execute(
                "SELECT location_id FROM locations WHERE system_id = ? AND location_name = ?;",
                (system_id, f"{system_name} {planet_name}"),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "SELECT location_id FROM locations WHERE system_id = ? AND location_category='planet' ORDER BY location_id LIMIT 1;",
                    (system_id,)
                )
                row = cur.fetchone()
            
            if not row:
                raise RuntimeError(f"Could not find a starting planet in system '{system_name}'.")
            location_id = row[0]

            cur.execute(
                "UPDATE player SET name=?, current_player_system_id=?, current_player_location_id=? WHERE id=1;",
                (commander_name, system_id, location_id),
            )
            conn.commit()

        finally:
            conn.close()

        now = datetime.utcnow().isoformat()
        meta = SaveMetadata(
            save_name=dest.name,
            commander_name=commander_name,
            created_iso=now,
            last_played_iso=now,
        )
        write_meta(dest / "meta.json", meta)

        cls.set_active_save(dest)
        db.get_connection()  # opens a connection to new DB

        # NEW: persist an initial (default) UI state if a provider is registered
        cls.write_ui_state(dest)

        return dest

    @classmethod
    def load_save(cls, save_dir: Path) -> None:
        # Close any existing connection before loading a new one.
        db.close_active_connection()
        
        db_path = save_dir / "game.db"
        if not db_path.exists():
            raise FileNotFoundError(f"Save database not found: {db_path}")
        cls.set_active_save(save_dir)
        db.get_connection()

        # NOTE: UI state is *not* auto-applied here to avoid touching UI from a non-UI caller.
        # MainWindow should call SaveManager.read_ui_state_for_active() after it builds the UI.

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

        # NEW: snapshot and persist current UI state
        cls.write_ui_state()

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

        # NEW: refresh UI state snapshot into the new folder (even if it was copied)
        cls.write_ui_state(dest)
            
        return dest

    @classmethod
    def rename_save(cls, old_dir: Path, new_name: str) -> Path:
        if not old_dir.exists():
            raise FileNotFoundError("Original save directory not found.")
        
        new_dir = old_dir.parent / sanitize_save_name(new_name)
        if new_dir.exists():
            raise FileExistsError(f"A save named '{new_dir.name}' already exists.")
            
        old_dir.rename(new_dir)
        
        meta_path = new_dir / "meta.json"
        meta = read_meta(meta_path)
        if meta:
            meta.save_name = new_dir.name
            write_meta(meta_path, meta)
            
        if cls._active_save_dir == old_dir:
            cls.set_active_save(new_dir)
            
        return new_dir

    @classmethod
    def delete_save(cls, save_dir: Path) -> None:
        if not save_dir.exists():
            raise FileNotFoundError("Save directory not found.")
        if not save_dir.is_dir():
            raise NotADirectoryError("Target for deletion is not a directory.")
        
        shutil.rmtree(save_dir)
        
        if cls._active_save_dir == save_dir:
            cls._active_save_dir = None
