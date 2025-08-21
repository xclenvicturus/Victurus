from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import QWidget, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem

from data import db


GREEN = QColor("#22c55e")  # tailwind's green-500-ish


def _item_matches_location(item_text: str, target_name: str) -> bool:
    """
    Heuristics if the item's text corresponds to the location name.
    Handles cases where the list shows "Sys-01 Planet 1" or just "Planet 1".
    """
    it = (item_text or "").strip()
    tn = (target_name or "").strip()
    if not it or not tn:
        return False
    if it == tn:
        return True
    # often lists prefix with system, so allow suffix match
    if it.endswith(tn):
        return True
    return False


def _mark_listwidget(listw: QListWidget, target_loc_id: int, target_loc_name: str) -> None:
    """
    Iterate items in a QListWidget and set green text on the item representing target_loc_id/name.
    Items are expected (optionally) to store location_id at Qt.UserRole.
    """
    default_color = listw.palette().color(QPalette.ColorRole.Text)
    for i in range(listw.count()):
        it: QListWidgetItem = listw.item(i)
        loc_id = it.data(Qt.ItemDataRole.UserRole)
        text = it.text()
        is_match = (loc_id == target_loc_id) or _item_matches_location(text, target_loc_name)
        it.setForeground(QBrush(GREEN if is_match else default_color))


def _walk_tree_items(root: Optional[QTreeWidgetItem]):
    """
    Depth-first traversal over a QTreeWidgetItem subtree.
    Accepts Optional and no-ops if root is None for type-checker friendliness.
    """
    if root is None:
        return
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        for i in range(n.childCount() - 1, -1, -1):
            stack.append(n.child(i))


def _mark_treewidget(tw: QTreeWidget, target_loc_id: int, target_loc_name: str) -> None:
    """
    Iterate items in a QTreeWidget and set green text on the item representing target_loc_id/name.
    Items are expected (optionally) to store location_id at Qt.UserRole (column 0).
    """
    default_color = tw.palette().color(QPalette.ColorRole.Text)
    for r in range(tw.topLevelItemCount()):
        root_item = tw.topLevelItem(r)
        for it in _walk_tree_items(root_item):
            if it is None:
                continue
            loc_id = it.data(0, Qt.ItemDataRole.UserRole)
            text = it.text(0)
            is_match = (loc_id == target_loc_id) or _item_matches_location(text, target_loc_name)
            it.setForeground(0, QBrush(GREEN if is_match else default_color))


def apply_green_text_to_current_location(root_widget: QWidget) -> None:
    """
    Color the text green for the player's current location in all list/tree widgets
    under `root_widget` (typically the MapView). Safe to call repeatedly.
    """
    p = db.get_player_full()
    loc_id = p.get("current_location_id")
    if not loc_id:
        return
    loc = db.get_location(int(loc_id))
    loc_name = loc.get("name", "")

    for listw in root_widget.findChildren(QListWidget):
        _mark_listwidget(listw, int(loc_id), loc_name)

    for treew in root_widget.findChildren(QTreeWidget):
        _mark_treewidget(treew, int(loc_id), loc_name)
