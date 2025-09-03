# /ui/widgets/system_location_list.py

"""
System Location List Widget

Provides filterable, sortable lists of system locations (planets, stations, etc.)
with search functionality, category filtering, and integration with the system map display.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple
import re

from game import player_status
from pathlib import Path

from PySide6.QtCore import QPoint, QEvent, Qt, Signal, QPointF
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
    QFileDialog,
)

from ui.error_utils import warn_on_exception

# Try to use the GIF-first pixmap helper if available (keeps thumbnails in sync with map GIFs)
try:
    from ui.maps.icons import pm_from_path_or_kind  # type: ignore
except Exception:  # pragma: no cover
    pm_from_path_or_kind = None  # type: ignore

try:
    from save.icon_paths import persist_location_icon, persist_system_icon
except Exception:  # pragma: no cover
    persist_location_icon = None  # type: ignore
    persist_system_icon = None  # type: ignore

from settings import system_config as cfg

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
    name = (r.get("name") or r.get("location_name") or "").lower()
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
    name = (r.get("name") or r.get("location_name") or "").lower()
    v = r.get("fuel_cost", None)
    try:
        if v is None or v == "—":
            return (1.0, 0.0, name)
        fv = float(v)
    except Exception:
        return (1.0, 0.0, name)
    return (0.0, -fv, name) if descending else (0.0, fv, name)


# -------- Widget (SYSTEM) --------

class SystemLocationList(QWidget):
    """
    System list. Supports grouped **Default View** (planets as parents, stations/moons as children),
    and flat list for other sorts/filters/searches.
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
        self.tree.setMouseTracking(True)
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

        # Enable click-to-sort on header; hide sort dropdown per UX request
        try:
            header.setSortIndicatorShown(True)
            header.setSectionsClickable(True)
            header.sectionClicked.connect(self._on_header_clicked)
        except Exception:
            pass
        try:
            self.sort.setVisible(False)      # remove sort dropdown
        except Exception:
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        # Title is provided by the dock header; avoid duplicating it inside the widget
        main_layout.addWidget(self.category)
        # Removed: sort dropdown from UI
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

        # Identify current player position
        snap = player_status.get_status_snapshot() or {}

        def _to_int_local(x):
            try:
                return int(x)
            except Exception:
                return None

        cur_loc_id = _to_int_local(snap.get("location_id"))

        is_current_loc = (entity_id >= 0 and cur_loc_id is not None and entity_id == cur_loc_id)

        menu = QMenu(self)
        # Only "Travel Here" for actual locations
        if entity_id >= 0 and not is_current_loc:
            act_travel_loc = QAction("Travel Here", self)
            act_travel_loc.triggered.connect(lambda: self.travelHere.emit(entity_id))
            menu.addAction(act_travel_loc)

        if menu.actions():
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

    @warn_on_exception("System location header click")
    def _on_header_clicked(self, logical_index: int) -> None:
        """
        Header click toggles sorting:
          Name: Default View → A–Z → Z–A → Default View ...
          Distance: ↑ ↔ ↓
          Fuel: ↑ ↔ ↓
        We drive the hidden "sort" combobox so existing logic keeps working.
        """
        try:
            current = (self.sort.currentText() or "").strip()
        except Exception:
            current = ""
        if logical_index == 0:
            # Cycle among Default View, Name A–Z, Name Z–A
            order = ["Default View", "Name A–Z", "Name Z–A"]
            try:
                idx = order.index(current)
            except ValueError:
                idx = 0
            next_key = order[(idx + 1) % len(order)]
        elif logical_index == 1:
            next_key = "Distance ↓" if "↑" in current else "Distance ↑"
        elif logical_index == 2:
            next_key = "Fuel ↓" if "↑" in current else "Fuel ↑"
        else:
            return
        i = self.sort.findText(next_key)
        if i >= 0:
            self.sort.setCurrentIndex(i)
        else:
            try:
                self.sort.setCurrentText(next_key)
            except Exception:
                pass
        # Update sort indicator (Name Default View shows Ascending)
        if logical_index == 0 and next_key == "Default View":
            order_qt = Qt.SortOrder.AscendingOrder
        else:
            order_qt = Qt.SortOrder.DescendingOrder if ("↓" in next_key or "Z–A" in next_key or "Z-A" in next_key) else Qt.SortOrder.AscendingOrder
        try:
            self.tree.header().setSortIndicator(logical_index, order_qt)
        except Exception:
            pass
        self.refreshRequested.emit()

    # ----- Utilities -----

    def _kind_of(self, r: Dict) -> str:
        """Determine kind strictly from explicit fields; never infer from name."""
        k = str(
            r.get("location_type")
            or r.get("kind")
            or r.get("type")
            or ""
        ).lower().strip()
        if k in ("warp gate", "warp_gate"):
            k = "warpgate"
        return k

    def _display_name(self, r: Dict) -> str:
        """Append ' (Star)' for explicit star rows; prefer location_name if present."""
        name = r.get("name") or r.get("location_name") or "Unknown"
        if self._kind_of(r) == "star" and "(star)" not in name.lower():
            name = f"{name} (Star)"
        return name

    def find_item_by_id(self, entity_id: int) -> Optional[QTreeWidgetItem]:
        """Finds an item by its stored entity ID."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            val = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(val, int) and val == entity_id:
                return item
        return None

    def _apply_row_styling(self, it: QTreeWidgetItem, r: Dict, *, red: QBrush, green: QBrush, yellow: QBrush) -> None:
        white = QBrush(QColor("white"))

        # ---- Name ----
        try:
            kind = str(r.get("kind") or r.get("location_type") or "").lower().strip()
        except Exception:
            kind = ""
        if kind == "star":
            it.setForeground(0, QBrush(QColor("lightblue")))
        elif bool(r.get("is_current", False)):
            it.setForeground(0, yellow)
        else:
            it.setForeground(0, white)

        # ---- Distance ----
        can_jump = bool(r.get("can_reach_jump", False))
        it.setForeground(1, green if can_jump else red)

        # ---- Fuel ----
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
        kind = r.get("kind") or r.get("location_type") or ""
        if isinstance(p, str) and p:
            if p.lower().endswith(".gif") and pm_from_path_or_kind is not None:
                try:
                    pm = pm_from_path_or_kind(p, kind, desired_px=24)
                    if pm is not None and not pm.isNull():
                        return QIcon(pm)
                except Exception:
                    pass
            try:
                return QIcon(p)
            except Exception:
                return None
        return None

    # ----- Population (grouped vs flat handled by sort mode) -----

    def populate(
        self,
        rows: List[Dict],
        list_font: QFont,
        icon_provider: Optional[Callable[[Dict], Optional[QIcon]]] = None,
    ):
        self.tree.clear()
        self.tree.setFont(list_font)

        # Remove any "system" entries entirely from the System list
        rows = [r for r in rows if self._kind_of(r) != "system"]

        red_brush = QBrush(QColor("red"))
        green_brush = QBrush(QColor("green"))
        yellow_brush = QBrush(QColor("yellow"))

        # Grouped default view?
        sort_text = self.sort.currentText()
        grouped = (sort_text in ("Default View",))

        self.tree.setRootIsDecorated(grouped)

        # Helper to apply icon from provider with GIF-first fallback
        def _apply_icon(it: QTreeWidgetItem, row: Dict) -> None:
            icon: Optional[QIcon] = None
            if icon_provider is not None:
                try:
                    icon = icon_provider(row)
                except Exception:
                    icon = None
            if icon is None:
                icon = self._default_icon_provider(row)
            if icon:
                it.setIcon(0, icon)

        if not grouped:
            # Flat list — skip 'system' rows; label star with '(star)'
            for r in rows:
                rid = _to_int(r.get("id") or r.get("location_id"))
                if rid is None:
                    continue
                dist_text = r.get("distance", "—")
                fuel_val = r.get("fuel_cost", "—")
                fuel_text = str(fuel_val) if fuel_val != "—" else "—"
                disp = self._display_name(r)

                it = QTreeWidgetItem(self.tree, [disp, dist_text, fuel_text])
                # Use negative system-id for star entries to support leader line
                if self._kind_of(r) == "star":
                    sys_id = _to_int(r.get("system_id") or r.get("systemid"))
                    it.setData(0, Qt.ItemDataRole.UserRole, -int(sys_id) if sys_id is not None else rid)
                else:
                    it.setData(0, Qt.ItemDataRole.UserRole, rid)

                _apply_icon(it, r)
                self._apply_row_styling(it, r, red=red_brush, green=green_brush, yellow=yellow_brush)
            return

        # Grouped (Default View): STAR first, planets with children, orphans, then WARP GATE(s) last
        planets: List[Dict] = []
        star: Optional[Dict] = None
        warpgates: List[Dict] = []
        children_of: Dict[int, List[Dict]] = {}
        used_child_ids: set[int] = set()

        # Pass 1: classify and collect
        for r in rows:
            rid = _to_int(r.get("id") or r.get("location_id"))
            if rid is None:
                continue
            k = self._kind_of(r)
            if k == "planet":
                planets.append(r)
            elif k == "star":
                if star is None:
                    star = r
            elif k == "warpgate":
                warpgates.append(r)
            else:
                parent_id = r.get("parent_location_id")
                if parent_id is not None:
                    try:
                        parent_id = int(parent_id)
                        children_of.setdefault(parent_id, []).append(r)
                    except Exception:
                        pass

        # 1) Star row (always first when present) — display with "(star)"
        if star is not None:
            rid = _to_int(star.get("id") or star.get("location_id"))
            if rid is not None:
                dist_text = star.get("distance", "—")
                fuel_val = star.get("fuel_cost", "—")
                fuel_text = str(fuel_val) if fuel_val != "—" else "—"
                disp = self._display_name(star)
                star_it = QTreeWidgetItem(self.tree, [disp, dist_text, fuel_text])
                # For star row, store negative system-id to enable leader line/system-centric behaviors
                sys_id = _to_int(star.get("system_id") or star.get("systemid"))
                star_entity_id = -int(sys_id) if sys_id is not None else rid
                star_it.setData(0, Qt.ItemDataRole.UserRole, star_entity_id)
                _apply_icon(star_it, star)
                self._apply_row_styling(star_it, star, red=red_brush, green=green_brush, yellow=yellow_brush)
                star_it.setExpanded(True)

        # 2) Planet heads (alphabetical)
        for r in sorted(planets, key=lambda rr: (rr.get("name") or rr.get("location_name") or "").lower()):
            rid = _to_int(r.get("id") or r.get("location_id"))
            if rid is None:
                continue

            dist_text = r.get("distance", "—")
            fuel_val = r.get("fuel_cost", "—")
            fuel_text = str(fuel_val) if fuel_val != "—" else "—"

            planet_it = QTreeWidgetItem(self.tree, [(r.get("name") or r.get("location_name") or "Unknown"), dist_text, fuel_text])
            planet_it.setData(0, Qt.ItemDataRole.UserRole, rid)
            _apply_icon(planet_it, r)
            self._apply_row_styling(planet_it, r, red=red_brush, green=green_brush, yellow=yellow_brush)

            # Order children: stations first, then moons, then others
            def _child_sort_key(rr: Dict) -> Tuple[int, str]:
                kk = self._kind_of(rr)
                rank = 0 if kk == "station" else (1 if kk == "moon" else 2)
                return (rank, (rr.get("name") or rr.get("location_name") or "").lower())

            # Attach children
            kids = sorted(children_of.get(rid, []), key=_child_sort_key)

            for ch in kids:
                cid = _to_int(ch.get("id") or ch.get("location_id"))
                if cid is None:
                    continue
                used_child_ids.add(cid)

                c_dist = ch.get("distance", "—")
                c_fuel_val = ch.get("fuel_cost", "—")
                c_fuel = str(c_fuel_val) if c_fuel_val != "—" else "—"

                child_it = QTreeWidgetItem(planet_it, [(ch.get("name") or ch.get("location_name") or "Unknown"), c_dist, c_fuel])
                child_it.setData(0, Qt.ItemDataRole.UserRole, cid)
                _apply_icon(child_it, ch)
                self._apply_row_styling(child_it, ch, red=red_brush, green=green_brush, yellow=yellow_brush)

            planet_it.setExpanded(True)

        # 3) Any remaining items that didn't get placed (e.g. stations/moons orphaned) — never include 'system'
        for r in rows:
            rid = _to_int(r.get("id") or r.get("location_id"))
            if rid is None:
                continue
            if rid in used_child_ids:
                continue
            k = self._kind_of(r)
            if k in ("planet", "star", "warpgate"):
                # already added (or will be added for warpgate below)
                continue

            dist_text = r.get("distance", "—")
            fuel_val = r.get("fuel_cost", "—")
            fuel_text = str(fuel_val) if fuel_val != "—" else "—"

            it = QTreeWidgetItem(self.tree, [(r.get("name") or r.get("location_name") or "Unknown"), dist_text, fuel_text])
            it.setData(0, Qt.ItemDataRole.UserRole, rid)
            _apply_icon(it, r)
            self._apply_row_styling(it, r, red=red_brush, green=green_brush, yellow=yellow_brush)

        # 4) Warpgate(s) always last (alphabetical)
        if warpgates:
            for wg in sorted(warpgates, key=lambda rr: (rr.get("name") or rr.get("location_name") or "").lower()):
                wid = _to_int(wg.get("id") or wg.get("location_id"))
                if wid is None:
                    continue
                w_dist = wg.get("distance", "—")
                w_fuel_val = wg.get("fuel_cost", "—")
                w_fuel = str(w_fuel_val) if w_fuel_val != "—" else "—"
                wg_it = QTreeWidgetItem(self.tree, [(wg.get("name") or wg.get("location_name") or "Unknown"), w_dist, w_fuel])
                wg_it.setData(0, Qt.ItemDataRole.UserRole, wid)
                _apply_icon(wg_it, wg)
                self._apply_row_styling(wg_it, wg, red=red_brush, green=green_brush, yellow=yellow_brush)

    # ----- Filtering & sorting -----

    def filtered_sorted(self, rows_all: List[Dict], player_pos: Optional[QPointF]) -> List[Dict]:
        # Remove any "system" entries entirely
        rows_all = [r for r in rows_all if self._kind_of(r) != "system"]

        # ---- Category filter ----
        cat = self.category.currentText()
        cat_norm = _norm(cat)
        rows: List[Dict] = []
        for r in rows_all:
            if not cat or cat_norm == _norm("All") or cat == "All":
                rows.append(r)
                continue
            kind_norm = _norm(self._kind_of(r))
            if kind_norm.startswith(cat_norm):
                rows.append(r)
                continue
            if cat_norm == "warpgate" and kind_norm in ("warpgate", "gate"):
                rows.append(r)
                continue

        # ---- Search filter (name + system_name + location_name) ----
        q = self.search.text().strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in (r.get("name") or r.get("location_name") or "").lower()
                or q in (r.get("system_name", "") or "").lower()
            ]

        # ---- Sort ----
        sort_key = self.sort.currentText()

        def _is_desc(k: str) -> bool:
            ks = k.lower()
            return ("↓" in k) or ("down" in ks) or ("desc" in ks)

        if sort_key in ("Default View",):
            # Grouping happens in populate(); just return a stable order for headings
            rows.sort(key=lambda r: ((r.get("name") or r.get("location_name") or "")).lower())
            return rows

        if "Name" in sort_key:
            reverse = sort_key.endswith("Z–A") or sort_key.endswith("Z-A")
            rows.sort(key=lambda r: ((r.get("name") or r.get("location_name") or "")).lower(), reverse=reverse)

        elif sort_key.startswith("Distance"):
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _smart_distance_key(rr, descending=desc))

        elif sort_key.startswith("Fuel"):
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _fuel_sort_key(rr, descending=desc))

        return rows

    # ----- Anchor utilities for leader line -----

    def anchor_point_for_item(self, overlay: QWidget, item: QTreeWidgetItem) -> QPoint:
        r = self.tree.visualItemRect(item)
        pt_view = r.center()
        pt_view.setX(r.right() - 4)
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
