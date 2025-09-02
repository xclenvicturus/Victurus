# /ui/state/window_state.py
"""
Window State Management

Handles persistence and restoration of window geometry, dock layouts, and other
UI state information to maintain user preferences across sessions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtCore import QByteArray

from save.paths import get_ui_state_path
import logging
import inspect
from save.ui_state_tracer import append_event

log = logging.getLogger(__name__)


# ---------- file i/o helpers ----------

def _load_state() -> Dict[str, Any]:
    p = get_ui_state_path()
    if not p.exists():
        return {}
    try:
        txt = p.read_text(encoding="utf-8")
        try:
            d = json.loads(txt)
        except Exception:
            raise
        return d
    except Exception:
        # Corrupt file: keep a backup for inspection and start fresh
        try:
            p.rename(p.with_suffix(p.suffix + ".bak"))
        except Exception:
            pass
        return {}


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _save_state(d: Dict[str, Any]) -> None:
    # If writes are suspended (e.g. during programmatic restore/close), don't
    # persist anything to disk. This prevents transient programmatic UI changes
    # from overwriting the user's last explicit settings.
    try:
        if _suspend_writes:
            try:
                caller = inspect.stack()[1]
                append_event("_save_state_suppressed", f"{caller.filename}:{caller.lineno}")
            except Exception:
                append_event("_save_state_suppressed")
            return
    except NameError:
        # _suspend_writes is defined below; defensive fallback
        pass

    p = get_ui_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            _atomic_write_text(p, json.dumps(d, indent=2))
        except Exception:
            raise
    except Exception:
        # Fall back to direct write if atomic write fails on this FS
        try:
            p.write_text(json.dumps(d, indent=2), encoding="utf-8")
        except Exception:
            pass


# Module-level suspend flag to prevent writes when callers (e.g. SaveManager)
# want to temporarily suppress persistence (during restores or shutdown).
_suspend_writes: bool = False

# Internal flag set when the caller is an explicit user-driven action.
# When False, update_window_data will not overwrite an existing global
# ui_state.json (prevents automatic startup code from clobbering user
# preferences).
_user_write: bool = False


def suspend_writes() -> None:
    """Temporarily disable writing to the global UI state file."""
    global _suspend_writes
    _suspend_writes = True
    try:
        caller = inspect.stack()[1]
        append_event("suspend_writes", f"{caller.filename}:{caller.lineno}")
    except Exception:
        append_event("suspend_writes")


def resume_writes() -> None:
    """Re-enable writing to the global UI state file."""
    global _suspend_writes
    _suspend_writes = False
    try:
        caller = inspect.stack()[1]
        append_event("resume_writes", f"{caller.filename}:{caller.lineno}")
    except Exception:
        append_event("resume_writes")


def writes_suspended() -> bool:
    return bool(_suspend_writes)


# ---------- QByteArray enc/dec helpers (with back-compat) ----------

def _encode_qba_base64(qba: QByteArray) -> str:
    """Return ASCII base64 for a QByteArray."""
    try:
        return bytes(qba.toBase64().data()).decode("ascii")
    except Exception:
        # Extremely defensive: last-ditch hex
        return bytes(qba.toHex().data()).decode("ascii")


def _decode_qba_maybe(s: Optional[str]) -> Optional[QByteArray]:
    """
    Best-effort decode: prefer base64; if that fails, try hex (for legacy files).
    Returns a QByteArray or None if s is falsy / invalid.
    """
    if not isinstance(s, str) or not s:
        return None
    # Try base64
    try:
        q = QByteArray.fromBase64(s.encode("ascii"))
        if not q.isEmpty():
            return q
    except Exception:
        pass
    # Try hex
    try:
        q = QByteArray.fromHex(s.encode("ascii"))
        if not q.isEmpty():
            return q
    except Exception:
        pass
    return None


# ---------- public api ----------

def save_mainwindow_state(win_id: str, geometry: QByteArray, state: QByteArray) -> None:
    """
    Persist a window's geometry/state globally (not per-save).
    Uses base64 for robustness across platforms and PySide versions.
    """
    # Persist only a human-readable numeric geometry (x/y/w/h/maximized)
    # to keep the config editable. Avoid writing raw hex/base64 blobs. The
    # MainWindow callers already update numeric geometry via
    # update_window_data; this function remains for compatibility but will
    # simply mark the window as open.
    # Avoid writing raw geometry/state here. Only mark the window as open
    # via update_window_data; this call will be suppressed when the global
    # ui_state.json already exists unless the caller is explicitly
    # user-driven.
    try:
        update_window_data(win_id, {"open": True})
    except Exception:
        # Fallback minimal write (only when absolutely necessary)
        try:
            d = _load_state()
            d[win_id] = d.get(win_id, {})
            d[win_id]["open"] = True
            _save_state(d)
        except Exception:
            pass


def restore_mainwindow_state(win, win_id: str) -> None:
    """
    Restore a window's geometry/state.
    Backward compatible with older files that may have stored hex as
    'geometry_hex' / 'state_hex'.
    """
    w = _load_state().get(win_id, {})

    # Prefer human-readable numeric geometry if present (new format).
    try:
        mg = w.get('main_geometry')
        if isinstance(mg, dict):
            try:
                x = int(mg.get('x', 0))
                y = int(mg.get('y', 0))
                wdt = int(mg.get('w', 800))
                hgt = int(mg.get('h', 600))
                win.setGeometry(x, y, wdt, hgt)
                if bool(mg.get('maximized', False)):
                    try:
                        win.showMaximized()
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    # Legacy fallback: restore from stored QByteArray (hex/base64)
    gb = _decode_qba_maybe(w.get("geometry_b64")) or _decode_qba_maybe(w.get("geometry_hex"))
    sb = (_decode_qba_maybe(w.get("main_state_b64")) or 
          _decode_qba_maybe(w.get("main_state_hex")) or
          _decode_qba_maybe(w.get("state_b64")) or 
          _decode_qba_maybe(w.get("state_hex")))

    try:
        if gb is not None and not gb.isEmpty():
            try:
                win.restoreGeometry(gb)
            except Exception:
                pass
    except Exception:
        pass
    try:
        if sb is not None and not sb.isEmpty():
            try:
                win.restoreState(sb)
            except Exception:
                pass
    except Exception:
        pass


def set_window_open(win_id: str, is_open: bool) -> None:
    # Treat dock/window open flags as user-driven when triggered by UI
    # visibility changes. Use the user_update_window_data helper so the
    # write path respects the user's intent. If writes are suspended
    # (programmatic restore/close), this will be suppressed.
    try:
        user_update_window_data(win_id, {"open": bool(is_open)})
    except Exception:
        # Fallback: merge into loaded state and attempt to save (will be
        # suppressed if writes are suspended or global file exists).
        d = _load_state()
        d[win_id] = d.get(win_id, {})
        d[win_id]["open"] = bool(is_open)
        _save_state(d)


def is_window_open(win_id: str, default: bool = True) -> bool:
    w = _load_state().get(win_id, {})
    return bool(w.get("open", default))


def update_window_data(win_id: str, data: Dict[str, Any]) -> None:
    """
    Merge the provided data into the stored entry for win_id and persist to
    the global UI state file (ui_windows.json). This is a small helper used
    by UI components to save their per-window/panel settings immediately.
    """
    if not isinstance(data, dict):
        return
    # If a global ui_state.json already exists and this is not an
    # explicit user-driven update, do not modify the file. This ensures
    # startup flows and automatic provider writes cannot overwrite an
    # existing user config. However, if the incoming data contains
    # layout-related keys (dock_layout, dock_visibility, splitter sizes,
    # or per-panel column widths) we allow the write so provider snapshots
    # can merge useful UI layout metadata into the global config even
    # when it already exists. This keeps per-dock numeric geometry in
    # the global file without requiring explicit user actions.
    try:
        p = get_ui_state_path()
        if p.exists() and not _user_write:
            try:
                # Permit writes that contain full-layout keys so provider
                # snapshots can populate dock entries even if the global
                # file already exists. Otherwise suppress to avoid
                # clobbering user configs.
                allow_keys = {
                    "dock_layout",
                    "dock_visibility",
                    "central_splitter_sizes",
                    "right_splitter_sizes",
                    "galaxy_col_widths",
                    "system_col_widths",
                }
                data_keys = set(data.keys()) if isinstance(data, dict) else set()
                if not (data_keys & allow_keys):
                    return
            except Exception:
                return
    except Exception:
        pass

    d = _load_state()
    d[win_id] = d.get(win_id, {})
    try:
        d[win_id].update(data)
        # If caller provided a human-readable main_geometry, remove legacy
        # binary/hex fields so the config remains readable.
        try:
            if "main_geometry" in data:
                for legacy in ("geometry_b64", "state_b64", "main_geometry_hex", "main_state_hex"):
                    if legacy in d[win_id]:
                        d[win_id].pop(legacy, None)
        except Exception:
            pass
    except Exception:
        # Defensive: ensure we don't crash UI on save errors
        pass
    _save_state(d)


def user_update_window_data(win_id: str, data: Dict[str, Any]) -> None:
    """
    Persist a window's data to the global UI state and force the write
    even if the global file already exists. This should be called only
    from user-driven event handlers (move/resize/menu toggles etc.).
    """
    global _user_write
    
    # Disable legacy system when new UIStateManager is active
    try:
        from ui.state.ui_state_manager import get_ui_state_manager
        ui_manager = get_ui_state_manager()
        if ui_manager:
            # New system is active, skip legacy saves
            try:
                caller = inspect.stack()[1]
                append_event("user_update_window_data_skipped", f"{caller.filename}:{caller.lineno}")
            except Exception:
                append_event("user_update_window_data_skipped")
            return
    except Exception:
        # If new system not available, continue with legacy system
        pass
    
    # Respect suspended writes: if writes are suspended, do not persist.
    try:
        if _suspend_writes:
            try:
                caller = inspect.stack()[1]
                append_event("user_update_window_data_suppressed", f"{win_id} {caller.filename}:{caller.lineno}")
            except Exception:
                append_event("user_update_window_data_suppressed", win_id)
            return
    except Exception:
        pass

    try:
        _user_write = True
        update_window_data(win_id, data)
    finally:
        _user_write = False
