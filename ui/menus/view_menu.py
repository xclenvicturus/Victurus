# /ui/menus/view_menu.py

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
    act_panel_log: Optional[QAction]
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

    # Log dock
    act = getattr(win, "act_panel_log", None)
    dock = getattr(win, "log_dock", None)
    if isinstance(act, QAction):
        try:
            act.blockSignals(True)
            act.setEnabled(isinstance(dock, QDockWidget))
            act.setChecked(_checked_visible(dock))
        finally:
            act.blockSignals(False)

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
            if isinstance(w, QWidget):
                try:
                    w.setVisible(bool(visible))
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

    # Log dock
    act_p_log = QAction("Log", panels)
    act_p_log.setCheckable(True)
    ld = getattr(win, "log_dock", None)
    act_p_log.setEnabled(isinstance(ld, QDockWidget))
    act_p_log.setChecked(_checked_visible(ld))
    act_p_log.toggled.connect(_toggle(lambda: getattr(win, "log_dock", None)))
    panels.addAction(act_p_log)
    win.act_panel_log = act_p_log

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

    panels.addSeparator()

    # Show/Hide all
    act_show_all = QAction("Show All", panels)
    act_show_all.triggered.connect(lambda: [
        _toggle(lambda: getattr(win, "status_dock", None))(True),
        _toggle(lambda: getattr(win, "log_dock", None))(True),
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(True),
        _toggle(lambda: getattr(win, "location_panel_system", None))(True),
        _toggle(lambda: getattr(win, "location_panel", None))(True),  # legacy
    ])
    panels.addAction(act_show_all)

    act_hide_all = QAction("Hide All", panels)
    act_hide_all.triggered.connect(lambda: [
        _toggle(lambda: getattr(win, "status_dock", None))(False),
        _toggle(lambda: getattr(win, "log_dock", None))(False),
        _toggle(lambda: getattr(win, "location_panel_galaxy", None))(False),
        _toggle(lambda: getattr(win, "location_panel_system", None))(False),
        _toggle(lambda: getattr(win, "location_panel", None))(False),  # legacy
    ])
    panels.addAction(act_hide_all)

    # Keep actions in sync with actual dock visibility
    if isinstance(sd, QDockWidget) and hasattr(sd, "visibilityChanged"):
        sd.visibilityChanged.connect(lambda _vis: sync_panels_menu_state(win))
    if isinstance(ld, QDockWidget) and hasattr(ld, "visibilityChanged"):
        ld.visibilityChanged.connect(lambda _vis: sync_panels_menu_state(win))

    # Initial sync
    sync_panels_menu_state(win)
