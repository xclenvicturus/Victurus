# /ui/maps/galaxy.py

"""
Galaxy Map Display System

Handles the visual display and interaction for the galaxy map, including
system positioning, background rendering, user interaction handling,
and travel path visualization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtCore import QPoint, Signal, Qt, QTimer
from PySide6.QtGui import QPainter, QAction, QCursor
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPixmapItem,
    QMenu,
    QToolTip,
    QLabel,
    QFrame,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from data import db
from game import player_status
from .background_view import BackgroundView
from .icons import list_gifs, pm_from_path_or_kind, randomized_px
from .travel_visualization import TravelVisualization, PathRenderer
from .simple_travel_vis import SimpleTravelStatus
from ..widgets.travel_status_overlay import TravelStatusOverlay
from game_controller.sim_loop import universe_sim
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('galaxy_map')

ASSETS_ROOT  = Path(__file__).resolve().parents[2] / "assets"
GAL_BG_DIR   = ASSETS_ROOT / "galaxy_backgrounds"
STARS_DIR    = ASSETS_ROOT / "stars"


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _as_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _norm_system_row(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a systems row to {id, x, y, name, icon_path}."""
    sid = r.get("id", r.get("system_id", r.get("sys_id")))
    x   = r.get("x", r.get("system_x", r.get("sx")))
    y   = r.get("y", r.get("system_y", r.get("sy")))
    if sid is None or x is None or y is None:
        return None
    name = r.get("name", r.get("system_name"))
    icon = r.get("icon_path")  # DB-only
    return {"id": _as_int(sid), "x": _as_float(x), "y": _as_float(y), "name": name if isinstance(name, str) else None, "icon_path": icon if isinstance(icon, str) else None}


class CustomTooltip(QLabel):
    """Custom tooltip widget that doesn't auto-hide like QToolTip."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #ccc;
                padding: 6px;
                color: #333;
                font-size: 12px;
            }
        """)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.hide()
    
    def show_at(self, pos: QPoint, text: str):
        """Show the tooltip at the specified global position with the given text."""
        self.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()
        self.raise_()
    
    def hide_tooltip(self):
        """Hide the tooltip."""
        self.hide()


class GalaxyMapWidget(BackgroundView):
    logMessage = Signal(str)
    systemClicked = Signal(int)  # Single click on system
    systemDoubleClicked = Signal(int)  # Double click on system
    systemRightClicked = Signal(int, QPoint)  # Right click on system with global position

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        try:
            self.setViewport(QOpenGLWidget())
        except Exception:
            pass
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        hints = self.renderHints()
        hints |= QPainter.RenderHint.SmoothPixmapTransform
        hints &= ~QPainter.RenderHint.Antialiasing
        self.setRenderHints(hints)

        try:
            self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        except Exception:
            pass

        self._system_items: Dict[int, QGraphicsItem] = {}
        self._player_highlight: Optional[QGraphicsItem] = None

        # Enable mouse tracking for hover tooltips
        self.setMouseTracking(True)
        self._hover_timer: Optional[QTimer] = None
        self._hide_timer: Optional[QTimer] = None
        self._last_hovered_system: Optional[int] = None
        self._tooltip_visible: bool = False
        
        # Custom tooltip widget that won't auto-hide
        self._custom_tooltip = CustomTooltip(self)

        self.set_unit_scale(10.0)
        self._apply_unit_scale()
        self.enable_starfield(True)
        self.set_background_mode("viewport")

        candidates = [GAL_BG_DIR / "default.png", GAL_BG_DIR / "defaul.png"]
        bg_path = next((p for p in candidates if p.exists()), None)
        if bg_path:
            self.set_background_image(str(bg_path))
            self.logMessage.emit(f"Galaxy background: {bg_path}")
        else:
            self.set_background_image(None)
            self.logMessage.emit("Galaxy background: gradient (no image found).")

        self._star_gifs: List[Path] = list_gifs(STARS_DIR)
        if not self._star_gifs:
            self.logMessage.emit("WARNING: No star GIFs found in /assets/stars; using placeholders.")

        # Travel visualization components - lines disabled, using overlay system instead
        # self._travel_viz = TravelVisualization()
        # self._path_renderer = PathRenderer(self._travel_viz, show_progress_dot=False, coordinate_system="galaxy")
        # self._path_renderer.set_scene(self._scene)
        
        # Travel status overlay
        self._travel_status = SimpleTravelStatus()
        self._travel_overlay = TravelStatusOverlay(self)
        self._travel_status.travel_status_changed.connect(self._travel_overlay.set_travel_info)
        
        # Connect hyperlink navigation signals
        self._travel_overlay.system_clicked.connect(self._navigate_to_system)
        self._travel_overlay.location_clicked.connect(self._navigate_to_location)

        universe_sim.ensure_running()
        universe_sim.set_visible_system(None)

        self.load()

    def _navigate_to_system(self, system_id: int) -> None:
        """Navigate to a system when hyperlink is clicked"""
        try:
            # Get the parent MapTabs widget to call navigation methods
            parent_widget = self.parent()
            while parent_widget is not None:
                if hasattr(parent_widget, 'center_galaxy_on_system') and callable(getattr(parent_widget, 'center_galaxy_on_system')):
                    getattr(parent_widget, 'center_galaxy_on_system')(system_id)
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            from game_controller.log_config import get_ui_logger
            logger = get_ui_logger(__name__)
            logger.error(f"Failed to navigate to system {system_id}: {e}")

    def _navigate_to_location(self, location_id: int) -> None:
        """Navigate to a location when hyperlink is clicked - switches to system map"""
        try:
            # For galaxy map, location clicks should switch to system map and center on location
            # First, get the system ID for this location
            from data import db
            location_data = db.get_location(location_id)
            if not location_data:
                from game_controller.log_config import get_ui_logger
                logger = get_ui_logger(__name__)
                logger.warning(f"Could not find location data for location_id {location_id}")
                return
            
            system_id = location_data.get('system_id')
            if not system_id:
                from game_controller.log_config import get_ui_logger
                logger = get_ui_logger(__name__)
                logger.warning(f"Location {location_id} has no system_id")
                return
            
            # Find the parent MapTabs widget
            parent_widget = self.parent()
            while parent_widget is not None:
                system_widget = getattr(parent_widget, 'system', None)
                if system_widget and hasattr(system_widget, 'load') and callable(getattr(system_widget, 'load')):
                    # 1) Load the system first (synchronously)
                    try:
                        getattr(system_widget, 'load')(int(system_id))
                    except Exception as e:
                        from game_controller.log_config import get_ui_logger
                        logger = get_ui_logger(__name__)
                        logger.warning(f"Failed to load system {system_id}: {e}")
                    
                    # 2) Switch to system tab
                    if hasattr(parent_widget, 'show_system') and callable(getattr(parent_widget, 'show_system')):
                        getattr(parent_widget, 'show_system')()
                    
                    # 3) Center on the location
                    if hasattr(parent_widget, 'center_system_on_location') and callable(getattr(parent_widget, 'center_system_on_location')):
                        getattr(parent_widget, 'center_system_on_location')(location_id)
                    
                    from game_controller.log_config import get_ui_logger
                    logger = get_ui_logger(__name__)
                    logger.debug(f"Successfully navigated to location {location_id} in system {system_id}")
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            from game_controller.log_config import get_ui_logger
            logger = get_ui_logger(__name__)
            logger.error(f"Failed to navigate to location {location_id}: {e}")

    def load(self) -> None:
        self._scene.clear()
        self._system_items.clear()
        self._player_highlight = None

        try:
            raw = [dict(r) for r in db.get_systems()]
        except Exception:
            raw = []

        systems: List[Dict[str, Any]] = []
        for r in raw:
            n = _norm_system_row(r)
            if n is not None:
                systems.append(n)

        if not systems:
            self._scene.setSceneRect(-50, -50, 100, 100)
            self.logMessage.emit("Galaxy: no systems to display (check DB.get_systems()).")
            return

        min_x = min(s["x"] for s in systems)
        max_x = max(s["x"] for s in systems)
        min_y = min(s["y"] for s in systems)
        max_y = max(s["y"] for s in systems)
        pad = 5
        self._scene.setSceneRect(min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

        desired_px = 20

        for s in systems:
            sid = int(s["id"])
            db_icon = s.get("icon_path")
            star_path: str = db_icon if db_icon else "assets/stars/missing_star.gif"

            x, y = float(s["x"]), float(s["y"])
            final_px = randomized_px(desired_px, salt=sid)

            pm = pm_from_path_or_kind(star_path, "star", final_px)
            item = QGraphicsPixmapItem(pm)
            item.setPos(x, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            # Store system ID for context menu
            item.setData(0, sid)  # Store system ID as data key 0

            try:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            except Exception:
                pass

            try:
                dpr = pm.devicePixelRatio() if hasattr(pm, "devicePixelRatio") else 1.0
            except Exception:
                dpr = 1.0
            item.setOffset(-(pm.width() / dpr) / 2.0, -(pm.height() / dpr) / 2.0)

            self._scene.addItem(item)
            self._system_items[sid] = item

        try:
            player = db.get_player_full() or {}
        except Exception:
            player = {}
        sid = player.get("current_player_system_id")
        if isinstance(sid, int):
            self.refresh_highlight(sid)
            self.center_on_system(sid)
        else:
            self.centerOn((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def get_entities(self) -> List[Dict]:
        try:
            rows = [dict(r) for r in db.get_systems()]
        except Exception:
            rows = []

        out: List[Dict[str, Any]] = []
        for r in rows:
            n = _norm_system_row(r)
            if n is None:
                continue
            sid = int(n["id"])
            db_icon = n.get("icon_path")
            icon = db_icon if isinstance(db_icon, str) and db_icon else None
            out.append({
                "id": sid,
                "name": n.get("name") or r.get("name") or r.get("system_name") or f"System {sid}",
                "x": n["x"],
                "y": n["y"],
                "icon_path": icon,
                "kind": "system",
            })
        return out

    def center_on_entity(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())
        universe_sim.set_visible_system(None)

    def get_entity_viewport_center_and_radius(self, system_id: int) -> Optional[Tuple[QPoint, float]]:
        it = self._system_items.get(system_id)
        if not it:
            return None
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        center = self.mapFromScene(rect.center())
        radius = max(rect.width(), rect.height()) * 0.5
        return (center, radius)

    def refresh_highlight(self, system_id: int) -> None:
        if self._player_highlight is not None:
            self._scene.removeItem(self._player_highlight)
            self._player_highlight = None

    def center_on_system(self, system_id: int) -> None:
        it = self._system_items.get(system_id)
        if not it:
            return
        rect = it.mapToScene(it.boundingRect()).boundingRect()
        self.centerOn(rect.center())
        universe_sim.set_visible_system(None)
        
    # ---------- Travel Visualization ----------
    def show_travel_path(self, dest_type: str, dest_id: int) -> bool:
        """
        Display travel path to destination and return True if path was calculated.
        NOTE: Line-based travel visualization disabled - using overlay system instead.
        """
        # Travel path visualization is now handled by overlay system
        return True
            
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

    def _gather_system_info(self, system_id: int) -> str:
        """Gather system information for tooltip display"""
        try:
            # Get system basic info
            system = db.get_system(system_id)
            if not system:
                return f"System {system_id}: No data available"
            
            system_name = system.get('system_name', system.get('name', f'System {system_id}'))
            info_lines = [f"<b>{system_name}</b>"]
            
            # Get locations (stations, planets, etc.) in the system
            locations = db.get_locations(system_id)
            
            # Count different types of stations and facilities
            stations = [loc for loc in locations if loc.get('location_type') == 'station']
            planets = [loc for loc in locations if loc.get('location_type') == 'planet']
            moons = [loc for loc in locations if loc.get('location_type') == 'moon']
            
            # Count resource node types - use resource_type field for actual type
            resource_types = {}
            for loc in locations:
                if loc.get('location_type') == 'resource':
                    res_type = loc.get('resource_type', 'unknown')
                    resource_types[res_type] = resource_types.get(res_type, 0) + 1
            
            resource_nodes = db.get_resource_nodes(system_id)
            facilities = db.get_facilities(system_id)
            
            # Analyze station names to determine services
            services = {
                'refuel': False,
                'repair': False,
                'market': False,
                'ship_sales': False,
                'refinery': False
            }
            
            # Check station names and facility types for services
            for station in stations:
                station_name = (station.get('location_name', '') or '').lower()
                if any(keyword in station_name for keyword in ['fuel', 'dockyard', 'shipyard']):
                    services['refuel'] = True
                    services['repair'] = True
                if any(keyword in station_name for keyword in ['exchange', 'market', 'trading', 'trade']):
                    services['market'] = True
                if any(keyword in station_name for keyword in ['shipyard', 'ship sales']):
                    services['ship_sales'] = True
                if any(keyword in station_name for keyword in ['refinery hub', 'refinery']):
                    services['refinery'] = True
                # Frontier relays typically provide basic services
                if 'frontier relay' in station_name:
                    services['refuel'] = True
                    services['repair'] = True
                # Orbital exchanges are markets
                if 'orbital exchange' in station_name:
                    services['market'] = True
                    
            # Check facilities for refinery
            for facility in facilities:
                facility_type = (facility.get('facility_type', '') or '').lower()
                if 'refinery' in facility_type:
                    services['refinery'] = True
            
            # Also check system economic tags for services
            try:
                conn = db.get_connection()
                econ_tags = conn.execute(
                    "SELECT tag FROM system_econ_tags WHERE system_id = ?", 
                    (system_id,)
                ).fetchall()
                econ_tag_list = [row[0] for row in econ_tags] if econ_tags else []
                
                if 'tradehub' in econ_tag_list:
                    services['market'] = True
                    services['refuel'] = True
                if 'refinery' in econ_tag_list:
                    services['refinery'] = True
                if 'industrial' in econ_tag_list:
                    services['repair'] = True
                    
            except Exception:
                econ_tag_list = []
            
            # Add locations section - vertically stacked
            location_items = []
            if stations:
                location_items.append(f"&nbsp;&nbsp;• Stations: {len(stations)}")
            if planets:
                location_items.append(f"&nbsp;&nbsp;• Planets: {len(planets)}")
            if moons:
                location_items.append(f"&nbsp;&nbsp;• Moons: {len(moons)}")
                
            if location_items:
                info_lines.append("Locations:")
                info_lines.extend(location_items)
                
            # Add resource node types - vertically stacked
            if resource_types:
                resource_names = {
                    'asteroid_field': 'Asteroid Fields',
                    'crystal_vein': 'Crystal Veins', 
                    'crystal_veins': 'Crystal Veins',  # Handle both singular/plural
                    'gas_cloud': 'Gas Clouds',
                    'gas_clouds': 'Gas Clouds',
                    'ice_field': 'Ice Fields',
                    'ice_fields': 'Ice Fields'
                }
                info_lines.append("Resources:")
                for res_type, count in resource_types.items():
                    display_name = resource_names.get(res_type, res_type.replace('_', ' ').title())
                    info_lines.append(f"&nbsp;&nbsp;• {display_name}: {count}")
                
            # Add services - vertically stacked
            service_items = []
            if services['refuel']:
                service_items.append("&nbsp;&nbsp;• ⛽ Fuel")
            if services['repair']:
                service_items.append("&nbsp;&nbsp;• 🔧 Repair")
            if services['market']:
                service_items.append("&nbsp;&nbsp;• 🏪 Market")
            if services['ship_sales']:
                service_items.append("&nbsp;&nbsp;• 🚢 Ships")
            if services['refinery']:
                service_items.append("&nbsp;&nbsp;• 🏭 Refinery")
                
            if service_items:
                info_lines.append("Services:")
                info_lines.extend(service_items)
            
            # Add economic tags if available (limit to first 4 to keep tooltip readable)
            if econ_tag_list:
                display_tags = econ_tag_list[:4]
                if len(econ_tag_list) > 4:
                    display_tags.append(f"(+{len(econ_tag_list) - 4} more)")
                info_lines.append(f"Economy: {', '.join(display_tags)}")
            
            # Ship counts placeholder - for future enhancement when NPC ships are added
            # info_lines.append("Ships: 3 Neutral, 1 Allied")
            
            return "<br>".join(info_lines)
            
        except Exception as e:
            logger.error(f"Error gathering system info for {system_id}: {e}")
            return f"System {system_id}: Error loading data"

    def mouseMoveEvent(self, ev) -> None:
        """Handle mouse move events for hover tooltips"""
        try:
            # Check if we're hovering over a system item (with buffer area)
            current_system_id = self._get_system_at_position(ev.pos())
            
            # If we're hovering over a different system than before
            if current_system_id != self._last_hovered_system:
                # Clear any existing timers
                self._clear_all_timers()
                
                # If we're no longer over any system, start hide timer
                if current_system_id is None:
                    self._last_hovered_system = None
                    self._start_hide_timer()
                else:
                    # We're over a new system - show tooltip after delay
                    global_pos = self.mapToGlobal(ev.pos())
                    self._last_hovered_system = current_system_id
                    self._hover_timer = QTimer()
                    self._hover_timer.setSingleShot(True)
                    self._hover_timer.timeout.connect(
                        lambda: self._show_system_tooltip(current_system_id, global_pos)
                    )
                    self._hover_timer.start(500)  # 500ms delay
            
            # If we're still over the same system, don't do anything
            # Just let the tooltip stay visible without refreshing
            
            super().mouseMoveEvent(ev)
        except Exception as e:
            logger.error(f"Error in galaxy map mouse move event: {e}")
            super().mouseMoveEvent(ev)

    def _get_system_at_position(self, pos: QPoint) -> Optional[int]:
        """Get system ID at position, with buffer area around small icons"""
        try:
            # First try direct item hit
            item = self.itemAt(pos)
            if item and item.data(0) is not None:
                system_data = item.data(0)
                if isinstance(system_data, int):
                    return system_data
            
            # If no direct hit, check nearby items with buffer
            buffer_radius = 25  # 25 pixel buffer around icons for easier hovering
            scene_pos = self.mapToScene(pos)
            
            # Find the closest system within buffer radius
            closest_system = None
            closest_distance = float('inf')
            
            for system_id, item in self._system_items.items():
                try:
                    item_scene_pos = item.pos()
                    dx = scene_pos.x() - item_scene_pos.x()
                    dy = scene_pos.y() - item_scene_pos.y()
                    distance = (dx * dx + dy * dy) ** 0.5
                    
                    # Convert scene distance to viewport pixels for consistent buffer
                    viewport_distance = distance * self.transform().m11()  # scale factor
                    
                    if viewport_distance <= buffer_radius and viewport_distance < closest_distance:
                        closest_distance = viewport_distance
                        closest_system = system_id
                except Exception:
                    continue
            
            return closest_system
        except Exception as e:
            logger.error(f"Error getting system at position: {e}")
            return None

    def _clear_all_timers(self) -> None:
        """Clear all tooltip-related timers"""
        try:
            if self._hover_timer:
                self._hover_timer.stop()
                self._hover_timer = None
            if self._hide_timer:
                self._hide_timer.stop()
                self._hide_timer = None
        except Exception as e:
            logger.error(f"Error clearing timers: {e}")

    def _start_hide_timer(self) -> None:
        """Start timer to hide tooltip after 1 second delay"""
        try:
            if self._hide_timer:
                self._hide_timer.stop()
            
            self._hide_timer = QTimer()
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self._hide_tooltip)
            self._hide_timer.start(1000)  # 1 second delay before hiding
        except Exception as e:
            logger.error(f"Error starting hide timer: {e}")

    def _hide_tooltip(self) -> None:
        """Hide the tooltip"""
        try:
            self._custom_tooltip.hide_tooltip()
            self._tooltip_visible = False
        except Exception as e:
            logger.error(f"Error hiding tooltip: {e}")

    def _show_system_tooltip(self, system_id: int, global_pos: QPoint) -> None:
        """Show tooltip for system with gathered information"""
        try:
            tooltip_text = self._gather_system_info(system_id)
            
            # Show custom tooltip that won't auto-hide
            self._custom_tooltip.show_at(global_pos, tooltip_text)
            self._tooltip_visible = True
            
        except Exception as e:
            logger.error(f"Error showing system tooltip: {e}")

    def leaveEvent(self, ev) -> None:
        """Hide tooltip when mouse leaves the widget"""
        try:
            self._clear_all_timers()
            self._custom_tooltip.hide_tooltip()
            self._last_hovered_system = None
            self._tooltip_visible = False
            super().leaveEvent(ev)
        except Exception as e:
            logger.error(f"Error in galaxy map leave event: {e}")
            super().leaveEvent(ev)

    # ---------- Mouse Event Handling ----------
    
    def mousePressEvent(self, ev):
        """Handle mouse press events to detect clicks on system items"""
        try:
            if ev.button() == Qt.MouseButton.LeftButton:
                # Handle left clicks (single and double click detection)
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    system_id = item.data(0)
                    if isinstance(system_id, int):
                        self.systemClicked.emit(system_id)
            elif ev.button() == Qt.MouseButton.RightButton:
                # Handle right clicks for context menu
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    system_id = item.data(0)
                    if isinstance(system_id, int):
                        # Convert to global position for menu display
                        global_pos = self.mapToGlobal(ev.pos())
                        # Show context menu directly instead of just emitting signal
                        self._show_context_menu(system_id, global_pos)
                        return  # Don't call super() to prevent default behavior
            
            # Call super for other mouse events (panning, etc.)
            super().mousePressEvent(ev)
        except Exception as e:
            logger.error(f"Error in galaxy map mouse press event: {e}")
            super().mousePressEvent(ev)
    
    def mouseDoubleClickEvent(self, ev):
        """Handle double clicks on system items"""
        try:
            if ev.button() == Qt.MouseButton.LeftButton:
                item = self.itemAt(ev.pos())
                if item and item.data(0) is not None:
                    system_id = item.data(0)
                    if isinstance(system_id, int):
                        self.systemDoubleClicked.emit(system_id)
                        return  # Don't call super() to prevent double processing
            
            super().mouseDoubleClickEvent(ev)
        except Exception as e:
            logger.error(f"Error in galaxy map double click event: {e}")
            super().mouseDoubleClickEvent(ev)

    def _show_context_menu(self, system_id: int, global_pos: QPoint) -> None:
        """Show context menu for system with travel options"""
        try:
            # Get current player system
            snap = player_status.get_status_snapshot() or {}
            current_system_id = None
            try:
                current_system_id = int(snap.get("system_id", 0))
            except Exception:
                current_system_id = 0

            # Don't show menu if clicking on current system
            if system_id == current_system_id:
                return

            # Create context menu
            menu = QMenu(self)
            travel_action = QAction("Travel to System", self)
            
            # Use negative system_id for galaxy context (consistent with list widgets)
            travel_action.triggered.connect(lambda: self._travel_to_system(-system_id))
            menu.addAction(travel_action)
            
            # Show menu at global position
            menu.exec(global_pos)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def _travel_to_system(self, entity_id: int) -> None:
        """Emit travel signal with entity_id"""
        try:
            # Find the main window and its presenter
            main_window = self.window()
            if main_window:
                presenter = getattr(main_window, 'presenter_galaxy', None)
                if presenter and hasattr(presenter, 'travel_here'):
                    presenter.travel_here(entity_id)
        except Exception as e:
            logger.error(f"Error initiating travel: {e}")
