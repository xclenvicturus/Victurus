from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable

SETTINGS_FILE = "user_settings.json"

def user_settings_path() -> Path:
    home = Path.home()
    docs = home / "Documents"
    if not docs.exists():
        docs = home / "My Documents"
    base = docs / "Victurus_Game"
    base.mkdir(parents=True, exist_ok=True)
    return base / SETTINGS_FILE

class Settings:
    def __init__(self):
        self._path = user_settings_path()
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def save(self):
        try:
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---- window persistence ----
    def get_window(self, win_id: str) -> Dict[str, Any]:
        return self._data.setdefault("windows", {}).setdefault(win_id, {})

    def set_window(self, win_id: str, **kwargs):
        w = self._data.setdefault("windows", {}).setdefault(win_id, {})
        w.update({k: v for k, v in kwargs.items() if v is not None})
        self.save()

    def list_open_windows(self):
        wins = self._data.get("windows", {})
        return [wid for wid, meta in wins.items() if meta.get("is_open")]

class WindowStateManager:
    """Attach to Toplevel windows to persist geometry, 'topmost', and open/close state."""
    def __init__(self, settings: Settings):
        self.settings = settings

    def bind(self, win, win_id: str, on_close: Optional[Callable[[], None]] = None):
        meta = self.settings.get_window(win_id)
        geom = meta.get("geometry")
        if geom:
            try:
                win.geometry(geom)
            except Exception:
                pass
        topmost = bool(meta.get("always_on_top", False))
        try:
            win.wm_attributes("-topmost", topmost)
        except Exception:
            pass

        # mark open
        self.settings.set_window(win_id, is_open=True)

        # listen for move/resize
        def on_configure(_evt=None):
            try:
                self.settings.set_window(win_id, geometry=win.geometry())
            except Exception:
                pass

        def on_close_cb():
            self.settings.set_window(win_id, is_open=False, geometry=win.geometry())
            try:
                if on_close:
                    on_close()
            finally:
                win.destroy()

        win.bind("<Configure>", on_configure)
        win.protocol("WM_DELETE_WINDOW", on_close_cb)

    def set_topmost(self, win, win_id: str, value: bool):
        try:
            win.wm_attributes("-topmost", bool(value))
        except Exception:
            pass
        self.settings.set_window(win_id, always_on_top=bool(value))
