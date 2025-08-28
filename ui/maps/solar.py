# ui/maps/solar.py
"""
SolarMapWidget (display-only, GIF-first assets):
- central star at (0, 0) using a star GIF (or a visible placeholder if missing)
- planets on orbit rings (deterministic angles), with UNIQUE planet GIF per system when available
- stations use UNIQUE station GIFs per system; stations orbit their parent planet, else the star
- moons orbit their parent planet
- resource nodes on outer rings
- background drawn in scene/viewport space via BackgroundView
- animated starfield overlay
- get_entities() surfaces assigned icon_path so list thumbnails can match the map
- resolve_entity(): returns ('star', system_id) or ('loc', location_id)
"""
from __future__ import annotations

import json
import math
import random
import time
from math import cos, radians, sin
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPen, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from data import db
from .background_view import BackgroundView
# uses list_images so static PNG/JPG/SVG are supported too (if present)
from .icons import AnimatedGifItem, list_gifs, list_images, make_map_symbol_item
from game_controller.sim_loop import universe_sim

# --- Assets ---
ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
SOLAR_BG_DIR = ASSETS_ROOT / "solar_backgrounds"
STARS_DIR = ASSETS_ROOT / "stars"
PLANETS_DIR = ASSETS_ROOT / "planets"
STATIONS_DIR = ASSETS_ROOT / "stations"
WARP_GATES_DIR = ASSETS_ROOT / "warpgates"  # corrected folder name
MOONS_DIR = ASSETS_ROOT / "moons"
GAS_DIR = ASSETS_ROOT / "gas_clouds"
ASTEROID_DIR = ASSETS_ROOT / "asteroid_fields"
ICE_DIR      = ASSETS_ROOT / "ice_fields"
CRYSTAL_DIR  = ASSETS_ROOT / "crystal_veins"


def _to_int(x: object) -> Optional[int]:
    try:
        return int(x)  # type: ignore[arg-type]
    except Exception:
        return None


def _row_id(row: Dict) -> Optional[int]:
    return row.get("id") or row.get("location_id")  # type: ignore[return-value]


def _row_kind(row: Dict) -> str:
    k = row.get("kind") or row.get("location_type") or ""
    return str(k).lower().strip()


def _db_icons_only() -> bool:
    """
    Read the DB-only icons toggle from the active save's meta.json.
    Defaults to False (lenient) so visuals appear even if DB lacks explicit icons.
    """
    try:
        try:
            from save.manager import SaveManager  # type: ignore
            save_dir = SaveManager.active_save_dir()  # type: ignore[attr-defined]
        except Exception:
            save_dir = None

        if not save_dir:
            return False

        meta_path = Path(save_dir) / "meta.json"
        if not meta_path.exists():
            return False

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        art = meta.get("art") or {}
        return bool(meta.get("db_icons_only", art.get("db_icons_only", False)))
    except Exception:
        return False


class SolarMapWidget(BackgroundView):
    logMessage = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # GPU-accelerated path when available
        try:
            self.setViewport(QOpenGLWidget())
        except Exception:
            pass

        # Items move often → bounding-rect updates are fine
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        # Smooth GIF movement, no global AA
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        try:
            self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        except Exception:
            pass

        # State
        self._items: Dict[int, QGraphicsItem] = {}            # location_id / synthetic id -> item
        self._drawpos: Dict[int, Tuple[float, float]] = {}    # scene coords (px)
        self._assigned_icons: Dict[int, Optional[str]] = {}   # entity id -> icon path (str/qrc)
        self._orbit_specs: List[Dict[str, float | int | None]] = []
        self._orbit_timer: Optional[QTimer] = None
        self._orbit_interval_ms: int = 16
        self._orbit_t0: float = 0.0

        self._player_highlight: Optional[QGraphicsItem] = None
        self._system_id: Optional[int] = None
        self._locs_cache: List[Dict] = []

        self._star_item: Optional[QGraphicsItem] = None
        self._star_radius_px: float = 20.0

        # Visual scale: we place items directly in pixels using a spread factor
        self._spread: float = 12.0
        # make ring spacing configurable (roomy defaults)
        self._ring_gap_au: float = 10.4
        self._base_orbit_au: float = 10.0

        # If BackgroundView exposes unit scaling, keep it harmless
        try:
            self.set_unit_scale(1.0)  # use raw px in this widget
        except Exception:
            pass

        # Starfield & background
        self.enable_starfield(True)
        self.set_background_mode("viewport")

    # adjustable orbit layout
    def set_ring_gap_au(self, gap_au: float, *, reload: bool = True) -> None:
        try:
            g = float(gap_au)
            if g > 0:
                self._ring_gap_au = g
                if reload and self._system_id is not None:
                    self.load(int(self._system_id))
        except Exception:
            pass

    def set_base_orbit_au(self, base_au: float, *, reload: bool = True) -> None:
        try:
            b = float(base_au)
            if b > 0:
                self._base_orbit_au = b
                if reload and self._system_id is not None:
                    self.load(int(self._system_id))
        except Exception:
            pass

    def set_spread_px_per_au(self, px_per_au: float, *, reload: bool = True) -> None:
        try:
            s = float(px_per_au)
            if s > 0:
                self._spread = s
                if reload and self._system_id is not None:
                    self.load(int(self._system_id))
        except Exception:
            pass

    # ---------- Public API ----------
    def get_entities(self) -> List[Dict]:
        """Expose entities for list panes, with icon_path set to the GIFs in use.
        Includes a synthetic star row (id = -system_id).
        """
        if self._system_id is None:
            return []

        rows = [dict(r) for r in db.get_locations(self._system_id)]
        # Carry over the icon we actually used in the scene if set
        for r in rows:
            lid = _row_id(r)
            if lid is not None and lid in self._assigned_icons:
                r["icon_path"] = self._assigned_icons.get(lid)

        sys_row = db.get_system(self._system_id)
        if sys_row:
            star_icon: Optional[str] = None
            db_only = _db_icons_only()
            db_path = sys_row.get("star_icon_path") or ""
            if db_path:
                star_icon = str(db_path)
            else:
                if not db_only:
                    star_imgs = list_images(STARS_DIR)
                    if star_imgs:
                        rng = random.Random(10_000 + int(self._system_id))
                        star_icon = str(star_imgs[rng.randrange(len(star_imgs))])
            rows.insert(
                0,
                {
                    "id": -int(self._system_id),
                    "system_id": int(self._system_id),
                    "name": f"{sys_row.get('name', '')} (Star)",
                    "kind": "star",
                    "icon_path": star_icon,
                },
            )
        return rows

    def resolve_entity(self, entity_id: int) -> Optional[Tuple[str, int]]:
        """Return ('star', system_id) for negatives, ('loc', id) for existing items."""
        if entity_id < 0 and self._system_id is not None:
            return ("star", int(self._system_id))
        if int(entity_id) in self._items:
            return ("loc", int(entity_id))
        return None

    def center_on_entity(self, entity_id: int) -> None:
        # Stars use negative ids of the form -system_id
        if entity_id < 0:
            target_sys_id = -entity_id
            if self._system_id != target_sys_id:
                self.load(target_sys_id)
            self.center_on_system(target_sys_id)
            return

        loc = db.get_location(entity_id) or {}
        target_sys_id = _to_int(loc.get("system_id") or loc.get("system"))
        if target_sys_id is not None and self._system_id != target_sys_id:
            self.load(target_sys_id)
        self.center_on_location(entity_id)

    def map_entity_to_viewport(self, entity_id: int) -> Optional[QPoint]:
        info = self.get_entity_viewport_center_and_radius(entity_id)
        return info[0] if info else None

    def get_entity_viewport_center_and_radius(
        self, entity_id: int
    ) -> Optional[Tuple[QPoint, float]]:
        if entity_id < 0:
            center = self.mapFromScene(QPointF(0.0, 0.0))
            return (center, self._star_radius_px)

        item = self._items.get(entity_id)
        if not item:
            return None
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        center = self.mapFromScene(rect.center())
        radius = max(rect.width(), rect.height()) * 0.5
        return (center, radius)

    # ---------- Core ----------
    def load(self, system_id: int) -> None:
        try:
            universe_sim.set_visible_system(int(system_id))
        except Exception:
            pass
        self._system_id = system_id

        # Clear scene and state
        self._scene.clear()
        self._items.clear()
        self._drawpos.clear()
        self._orbit_specs.clear()
        self._assigned_icons.clear()
        self._player_highlight = None
        self._star_item = None

        # Cache rows
        try:
            self._locs_cache = [dict(r) for r in (db.get_locations(system_id) or [])]
        except Exception:
            self._locs_cache = []

        # Background selection
        candidates = [
            SOLAR_BG_DIR / f"system_bg_{system_id}.png",
            SOLAR_BG_DIR / "system_bg_01.png",
            SOLAR_BG_DIR / "default.png",
        ]
        bg_path = next((p for p in candidates if p.exists()), None)
        self.set_background_image(str(bg_path) if bg_path else None)

        # Group by kind (normalized)
        planets    = [l for l in self._locs_cache if _row_kind(l) == "planet"]
        stations   = [l for l in self._locs_cache if _row_kind(l) == "station"]
        warp_gates = [l for l in self._locs_cache if _row_kind(l) in ("warp_gate", "warpgate", "warp gate")]
        moons      = [l for l in self._locs_cache if _row_kind(l) == "moon"]

        # --- Resource nodes come from resource_nodes (not locations) ---
        try:
            res_all = [dict(r) for r in (db.get_resource_nodes(system_id) or [])]
        except Exception:
            res_all = []

        # Schema uses: asteroid_field, gas_cloud, ice_field, crystal_vein
        rt = lambda v: str(v or "").strip().lower()
        res_asteroid = [r for r in res_all if rt(r.get("resource_type")) == "asteroid_field"]
        res_gas      = [r for r in res_all if rt(r.get("resource_type")) in ("gas_cloud", "gas_clouds")]
        res_ice      = [r for r in res_all if rt(r.get("resource_type")) == "ice_field"]
        res_crystal  = [r for r in res_all if rt(r.get("resource_type")) == "crystal_vein"]

        # Scene rect: generous padding around outermost ring
        ring_gap_au = self._ring_gap_au
        base_au = self._base_orbit_au
        n_outer_bands = len(warp_gates) + len(res_asteroid) + len(res_gas) + len(res_ice) + len(res_crystal)
        max_r_au = base_au + (len(planets) + n_outer_bands + 2) * ring_gap_au
        pad = 2.0
        R = (max_r_au + pad) * self._spread
        self._scene.setSceneRect(-R, -R, 2 * R, 2 * R)

        # Catalogs (use list_images so PNG/JPG/SVG/GIF all work)
        star_imgs     = list_images(STARS_DIR)
        planet_imgs   = list_images(PLANETS_DIR)
        station_imgs  = list_images(STATIONS_DIR)
        gate_imgs     = list_images(WARP_GATES_DIR)
        moon_imgs     = list_images(MOONS_DIR)
        asteroid_imgs = list_images(ASTEROID_DIR)
        gas_imgs      = list_images(GAS_DIR)
        ice_imgs      = list_images(ICE_DIR)
        crystal_imgs  = list_images(CRYSTAL_DIR)

        # Deterministic RNG per system
        rng = random.Random(10_000 + system_id)

        # Strict DB-only toggle
        db_only = _db_icons_only()

        # -------- Star (always draw; placeholder if missing) --------
        sys_row = db.get_system(system_id) or {}
        star_icon_path = sys_row.get("star_icon_path") or ""
        star_path: Optional[str] = None
        if star_icon_path:
            star_path = str(star_icon_path)
        elif not db_only and star_imgs:
            star_path = str(star_imgs[rng.randrange(len(star_imgs))])

        min_px_star, max_px_star = 180, 300
        desired_px_star = rng.randint(min_px_star, max_px_star)
        star_item = make_map_symbol_item(star_path or "", int(desired_px_star), self, salt=system_id)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)
        self._scene.addItem(star_item)
        try:
            star_item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception:
            pass
        self._star_item = star_item
        self._star_radius_px = desired_px_star / 2.0

        # -------- Helpers for unique assignments (store strings, not Paths) --------
        def assign_icons(paths: List[Path], rows: List[Dict], salt: int) -> Dict[int, Optional[str]]:
            mapping: Dict[int, Optional[str]] = {}
            if not rows:
                return mapping
            rows_sorted = sorted(rows, key=lambda r: _row_id(r) or 0)
            remaining_paths = [str(p) for p in paths]
            rng_local = random.Random(77_000 + system_id * 13 + salt)
            rng_local.shuffle(remaining_paths)
            i = 0
            for r in rows_sorted:
                rid = _row_id(r)
                if rid is None:
                    continue
                db_icon = r.get("icon_path") or ""
                if db_icon:
                    mapping[rid] = str(db_icon)
                    continue
                if db_only:
                    mapping[rid] = None
                    continue
                mapping[rid] = remaining_paths[i] if i < len(remaining_paths) else (remaining_paths[-1] if remaining_paths else None)
                i += 1
            return mapping

        planet_map   = assign_icons(planet_imgs,   planets,    1)
        station_map  = assign_icons(station_imgs,  stations,   2)
        gate_map     = assign_icons(gate_imgs,     warp_gates, 3)
        moon_map     = assign_icons(moon_imgs,     moons,      4)

        # Resource nodes: KEY BY location_id (matches schema + join)
        def assign_resource_icons(paths: List[Path], rows: List[Dict], salt: int) -> Dict[int, Optional[str]]:
            mapping: Dict[int, Optional[str]] = {}
            remaining = [str(p) for p in paths]
            rng_local = random.Random(88_000 + system_id * 17 + salt)
            rng_local.shuffle(remaining)
            i = 0
            for r in rows:
                rid = _to_int(r.get("location_id"))  # <-- FIX: use location_id
                if rid is None:
                    continue
                db_icon = r.get("icon_path") or ""
                if db_icon:
                    mapping[rid] = str(db_icon)
                    continue
                if db_only:
                    mapping[rid] = None
                    continue
                mapping[rid] = remaining[i] if i < len(remaining) else (remaining[-1] if remaining else None)
                i += 1
            return mapping

        asteroid_map = assign_resource_icons(asteroid_imgs, res_asteroid, 5)
        gas_map      = assign_resource_icons(gas_imgs,      res_gas,      6)
        ice_map      = assign_resource_icons(ice_imgs,      res_ice,      7)
        crystal_map  = assign_resource_icons(crystal_imgs,  res_crystal,  8)

        # -------- Orbit rings (under everything) --------
        ring_pen = QPen(QColor(200, 210, 230, 200))
        ring_pen.setCosmetic(True)
        ring_pen.setWidth(1)
        ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        ring_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        for i in range(len(planets)):
            r_au = base_au + i * ring_gap_au
            r = r_au * self._spread
            ring = self._scene.addEllipse(-r, -r, 2 * r, 2 * r, ring_pen)
            ring.setZValue(-9)
            try:
                ring.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass

        # -------- Planets --------
        min_px_planet, max_px_planet = 45, 95
        n_planets = max(1, len(planets))
        for i, l in enumerate(sorted(planets, key=lambda r: _row_id(r) or 0)):
            desired_px = (
                (min_px_planet + max_px_planet) / 2.0
                if n_planets == 1
                else (min_px_planet + (max_px_planet - min_px_planet) * (i / (n_planets - 1)))
            )
            ring_r = (base_au + i * ring_gap_au) * self._spread
            angle_deg = (((_row_id(l) or 0) * 73.398) % 360.0)
            a0 = radians(angle_deg)
            x = ring_r * cos(a0)
            y = ring_r * sin(a0)
            lid = _row_id(l) or 0
            icon = planet_map.get(lid)
            item = make_map_symbol_item(icon or "", int(desired_px), self, salt=lid)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._drawpos[lid] = (x, y)
            self._assigned_icons[lid] = icon

            base_speed = random.Random(15_000 + system_id * 41 + lid).uniform(0.05, 0.12)
            omega = base_speed * (1.0 / (1.0 + i * 0.25))
            self._orbit_specs.append({
                "id": lid, "parent": None, "radius_px": ring_r, "theta0": a0, "omega": omega, "angle": a0
            })

        planet_ids = [pid for pid in (_row_id(p) for p in planets) if pid is not None]

        # -------- Stations --------
        min_px_station, max_px_station = 15, 18
        station_rows = sorted(stations, key=lambda r: _row_id(r) or 0)
        for j, l in enumerate(station_rows):
            lid = _row_id(l) or 0
            parent_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            if parent_from_db in planet_ids:
                parent_id = parent_from_db  # type: ignore[assignment]
            elif planet_ids:
                parent_id = planet_ids[j % len(planet_ids)]  # type: ignore[assignment]
            else:
                parent_id = None  # type: ignore[assignment]

            if parent_id is not None:
                radius_px = 8.0
                px, py = self._drawpos.get(parent_id, (0.0, 0.0))
            else:
                radius_px = ((base_au + 0.5) * self._spread) * 0.5
                px, py = (0.0, 0.0)

            a0 = radians(((lid * 211.73) % 360.0))
            sx = px + radius_px * math.cos(a0)
            sy = py + radius_px * math.sin(a0)
            icon = station_map.get(lid)
            desired_px = int(min_px_station + (max_px_station - min_px_station) * (j / max(1, len(station_rows) - 1)))
            item = make_map_symbol_item(icon or "", desired_px, self, salt=lid)
            item.setPos(sx, sy)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._assigned_icons[lid] = icon
            omega = random.Random(17_000 + system_id * 97 + lid).uniform(0.15, 0.30)
            self._orbit_specs.append({
                "id": lid, "parent": parent_id, "radius_px": radius_px, "theta0": a0, "omega": omega, "angle": a0
            })

        # -------- Warp Gates --------
        gate_rows = sorted(warp_gates, key=lambda r: _row_id(r) or 0)
        for k, l in enumerate(gate_rows):
            lid = _row_id(l) or 0
            outer_index = len(planets) + k
            ring_r = (base_au + outer_index * ring_gap_au) * self._spread

            ring = self._scene.addEllipse(-ring_r, -ring_r, 2 * ring_r, 2 * ring_r, ring_pen)
            ring.setZValue(-9)
            try:
                ring.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass

            angle_deg = (((lid * 73.398) % 360.0) + (180 if k % 2 == 0 else 0))
            a0 = radians(angle_deg)
            x = ring_r * cos(a0)
            y = ring_r * sin(a0)
            icon = gate_map.get(lid)
            size_px = int(20 + (10 * (k / max(1, len(gate_rows) - 1))))
            item = make_map_symbol_item(icon or "", size_px, self, salt=lid)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._assigned_icons[lid] = icon
            base_speed = random.Random(19_000 + system_id * 131 + lid).uniform(0.08, 0.15)
            omega = base_speed * (1.0 / (1.0 + outer_index * 0.25))
            self._orbit_specs.append({
                "id": lid, "parent": None, "radius_px": ring_r, "theta0": a0, "omega": omega, "angle": a0
            })

        # -------- Moons --------
        moon_rows = sorted(moons, key=lambda r: _row_id(r) or 0)
        ring_gap_px = ring_gap_au * self._spread
        max_sat_radius = max(3.0, min(10.0, ring_gap_px * 0.6))
        base_sat_radii = [max_sat_radius * 0.35, max_sat_radius * 0.55, max_sat_radius * 0.75]
        sat_radii = sorted({max(3.0, min(float(r), max_sat_radius - 0.75)) for r in base_sat_radii})
        planet_ids = [pid for pid in (_row_id(p) for p in planets) if pid is not None]
        next_radius_index: Dict[int, int] = {pid: 0 for pid in planet_ids}

        for m_idx, l in enumerate(moon_rows):
            lid = _row_id(l) or 0
            pid_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            parent_id = pid_from_db if pid_from_db in planet_ids else (planet_ids[m_idx % len(planet_ids)] if planet_ids else None)
            parent_key = int(parent_id) if parent_id is not None else 0
            px, py = self._drawpos.get(parent_key, (0.0, 0.0))

            ridx = next_radius_index.get(parent_key, 0)
            ridx = min(ridx, max(0, len(sat_radii) - 1))
            radius_px = sat_radii[ridx] if sat_radii else 5.0
            next_radius_index[parent_key] = min(ridx + 1, max(0, len(sat_radii) - 1))

            a0 = radians((((lid * 997.13) % 360.0)))
            mx = px + radius_px * math.cos(a0)
            my = py + math.sin(a0) * radius_px
            icon = moon_map.get(lid)
            desired_px = int(random.Random(21_000 + system_id * 29 + lid).uniform(14, 18))
            item = make_map_symbol_item(icon or "", desired_px, self, salt=lid)
            item.setPos(mx, my)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._assigned_icons[lid] = icon
            omega = random.Random(23_000 + system_id * 171 + lid).uniform(0.20, 0.35)
            self._orbit_specs.append({
                "id": lid, "parent": parent_id, "radius_px": radius_px, "theta0": a0, "omega": omega, "angle": a0
            })

        # -------- Resource Nodes (outer rings after gates) --------
        # Use the real location_id so selection/resolve works uniformly.
        def place_resources(rows: List[Dict], icon_map: Dict[int, Optional[str]], start_outer_index: int, size_px: int) -> int:
            count = 0
            for n, l in enumerate(rows):
                rid = _to_int(l.get("location_id")) or 0  # <-- FIX: use location_id
                outer_index = len(planets) + len(gate_rows) + start_outer_index + n
                ring_r = (base_au + outer_index * ring_gap_au) * self._spread

                ring = self._scene.addEllipse(-ring_r, -ring_r, 2 * ring_r, 2 * ring_r, ring_pen)
                ring.setZValue(-9)
                try:
                    ring.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
                except Exception:
                    pass

                angle_deg = (((rid * 61.713) + n * 37.0) % 360.0)
                a0 = radians(angle_deg)
                x = ring_r * cos(a0)
                y = ring_r * sin(a0)
                icon = icon_map.get(rid)
                item = make_map_symbol_item(icon or "", size_px, self, salt=rid)
                item.setPos(x, y)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                self._scene.addItem(item)
                try:
                    item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
                except Exception:
                    pass
                ent_id = rid  # <-- FIX: use real location_id (no offset)
                self._items[ent_id] = item
                self._assigned_icons[ent_id] = icon
                base_speed = random.Random(25_000 + system_id * 211 + rid).uniform(0.04, 0.07)
                omega = base_speed * (1.0 / (1.0 + outer_index * 0.15))
                self._orbit_specs.append({
                    "id": ent_id, "parent": None, "radius_px": ring_r, "theta0": a0, "omega": omega, "angle": a0
                })
                count += 1
            return count

        outer_cursor = 0
        outer_cursor += place_resources(sorted(res_asteroid, key=lambda r: _to_int(r.get("location_id")) or 0), asteroid_map, outer_cursor, 22)
        outer_cursor += place_resources(sorted(res_gas,      key=lambda r: _to_int(r.get("location_id")) or 0), gas_map,      outer_cursor, 22)
        outer_cursor += place_resources(sorted(res_ice,      key=lambda r: _to_int(r.get("location_id")) or 0), ice_map,      outer_cursor, 22)
        outer_cursor += place_resources(sorted(res_crystal,  key=lambda r: _to_int(r.get("location_id")) or 0), crystal_map,  outer_cursor, 22)

        # Start/stop orbits based on global flag
        try:
            self.set_animations_enabled(getattr(self, "_animations_enabled", True))
        except Exception:
            pass

        # Highlight player location if available
        player = db.get_player_full()
        if player and player.get("current_player_location_id") is not None:
            self.refresh_highlight(player["current_player_location_id"])

        # Center on star
        self.center_on_system(system_id)

    # ---------- Highlight / Center ----------
    def refresh_highlight(self, location_id: Optional[int]) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None
        if location_id is None:
            return
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        center = rect.center()
        r = max(rect.width(), rect.height()) * 0.9
        ring = self._scene.addEllipse(center.x() - r, center.y() - r, 2 * r, 2 * r)
        pen = ring.pen()
        pen.setWidthF(0.1)
        ring.setPen(pen)
        self._player_highlight = ring

    def center_on_system(self, system_id: int | None) -> None:
        try:
            sid = system_id if system_id is not None else getattr(self, "_system_id", None)
            if sid is not None:
                universe_sim.set_visible_system(int(sid))
        except Exception:
            pass
        self.centerOn(0.0, 0.0)

    def center_on_location(self, location_id: int) -> None:
        try:
            sid = getattr(self, "_system_id", None)
            if sid is not None:
                universe_sim.set_visible_system(int(sid))
        except Exception:
            pass
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        self.centerOn(rect.center())

    # ---------- Animations ----------
    def set_animations_enabled(self, enabled: bool) -> None:
        super().set_animations_enabled(enabled)
        if enabled:
            if self._orbit_timer is None:
                self._orbit_timer = QTimer(self)
                self._orbit_timer.setTimerType(Qt.TimerType.PreciseTimer)
                self._orbit_timer.timeout.connect(self._tick_orbits)  # type: ignore[attr-defined]
            self._orbit_timer.setInterval(self._orbit_interval_ms)
            self._orbit_t0 = time.monotonic()
            if not self._orbit_timer.isActive():
                self._orbit_timer.start()
        else:
            if self._orbit_timer is not None and self._orbit_timer.isActive():
                self._orbit_timer.stop()

    def _tick_orbits(self) -> None:
        if not self._orbit_specs or not self._items:
            return
        now = time.monotonic()

        # Visible rect (with margin) to manage GIF playback
        vis_rect = self.mapToScene(self.viewport().rect()).boundingRect().adjusted(-120, -120, 120, 120)

        def _maybe_move(item: QGraphicsItem, x: float, y: float) -> None:
            visible = vis_rect.contains(x, y)
            try:
                if isinstance(item, AnimatedGifItem):
                    item.set_playing(visible)
            except Exception:
                pass
            if not visible:
                return
            cur = item.pos()
            if (abs(cur.x() - x) < 0.15) and (abs(cur.y() - y) < 0.15):
                return
            item.setPos(x, y)

        # Parents (around star)
        parent_pos: Dict[int | None, Tuple[float, float]] = {None: (0.0, 0.0)}
        for spec in self._orbit_specs:
            if spec.get("parent") is None:
                theta0_v = spec.get("theta0", 0.0)
                omega_v = spec.get("omega", 0.0)
                theta0 = float(theta0_v) if theta0_v is not None else 0.0
                omega = float(omega_v) if omega_v is not None else 0.0
                a = (theta0 + omega * (now - self._orbit_t0)) % (2.0 * math.pi)
                spec["angle"] = a
                r_v = spec.get("radius_px", 0.0)
                r = float(r_v) if r_v is not None else 0.0
                x = r * math.cos(a)
                y = r * math.sin(a)
                id_v = spec.get("id")
                ent_id = int(id_v) if id_v is not None else 0
                item = self._items.get(ent_id)
                if item is not None:
                    _maybe_move(item, x, y)
                parent_pos[ent_id] = (x, y)

        # Children (around parent)
        for spec in self._orbit_specs:
            if spec.get("parent") is not None:
                theta0_v = spec.get("theta0", 0.0)
                omega_v = spec.get("omega", 0.0)
                theta0 = float(theta0_v) if theta0_v is not None else 0.0
                omega = float(omega_v) if omega_v is not None else 0.0
                a = (theta0 + omega * (now - self._orbit_t0)) % (2.0 * math.pi)
                spec["angle"] = a
                r_v = spec.get("radius_px", 0.0)
                r = float(r_v) if r_v is not None else 0.0
                parent_v = spec.get("parent")
                parent_key = int(parent_v) if parent_v is not None else None
                px, py = parent_pos.get(parent_key, (0.0, 0.0))
                x = px + r * math.cos(a)
                y = py + r * math.sin(a)
                id_v = spec.get("id")
                ent_id = int(id_v) if id_v is not None else 0
                item = self._items.get(ent_id)
                if item is not None:
                    _maybe_move(item, x, y)
