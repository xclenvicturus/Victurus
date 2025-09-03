# /ui/maps/system.py

"""
System Map Display Widget

SystemMapWidget (display-only, GIF-first assets):
- central star at (0, 0) using a star GIF (or a visible placeholder if missing)
- planets on orbit rings (deterministic angles), with UNIQUE planet GIF per system when available
- stations use UNIQUE station GIFs per system; stations orbit their parent planet, else the star
- moons orbit their parent planet
- resource nodes on outer rings
- background drawn in scene/viewport space via BackgroundView
- animated starfield overlay
- get_entities() surfaces assigned icon_path so list thumbnails can match the map
- resolve_entity(): returns ('star', system_id) or ('loc', location_id)
- Travel visualization: displays travel paths and progress indicators
"""
from __future__ import annotations

import json
import math
import random
import time
from math import cos, radians, sin
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QTimer, Qt, Signal, QEvent
from PySide6.QtGui import QColor, QPen, QPainter, QAction, QCursor
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QApplication, QMenu
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from data import db
from game import player_status
from settings import system_config as cfg
from .background_view import BackgroundView
# uses list_images so static PNG/JPG/SVG are supported too (if present)
from .icons import AnimatedGifItem, list_gifs, list_images, make_map_symbol_item
from .travel_visualization import TravelVisualization, PathRenderer
from .simple_travel_vis import SimpleTravelStatus
from ..widgets.travel_status_overlay import TravelStatusOverlay
from game_controller.sim_loop import universe_sim
from save.icon_paths import persist_icon_paths_bulk, persist_system_icon
from data import db as data_db
import logging
from game_controller.log_config import get_ui_logger, get_travel_logger

logger = get_ui_logger('system_map')
travel_logger = get_travel_logger('system_map')

# --- Assets ---
ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
SYSTEM_BG_DIR = ASSETS_ROOT / "system_backgrounds"
STARS_DIR = ASSETS_ROOT / "stars"
PLANETS_DIR = ASSETS_ROOT / "planets"
STATIONS_DIR = ASSETS_ROOT / "stations"
WARP_GATES_DIR = ASSETS_ROOT / "warp_gates"  # corrected folder name
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


class SystemMapWidget(BackgroundView):
    logMessage = Signal(str)
    locationClicked = Signal(int)  # Single click on location
    locationDoubleClicked = Signal(int)  # Double click on location  
    locationRightClicked = Signal(int, QPoint)  # Right click on location with global position

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # GPU-accelerated path when available
        try:
            self.setViewport(QOpenGLWidget())
        except Exception:
            pass

        # Ensure we receive wheel events even when the viewport is an
        # OpenGL widget (it receives wheel events directly). Install an
        # event filter on the viewport so we can intercept and handle
        # QWheelEvent consistently.
        try:
            vp = self.viewport()
            if vp is not None:
                vp.installEventFilter(self)
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
        # When orbit updates are paused due to user interaction, record
        # the start time so we can advance the orbit clock by the paused
        # duration when resuming to avoid large time deltas causing jumps.
        self._orbit_paused_since: Optional[float] = None
        self._player_highlight: Optional[QGraphicsItem] = None
        self._system_id: Optional[int] = None
        self._locs_cache: List[Dict] = []

        # Transient user-interaction guard: when True, external centering
        # requests should be ignored. It's set on wheel/mouse events and
        # cleared automatically after a short timeout.
        self._user_interaction_active = False

        # Star & visual-parent state
        self._star_item = None
        self._star_radius_px = 20.0
        # Visual parent mapping (location_id -> parent_location_id) used to
        # reflect map-assigned parents in list views without mutating DB.
        self._visual_parent_map = {}
        # Temporary suppression window (monotonic time) to avoid external
        # center calls (e.g., from the location list) overriding the user's
        # wheel zoom/pan interaction. Wheel sets this to now+duration.
        self._suppress_auto_center_until = 0.0
        # Optional center lock: when set to a location_id, the view will
        # follow that entity (center will be updated every tick). Cleared
        # by centering on the system or by user interaction.
        self._center_lock_entity = None

        # Smooth centering state: targets and tuning. When set, the tick
        # loop will interpolate the view center toward `_center_target` to
        # avoid instantaneous jumps.
        self._center_target = None
        try:
            self._center_smooth_alpha = float(getattr(cfg, "VIEW_CENTER_SMOOTH_ALPHA", 0.25))
        except Exception:
            self._center_smooth_alpha = 0.25
        try:
            self._center_retry_delay_ms = int(getattr(cfg, "VIEW_CENTER_RETRY_MS", 50))
        except Exception:
            self._center_retry_delay_ms = 50
        try:
            self._center_retry_max = int(getattr(cfg, "VIEW_CENTER_RETRY_MAX", 8))
        except Exception:
            self._center_retry_max = 8
        try:
            # Pixel threshold (in device pixels) before we actually recenter.
            # Increasing this reduces visible micro-jitter when following.
            self._center_pixel_threshold = int(getattr(cfg, "VIEW_CENTER_PIXEL_THRESHOLD", 2))
        except Exception:
            self._center_pixel_threshold = 2

        # Center request token used to invalidate pending retries when the
        # user manually intervenes (pans). Incrementing this ID cancels
        # previous pending center attempts.
        self._center_request_id = 0
        # When True the user has manually cleared the center lock by panning
        # and auto-follow should not resume until the next explicit lock.
        self._user_cleared_center_lock = False

        # Track potential pan gestures: we only clear the center-lock when
        # the user actually begins a pan (drag). _press_pos stores the
        # initial press point in viewport coords; _is_panning becomes True
        # once movement exceeds the platform drag threshold while a button
        # is down.
        self._press_pos = None
        self._is_panning = False

        # Visual scale: we place items directly in pixels using a spread factor
        # Prefer values from the central config but fall back to local defaults
        self._spread = float(getattr(cfg, "SPREAD_PX_PER_AU", 8.0))
        # make ring spacing configurable (roomy defaults)
        self._ring_gap_au = float(getattr(cfg, "RING_GAP_AU", 20.0))
        self._base_orbit_au = float(getattr(cfg, "BASE_ORBIT_AU", 20.0))
        # Optional per-ring AU offsets. If provided, this list defines the gap
        # between consecutive rings starting at the gap after the base ring.
        # For example, [4.0, 6.0] means: ring0=base, ring1=base+4.0, ring2=base+4.0+6.0
        self._ring_offsets_au = None

        # If BackgroundView exposes unit scaling, keep it harmless
        try:
            self.set_unit_scale(1.0)  # use raw px in this widget
        except Exception:
            pass
            
        # Travel visualization components (lines disabled - using overlay instead)
        # self._travel_viz = TravelVisualization()
        # self._path_renderer = PathRenderer(self._travel_viz, coordinate_system="system")
        # self._path_renderer.set_scene(self._scene)
        
        # Travel status overlay
        self._travel_status = SimpleTravelStatus()
        self._travel_overlay = TravelStatusOverlay(self)
        self._travel_status.travel_status_changed.connect(self._travel_overlay.set_travel_info)
        
        # Connect hyperlink navigation signals
        self._travel_overlay.system_clicked.connect(self._navigate_to_system)
        self._travel_overlay.location_clicked.connect(self._navigate_to_location)

        # Starfield & background
        self.enable_starfield(True)
        self.set_background_mode("viewport")

    def _navigate_to_system(self, system_id: int) -> None:
        """Navigate to a system when hyperlink is clicked"""
        try:
            # Get the parent MapTabs widget to call navigation methods
            parent_widget = self.parent()
            while parent_widget is not None:
                if hasattr(parent_widget, 'center_system_on_system') and callable(getattr(parent_widget, 'center_system_on_system')):
                    getattr(parent_widget, 'center_system_on_system')(system_id)
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            from game_controller.log_config import get_ui_logger
            logger = get_ui_logger(__name__)
            logger.error(f"Failed to navigate to system {system_id}: {e}")

    def _navigate_to_location(self, location_id: int) -> None:
        """Navigate to a location when hyperlink is clicked"""
        try:
            # Get the location's system ID and ensure we're viewing the correct system
            from data import db
            location_data = db.get_location(location_id)
            if not location_data:
                from game_controller.log_config import get_ui_logger
                logger = get_ui_logger(__name__)
                logger.warning(f"Could not find location data for location_id {location_id}")
                return
            
            location_system_id = location_data.get('system_id')
            current_system_id = getattr(self, '_system_id', None)
            
            # If the location is in a different system, load that system first
            if location_system_id and location_system_id != current_system_id:
                try:
                    self.load(int(location_system_id))
                except Exception as e:
                    from game_controller.log_config import get_ui_logger
                    logger = get_ui_logger(__name__)
                    logger.warning(f"Failed to load system {location_system_id}: {e}")
            
            # Get the parent MapTabs widget to call navigation methods
            parent_widget = self.parent()
            while parent_widget is not None:
                if hasattr(parent_widget, 'center_system_on_location') and callable(getattr(parent_widget, 'center_system_on_location')):
                    getattr(parent_widget, 'center_system_on_location')(location_id)
                    
                    from game_controller.log_config import get_ui_logger
                    logger = get_ui_logger(__name__)
                    logger.debug(f"Successfully navigated to location {location_id} in system {location_system_id}")
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            from game_controller.log_config import get_ui_logger
            logger = get_ui_logger(__name__)
            logger.error(f"Failed to navigate to location {location_id}: {e}")

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

    def set_ring_offsets_au(self, offsets: Optional[List[float]], *, reload: bool = True) -> None:
        """Set explicit per-ring AU offsets (list of gaps between consecutive rings).

        If `offsets` is None, the widget falls back to the uniform `_ring_gap_au`.
        """
        try:
            if offsets is None:
                self._ring_offsets_au = None
            else:
                self._ring_offsets_au = [float(x) for x in offsets]
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

    # ---------- Orbit helpers ----------
    def _ring_au_for_index(self, index: int) -> float:
        """Return the AU distance for the ring at `index`.

        index=0 => base orbit; index=1 => next ring, etc. If per-ring offsets
        are provided via `_ring_offsets_au`, they are used; otherwise the
        uniform `_ring_gap_au` is applied.
        """
        try:
            base = float(self._base_orbit_au)
            if index <= 0:
                return base
            # If explicit offsets provided, consume them where available
            if self._ring_offsets_au:
                s = 0.0
                for i in range(index):
                    if i < len(self._ring_offsets_au):
                        try:
                            s += float(self._ring_offsets_au[i])
                        except Exception:
                            s += float(self._ring_gap_au)
                    else:
                        s += float(self._ring_gap_au)
                return base + s
            # Fallback: uniform spacing
            return base + float(index) * float(self._ring_gap_au)
        except Exception:
            return float(self._base_orbit_au)

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
            # If the map assigned a visual parent for this location, expose
            # it when the DB row lacks a parent or when the DB parent isn't
            # a planet (for example, points to a resource). This keeps the
            # list views consistent with the map while avoiding DB writes.
            try:
                if lid is not None and lid in getattr(self, "_visual_parent_map", {}):
                    vis_parent = self._visual_parent_map.get(lid)
                    if vis_parent is not None:
                        parent_kind = str(r.get("parent_kind") or r.get("parent_type") or "").lower()
                        if not (r.get("parent_location_id") or r.get("parent_id")) or not parent_kind.startswith("planet"):
                            r["parent_location_id"] = int(vis_parent)
                            r["parent_id"] = int(vis_parent)
            except Exception:
                pass

        sys_row = db.get_system(self._system_id)
        if sys_row:
            star_icon: Optional[str] = None
            db_only = _db_icons_only()
            db_path = sys_row.get("icon_path") or ""
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
        
    # ---------- Travel Visualization ----------
    def show_travel_path(self, dest_type: str, dest_id: int) -> bool:
        """
        Display travel path to destination and return True if path was calculated.
        NOTE: Line-based travel visualization disabled - using overlay system instead.
        """
        # Travel path visualization is now handled by overlay system
        return True
        try:
            # Get current player location
            from data import db
            player_loc = db.get_player_location()
            if not player_loc:
                return False
                
            current_location_id = player_loc.get('location_id')
            
            travel_logger.info(f"Current player location_id = {current_location_id}")
            travel_logger.info(f"Destination type = {dest_type}, id = {dest_id}")
            
            # Get positions using actual map coordinates
            if current_location_id:
                current_pos_tuple = self._drawpos.get(current_location_id)
                logger.info(f"Travel debug: Looking for current location {current_location_id} in _drawpos")
                logger.info(f"Travel debug: Found current position: {current_pos_tuple}")
                from_pos = QPointF(*current_pos_tuple) if current_pos_tuple else QPointF(0, 0)
            else:
                from_pos = QPointF(0, 0)  # Star position
                logger.info(f"Travel debug: Using star position for current location")
                
            if dest_type == "star":
                to_pos = QPointF(0, 0)  # Star is always at center
                logger.info(f"Travel debug: Destination is star at (0, 0)")
            elif dest_type == "loc":
                dest_pos_tuple = self._drawpos.get(dest_id)
                logger.info(f"Travel debug: Looking for destination location {dest_id} in _drawpos")
                logger.info(f"Travel debug: Found destination position: {dest_pos_tuple}")
                to_pos = QPointF(*dest_pos_tuple) if dest_pos_tuple else QPointF(0, 0)
            else:
                return False
                
            travel_logger.info(f"Travel path: from {from_pos.x():.1f}, {from_pos.y():.1f} to {to_pos.x():.1f}, {to_pos.y():.1f}")
            travel_logger.debug(f"Available positions in _drawpos: {list(self._drawpos.keys())}")
            
            # Use the travel visualization's calculate_path method for intelligent routing
            travel_logger.info(f"Calling travel visualization calculate_path({dest_type}, {dest_id})")
            path = self._travel_viz.calculate_path(dest_type, dest_id)
            
            if path:
                travel_logger.info(f"Travel visualization returned path with {len(path.segments)} segments")
                travel_logger.debug(f"About to call set_travel_path with {len(path.segments)} segments")
                self._travel_viz.set_travel_path(path)
                travel_logger.debug(f"Completed set_travel_path call")
                return True
            else:
                travel_logger.warning("Travel visualization returned None, using fallback simple path")
                # Fallback to simple path if calculation fails
                from ui.maps.travel_visualization import PathSegment, TravelPath
                segment = PathSegment(
                    from_pos=from_pos,
                    to_pos=to_pos,
                    segment_type="cruise",
                    distance=((to_pos.x() - from_pos.x())**2 + (to_pos.y() - from_pos.y())**2)**0.5 / 100.0,
                    fuel_cost=10.0,  # Placeholder
                    time_estimate=5000.0  # Placeholder
                )
                
                path = TravelPath(
                    segments=[segment], 
                    total_distance=segment.distance, 
                    total_fuel=segment.fuel_cost, 
                    total_time=segment.time_estimate,
                    destination_type=dest_type,
                    destination_id=dest_id
                )
                
                self._travel_viz.set_travel_path(path)
                return True
            
        except Exception as e:
            logger.warning(f"Error showing travel path: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
            return False
            
    def hide_travel_path(self) -> None:
        """Clear/hide the current travel path visualization"""
        # Travel path visualization disabled - using overlay system instead
        pass
        
    def update_travel_progress(self, progress: float) -> None:
        """
        Update travel progress along the current path.
        NOTE: Progress is now handled automatically by SimpleTravelStatus
        """
        # Travel progress is handled by overlay system
        pass
        
    def get_travel_visualization(self):
        """Get the travel visualization instance for external updates"""
        # Travel visualization disabled - using overlay system instead
        return None
    
    def get_travel_status(self) -> SimpleTravelStatus:
        """Get the travel status instance for external connections"""
        return self._travel_status

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
        self._visual_parent_map.clear()
        self._player_highlight = None
        self._star_item = None

        # Cache rows
        try:
            self._locs_cache = [dict(r) for r in (db.get_locations(system_id) or [])]
        except Exception:
            self._locs_cache = []

        # Background selection
        candidates = [
            SYSTEM_BG_DIR / f"system_bg_{system_id}.png",
            SYSTEM_BG_DIR / "system_bg_01.png",
            SYSTEM_BG_DIR / "default.png",
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
        star_icon_val = sys_row.get("icon_path") or ""
        star_path: Optional[str] = None
        if star_icon_val:
            star_path = str(star_icon_val)
        min_px_star, max_px_star = 180, 300
        desired_px_star = rng.randint(min_px_star, max_px_star)
        star_item = make_map_symbol_item(star_path or "", int(desired_px_star), self, salt=system_id)
        star_item.setPos(0.0, 0.0)
        star_item.setZValue(-8)
        # Store star entity ID (negative system_id) for context menu
        star_item.setData(0, -system_id)  # Star uses negative system ID
        self._scene.addItem(star_item)
        try:
            star_item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception:
            pass
        self._star_item = star_item
        self._star_radius_px = desired_px_star / 2.0
        # Add star to _drawpos for travel visualization
        star_id = -system_id  # Star has negative system_id as location_id
        self._drawpos[star_id] = (0.0, 0.0)

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
                mapping[rid] = None
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
                mapping[rid] = None
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
            r_au = self._ring_au_for_index(i)
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
            ring_r = (self._ring_au_for_index(i)) * self._spread
            angle_deg = (((_row_id(l) or 0) * 73.398) % 360.0)
            a0 = radians(angle_deg)
            x = ring_r * cos(a0)
            y = ring_r * sin(a0)
            lid = _row_id(l) or 0
            icon = planet_map.get(lid)
            item = make_map_symbol_item(icon or "", int(desired_px), self, salt=lid)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            # Store location ID for context menu
            item.setData(0, lid)  # Store location ID as data key 0
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

        # track per-parent offsets so multiple child orbiters (stations + moons)
        # around the same planet don't collide. We use a single shared index
        # allocator so stations and moons consume distinct orbital slots.
        child_next_index: Dict[Optional[int], int] = {}

        # Precompute visual parent and base angle for each station so we can
        # group children by parent and evenly spread their angles.
        station_parent_map: Dict[int, Tuple[Optional[int], float]] = {}
        parent_groups: Dict[Optional[int], list] = {}
        for l in station_rows:
            lid = _row_id(l) or 0
            parent_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            base_a0 = radians(((lid * 211.73) % 360.0))
            if parent_from_db in planet_ids:
                p_id = parent_from_db
            elif planet_ids:
                best_pid = None
                best_diff = None
                for pid in planet_ids:
                    ppos = self._drawpos.get(pid)
                    if not ppos:
                        continue
                    pxp, pyp = ppos
                    p_ang = math.atan2(pyp, pxp)
                    diff = abs((p_ang - base_a0 + math.pi) % (2.0 * math.pi) - math.pi)
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_pid = pid
                p_id = best_pid
            else:
                p_id = None
            station_parent_map[lid] = (p_id, base_a0)
            parent_groups.setdefault(p_id, []).append(lid)

        for j, l in enumerate(station_rows):
            lid = _row_id(l) or 0
            parent_id, a0 = station_parent_map.get(lid, (None, radians(((lid * 211.73) % 360.0))))
            siblings = parent_groups.get(parent_id, [])
            try:
                idx_in_parent = siblings.index(lid)
            except Exception:
                idx_in_parent = 0
            sibling_count = max(1, len(siblings))

            # If we chose a fallback visual parent, remember it for lists
            try:
                parent_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
                if parent_from_db not in planet_ids and parent_id is not None:
                    self._visual_parent_map[lid] = parent_id
            except Exception:
                pass

            parent_key = parent_id if parent_id is not None else None
            if parent_id is not None:
                parent_item = self._items.get(parent_id)
                if parent_item is not None:
                    try:
                        pr = parent_item.mapToScene(parent_item.boundingRect()).boundingRect()
                        parent_radius = max(pr.width(), pr.height()) * 0.5
                    except Exception:
                        parent_radius = 0.0
                else:
                    parent_radius = 0.0

                # radial offset to avoid overlapping the planet graphic
                base_margin_px = float(getattr(cfg, "STATION_BASE_MARGIN_PX", 12.0))
                per_item_delta_px = float(getattr(cfg, "STATION_PER_ITEM_DELTA_PX", 6.0))
                idx = child_next_index.get(parent_key, 0)
                reserve_idx = max(idx, idx_in_parent)
                child_next_index[parent_key] = reserve_idx + 1
                cfg_gap = float(getattr(cfg, "CHILD_MIN_GAP_PX", 8.0))
                step = max(per_item_delta_px, cfg_gap)
                radius_px = max(10.0, parent_radius + base_margin_px + reserve_idx * step)
                px, py = self._drawpos.get(parent_id, (0.0, 0.0))
            else:
                radius_px = ((self._ring_au_for_index(0) + 0.5) * self._spread) * 0.5
                px, py = (0.0, 0.0)

            # Evenly space children around the parent by index/total
            angle_offset = (2.0 * math.pi * idx_in_parent) / float(sibling_count)
            child_angle = a0 + angle_offset
            sx = px + radius_px * math.cos(child_angle)
            sy = py + radius_px * math.sin(child_angle)
            icon = station_map.get(lid)
            desired_px = int(min_px_station + (max_px_station - min_px_station) * (j / max(1, len(station_rows) - 1)))
            item = make_map_symbol_item(icon or "", desired_px, self, salt=lid)
            item.setPos(sx, sy)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            # Store location ID for context menu
            item.setData(0, lid)  # Store location ID as data key 0
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._drawpos[lid] = (sx, sy)  # FIX: Add station position to _drawpos
            self._assigned_icons[lid] = icon
            self._assigned_icons[lid] = icon
            # children inherit the parent's angular velocity when possible
            if parent_id is not None:
                parent_spec = next((s for s in self._orbit_specs if s.get("id") == parent_id and s.get("parent") is None), None)
                if parent_spec is not None:
                    p_omega = parent_spec.get("omega")
                    if p_omega is not None:
                        omega = float(p_omega)
                    else:
                        omega = random.Random(17_000 + system_id * 97 + lid).uniform(0.15, 0.30)
                else:
                    omega = random.Random(17_000 + system_id * 97 + lid).uniform(0.15, 0.30)
            else:
                omega = random.Random(17_000 + system_id * 97 + lid).uniform(0.15, 0.30)
            # Use child_angle as theta0 so orbit animation matches placement
            self._orbit_specs.append({
                "id": lid, "parent": parent_id, "radius_px": radius_px, "theta0": child_angle, "omega": omega, "angle": child_angle
            })

        # -------- Warp Gates --------
        gate_rows = sorted(warp_gates, key=lambda r: _row_id(r) or 0)
        for k, l in enumerate(gate_rows):
            lid = _row_id(l) or 0
            outer_index = len(planets) + k
            ring_r = (self._ring_au_for_index(outer_index)) * self._spread

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
            # Store location ID for context menu
            item.setData(0, lid)  # Store location ID as data key 0
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

        # reuse child_next_index declared earlier so moons and stations share slots
        for m_idx, l in enumerate(moon_rows):
            lid = _row_id(l) or 0
            pid_from_db = _to_int(l.get("parent_location_id") or l.get("parent_id"))
            # Only respect an explicit DB parent. Avoid assigning a fallback
            # parent so the UI list and the map remain consistent.
            parent_id = pid_from_db if pid_from_db in planet_ids else None
            parent_key = parent_id if parent_id is not None else None
            # dicts are keyed by int ids; avoid passing None as a key to get()
            if parent_key is None:
                px, py = (0.0, 0.0)
            else:
                px, py = self._drawpos.get(parent_key, (0.0, 0.0))

            idx = child_next_index.get(parent_key, 0)
            idx = min(idx, max(0, len(sat_radii) - 1))
            # Prefer an orbit radius that places the moon outside the parent's
            # visual radius so it's always visible; fall back to sat_radii.
            parent_item = self._items.get(parent_key) if parent_key is not None else None
            if parent_item is not None:
                try:
                    pr = parent_item.mapToScene(parent_item.boundingRect()).boundingRect()
                    parent_radius = max(pr.width(), pr.height()) * 0.5
                except Exception:
                    parent_radius = 0.0
            else:
                parent_radius = 0.0
            base_margin_px = float(getattr(cfg, "MOON_BASE_MARGIN_PX", 10.0))
            per_item_delta_px = float(getattr(cfg, "MOON_PER_ITEM_DELTA_PX", 6.0))
            cfg_gap = float(getattr(cfg, "CHILD_MIN_GAP_PX", 8.0))
            step = max(per_item_delta_px, cfg_gap)
            fallback_radius = sat_radii[idx] if sat_radii else 5.0
            # Consider a fraction of the parent's visual radius as a minimum
            # additional margin so moons don't end up too close on large
            # planets.
            parent_scale = float(getattr(cfg, "MOON_PARENT_RADIUS_SCALE", 0.35))
            min_margin = max(base_margin_px, parent_radius * parent_scale)
            radius_px = max(fallback_radius, parent_radius + min_margin + idx * step)
            child_next_index[parent_key] = min(idx + 1, max(0, len(sat_radii) - 1))

            a0 = radians((((lid * 997.13) % 360.0)))
            mx = px + radius_px * math.cos(a0)
            my = py + math.sin(a0) * radius_px
            icon = moon_map.get(lid)
            desired_px = int(random.Random(21_000 + system_id * 29 + lid).uniform(14, 18))
            item = make_map_symbol_item(icon or "", desired_px, self, salt=lid)
            item.setPos(mx, my)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            # Store location ID for context menu
            item.setData(0, lid)  # Store location ID as data key 0
            self._scene.addItem(item)
            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass
            self._items[lid] = item
            self._drawpos[lid] = (mx, my)  # FIX: Add moon position to _drawpos
            self._assigned_icons[lid] = icon
            # Children inherit the parent's angular velocity so moons orbit
            # in step with their parent planet (option A). Fall back to a
            # seeded random omega if parent's spec isn't available.
            if parent_id is not None:
                parent_spec = next((s for s in self._orbit_specs if s.get("id") == parent_id and s.get("parent") is None), None)
                if parent_spec is not None:
                    p_omega = parent_spec.get("omega")
                    if p_omega is not None:
                        omega = float(p_omega)
                    else:
                        omega = random.Random(23_000 + system_id * 171 + lid).uniform(0.20, 0.35)
                else:
                    omega = random.Random(23_000 + system_id * 171 + lid).uniform(0.20, 0.35)
            else:
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
                ring_r = (self._ring_au_for_index(outer_index)) * self._spread

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
                # Store location ID for context menu
                item.setData(0, rid)  # Store location ID as data key 0
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

        # Persist any assigned icons into the active save DB so they are
        # available on subsequent loads. We only write values for rows that
        # did not already have an `icon_path` stored by the seed or previous
        # user action, to avoid overwriting deliberate choices.
        try:
            # Persist system/star icon if we selected one and DB lacks it
            try:
                db_sys_icon = sys_row.get("icon_path") if sys_row else None
            except Exception:
                db_sys_icon = None
            if sys_row and not (db_sys_icon or "") and star_path:
                try:
                    persist_system_icon(system_id, star_path)
                except Exception:
                    logger.exception("Failed to persist system icon for %s", system_id)

            # Persist per-location assigned icons when the location had no stored icon
            pairs = []
            rn_pairs: list[tuple[int, Optional[str]]] = []
            for r in self._locs_cache:
                rid = _row_id(r)
                if rid is None:
                    continue
                existing = r.get("icon_path") or ""
                assigned = self._assigned_icons.get(rid)
                if assigned and not existing:
                    pairs.append((rid, assigned))
            # Resource nodes are represented as locations with resource_type set;
            # fetch them and persist any assigned icons that weren't already present.
            try:
                res_nodes = data_db.get_resource_nodes(system_id) or []
                for rn in res_nodes:
                    lid = rn.get("location_id") or rn.get("location")
                    if lid is None:
                        continue
                    existing_rn = rn.get("icon_path") or ""
                    assigned_rn = self._assigned_icons.get(int(lid))
                    if assigned_rn and not existing_rn:
                        rn_pairs.append((int(lid), assigned_rn))
            except Exception:
                logger.exception("Failed reading resource_nodes for persistence for system %s", system_id)
            if pairs:
                try:
                    persist_icon_paths_bulk(pairs)
                except Exception:
                    logger.exception("Failed to persist location icons; pairs=%s", pairs[:10])
            if rn_pairs:
                try:
                    # prefer data.db bulk API if available
                    try:
                        data_db.set_resource_node_icons_bulk(rn_pairs)
                    except Exception:
                        # fallback: update locations.icon_path directly
                        conn = data_db.get_connection()
                        cur = conn.cursor()
                        cur.executemany("UPDATE locations SET icon_path=? WHERE location_id=?", [(p, lid) for (lid, p) in rn_pairs])
                        conn.commit()
                except Exception:
                    logger.exception("Failed to persist resource node icons; pairs=%s", rn_pairs[:10])
        except Exception:
            # Never bubble UI errors from persistence
            logger.exception("Error while persisting assigned icons for system %s", system_id)

    # ---------- Highlight / Center ----------
    def refresh_highlight(self, location_id: Optional[int]) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None
        if location_id is None:
            return
        item = self._items.get(location_id)
        # Debug: surface items keys to help diagnose missing-lookups
        try:
            keys = list(self._items.keys())
        except Exception:
            keys = None
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

    def center_on_system(self, system_id: int | None, force: bool = False) -> None:
        try:
            # Respect temporary suppression so user interactions aren't
            # immediately overridden by external center calls.
            caller = None
            try:
                import inspect

                stack = inspect.stack()
                # pick the immediate caller function name if available
                caller = stack[1].function if len(stack) > 1 else None
            except Exception:
                caller = None
            now = time.monotonic()
            sup = float(getattr(self, "_suppress_auto_center_until", 0.0))
            # If not forced, respect temporary suppression so user
            # interactions aren't immediately overridden by external calls.
            if not force:
                if getattr(self, "_user_interaction_active", False):
                    return
                if now < sup:
                    return
            sid = system_id if system_id is not None else getattr(self, "_system_id", None)
            if sid is not None:
                universe_sim.set_visible_system(int(sid))
        except Exception:
            pass
        # Clear any active location lock when centering on the system
        # Must do this BEFORE centerOn to prevent tick loop race condition
        try:
            self._center_lock_entity = None
            self._center_target = None
        except Exception:
            pass
        self.centerOn(0.0, 0.0)

    def center_on_location(self, location_id: int, force: bool = False, _attempt: int = 0) -> None:
        try:
            # Respect temporary suppression so user interactions aren't
            # immediately overridden by external center calls.
            caller = None
            try:
                import inspect

                stack = inspect.stack()
                caller = stack[1].function if len(stack) > 1 else None
            except Exception:
                caller = None
            now = time.monotonic()
            sup = float(getattr(self, "_suppress_auto_center_until", 0.0))
            # If not forced, respect temporary suppression so user
            # interactions aren't immediately overridden by external calls.
            if not force:
                if getattr(self, "_user_interaction_active", False):
                    return
                if now < sup:
                    return
            sid = getattr(self, "_system_id", None)
            if sid is not None:
                universe_sim.set_visible_system(int(sid))
        except Exception:
            pass
        # An explicit center request means the user (or UI) intends to
        # focus this location — clear the manual-clear flag so auto-follow
        # may resume for this new lock.
        try:
            self._user_cleared_center_lock = False
        except Exception:
            pass

        item = self._items.get(location_id)
        if not item:
            # Item not present yet (race). Retry a few times before giving up.
            try:
                if _attempt < int(getattr(self, "_center_retry_max", 8)):
                    QTimer.singleShot(int(getattr(self, "_center_retry_delay_ms", 50)), lambda: self.center_on_location(location_id, force=True, _attempt=_attempt + 1))
            except Exception:
                pass
            return

        # Compute target center in scene coords and set as the smooth target.
        try:
            rect = item.mapToScene(item.boundingRect()).boundingRect()
            center_pt = rect.center()
        except Exception:
            center_pt = None

        if center_pt is not None:
            try:
                # Set smooth target; tick loop will interpolate toward it.
                self._center_target = center_pt
            except Exception:
                try:
                    self._center_target = None
                except Exception:
                    pass

        # Lock to this entity so subsequent ticks keep the target updated
        try:
            self._center_lock_entity = int(location_id)
        except Exception:
            try:
                self._center_lock_entity = None
            except Exception:
                pass

    def lock_center_to_location(self, location_id: int) -> None:
        """Public helper to lock the center to a location and center now."""
        try:
            # Clear any manual-clear state since this is an explicit lock
            try:
                self._user_cleared_center_lock = False
            except Exception:
                pass
            self.center_on_location(location_id, force=True)
            self._center_lock_entity = int(location_id)
        except Exception:
            pass

    def center_on_location_no_lock(self, location_id: int, force: bool = False) -> None:
        """Center on a location without locking the camera to follow it."""
        try:
            # Respect temporary suppression unless forced
            if not force:
                if getattr(self, "_user_interaction_active", False):
                    return
                now = time.monotonic()
                sup = float(getattr(self, "_suppress_auto_center_until", 0.0))
                if now < sup:
                    return

            # Clear any existing lock first so we don't jump back to the old location
            self._center_lock_entity = None
            self._center_target = None

            # Find the item and center on it
            item = self._items.get(location_id)
            if not item:
                return

            # Center on the item without setting up a lock
            rect = item.mapToScene(item.boundingRect()).boundingRect()
            center_pt = rect.center()
            self.centerOn(center_pt)
            
        except Exception:
            pass

    def unlock_center(self) -> None:
        """Clear any active center lock so the view no longer follows an entity."""
        try:
            self._center_lock_entity = None
        except Exception:
            pass

    def is_suppressing_auto_center(self) -> bool:
        """Return True when temporary suppression window is active.

        Public helper so external callers (presenters/tabs) can avoid forcing
        a center while the user is interacting with the map.
        """
        try:
            if getattr(self, "_user_interaction_active", False):
                return True
            return time.monotonic() < float(getattr(self, "_suppress_auto_center_until", 0.0))
        except Exception:
            return False

    # ---------- Zoom / Wheel ----------
    def _apply_view_unit_scale(self, new_scale: float, *, preserve_center: bool = True) -> None:
        """Safely apply a new unit scale (logical -> pixel multiplier).

        This wraps BackgroundView.set_unit_scale to keep the transform
        stable while preserving scene centering.
        """
        try:
            # clamp
            min_s = float(getattr(cfg, "VIEW_MIN_UNIT_SCALE", 0.25))
            max_s = float(getattr(cfg, "VIEW_MAX_UNIT_SCALE", 6.0))
            s = max(min_s, min(max_s, float(new_scale)))
            # Optionally preserve current viewport center in scene coords.
            center_scene = None
            if preserve_center:
                try:
                    center_scene = self.mapToScene(self.viewport().rect().center())
                except Exception:
                    center_scene = None

            self.set_unit_scale(s)
            # BackgroundView._apply_unit_scale performs the actual QTransform
            # reset + scale. Call it to make the change visible immediately.
            try:
                self._apply_unit_scale()
            except Exception:
                pass

            if preserve_center and center_scene is not None:
                try:
                    self.centerOn(center_scene)
                except Exception:
                    pass
        except Exception:
            pass

    def drawForeground(self, painter: QPainter, rect) -> None:
        """HUD disabled: zoom HUD removed since zooming is turned off.

        The function intentionally returns immediately to avoid drawing a
        redundant zoom indicator now that wheel zooming is disabled.
        """
        return

    def _suppress_auto_center_for_interaction(self, duration: Optional[float] = None) -> None:
        """Set the temporary suppression window so external centering is ignored.

        Duration falls back to `VIEW_USER_INTERACTION_SUPPRESS_SEC` in config or 1.25s.
        """
        try:
            if duration is None:
                duration = float(getattr(cfg, "VIEW_USER_INTERACTION_SUPPRESS_SEC", 1.25))
            self._suppress_auto_center_until = time.monotonic() + float(duration)
        except Exception:
            try:
                self._suppress_auto_center_until = time.monotonic() + 1.25
            except Exception:
                self._suppress_auto_center_until = 0.0

    def _begin_user_interaction(self, duration: Optional[float] = None) -> None:
        """Mark the widget as under user interaction for `duration` seconds.

        This provides an immediate guard that prevents external centering
        for the duration even if suppression timestamp hasn't been set yet.
        """
        try:
            if duration is None:
                duration = float(getattr(cfg, "VIEW_USER_INTERACTION_SUPPRESS_SEC", 1.25))
            self._user_interaction_active = True
            # Clear after `duration` ms. When clearing, also adjust the
            # orbit clock to account for the paused interval so orbits don't
            # jump when updates resume.
            try:
                def _clear_user_interaction():
                    try:
                        # compute paused duration and advance orbit base time
                        now = time.monotonic()
                        paused = getattr(self, "_orbit_paused_since", None)
                        if paused is not None:
                            try:
                                self._orbit_t0 += (now - float(paused))
                            except Exception:
                                pass
                        try:
                            self._user_interaction_active = False
                        except Exception:
                            pass
                    finally:
                        try:
                            self._orbit_paused_since = None
                        except Exception:
                            pass

                QTimer.singleShot(int(float(duration) * 1000.0), _clear_user_interaction)
            except Exception:
                # fallback: clear via time-based check if timers aren't available
                def _clear():
                    try:
                        now = time.monotonic()
                        paused = getattr(self, "_orbit_paused_since", None)
                        if paused is not None:
                            try:
                                self._orbit_t0 += (now - float(paused))
                            except Exception:
                                pass
                        self._user_interaction_active = False
                    except Exception:
                        pass
                    try:
                        self._orbit_paused_since = None
                    except Exception:
                        pass
                try:
                    QTimer.singleShot(1250, _clear)
                except Exception:
                    self._user_interaction_active = False
        except Exception:
            try:
                self._user_interaction_active = False
            except Exception:
                pass

    def wheelEvent(self, ev) -> None:
        # Zooming via mouse wheel is disabled for this widget; ignore wheel
        # events to prevent accidental zooming. Mark the user interaction
    # events to prevent accidental zooming. Do not mark user interaction
    # so a harmless wheel won't temporarily pause or clear follow locks.
        try:
            ev.ignore()
        except Exception:
            pass

    def eventFilter(self, obj, ev) -> bool:
        """Forward wheel events from the viewport to this widget's wheelEvent
        so we handle wheel consistently and only clear the center-lock when
        the user actually begins a pan (drag) gesture.
        """
        # Handle wheel immediately
        try:
            if ev.type() == QEvent.Type.Wheel:
                self.wheelEvent(ev)
                return True
        except Exception:
            pass

        # Short-circuit: only care about mouse press/move/release here
        try:
            if ev.type() == QEvent.Type.MouseButtonPress:
                try:
                    self._press_pos = ev.pos()
                except Exception:
                    self._press_pos = None
                self._is_panning = False
                return super().eventFilter(obj, ev)

            if ev.type() == QEvent.Type.MouseMove:
                try:
                    buttons = getattr(ev, "buttons", lambda: 0)()
                    if buttons and self._press_pos is not None and not self._is_panning:
                        try:
                            drag_thr = QApplication.startDragDistance()
                        except Exception:
                            drag_thr = 6
                        try:
                            dx = int(ev.pos().x() - self._press_pos.x())
                            dy = int(ev.pos().y() - self._press_pos.y())
                        except Exception:
                            dx = dy = 0
                        if (dx * dx + dy * dy) >= (drag_thr * drag_thr):
                            # user started a drag/pan — mark and clear lock
                            self._is_panning = True
                            try:
                                self._begin_user_interaction()
                                self._suppress_auto_center_for_interaction()
                            except Exception:
                                pass
                            try:
                                # User pan clears any active center lock and
                                # prevents auto-follow from resuming until the
                                # next explicit center request.
                                self._center_lock_entity = None
                                self._user_cleared_center_lock = True
                                try:
                                    self._center_request_id += 1
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            # Ensure the closed-hand cursor is shown while panning.
                            try:
                                closed_cur = getattr(Qt, "ClosedHandCursor", None)
                                if closed_cur is not None:
                                    try:
                                        self.setCursor(closed_cur)
                                    except Exception:
                                        pass
                                    try:
                                        vp = self.viewport()
                                        if vp is not None:
                                            vp.setCursor(closed_cur)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass
                return super().eventFilter(obj, ev)

            if ev.type() == QEvent.Type.MouseButtonRelease:
                try:
                    self._press_pos = None
                    self._is_panning = False
                    self._begin_user_interaction()
                    self._suppress_auto_center_for_interaction()
                except Exception:
                    pass
                # Restore default cursor when the user finishes a pan
                try:
                    try:
                        self.unsetCursor()
                    except Exception:
                        pass
                    try:
                        vp = self.viewport()
                        if vp is not None:
                            try:
                                vp.unsetCursor()
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
                return super().eventFilter(obj, ev)
        except Exception:
            pass

        return super().eventFilter(obj, ev)

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
            # Always update the item's position so off-screen objects remain
            # in the correct orbit state; otherwise they visibly 'freeze' and
            # then snap when they re-enter the viewport. GIF playback is
            # still gated by visibility above for performance.
            try:
                cur = item.pos()
                # Avoid tiny moves that cause sub-pixel jitter. If movement is
                # below the micro threshold, skip. When applying a new position,
                # snap to 0.5px increments to keep alignment stable on screen.
                if (abs(cur.x() - x) < 0.25) and (abs(cur.y() - y) < 0.25):
                    return
                def _snap_half(v: float) -> float:
                    return float(round(v * 2.0) / 2.0)
                sx = _snap_half(x)
                sy = _snap_half(y)
                item.setPos(sx, sy)
            except Exception:
                try:
                    item.setPos(x, y)
                except Exception:
                    pass

        # Parents (around star)
        parent_pos: Dict[int | None, Tuple[float, float]] = {None: (0.0, 0.0)}
        # Update star position in _drawpos for travel visualization
        if hasattr(self, '_system_id') and self._system_id is not None:
            star_id = -self._system_id
            self._drawpos[star_id] = (0.0, 0.0)
            
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
                    # keep parent angle in the spec for completeness
                    # (children will compute their own angle independently)
                    try:
                        spec["angle"] = a
                    except Exception:
                        pass
                # Update _drawpos with current orbital position for travel visualization
                self._drawpos[ent_id] = (x, y)
                parent_pos[ent_id] = (x, y)

        # Children (around parent) — compute their own theta so they orbit
        # slowly and remain separated; do not rigidly copy the parent's theta.
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
                # Update _drawpos with current orbital position for travel visualization
                self._drawpos[ent_id] = (x, y)

        # If the user is actively interacting (panning/dragging or in a
        # brief interaction window), do not force the view back to the
        # locked entity — allow the user's pan to take effect.
        try:
            # If the user has manually cleared the center lock via panning,
            # do not resume auto-follow. Also avoid forcing while interaction
            # is active or a pan is in progress.
            if getattr(self, "_user_cleared_center_lock", False):
                return
            if getattr(self, "_user_interaction_active", False) or getattr(self, "_is_panning", False):
                # Do not update _center_target or perform interpolation while
                # the user is interacting. Keep existing target until interaction ends.
                return
        except Exception:
            pass

        # If a center lock is active, follow that entity's current position
        try:
            lock_id = getattr(self, "_center_lock_entity", None)
            if lock_id is not None:
                locked_item = self._items.get(int(lock_id))
                if locked_item is not None:
                    try:
                        crect = locked_item.mapToScene(locked_item.boundingRect()).boundingRect()
                        # Update the target center each tick so the view will
                        # smoothly interpolate toward it below.
                        try:
                            self._center_target = crect.center()
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pass

        # Smoothly interpolate current view center toward _center_target
        try:
            tgt = getattr(self, "_center_target", None)
            if tgt is not None:
                try:
                    # current center in scene coords
                    cur_scene = self.mapToScene(self.viewport().rect().center())
                    alpha = float(getattr(self, "_center_smooth_alpha", 0.25))
                    nx = cur_scene.x() + (tgt.x() - cur_scene.x()) * alpha
                    ny = cur_scene.y() + (tgt.y() - cur_scene.y()) * alpha

                    # Map the interpolated scene point to viewport integer pixels
                    vp_target = None
                    try:
                        vp_center = self.viewport().rect().center()
                        vp_target = self.mapFromScene(QPointF(nx, ny))
                        dx = int(vp_target.x() - vp_center.x())
                        dy = int(vp_target.y() - vp_center.y())
                    except Exception:
                        dx = dy = 0

                    # Only re-center when movement is at least one device pixel
                    if abs(dx) >= 1 or abs(dy) >= 1:
                        try:
                            # Use the integer-aligned viewport point to compute
                            # the exact scene coordinate that maps to that
                            # pixel. This avoids sub-pixel center jitter.
                            if vp_target is not None:
                                desired_scene = self.mapToScene(vp_target)
                            else:
                                desired_scene = QPointF(nx, ny)
                            self.centerOn(desired_scene)
                        except Exception:
                            # Fallback to centering on the raw interpolated
                            # scene coords if mapping fails.
                            try:
                                self.centerOn(nx, ny)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
    
    # ---------- Mouse Event Handling ----------
    
    def mousePressEvent(self, ev):
        """Handle mouse press events to detect clicks on location items"""
        try:
            if ev.button() == Qt.MouseButton.LeftButton:
                # Handle left clicks (single and double click detection)
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    location_id = item.data(0)
                    if isinstance(location_id, int):
                        self.locationClicked.emit(location_id)
            elif ev.button() == Qt.MouseButton.RightButton:
                # Handle right clicks for context menu
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    location_id = item.data(0)
                    if isinstance(location_id, int):
                        # Convert to global position for menu display
                        global_pos = self.mapToGlobal(ev.pos())
                        # Show context menu directly instead of just emitting signal
                        self._show_context_menu(location_id, global_pos)
                        return  # Don't call super() to prevent default behavior
            
            # Call super for other mouse events (panning, etc.)
            super().mousePressEvent(ev)
        except Exception as e:
            logger.error(f"Error in system map mouse press event: {e}")
            super().mousePressEvent(ev)
    
    def mouseDoubleClickEvent(self, ev):
        """Handle double clicks on location items"""
        try:
            if ev.button() == Qt.MouseButton.LeftButton:
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    location_id = item.data(0)
                    if isinstance(location_id, int):
                        self.locationDoubleClicked.emit(location_id)
                        return  # Don't call super() to prevent double processing
            
            super().mouseDoubleClickEvent(ev)
        except Exception as e:
            logger.error(f"Error in system map double click event: {e}")
            super().mouseDoubleClickEvent(ev)

    def _show_context_menu(self, location_id: int, global_pos: QPoint) -> None:
        """Show context menu for location with actions based on player status and location type"""
        try:
            # Get current player status
            snap = player_status.get_status_snapshot() or {}
            current_location_id = None
            try:
                current_location_id = int(snap.get("location_id", 0))
            except Exception:
                current_location_id = 0
                
            current_status = snap.get("status", "Unknown")
            
            # Get location information
            location = db.get_location(location_id)
            if not location:
                return
                
            location_type = (location.get("location_type") or location.get("kind") or "").lower()
            location_name = location.get("location_name") or location.get("name") or f"Location {location_id}"

            # Create context menu
            menu = QMenu(self)
            
            # If this is our current location, show current-location actions
            if location_id == current_location_id:
                self._add_current_location_actions(menu, location_type, location_name, current_status)
            else:
                # Different location - show travel option
                travel_action = QAction(f"Travel to {location_name}", self)
                travel_action.triggered.connect(lambda: self._travel_to_location(location_id))
                menu.addAction(travel_action)
            
            # Show menu at global position
            menu.exec(global_pos)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def _add_current_location_actions(self, menu: QMenu, location_type: str, location_name: str, current_status: str) -> None:
        """Add context-sensitive actions for the current location"""
        try:
            if location_type == "station":
                if current_status.lower() == "orbiting":
                    # Orbiting a station - show docking options
                    dock_action = QAction("Request Docking...", self)
                    dock_action.triggered.connect(lambda: self._request_docking(location_name))
                    menu.addAction(dock_action)
                    
                    refuel_action = QAction("Request Refueling...", self)
                    refuel_action.triggered.connect(lambda: self._request_refueling(location_name))
                    menu.addAction(refuel_action)
                    
                elif current_status.lower() == "docked":
                    # Docked at station - show docked actions
                    menu.addAction(QAction("Access Market", self))
                    menu.addAction(QAction("Ship Services", self))
                    menu.addAction(QAction("Station Services", self))
                    menu.addSeparator()
                    undock_action = QAction("Undock", self)
                    undock_action.triggered.connect(lambda: self._undock_from_station(location_name))
                    menu.addAction(undock_action)
                    
            elif location_type == "planet":
                if current_status.lower() == "orbiting":
                    # Orbiting a planet
                    scan_action = QAction("Scan Planet", self)
                    menu.addAction(scan_action)
                    
                    shuttle_action = QAction("Take Shuttle to Surface...", self)
                    menu.addAction(shuttle_action)
                    
            elif location_type == "moon":
                if current_status.lower() == "orbiting":
                    # Orbiting a moon
                    scan_action = QAction("Scan Moon", self)
                    menu.addAction(scan_action)
                    
            elif location_type in ["asteroid_field", "gas_clouds", "ice_field", "crystal_vein"]:
                if current_status.lower() == "orbiting":
                    # At a resource node
                    mine_action = QAction("Begin Mining Operations", self)
                    menu.addAction(mine_action)
                    
                    scan_action = QAction("Scan Resources", self)
                    menu.addAction(scan_action)
                    
            # Add generic options
            menu.addSeparator()
            info_action = QAction(f"Location: {location_name}", self)
            info_action.setEnabled(False)
            menu.addAction(info_action)
            
        except Exception as e:
            logger.error(f"Error adding current location actions: {e}")

    def _request_docking(self, location_name: str) -> None:
        """Initiate docking request process"""
        try:
            # Start docking process
            from PySide6.QtCore import QTimer
            
            # Show immediate feedback
            player_status.set_ship_state("Requesting docking clearance...")
            
            # Simulate docking approval process (10 seconds)
            def complete_docking():
                try:
                    # Get current location
                    snap = player_status.get_status_snapshot() or {}
                    current_location_id = int(snap.get("location_id", 0))
                    
                    # Set status to docked
                    player_status.dock_at_location(current_location_id)
                    player_status.set_ship_state("Docked")
                    
                    logger.info(f"Successfully docked at {location_name}")
                except Exception as e:
                    logger.error(f"Error completing docking: {e}")
                    player_status.set_ship_state("Orbiting")
            
            # Set up timer for docking completion
            docking_timer = QTimer()
            docking_timer.setSingleShot(True)
            docking_timer.timeout.connect(complete_docking)
            docking_timer.start(10000)  # 10 seconds
            
            logger.info(f"Initiated docking request at {location_name}")
            
        except Exception as e:
            logger.error(f"Error requesting docking: {e}")

    def _request_refueling(self, location_name: str) -> None:
        """Request refueling while in orbit (placeholder)"""
        try:
            logger.info(f"Refueling request at {location_name} - not yet implemented")
        except Exception as e:
            logger.error(f"Error requesting refueling: {e}")

    def _undock_from_station(self, location_name: str) -> None:
        """Undock from station and return to orbit"""
        try:
            # Get current location
            snap = player_status.get_status_snapshot() or {}
            current_location_id = int(snap.get("location_id", 0))
            
            # Set status back to orbiting
            player_status.enter_orbit(current_location_id)
            player_status.set_ship_state("Orbiting")
            
            logger.info(f"Undocked from {location_name}, now orbiting")
            
        except Exception as e:
            logger.error(f"Error undocking: {e}")

    def _travel_to_location(self, entity_id: int) -> None:
        """Emit travel signal with entity_id"""
        try:
            # Find the main window and its presenter
            main_window = self.window()
            if main_window:
                presenter = getattr(main_window, 'presenter_system', None)
                if presenter and hasattr(presenter, 'travel_here'):
                    presenter.travel_here(entity_id)
        except Exception as e:
            logger.error(f"Error initiating travel: {e}")
