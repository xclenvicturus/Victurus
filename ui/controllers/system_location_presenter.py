from __future__ import annotations

from typing import Dict, List, Optional, Iterable, Any, Protocol, runtime_checkable, cast
import math

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QWidget

from data import db

# travel planner is optional; we fall back gracefully when it isn't present
try:
    from game import travel  # type: ignore
except Exception:  # pragma: no cover
    travel = None  # type: ignore

from ..maps.tabs import MapTabs
from ..widgets.system_location_list import SystemLocationList

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

class SystemLocationPresenter:
    """
    Populates the SystemLocationList (star + locations).

    Distances/fuel come from travel.get_travel_display_data() when available.
    """

    def __init__(self,
                 map_view: MapTabs | QWidget,
                 system_panel: SystemLocationList) -> None:
        self._tabs = map_view
        self._sol = system_panel

    # -------- public API --------

    def refresh(self) -> None:
        """
        Always refresh the System list using whatever system the Solar widget
        currently has loaded (or the player's system as a fallback).

        We deliberately do NOT gate on the active tab so the System list updates
        while the Galaxy tab is visible (e.g., after a single-click in the galaxy list).
        """
        list_font = QFont()
        try:
            player = db.get_player_full() or {}
        except Exception:
            player = {}

        cur_sys_id = _safe_int(player.get("current_player_system_id") or player.get("system_id"), 0)
        cur_loc_id = _safe_int(player.get("current_player_location_id") or player.get("location_id"), 0)

        solar_widget = getattr(self._tabs, "solar", None)
        viewed_sys_id = getattr(solar_widget, "_system_id", None) or cur_sys_id

        system_rows = self._build_system_rows(int(viewed_sys_id), cur_loc_id, cur_sys_id)
        rows_s = self._sol.filtered_sorted(system_rows, player_pos=None)
        self._sol.populate(rows_s, list_font, icon_provider=self._icon_provider)

    def focus(self, entity_id: int) -> None:
        """
        Single-click in System tab:
          • Negative => star/system sentinel: center star in Solar.
          • Positive => concrete location id: center on that location.
        """
        solar_widget = getattr(self._tabs, "solar", None)

        try:
            if int(entity_id) < 0:
                sys_id = -int(entity_id)
                center_sys = getattr(self._tabs, "center_solar_on_system", None)
                if callable(center_sys):
                    try:
                        center_sys(sys_id)
                    except Exception:
                        pass
                    return
                if solar_widget is not None:
                    try:
                        if hasattr(solar_widget, "center_on_system"):
                            solar_widget.center_on_system(sys_id)
                            return
                        if hasattr(solar_widget, "center_on_entity"):
                            solar_widget.center_on_entity(-sys_id)
                            return
                    except Exception:
                        pass
                return
            else:
                loc_id = int(entity_id)
                center_loc = getattr(self._tabs, "center_solar_on_location", None)
                if callable(center_loc):
                    try:
                        center_loc(loc_id)
                    except Exception:
                        pass
                    return
                if solar_widget is not None and hasattr(solar_widget, "center_on_entity"):
                    try:
                        solar_widget.center_on_entity(loc_id)
                    except Exception:
                        pass
        except Exception:
            pass

    def open(self, entity_id: int) -> None:
        """
        Double-click in System tab:
          - System row (entity_id < 0): ensure that system is loaded in Solar and centered.
          - Location row (entity_id >= 0): center on that location.
        """
        try:
            tabs = getattr(self._tabs, "tabs", None)
            solar = getattr(self._tabs, "solar", None)

            if entity_id < 0:
                system_id = -int(entity_id)
                if solar and hasattr(solar, "load") and hasattr(solar, "center_on_system"):
                    try:
                        solar.load(system_id)
                        solar.center_on_system(system_id)
                    except Exception:
                        try:
                            solar.center_on_entity(-system_id)
                        except Exception:
                            pass
            else:
                if solar and hasattr(solar, "center_on_entity"):
                    try:
                        solar.center_on_entity(int(entity_id))
                    except Exception:
                        pass

            # Ensure we are on the Solar tab
            if tabs is not None:
                try:
                    if getattr(tabs, "count", lambda: 0)() >= 2:
                        tabs.setCurrentIndex(1)  # Galaxy=0, Solar=1
                except Exception:
                    pass
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

    def _fmt_system_distance(self, td: Dict[str, Any]) -> str:
        same = bool(td.get("same_system", False))
        au = _safe_float(td.get("dist_au", 0.0), 0.0)
        if same:
            return f"{au:.2f} AU"
        ly = _safe_float(td.get("dist_ly", 0.0), 0.0)
        tail_au = _safe_float(td.get("intra_target_au", 0.0), 0.0)
        return f"{ly:.2f} ly + {tail_au:.2f} AU"

    # ---------- helpers ----------

    def _norm_kind(self, v):
        try:
            k = str(v or "").lower().strip()
        except Exception:
            return ""
        if k in ("warp gate", "warp_gate"):
            return "warp_gate"
        return k

# ---------- row builders ----------

    def _build_system_rows(self, viewed_sys_id: int, cur_loc_id: int, cur_sys_id: int) -> List[Dict[str, Any]]:
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
            # Load real locations from DB (including star). Map fields to expected keys.
            try:
                for loc in db.get_locations(viewed_sys_id):
                    d = dict(loc)
                    mapped = {
                        "id": d.get("location_id"),
                        "system_id": d.get("system_id", viewed_sys_id),
                        "name": d.get("location_name"),
                        "kind": (d.get("location_type") or "").lower(),
                        "icon_path": d.get("icon_path"),
                        "x": d.get("local_x_au", d.get("location_x", 0.0)),
                        "y": d.get("local_y_au", d.get("location_y", 0.0)),
                        "parent_location_id": d.get("parent_location_id"),
                    }
                    entities.append(mapped)
            except Exception:
                pass

        # Normalize: keep only real locations; strip any system/sentinel rows and ensure the STAR is present
        try:
            db_locs = db.get_locations(viewed_sys_id) or []
        except Exception:
            db_locs = []
        # Find the authoritative star location (if any)
        star_loc = None
        for _dl in db_locs:
            if self._norm_kind(_dl.get("kind") or _dl.get("location_type")) == "star":
                star_loc = _dl
                break

        normalized_entities: List[Dict[str, Any]] = []
        has_star = False
        for e in entities:
            eid = int(e.get("id", e.get("location_id", 0)) or 0)
            kind = self._norm_kind(e.get("kind") or e.get("location_type"))
            # Drop system rows or synthetic negatives
            if eid < 0 or kind == "system":
                continue
            # Track if we already have the real star
            if kind == "star":
                has_star = True
            mapped = {
                "id": eid,
                "system_id": int(e.get("system_id", viewed_sys_id) or viewed_sys_id),
                "name": e.get("name") or e.get("location_name"),
                "kind": kind or "location",
                "icon_path": e.get("icon_path"),
                "x": e.get("x", e.get("local_x_au", e.get("location_x", 0.0))),
                "y": e.get("y", e.get("local_y_au", e.get("location_y", 0.0))),
                "parent_location_id": e.get("parent_location_id"),
            }
            normalized_entities.append(mapped)

        if not has_star and star_loc is not None:
            normalized_entities.append({
                "id": _safe_int(star_loc.get("id", star_loc.get("location_id")), 0),
                "system_id": _safe_int(star_loc.get("system_id", viewed_sys_id), viewed_sys_id),
                "name": star_loc.get("name", star_loc.get("location_name")),
                "kind": "star",
                "icon_path": star_loc.get("icon_path"),
                "x": star_loc.get("local_x_au", star_loc.get("location_x", 0.0)),
                "y": star_loc.get("local_y_au", star_loc.get("location_y", 0.0)),
                "parent_location_id": star_loc.get("parent_location_id"),
            })

        entities = normalized_entities

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
            parent_id_val = e.get("parent_location_id")
            if parent_id_val is None and kind in ("moon", "station") and eid >= 0:
                if not locrow_cache:
                    locrow_cache = db.get_location(eid) or {}
                parent_id_val = locrow_cache.get("parent_location_id")

            td: Dict[str, Any] = {}
            if travel and hasattr(travel, "get_travel_display_data"):
                try:
                    td = travel.get_travel_display_data("loc", eid) or {}
                except Exception:
                    td = {}

            # fuel fallback
            fuel_cost_val = td.get("fuel_cost", None)
            if not isinstance(fuel_cost_val, (int, float)) or fuel_cost_val <= 0:
                dx = exf - cur_x
                dy = eyf - cur_y
                dist_au = math.hypot(dx, dy)
                fuel_cost_val = _fallback_fuel_from_au(dist_au)

            same_system = bool(td.get("same_system", sys_id == cur_sys_id))

            if "can_reach_jump" in td:
                can_reach_jump = bool(td.get("can_reach_jump"))
            else:
                can_reach_jump = True if same_system else False

            can_reach_fuel = bool(td.get("can_reach_fuel", True))
            can_reach = bool(td.get("can_reach", True))

            is_current_system = (eid < 0 and (-eid == cur_sys_id))

            rows.append({
                "id": int(eid),
                "name": e.get("name", e.get("location_name", "Location")),
                "kind": kind,
                "distance": self._fmt_system_distance(td),
                "dist_ly": _safe_float(td.get("dist_ly", 0.0), 0.0),
                "dist_au": _safe_float(td.get("dist_au", 0.0), 0.0),
                "fuel_cost": int(fuel_cost_val) if fuel_cost_val and fuel_cost_val > 0 else "—",
                "x": exf,
                "y": eyf,
                "system_id": sys_id,
                "icon_path": e.get("icon_path"),
                "is_current_system": bool(is_current_system),
                "is_current": (eid == cur_loc_id) if eid >= 0 else False,
                "can_reach": bool(can_reach),
                "can_reach_jump": bool(can_reach_jump),
                "can_reach_fuel": bool(can_reach_fuel),
                "parent_location_id": parent_id_val,
            })

        return rows
