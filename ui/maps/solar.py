"""
SolarMapWidget (display-only, GIF-only assets):
- central star at (0,0) using a star GIF
- planets on orbit rings (deterministic angles), each with a UNIQUE planet GIF in this system
- stations with UNIQUE station GIFs for this system; stations orbit their parent planet, else the star
- background drawn in SCENE space (centered), so it aligns visually with (0,0)
- animated starfield overlay
- get_entities() surfaces assigned icon_path so list thumbnails match the map exactly
"""

from __future__ import annotations

import time, math, random
from math import radians, sin, cos
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, Signal
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from data import db
from .panzoom_view import PanZoomView
from .icons import make_map_symbol_item, list_gifs

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
SOL_BG_DIR   = ASSETS_ROOT / "solar_backgrounds"
STARS_DIR    = ASSETS_ROOT / "stars"
PLANETS_DIR  = ASSETS_ROOT / "planets"
STATIONS_DIR = ASSETS_ROOT / "stations"


class SolarMapWidget(PanZoomView):
    logMessage = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._items: Dict[int, QGraphicsItem] = {}         # location_id -> item (not star)
        self._drawpos: Dict[int, Tuple[float, float]] = {}  # scene coords
        self._player_highlight: Optional[QGraphicsItem] = None
        self._system_id: Optional[int] = None
        self._locs_cache: List[Dict] = []

        # Track assigned GIFs so list thumbnails are in sync
        self._assigned_icons: Dict[int, Optional[Path]] = {}  # location_id -> Path|None

        # Orbit animation
        self._orbit_specs = []  # list of dicts: id, parent, radius_px, angle, speed
        self._last_orbit_t = 0.0
        self._orbit_timer = None

        self._star_item: Optional[QGraphicsItem] = None
        self._star_entity_id: Optional[int] = None          # synthetic id = -system_id
        self._star_radius_px: float = 20.0

        self._spread = 12.0          # AU visual multiplier (orbit radii are in AU * spread)
        self.set_unit_scale(8.0)   # 1 AU base ~ 12 px
        self._apply_unit_scale()
        
        # Use a starfield here too
        self.enable_starfield(True)
        # Draw background in scene space so it aligns with (0,0)
        self.set_background_mode("viewport")

    # ---------- External list helpers ----------
    def get_entities(self) -> List[Dict]:
        """Expose entities for list panes, with icon_path set to the assigned GIFs.
        Stars get a deterministic star GIF consistent with load()."""
        if self._system_id is None:
            return []
        # base rows
        rows = [dict(r) for r in db.get_locations(self._system_id)]
        # apply assigned icons
        for r in rows:
            lid = r.get("id")
            if lid in self._assigned_icons:
                p = self._assigned_icons.get(lid)
                r["icon_path"] = str(p) if p is not None else None
        # inject star row at the top, with a deterministic star GIF
        star_row = db.get_system(self._system_id)
        if star_row:
            star_icon: Optional[Path] = None
            star_gifs = list_gifs(STARS_DIR)
            if star_gifs:
                rng = random.Random(10_000 + self._system_id)
                star_icon = star_gifs[rng.randrange(len(star_gifs))]
            sdict = dict(star_row)
            rows.insert(0, {
                "id": -self._system_id,
                "system_id": self._system_id,
                "name": sdict.get("name", "") + " (Star)",
                "kind": "star",
                "icon_path": str(star_icon) if star_icon is not None else None
            })
        return rows
    
    def center_on_entity(self, entity_id: int) -> None:
        if entity_id < 0:
            self.center_on_system(self._system_id)
        else:
            self.center_on_location(entity_id)

    def map_entity_to_viewport(self, entity_id: int) -> Optional[QPoint]:
        info = self.get_entity_viewport_center_and_radius(entity_id)
        return info[0] if info else None

    def get_entity_viewport_center_and_radius(self, entity_id: int) -> Optional[Tuple[QPoint, float]]:
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
        self._system_id = system_id

        # Clear everything to avoid duplicates / leftover items
        self._scene.clear()
        self._items.clear()
        self._drawpos.clear()
        self._orbit_specs.clear()
        self._assigned_icons.clear()
        self._player_highlight = None
        self._star_item = None
        self._star_entity_id = -system_id

        # Cache rows
        self._locs_cache = [dict(r) for r in db.get_locations(system_id)]

        # Background per system (optional, STATIC) — drawn in scene space
        # Accept both "default.png" and common typo "defaul.png"
        candidates = [
            SOL_BG_DIR / f"system_bg_{system_id}.png",
            SOL_BG_DIR / "default.png",
            SOL_BG_DIR / "defaul.png",
        ]
        bg_path = next((p for p in candidates if p.exists()), None)
        if bg_path:
            self.set_background_image(str(bg_path))
            self.logMessage.emit(f"Solar background (system {system_id}): {bg_path}")
        else:
            self.set_background_image(None)
            self.logMessage.emit(f"Solar background (system {system_id}): gradient (no image found).")

        # Layout ingredients
        planets = [l for l in self._locs_cache if l["kind"] == "planet"]
        stations = [l for l in self._locs_cache if l["kind"] == "station"]

        # Scene rect fits all rings comfortably around (0,0)
        n_rings = max(1, len(planets) + max(0, len(stations) // max(1, len(planets))) + 2)
        ring_gap_au = 1.2
        base_au = 1.5
        max_r_au = base_au + (n_rings + 1) * ring_gap_au
        pad = 2.0
        R = (max_r_au + pad) * self._spread
        self._scene.setSceneRect(-R, -R, 2 * R, 2 * R)

        # ---- GIF catalogs & deterministic unique assignments ----
        star_gifs    = list_gifs(STARS_DIR)
        planet_gifs  = list_gifs(PLANETS_DIR)
        station_gifs = list_gifs(STATIONS_DIR)

        rng = random.Random(10_000 + system_id)

        def pick_star_gif() -> Optional[Path]:
            if not star_gifs:
                return None
            return star_gifs[rng.randrange(len(star_gifs))]

        def assign_unique(paths: List[Path], count: int, salt: int) -> List[Optional[Path]]:
            """Return `count` unique paths (or None) deterministically for this system."""
            if not paths:
                return [None] * count
            local = paths[:]
            rng_local = random.Random(77_000 + system_id * 13 + salt)
            rng_local.shuffle(local)
            out: List[Optional[Path]] = [None] * count
            take = min(count, len(local))
            for i in range(take):
                out[i] = local[i]
            return out

        planet_rows = sorted(planets, key=lambda x: x["id"])
        station_rows = sorted(stations, key=lambda x: x["id"])

        planet_assignments  = assign_unique(planet_gifs,  len(planet_rows), 1)
        station_assignments = assign_unique(station_gifs, len(station_rows), 2)

        # ---- Orbit rings (under everything) ----
        from PySide6.QtGui import QPen, QColor
        pen = QPen()
        pen.setWidthF(0.1)
        # subtle bluish-gray ring color with alpha
        pen.setColor(QColor(200, 210, 230, 180))
        for i in range(len(planet_rows)):
            r = (base_au + i * ring_gap_au) * self._spread
            ring = self._scene.addEllipse(-r, -r, 2 * r, 2 * r, pen)
            ring.setZValue(-9)

        # ---- Central star (GIF-only) ----
        min_px_star = 100
        max_px_star = 250
        desired_px_star = rng.randint(min_px_star, max_px_star)
        star_gif = pick_star_gif()
        star_path = star_gif if star_gif is not None else Path("missing_star.gif")
        star_item = make_map_symbol_item(star_path, desired_px_star, self, salt=system_id)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)
        self._scene.addItem(star_item)
        self._star_item = star_item
        self._star_radius_px = desired_px_star / 2.0

        # ---- Planets (even angles, UNIQUE GIFs) ----
        # Planet sizes range from 30 to 75 px, evenly distributed
        min_px_planet = 30
        max_px_planet = 75
        n_planets = max(1, len(planet_rows))
        for i, l in enumerate(planet_rows):
            # Interpolate size between min and max
            if n_planets == 1:
                desired_px_planet = (min_px_planet + max_px_planet) / 2
            else:
                desired_px_planet = min_px_planet + (max_px_planet - min_px_planet) * (i / (n_planets - 1))
            ring_r = (base_au + i * ring_gap_au) * self._spread
            angle_deg = ((l["id"] * 73.398) % 360.0)
            a = radians(angle_deg)
            x = ring_r * cos(a)
            y = ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            pgif = planet_assignments[i] if i < len(planet_assignments) else None
            if pgif is None:
                self.logMessage.emit(f"WARNING: Not enough planet GIFs for system {system_id}; planet {l['id']} gets placeholder.")
                pgif = Path("missing_planet.gif")

            item = make_map_symbol_item(pgif, int(desired_px_planet), self, salt=l.get("id"))
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item
            # record assigned path for list thumbnails
            self._assigned_icons[l["id"]] = pgif

        # ---- Stations (between rings, UNIQUE GIFs) ----
        # 50% CLOSER orbits: halve previous radius (around planet) and halve interleaved case
        min_px_station = 15
        max_px_station = 18
        station_count = max(1, len(station_rows))
        for j, l in enumerate(station_rows):
            ring_index = min(len(planet_rows) - 1, j % max(1, len(planet_rows))) if planet_rows else 0
            base_ring_r = (base_au + ring_index * ring_gap_au + ring_gap_au * 0.5) * self._spread
            angle_deg = ((l["id"] * 137.50776) + 40.0) % 360.0
            a = radians(angle_deg)
            x = base_ring_r * cos(a)
            y = base_ring_r * sin(a)
            self._drawpos[l["id"]] = (x, y)

            sgif = station_assignments[j] if j < len(station_assignments) else None
            if sgif is None:
                self.logMessage.emit(f"WARNING: Not enough station GIFs for system {system_id}; station {l['id']} gets placeholder.")
                sgif = Path("missing_station.gif")

            # Size distributed across stations within the desired range [15, 25] px
            if station_count == 1:
                desired_px_station = (min_px_station + max_px_station) / 2
            else:
                desired_px_station = min_px_station + (max_px_station - min_px_station) * (j / (station_count - 1))

            item = make_map_symbol_item(sgif, int(desired_px_station), self, salt=l.get("id"))
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item
            self._assigned_icons[l["id"]] = sgif

        # ---- Build simple orbit specs (visual only) ----
        self._orbit_specs = []
        planet_ids = [l["id"] for l in planet_rows]

        # Speed ranges (tweak these to adjust overall slow/fast behavior per system)
        planet_speed_min = 0.05
        planet_speed_max = 0.12
        station_speed_min = 0.15
        station_speed_max = 0.30

        # Planets: orbit around the star at (0,0)
        for i, l in enumerate(planet_rows):
            ring_r = (base_au + i * ring_gap_au) * self._spread
            initial_angle = ((l["id"] * 73.398) % 360.0) * (math.pi / 180.0)
            # Pick a deterministic per-system/per-entity base speed between min/max, then scale by orbit index
            base_speed = rng.uniform(planet_speed_min, planet_speed_max)
            speed = base_speed * (1.0 / (1.0 + i * 0.25))
            self._orbit_specs.append({"id": l["id"], "parent": None, "radius_px": ring_r, "angle": initial_angle, "speed": speed})

        # Stations: orbit their ring's planet if exists, else the star — with 50% radius
        for j, l in enumerate(station_rows):
            if planet_ids:
                ring_index = min(len(planet_ids) - 1, j % len(planet_ids))
                parent_id = planet_ids[ring_index]
                radius_px = 8.0  # was 16.0 → 50% closer
            else:
                parent_id = None
                radius_px = ((base_au + 0.5) * self._spread) * 0.5  # halve interleaved distance

            # Compute initial angle from the already-placed station position so the orbit starts smoothly.
            # If the station orbits a planet, compute angle relative to the planet; otherwise relative to origin.
            parent_px, parent_py = (0.0, 0.0)
            if parent_id is not None:
                parent_px, parent_py = self._drawpos.get(parent_id, (0.0, 0.0))
            sx, sy = self._drawpos.get(l["id"], (0.0, 0.0))
            dx = sx - parent_px
            dy = sy - parent_py
            initial_angle = math.atan2(dy, dx)

            # Pick a deterministic per-system/per-entity station speed between min/max
            speed = rng.uniform(station_speed_min, station_speed_max)

            # Append the station orbit spec (previous code accidentally only appended for the else branch)
            self._orbit_specs.append({"id": l["id"], "parent": parent_id, "radius_px": radius_px, "angle": initial_angle, "speed": speed})

        # Start/stop orbits respecting global animation toggle
        try:
            self.set_animations_enabled(getattr(self, "_animations_enabled", True))
        except Exception:
            pass

        # Highlight player location if present
        player = db.get_player_full()
        if player and player.get("current_player_location_id"):
            self.refresh_highlight(player["current_player_location_id"])

        # Center the camera on the star (aligns background scene draw)
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
        pen.setWidthF(0.02)
        ring.setPen(pen)
        self._player_highlight = ring

    def center_on_system(self, system_id: int | None) -> None:
        self.centerOn(0.0, 0.0)

    def center_on_location(self, location_id: int) -> None:
        item = self._items.get(location_id)
        if not item:
            return
        rect = item.mapToScene(item.boundingRect()).boundingRect()
        self.centerOn(rect.center())

    # ---------- Animations ----------
    def set_animations_enabled(self, enabled: bool) -> None:
        super().set_animations_enabled(enabled)
        from PySide6.QtCore import QTimer
        if enabled:
            if self._orbit_timer is None:
                self._orbit_timer = QTimer(self)
                self._orbit_timer.setInterval(33)
                self._orbit_timer.timeout.connect(self._tick_orbits)
            self._last_orbit_t = time.monotonic()
            if not self._orbit_timer.isActive():
                self._orbit_timer.start()
        else:
            if self._orbit_timer is not None and self._orbit_timer.isActive():
                self._orbit_timer.stop()

    def _tick_orbits(self) -> None:
        if not self._orbit_specs or not self._items:
            return
        now = time.monotonic()
        dt = max(0.0, min(0.1, now - (self._last_orbit_t or now)))
        self._last_orbit_t = now

        # Update planets first
        parent_pos: dict[int | None, tuple[float, float]] = {None: (0.0, 0.0)}
        for spec in self._orbit_specs:
            if spec.get("parent") is None:
                spec["angle"] = (spec["angle"] + spec["speed"] * dt) % (2 * math.pi)
                a = spec["angle"]
                r = spec["radius_px"]
                x = r * math.cos(a)
                y = r * math.sin(a)
                ent_id = spec["id"]
                item = self._items.get(ent_id)
                if item is not None:
                    item.setPos(x, y)
                parent_pos[ent_id] = (x, y)

        # Then stations around their parent
        for spec in self._orbit_specs:
            if spec.get("parent") is not None:
                spec["angle"] = (spec["angle"] + spec["speed"] * dt) % (2 * math.pi)
                a = spec["angle"]
                r = spec["radius_px"]
                px, py = parent_pos.get(spec["parent"], (0.0, 0.0))
                x = px + r * math.cos(a)
                y = py + r * math.sin(a)
                ent_id = spec["id"]
                item = self._items.get(ent_id)
                if item is not None:
                    item.setPos(x, y)