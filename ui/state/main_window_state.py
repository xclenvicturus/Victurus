# /ui/state/main_window_state.py

from __future__ import annotations

from typing import Dict, Any, Optional, List
from PySide6.QtCore import QByteArray, Qt

def collect(win) -> Dict[str, Any]:
    """
    Capture per-save UI state for the current MainWindow instance.
    This is stored via SaveManager (NOT the global window_state).
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
        tabs = getattr(win._map_view, "tabs", None)
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

    # Location List visibility + settings
    try:
        panel = getattr(win, "location_panel", None)
        state["location_list_visible"] = bool(panel.isVisible()) if panel else True
        if panel:
            state["panel_category_index"] = int(panel.category.currentIndex())
            state["panel_sort_text"]     = str(panel.sort.currentText())
            state["panel_search"]        = str(panel.search.text())
            tree = panel.tree
            state["panel_col_widths"]    = [tree.columnWidth(i) for i in range(tree.columnCount())]
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
        tabs = getattr(win._map_view, "tabs", None)
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

    # Location List visibility + settings
    try:
        panel = getattr(win, "location_panel", None)
        if panel:
            vis = state.get("location_list_visible", True)
            panel.setVisible(bool(vis))

            cat_idx = int(state.get("panel_category_index", 0))
            panel.category.setCurrentIndex(cat_idx)

            sort_text = state.get("panel_sort_text")
            if isinstance(sort_text, str) and sort_text:
                i = panel.sort.findText(sort_text)
                if i >= 0:
                    panel.sort.setCurrentIndex(i)

            panel.search.setText(str(state.get("panel_search", "")))

            widths = state.get("panel_col_widths")
            if isinstance(widths, list):
                tree = panel.tree
                for i, w in enumerate(widths):
                    try:
                        tree.setColumnWidth(i, int(w))
                    except Exception:
                        pass
    except Exception:
        pass
