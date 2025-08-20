from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import math
import sqlite3
from .. import world

@dataclass
class RouteStep:
    x1: float; y1: float
    x2: float; y2: float
    distance: float

@dataclass
class RoutePlan:
    origin_station_id: int
    dest_station_id: int
    steps: List[RouteStep]
    total_distance: float

class RouteController:
    """Creates linear routes subdivided into dots for encounter checks."""
    def __init__(self, conn: sqlite3.Connection, dot_spacing: float = 6.0):
        self.conn = conn
        self.dot_spacing = max(1.0, float(dot_spacing))

    def plan(self, origin_station_id: int, dest_station_id: int) -> RoutePlan:
        s1_sys = world.system_of_station(self.conn, origin_station_id)
        s2_sys = world.system_of_station(self.conn, dest_station_id)
        # We'll use system coordinates as endpoints for now
        sys1 = self.conn.execute("SELECT * FROM systems WHERE id=?", (s1_sys,)).fetchone()
        sys2 = self.conn.execute("SELECT * FROM systems WHERE id=?", (s2_sys,)).fetchone()
        x1, y1 = float(sys1["x"]), float(sys1["y"])
        x2, y2 = float(sys2["x"]), float(sys2["y"])
        dx, dy = (x2 - x1), (y2 - y1)
        dist = math.hypot(dx, dy)
        if dist == 0:
            return RoutePlan(origin_station_id, dest_station_id, [], 0.0)
        steps: List[RouteStep] = []
        n_dots = max(1, int(math.ceil(dist / self.dot_spacing)))
        for i in range(n_dots):
            t1 = i / n_dots
            t2 = (i + 1) / n_dots
            ax, ay = (x1 + dx * t1), (y1 + dy * t1)
            bx, by = (x1 + dx * t2), (y1 + dy * t2)
            steps.append(RouteStep(ax, ay, bx, by, dist / n_dots))
        return RoutePlan(origin_station_id, dest_station_id, steps, dist)
