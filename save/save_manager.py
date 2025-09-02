# /save/save_manager.py

"""
Victurus Save Game Management System

Comprehensive save game functionality:
- Debounced save system with automatic UI state persistence
- Save slot management and metadata tracking
- Database backup and restoration
- UI state serialization and restoration
- Thread-safe save operations
"""

from __future__ import annotations

import shutil
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Dict, Any, cast, Type
import threading
# Prefer scheduling the debounced flush on the Qt main thread when available so
# the provider (which reads widget geometry) runs safely in the GUI thread.
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    _QT_AVAILABLE = True
except Exception:
    QTimer = None  # type: ignore
    QApplication = None  # type: ignore
    _QT_AVAILABLE = False

from data import db
from data import seed as seed_module
from .paths import get_saves_dir, save_folder_for, sanitize_save_name, get_ui_state_path
# Import window_state updater so UI state is persisted to the global config
from ui.state.window_state import update_window_data, _load_state as _load_global_ui_state
from ui.state.window_state import suspend_writes as _suspend_window_state_writes, resume_writes as _resume_window_state_writes
from .ui_state_tracer import append_event
from game_controller.log_config import get_system_logger
import inspect

logger = get_system_logger('save_manager')
import traceback

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
    # Internal flag used to suppress writes while we're applying/restoring state
    _suspend_ui_writes: bool = False
    # Debounce timers (keep Qt and threaded timers separate so static type
    # checkers don't complain about mixed types) & lock for coalescing rapid
    # UI-state writes
    # Qt timer (when Qt is available). Use a permissive Any-typed attribute so
    # static type checkers don't complain about the optional PySide6 import.
    _qt_ui_write_timer: Any = None
    # Threading timer fallback
    _thread_ui_write_timer: Optional[threading.Timer] = None
    _ui_write_lock: threading.Lock = threading.Lock()
    _UI_WRITE_DEBOUNCE_SECONDS: float = 0.25

    @classmethod
    def install_ui_state_provider(cls, fn: Callable[[], Dict[str, Any]]) -> None:
        global _UI_STATE_PROVIDER
        _UI_STATE_PROVIDER = fn
        try:
            caller = inspect.stack()[1]
            logger.debug("Installed UI state provider %s (requested by %s:%s)", fn, caller.filename, caller.lineno)
        except Exception:
            logger.debug("Installed UI state provider %s", fn)

    @classmethod
    def _ui_state_path(cls, save_dir: Path) -> Path:
        return save_dir / "ui_state.json"

    @classmethod
    def _log_path(cls, save_dir: Path) -> Path:
        return save_dir / "game_log.jsonl"

    @classmethod
    def write_ui_state(cls, save_dir: Optional[Path] = None) -> None:
        provider = _UI_STATE_PROVIDER
        if provider is None:
            return
        if cls._suspend_ui_writes:
            # Quietly skip writes while a restore operation is in progress
            try:
                caller = inspect.stack()[1]
                logger.debug("write_ui_state skipped (suspended) requested by %s:%s", caller.filename, caller.lineno)
            except Exception:
                logger.debug("write_ui_state skipped (suspended)")
            return
        # Log the immediate requester for diagnostics
        try:
            caller = inspect.stack()[1]
            logger.debug("write_ui_state requested by %s:%s", caller.filename, caller.lineno)
        except Exception:
            pass

        # Debounced flush function (runs in a background timer thread)
        def _flush(sd: Optional[Path]) -> None:
            # Ensure only one flush runs at a time
            try:
                with cls._ui_write_lock:
                    # clear timer references so new schedules can be created
                    cls._qt_ui_write_timer = None
                    cls._thread_ui_write_timer = None
                if cls._suspend_ui_writes:
                    logger.debug("UI-state flush aborted: suspend flag set")
                    return
                # Temporarily suspend window_state writes while performing the
                # flush so programmatic persistence/mirroring doesn't itself
                # trigger additional writes or races that can overwrite a
                # restored layout. Resume at the end of the flush.
                append_event("flush_start", f"save_dir={sd}")
                try:
                    _suspend_window_state_writes()
                except Exception:
                    pass
                data = {}
                try:
                    data = provider() or {}
                except Exception:
                    data = {}
                try:
                    try:
                        # Include a short preview of keys to reduce verbosity
                        try:
                            keys = sorted(list(data.keys())) if isinstance(data, dict) else []
                        except Exception:
                            keys = []
                        logger.debug("Persisting UI state (MainWindow), keys=%s: %s", keys, data)
                        # If suspicious keys are present, emit a stack trace for diagnosis
                        interesting = set(keys) & {"galaxy_col_widths", "system_col_widths", "central_splitter_sizes"}
                        if interesting:
                            stack = ''.join(traceback.format_stack(limit=10))
                            logger.debug("Persist flush stack (interesting keys=%s):\n%s", list(interesting), stack)
                    except Exception:
                        pass

                    # If a global ui_state.json already exists, do NOT overwrite
                    # it here. Instead, write a per-save ui_state.json in the
                    # provided save_dir (or the active save) so non-user-driven
                    # operations don't clobber the central config. Only create
                    # the global file via update_window_data when it does not
                    # already exist (first-run/new-game).
                    try:
                        p_glob = get_ui_state_path()
                    except Exception:
                        p_glob = None

                    # Determine target per-save path
                    target_save = sd or cls._active_save_dir
                    per_path = None
                    if target_save is not None:
                        try:
                            per_path = target_save / "ui_state.json"
                        except Exception:
                            per_path = None
                    if p_glob is not None and p_glob.exists():
                        # Write only to per-save ui_state.json (if available).
                        if per_path is not None:
                            try:
                                per_path.parent.mkdir(parents=True, exist_ok=True)
                                per_path.write_text(json.dumps({"MainWindow": data}, indent=2), encoding="utf-8")
                                logger.debug("Wrote per-save UI state to %s", per_path)
                                append_event("wrote_per_save", str(per_path))
                            except Exception:
                                logger.exception("Failed writing per-save UI state to %s", per_path)
                        else:
                            # No target save available; skip global write to avoid overwriting user config
                            logger.debug("Skipping UI state write: global config exists and no target save_dir provided")
                    else:
                        # Global file missing: persist to global via update_window_data
                        try:
                            update_window_data("MainWindow", data)
                        except Exception:
                            # Fallback: write minimal wrapper to global path
                            try:
                                if p_glob is not None:
                                    p_glob.parent.mkdir(parents=True, exist_ok=True)
                                    tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                                    tmp.write_text(json.dumps({"MainWindow": data}, indent=2), encoding="utf-8")
                                    tmp.replace(p_glob)
                            except Exception:
                                pass

                    # Also mirror per-dock visibility into individual dock entries
                    try:
                        vis = (data or {}).get("dock_visibility") or {}
                        if isinstance(vis, dict):
                            for obj_name, is_open in vis.items():
                                try:
                                    logger.debug("Mirroring dock open flag for %s = %s", obj_name, bool(is_open))
                                    # Only write per-dock entries to the global file if
                                    # it doesn't exist yet. If global exists, avoid
                                    # touching it; per-save file already contains
                                    # MainWindow above.
                                    if p_glob is None or not p_glob.exists():
                                        update_window_data(obj_name, {"open": bool(is_open)})
                                        append_event("mirrored_dock", obj_name)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                except Exception:
                    # best-effort fallback: write minimal wrapper to config path
                    try:
                        p_glob = get_ui_state_path()
                        p_glob.parent.mkdir(parents=True, exist_ok=True)
                        tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                        tmp.write_text(json.dumps({"MainWindow": data}, indent=2), encoding="utf-8")
                        tmp.replace(p_glob)
                    except Exception:
                        pass
            except Exception:
                # swallow any exceptions from the timer thread
                pass
            finally:
                # Always resume window_state writes even if an error occurred
                try:
                    _resume_window_state_writes()
                    append_event("flush_end", f"save_dir={sd}")
                except Exception:
                    pass

        # Schedule (or reschedule) the debounced flush
        try:
            with cls._ui_write_lock:
                # Cancel any existing scheduled flush. Keep Qt and thread
                # timers in separate attributes to avoid mixed-type ops.
                try:
                    if cls._qt_ui_write_timer is not None:
                        try:
                            cls._qt_ui_write_timer.stop()
                        except Exception:
                            pass
                        cls._qt_ui_write_timer = None
                except Exception:
                    pass
                try:
                    if cls._thread_ui_write_timer is not None:
                        try:
                            cls._thread_ui_write_timer.cancel()
                        except Exception:
                            pass
                        cls._thread_ui_write_timer = None
                except Exception:
                    pass

            # If Qt is available and an application instance exists, schedule
            # the flush on the Qt event loop so the provider() runs in the
            # GUI thread (safe to read widget geometry).
            if _QT_AVAILABLE and QApplication is not None and QApplication.instance() is not None:
                try:
                    # Assign QTimer to a local name with an ignore so static
                    # type checkers don't complain about the optional import.
                    qt_timer_cls = cast(Type[Any], QTimer)
                    qt_timer = qt_timer_cls()
                    qt_timer.setSingleShot(True)
                    # Ensure the timer isn't GC'd; parent it to the app
                    try:
                        qt_timer.setParent(QApplication.instance())
                    except Exception:
                        pass
                    qt_timer.timeout.connect(lambda sd=save_dir: _flush(sd))
                    cls._qt_ui_write_timer = qt_timer
                    logger.debug("Scheduling UI-state flush on Qt event loop in %.3fs", cls._UI_WRITE_DEBOUNCE_SECONDS)
                    qt_timer.start(int(cls._UI_WRITE_DEBOUNCE_SECONDS * 1000))
                except Exception:
                    # Fall back to threading.Timer if Qt scheduling fails
                    t = threading.Timer(cls._UI_WRITE_DEBOUNCE_SECONDS, lambda: _flush(save_dir))
                    t.daemon = True
                    cls._thread_ui_write_timer = t
                    logger.debug("Scheduling UI-state flush in %.3fs (threading fallback)", cls._UI_WRITE_DEBOUNCE_SECONDS)
                    t.start()
            else:
                # No Qt available: use threading.Timer as before
                t = threading.Timer(cls._UI_WRITE_DEBOUNCE_SECONDS, lambda: _flush(save_dir))
                t.daemon = True
                cls._thread_ui_write_timer = t
                logger.debug("Scheduling UI-state flush in %.3fs", cls._UI_WRITE_DEBOUNCE_SECONDS)
                t.start()
        except Exception:
            # If timer scheduling fails for any reason, fall back to immediate write
            try:
                _flush(save_dir)
            except Exception:
                pass

    @classmethod
    def write_log_entries(cls, entries: List[Tuple[str, str, str]], save_dir: Optional[Path] = None) -> None:
        """Write log entries as JSON-lines (ts_iso, category, text)."""
        target = save_dir or cls._active_save_dir
        if not target:
            return
        p = cls._log_path(target)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                for ts_iso, cat, txt in entries:
                    json.dump((ts_iso, cat, txt), f)
                    f.write("\n")
        except Exception:
            pass

    @classmethod
    def read_log_entries_for_active(cls) -> List[Tuple[str, str, str]]:
        """Read saved log entries for active save, return list of tuples."""
        if not cls._active_save_dir:
            return []
        p = cls._log_path(cls._active_save_dir)
        if not p.exists():
            return []
        out: List[Tuple[str, str, str]] = []
        try:
            with p.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        tup = json.loads(ln)
                        if isinstance(tup, (list, tuple)) and len(tup) == 3:
                            out.append((str(tup[0]), str(tup[1]), str(tup[2])))
                    except Exception:
                        continue
        except Exception:
            return []
        return out

    @classmethod
    def read_ui_state_for_active(cls) -> Optional[Dict[str, Any]]:
        # Read global UI state (Config/ui_state.json) and return the MainWindow entry.
        try:
            # First, prefer a per-save ui_state.json in the active save directory
            try:
                active = cls._active_save_dir
                if active is not None:
                    per = cls._ui_state_path(active)
                    if per.exists():
                        try:
                            txt = per.read_text(encoding="utf-8")
                            pdata = json.loads(txt) if txt else {}
                        except Exception:
                            pdata = {}
                        if isinstance(pdata, dict):
                            mw = pdata.get("MainWindow")
                            if isinstance(mw, dict):
                                try:
                                    append_event("read_ui_state", f"source=per-save path={per}")
                                except Exception:
                                    pass
                                return mw

            except Exception:
                pass

            # Fallback: read the global UI state
            glob = _load_global_ui_state()
            if isinstance(glob, dict):
                mw = glob.get("MainWindow")
                if isinstance(mw, dict):
                    try:
                        pglob = get_ui_state_path()
                        msg = f"Loaded UI state from global config (MainWindow) at: {pglob}"
                        logger.info(msg)
                        # DEBUG: show top-level keys present in the MainWindow entry
                        logger.debug("Global MainWindow UI state keys: %s", sorted(list(mw.keys())))
                    except Exception:
                        msg = "Loaded UI state from global config (MainWindow)"
                        logger.info(msg)
                    # Merge legacy per-dock entries (dock_* -> {open: bool}) into
                    # MainWindow.dock_visibility for backward compatibility. This
                    # ensures older files that stored per-dock "open" flags are
                    # respected when restoring.
                    try:
                        if isinstance(glob, dict):
                            vis = mw.setdefault("dock_visibility", {})
                            for key, val in glob.items():
                                try:
                                    if isinstance(key, str) and key.startswith("dock_") and isinstance(val, dict):
                                        if "open" in val:
                                            vis[key] = bool(val.get("open"))
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    try:
                        try:
                            path_str = str(get_ui_state_path())
                        except Exception:
                            path_str = "(unknown)"
                        append_event("read_ui_state", f"source=global path={path_str}")
                    except Exception:
                        pass
                    return mw
        except Exception as e:
            logger.exception("Failed to read global UI state: %s", e)
            pass
        return None

    @classmethod
    def suspend_ui_state_writes(cls) -> None:
        cls._suspend_ui_writes = True
        # Cancel any pending debounced flush so it cannot run while we're
        # suspending writes (race condition during shutdown/restore).
        try:
            with cls._ui_write_lock:
                try:
                    if cls._qt_ui_write_timer is not None:
                        try:
                            cls._qt_ui_write_timer.stop()
                        except Exception:
                            pass
                        cls._qt_ui_write_timer = None
                except Exception:
                    pass
                try:
                    if cls._thread_ui_write_timer is not None:
                        try:
                            cls._thread_ui_write_timer.cancel()
                        except Exception:
                            pass
                        cls._thread_ui_write_timer = None
                except Exception:
                    pass
        except Exception:
            pass
        try:
            _suspend_window_state_writes()
        except Exception:
            pass

    @classmethod
    def resume_ui_state_writes(cls) -> None:
        cls._suspend_ui_writes = False
        try:
            _resume_window_state_writes()
        except Exception:
            pass

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
        # If the global UI state file doesn't exist yet, create it now from
        # the installed UI state provider (if present). We intentionally
        # create/update the global Config/ui_state.json so UI state is kept
        # in the central config rather than scattered into per-save files.
        try:
            p_glob = get_ui_state_path()
            if not p_glob.exists():
                # Try to create a full global UI state now (provider may
                # return a richer snapshot than the minimal file creator).
                try:
                    cls._ensure_global_ui_state_present(dest)
                except Exception:
                    pass
        except Exception:
            # Non-fatal: continue even if we fail to write the global file
            pass
        # Do NOT schedule a UI-state write here - this would overwrite user preferences
        # The global config file should already exist and contain user settings
        return dest

    @classmethod
    def _create_ui_state_file_if_missing(cls, save_dir: Path) -> None:
        """Create a minimal per-save ui_state.json if it doesn't exist.

        The file will contain a MainWindow entry produced by the installed
        UI provider (if present) or copied from the global MainWindow UI
        state. Also mirror any dock_visibility into per-dock `open` flags so
        older code expecting dock_* entries can read them.
        """
        # Write the snapshot into the global Config/ui_state.json so UI
        # state is centralized. If the global file already exists, do nothing.
        p = get_ui_state_path()
        if p.exists():
            return
        # Suspend window_state writes while we assemble and write the
        # global snapshot so mirroring/update_window_data calls below
        # cannot trigger nested writes that overwrite restored state.
        try:
            _suspend_window_state_writes()
        except Exception:
            pass
        # Gather MainWindow data from provider or global config
        mw_data: Dict[str, Any] = {}
        try:
            if _UI_STATE_PROVIDER:
                try:
                    mw_data = (_UI_STATE_PROVIDER() or {})
                except Exception:
                    mw_data = {}
            if not mw_data:
                # fall back to reading global MainWindow state
                try:
                    glob = _load_global_ui_state() or {}
                    if isinstance(glob, dict):
                        maybe = glob.get("MainWindow")
                        if isinstance(maybe, dict):
                            mw_data = maybe.copy()
                except Exception:
                    pass
        except Exception:
            mw_data = {}

        # Build output: prefer provider MainWindow if available, otherwise
        # copy MainWindow from the global UI state; also copy any existing
        # top-level dock_/panel_ entries from the global config so the
        # per-save file is a more complete snapshot. Finally, mirror
        # dock_visibility into per-dock open flags for any docks missing
        # individual entries.
        out: Dict[str, Any] = {}
        try:
            # Attempt to read the full global UI state (may be empty)
            try:
                glob_all = _load_global_ui_state() or {}
            except Exception:
                glob_all = {}

            # MainWindow: prefer provider data if present
            if mw_data:
                out["MainWindow"] = mw_data.copy()
            else:
                maybe = (glob_all or {}).get("MainWindow")
                out["MainWindow"] = maybe.copy() if isinstance(maybe, dict) else {}

            # Copy any existing dock_/panel_ top-level entries from global
            if isinstance(glob_all, dict):
                for key, val in glob_all.items():
                    try:
                        if isinstance(key, str) and (key.startswith("dock_") or key.startswith("panel_")) and isinstance(val, dict):
                            out[key] = val.copy()
                    except Exception:
                        pass

            # Mirror dock_visibility into per-dock open flags for docks not
            # already present in the output
            try:
                vis = (out.get("MainWindow") or {}).get("dock_visibility") or {}
                if isinstance(vis, dict):
                    for obj_name, is_open in vis.items():
                        try:
                            if obj_name not in out:
                                out[obj_name] = {"open": bool(is_open)}
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            out = {"MainWindow": mw_data or {}}

        # If the snapshot is empty (no MainWindow data and no copied
        # top-level panel/dock entries), don't create the global file now.
        # In many cases the UI isn't fully initialized yet during save/create
        # flows; rely on the normal debounced SaveManager.write_ui_state to
        # persist the complete state once the UI is ready.
        try:
            mw = out.get("MainWindow") or {}
            other_keys = [k for k in out.keys() if k != "MainWindow"]
            has_content = bool(mw) or bool(other_keys)
        except Exception:
            has_content = False

        if not has_content:
            logger.debug("Skipping creation of global UI state: no snapshot data available yet")
            try:
                _resume_window_state_writes()
            except Exception:
                pass
            return

        # Ensure parent dir exists and write file
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, indent=2), encoding="utf-8")
            logger.debug("Created global UI state at %s; keys=%s", p, sorted(list(out.keys())))
        except Exception:
            logger.debug("Failed to create global UI state at %s", p)
        finally:
            try:
                _resume_window_state_writes()
            except Exception:
                pass

    @classmethod
    def _ensure_global_ui_state_present(cls, save_dir: Path) -> None:
        """Ensure a global UI state exists. If missing, attempt to obtain a
        full snapshot from the installed provider and persist it immediately
        (via update_window_data) so the config contains all readable fields
        when a new game is created or a save is loaded.
        """
        p_glob = get_ui_state_path()
        if p_glob.exists():
            return
        # Suspend window_state writes for the entire ensure/create flow so
        # provider mirroring and multiple update_window_data calls cannot
        # write partial state that would clobber a restored layout.
        try:
            _suspend_window_state_writes()
        except Exception:
            pass

        provider = _UI_STATE_PROVIDER
        got = None
        # Try calling the provider (expected to be run on the GUI thread).
        if provider:
            try:
                got = provider() or {}
            except Exception:
                got = None

        # If provider returned useful MainWindow data, persist it immediately.
        def _looks_complete(d: dict) -> bool:
            # Keys we expect for a complete snapshot
            expected = ("dock_visibility", "dock_order", "central_splitter_sizes", "galaxy_col_widths", "system_col_widths")
            for k in expected:
                if k in d:
                    return True
            return False

        if isinstance(got, dict) and got:
            try:
                # Persist MainWindow entry via update_window_data which writes
                # atomically to the global config.
                try:
                    update_window_data("MainWindow", got)
                except Exception:
                    # Fallback: write minimal wrapper if update fails
                    try:
                        p_glob.parent.mkdir(parents=True, exist_ok=True)
                        tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                        tmp.write_text(json.dumps({"MainWindow": got}, indent=2), encoding="utf-8")
                        tmp.replace(p_glob)
                    except Exception:
                        pass

                # Mirror dock_visibility into individual dock entries
                try:
                    vis = (got or {}).get("dock_visibility") or {}
                    if isinstance(vis, dict):
                        for obj_name, is_open in vis.items():
                            try:
                                update_window_data(obj_name, {"open": bool(is_open)})
                            except Exception:
                                pass
                except Exception:
                    pass

                logger.debug("Created global UI state via provider at %s", p_glob)

                # If the snapshot looks incomplete (e.g. only geometry),
                # try one more time after a short delay on the Qt event loop
                # so lazily-created docks/splitters have a chance to exist.
                try:
                    if not _looks_complete(got) and _QT_AVAILABLE and QApplication is not None and QApplication.instance() is not None:
                        def _retry():
                            try:
                                prov = _UI_STATE_PROVIDER
                                if not prov:
                                    return
                                new = prov() or {}
                                if isinstance(new, dict) and new:
                                    try:
                                        update_window_data("MainWindow", new)
                                    except Exception:
                                        try:
                                            tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                                            tmp.write_text(json.dumps({"MainWindow": new}, indent=2), encoding="utf-8")
                                            tmp.replace(p_glob)
                                        except Exception:
                                            pass
                                    try:
                                        vis = (new or {}).get("dock_visibility") or {}
                                        if isinstance(vis, dict):
                                            for obj_name, is_open in vis.items():
                                                try:
                                                    update_window_data(obj_name, {"open": bool(is_open)})
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        try:
                            # 100ms should be enough for lazy dock creation in most cases
                            # Cast QTimer to Any/Type to satisfy static checkers when
                            # PySide6 isn't present at type-check time.
                            qt_timer_cls = cast(Type[Any], QTimer)
                            qt_timer_cls.singleShot(100, _retry)
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    _resume_window_state_writes()
                except Exception:
                    pass
                return
            except Exception:
                try:
                    _resume_window_state_writes()
                except Exception:
                    pass

        # If provider was not available or returned nothing useful, try
        # merging any per-save ui_state.json into global so we don't lose
        # panel settings that live in the save folder.
        try:
            cls._merge_per_save_into_global(save_dir)
        except Exception:
            pass
        finally:
            try:
                _resume_window_state_writes()
            except Exception:
                pass

        # If we still don't have a global file, schedule a normal debounced
        # write so it will be created once the UI finishes initializing.
        try:
            if not p_glob.exists():
                cls.write_ui_state(save_dir)
        except Exception:
            pass

    @classmethod
    def _merge_per_save_into_global(cls, save_dir: Path) -> None:
        """If a per-save ui_state.json exists, merge any missing keys into
        the global UI state so data isn't left only in the save folder.
        This is intentionally conservative: existing global keys are not
        overwritten; only missing top-level keys or missing dict entries
        are copied.
        """
        per = cls._ui_state_path(save_dir)
        if not per.exists():
            return
        try:
            txt = per.read_text(encoding="utf-8")
            try:
                pdata = json.loads(txt) if txt else {}
            except Exception:
                pdata = {}
            if not isinstance(pdata, dict):
                return
        except Exception:
            return

        try:
            glob = _load_global_ui_state() or {}
        except Exception:
            glob = {}

        changed = False
        # Shallow merge: copy missing top-level keys; for dict values, copy
        # missing subkeys only.
        for key, val in pdata.items():
            try:
                if key not in glob:
                    glob[key] = val
                    changed = True
                else:
                    if isinstance(val, dict) and isinstance(glob.get(key), dict):
                        for subk, subv in val.items():
                            if subk not in glob[key]:
                                glob[key][subk] = subv
                                changed = True
            except Exception:
                pass

        if not changed:
            return

        # Persist merged entries by writing the merged global snapshot
        # atomically to avoid invoking update_window_data repeatedly which
        # can trigger loads/writes and cause write storms during startup.
        try:
            p_glob = get_ui_state_path()
            try:
                p_glob.parent.mkdir(parents=True, exist_ok=True)
                tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                tmp.write_text(json.dumps(glob, indent=2), encoding="utf-8")
                tmp.replace(p_glob)
                logger.debug("Persisted merged global UI state to %s", p_glob)
            except Exception:
                logger.exception("Failed to persist merged global UI state to %s", p_glob)
        except Exception:
            pass

    @classmethod
    def load_save(cls, save_dir: Path) -> None:
        db.close_active_connection()
        db_path = save_dir / "game.db"
        if not db_path.exists():
            raise FileNotFoundError(f"Save database not found: {db_path}")
        cls.set_active_save(save_dir)
        db.get_connection()
        
        # Update last played timestamp when loading a save
        meta_path = save_dir / "meta.json"
        meta = read_meta(meta_path)
        if meta:
            meta.last_played_iso = datetime.utcnow().isoformat()
            write_meta(meta_path, meta)
        
        # Ensure a global UI state file exists. If not, create one from the
        # active UI provider or the global MainWindow state so the config
        # has a snapshot of the current window/panel configuration.
        try:
            p_glob = get_ui_state_path()
            if not p_glob.exists():
                try:
                    cls._ensure_global_ui_state_present(save_dir)
                except Exception:
                    pass
        except Exception:
            pass

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
