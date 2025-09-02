# /data/seed.py

"""
Victurus Database Seeding and Setup

Handles database initialization and data seeding:
- Creates database schema from schema.sql
- Seeds universe data from universe_seed.json
- Provides database reset and migration functionality
- Manages initial game world state
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Tuple, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SEED_PATHS = [DATA_DIR / "universe_seed.json", DATA_DIR / "universe_seed_v2.json"]


# ----------------------------- helpers -----------------------------

def _try_execmany(cur: sqlite3.Cursor, sql: str, rows: Iterable[tuple]) -> None:
    """Execute a batch. On FK errors, retry row-by-row and skip offending rows."""
    rows = list(rows)
    if not rows:
        return
    try:
        cur.executemany(sql, rows)
        return
    except sqlite3.IntegrityError:
        pass  # fall back to row-by-row

    for r in rows:
        try:
            cur.execute(sql, r)
        except sqlite3.IntegrityError:
            # Skip bad row silently
            continue


# ----------------------------- seed loading -----------------------------

def _load_seed() -> Dict[str, Any]:
    for p in SEED_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        f"No universe seed found. Looked for: {', '.join(str(p) for p in SEED_PATHS)}"
    )


# ----------------------------- normalization -----------------------------

def _norm_loc_type(t: str) -> str:
    # accept 'warpgate' from old seeds, convert to 'warp_gate'
    return "warp_gate" if t == "warpgate" else t

def _norm_resource_type(t: str) -> str:
    # canonicalize resource types to match asset folders and UI expectations
    if t == "gas_cloud":
        return "gas_clouds"
    return t


def _prepare_location_row(loc: Dict[str, Any]) -> Tuple[int, int, str, str, float, float, Optional[int], Optional[str]]:
    lt = _norm_loc_type(loc.get("location_type", ""))
    parent_id = loc.get("parent_location_id")
    if not parent_id:
        parent_id = None
    return (
        int(loc["location_id"]),
        int(loc["system_id"]),
        loc["location_name"],
        lt,
        float(loc.get("location_x", 0.0)),
        float(loc.get("location_y", 0.0)),
        int(parent_id) if parent_id is not None else None,
        loc.get("location_description"),
    )


# ----------------------------- location insertion -----------------------------

def _insert_locations_topologically(cur: sqlite3.Cursor, locs: List[Dict[str, Any]]) -> Tuple[set[int], List[Tuple]]:
    """
    Insert locations while respecting parent -> child dependencies.
    Filters out locations whose system_id is not present.
    If parent id not present among the seed's location ids, parent is set to NULL.
    In cycles, remaining parents are set to NULL and inserted if possible.
    Leaves all icon_path columns NULL; New Game creation assigns icons once.
    Returns: (inserted_ids, forced_or_skipped_rows)
    """
    if not locs:
        return set(), []

    system_ids = {row[0] for row in cur.execute("SELECT system_id FROM systems").fetchall()}
    rows = [_prepare_location_row(l) for l in locs]
    rows = [r for r in rows if r[1] in system_ids]

    valid_loc_ids = {r[0] for r in rows}

    sanitized: Dict[int, Tuple] = {}
    forced: List[Tuple] = []  # rows we had to force parent=NULL or skip later
    for r in rows:
        lid, sid, name, lt, x, y, parent_id, desc = r
        if parent_id is not None and parent_id not in valid_loc_ids:
            parent_id = None
            forced.append(r)
        sanitized[lid] = (lid, sid, name, lt, x, y, parent_id, desc)

    pending = dict(sanitized)  # lid -> row
    inserted: set[int] = set()

    sql = """        INSERT OR REPLACE INTO locations
          (location_id, system_id, location_name, location_type,
           location_x, location_y, parent_location_id, location_description, icon_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    def _row_with_icon(base_row: Tuple[int, int, str, str, float, float, Optional[int], Optional[str]],
                       parent_override: Optional[int] = None) -> Tuple:
        """Return a row tuple including an icon_path value.
    For stars, copy systems.icon_path into locations.icon_path. Otherwise NULL.
        """
        lid, sid, name, lt, x, y, parent_id, desc = base_row
        if parent_override is not None:
            parent_id = parent_override
        icon_path: Optional[str] = None
        if lt == "star":
            # For stars, copy systems.icon_path into locations.icon_path when present.
            row = cur.execute("SELECT icon_path FROM systems WHERE system_id=?;", (sid,)).fetchone()
            if row:
                icon_path = row[0]
        return (lid, sid, name, lt, x, y, parent_id, desc, icon_path)

    safety = 0
    while pending and safety < 20000:
        safety += 1
        ready_ids = [lid for lid, r in pending.items() if (r[6] is None or r[6] in inserted)]
        if not ready_ids:
            # break the deadlock: force parent=NULL for all remaining
            to_force = list(pending.items())
            for lid, r in to_force:
                _, sid, name, lt, x, y, _pid, desc = r
                r2 = _row_with_icon((lid, sid, name, lt, x, y, None, desc))
                try:
                    cur.execute(sql, r2)
                    inserted.add(lid)
                    forced.append(r)
                except sqlite3.IntegrityError:
                    # skip if still not insertable
                    pass
                pending.pop(lid, None)
            break

        for lid in ready_ids:
            r = pending.pop(lid)
            try:
                cur.execute(sql, _row_with_icon(r))
                inserted.add(lid)
            except sqlite3.IntegrityError:
                # retry with parent=NULL
                r2 = _row_with_icon(r, parent_override=None)
                try:
                    cur.execute(sql, r2)
                    inserted.add(lid)
                    forced.append(r)
                except sqlite3.IntegrityError:
                    # skip if still failing
                    pass

    return inserted, forced


# ----------------------------- main seed -----------------------------

def seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    seed = _load_seed()

    # ----------------- items -----------------
    if seed.get("items"):
        _try_execmany(
            cur,
            """            INSERT OR REPLACE INTO items
              (item_id, item_name, item_base_price, item_description, item_category)
            VALUES (?, ?, ?, ?, ?);
            """,
            [
                (
                    it["item_id"],
                    it["item_name"],
                    it.get("item_base_price", 0),
                    it.get("item_description"),
                    it.get("item_category"),
                )
                for it in seed["items"]
            ],
        )

    # ----------------- ships -----------------
    if seed.get("ships"):
        _try_execmany(
            cur,
            """            INSERT OR REPLACE INTO ships
              (ship_id, ship_name, base_ship_cargo, base_ship_fuel,
               base_ship_jump_distance, base_ship_shield, base_ship_hull, base_ship_energy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                (
                    sh.get("ship_id"),
                    sh["ship_name"],
                    int(sh.get("base_ship_cargo", 0)),
                    int(sh.get("base_ship_fuel", 0)),
                    float(sh.get("base_ship_jump_distance", 0.0)),
                    int(sh.get("base_ship_shield", 0)),
                    int(sh.get("base_ship_hull", 0)),
                    int(sh.get("base_ship_energy", 0)),
                )
                for sh in seed["ships"]
            ],
        )

    # ----------------- systems -----------------
    if seed.get("systems"):
        sys_rows = [
            (
                s["system_id"],
                s["system_name"],
                int(s["system_x"]),
                int(s["system_y"]),
                s.get("icon_path"),
            )
            for s in seed["systems"]
        ]
        _try_execmany(
            cur,
            """            INSERT OR REPLACE INTO systems
              (system_id, system_name, system_x, system_y, icon_path)
            VALUES (?, ?, ?, ?, ?);
            """ ,
            sys_rows,
        )

        # econ tags (optional)
        tag_rows = []
        for s in seed["systems"]:
            tags = s.get("econ_tags") or []
            for t in tags:
                tag_rows.append((s["system_id"], str(t)))
        if tag_rows:
            _try_execmany(
                cur,
                "INSERT OR IGNORE INTO system_econ_tags (system_id, tag) VALUES (?, ?);" ,
                tag_rows,
            )

    # Precompute system_ids
    system_ids = {row[0] for row in cur.execute("SELECT system_id FROM systems").fetchall()}

    # ----------------- markets -----------------
    if seed.get("markets"):
        _try_execmany(
            cur,
            """            INSERT OR REPLACE INTO markets
              (system_id, item_id, local_market_price, local_market_stock)
            VALUES (?, ?, ?, ?);
            """ ,
            [
                (
                    m["system_id"],
                    m["item_id"],
                    int(m["local_market_price"]),
                    int(m["local_market_stock"]),
                )
                for m in seed["markets"]
                if m["system_id"] in system_ids
            ],
        )

    # ----------------- locations (topological) -----------------
    inserted_loc_ids: set[int] = set()
    if seed.get("locations"):
        inserted_loc_ids, _ = _insert_locations_topologically(cur, seed["locations"])

    # ----------------- ensure warpgate location rows exist -----------------
    if seed.get("warpgates"):
        for wg in seed["warpgates"]:
            sid = wg.get("system_id")
            lid = wg.get("location_id")
            if sid is None or lid is None:
                continue
            if sid not in system_ids:
                continue
            row = cur.execute("SELECT system_id, location_type FROM locations WHERE location_id=?;", (lid,)).fetchone()
            if row is None:
                # create a minimal warp gate location at (0,0) with name 'Warp Gate'
                try:
                    cur.execute(
                        """                        INSERT OR REPLACE INTO locations
                          (location_id, system_id, location_name, location_type, location_x, location_y, parent_location_id, location_description, icon_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """ ,
                        (lid, sid, "Warp Gate", "warp_gate", 0.0, 0.0, None, None, None),
                    )
                    inserted_loc_ids.add(int(lid))
                except sqlite3.IntegrityError:
                    pass
            else:
                if row[0] == sid and row[1] != "warp_gate":
                    # normalize existing row to warp_gate type
                    cur.execute("UPDATE locations SET location_type='warp_gate' WHERE location_id=?;", (lid,))

    # ----------------- races / ownership / diplomacy -----------------
    if seed.get("races"):
        _try_execmany(
            cur,
            """            INSERT OR REPLACE INTO races
              (race_id, name, adjective, description, tech_theme, ship_doctrine,
               government, color, home_system_id, home_planet_location_id, starting_world)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """ ,
            [
                (
                    r["race_id"],
                    r["name"],
                    r.get("adjective"),
                    r.get("description"),
                    r.get("tech_theme"),
                    r.get("ship_doctrine"),
                    r.get("government"),
                    r.get("color"),
                    r.get("home_system_id"),
                    r.get("home_planet_location_id"),
                    1 if r.get("starting_world", 1) else 0,
                )
                for r in seed["races"]
            ],
        )

    # Precompute race_ids (for ownership/diplomacy)
    race_ids = {row[0] for row in cur.execute("SELECT race_id FROM races").fetchall()}

    if seed.get("ownerships"):
        own_rows = []
        for o in seed["ownerships"]:
            sid = o["system_id"]
            rid = o.get("race_id")
            if sid not in system_ids:
                continue
            if rid is not None and rid not in race_ids:
                rid = None
            own_rows.append((sid, rid, o.get("status", "unclaimed")))
        _try_execmany(
            cur,
            "INSERT OR REPLACE INTO ownerships (system_id, race_id, status) VALUES (?, ?, ?);" ,
            own_rows,
        )

    if seed.get("diplomacy"):
        dip_rows = []
        for d in seed["diplomacy"]:
            a = d["race_a_id"]
            b = d["race_b_id"]
            if a == b:
                continue
            if a in race_ids and b in race_ids:
                dip_rows.append((a, b, int(d.get("stance", 0)), d.get("status", "neutral")))
        _try_execmany(
            cur,
            "INSERT OR REPLACE INTO diplomacy (race_a_id, race_b_id, stance, status) VALUES (?, ?, ?, ?);" ,
            dip_rows,
        )

    # ----------------- warp graph -----------------
    if seed.get("gate_links"):
        gl_set = set()  # canonicalize undirected edges as (min,max)
        for gl in seed["gate_links"]:
            a = gl.get("a") or gl.get("system_a_id")
            b = gl.get("b") or gl.get("system_b_id")
            if a is None or b is None:
                continue
            if a not in system_ids or b not in system_ids:
                continue
            a2, b2 = (a, b) if a <= b else (b, a)
            dist = float(gl["distance_pc"]) if gl.get("distance_pc") is not None else 0.0
            gl_set.add((a2, b2, dist))
        gl_rows = list(gl_set)
        _try_execmany(
            cur,
            "INSERT OR REPLACE INTO gate_links (system_a_id, system_b_id, distance_pc) VALUES (?, ?, ?);" ,
            gl_rows,
        )

    # ----------------- resources & facilities -----------------
    if seed.get("resource_nodes"):
        # Merge resource node metadata into the corresponding `locations` rows.
        for rn in seed["resource_nodes"]:
            lid = rn["location_id"]
            if lid not in inserted_loc_ids:
                continue
            rtype = _norm_resource_type(rn["resource_type"])
            try:
                cur.execute(
                    "UPDATE locations SET resource_type=?, richness=?, regen_rate=? WHERE location_id=?",
                    (rtype, int(rn.get("richness", 0)), float(rn.get("regen_rate", 0.0)), lid),
                )
            except Exception:
                # ignore problematic resource rows during seed
                continue

    if seed.get("facilities"):
        fac_rows = []
        finputs = []
        foutputs = []

        for f in seed["facilities"]:
            lid = f["location_id"]
            if lid not in inserted_loc_ids:
                continue
            fac_rows.append((f["facility_id"], lid, f["facility_type"], f.get("notes")))
            for ent in f.get("inputs", []):
                finputs.append((f["facility_id"], ent["item_id"], float(ent["rate"])))
            for ent in f.get("outputs", []):
                foutputs.append((f["facility_id"], ent["item_id"], float(ent["rate"])))

        if fac_rows:
            _try_execmany(
                cur,
                "INSERT OR REPLACE INTO facilities (facility_id, location_id, facility_type, notes) VALUES (?, ?, ?, ?);" ,
                fac_rows,
            )
        if finputs:
            _try_execmany(
                cur,
                "INSERT OR REPLACE INTO facility_inputs (facility_id, item_id, rate) VALUES (?, ?, ?);" ,
                finputs,
            )
        if foutputs:
            _try_execmany(
                cur,
                "INSERT OR REPLACE INTO facility_outputs (facility_id, item_id, rate) VALUES (?, ?, ?);" ,
                foutputs,
            )

    # ----------------- ship roles -----------------
    if seed.get("ship_roles"):
        sr_rows = []
        for sr in seed["ship_roles"]:
            sid = sr["ship_id"]
            for role in sr.get("roles", []):
                sr_rows.append((sid, role))
        if sr_rows:
            _try_execmany(
                cur,
                "INSERT OR IGNORE INTO ship_roles (ship_id, role) VALUES (?, ?);" ,
                sr_rows,
            )

    # ----------------- consumption profiles (ships) -----------------
    cp = seed.get("consumption_profiles") or {}
    ship_profiles = cp.get("ship") or []
    if ship_profiles:
        rows = []
        for prof in ship_profiles:
            role = str(prof.get("role", "any"))
            for ent in prof.get("consumes", []):
                rows.append((role, ent["item_id"], float(ent["rate"])))
        if rows:
            _try_execmany(
                cur,
                "INSERT OR REPLACE INTO consumption_profiles_ship (role, item_id, rate) VALUES (?, ?, ?);" ,
                rows,
            )

    # ----------------- player row -----------------
    # Provide a default player so the UI can load even before "New Game" places the commander.
    # The real placement/name happens later by the new-game flow.
    row = cur.execute(
        "SELECT MIN(race_id), home_system_id, home_planet_location_id FROM races"
    ).fetchone()
    if row and row[0] is not None:
        _, start_sid, start_lid = row
        ship = cur.execute(
            """            SELECT ship_id, ship_name, base_ship_fuel, base_ship_hull,
                   base_ship_shield, base_ship_energy, base_ship_jump_distance,
                   base_ship_cargo
            FROM ships
            ORDER BY (ship_name='Shuttle') DESC, base_ship_cargo ASC
            LIMIT 1;
            """
        ).fetchone()
        if ship:
            cur.execute(
                """                INSERT OR REPLACE INTO player(
                    id, name, current_wallet_credits, current_player_system_id,
                    current_player_ship_id, current_player_ship_fuel,
                    current_player_ship_hull, current_player_ship_shield,
                    current_player_ship_energy, current_player_ship_cargo,
                    current_player_location_id
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """ ,
                (
                    "Captain",
                    1000,
                    start_sid,
                    ship[0],
                    ship[2],
                    ship[3],
                    ship[4],
                    ship[5],
                    0,
                    start_lid,
                ),
            )

    conn.commit()
