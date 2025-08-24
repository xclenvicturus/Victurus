# /ui/widgets/location_list.py

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple
import re

from PySide6.QtCore import QPoint, QEvent, Qt, Signal, QPointF
from PySide6.QtGui import QFont, QIcon, QColor, QBrush, QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
)

# -------- Helpers --------
_LY_TO_AU = 63241.0  # Approximate astronomical units in one light-year

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


_LY_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*ly\b", re.IGNORECASE)
_AU_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*au\b", re.IGNORECASE)

def _extract_ly(r: Dict) -> float:
    """Prefer numeric LY, else parse from 'distance'. Unknown -> inf."""
    # numeric first
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
    # parse from string
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
    # numeric first
    try:
        v = r.get("dist_au")
        if v not in (None, ""):
            return float(v)
    except Exception:
        pass
    # sum legs if present
    total = 0.0
    has_leg = False
    try:
        v = r.get("intra_current_au")
        if v not in (None, ""):
            total += float(v); has_leg = True
    except Exception:
        pass
    try:
        v = r.get("intra_target_au")
        if v not in (None, ""):
            total += float(v); has_leg = True
    except Exception:
        pass
    if has_leg:
        return total
    # parse last AU in the string (handles "XX ly + YY AU")
    try:
        txt = str(r.get("distance") or "")
        ms = _AU_RE.findall(txt)
        if ms:
            return float(ms[-1])
    except Exception:
        pass
    return float("inf")


def _smart_distance_key(r: Dict, descending: bool) -> Tuple[float, float, str]:
    """
    Calculates a distance key using a simple, robust priority system.
    - If any numeric distance fields exist, they are summed and used as the definitive total.
    - If no numeric fields exist, it falls back to parsing the 'distance' string.
    This prevents conflicts and double-counting between numeric and string sources.
    """
    name = (r.get("name", "") or "").lower()
    total_au = 0.0
    has_ly_numeric = False
    has_au_numeric = False

    # --- Step 1: Process all available NUMERIC fields first. ---
    # We sum all numeric components we can find.
    
    # LY numeric components
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

    # AU numeric components
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

    # --- Step 2: Fallback parsing for missing parts ---
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

    # --- Step 3: If we have any distance (numeric or parsed), use it; else unknown ---
    if has_ly_numeric or has_au_numeric or has_parsed:
        val = total_au
        key = (0.0, -val if descending else val, name)
        return key
    else:
        # No string to parse or no matches, it's an unknown distance.
        key = (1.0, 0.0, name)
        return key

def _fuel_sort_key(r: Dict, descending: bool) -> Tuple[float, float, str]:
    """Fuel key that keeps unknown at bottom in both directions."""
    name = (r.get("name", "") or "").lower()
    v = r.get("fuel_cost", None)
    try:
        if v is None or v == "—":
            return (1.0, 0.0, name)
        fv = float(v)
    except Exception:
        return (1.0, 0.0, name)
    return (0.0, -fv, name) if descending else (0.0, fv, name)

# -------- Widget --------

class LocationList(QWidget):
    """
    Reusable right-side panel with:
    - category dropdown
    - sort dropdown
    - live search box
    - list view with hover/click/double-click signals
    - distance and fuel columns (Jump column removed)
    - right-click context menu with "Travel to"
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        main_layout.addWidget(QLabel(title))
        main_layout.addWidget(self.category)
        main_layout.addWidget(self.sort)
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
        self.tree.verticalScrollBar().valueChanged.connect(self.anchorMoved.emit)
        self.tree.horizontalScrollBar().valueChanged.connect(self.anchorMoved.emit)

    # ----- Context menu -----

    def _show_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return
        entity_id = int(item.data(0, Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        travel_action = QAction("Travel to", self)
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
                    self.hovered.emit(int(it.data(0, Qt.ItemDataRole.UserRole)))
            elif ev.type() in (QEvent.Type.Resize, QEvent.Type.Paint):
                self.anchorMoved.emit()
        return super().eventFilter(obj, ev)

    def _on_item_entered(self, item: QTreeWidgetItem):
        self.hovered.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def _on_item_clicked(self, item: QTreeWidgetItem):
        self.clicked.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def _on_item_double_clicked(self, item: QTreeWidgetItem):
        self.doubleClicked.emit(int(item.data(0, Qt.ItemDataRole.UserRole)))

    # ----- Utilities -----

    def find_item_by_id(self, entity_id: int) -> Optional[QTreeWidgetItem]:
        """Finds a top-level item in the tree by its stored entity ID."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data == entity_id:
                return item
        return None

    # ----- Population & styling -----

    def populate(
        self,
        rows: List[Dict],
        list_font: QFont,
        icon_provider: Optional[Callable[[Dict], Optional[QIcon]]] = None,
    ):
        self.tree.clear()
        self.tree.setFont(list_font)

        red_brush    = QBrush(QColor("red"))
        green_brush  = QBrush(QColor("green"))
        yellow_brush = QBrush(QColor("yellow"))

        for r in rows:
            dist_text = r.get("distance", "—")
            fuel_val = r.get("fuel_cost", "—")
            fuel_text = str(fuel_val) if fuel_val != "—" else "—"

            it = QTreeWidgetItem(self.tree, [r.get("name", "Unknown"), dist_text, fuel_text])
            it.setData(0, Qt.ItemDataRole.UserRole, r.get("id"))

            if icon_provider:
                icon = icon_provider(r)
                if icon:
                    it.setIcon(0, icon)

            # --- Coloring rules ---
            is_current = bool(r.get("is_current", False))
            can_reach = r.get("can_reach", True)
            can_reach_jump = r.get("can_reach_jump", True)
            can_reach_fuel = r.get("can_reach_fuel", True)

            # Name column: current rows are YELLOW; unreachable rows turn red.
            if is_current:
                it.setForeground(0, yellow_brush)
            elif not can_reach:
                it.setForeground(0, red_brush)

            # Distance column (index 1): green if jumpable, red if too far.
            try:
                jump_val = 0.0
                if "dist_ly" in r and r["dist_ly"] not in (None, ""):
                    jump_val = float(r["dist_ly"])
                elif "jump_dist" in r and r["jump_dist"] not in (None, ""):
                    jump_val = float(r["jump_dist"])
            except Exception:
                jump_val = 0.0

            if jump_val > 0.0:
                it.setForeground(1, green_brush if can_reach_jump else red_brush)
            else:
                it.setForeground(1, green_brush)

            # Fuel column (index 2): green if enough fuel for a positive cost, red if not.
            try:
                if isinstance(fuel_val, (int, float)) and float(fuel_val) > 0:
                    it.setForeground(2, green_brush if can_reach_fuel else red_brush)
            except Exception:
                pass

    # ----- Filtering & sorting -----

    def filtered_sorted(self, rows_all: List[Dict], player_pos: Optional[QPointF]) -> List[Dict]:
        # ---- Category filter ----
        cat = self.category.currentText()
        cat_norm = _norm(cat)
        rows = []
        for r in rows_all:
            if not cat or cat_norm == _norm("All") or cat == "All":
                rows.append(r)
                continue
            kind_norm = _norm(r.get("kind", ""))
            if kind_norm.startswith(cat_norm):
                rows.append(r)
                continue
            if cat_norm == "warpgate" and kind_norm in ("warpgate", "gate"):
                rows.append(r)
                continue
            if cat_norm == "system" and _norm(r.get("kind", "")) == "system":
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
        sort_key = self.sort.currentText()

        def _is_desc(k: str) -> bool:
            ks = k.lower()
            return ("↓" in k) or ("down" in ks) or ("desc" in ks)

        if "Name" in sort_key:
            reverse = sort_key.endswith("Z–A") or sort_key.endswith("Z-A")
            rows.sort(key=lambda r: (r.get("name", "") or "").lower(), reverse=reverse)

        elif sort_key.startswith("Distance"):
            # Two labels only: "Distance ↑" / "Distance ↓"
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _smart_distance_key(rr, descending=desc))

        elif sort_key.startswith("Fuel"):
            # "Fuel ↑" / "Fuel ↓"
            desc = _is_desc(sort_key)
            rows.sort(key=lambda rr: _fuel_sort_key(rr, descending=desc))

        return rows

    # ----- Anchor utilities for leader line -----

    def anchor_point_for_item(self, overlay: QWidget, item: QTreeWidgetItem) -> QPoint:
        r = self.tree.visualItemRect(item)
        pt_view = r.center()
        pt_view.setX(r.right())
        p_global = self.tree.viewport().mapToGlobal(pt_view)
        p_overlay = overlay.mapFromGlobal(p_global)
        return QPoint(
            min(max(0, p_overlay.x()), overlay.width() - 1),
            min(max(0, p_overlay.y()), overlay.height() - 1),
        )

    def current_hover_item(self) -> Optional[QTreeWidgetItem]:
        pos = self.tree.viewport().mapFromGlobal(self.cursor().pos())
        return self.tree.itemAt(pos)