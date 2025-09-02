# /ui/widgets/galaxy_system_list.py
"""
Galaxy System List Widget

Provides filterable, sortable lists of galaxy systems with search functionality,
category filtering, and integration with the galaxy map display system.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple
import re

from game import player_status

from PySide6.QtCore import QPoint, QEvent, Qt, Signal, QPointF
from settings import system_config as cfg
from PySide6.QtGui import QFont, QIcon, QColor, QBrush, QAction, QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
    QHeaderView,
)

# Try to use the GIF-first pixmap helper if available (keeps thumbnails in sync with map GIFs)
try:
    from ui.maps.icons import pm_from_path_or_kind  # type: ignore
except Exception:  # pragma: no cover
    pm_from_path_or_kind = None  # type: ignore

# -------- Helpers (duplicated for independence) --------
_LY_TO_AU = float(getattr(cfg, "LY_TO_AU", 63241.0))  # Approximate astronomical units in one light-year


def _norm(s: Optional[str]) -> str:
    """Normalize kind/category text for robust matching (case/space/punct-insensitive)."""
    if not s:
        return ""
    s = s.lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def _to_int(x) -> Optional[int]:
    try:
        return int(x)  # type: ignore[arg-type]
    except Exception:
        return None


_LY_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*ly\b", re.IGNORECASE)
_AU_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*au\b", re.IGNORECASE)


def _extract_ly(r: Dict) -> float:
    """Prefer numeric LY, else parse from 'distance'. Unknown -> inf."""
    try:
        v = r.get("dist_ly")
        if v not in (None, ""):
            return float(v)
    except Exception:
        pass
    try:
        v = r.get("jump_dist")
        if v not in (None, ""):
            return float(v)
    except Exception:
        pass
    try:
        txt = str(r.get("distance") or "")
        m = _LY_RE.search(txt)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return float("inf")


def _extract_au(r: Dict) -> float:
    """Prefer numeric AU, else sum intra legs, else parse AU from 'distance'. Unknown -> inf."""
    try:
        v = r.get("dist_au")
        if v not in (None, ""):
            return float(v)
    except Exception:
        pass
    total = 0.0
    has_leg = False
    try:
        v = r.get("intra_current_au")
        if v not in (None, ""):
            total += float(v)
            has_leg = True
    except Exception:
        pass
    try:
        v = r.get("intra_target_au")
        if v not in (None, ""):
            total += float(v)
            has_leg = True
    except Exception:
        pass
    if has_leg:
        return total
    try:
        txt = str(r.get("distance") or "")
        ms = _AU_RE.findall(txt)
        if ms:
            return float(ms[-1])
    except Exception:
        pass
    return float("inf")


def _smart_distance_key(r: Dict, descending: bool) -> Tuple[float, float, str]:
    name = (r.get("name", "") or "").lower()
    total_au = 0.0
    has_ly_numeric = False
    has_au_numeric = False

    v_ly_str = None
    try:
        v_ly_str = r.get("dist_ly")
        if v_ly_str in (None, ""):
            v_ly_str = r.get("jump_dist")
        if v_ly_str not in (None, ""):
            ly_val = float(v_ly_str)
            total_au += ly_val * _LY_TO_AU
            has_ly_numeric = True
    except (ValueError, TypeError):
        pass

    if not has_ly_numeric:
        try:
            v_au_str = r.get("dist_au")
            if v_au_str not in (None, ""):
                au_val = float(v_au_str)
                total_au += au_val
                has_au_numeric = True
        except (ValueError, TypeError):
            pass
    try:
        v_intra1 = r.get("intra_current_au")
        if v_intra1 not in (None, ""):
            intra1_val = float(v_intra1)
            total_au += intra1_val
            has_au_numeric = True
    except (ValueError, TypeError):
        pass
    try:
        v_intra2 = r.get("intra_target_au")
        if v_intra2 not in (None, ""):
            intra2_val = float(v_intra2)
            total_au += intra2_val
            has_au_numeric = True
    except (ValueError, TypeError):
        pass

    has_parsed = False
    txt = str(r.get("distance") or "")
    try:
        if txt:
            if not has_ly_numeric:
                m_ly = _LY_RE.search(txt)
                if m_ly:
                    parsed_ly = float(m_ly.group(1))
                    total_au += parsed_ly * _LY_TO_AU
                    has_parsed = True
            if not has_au_numeric:
                ms_au = _AU_RE.findall(txt)
                if ms_au:
                    parsed_au = float(ms_au[-1])
                    total_au += parsed_au
                    has_parsed = True
    except (ValueError, TypeError):
        pass

    if has_ly_numeric or has_au_numeric or has_parsed:
        val = total_au
        key = (0.0, -val if descending else val, name)
        return key
    else:
        key = (1.0, 0.0, name)
        return key


def _fuel_sort_key(r: Dict, descending: bool) -> Tuple[float, float, str]:
    name = (r.get("name", "") or "").lower()
    v = r.get("fuel_cost", None)
    try:
        if v is None or v == "—":
            return (1.0, 0.0, name)
        fv = float(v)
    except Exception:
        return (1.0, 0.0, name)
    return (0.0, -fv, name) if descending else (0.0, fv, name)


# -------- Widget (GALAXY) --------

class GalaxySystemList(QWidget):
    """
    Galaxy list (systems). Always a flat list (no grouped Default View).
    Signals mirror SystemLocationList for drop-in compatibility.
    """
    hovered = Signal(int)
    clicked = Signal(int)
    doubleClicked = Signal(int)
    leftView = Signal()
    refreshRequested = Signal()
    anchorMoved = Signal()
    travelHere = Signal(int)

    def __init__(self, categories: List[str], sorts: List[str], title: str):
        super().__init__()
        self.category = QComboBox()
        self.category.addItems(categories)

        self.sort = QComboBox()
        self.sort.addItems(sorts)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)  # Name, Distance, Fuel
        self.tree.setHeaderLabels(["Name", "Distance", "Fuel"])
        self.tree.setMouseTracking(True)                    # for itemEntered
        self.tree.viewport().setMouseTracking(True)         # ensure viewport tracks too
        self.tree.setUniformRowHeights(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setRootIsDecorated(False)

        # Header + sizing
        header = self.tree.header()
        try:
            header.setStretchLastSection(False)
            header.setDefaultSectionSize(160)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)            # Name stretches
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)   # Distance autosize
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)   # Fuel autosize
        except Exception:
            pass

        # Enable click-to-sort on header; hide dropdowns per UX request
        try:
            header.setSortIndicatorShown(True)
            header.setSectionsClickable(True)
            header.sectionClicked.connect(self._on_header_clicked)
        except Exception:
            pass
        try:
            self.category.setVisible(False)  # hide category selector
        except Exception:
            pass
        try:
            self.sort.setVisible(False)      # hide sort dropdown (we drive it via header)
        except Exception:
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        # Title is provided by the dock header; avoid duplicating it inside the widget
        # Removed: category & sort dropdowns from UI
        main_layout.addWidget(self.search)
        main_layout.addWidget(self.tree, 1)

        # Signals
        self.tree.itemEntered.connect(self._on_item_entered)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.search.textChanged.connect(lambda _s: self.refreshRequested.emit())
        self.category.currentIndexChanged.connect(lambda _i: self.refreshRequested.emit())
        self.sort.currentIndexChanged.connect(lambda _i: self.refreshRequested.emit())
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        self.tree.viewport().installEventFilter(self)
        self.tree.verticalScrollBar().valueChanged.connect(lambda _v: self.anchorMoved.emit())
        self.tree.horizontalScrollBar().valueChanged.connect(lambda _v: self.anchorMoved.emit())

    # ----- Context menu -----

    def _show_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return

        val = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            entity_id = int(val)
        except Exception:
            return

        # Identify current player system
        snap = player_status.get_status_snapshot() or {}

        def _to_int_local(x):
            try:
                return int(x)
            except Exception:
                return None

        cur_sys_id = _to_int_local(snap.get("system_id"))

        # In galaxy list, entity_id is NEGATIVE system_id
        is_current_system = (entity_id < 0 and cur_sys_id is not None and -entity_id == cur_sys_id)
        if is_current_system:
            return  # Already here — no travel menu

        menu = QMenu(self)
        travel_action = QAction("Travel to System", self)
        travel_action.triggered.connect(lambda: self.travelHere.emit(entity_id))
        menu.addAction(travel_action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ----- Event plumbing -----

    def eventFilter(self, obj, ev):
        if obj is self.tree.viewport():
            if ev.type() == QEvent.Type.Leave:
                self.leftView.emit()
            elif ev.type() == QEvent.Type.MouseMove:
                it = self.current_hover_item()
                if it:
                    val = it.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(val, int):
                        self.hovered.emit(val)
            elif ev.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
                self.anchorMoved.emit()
        return super().eventFilter(obj, ev)

    def _on_item_entered(self, item: QTreeWidgetItem):
        val = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(val, int):
            self.hovered.emit(val)

    def _on_item_clicked(self, item: QTreeWidgetItem):
        val = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(val, int):
            self.clicked.emit(val)

    def _on_item_double_clicked(self, item: QTreeWidgetItem):
        val = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(val, int):
            self.doubleClicked.emit(val)

    def _on_header_clicked(self, logical_index: int) -> None:
        """
        Header click toggles sorting:
          Name: A–Z ↔ Z–A (robust: no substring ambiguity)
          Distance: ↑ ↔ ↓
          Fuel: ↑ ↔ ↓
        We drive the hidden "sort" combobox so existing sorting/filtering code keeps working.
        """
        try:
            current = (self.sort.currentText() or "").strip()
        except Exception:
            current = ""

        if logical_index == 0:  # Name
            # Avoid substring checks: decide based on exact current value.
            if current in ("Name A–Z", "Name A-Z"):
                next_key = "Name Z–A"
            else:
                # From any other state (incl. Distance/Fuel), go to A–Z first.
                next_key = "Name A–Z"
        elif logical_index == 1:  # Distance
            next_key = "Distance ↓" if "↑" in current else "Distance ↑"
        elif logical_index == 2:  # Fuel
            next_key = "Fuel ↓" if "↑" in current else "Fuel ↑"
        else:
            return

        i = self.sort.findText(next_key)
        if i >= 0:
            self.sort.setCurrentIndex(i)
        else:
            # Fallback in case list variants differ; set text and continue.
            try:
                self.sort.setCurrentText(next_key)
            except Exception:
                pass

        # Update sort indicator
        order = Qt.SortOrder.DescendingOrder if (next_key in ("Name Z–A", "Name Z-A") or "↓" in next_key) else Qt.SortOrder.AscendingOrder
        try:
            self.tree.header().setSortIndicator(logical_index, order)
        except Exception:
            pass

        self.refreshRequested.emit()

    # ----- Utilities -----

    def find_item_by_id(self, entity_id: int) -> Optional[QTreeWidgetItem]:
        """Finds a top-level item by its stored entity ID."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            val = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(val, int) and val == entity_id:
                return item
        return None

    def _apply_row_styling(self, it: QTreeWidgetItem, r: Dict, *, red: QBrush, green: QBrush, yellow: QBrush) -> None:
        # Brushes
        white = QBrush(QColor("white"))

        # ---- Name (system) ----
        # Yellow only for the player's current system; otherwise white.
        if bool(r.get("is_current", False)):
            it.setForeground(0, yellow)
        else:
            it.setForeground(0, white)

        # ---- Distance (jump range) ----
        # Green if we have enough jump range, red otherwise.
        can_jump = bool(r.get("can_reach_jump", False))
        it.setForeground(1, green if can_jump else red)

        # ---- Fuel ----
        # Green if enough fuel, red if not; if unknown/“—”, leave white.
        fuel_val = r.get("fuel_cost", "—")
        if isinstance(fuel_val, (int, float)) and float(fuel_val) > 0:
            can_fuel = bool(r.get("can_reach_fuel", False))
            it.setForeground(2, green if can_fuel else red)
        else:
            it.setForeground(2, white)

    # ----- Icon fallback (GIF-first) -----

    def _default_icon_provider(self, r: Dict) -> Optional[QIcon]:
        """
        If presenter doesn't provide an icon, prefer a GIF-first pixmap (first frame)
        so list thumbnails match the map exactly; fallback to QIcon(path).
        """
        p = r.get("icon_path")
        if isinstance(p, str) and p:
            if p.lower().endswith(".gif") and pm_from_path_or_kind is not None:
                try:
                    pm = pm_from_path_or_kind(p, "star", desired_px=24)
                    if pm is not None and not pm.isNull():
                        return QIcon(pm)
                except Exception:
                    pass
            try:
                return QIcon(p)
            except Exception:
                return None
        return None

    # ----- Population & sorting/filtering -----

    def populate(
        self,
        rows: List[Dict],
        list_font: QFont,
        icon_provider: Optional[Callable[[Dict], Optional[QIcon]]] = None,
    ):
        """Always populate as a flat list."""
        self.tree.clear()
        self.tree.setFont(list_font)
        self.tree.setRootIsDecorated(False)

        red_brush = QBrush(QColor("red"))
        green_brush = QBrush(QColor("green"))
        yellow_brush = QBrush(QColor("yellow"))

        for r in rows:
            rid = _to_int(r.get("id"))
            if rid is None:
                continue
            dist_text = r.get("distance", "—")
            fuel_val = r.get("fuel_cost", "—")
            fuel_text = str(fuel_val) if fuel_val != "—" else "—"

            it = QTreeWidgetItem(self.tree, [r.get("name", "Unknown"), dist_text, fuel_text])
            it.setData(0, Qt.ItemDataRole.UserRole, rid)

            # Icon, with GIF-first fallback if presenter does not supply
            icon = None
            if icon_provider is not None:
                try:
                    icon = icon_provider(r)
                except Exception:
                    icon = None
            if icon is None:
                icon = self._default_icon_provider(r)
            if icon:
                it.setIcon(0, icon)

            self._apply_row_styling(it, r, red=red_brush, green=green_brush, yellow=yellow_brush)

    def filtered_sorted(self, rows_all: List[Dict], _player_pos: Optional[QPointF]) -> List[Dict]:
        # ---- Category filter ----
        cat = (self.category.currentText() or "").strip()
        cat_norm = _norm(cat)
        rows = []
        for r in rows_all:
            if not cat or cat_norm == "all":
                rows.append(r)
                continue
            # Accept "system" / "systems" (and tolerate legacy "star")
            kind_norm = _norm(r.get("kind", "system"))
            if cat_norm in ("system", "systems") and kind_norm in ("system", "star"):
                rows.append(r)
                continue

        # ---- Search filter (name + system_name) ----
        q = self.search.text().strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in (r.get("name", "") or "").lower()
                or q in (r.get("system_name", "") or "").lower()
            ]

        # ---- Sort ----
        sort_key = (self.sort.currentText() or "").strip()

        def _is_desc(k: str) -> bool:
            ks = k.lower()
            return ("↓" in k) or ("down" in ks) or ("desc" in ks)

        # Default View -> stable by name
        if sort_key == "Default View":
            rows.sort(key=lambda r: (r.get("name", "") or "").lower())
            return rows

        if "Name" in sort_key:
            reverse = sort_key.endswith("Z–A") or sort_key.endswith("Z-A")
            rows.sort(key=lambda r: (r.get("name", "") or "").lower(), reverse=reverse)
            return rows

        if sort_key.startswith("Distance"):
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _smart_distance_key(rr, descending=desc))
            return rows

        if sort_key.startswith("Fuel"):
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _fuel_sort_key(rr, descending=desc))
            return rows

        # Fallback: sort by name if an unknown sort shows up
        rows.sort(key=lambda r: (r.get("name", "") or "").lower())
        return rows

    # ----- Anchor utilities for leader line -----

    def anchor_point_for_item(self, overlay: QWidget, item: QTreeWidgetItem) -> QPoint:
        r = self.tree.visualItemRect(item)
        pt_view = r.center()
        pt_view.setX(r.right() - 4)  # near the right edge
        p_view = self.tree.viewport().mapToGlobal(pt_view)
        p_overlay = overlay.mapFromGlobal(p_view)
        return QPoint(
            min(max(0, p_overlay.x()), overlay.width() - 1),
            min(max(0, p_overlay.y()), overlay.height() - 1),
        )

    def current_hover_item(self) -> Optional[QTreeWidgetItem]:
        vp = self.tree.viewport()
        local_pos = vp.mapFromGlobal(QCursor.pos())
        if not vp.rect().contains(local_pos):
            return None
        return self.tree.itemAt(local_pos)

    def cursor_inside_viewport(self) -> bool:
        vp = self.tree.viewport()
        local_pos = vp.mapFromGlobal(QCursor.pos())
        return vp.rect().contains(local_pos)
