from __future__ import annotations

from typing import Dict, List, Optional, Iterable, Any
import math

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QTabWidget

from data import db
from game import travel
from .maps.tabs import MapTabs
from .widgets.location_list import LocationList
from .constants import STAR_ID_SENTINEL


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
    """Mirror of travel._intra_fuel_cost for a presenter-side fallback."""
    if dist_au <= 0.0:
        return 0
    return max(1, int(math.ceil(dist_au / 5.0)))


class LocationPresenter:
    """
    Builds and populates rows for the right-hand LocationList based on the active tab
    (Galaxy: systems; System: star + locations).
    """

    def __init__(self, tabs: MapTabs, panel: LocationList) -> None:
        self._tabs = tabs
        self._panel = panel

    # -------- public API --------

    def refresh(self) -> None:
        list_font = QFont()
        player = db.get_player_full() or {}
        cur_sys_id = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)
        cur_loc_id = _safe_int(player.get("current_player_location_id") or player.get("location_id"), 0)

        if self._using_galaxy():
            rows = self._build_galaxy_rows(cur_sys_id)
        else:
            viewed_sys_id = getattr(self._tabs, "solar", None)
            viewed_sys_id = getattr(viewed_sys_id, "_system_id", None) or cur_sys_id
            rows = self._build_system_rows(int(viewed_sys_id), cur_loc_id)

        rows_sorted = self._panel.filtered_sorted(rows, player_pos=None)
        self._panel.populate(rows_sorted, list_font, icon_provider=self._icon_provider)

    # -------- internals --------

    def _tab_widget(self) -> Optional[QTabWidget]:
        tw = getattr(self._tabs, "tabs", None)
        return tw if isinstance(tw, QTabWidget) else None

    def _current_tab_index(self) -> int:
        tw = self._tab_widget()
        if tw is not None:
            try:
                return int(tw.currentIndex())
            except Exception:
                pass
        return 0

    def _using_galaxy(self) -> bool:
        return self._current_tab_index() == 0

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

    # ---------- distance formatting helpers ----------

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
        gal = getattr(self._tabs, "galaxy", None)
        get_entities = getattr(gal, "get_entities", None)
        entities: List[Dict[str, Any]] = []
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
            try:
                td: Dict[str, Any] = travel.get_travel_display_data("star", sid) or {}
            except Exception:
                td = {}

            # Fuel fallback (galaxy): if planner didn't provide one, use the "to gate" leg
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                fuel_cost_val = _fallback_fuel_from_au(_safe_float(td.get("intra_current_au", 0.0), 0.0))

            rows.append({
                "id": sid,
                "name": s.get("name", "System"),
                "kind": "system",
                "distance": self._fmt_galaxy_distance(td),
                "dist_ly": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "dist_au": _safe_float(td.get("dist_au", 0.0), 0.0),
                "jump_dist": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "fuel_cost": int(fuel_cost_val) if fuel_cost_val > 0 else "—",
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
            try:
                sysrow = db.get_system(viewed_sys_id) or {}
            except Exception:
                sysrow = {}
            entities.append({
                "id": STAR_ID_SENTINEL * viewed_sys_id,
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
                # Prefer AU aliases from db.py
                cur_x = _safe_float(cur_loc.get("local_x_au", cur_loc.get("location_x", 0.0)), 0.0)
                cur_y = _safe_float(cur_loc.get("local_y_au", cur_loc.get("location_y", 0.0)), 0.0)
            except Exception:
                pass

        for e in entities:
            eid = _safe_int(e.get("id"), 0)
            kind = str(e.get("kind") or e.get("location_type") or "location").lower()

            # coords
            ex = e.get("x", None)
            ey = e.get("y", None)
            if ex is None or ey is None:
                if eid >= 0:
                    locrow = db.get_location(eid) or {}
                    # use db.py AU aliases, fallback to raw columns
                    ex = locrow.get("local_x_au", locrow.get("location_x", 0.0))
                    ey = locrow.get("local_y_au", locrow.get("location_y", 0.0))
                else:
                    ex = 0.0
                    ey = 0.0
            exf = _safe_float(ex, 0.0)
            eyf = _safe_float(ey, 0.0)

            # Query travel for distances
            try:
                if eid < 0:
                    td: Dict[str, Any] = travel.get_travel_display_data("star", viewed_sys_id) or {}
                else:
                    td = travel.get_travel_display_data("loc", eid) or {}
            except Exception:
                td = {}

            # AU fallback if travel couldn't provide
            dist_au = _safe_float(td.get("dist_au", 0.0), 0.0)
            if not dist_au:
                # try baked values on the entity
                for k in ("distance_au", "orbit_radius_au", "au", "orbit_au"):
                    v = e.get(k)
                    if v not in (None, ""):
                        dist_au = _safe_float(v, 0.0)
                        if dist_au:
                            break
            if not dist_au:
                # geometric as last resort
                dist_au = math.hypot(exf - cur_x, eyf - cur_y)

            # Fuel: prefer travel module; fallback to a coarse AU-based estimate
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                # same-system: use dist_au; inter-system: use arrival leg as a floor
                if bool(td.get("same_system", False)):
                    fuel_cost_val = _fallback_fuel_from_au(dist_au)
                else:
                    fuel_cost_val = _fallback_fuel_from_au(_safe_float(td.get("intra_target_au", 0.0), 0.0))

            rows.append({
                "id": eid,
                "name": e.get("name", "—"),
                "kind": kind,
                "distance": self._fmt_system_distance(td),
                "dist_ly": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "dist_au": _safe_float(dist_au, 0.0),
                "jump_dist": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "fuel_cost": int(fuel_cost_val) if fuel_cost_val > 0 else "—",
                "x": exf,
                "y": eyf,
                "can_reach": bool(td.get("can_reach", True)),
                "can_reach_jump": bool(td.get("can_reach_jump", True)),
                "can_reach_fuel": bool(td.get("can_reach_fuel", True)),
                "icon_path": e.get("icon_path"),
                "is_current": (eid == cur_loc_id) if eid >= 0 else False,
            })

        return rows
