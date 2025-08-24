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
from collections import deque
from typing import Deque

from PySide6.QtCore import QPoint, QPointF, Signal, QTimer, Qt
from PySide6.QtGui import QPen, QColor, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsPathItem

from data import db
from .background import BackgroundView
from .icons import make_map_symbol_item, list_gifs

ASSETS_ROOT  = Path(__file__).resolve().parents[2] / "assets"
SOL_BG_DIR   = ASSETS_ROOT / "solar_backgrounds"
STARS_DIR    = ASSETS_ROOT / "stars"
PLANETS_DIR  = ASSETS_ROOT / "planets"
STATIONS_DIR = ASSETS_ROOT / "stations"
WARP_GATE_DIR = ASSETS_ROOT / "warp_gate"
MOONS_DIR    = ASSETS_ROOT / "moons"   # <-- NEW


def _to_int(x) -> Optional[int]:
    try:
        return int(x)  # type: ignore[arg-type]
    except Exception:
        return None


class SolarMapWidget(BackgroundView):
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
        # Each spec: { id, parent, radius_px, theta0, omega, angle }
        self._orbit_specs: List[Dict[str, float | int | None]] = []
        self._orbit_t0 = 0.0
        self._last_orbit_t = 0.0
        self._orbit_timer: Optional[QTimer] = None

        self._star_item: Optional[QGraphicsItem] = None
        self._star_entity_id: Optional[int] = None          # synthetic id = -system_id
        self._star_radius_px: float = 20.0

        self._spread = 12.0          # AU visual multiplier (orbit radii are in AU * spread)
        self.set_unit_scale(8.0)     # 1 AU base ~ 12 px
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
        planets    = [l for l in self._locs_cache if l.get("kind") == "planet"]
        stations   = [l for l in self._locs_cache if l.get("kind") == "station"]
        warp_gates = [l for l in self._locs_cache if l.get("kind") == "warp_gate"]
        moons      = [l for l in self._locs_cache if l.get("kind") == "moon"]

        # Scene rect fits all rings comfortably around (0,0)
        n_rings = max(1, len(planets) + max(0, len(stations) // max(1, len(planets))) + len(warp_gates) + 2)
        ring_gap_au = 1.2
        base_au = 1.5
        max_r_au = base_au + (n_rings + 1) * ring_gap_au
        pad = 2.0
        R = (max_r_au + pad) * self._spread
        self._scene.setSceneRect(-R, -R, 2 * R, 2 * R)

        # ---- GIF catalogs & deterministic unique assignments ----
        star_gifs     = list_gifs(STARS_DIR)
        planet_gifs   = list_gifs(PLANETS_DIR)
        station_gifs  = list_gifs(STATIONS_DIR)
        warp_gate_gifs = list_gifs(WARP_GATE_DIR)
        moon_gifs     = list_gifs(MOONS_DIR)

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
        warp_gate_rows = sorted(warp_gates, key=lambda x: x["id"])
        moon_rows = sorted(moons, key=lambda x: x["id"])     # <-- NEW

        planet_assignments   = assign_unique(planet_gifs,  len(planet_rows),   1)
        station_assignments  = assign_unique(station_gifs, len(station_rows),  2)
        warp_gate_assignments = assign_unique(warp_gate_gifs, len(warp_gate_rows), 3)
        moon_assignments     = assign_unique(moon_gifs,     len(moon_rows),    4)

        # ---- Orbit rings (under everything) ----
        pen = QPen()
        pen.setWidthF(0.1)
        pen.setColor(QColor(200, 210, 230, 180))
        for i in range(len(planet_rows)):
            r = (base_au + i * ring_gap_au) * self._spread
            ring = self._scene.addEllipse(-r, -r, 2 * r, 2 * r, pen)
            ring.setZValue(-9)

        # ---- Central star (GIF-only) ----
        min_px_star = 180
        max_px_star = 300
        desired_px_star = rng.randint(min_px_star, max_px_star)
        star_gif = pick_star_gif()
        star_path = star_gif if star_gif is not None else Path("missing_star.gif")
        star_item = make_map_symbol_item(star_path, int(desired_px_star), self, salt=system_id)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)
        self._scene.addItem(star_item)
        self._star_item = star_item
        self._star_radius_px = desired_px_star / 2.0

        # ---- Planets (even angles, UNIQUE GIFs) ----
        min_px_planet = 45
        max_px_planet = 95
        n_planets = max(1, len(planet_rows))
        for i, l in enumerate(planet_rows):
            if n_planets == 1:
                desired_px_planet = (min_px_planet + max_px_planet) / 2
            else:
                desired_px_planet = min_px_planet + (max_px_planet - min_px_planet) * (i / (n_planets - 1))
            ring_r = (base_au + i * ring_gap_au) * self._spread
            angle_deg = ((l["id"] * 73.398) % 360.0)
            a0 = radians(angle_deg)
            x = ring_r * cos(a0)
            y = ring_r * sin(a0)
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
            self._assigned_icons[l["id"]] = pgif

            # absolute-time orbit spec
            base_speed = rng.uniform(0.05, 0.12)  # rad/sec
            omega = base_speed * (1.0 / (1.0 + i * 0.25))
            self._orbit_specs.append({"id": l["id"], "parent": None, "radius_px": ring_r, "theta0": a0, "omega": omega, "angle": a0})

        # ---- Stations (RESPECT DB PARENT if present) ----
        min_px_station = 15
        max_px_station = 18
        station_count = max(1, len(station_rows))
        planet_ids = [l["id"] for l in planet_rows]
        planets_with_station: set[int] = set()   # <-- track for moon radii spacing

        for j, l in enumerate(station_rows):
            # Choose parent:
            parent_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            chosen_parent: Optional[int] = None
            parent_source = "RR"
            if parent_from_db is not None and parent_from_db in planet_ids:
                chosen_parent = parent_from_db
                parent_source = "DB"
            elif planet_ids:
                # fallback: round-robin across planets to spread visuals
                ring_index = min(len(planet_ids) - 1, j % len(planet_ids))
                chosen_parent = planet_ids[ring_index]
                parent_source = "RR"

            if chosen_parent is not None:
                radius_px = 8.0
                parent_px, parent_py = self._drawpos.get(chosen_parent, (0.0, 0.0))
                planets_with_station.add(chosen_parent)
            else:
                # No planets; orbit the star
                radius_px = ((base_au + 0.5) * self._spread) * 0.5
                parent_px, parent_py = (0.0, 0.0)

            # Deterministic initial angle for the station (stable per system/id)
            a0 = radians(((l["id"] * 211.73) % 360.0))

            # Place station ON ITS ORBIT relative to parent immediately
            sx = parent_px + radius_px * math.cos(a0)
            sy = parent_py + radius_px * math.sin(a0)
            self._drawpos[l["id"]] = (sx, sy)

            sgif = station_assignments[j] if j < len(station_assignments) else None
            if sgif is None:
                self.logMessage.emit(f"WARNING: Not enough station GIFs for system {system_id}; station {l['id']} gets placeholder.")
                sgif = Path("missing_station.gif")

            if station_count == 1:
                desired_px_station = (min_px_station + max_px_station) / 2
            else:
                desired_px_station = min_px_station + (max_px_station - min_px_station) * (j / (station_count - 1))

            item = make_map_symbol_item(sgif, int(desired_px_station), self, salt=l.get("id"))
            item.setPos(sx, sy)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item
            self._assigned_icons[l["id"]] = sgif

            # Station angular speed
            omega = random.Random(10_000 + system_id * 97 + l["id"]).uniform(0.15, 0.30)  # rad/sec
            self._orbit_specs.append({
                "id": l["id"], "parent": chosen_parent,
                "radius_px": radius_px, "theta0": a0, "omega": omega, "angle": a0
            })

        # ---- Warp Gates ----
        n_warp_gates = max(1, len(warp_gate_rows))
        for k, l in enumerate(warp_gate_rows):
            outer_ring_index = len(planet_rows) + k
            ring_r = (base_au + outer_ring_index * ring_gap_au) * self._spread
            angle_deg = ((l["id"] * 73.398) % 360.0) + (180 if k % 2 == 0 else 0)
            a0 = radians(angle_deg)
            x = ring_r * cos(a0)
            y = ring_r * sin(a0)
            self._drawpos[l["id"]] = (x, y)

            wgif = warp_gate_assignments[k] if k < len(warp_gate_assignments) else None
            if wgif is None:
                self.logMessage.emit(f"WARNING: Not enough warp gate GIFs for system {system_id}; warp gate {l['id']} gets placeholder.")
                wgif = Path("missing_warp_gate.gif")

            item = make_map_symbol_item(wgif, int(20 + (10 * (k / max(1, n_warp_gates - 1)))), self, salt=l.get("id"))
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item
            self._assigned_icons[l["id"]] = wgif

            base_speed = random.Random(20_000 + system_id * 131 + l["id"]).uniform(0.08, 0.15)
            omega = base_speed * (1.0 / (1.0 + outer_ring_index * 0.25))
            self._orbit_specs.append({"id": l["id"], "parent": None, "radius_px": ring_r, "theta0": a0, "omega": omega, "angle": a0})

        # ---- Moons (RESPECT DB PARENT; avoid station radius) ----
        ring_gap_px = ring_gap_au * self._spread
        max_sat_radius = max(3.0, min(10.0, ring_gap_px * 0.6))
        base_sat_radii = [max_sat_radius * 0.35, max_sat_radius * 0.55, max_sat_radius * 0.75]
        sat_radii_template = sorted({max(3.0, min(float(r), max_sat_radius - 0.75)) for r in base_sat_radii})

        next_radius_index: Dict[int, int] = {pid: 0 for pid in [p["id"] for p in planet_rows]}

        moon_count = len(moon_rows)
        for m_idx, l in enumerate(moon_rows):
            if not planet_ids:
                continue

            pid_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            if pid_from_db in planet_ids:
                parent_id = pid_from_db
                parent_src = "DB"
            else:
                parent_id = planet_ids[m_idx % len(planet_ids)]
                parent_src = "RR"

            parent_key = int(parent_id) if parent_id is not None else 0
            parent_px, parent_py = self._drawpos.get(parent_key, (0.0, 0.0))

            has_station_here = parent_key in planets_with_station
            if has_station_here:
                candidates = [r for r in sat_radii_template if abs(r - 8.0) >= 1.0]
            else:
                candidates = sat_radii_template[:]

            ridx = next_radius_index.get(parent_key, 0)
            if ridx >= len(candidates):
                ridx = len(candidates) - 1 if candidates else 0
            radius_px = candidates[ridx] if candidates else 5.0
            next_radius_index[parent_key] = min(ridx + 1, max(0, len(candidates) - 1))

            a0 = radians(((l["id"] * 997.13) % 360.0))
            mx = parent_px + radius_px * math.cos(a0)
            my = parent_py + radius_px * math.sin(a0)
            self._drawpos[l["id"]] = (mx, my)

            mgif = moon_assignments[m_idx] if m_idx < len(moon_assignments) else None
            if mgif is None:
                self.logMessage.emit(f"WARNING: Not enough moon GIFs for system {system_id}; moon {l['id']} gets placeholder.")
                mgif = Path("missing_moon.gif")

            desired_px_moon = int(random.Random(30_000 + system_id * 29 + l["id"]).uniform(14, 18))
            item = make_map_symbol_item(mgif, desired_px_moon, self, salt=l.get("id"))
            item.setPos(mx, my)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(item)
            self._items[l["id"]] = item
            self._assigned_icons[l["id"]] = mgif

            omega = random.Random(40_000 + system_id * 171 + l["id"]).uniform(0.20, 0.35)  # rad/sec
            self._orbit_specs.append({
                "id": l["id"], "parent": parent_id,
                "radius_px": radius_px, "theta0": a0, "omega": omega, "angle": a0
            })

        # Start/stop orbits respecting global animation toggle
        try:
            self.set_animations_enabled(getattr(self, "_animations_enabled", True))
        except Exception:
            pass

        # Highlight player location if present
        player = db.get_player_full()
        if player and player.get("current_player_location_id"):
            self.refresh_highlight(player["current_player_location_id"])

        # Center the camera on the star
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
                self._orbit_timer.setTimerType(Qt.TimerType.PreciseTimer)
                self._orbit_timer.setInterval(16)                # ~60 FPS
                self._orbit_timer.timeout.connect(self._tick_orbits)
            self._orbit_t0 = time.monotonic()
            self._last_orbit_t = self._orbit_t0
            if not self._orbit_timer.isActive():
                self._orbit_timer.start()
        else:
            if self._orbit_timer is not None and self._orbit_timer.isActive():
                self._orbit_timer.stop()

    def _tick_orbits(self) -> None:
        if not self._orbit_specs or not self._items:
            return
        now = time.monotonic()
        # dt still tracked (can be useful for future easing), but angle is absolute-time based
        self._last_orbit_t = now

        # absolute-time angle helper
        def angle_for(spec: Dict[str, float | int | None], t0: float, now_t: float) -> float:
            theta0_v = spec.get("theta0", 0.0)
            theta0 = float(theta0_v) if theta0_v is not None else 0.0
            omega_v = spec.get("omega", 0.0)
            omega = float(omega_v) if omega_v is not None else 0.0
            return (theta0 + omega * (now_t - t0)) % (2.0 * math.pi)

        # Update parents (planets / gates around star)
        parent_pos: dict[int | None, tuple[float, float]] = {None: (0.0, 0.0)}
        for spec in self._orbit_specs:
            if spec.get("parent") is None:
                a = angle_for(spec, self._orbit_t0, now)
                spec["angle"] = a
                r_v = spec.get("radius_px", 0.0)
                r = float(r_v) if r_v is not None else 0.0
                x = r * math.cos(a)
                y = r * math.sin(a)
                id_v = spec.get("id")
                ent_id = int(id_v) if id_v is not None else 0
                item = self._items.get(ent_id)
                if item is not None:
                    item.setPos(x, y)
                parent_pos[ent_id] = (x, y)

        # Update children (stations & moons around their parent)
        for spec in self._orbit_specs:
            if spec.get("parent") is not None:
                a = angle_for(spec, self._orbit_t0, now)
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
                    item.setPos(x, y)
