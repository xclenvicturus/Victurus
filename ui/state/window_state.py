# /ui/state/window_state.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtCore import QByteArray

from save.paths import get_ui_state_path


# ---------- file i/o helpers ----------

def _load_state() -> Dict[str, Any]:
    p = get_ui_state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
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
    p = get_ui_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_write_text(p, json.dumps(d, indent=2))
    except Exception:
        # Fall back to direct write if atomic write fails on this FS
        p.write_text(json.dumps(d, indent=2), encoding="utf-8")


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
    d = _load_state()
    d[win_id] = d.get(win_id, {})
    d[win_id]["geometry_b64"] = _encode_qba_base64(geometry)
    d[win_id]["state_b64"] = _encode_qba_base64(state)
    d[win_id]["open"] = True
    _save_state(d)


def restore_mainwindow_state(win, win_id: str) -> None:
    """
    Restore a window's geometry/state.
    Backward compatible with older files that may have stored hex as
    'geometry_hex' / 'state_hex'.
    """
    w = _load_state().get(win_id, {})

    gb = _decode_qba_maybe(w.get("geometry_b64")) or _decode_qba_maybe(w.get("geometry_hex"))
    sb = _decode_qba_maybe(w.get("state_b64")) or _decode_qba_maybe(w.get("state_hex"))

    try:
        if gb is not None and not gb.isEmpty():
            win.restoreGeometry(gb)
    except Exception:
        pass
    try:
        if sb is not None and not sb.isEmpty():
            win.restoreState(sb)
    except Exception:
        pass


def set_window_open(win_id: str, is_open: bool) -> None:
    d = _load_state()
    d[win_id] = d.get(win_id, {})
    d[win_id]["open"] = bool(is_open)
    _save_state(d)


def is_window_open(win_id: str, default: bool = True) -> bool:
    w = _load_state().get(win_id, {})
    return bool(w.get("open", default))
