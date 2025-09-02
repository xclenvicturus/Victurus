# /ui/maps/galaxy_leadline.py

"""Galaxy Map Lead Line Overlay

Transparent overlay widget that draws lead lines from hover items to their entries in lists.
• Real-time line drawing based on mouse position  
• Viewport coordinate mapping between map and list widgets
• Color and width customization with optional glow effects
• Timer-based delayed display to prevent flicker
"""

from __future__ import annotations

from typing import Optional, Union, Callable, Tuple, cast, Any, TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QTimer, Qt, QEvent
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QTreeWidgetItem, QTabWidget

if TYPE_CHECKING:
    from .tabs import MapTabs

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
        self._active = True
        self._anchor = QPoint(anchor)
        self._target = QPoint(target_endpoint)
        self.update()

    def clear(self):
        self._active = False
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


class GalaxyLeaderLineController(QObject):
    """
    Hover → leader-line controller for the **Galaxy** map.
    - Active ONLY when the Galaxy tab is selected.
    - No click-lock; hover-only.
    - Systems in the list use negative ids; convert to positive system ids for map queries.
    """

    def __init__(
        self,
        tabs: MapTabs,                    # type: ignore[name-defined]
        list_panel: LocationList,         # type: ignore[name-defined]
        make_overlay: Callable[[QWidget], LeadLine] = LeadLine,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(tabs)
        self._tabs = tabs
        self._panel = list_panel
        self._make_overlay = make_overlay
        self._log = log or (lambda _m: None)

        self._overlay: Optional[LeadLine] = None
        self._overlay_src: Optional[QWidget] = None  # where map coords live

        # Smooth follow timer (~60 FPS)
        self._tick = QTimer(self)
        self._tick.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._on_tick)
        self._line_active: bool = False

        self._install_view_event_filters()

        # wire panel signals we need (hover-only)
        self._panel.hovered.connect(self.on_hover)
        self._panel.leftView.connect(self.on_leave)
        self._panel.anchorMoved.connect(self.refresh)

    # -------- public API --------

    def attach(self) -> None:
        """Create/parent overlay to the active map's source widget and do an initial refresh."""
        self._reparent_overlay_to_current_view()
        if self._overlay:
            if self._is_galaxy_tab():
                self._overlay.show()
                self._overlay.raise_()
            else:
                self._overlay.hide()
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
        """When tabs change, reparent the overlay and enforce scope immediately."""
        self._reparent_overlay_to_current_view()
        if not self._is_galaxy_tab():
            self._line_active = False
            if self._overlay:
                try:
                    self._overlay.clear()
                    self._overlay.hide()
                except Exception:
                    pass
            self._maybe_stop_tick()
            return

        if self._overlay:
            try:
                self._overlay.show()
                self._overlay.raise_()
            except Exception:
                pass
        self.refresh()
        self._ensure_tick_running()

    def _scope_allows_now(self) -> bool:
        """
        Active only when:
        1) The Galaxy tab is the currently selected tab, AND
        2) Our overlay is parented to the Galaxy viewport.
        """
        try:
            tw = getattr(self._tabs, "tabs", None)
            gal = getattr(self._tabs, "galaxy", None)
            if tw is None or gal is None or self._overlay_src is None:
                return False

            # Must be on the Galaxy tab
            try:
                if tw.currentWidget() is not gal:
                    return False
            except Exception:
                return False

            # And our overlay must be attached to the Galaxy viewport
            gal_vp = self._widget_viewport(gal)
            return self._overlay_src is gal_vp
        except Exception:
            return False

    def on_hover(self, entity_id: int) -> None:
        if not self._scope_allows_now():
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        inside = getattr(self._panel, "cursor_inside_viewport", None)
        if callable(inside) and not inside():
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        if self._overlay is None:
            return
        try:
            eid = int(entity_id)
        except Exception:
            return
        self._line_active = True
        self._attach_leader(eid)
        if self._overlay:
            self._overlay.show()
            self._overlay.raise_()
        self._ensure_tick_running()

    def on_leave(self) -> None:
        self.clear()

    def refresh(self) -> None:
        if not self._scope_allows_now():
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        inside = getattr(self._panel, "cursor_inside_viewport", None)
        if callable(inside) and not inside():
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        if self._overlay is None:
            return

        item = self._panel.current_hover_item()
        if not isinstance(item, QTreeWidgetItem):
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        data_val = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            eid = int(data_val)
        except Exception:
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        self._line_active = True
        self._attach_leader(eid)
        if self._overlay:
            self._overlay.show()
            self._overlay.raise_()
        self._ensure_tick_running()

    def clear(self) -> None:
        self._line_active = False
        if self._overlay:
            self._overlay.clear()
        self._maybe_stop_tick()

    # -------- internals --------

    def _tab_widget(self) -> Optional[QTabWidget]:
        tw = getattr(self._tabs, "tabs", None)
        return tw if isinstance(tw, QTabWidget) else None

    def _safe_current_widget(self) -> Optional[QWidget]:
        tw = self._tab_widget()
        if tw is not None:
            try:
                w = tw.currentWidget()
                return w if isinstance(w, QWidget) else None
            except Exception:
                pass
        return None

    def _is_galaxy_tab(self) -> bool:
        """True when the active tab is the Galaxy map widget."""
        try:
            tw = self._tab_widget()
            if tw is None:
                return False
            gw = getattr(self._tabs, "galaxy", None)
            if gw is None:
                return False
            idx_current = tw.currentIndex()
            idx_galaxy = tw.indexOf(gw)
            return idx_galaxy >= 0 and idx_current == idx_galaxy
        except Exception:
            return False

    def _install_view_event_filters(self) -> None:
        for wname in ("galaxy", "system"):
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
        active = self._safe_current_widget()
        if obj is active or obj is self._widget_viewport(active):
            if event.type() in (QEvent.Type.Show, QEvent.Type.Polish, QEvent.Type.Resize):
                QTimer.singleShot(0, self._reparent_overlay_to_current_view)
                QTimer.singleShot(0, self.refresh)
                self._ensure_tick_running()
        return super().eventFilter(obj, event)

    def _widget_viewport(self, w: Optional[QWidget]) -> Optional[QWidget]:
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
        """Parent the overlay to the current map viewport; hide it if out of scope."""
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
            if self._is_galaxy_tab():
                self._overlay.show()
                self._overlay.raise_()
            else:
                self._overlay.hide()
        except Exception:
            pass

    def _attach_leader(self, eid: int) -> None:
        if self._overlay is None or self._overlay_src is None:
            return

        anchor = self._compute_anchor(eid)
        endpoint = self._compute_endpoint(eid, anchor)

        if anchor is None or endpoint is None:
            self.clear()
            return

        self._overlay.show_temp(anchor, endpoint)

    # ---- continuous follow ----

    def _ensure_tick_running(self) -> None:
        if self._is_galaxy_tab() and self._line_active and (self._overlay is not None) and (self._overlay_src is not None):
            if not self._tick.isActive():
                self._tick.start()
        else:
            self._maybe_stop_tick()

    def _maybe_stop_tick(self) -> None:
        if self._tick.isActive() and (not self._line_active or self._overlay is None or not self._is_galaxy_tab()):
            self._tick.stop()

    def _on_tick(self) -> None:
        if not self._scope_allows_now():
            self.clear()
            if self._overlay:
                self._overlay.hide()
            return

        if self._overlay is None or self._overlay_src is None:
            self._maybe_stop_tick()
            return

        inside = getattr(self._panel, "cursor_inside_viewport", None)
        if callable(inside) and not inside():
            self._line_active = False
            if self._overlay:
                self._overlay.clear()
            self._maybe_stop_tick()
            return

        try:
            if self._overlay.geometry() != self._overlay_src.rect():
                self._overlay.setGeometry(self._overlay_src.rect())
        except Exception:
            pass

        eid: Optional[int] = None
        item = self._panel.current_hover_item()
        if isinstance(item, QTreeWidgetItem):
            data_val = item.data(0, Qt.ItemDataRole.UserRole)
            try:
                eid = int(data_val)
            except Exception:
                eid = None

        if eid is None:
            self._line_active = False
            self._maybe_stop_tick()
            if self._overlay:
                self._overlay.clear()
            return

        anchor = self._compute_anchor(eid)
        endpoint = self._compute_endpoint(eid, anchor)
        if anchor is None or endpoint is None:
            return

        self._overlay.show_temp(anchor, endpoint)
        self._overlay.show()
        self._overlay.raise_()

    # ---- geometry helpers ----

    def _compute_anchor(self, eid: int) -> Optional[QPoint]:
        if self._overlay is None:
            return None

        item: Optional[QTreeWidgetItem] = None
        try:
            raw = self._panel.current_hover_item()
        except Exception:
            raw = None

        if isinstance(raw, QTreeWidgetItem):
            item = raw

        apfi = getattr(self._panel, "anchor_point_for_item", None)
        if isinstance(item, QTreeWidgetItem) and callable(apfi):
            try:
                a = apfi(self._overlay, item)
                if isinstance(a, QPoint):
                    return a
            except Exception:
                pass

        # fallback: right edge of the panel, vertically centered
        try:
            panel_rect = self._panel.rect()
            p = panel_rect.center()
            p.setX(panel_rect.right() - 8)
            g = self._panel.mapToGlobal(p)
            a = self._overlay.mapFromGlobal(g)
            ax = max(0, min(self._overlay.width() - 1, a.x()))
            ay = max(0, min(self._overlay.height() - 1, a.y()))
            return QPoint(ax, ay)
        except Exception:
            return QPoint(max(0, self._overlay.width() - 8), self._overlay.height() // 2)

    def _compute_endpoint(self, eid: int, anchor: Optional[QPoint]) -> Optional[QPoint]:
        if anchor is None:
            return None

        # Galaxy list encodes systems as negative ids; normalize to positive for map lookups.
        if isinstance(eid, int) and eid < 0:
            eid = -eid

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
