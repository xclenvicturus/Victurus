# engine/ui/map_window.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import sqlite3
from typing import Optional, Tuple, List, Dict, Any


def _has_col(conn: sqlite3.Connection, table: str, col: str) -> bool:
    try:
        info = conn.execute(f"PRAGMA table_info({table});").fetchall()
        return any(r[1] == col for r in info)
    except Exception:
        return False


class MapWindow(tk.Toplevel):
    """
    Galaxy map window.

    - Left-drag to pan.
    - Mouse wheel (or Button-4/5 on Linux) to zoom, focusing around the mouse.
    - Right-click a station to open the travel menu.
      The menu shows 🟢/🔴 next to destinations depending on jump range & fuel.
    - If the content DB has no `links` table, we build a fallback graph in memory
      by linking stations within the same system.
    """

    def __init__(
        self,
        root: tk.Misc,
        conn: sqlite3.Connection,
        bus,
        travel,
        wsm,
        on_close=None,
    ):
        super().__init__(root)
        self.title("Galaxy Map")
        self.conn = conn
        self.bus = bus
        self.travel = travel
        self.wsm = wsm
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.geometry("900x600")

        self.canvas = tk.Canvas(self, bg="#0d0f12", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Transform
        self.scale = 1.0
        self.offset = [0.0, 0.0]
        self._drag_start: Optional[Tuple[int, int]] = None

        # Data
        self._stations = self._load_stations()
        self._links = self._load_links()  # list of (a_id, b_id, distance)

        # Bindings
        # Left mouse to drag
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)

        # Zoom (Windows)
        self.canvas.bind("<MouseWheel>", self._zoom_windows)
        # Zoom (Linux)
        self.canvas.bind("<Button-4>", self._zoom_linux_up)
        self.canvas.bind("<Button-5>", self._zoom_linux_down)

        # Right-click for travel menu
        self.canvas.bind("<Button-3>", self._open_travel_menu)

        self._draw()

    # ---------- lifecycle ----------

    def _close(self):
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()

    # ---------- data loading ----------

    def _load_stations(self) -> List[Dict[str, Any]]:
        """
        Loads stations. If your content provides real coordinates, add them as columns
        (e.g., s.x, s.y) and use them here. We generate a simple grid if none exist.
        """
        rows = self.conn.execute("""
            SELECT
                s.id,
                s.name,
                p.id   AS planet_id,
                p.name AS planet,
                sys.id AS system_id,
                sys.name AS system
            FROM stations s
            JOIN planets p ON p.id = s.planet_id
            JOIN systems sys ON sys.id = p.system_id
            ORDER BY sys.name, p.name, s.name
        """).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                "id":        int(r["id"]),
                "name":      str(r["name"]),
                "planet_id": int(r["planet_id"]),
                "planet":    str(r["planet"]),
                "system_id": int(r["system_id"]),
                "system":    str(r["system"]),
            })

        # Simple layout if you don't have map coords in DB
        # (Feel free to replace with real coords from DB.)
        x0, y0 = 80, 80
        for i, st in enumerate(out):
            st["x"] = (i % 8) * 120 + x0
            st["y"] = (i // 8) * 120 + y0

        return out

    def _fallback_links(self) -> List[Tuple[int, int, int]]:
        """
        Build a simple connected graph inside each system:
        - Sort stations by (planet, name) and chain them with distances.
        - Distances are heuristic (same planet shorter, different planet longer).
        """
        links: List[Tuple[int, int, int]] = []

        # group by system
        by_sys: Dict[int, List[Dict[str, Any]]] = {}
        for s in self._stations:
            by_sys.setdefault(s["system_id"], []).append(s)

        for sys_id, sts in by_sys.items():
            # Sort for stable chain
            sts.sort(key=lambda s: (s["planet"], s["name"]))
            for i in range(len(sts) - 1):
                a = sts[i]
                b = sts[i + 1]
                base = 4 if a["planet_id"] == b["planet_id"] else 8
                links.append((a["id"], b["id"], base))

        return links

    def _load_links(self) -> List[Tuple[int, int, int]]:
        """
        Load links from DB if present. Expected schema:
          links(a INTEGER, b INTEGER, distance INTEGER DEFAULT 5)

        If table is missing, we create a fallback set of links in memory.
        """
        try:
            # Short-circuit if table missing
            has_links = bool(self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='links';"
            ).fetchone())
            if not has_links:
                return self._fallback_links()

            has_distance = _has_col(self.conn, "links", "distance")
            sql = "SELECT a, b{} FROM links".format(", distance" if has_distance else "")
            rows = self.conn.execute(sql).fetchall()
            out: List[Tuple[int, int, int]] = []
            for r in rows:
                a = int(r["a"]); b = int(r["b"])
                d = int(r["distance"]) if has_distance and r["distance"] is not None else 5
                out.append((a, b, max(1, d)))
            return out
        except sqlite3.OperationalError:
            # Any failure -> fallback
            return self._fallback_links()

    # ---------- transforms ----------

    def _to_screen(self, x: float, y: float) -> Tuple[float, float]:
        return (x * self.scale + self.offset[0], y * self.scale + self.offset[1])

    def _from_screen(self, sx: float, sy: float) -> Tuple[float, float]:
        return ((sx - self.offset[0]) / self.scale, (sy - self.offset[1]) / self.scale)

    # ---------- drawing ----------

    def _draw(self):
        self.canvas.delete("all")

        # draw links
        for a, b, _d in self._links:
            sa = next((s for s in self._stations if s["id"] == a), None)
            sb = next((s for s in self._stations if s["id"] == b), None)
            if not sa or not sb:
                continue
            x0, y0 = self._to_screen(sa["x"], sa["y"])
            x1, y1 = self._to_screen(sb["x"], sb["y"])
            self.canvas.create_line(x0, y0, x1, y1, fill="#3a3f46")

        # draw stations
        for s in self._stations:
            sx, sy = self._to_screen(s["x"], s["y"])
            r = 8
            self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r, fill="#b0d7ff", outline="")
            self.canvas.create_text(sx + 12, sy, text=f"{s['name']} ({s['system']})", anchor="w", fill="#dfe6ee")

    # ---------- interactions ----------

    def _start_drag(self, evt):
        self._drag_start = (evt.x, evt.y)

    def _drag(self, evt):
        if not self._drag_start:
            return
        dx = evt.x - self._drag_start[0]
        dy = evt.y - self._drag_start[1]
        self.offset[0] += dx
        self.offset[1] += dy
        self._drag_start = (evt.x, evt.y)
        self._draw()

    def _end_drag(self, _evt):
        self._drag_start = None

    def _zoom_at(self, factor: float, mouse_x: int, mouse_y: int):
        """Zoom keeping the mouse position stable in screen space."""
        wx, wy = self._from_screen(mouse_x, mouse_y)
        self.scale = max(0.2, min(5.0, self.scale * factor))
        sx, sy = self._to_screen(wx, wy)
        self.offset[0] += (mouse_x - sx)
        self.offset[1] += (mouse_y - sy)
        self._draw()

    def _zoom_windows(self, evt):
        if evt.delta > 0:
            self._zoom_at(1.1, evt.x, evt.y)
        else:
            self._zoom_at(1 / 1.1, evt.x, evt.y)

    def _zoom_linux_up(self, evt):
        self._zoom_at(1.1, evt.x, evt.y)

    def _zoom_linux_down(self, evt):
        self._zoom_at(1 / 1.1, evt.x, evt.y)

    def _open_travel_menu(self, evt):
        mx, my = self._from_screen(evt.x, evt.y)

        def nearest_station():
            best = None
            bd = 1e18
            for s in self._stations:
                dx = s["x"] - mx
                dy = s["y"] - my
                d2 = dx * dx + dy * dy
                if d2 < bd:
                    bd = d2
                    best = s
            return best

        target = nearest_station()
        if not target:
            return

        # neighbors from links
        neighbors: List[Tuple[int, int]] = []  # (sid, dist)
        for a, b, d in self._links:
            if a == target["id"]:
                neighbors.append((b, d))
            elif b == target["id"]:
                neighbors.append((a, d))

        # Player fuel
        pr = self.conn.execute("SELECT fuel FROM player WHERE id=1").fetchone()
        fuel = int(pr["fuel"]) if pr else 0

        # Ship jump range
        ship = self.conn.execute("""
            SELECT s.jump_range
            FROM hangar_ships h
            JOIN ships s ON s.id = h.ship_id
            WHERE h.is_active = 1
        """).fetchone()
        jump = int(ship["jump_range"]) if ship and ship["jump_range"] is not None else 5

        menu = tk.Menu(self, tearoff=0)

        # Neighbor destinations
        for sid, dist in neighbors:
            ok = (dist <= jump) and (fuel >= dist)
            dot = "🟢" if ok else "🔴"
            name = next((s["name"] for s in self._stations if s["id"] == sid), f"#{sid}")
            label = f"{dot}  Travel to {name}  (dist {dist})"
            if ok:
                menu.add_command(label=label, command=(lambda s=sid: self._begin_route(s)))
            else:
                menu.add_command(label=label, state="disabled")

        # Also allow traveling directly to the clicked station (self-target),
        # useful if the user right-clicks not exactly on a node linked set.
        self_lbl = f"🟢  Travel to {target['name']} ({target['system']})"
        menu.add_command(label=self_lbl, command=lambda: self._begin_route(target["id"]))

        menu.tk_popup(evt.x_root, evt.y_root)

    def _begin_route(self, station_id: int):
        try:
            # TravelController handles fuel consumption, events, etc.
            self.travel.begin_travel(int(station_id))
        except Exception as e:
            # Keep UI alive; log to the bus if available.
            try:
                self.bus.emit("log", {"category": "system", "message": f"Travel failed: {e}"})
            except Exception:
                pass