# /ui/state/main_window_state.py

from __future__ import annotations

from typing import Dict, Any, Optional, List
from PySide6.QtCore import QByteArray, Qt


def _collect_panel_state(panel) -> Optional[Dict[str, Any]]:
    """Capture list panel state (Category/Sort/Search/Column widths/Visible)."""
    if not panel:
        return None
    try:
        tree = getattr(panel, "tree", None)
        return {
            "visible": bool(panel.isVisible()),
            "category_index": int(getattr(panel, "category").currentIndex()) if hasattr(panel, "category") else 0,
            "sort_text": str(getattr(panel, "sort").currentText()) if hasattr(panel, "sort") else "",
            "search": str(getattr(panel, "search").text()) if hasattr(panel, "search") else "",
            "col_widths": [tree.columnWidth(i) for i in range(tree.columnCount())] if tree else [],
        }
    except Exception:
        return None


def _restore_panel_state(panel, state: Dict[str, Any]) -> None:
    """Restore list panel state captured by _collect_panel_state()."""
    if not panel or not isinstance(state, dict):
        return
    try:
        if "visible" in state:
            panel.setVisible(bool(state["visible"]))
    except Exception:
        pass
    try:
        if "category_index" in state and hasattr(panel, "category"):
            panel.category.setCurrentIndex(int(state["category_index"]))
    except Exception:
        pass
    try:
        if "sort_text" in state and hasattr(panel, "sort"):
            sort_text = state.get("sort_text")
            if isinstance(sort_text, str) and sort_text:
                i = panel.sort.findText(sort_text)
                if i >= 0:
                    panel.sort.setCurrentIndex(i)
                else:
                    # allow unknown/legacy values to still be applied
                    try:
                        panel.sort.setCurrentText(sort_text)
                    except Exception:
                        pass
    except Exception:
        pass
    try:
        if "search" in state and hasattr(panel, "search"):
            panel.search.setText(str(state.get("search", "")))
    except Exception:
        pass
    try:
        widths = state.get("col_widths")
        if isinstance(widths, list):
            tree = getattr(panel, "tree", None)
            if tree:
                for i, w in enumerate(widths):
                    try:
                        tree.setColumnWidth(i, int(w))
                    except Exception:
                        continue
    except Exception:
        pass


def collect(win) -> Dict[str, Any]:
    """
    Capture per-save UI state for the current MainWindow instance.
    Stored via SaveManager (NOT the global window_state).
    """
    state: Dict[str, Any] = {}

    # Geometry/state snapshot (helpful when swapping saves on multi-monitor rigs)
    try:
        geo_hex = bytes(win.saveGeometry().toHex().data()).decode("ascii")
        sta_hex = bytes(win.saveState().toHex().data()).decode("ascii")
        state["main_geometry_hex"] = geo_hex
        state["main_state_hex"] = sta_hex
    except Exception:
        pass

    # Splitter sizes
    try:
        if getattr(win, "_central_splitter", None):
            state["central_splitter_sizes"] = list(win._central_splitter.sizes())
    except Exception:
        pass

    # Map tab index
    try:
        tabs = getattr(win, "_map_view", None)
        tabs = getattr(tabs, "tabs", None) if tabs else None
        state["map_tab_index"] = int(tabs.currentIndex()) if tabs else 0
    except Exception:
        state["map_tab_index"] = 0

    # Leader line style (prefs)
    try:
        prefs = getattr(win, "leader_prefs", None)
        if prefs:
            state["leader_color"] = prefs.color.name()
            state["leader_width"] = int(prefs.width)
            state["leader_glow"]  = bool(prefs.glow)
    except Exception:
        pass

    # ---- Panels (new: capture BOTH if present) ----
    try:
        # Preferred names in the new split UI:
        panel_system = getattr(win, "location_panel_system",  None)
        panel_galaxy = getattr(win, "location_panel_galaxy", None)

        # Back-compat: some builds still expose a single 'location_panel'
        legacy_panel = getattr(win, "location_panel", None)

        system_state  = _collect_panel_state(panel_system)  or _collect_panel_state(legacy_panel)
        galaxy_state = _collect_panel_state(panel_galaxy)

        if system_state:
            state["panel_system"] = system_state
        if galaxy_state:
            state["panel_galaxy"] = galaxy_state

        # Also keep legacy keys for older restores
        if legacy_panel and "panel_system" not in state:
            state["panel_legacy"] = system_state or {}
    except Exception:
        pass

    return state


def restore(win, state: Dict[str, Any]) -> None:
    """Restore a previously captured per-save UI state to the MainWindow."""
    # Geometry/state
    try:
        geo_hex = state.get("main_geometry_hex")
        sta_hex = state.get("main_state_hex")
        if isinstance(geo_hex, str) and geo_hex:
            win.restoreGeometry(QByteArray.fromHex(geo_hex.encode("ascii")))
        if isinstance(sta_hex, str) and sta_hex:
            win.restoreState(QByteArray.fromHex(sta_hex.encode("ascii")))
    except Exception:
        pass

    # Splitter sizes
    try:
        sizes = state.get("central_splitter_sizes")
        if sizes and getattr(win, "_central_splitter", None):
            win._central_splitter.setSizes([int(x) for x in sizes])
    except Exception:
        pass

    # Map tab index
    try:
        idx = int(state.get("map_tab_index", 0))
        tabs = getattr(win, "_map_view", None)
        tabs = getattr(tabs, "tabs", None) if tabs else None
        if tabs:
            tabs.setCurrentIndex(max(0, min(tabs.count() - 1, idx)))
    except Exception:
        pass

    # Leader line prefs
    try:
        prefs = getattr(win, "leader_prefs", None)
        if prefs:
            c = state.get("leader_color")
            if isinstance(c, str) and c:
                from PySide6.QtGui import QColor
                prefs.color = QColor(c)
            prefs.width = max(1, int(state.get("leader_width", prefs.width)))
            prefs.glow  = bool(state.get("leader_glow", prefs.glow))
            prefs.apply_to(getattr(win, "lead", None))
            if getattr(win, "act_leader_glow", None):
                win.act_leader_glow.setChecked(bool(prefs.glow))
    except Exception:
        pass

    # ---- Panels (new: restore BOTH if present) ----
    try:
        panel_system  = getattr(win, "location_panel_system",  None)
        panel_galaxy = getattr(win, "location_panel_galaxy", None)
        legacy_panel = getattr(win, "location_panel", None)

        system_state  = state.get("panel_system")
        galaxy_state = state.get("panel_galaxy")

        if system_state:
            _restore_panel_state(panel_system or legacy_panel, system_state)
        elif "panel_legacy" in state:
            _restore_panel_state(legacy_panel, state.get("panel_legacy", {}))

        if galaxy_state:
            _restore_panel_state(panel_galaxy, galaxy_state)
    except Exception:
        pass
