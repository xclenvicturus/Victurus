# /ui/controllers/dual_location_presenter.py
from __future__ import annotations

from typing import Dict, List, Optional, Iterable, Any, Protocol, runtime_checkable, cast
import math

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QWidget

from data import db
from game import travel
from ..maps.tabs import MapTabs
from ..widgets.location_list import LocationList


# ------------------------ typing helpers ------------------------

class _TravelFlowLike(Protocol):
    def begin(self, kind: str, ident: int) -> None: ...


@runtime_checkable
class _MainWindowLike(Protocol):
    def _ensure_travel_flow(self) -> _TravelFlowLike: ...
    travel_flow: Optional[_TravelFlowLike]


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
    return max(1, int(math.ceil(dist_au / 5.0)))


# ------------------------ presenter ------------------------

class DualLocationPresenter:
    """
    Populates two LocationList widgets:

      • Galaxy (systems): rows use id = -system_id  (negative => system/star)
      • System (star + locations): star row id = -system_id; locations use positive location_id

    Distances/fuel come from travel.get_travel_display_data() so UI matches TravelFlow.
    AU/fuel fallbacks are kept for robustness when travel data is unavailable.
    """

    def __init__(self,
                 map_view: MapTabs | QWidget,
                 galaxy_panel: LocationList,
                 solar_panel: LocationList) -> None:
        self._tabs = map_view
        self._gal = galaxy_panel
        self._sol = solar_panel

    # -------- public API --------

    def refresh(self) -> None:
        list_font = QFont()
        try:
            player = db.get_player_full() or {}
        except Exception:
            player = {}

        cur_sys_id = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)
        cur_loc_id = _safe_int(player.get("current_player_location_id") or player.get("location_id"), 0)

        # Galaxy (systems)
        galaxy_rows = self._build_galaxy_rows(cur_sys_id)
        rows_g = self._gal.filtered_sorted(galaxy_rows, player_pos=None)
        self._gal.populate(rows_g, list_font, icon_provider=self._icon_provider)

        # System (star + locations) – use system currently viewed by solar tab if available
        viewed_sys_id = getattr(self._tabs, "solar", None)
        viewed_sys_id = getattr(viewed_sys_id, "_system_id", None) or cur_sys_id
        system_rows = self._build_system_rows(int(viewed_sys_id), cur_loc_id)
        rows_s = self._sol.filtered_sorted(system_rows, player_pos=None)
        self._sol.populate(rows_s, list_font, icon_provider=self._icon_provider)

    def focus(self, entity_id: int) -> None:
        """Single-click behavior (kept minimal)."""
        # You could add lightweight highlighting here if desired.
        pass

    def open(self, entity_id: int) -> None:
        """
        Double-click:
          - If a system row (entity_id < 0), load that system in Solar and switch to the Solar tab.
          - If a location row (entity_id >= 0), center on that location in Solar (loading its system if needed).
        """
        try:
            tabs = getattr(self._tabs, "tabs", None)
            solar = getattr(self._tabs, "solar", None)

            # Helper to switch to Solar tab safely
            def _switch_to_solar_tab() -> None:
                if tabs is None:
                    return
                idx = getattr(tabs, "indexOfSolar", None)
                if isinstance(idx, int):
                    tabs.setCurrentIndex(idx)
                else:
                    # fall back to index 1 if there are only two tabs (Galaxy=0, Solar=1)
                    try:
                        if hasattr(tabs, "setCurrentIndex") and getattr(tabs, "count", lambda: 0)() >= 2:
                            tabs.setCurrentIndex(1)
                    except Exception:
                        pass

            # System (negative id)
            if entity_id < 0:
                system_id = -int(entity_id)
                if solar and hasattr(solar, "load") and hasattr(solar, "center_on_system"):
                    try:
                        solar.load(system_id)
                        solar.center_on_system(system_id)
                    except Exception:
                        # robust fallback: use center_on_entity with -system_id
                        try:
                            solar.center_on_entity(-system_id)
                        except Exception:
                            pass
                _switch_to_solar_tab()
                # Refresh lists so the System pane shows the newly loaded system
                self.refresh()
                return

            # Location (positive id)
            if solar and hasattr(solar, "center_on_entity"):
                try:
                    solar.center_on_entity(int(entity_id))
                except Exception:
                    pass
            _switch_to_solar_tab()
            # No need to refresh here unless your Solar widget mutates data used by the list;
            # if you want the distance/fuel to reflect player position immediately, uncomment:
            # self.refresh()
        except Exception:
            pass

    def travel_here(self, entity_id: int) -> None:
        """Relay to TravelFlow via the MainWindow, handling systems (neg ids) vs locations (pos ids)."""
        try:
            mw = self._main_window()
            if mw is None:
                return

            flow: Optional[_TravelFlowLike] = getattr(mw, "travel_flow", None)
            if flow is None:
                flow = mw._ensure_travel_flow()

            if entity_id >= 0:
                flow.begin("loc", int(entity_id))
            else:
                flow.begin("star", int(-entity_id))
        except Exception:
            pass

    # -------- internals --------

    def _main_window(self) -> Optional[_MainWindowLike]:
        """Return the top-level window typed to something that exposes _ensure_travel_flow()."""
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
        p = r.get("icon_path")
        return QIcon(p) if isinstance(p, str) and p else None

    # ---------- formatting helpers ----------

    def _fmt_galaxy_distance(self, td: Dict[str, Any]) -> str:
        ly = _safe_float(td.get("dist_ly", 0.0), 0.0)
        return f"{ly:.2f} ly"

    def _fmt_system_distance(self, td: Dict[str, Any]) -> str:
        same = bool(td.get("same_system", False))
        au = _safe_float(td.get("dist_au", 0.0), 0.0)
        if same:
            return f"{au:.2f} AU"
        ly = _safe_float(td.get("dist_ly", 0.0), 0.0)
        tail_au = _safe_float(td.get("intra_target_au", 0.0), 0.0)
        return f"{ly:.2f} ly + {tail_au:.2f} AU"

    # ---------- row builders ----------

    def _build_galaxy_rows(self, cur_sys_id: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        # Prefer entities coming from the galaxy widget
        entities: List[Dict[str, Any]] = []
        gal = getattr(self._tabs, "galaxy", None)
        get_entities = getattr(gal, "get_entities", None)
        if callable(get_entities):
            try:
                entities = self._coerce_list(get_entities())
            except Exception:
                entities = []

        if not entities:
            try:
                entities = [dict(r) for r in db.get_systems()]
            except Exception:
                entities = []

        for s in entities:
            sid = _safe_int(s.get("id") or s.get("system_id"), 0)
            if sid <= 0:
                continue

            try:
                td: Dict[str, Any] = travel.get_travel_display_data("star", sid) or {}
            except Exception:
                td = {}

            # Fuel fallback (galaxy): if planner didn't provide one, use the "to gate" leg
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                fuel_cost_val = _fallback_fuel_from_au(_safe_float(td.get("intra_current_au", 0.0), 0.0))

            rows.append({
                "id": -sid,  # negative => system/star for travel semantics
                "name": s.get("name", "System"),
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
                "icon_path": s.get("icon_path"),
                "is_current": (sid == cur_sys_id),
            })
        return rows

    def _build_system_rows(self, viewed_sys_id: int, cur_loc_id: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        sys_id = int(viewed_sys_id)

        # Prefer entities coming from the solar widget
        entities: List[Dict[str, Any]] = []
        sol = getattr(self._tabs, "solar", None)
        get_entities = getattr(sol, "get_entities", None)
        if callable(get_entities):
            try:
                entities = self._coerce_list(get_entities())
            except Exception:
                entities = []

        if not entities:
            # synthesize star + DB locations as a fallback
            try:
                sysrow = db.get_system(viewed_sys_id) or {}
            except Exception:
                sysrow = {}

            entities.append({
                "id": -viewed_sys_id,  # negative id => star/system
                "system_id": viewed_sys_id,
                "name": f"{sysrow.get('name','System')} (Star)",
                "kind": "star",
                "icon_path": None,
                "x": 0.0,
                "y": 0.0,
            })
            try:
                for loc in db.get_locations(viewed_sys_id):
                    d = dict(loc)
                    d.setdefault("x", 0.0)
                    d.setdefault("y", 0.0)
                    entities.append(d)
            except Exception:
                pass

        # Current player location coord (fallback 0,0)
        cur_x = 0.0
        cur_y = 0.0
        if cur_loc_id:
            try:
                cur_loc = db.get_location(cur_loc_id) or {}
                cur_x = _safe_float(cur_loc.get("local_x_au", cur_loc.get("location_x", 0.0)), 0.0)
                cur_y = _safe_float(cur_loc.get("local_y_au", cur_loc.get("location_y", 0.0)), 0.0)
            except Exception:
                pass

        for e in entities:
            eid = _safe_int(e.get("id"), 0)
            kind = str(e.get("kind") or e.get("location_type") or "location").lower().strip()

            # coords
            ex = e.get("x", None)
            ey = e.get("y", None)
            locrow_cache: Dict[str, Any] = {}
            if ex is None or ey is None:
                if eid >= 0:
                    locrow_cache = db.get_location(eid) or {}
                    ex = locrow_cache.get("local_x_au", locrow_cache.get("location_x", 0.0))
                    ey = locrow_cache.get("local_y_au", locrow_cache.get("location_y", 0.0))
                else:
                    ex = 0.0
                    ey = 0.0
            exf = _safe_float(ex, 0.0)
            eyf = _safe_float(ey, 0.0)

            # authoritative parent id for moons/stations
            parent_id_val = None
            if kind in ("moon", "station") and eid >= 0:
                if not locrow_cache:
                    locrow_cache = db.get_location(eid) or {}
                parent_id_val = (
                    locrow_cache.get("parent_location_id")
                    if locrow_cache.get("parent_location_id") not in (None, "", 0)
                    else locrow_cache.get("parent_id")
                )
            else:
                parent_id_val = e.get("parent_location_id") or e.get("parent_id")

            # Query travel for distances
            try:
                if eid < 0:
                    td: Dict[str, Any] = travel.get_travel_display_data("star", sys_id) or {}
                else:
                    td = travel.get_travel_display_data("loc", eid) or {}
            except Exception:
                td = {}

            # AU fallback if travel couldn't provide
            dist_au = _safe_float(td.get("dist_au", 0.0), 0.0)
            if not dist_au:
                for k in ("distance_au", "orbit_radius_au", "au", "orbit_au"):
                    v = e.get(k)
                    if v not in (None, ""):
                        dist_au = _safe_float(v, 0.0)
                        if dist_au:
                            break
            if not dist_au:
                dist_au = math.hypot(exf - cur_x, eyf - cur_y)

            # Fuel: prefer travel module; fallback to AU-based estimate
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                if bool(td.get("same_system", False)):
                    fuel_cost_val = _fallback_fuel_from_au(dist_au)
                else:
                    fuel_cost_val = _fallback_fuel_from_au(_safe_float(td.get("intra_target_au", 0.0), 0.0))

            rows.append({
                "id": eid,
                "system_id": sys_id,
                "name": e.get("name", "—"),
                "kind": kind,
                "parent_location_id": parent_id_val,

                "distance": self._fmt_system_distance(td),
                "dist_ly": float(td.get("dist_ly") or 0.0),
                "dist_au": float(dist_au or 0.0),
                "fuel_cost": int(fuel_cost_val or 0),

                "x": exf,
                "y": eyf,
                "can_reach": bool(td.get("can_reach", True)),
                "can_reach_jump": bool(td.get("can_reach_jump", True)),
                "can_reach_fuel": bool(td.get("can_reach_fuel", True)),
                "icon_path": e.get("icon_path"),
                "is_current": (eid < 0 and cur_loc_id == 0) or (eid >= 0 and eid == cur_loc_id),
            })

        return rows
