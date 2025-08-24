# /ui/maps/leadline.py

from __future__ import annotations

from typing import Optional, Union, Callable, Tuple, cast, Any, TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QTimer, Qt, QEvent
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QTreeWidgetItem, QTabWidget

if TYPE_CHECKING:
    from .tabs import MapTabs
    from ..widgets.location_list import LocationList

ColorLike = Union[QColor, str]


class LeadLine(QWidget):
    """
    Transparent overlay that draws the lead line over the map viewport on hover.
    Supports runtime color/width (and an optional soft glow).
    The line:
      - starts at the list item's right edge point (projected into the map viewport)
      - draws a short horizontal stub into the map
      - then angles to the target symbol edge
    """
    def __init__(self, parent: Optional[QWidget]):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)

        self._active = False
        self._locked = False
        self._anchor = QPoint(0, 0)
        self._target = QPoint(0, 0)
        self._stub = 14  # px

        # Style
        self._color: QColor = QColor(0, 255, 128)   # neon green default
        self._width: int = 2                        # px
        self._glow_enabled: bool = True
        self._glow_extra_px: int = 6
        self._glow_alpha: int = 90                  # 0..255

    # ---------- public API (state) ----------
    def show_temp(self, anchor: QPoint, target_endpoint: QPoint):
        if self._locked:
            return
        self._active = True
        self._anchor = QPoint(anchor)
        self._target = QPoint(target_endpoint)
        self.update()

    def lock_to(self, anchor: QPoint, target_endpoint: QPoint):
        self._locked = True
        self._active = True
        self._anchor = QPoint(anchor)
        self._target = QPoint(target_endpoint)
        self.update()

    def clear(self):
        self._active = False
        self._locked = False
        self.update()

    # ---------- public API (style) ----------
    def set_style(
        self,
        color: Optional[ColorLike] = None,
        width: Optional[int] = None,
        glow_enabled: Optional[bool] = None,
        glow_extra_px: Optional[int] = None,
        glow_alpha: Optional[int] = None,
    ) -> None:
        if color is not None:
            self.set_color(color)
        if width is not None:
            self.set_width(width)
        if glow_enabled is not None:
            self._glow_enabled = bool(glow_enabled)
        if glow_extra_px is not None:
            try:
                self._glow_extra_px = max(0, int(glow_extra_px))
            except Exception:
                pass
        if glow_alpha is not None:
            try:
                self._glow_alpha = max(0, min(255, int(glow_alpha)))
            except Exception:
                pass
        self.update()

    def set_color(self, color: ColorLike) -> None:
        if isinstance(color, QColor):
            self._color = QColor(color)
        else:
            c = QColor(str(color))
            if c.isValid():
                self._color = c
        self.update()

    def set_width(self, width: int) -> None:
        try:
            self._width = max(1, int(width))
            self.update()
        except Exception:
            pass

    # ---------- painting ----------
    def paintEvent(self, _ev):
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        def mkpen(color: QColor, width: int) -> QPen:
            pen = QPen(color)
            pen.setWidth(width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            return pen

        mid = QPoint(max(0, self._anchor.x() - self._stub), self._anchor.y())

        # optional glow underlay
        if self._glow_enabled and self._glow_extra_px > 0 and self._width > 0:
            glow = QColor(self._color)
            glow.setAlpha(self._glow_alpha)
            p.setPen(mkpen(glow, self._width + self._glow_extra_px))
            p.drawLine(self._anchor, mid)
            p.drawLine(mid, self._target)

        # main stroke
        p.setPen(mkpen(self._color, self._width))
        p.drawLine(self._anchor, mid)
        p.drawLine(mid, self._target)


class LeaderLineController(QObject):
    """
    Encapsulates hover/click → leader-line behavior, including:
      - Parenting the overlay onto the active map's source widget (viewport() if present)
      - Reattaching the line when tabs change, list scrolls/resizes, or viewports appear later
      - Optional click-to-lock behavior (per-tab)
      - Continuous refresh so the line smoothly follows moving targets / pan-zoom changes
    """

    def __init__(
        self,
        tabs: MapTabs,                    # type: ignore[name-defined]
        list_panel: LocationList,         # type: ignore[name-defined]
        make_overlay: Callable[[QWidget], LeadLine] = LeadLine,
        log: Optional[Callable[[str], None]] = None,
        enable_lock: bool = False,
    ) -> None:
        super().__init__(tabs)
        self._tabs = tabs
        self._panel = list_panel
        self._make_overlay = make_overlay
        self._log = log or (lambda _m: None)
        self._enable_lock = bool(enable_lock)

        self._overlay: Optional[LeadLine] = None
        self._overlay_src: Optional[QWidget] = None  # where map coords live

        # separate locks per tab (0=galaxy, 1=system)
        self._locked_by_tab: dict[int, Optional[int]] = {0: None, 1: None}

        # Smooth follow timer (~60 FPS by default)
        self._tick = QTimer(self)
        self._tick.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick.setInterval(16)  # ~60 fps
        self._tick.timeout.connect(self._on_tick)
        self._line_active: bool = False  # whether we should draw/follow now

        # watch the map widgets and their viewports so we can reparent overlay when they initialize
        self._install_view_event_filters()

        # wire panel signals we need
        self._panel.hovered.connect(self.on_hover)
        self._panel.leftView.connect(self.on_leave)
        self._panel.anchorMoved.connect(self.refresh)
        if self._enable_lock:
            self._panel.clicked.connect(self.on_click)

    # -------- public API --------

    def attach(self) -> None:
        """Create/parent overlay to the active map's source widget and do an initial refresh."""
        self._reparent_overlay_to_current_view()
        self._ensure_tick_running()
        QTimer.singleShot(0, self.refresh)

    # ---- style passthroughs ----
    def set_line_color(self, color: QColor | str) -> None:
        if self._overlay is not None:
            self._overlay.set_color(color)

    def set_line_width(self, width: int) -> None:
        if self._overlay is not None:
            self._overlay.set_width(width)

    def set_line_style(
        self,
        color: QColor | str | None = None,
        width: int | None = None,
        glow_enabled: bool | None = None,
        glow_extra_px: int | None = None,
        glow_alpha: int | None = None,
    ) -> None:
        if self._overlay is not None:
            self._overlay.set_style(
                color=color,
                width=width,
                glow_enabled=glow_enabled,
                glow_extra_px=glow_extra_px,
                glow_alpha=glow_alpha,
            )

    def set_follow_fps(self, fps: int) -> None:
        """Optional: adjust the refresh rate (default 60)."""
        try:
            fps = max(10, min(120, int(fps)))
            self._tick.setInterval(int(1000 / fps))
        except Exception:
            pass

    def on_tab_changed(self, _idx: int) -> None:
        self._reparent_overlay_to_current_view()
        self.refresh()
        self._ensure_tick_running()

    def on_hover(self, entity_id: int) -> None:
        if self._overlay is None:
            return
        if self._enable_lock and self._current_lock() is not None:
            return
        try:
            eid = int(entity_id)
        except Exception:
            return
        self._line_active = True
        self._attach_leader(eid, locked=False)
        self._ensure_tick_running()

    def on_click(self, entity_id: int) -> None:
        """Toggle click lock (only if enabled)."""
        if not self._enable_lock:
            return
        try:
            eid = int(entity_id)
        except Exception:
            return
        cur = self._current_lock()
        if cur == eid:
            self._set_current_lock(None)
            self._log("Leader line unlocked.")
            self.clear()
            return
        self._set_current_lock(eid)
        self._line_active = True
        self._attach_leader(eid, locked=True)
        self._ensure_tick_running()

    def on_leave(self) -> None:
        """Hide leader when mouse leaves the list (unless locked)."""
        if not self._enable_lock or self._current_lock() is None:
            self.clear()

    def refresh(self) -> None:
        """One-shot re-attach (also used when list resizes/scrolls)."""
        if self._overlay is None:
            return
        locked = self._current_lock()
        if locked is not None:
            self._line_active = True
            self._attach_leader(locked, locked=True)
            self._ensure_tick_running()
            return

        item = self._panel.current_hover_item()
        if not isinstance(item, QTreeWidgetItem):
            # nothing hovered; only active if locked
            if self._current_lock() is None:
                self.clear()
            return
        data_val = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            eid = int(data_val)
        except Exception:
            self.clear()
            return
        self._line_active = True
        self._attach_leader(eid, locked=False)
        self._ensure_tick_running()

    def clear(self) -> None:
        self._line_active = False
        if self._overlay:
            self._overlay.clear()
        self._maybe_stop_tick()

    # -------- internals --------

    def _tab_widget(self) -> Optional[QTabWidget]:
        """Return the inner QTabWidget from MapTabs if present and typed."""
        tw = getattr(self._tabs, "tabs", None)
        return tw if isinstance(tw, QTabWidget) else None

    def _safe_current_index(self) -> int:
        tw = self._tab_widget()
        if tw is not None:
            try:
                return tw.currentIndex()
            except Exception:
                pass
        return 0

    def _safe_current_widget(self) -> Optional[QWidget]:
        tw = self._tab_widget()
        if tw is not None:
            try:
                w = tw.currentWidget()
                return w if isinstance(w, QWidget) else None
            except Exception:
                pass
        return None

    def _current_lock(self) -> Optional[int]:
        return self._locked_by_tab.get(self._safe_current_index(), None)

    def _set_current_lock(self, eid: Optional[int]) -> None:
        self._locked_by_tab[self._safe_current_index()] = eid

    def _install_view_event_filters(self) -> None:
        for wname in ("galaxy", "solar"):
            w = getattr(self._tabs, wname, None)
            if isinstance(w, QWidget):
                try:
                    w.installEventFilter(self)
                except Exception:
                    pass
                vp = self._widget_viewport(w)
                if isinstance(vp, QWidget) and vp is not w:
                    try:
                        vp.installEventFilter(self)
                    except Exception:
                        pass

    def eventFilter(self, obj, event):
        # reparent/sync overlay when active map or its viewport shows/polishes/resizes
        active = self._safe_current_widget()
        if obj is active or obj is self._widget_viewport(active):
            if event.type() in (QEvent.Type.Show, QEvent.Type.Polish, QEvent.Type.Resize):
                QTimer.singleShot(0, self._reparent_overlay_to_current_view)
                QTimer.singleShot(0, self.refresh)
                self._ensure_tick_running()
        return super().eventFilter(obj, event)

    def _widget_viewport(self, w: Optional[QWidget]) -> Optional[QWidget]:
        """Safely get a widget's viewport() if it exists and is a QWidget; else return the widget."""
        if w is None:
            return None
        vp_attr = getattr(w, "viewport", None)
        try:
            if callable(vp_attr):
                vpw = vp_attr()
                if isinstance(vpw, QWidget):
                    return vpw
        except Exception:
            pass
        return w

    def _reparent_overlay_to_current_view(self) -> None:
        src = self._widget_viewport(self._safe_current_widget())
        if not isinstance(src, QWidget):
            return
        self._overlay_src = src
        if self._overlay is None:
            self._overlay = self._make_overlay(src)
        else:
            self._overlay.setParent(src)
        try:
            self._overlay.setGeometry(src.rect())
            self._overlay.show()      # make sure it's visible
            self._overlay.raise_()    # keep it above the viewport
        except Exception:
            pass

    def _attach_leader(self, eid: int, locked: bool) -> None:
        """Compute anchor/endpoint once and draw."""
        if self._overlay is None or self._overlay_src is None:
            return

        anchor = self._compute_anchor(eid, locked)
        endpoint = self._compute_endpoint(eid, anchor)

        if anchor is None or endpoint is None:
            self.clear()
            return

        if locked and self._enable_lock:
            self._overlay.lock_to(anchor, endpoint)
        else:
            self._overlay.show_temp(anchor, endpoint)

    # ---- continuous follow ----

    def _ensure_tick_running(self) -> None:
        """Run the refresh timer whenever a line is active and we have a view."""
        if self._line_active and (self._overlay is not None) and (self._overlay_src is not None):
            if not self._tick.isActive():
                self._tick.start()
        else:
            self._maybe_stop_tick()

    def _maybe_stop_tick(self) -> None:
        if self._tick.isActive() and (not self._line_active or self._overlay is None):
            self._tick.stop()

    def _on_tick(self) -> None:
        """Recompute anchor/endpoint frequently to follow moving targets."""
        if self._overlay is None or self._overlay_src is None:
            self._maybe_stop_tick()
            return

        # keep overlay geometry in sync with the source view
        try:
            if self._overlay.geometry() != self._overlay_src.rect():
                self._overlay.setGeometry(self._overlay_src.rect())
        except Exception:
            pass

        eid = self._current_lock()
        locked = True
        if eid is None:
            # if not locked, follow the currently hovered item (if any)
            item = self._panel.current_hover_item()
            if isinstance(item, QTreeWidgetItem):
                data_val = item.data(0, Qt.ItemDataRole.UserRole)
                try:
                    eid = int(data_val)
                    locked = False
                except Exception:
                    eid = None

        if eid is None:
            # nothing to draw
            self._line_active = False
            self._maybe_stop_tick()
            if self._overlay:
                self._overlay.clear()
            return

        anchor = self._compute_anchor(eid, locked)
        endpoint = self._compute_endpoint(eid, anchor)
        if anchor is None or endpoint is None:
            return

        if locked and self._enable_lock:
            self._overlay.lock_to(anchor, endpoint)
        else:
            self._overlay.show_temp(anchor, endpoint)

    # ---- geometry helpers ----

    def _compute_anchor(self, eid: int, locked: bool) -> Optional[QPoint]:
        """Anchor at list item's right edge projected into the overlay coords."""
        if self._overlay is None:
            return None

        # Narrow from object -> QTreeWidgetItem via isinstance
        item: Optional[QTreeWidgetItem] = None
        raw: Any = None

        if locked:
            finder = getattr(self._panel, "find_item_by_id", None)
            if callable(finder):
                try:
                    raw = finder(int(eid))
                except Exception:
                    raw = None
        else:
            try:
                raw = self._panel.current_hover_item()
            except Exception:
                raw = None

        if isinstance(raw, QTreeWidgetItem):
            item = raw

        # Preferred: ask the panel (it already maps via global→overlay)
        if isinstance(item, QTreeWidgetItem):
            apfi = getattr(self._panel, "anchor_point_for_item", None)
            if callable(apfi):
                try:
                    a = apfi(self._overlay, item)
                    if isinstance(a, QPoint):
                        return a
                except Exception:
                    pass

        # Fallback: right-center of the panel → GLOBAL → overlay (no hierarchy requirement)
        try:
            panel_rect = self._panel.rect()
            p = panel_rect.center()
            p.setX(panel_rect.right() - 8)

            g = self._panel.mapToGlobal(p)      # panel → global
            a = self._overlay.mapFromGlobal(g)  # global → overlay

            # Clamp to overlay bounds
            ax = max(0, min(self._overlay.width() - 1, a.x()))
            ay = max(0, min(self._overlay.height() - 1, a.y()))
            return QPoint(ax, ay)
        except Exception:
            # Last resort: near right edge of overlay
            return QPoint(max(0, self._overlay.width() - 8), self._overlay.height() // 2)

    def _compute_endpoint(self, eid: int, anchor: Optional[QPoint]) -> Optional[QPoint]:
        """Trim line to the icon edge for the target entity (map coords already in overlay)."""
        if anchor is None:
            return None
        current_view = self._safe_current_widget()
        get_info = getattr(current_view, "get_entity_viewport_center_and_radius", None)
        if not callable(get_info):
            return None
        info = get_info(int(eid))
        if info is None:
            return None
        center, radius = cast(Tuple[QPoint, float], info)

        dx = center.x() - anchor.x()
        dy = center.y() - anchor.y()
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= 1.0:
            return QPoint(center.x(), center.y())
        ux, uy = dx / dist, dy / dist
        return QPoint(int(round(center.x() - ux * radius)),
                      int(round(center.y() - uy * radius)))
