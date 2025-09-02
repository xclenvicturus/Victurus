# /ui/controllers/galaxy_location_presenter.py

"""
Victurus Galaxy Location Presenter

Controller for galaxy system list and map integration:
- Populates galaxy system list with filterable/sortable data
- Handles single-click (focus) and double-click (open) actions
- Coordinates between galaxy map and system views
- Manages travel integration and system loading
"""

from __future__ import annotations

from typing import Dict, List, Optional, Iterable, Any, Protocol, runtime_checkable, cast

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QWidget

from ui.error_utils import catch_and_log, ErrorContext

# Prefer GIF-first pixmap helper for crisp list thumbnails
try:
    from ui.maps.icons import pm_from_path_or_kind  # type: ignore
except Exception:  # pragma: no cover
    pm_from_path_or_kind = None  # type: ignore

from data import db

# travel planner is optional; we fall back gracefully when it isn't present
try:
    from game import travel  # type: ignore
except Exception:  # pragma: no cover
    travel = None  # type: ignore

from ..maps.tabs import MapTabs
from ..widgets.galaxy_system_list import GalaxySystemList


# ------------------------ typing helpers ------------------------

class _TravelFlowLike(Protocol):
    def begin(self, kind: str, ident: int) -> None: ...


@runtime_checkable
class _MainWindowLike(Protocol):
    def _ensure_travel_flow(self) -> _TravelFlowLike: ...
    travel_flow: Optional[_TravelFlowLike]
    # Optional presenters / panels (new split or legacy dual)
    presenter_system: Any  # may not exist in older builds
    presenter_dual: Any    # legacy
    location_panel_system: Optional[QWidget]


# ------------------------ small utils ------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except Exception:
        return default


def _fallback_fuel_from_au(dist_au: float) -> int:
    """Coarse AU→fuel fallback mirroring prior presenter behavior."""
    if dist_au <= 0.0:
        return 0
    # galaxy rows use the current leg to gate as a proxy; 5 AU per fuel (coarse)
    return max(1, int(round(dist_au / 5.0)))


# ------------------------ presenter ------------------------

class GalaxyLocationPresenter:
    """
    Populates the GalaxySystemList (systems only).

    Rows use id = -system_id  (negative => system/star).
    Distances/fuel come from travel.get_travel_display_data() when available.
    """

    def __init__(self,
                 map_view: MapTabs | QWidget,
                 galaxy_panel: GalaxySystemList,
                 travel_coordinator = None) -> None:
        self._tabs = map_view
        self._gal = galaxy_panel
        self._travel_coordinator = travel_coordinator

    # -------- public API --------

    def refresh(self) -> None:
        """
        Always refresh the list (do not gate on the active map tab), so that
        filters/sorting/search respond immediately even while the System map tab is active.
        """
        list_font = QFont()
        try:
            player = db.get_player_full() or {}
        except Exception:
            player = {}

        cur_sys_id = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)

        galaxy_rows = self._build_galaxy_rows(cur_sys_id)
        rows_g = self._gal.filtered_sorted(galaxy_rows, _player_pos=None)
        self._gal.populate(rows_g, list_font, icon_provider=self._icon_provider)

    def focus(self, entity_id: int) -> None:
        """
        Single-click behavior for Galaxy tab:
          • Center the galaxy map on the clicked system.
          • ALSO load that system into the System view and refresh the System list,
            without switching tabs. This makes the right-side System list reflect
            the clicked system immediately.
        """
        try:
            sys_id = -int(entity_id) if int(entity_id) < 0 else int(entity_id)
        except Exception:
            return

        # Center on Galaxy map as before
        center_gal = getattr(self._tabs, "center_galaxy_on_system", None)
        if callable(center_gal):
            try:
                center_gal(sys_id)
            except Exception:
                pass
        else:
            galaxy_widget = getattr(self._tabs, "galaxy", None)
            if galaxy_widget is not None:
                try:
                    if hasattr(galaxy_widget, "center_on_system"):
                        galaxy_widget.center_on_system(sys_id)
                    elif hasattr(galaxy_widget, "center_on_entity"):
                        try:
                            galaxy_widget.center_on_entity(-sys_id)
                        except Exception:
                            galaxy_widget.center_on_entity(sys_id)
                except Exception:
                    pass

        # Load the selected system into the System widget (no tab switch).
        system_widget = getattr(self._tabs, "system", None)
        if system_widget is not None and hasattr(system_widget, "load"):
            try:
                system_widget.load(sys_id)
            except Exception:
                pass

        # Kick the System list to refresh immediately, regardless of which tab is active.
        self._trigger_system_list_refresh()

    def open(self, entity_id: int) -> None:
        """
        Double-click:
          - System row (entity_id < 0): load that system in the System view and switch to the System tab.
        """
        try:
            if entity_id >= 0:
                # Unexpected in galaxy list, but ignore safely.
                return
            system_id = -int(entity_id)

            tabs = getattr(self._tabs, "tabs", None)
            system_widget = getattr(self._tabs, "system", None)

            if system_widget and hasattr(system_widget, "load") and hasattr(system_widget, "center_on_system"):
                try:
                    system_widget.load(system_id)
                    system_widget.center_on_system(system_id)
                except Exception:
                    try:
                        system_widget.center_on_entity(-system_id)
                    except Exception:
                        pass

            # Switch to System tab
            if tabs is not None:
                try:
                    if getattr(tabs, "count", lambda: 0)() >= 2:
                        tabs.setCurrentIndex(1)  # Galaxy=0, System=1
                except Exception:
                    pass
        except Exception:
            pass

    @catch_and_log("Galaxy location travel")
    def travel_here(self, entity_id: int) -> None:
        """Relay to TravelFlow via the MainWindow for systems (neg ids)."""
        try:
            if entity_id >= 0:
                # Galaxy list should use negative ids; ignore unexpected positives.
                return

            mw = self._main_window()
            if mw is None:
                return

            flow: Optional[_TravelFlowLike] = getattr(mw, "travel_flow", None)
            if flow is None:
                flow = mw._ensure_travel_flow()

            # Start travel to system
            system_id = int(-entity_id)
            
            # Get the galaxy map and start travel status tracking
            galaxy_widget = getattr(self._tabs, "galaxy", None)
            if galaxy_widget and hasattr(galaxy_widget, 'get_travel_status'):
                travel_status = galaxy_widget.get_travel_status()
                travel_status.start_travel_tracking("star", system_id)
            
            # Begin actual travel
            flow.begin("star", system_id)
            
        except Exception as e:
            from game_controller.log_config import get_ui_logger
            logger = get_ui_logger('galaxy_presenter')
            logger.error(f"Error in travel_here: {e}")
            pass

    # -------- internals --------

    def _trigger_system_list_refresh(self) -> None:
        """
        Try multiple strategies (new split presenters and legacy dual) to refresh
    the right-side System list immediately after we load the System.
        """
        try:
            mw = self._main_window()
            if mw is None:
                return

            # Preferred (split presenters)
            ps = getattr(mw, "presenter_system", None)
            if ps is not None and hasattr(ps, "refresh"):
                try:
                    ps.refresh()
                    return
                except Exception:
                    pass

            # Legacy dual presenter, if still present
            pd = getattr(mw, "presenter_dual", None)
            if pd is not None and hasattr(pd, "refresh"):
                try:
                    pd.refresh()
                except Exception:
                    pass

            # As a last resort, poke the System list panel to ask for a refresh
            panel = getattr(mw, "location_panel_system", None)
            if panel is not None and hasattr(panel, "refreshRequested"):
                try:
                    panel.refreshRequested.emit()
                except Exception:
                    pass
        except Exception:
            pass

    def _main_window(self) -> Optional[_MainWindowLike]:
        try:
            w = self._tabs.window()
        except Exception:
            return None
        if hasattr(w, "_ensure_travel_flow"):
            return cast(_MainWindowLike, w)
        return None

    def _coerce_list(self, obj: Any) -> List[Dict[str, Any]]:
        if isinstance(obj, list):
            return obj  # type: ignore[return-value]
        if isinstance(obj, tuple):
            return list(obj)  # type: ignore[return-value]
        if isinstance(obj, Iterable):
            return list(obj)  # type: ignore[return-value]
        return []

    def _icon_provider(self, r: Dict[str, Any]):
        """Use the universal pm_from_path_or_kind for crisp thumbnails from any source."""
        p = r.get("icon_path")
        if isinstance(p, str) and p:
            if pm_from_path_or_kind is not None:
                try:
                    pm = pm_from_path_or_kind(p, "star", desired_px=24)
                    if pm is not None and not pm.isNull():
                        return QIcon(pm)
                except Exception:
                    pass
            return QIcon(p)
        return None

    # ---------- formatting helpers ----------

    def _fmt_galaxy_distance(self, td: Dict[str, Any]) -> str:
        ly = _safe_float(td.get("dist_ly", 0.0), 0.0)
        return f"{ly:.2f} ly"

    # ---------- row builders ----------

    def _build_galaxy_rows(self, cur_sys_id: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        # Prefer entities coming from the galaxy widget (already filtered/sorted for view)
        entities: List[Dict[str, Any]] = []
        gal = getattr(self._tabs, "galaxy", None)
        get_entities = getattr(gal, "get_entities", None)
        if callable(get_entities):
            try:
                entities = self._coerce_list(get_entities())
            except Exception:
                entities = []

        if not entities:
            # DB fallback
            try:
                entities = [dict(r) for r in db.get_systems()]
            except Exception:
                entities = []

        for s in entities:
            sid = _safe_int(s.get("id") or s.get("system_id"), 0)
            if sid <= 0:
                continue

            td: Dict[str, Any] = {}
            if travel and hasattr(travel, "get_travel_display_data"):
                try:
                    td = travel.get_travel_display_data("star", sid) or {}
                except Exception:
                    td = {}

            # Fuel fallback (galaxy): if planner didn't provide one, use the "to gate" leg
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                fuel_cost_val = _fallback_fuel_from_au(_safe_float(td.get("intra_current_au", 0.0), 0.0))

            rows.append({
                "id": -sid,  # negative => system/star for travel semantics
                "name": s.get("name", s.get("system_name", "System")),
                "kind": "system",
                "distance": self._fmt_galaxy_distance(td),
                "dist_ly": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "dist_au": _safe_float(td.get("dist_au", 0.0), 0.0),
                "jump_dist": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "fuel_cost": int(fuel_cost_val) if fuel_cost_val and fuel_cost_val > 0 else "—",
                "x": _safe_float(s.get("x", s.get("system_x", 0.0)), 0.0),
                "y": _safe_float(s.get("y", s.get("system_y", 0.0)), 0.0),
                "can_reach": bool(td.get("can_reach", True)),
                "can_reach_jump": bool(td.get("can_reach_jump", True)),
                "can_reach_fuel": bool(td.get("can_reach_fuel", True)),
                # Prefer DB icon_path (system-level) if present, else whatever the galaxy widget provided
                "icon_path": s.get("icon_path"),
                "is_current": (sid == cur_sys_id),
            })
        return rows
