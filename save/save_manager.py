# /save/save_manager.py

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
from save.icon_paths import bake_icon_paths

_UI_STATE_PROVIDER: Optional[Callable[[], Dict[str, Any]]] = None

def _apply_pragmas(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass

def _count_missing_icons(conn: sqlite3.Connection) -> Dict[str, int]:
    cur = conn.cursor()
    systems_missing = cur.execute("SELECT COUNT(*) FROM systems WHERE COALESCE(icon_path,'') = ''").fetchone()[0]
    locations_missing = cur.execute("SELECT COUNT(*) FROM locations WHERE COALESCE(icon_path,'') = ''").fetchone()[0]
    # resource nodes are now represented as locations with resource_type != ''
    resources_missing = cur.execute("SELECT COUNT(*) FROM locations WHERE COALESCE(icon_path,'') = '' AND COALESCE(resource_type,'') != ''").fetchone()[0]
    return {"systems": int(systems_missing), "locations": int(locations_missing), "resources": int(resources_missing)}

class SaveManager:
    _active_save_dir: Optional[Path] = None

    @classmethod
    def install_ui_state_provider(cls, fn: Callable[[], Dict[str, Any]]) -> None:
        global _UI_STATE_PROVIDER
        _UI_STATE_PROVIDER = fn

    @classmethod
    def _ui_state_path(cls, save_dir: Path) -> Path:
        return save_dir / "ui_state.json"

    @classmethod
    def write_ui_state(cls, save_dir: Optional[Path] = None) -> None:
        provider = _UI_STATE_PROVIDER
        if provider is None:
            return
        target = save_dir or cls._active_save_dir
        if not target:
            return
        try:
            data = provider() or {}
            p = cls._ui_state_path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def read_ui_state_for_active(cls) -> Optional[Dict[str, Any]]:
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
        saves: List[Tuple[str, Path]] = []
        root = get_saves_dir()
        if not root.exists():
            return []
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "game.db").exists():
                saves.append((child.name, child))
        return saves

    @classmethod
    def _find_fallback_start(cls, conn: sqlite3.Connection) -> Tuple[int, int]:
        row = conn.execute("""
            SELECT r.home_system_id, r.home_planet_location_id
            FROM races r
            WHERE COALESCE(r.starting_world, 1) = 1
            ORDER BY r.race_id
            LIMIT 1;
        """).fetchone()
        if row and row[0] is not None and row[1] is not None:
            return int(row[0]), int(row[1])
        sys_row = conn.execute("SELECT system_id FROM systems ORDER BY system_id LIMIT 1;").fetchone()
        if not sys_row:
            raise RuntimeError("No systems available for fallback start.")
        system_id = int(sys_row[0])
        loc_row = conn.execute("""
            SELECT location_id
            FROM locations
            WHERE system_id=? AND location_type='planet'
            ORDER BY location_id
            LIMIT 1;
        """, (system_id,)).fetchone()
        if not loc_row:
            loc_row = conn.execute("SELECT location_id FROM locations WHERE system_id=? ORDER BY location_id LIMIT 1;", (system_id,)).fetchone()
        if not loc_row:
            raise RuntimeError("No locations available for fallback start.")
        return system_id, int(loc_row[0])

    @classmethod
    def _validate_and_coerce_start(cls, conn: sqlite3.Connection, start_ids: Optional[Dict[str, int]]) -> Tuple[int, int]:
        if not start_ids:
            return cls._find_fallback_start(conn)

        sys_id = int(start_ids.get("system_id", 0) or 0)
        loc_id = int(start_ids.get("location_id", 0) or 0)

        sid_row = conn.execute("SELECT 1 FROM systems WHERE system_id=?;", (sys_id,)).fetchone()
        if not sid_row:
            return cls._find_fallback_start(conn)

        loc_row = conn.execute("SELECT system_id, location_type FROM locations WHERE location_id=?;", (loc_id,)).fetchone()
        if not loc_row:
            repl = conn.execute("""
                SELECT location_id FROM locations
                WHERE system_id=? AND location_type='planet'
                ORDER BY location_id LIMIT 1;
            """, (sys_id,)).fetchone()
            if repl:
                return sys_id, int(repl[0])
            repl = conn.execute("SELECT location_id FROM locations WHERE system_id=? ORDER BY location_id LIMIT 1;", (sys_id,)).fetchone()
            if repl:
                return sys_id, int(repl[0])
            return cls._find_fallback_start(conn)

        loc_sys_id = int(loc_row[0])
        if loc_sys_id != sys_id:
            repl = conn.execute("""
                SELECT location_id FROM locations
                WHERE system_id=? AND location_type='planet'
                ORDER BY location_id LIMIT 1;
            """, (sys_id,)).fetchone()
            if repl:
                return sys_id, int(repl[0])
            repl = conn.execute("SELECT location_id FROM locations WHERE system_id=? ORDER BY location_id LIMIT 1;", (sys_id,)).fetchone()
            if repl:
                return sys_id, int(repl[0])
            return cls._find_fallback_start(conn)

        return sys_id, loc_id

    @classmethod
    def create_new_save(cls, save_name: str, commander_name: str, starting_location_label: str, start_ids: Optional[Dict[str, int]] = None) -> Path:
        db.close_active_connection()

        dest = save_folder_for(save_name)
        if dest.exists():
            raise FileExistsError(f"Save folder '{dest.name}' already exists.")
        dest.mkdir(parents=True)

        db_path = dest / "game.db"
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            conn.row_factory = sqlite3.Row
            _apply_pragmas(conn)

            schema_path = Path(__file__).resolve().parents[1] / "data" / "schema.sql"
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

            seed_module.seed(conn)
            # Populate icon_path values for systems and locations using available assets.
            try:
                bake_icon_paths(conn, only_missing=True)
            except Exception:
                # Non-fatal: if bake fails, continue without blocking save creation
                pass
            conn.commit()

            system_id, location_id = cls._validate_and_coerce_start(conn, start_ids)

            cur = conn.cursor()
            has_player = cur.execute("SELECT 1 FROM player WHERE id=1;").fetchone()
            if not has_player:
                ship = cur.execute("""
                    SELECT ship_id, base_ship_fuel, base_ship_hull, base_ship_shield, base_ship_energy, base_ship_cargo
                    FROM ships
                    ORDER BY (ship_name='Shuttle') DESC, base_ship_cargo ASC
                    LIMIT 1;
                """).fetchone()
                if not ship:
                    raise RuntimeError("No ships available to initialize the player.")
                cur.execute("""
                    INSERT INTO player(
                        id, name, current_wallet_credits, current_player_system_id,
                        current_player_ship_id, current_player_ship_fuel,
                        current_player_ship_hull, current_player_ship_shield,
                        current_player_ship_energy, current_player_ship_cargo,
                        current_player_location_id
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    commander_name or "Captain",
                    1000,
                    system_id,
                    int(ship[0]), int(ship[1]), int(ship[2]), int(ship[3]), int(ship[4]),
                    0,
                    location_id,
                ))
            else:
                cur.execute("""
                    UPDATE player
                       SET name=?,
                           current_player_system_id=?,
                           current_player_location_id=?
                     WHERE id=1;
                """, (commander_name or "Captain", system_id, location_id))

            conn.commit()
        finally:
            conn.close()

        now = datetime.utcnow().isoformat()
        meta = SaveMetadata(
            save_name=dest.name,
            commander_name=commander_name,
            created_iso=now,
            last_played_iso=now,
            db_icons_only=True,
        )
        write_meta(dest / "meta.json", meta)

        cls.set_active_save(dest)
        db.get_connection()
        cls.write_ui_state(dest)
        return dest

    @classmethod
    def load_save(cls, save_dir: Path) -> None:
        db.close_active_connection()
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
        meta_path = cls._active_save_dir / "meta.json"
        meta = read_meta(meta_path)
        conn.commit()
        if meta:
            meta.last_played_iso = datetime.utcnow().isoformat()
            write_meta(meta_path, meta)
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
        if cls._active_save_dir == save_dir:
            try:
                db.close_active_connection()
            except Exception:
                pass
            cls._active_save_dir = None
        shutil.rmtree(save_dir)
