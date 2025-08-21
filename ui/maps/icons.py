"""
ui/maps/icons.py
File-first icons with procedural fallbacks, for both lists and map items.

Conventions:
- System star icons: stored in DB as systems.star_icon_path (e.g., assets/stars/t01.svg)
- Generic fallbacks: assets/icons/star.svg, planet.svg, station.svg
- Per-location icons (planets/stations) come from DB (locations.icon_path)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF, QBrush

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"
ICONS_DIR = ASSETS_ROOT / "icons"  # for generic fallbacks


# ---------- Low-level loaders ----------
def _icon_from_path(path: Optional[str]) -> Optional[QIcon]:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (ASSETS_ROOT.parent / p).resolve()
    if p.exists():
        return QIcon(str(p))
    return None


def _icon_generic(name: str) -> Optional[QIcon]:
    p = ICONS_DIR / f"{name}.svg"
    if p.exists():
        return QIcon(str(p))
    return None


# ---------- Public: List icons (QIcon) ----------
def icon_from_path_or_kind(icon_path: Optional[str], kind: Optional[str]) -> QIcon:
    """Load an icon for list items; falls back by kind (planet/station/star) or to procedural."""
    ico = _icon_from_path(icon_path)
    if ico:
        return ico
    k = (kind or "").lower()
    if k == "planet":
        return _icon_generic("planet") or _proc_planet_icon()
    if k == "station":
        return _icon_generic("station") or _proc_station_icon()
    if k == "star":
        return _icon_generic("star") or _proc_star_icon()
    # default:
    return _icon_generic("planet") or _proc_planet_icon()


# ---------- Public: Map pixmaps (QPixmap) ----------
def pm_star_from_path(star_icon_path: Optional[str], size_px: int) -> QPixmap:
    """Pixmap for a star/system on the map."""
    ico = _icon_from_path(star_icon_path) or _icon_generic("star")
    if ico:
        return ico.pixmap(QSize(size_px, size_px))
    return _proc_star_pixmap(size_px)


def pm_from_path_or_kind(icon_path: Optional[str], kind: Optional[str], size_px: int) -> QPixmap:
    """Pixmap for a location (planet/station) on the map."""
    ico = _icon_from_path(icon_path)
    if ico:
        return ico.pixmap(QSize(size_px, size_px))
    k = (kind or "").lower()
    if k == "planet":
        g = _icon_generic("planet")
        return g.pixmap(QSize(size_px, size_px)) if g else _proc_planet_pixmap(size_px)
    if k == "station":
        g = _icon_generic("station")
        return g.pixmap(QSize(size_px, size_px)) if g else _proc_station_pixmap(size_px)
    if k == "star":
        g = _icon_generic("star")
        return g.pixmap(QSize(size_px, size_px)) if g else _proc_star_pixmap(size_px)
    # default:
    g = _icon_generic("planet")
    return g.pixmap(QSize(size_px, size_px)) if g else _proc_planet_pixmap(size_px)


# ---------- Procedural fallbacks (QIcon + QPixmap variants) ----------
def _proc_star_icon() -> QIcon:
    return QIcon(_proc_star_pixmap(96))


def _proc_planet_icon() -> QIcon:
    return QIcon(_proc_planet_pixmap(96))


def _proc_station_icon() -> QIcon:
    return QIcon(_proc_station_pixmap(96))


def _proc_star_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    thick = max(2, size // 16)
    p.setPen(QPen(QColor("#fff176"), thick))
    p.setBrush(QBrush(QColor("#ffd600")))
    d = int(size * 0.62)
    off = (size - d) // 2
    p.drawEllipse(off, off, d, d)
    p.end()
    return pm


def _proc_planet_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    thick = max(2, size // 16)
    p.setPen(QPen(QColor("#ffd08a"), thick))
    p.setBrush(QBrush(QColor("#ffb74d")))
    d = int(size * 0.68)
    off = (size - d) // 2
    p.drawEllipse(off, off, d, d)
    p.end()
    return pm


def _proc_station_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    thick = max(2, size // 16)
    p.setPen(QPen(QColor("#c5e1a5"), thick))
    p.setBrush(QBrush(QColor("#7cb342")))
    s = int(size * 0.62)
    cx = cy = size // 2
    half = s // 2
    poly = QPolygonF([QPointF(cx, cy - half), QPointF(cx + half, cy), QPointF(cx, cy + half), QPointF(cx - half, cy)])
    p.drawPolygon(poly)
    p.end()
    return pm
