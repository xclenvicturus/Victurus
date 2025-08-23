# ui/location_presenter.py
from __future__ import annotations

from typing import Dict, List, Optional, Iterable

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QTabWidget

from data import db
from game import travel
from .maps.tabs import MapTabs
from .widgets.location_list import LocationList
from .constants import STAR_ID_SENTINEL


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
        cur_sys_id = int(player.get("current_player_system_id") or 0)
        cur_loc_id = int(player.get("current_player_location_id") or 0)

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
        """Return the inner QTabWidget from MapTabs if present and typed."""
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

    def _coerce_list(self, obj) -> List[Dict]:
        if isinstance(obj, list):
            return obj
        if isinstance(obj, tuple):
            return list(obj)
        if isinstance(obj, Iterable):
            return list(obj)
        return []

    def _icon_provider(self, r: Dict):
        p = r.get("icon_path")
        return QIcon(p) if p else None

    def _build_galaxy_rows(self, cur_sys_id: int) -> List[Dict]:
        rows: List[Dict] = []
        gal = getattr(self._tabs, "galaxy", None)
        get_entities = getattr(gal, "get_entities", None)
        entities: List[Dict] = []
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
            sid = int(s.get("id") or 0)
            try:
                td = travel.get_travel_display_data(target_id=sid, is_system_target=True) or {}
            except Exception:
                td = {}
            dist_ly = float(td.get("dist_ly", 0.0) or 0.0)
            rows.append({
                "id": sid,
                "name": s.get("name", "System"),
                "kind": "system",
                "distance": td.get("distance", f"{dist_ly:.2f} ly"),
                "fuel_cost": td.get("fuel_cost", "—"),
                "x": s.get("x", 0.0),
                "y": s.get("y", 0.0),
                "can_reach": True,
                "icon_path": s.get("icon_path"),
                "is_current": (sid == cur_sys_id),
            })
        return rows

    def _build_system_rows(self, viewed_sys_id: int, cur_loc_id: int) -> List[Dict]:
        rows: List[Dict] = []

        # Prefer entities coming from the solar widget
        entities: List[Dict] = []
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
        player = db.get_player_full() or {}
        cur_x = 0.0
        cur_y = 0.0
        if cur_loc_id:
            try:
                cur_loc = db.get_location(cur_loc_id) or {}
                cur_x = float(cur_loc.get("x", 0.0) or 0.0)
                cur_y = float(cur_loc.get("y", 0.0) or 0.0)
            except Exception:
                pass

        for e in entities:
            eid = int(e.get("id") or 0)
            kind = (e.get("kind") or e.get("location_type") or "location").lower()

            # coords
            ex = e.get("x", None)
            ey = e.get("y", None)
            if ex is None or ey is None:
                if eid >= 0:
                    locrow = db.get_location(eid) or {}
                    ex = locrow.get("x", 0.0)
                    ey = locrow.get("y", 0.0)
                else:
                    ex = 0.0
                    ey = 0.0
            try:
                ex = float(ex or 0.0)
                ey = float(ey or 0.0)
            except Exception:
                ex = 0.0
                ey = 0.0

            # AU distance (prefer travel module, else baked, else geometry)
            dist_au = 0.0
            td: Dict = {}
            try:
                td = travel.get_travel_display_data(
                    target_id=(viewed_sys_id if eid < 0 else eid),
                    is_system_target=(eid < 0),
                    current_view_system_id=viewed_sys_id,
                ) or {}
                v = td.get("dist_au", None)
                if v is not None:
                    dist_au = float(v)
            except Exception:
                pass
            if not dist_au:
                for k in ("distance_au", "orbit_radius_au", "au", "orbit_au"):
                    v = e.get(k)
                    if v not in (None, ""):
                        try:
                            dist_au = float(str(v))
                            break
                        except Exception:
                            pass
            if not dist_au:
                from math import hypot
                dist_au = hypot(ex - cur_x, ey - cur_y)

            rows.append({
                "id": eid,
                "name": e.get("name", "—"),
                "kind": kind,
                "distance": td.get("distance", f"0.00 ly, {dist_au:.2f} AU"),
                "fuel_cost": td.get("fuel_cost", "—"),
                "x": ex,
                "y": ey,
                "can_reach": True,
                "icon_path": e.get("icon_path"),
                "is_current": (eid == cur_loc_id) if eid >= 0 else False,
            })

        return rows
