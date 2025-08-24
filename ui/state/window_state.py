# /ui/state/window_state.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from PySide6.QtCore import QByteArray

from save.paths import get_ui_state_path


def _load_state() -> Dict[str, Any]:
    p = get_ui_state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(d: Dict[str, Any]) -> None:
    p = get_ui_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")


def save_mainwindow_state(win_id: str, geometry: QByteArray, state: QByteArray) -> None:
    d = _load_state()
    d[win_id] = d.get(win_id, {})
    # Use QByteArray's own base64 to avoid type-checker issues
    d[win_id]["geometry_b64"] = bytes(geometry.toBase64().data()).decode("ascii")
    d[win_id]["state_b64"] = bytes(state.toBase64().data()).decode("ascii")
    d[win_id]["open"] = True
    _save_state(d)


def restore_mainwindow_state(win, win_id: str) -> None:
    d = _load_state().get(win_id, {})
    try:
        gb64 = d.get("geometry_b64", "")
        sb64 = d.get("state_b64", "")
        if gb64:
            gb = QByteArray.fromBase64(gb64.encode("ascii"))
            win.restoreGeometry(gb)
        if sb64:
            sb = QByteArray.fromBase64(sb64.encode("ascii"))
            win.restoreState(sb)
    except Exception:
        pass


def set_window_open(win_id: str, is_open: bool) -> None:
    d = _load_state()
    d[win_id] = d.get(win_id, {})
    d[win_id]["open"] = bool(is_open)
    _save_state(d)


def is_window_open(win_id: str, default: bool = True) -> bool:
    d = _load_state().get(win_id, {})
    return bool(d.get("open", default))
