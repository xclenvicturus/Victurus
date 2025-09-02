# /ui/menus/view_menu.py

"""
View Menu System

Handles panel visibility controls, including Show All/Hide All functionality
for docks, log panels, and other UI components with proper state synchronization.
"""

from __future__ import annotations

from typing import Protocol, Optional, cast, Any, Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget, QDockWidget


# ---- Structural type for MainWindow so Pylance knows these attrs exist ----
class _MainWindowLike(Protocol):
    def menuBar(self) -> QMenuBar: ...
    # docks (status may be created lazily)
    status_dock: Optional[QDockWidget]
    log_dock: Optional[QDockWidget]
    # location panels (split UI)
    location_panel_galaxy: Optional[QWidget]
    location_panel_system: Optional[QWidget]
    # legacy single panel (optional)
    location_panel: Optional[QWidget]
    # actions set up by this module
    act_panel_status: Optional[QAction]
    act_panel_location_galaxy: Optional[QAction]
    act_panel_location_system: Optional[QAction]
    act_panel_location: Optional[QAction]
    # legacy global leader-line toggle
    act_leader_glow: Optional[QAction]
    # new per-line toggles (if present)
    act_system_leader_glow: Optional[QAction]
    act_galaxy_leader_glow: Optional[QAction]


# ---------- helpers ----------

def _menu_bar(win: _MainWindowLike) -> QMenuBar:
    """Return the window's QMenuBar with a concrete type for linters."""
    return cast(QMenuBar, win.menuBar())


def _ensure_view_menu(win: _MainWindowLike) -> QMenu:
    """Find an existing '&View' menu or create one (typed for Pylance)."""
    mb = _menu_bar(win)
    for act in mb.actions():
        m = act.menu()
        if isinstance(m, QMenu) and act.text().replace("&", "").lower() == "view":
            return m
    # QMenuBar.addMenu returns QMenu in PySide6
    return mb.addMenu("&View")


def _checked_visible(w: Optional[QWidget]) -> bool:
    return bool(w and w.isVisible())


# ---------- public API ----------

def sync_panels_menu_state(win: _MainWindowLike) -> None:
    """Reflect actual widget visibility into the Panels submenu actions."""
    # Status dock (may not exist yet)
    act = getattr(win, "act_panel_status", None)
    dock = getattr(win, "status_dock", None)
    if isinstance(act, QAction):
        try:
            act.blockSignals(True)
            act.setEnabled(isinstance(dock, QDockWidget))
            act.setChecked(_checked_visible(dock))
        finally:
            act.blockSignals(False)

    # Per-category log actions (if installed by install_view_menu_extras)
    try:
        act_map = getattr(win, "_act_log_categories", None)
        if isinstance(act_map, dict):
            for cat, action in act_map.items():
                try:
                    action.blockSignals(True)
                    # find corresponding dock in window._log_docks (created lazily)
                    dock = None
                    try:
                        dock = getattr(win, "_log_docks", {}).get(cat)
                    except Exception:
                        dock = None
                    # Disable if dock doesn't exist yet (consistent with other panels)
                    action.setEnabled(isinstance(dock, QDockWidget))
                    action.setChecked(_checked_visible(dock))
                finally:
                    try:
                        action.blockSignals(False)
                    except Exception:
                        pass
    except Exception:
        pass

    # Galaxy list (top)
    act = getattr(win, "act_panel_location_galaxy", None)
    panel = getattr(win, "location_panel_galaxy", None)
    if isinstance(act, QAction):
        try:
            act.blockSignals(True)
            act.setEnabled(isinstance(panel, QWidget))
            act.setChecked(_checked_visible(panel))
        finally:
            act.blockSignals(False)

    # System list (bottom)
    act = getattr(win, "act_panel_location_system", None)
    panel = getattr(win, "location_panel_system", None)
    if isinstance(act, QAction):
        try:
            act.blockSignals(True)
            act.setEnabled(isinstance(panel, QWidget))
            act.setChecked(_checked_visible(panel))
        finally:
            act.blockSignals(False)

    # Legacy single list (optional)
    act = getattr(win, "act_panel_location", None)
    panel = getattr(win, "location_panel", None)
    if isinstance(act, QAction):
        try:
            act.blockSignals(True)
            act.setEnabled(isinstance(panel, QWidget))
            act.setChecked(_checked_visible(panel))
        finally:
            act.blockSignals(False)


def install_view_menu_extras(win: _MainWindowLike, prefs: Any) -> None:
    """
    Create View → Panels submenu, and leader-line controls.

    Backwards compatible:
      • Always installs legacy "Leader Line" submenu using `prefs` (single set).
      • If the MainWindow exposes per-line handlers, also installs separate
        "Galaxy Leader Line" and "System Leader Line" submenus with independent
        color/width/glow controls.
    """
    view_menu = _ensure_view_menu(win)

    # Add debug/error menu items
    view_menu.addSeparator()
    
    # Error logs menu
    debug_menu = QMenu("Debug", view_menu)
    view_menu.addMenu(debug_menu)
    
    def _open_log_folder():
        """Open the logs folder in the file explorer"""
        try:
            import os
            import subprocess
            import platform
            from pathlib import Path
            
            log_dir = Path(__file__).resolve().parents[2] / "logs"
            log_dir.mkdir(exist_ok=True)
            
            system = platform.system()
            if system == "Windows":
                os.startfile(log_dir)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(log_dir)])
            else:  # Linux and others
                subprocess.run(["xdg-open", str(log_dir)])
        except Exception as e:
            from ui.error_handler import handle_error
            handle_error(e, "Opening log folder")
    
    def _trigger_test_error():
        """Trigger a test error to verify error handling"""
        from ui.error_handler import handle_error
        test_error = RuntimeError("This is a test error to verify the error reporting system works correctly.")
        handle_error(test_error, "Test error from Debug menu")
    
    def _show_system_info():
        """Show system information dialog"""
        try:
            from PySide6.QtWidgets import QMessageBox
            import platform
            import sys
            
            info_text = f"""System Information:
            
Python Version: {sys.version}
Platform: {platform.platform()}
System: {platform.system()} {platform.release()}
Architecture: {platform.architecture()[0]}
Machine: {platform.machine()}
Processor: {platform.processor()}

PySide6 Version: {getattr(__import__('PySide6'), '__version__', 'Unknown')}
Application: Victurus"""
            
            QMessageBox.information(cast(QWidget, win), "System Information", info_text)
        except Exception as e:
            from ui.error_handler import handle_error
            handle_error(e, "Showing system information")
    
    act_logs = QAction("Open Log Folder", debug_menu)
    act_logs.triggered.connect(_open_log_folder)
    debug_menu.addAction(act_logs)
    
    act_test_error = QAction("Test Error Handler", debug_menu)
    act_test_error.triggered.connect(_trigger_test_error)
    debug_menu.addAction(act_test_error)
    
    act_system_info = QAction("System Information", debug_menu)
    act_system_info.triggered.connect(_show_system_info)
    debug_menu.addAction(act_system_info)
    
    view_menu.addSeparator()

    # ---------- Optional: separate per-line submenus ----------
    def _maybe_bool(obj: Any, default: bool = True) -> bool:
        try:
            return bool(obj)
        except Exception:
            return default

    # Helpers: discover handlers and state on the window
    has_gal_handlers = all(
        hasattr(win, name) for name in (
            "_pick_galaxy_leader_color", "_pick_galaxy_leader_width", "_set_galaxy_leader_glow"
        )
    )
    has_sys_handlers = all(
        hasattr(win, name) for name in (
            "_pick_system_leader_color", "_pick_system_leader_width", "_set_system_leader_glow"
        )
    )

    # Try to read current glow state from window prefs if available
    gal_glow_now = _maybe_bool(getattr(getattr(win, "_galaxy_ll_prefs", None), "glow", True), True)
    sys_glow_now = _maybe_bool(getattr(getattr(win, "_system_ll_prefs", None), "glow", True), True)

    if has_gal_handlers:
        gal_menu = view_menu.addMenu("Galaxy Leader Line")
        act_gal_color = gal_menu.addAction("Pick Color…")
        act_gal_color.triggered.connect(getattr(win, "_pick_galaxy_leader_color"))
        act_gal_width = gal_menu.addAction("Set Width…")
        act_gal_width.triggered.connect(getattr(win, "_pick_galaxy_leader_width"))
        act_gal_glow = gal_menu.addAction("Glow")
        act_gal_glow.setCheckable(True)
        act_gal_glow.setChecked(gal_glow_now)
        act_gal_glow.toggled.connect(getattr(win, "_set_galaxy_leader_glow"))
        # expose handle for state restore
        win.act_galaxy_leader_glow = act_gal_glow  # type: ignore[attr-defined]

    if has_sys_handlers:
        sys_menu = view_menu.addMenu("System Leader Line")
        act_sys_color = sys_menu.addAction("Pick Color…")
        act_sys_color.triggered.connect(getattr(win, "_pick_system_leader_color"))
        act_sys_width = sys_menu.addAction("Set Width…")
        act_sys_width.triggered.connect(getattr(win, "_pick_system_leader_width"))
        act_sys_glow = sys_menu.addAction("Glow")
        act_sys_glow.setCheckable(True)
        act_sys_glow.setChecked(sys_glow_now)
        act_sys_glow.toggled.connect(getattr(win, "_set_system_leader_glow"))
        # expose handle for state restore
        win.act_system_leader_glow = act_sys_glow  # type: ignore[attr-defined]

    # ---------- Panels submenu ----------
    panels = QMenu("Panels", view_menu)
    view_menu.addMenu(panels)

    def _toggle(getter: Callable[[], Optional[QWidget]]):
        def _fn(visible: bool):
            w = getter()
            # If the widget is inside a QDockWidget, toggle the dock instead
            try:
                if isinstance(w, QWidget):
                    # prefer parent dock if present
                    parent = getattr(w, 'parent', None)
                    dock = None
                    try:
                        # some widgets may expose parent() method
                        p = w.parent() if callable(getattr(w, 'parent', None)) else None
                        if isinstance(p, QDockWidget):
                            dock = p
                    except Exception:
                        dock = None
                    if isinstance(dock, QDockWidget):
                        try:
                            dock.setVisible(bool(visible))
                        except Exception:
                            pass
                    else:
                        try:
                            w.setVisible(bool(visible))
                        except Exception:
                            pass
            except Exception:
                pass
            sync_panels_menu_state(win)
        return _fn

    # Status dock (may not exist yet; action disabled until it does)
    act_p_status = QAction("Status", panels)
    act_p_status.setCheckable(True)
    sd = getattr(win, "status_dock", None)
    act_p_status.setEnabled(isinstance(sd, QDockWidget))
    act_p_status.setChecked(_checked_visible(sd))
    act_p_status.toggled.connect(_toggle(lambda: getattr(win, "status_dock", None)))
    panels.addAction(act_p_status)
    win.act_panel_status = act_p_status

    # Logs submenu: one toggle per log category (if available)
    from ui.state.window_state import update_window_data
    logs_menu = QMenu("Logs", panels)
    panels.addMenu(logs_menu)

    # Known categories; if MainWindow created log docks, they will be present in win._log_docks
    log_categories = ["All", "Combat", "Trade", "Dialogue", "Reputation", "Loot", "Quest"]
    for cat in log_categories:
        obj_name = f"dock_Log_{cat}"
        act = QAction(cat, logs_menu)
        act.setCheckable(True)
        dock = None
        try:
            dock = getattr(win, "_log_docks", {}).get(cat)
        except Exception:
            dock = None
        # Enable by default - docks will be created when game starts
        act.setEnabled(True)
        act.setChecked(_checked_visible(dock))

        def make_toggle(dock_name, category, window=win):
            def _fn(visible: bool):
                try:
                    dct = None
                    try:
                        dct = getattr(window, "_log_docks", {}).get(category)
                    except Exception:
                        dct = None
                    if isinstance(dct, QDockWidget):
                        dct.setVisible(bool(visible))
                    # Persist global config so this applies across saves
                    try:
                        # This call is user-driven (menu toggle); persist explicitly
                        from ui.state.window_state import user_update_window_data
                        user_update_window_data("MainWindow", {"dock_visibility": {dock_name: bool(visible)}})
                    except Exception:
                        pass
                except Exception:
                    pass
                sync_panels_menu_state(window)
            return _fn

        act.toggled.connect(make_toggle(obj_name, cat))
        logs_menu.addAction(act)

    # Galaxy list (top)
    act_p_gal = QAction("Galaxy List", panels)
    act_p_gal.setCheckable(True)
    act_p_gal.setEnabled(isinstance(getattr(win, "location_panel_galaxy", None), QWidget))
    act_p_gal.setChecked(_checked_visible(getattr(win, "location_panel_galaxy", None)))
    act_p_gal.toggled.connect(_toggle(lambda: getattr(win, "location_panel_galaxy", None)))
    panels.addAction(act_p_gal)
    win.act_panel_location_galaxy = act_p_gal

    # System list (bottom)
    act_p_sys = QAction("System List", panels)
    act_p_sys.setCheckable(True)
    act_p_sys.setEnabled(isinstance(getattr(win, "location_panel_system", None), QWidget))
    act_p_sys.setChecked(_checked_visible(getattr(win, "location_panel_system", None)))
    act_p_sys.toggled.connect(_toggle(lambda: getattr(win, "location_panel_system", None)))
    panels.addAction(act_p_sys)
    win.act_panel_location_system = act_p_sys

    # Legacy single list (optional)
    act_p_loc = QAction("Location List (legacy)", panels)
    act_p_loc.setCheckable(True)
    act_p_loc.setEnabled(isinstance(getattr(win, "location_panel", None), QWidget))
    act_p_loc.setChecked(_checked_visible(getattr(win, "location_panel", None)))
    act_p_loc.toggled.connect(_toggle(lambda: getattr(win, "location_panel", None)))
    panels.addAction(act_p_loc)
    win.act_panel_location = act_p_loc

    # Keep a mapping of per-category log actions on the window so
    # sync_panels_menu_state can update them when log docks are created.
    try:
        # store as { category: QAction } under a private attribute
        setattr(win, "_act_log_categories", {})
        for a in logs_menu.actions():
            # action text is the category name
            try:
                txt = a.text()
                if isinstance(txt, str) and txt in log_categories:
                    getattr(win, "_act_log_categories")[txt] = a
            except Exception:
                pass
    except Exception:
        pass

    panels.addSeparator()

    # Show/Hide all
    def _show_all():
        # Show main panels
        _toggle(lambda: getattr(win, "status_dock", None))(True)
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(True)
        _toggle(lambda: getattr(win, "location_panel_system", None))(True)
        _toggle(lambda: getattr(win, "location_panel", None))(True)  # legacy
        
        # Show all log docks
        try:
            act_log_map = getattr(win, "_act_log_categories", {})
            for cat, action in act_log_map.items():
                try:
                    # Trigger the toggle for this log category
                    if isinstance(action, QAction) and action.isCheckable():
                        action.blockSignals(True)
                        action.setChecked(True)
                        action.blockSignals(False)
                        action.toggled.emit(True)
                except Exception:
                    pass
        except Exception:
            pass

    def _hide_all():
        # Hide main panels
        _toggle(lambda: getattr(win, "status_dock", None))(False)
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(False)
        _toggle(lambda: getattr(win, "location_panel_system", None))(False)
        _toggle(lambda: getattr(win, "location_panel", None))(False)  # legacy
        
        # Hide all log docks
        try:
            act_log_map = getattr(win, "_act_log_categories", {})
            for cat, action in act_log_map.items():
                try:
                    # Trigger the toggle for this log category
                    if isinstance(action, QAction) and action.isCheckable():
                        action.blockSignals(True)
                        action.setChecked(False)
                        action.blockSignals(False)
                        action.toggled.emit(False)
                except Exception:
                    pass
        except Exception:
            pass

    act_show_all = QAction("Show All", panels)
    act_show_all.triggered.connect(_show_all)
    panels.addAction(act_show_all)

    act_hide_all = QAction("Hide All", panels)
    act_hide_all.triggered.connect(_hide_all)
    panels.addAction(act_hide_all)

    # Keep actions in sync with actual dock visibility
    if isinstance(sd, QDockWidget) and hasattr(sd, "visibilityChanged"):
        sd.visibilityChanged.connect(lambda _vis: sync_panels_menu_state(win))

    # Initial sync
    sync_panels_menu_state(win)
