from __future__ import annotations

from typing import Callable, Dict, Any, Optional, Type, Any as TypingAny, cast
from pathlib import Path
import json
import logging

from PySide6.QtCore import QTimer

from ui.state.window_state import _load_state as _load_global_ui_state
from save.paths import get_ui_state_path

log = logging.getLogger(__name__)

# Provider installed by the UI (usually MainWindow._collect_ui_state)
_UI_STATE_PROVIDER: Optional[Callable[[], Dict[str, Any]]] = None


def install_ui_state_provider(fn: Callable[[], Dict[str, Any]]) -> None:
    global _UI_STATE_PROVIDER
    _UI_STATE_PROVIDER = fn


def _load_global() -> Dict[str, Any]:
    try:
        return _load_global_ui_state() or {}
    except Exception:
        return {}


def ensure_global_ui_state_present(save_dir: Path) -> None:
    """Ensure a full global ui_state.json exists. If missing, call the
    installed provider (if any) and persist its snapshot immediately. If
    the provider is not ready, merge per-save ui_state.json into global
    and schedule a delayed retry.
    """
    p_glob = Path.cwd() / "Config" / "ui_state.json"
    try:
        # Prefer project helper if available
        from save.paths import get_ui_state_path
        p_glob = get_ui_state_path()
    except Exception:
        pass

    if p_glob.exists():
        return

    provider = _UI_STATE_PROVIDER
    snap = None
    if provider:
        try:
            snap = provider() or {}
        except Exception:
            snap = None

    if isinstance(snap, dict) and snap:
        try:
            # Assemble a single global snapshot and write atomically to avoid
            # invoking update_window_data (which can trigger loads/writes)
            out = {"MainWindow": snap.copy()}
            try:
                vis = (snap or {}).get("dock_visibility") or {}
                if isinstance(vis, dict):
                    for obj_name, is_open in vis.items():
                        if obj_name not in out:
                            out[obj_name] = {"open": bool(is_open)}
            except Exception:
                pass
            try:
                dock_layout = (snap or {}).get("dock_layout") or {}
                if isinstance(dock_layout, dict):
                    for obj_name, layout in dock_layout.items():
                        try:
                            out[obj_name] = layout if isinstance(layout, dict) else {"open": bool(layout)}
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                p_glob.parent.mkdir(parents=True, exist_ok=True)
                tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
                tmp.replace(p_glob)
            except Exception:
                pass
            # If snapshot looks incomplete, schedule a short retry on the
            # Qt event loop to allow lazy UI parts to initialize.
            def _looks_complete(d: Dict[str, Any]) -> bool:
                for k in ("dock_visibility", "dock_order", "central_splitter_sizes", "galaxy_col_widths", "system_col_widths"):
                    if k in d:
                        return True
                return False

            if not _looks_complete(snap):
                try:
                    qt_timer_cls = cast(Type[TypingAny], QTimer)
                    qt_timer_cls.singleShot(100, lambda: persist_provider_snapshot())
                except Exception:
                    pass
            return
        except Exception:
            pass

    # fallback: merge per-save into global if present
    try:
        per = save_dir / "ui_state.json"
        if per.exists():
            try:
                txt = per.read_text(encoding="utf-8")
                pdata = json.loads(txt) if txt else {}
            except Exception:
                pdata = {}
            if isinstance(pdata, dict):
                # shallow merge missing keys and write the merged global
                glob = _load_global() or {}
                changed = False
                for key, val in pdata.items():
                    if key not in glob:
                        glob[key] = val
                        changed = True
                    elif isinstance(val, dict) and isinstance(glob.get(key), dict):
                        for subk, subv in val.items():
                            if subk not in glob[key]:
                                glob[key][subk] = subv
                                changed = True
                if changed:
                    try:
                        p_glob.parent.mkdir(parents=True, exist_ok=True)
                        tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
                        tmp.write_text(json.dumps(glob, indent=2), encoding="utf-8")
                        tmp.replace(p_glob)
                    except Exception:
                        log.exception("Failed to persist merged global UI state to %s", p_glob)
    except Exception:
        pass

    # final fallback: schedule a provider write later
    try:
        if provider:
            qt = QTimer
            try:
                qt.singleShot(200, lambda: persist_provider_snapshot())
            except Exception:
                try:
                    persist_provider_snapshot()
                except Exception:
                    pass
    except Exception:
        pass


def persist_provider_snapshot() -> None:
    """Call the installed provider and persist its data immediately via
    update_window_data (atomic write)."""
    provider = _UI_STATE_PROVIDER
    if not provider:
        return
    # Do not overwrite an existing global config. Only create/persist a
    # snapshot when no global file exists (first-run/new-game) or when the
    # caller explicitly intends to initialize the config.
    try:
        from save.paths import get_ui_state_path
        p_glob = get_ui_state_path()
        if p_glob.exists():
            return
    except Exception:
        p_glob = Path.cwd() / "Config" / "ui_state.json"
    try:
        snap = provider() or {}
    except Exception:
        snap = {}
    if not isinstance(snap, dict) or not snap:
        return
    try:
        # Assemble and write atomically to avoid calling update_window_data
        out = {"MainWindow": snap.copy()}
        try:
            vis = (snap or {}).get("dock_visibility") or {}
            if isinstance(vis, dict):
                for obj_name, is_open in vis.items():
                    if obj_name not in out:
                        out[obj_name] = {"open": bool(is_open)}
        except Exception:
            pass
        try:
            p_glob.parent.mkdir(parents=True, exist_ok=True)
            tmp = p_glob.with_suffix(p_glob.suffix + ".tmp")
            tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
            tmp.replace(p_glob)
        except Exception:
            log.exception("Failed to persist provider snapshot to %s", p_glob)
    except Exception:
        pass
