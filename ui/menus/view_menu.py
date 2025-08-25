# /ui/menus/view_menu.py
from __future__ import annotations

from typing import Any, Protocol, cast

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar


# ---- Structural type for MainWindow so Pylance knows these attrs exist ----
class _MainWindowLike(Protocol):
    def menuBar(self) -> QMenuBar: ...
    # docks
    status_dock: Any
    log_dock: Any
    # location panels (new split UI)
    location_panel_galaxy: Any
    location_panel_solar: Any
    # legacy single panel (optional in your app, but we keep support)
    location_panel: Any
    # actions set up by this module
    act_panel_status: Any
    act_panel_log: Any
    act_panel_location_galaxy: Any
    act_panel_location_solar: Any
    act_panel_location: Any
    act_leader_glow: Any


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
    return cast(QMenu, mb.addMenu("&View"))


# ---------- public API ----------

def sync_panels_menu_state(win: _MainWindowLike) -> None:
    """Reflect actual widget visibility into the Panels submenu actions."""
    # Status dock
    if getattr(win, "act_panel_status", None):
        try:
            win.act_panel_status.blockSignals(True)
            win.act_panel_status.setChecked(bool(win.status_dock.isVisible()))
        finally:
            win.act_panel_status.blockSignals(False)

    # Log dock
    if getattr(win, "act_panel_log", None):
        try:
            win.act_panel_log.blockSignals(True)
            win.act_panel_log.setChecked(bool(win.log_dock.isVisible()))
        finally:
            win.act_panel_log.blockSignals(False)

    # Galaxy list (top)
    if getattr(win, "act_panel_location_galaxy", None):
        has_gal = getattr(win, "location_panel_galaxy", None) is not None
        win.act_panel_location_galaxy.setEnabled(has_gal)
        try:
            win.act_panel_location_galaxy.blockSignals(True)
            win.act_panel_location_galaxy.setChecked(has_gal and bool(win.location_panel_galaxy.isVisible()))
        finally:
            win.act_panel_location_galaxy.blockSignals(False)

    # System list (bottom)
    if getattr(win, "act_panel_location_solar", None):
        has_sol = getattr(win, "location_panel_solar", None) is not None
        win.act_panel_location_solar.setEnabled(has_sol)
        try:
            win.act_panel_location_solar.blockSignals(True)
            win.act_panel_location_solar.setChecked(has_sol and bool(win.location_panel_solar.isVisible()))
        finally:
            win.act_panel_location_solar.blockSignals(False)

    # Legacy single list (if your app still exposes it)
    if getattr(win, "act_panel_location", None):
        has_loc = getattr(win, "location_panel", None) is not None
        win.act_panel_location.setEnabled(has_loc)
        try:
            win.act_panel_location.blockSignals(True)
            win.act_panel_location.setChecked(has_loc and bool(win.location_panel.isVisible()))
        finally:
            win.act_panel_location.blockSignals(False)


def install_view_menu_extras(win: _MainWindowLike, prefs) -> None:
    """Create View → Leader Line and Panels submenus, wiring to the window."""
    view_menu = _ensure_view_menu(win)

    # Leader Line submenu
    ll_menu = QMenu("Leader Line", cast(QMenuBar, view_menu.parentWidget()))
    view_menu.addMenu(ll_menu)

    act_color = QAction("Set Color…", cast(QMenuBar, view_menu.parentWidget()))
    act_color.triggered.connect(lambda: prefs.pick_color(win))
    ll_menu.addAction(act_color)

    act_width = QAction("Set Width…", cast(QMenuBar, view_menu.parentWidget()))
    act_width.triggered.connect(lambda: prefs.pick_width(win))
    ll_menu.addAction(act_width)

    act_glow = QAction("Glow", cast(QMenuBar, view_menu.parentWidget()))
    act_glow.setCheckable(True)
    act_glow.setChecked(bool(prefs.glow))
    act_glow.toggled.connect(lambda v: prefs.set_glow(v, win))
    ll_menu.addAction(act_glow)
    win.act_leader_glow = act_glow  # state handle for restore

    # Panels submenu
    panels = QMenu("Panels", cast(QMenuBar, view_menu.parentWidget()))
    view_menu.addMenu(panels)

    def _toggle(getter):
        def _fn(visible: bool):
            w = getter()
            if w:
                w.setVisible(bool(visible))
            sync_panels_menu_state(win)
        return _fn

    # Status dock
    act_p_status = QAction("Status", panels)
    act_p_status.setCheckable(True)
    act_p_status.setChecked(bool(win.status_dock.isVisible()))
    act_p_status.toggled.connect(_toggle(lambda: win.status_dock))
    panels.addAction(act_p_status)
    win.act_panel_status = act_p_status

    # Log dock
    act_p_log = QAction("Log", panels)
    act_p_log.setCheckable(True)
    act_p_log.setChecked(bool(win.log_dock.isVisible()))
    act_p_log.toggled.connect(_toggle(lambda: win.log_dock))
    panels.addAction(act_p_log)
    win.act_panel_log = act_p_log

    # Galaxy list (top)
    act_p_gal = QAction("Galaxy List", panels)
    act_p_gal.setCheckable(True)
    act_p_gal.setEnabled(getattr(win, "location_panel_galaxy", None) is not None)
    act_p_gal.toggled.connect(_toggle(lambda: getattr(win, "location_panel_galaxy", None)))
    panels.addAction(act_p_gal)
    win.act_panel_location_galaxy = act_p_gal

    # System list (bottom)
    act_p_sol = QAction("System List", panels)
    act_p_sol.setCheckable(True)
    act_p_sol.setEnabled(getattr(win, "location_panel_solar", None) is not None)
    act_p_sol.toggled.connect(_toggle(lambda: getattr(win, "location_panel_solar", None)))
    panels.addAction(act_p_sol)
    win.act_panel_location_solar = act_p_sol

    panels.addSeparator()

    # Show/Hide all (support new and legacy panels)
    act_show_all = QAction("Show All", panels)
    act_show_all.triggered.connect(lambda: [
        _toggle(lambda: win.status_dock)(True),
        _toggle(lambda: win.log_dock)(True),
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(True),
        _toggle(lambda: getattr(win, "location_panel_solar", None))(True),
        _toggle(lambda: getattr(win, "location_panel", None))(True),  # legacy
    ])
    panels.addAction(act_show_all)

    act_hide_all = QAction("Hide All", panels)
    act_hide_all.triggered.connect(lambda: [
        _toggle(lambda: win.status_dock)(False),
        _toggle(lambda: win.log_dock)(False),
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(False),
        _toggle(lambda: getattr(win, "location_panel_solar", None))(False),
        _toggle(lambda: getattr(win, "location_panel", None))(False),  # legacy
    ])
    panels.addAction(act_hide_all)

    # Keep actions in sync with actual dock visibility
    win.status_dock.visibilityChanged.connect(lambda _vis: sync_panels_menu_state(win))
    win.log_dock.visibilityChanged.connect(lambda _vis: sync_panels_menu_state(win))
    # Galaxy/System lists are regular widgets; MainWindow should call sync after creating them

    # Initial sync
    sync_panels_menu_state(win)
