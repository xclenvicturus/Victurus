import os, json, sqlite3
from . import save_schema

def load_content_pack(conn: sqlite3.Connection, path: str) -> str:
    if not os.path.exists(path):
        return "Content pack not found."
    try:
        with open(path, "r", encoding="utf-8") as f:
            pack = json.load(f)
    except Exception as e:
        return f"Failed to read pack: {e}"
    cur = conn.cursor()
    # Insert in dependency order; ignore conflicts
    for fct in pack.get("factions", []):
        cur.execute("INSERT OR IGNORE INTO factions(id,name,description) VALUES (?,?,?)", (fct["id"], fct["name"], fct.get("description","")))
        cur.execute("INSERT OR IGNORE INTO faction_rep(faction_id,rep) VALUES (?,?)", (fct["id"], 0))
    for rel in pack.get("relations", []):
        a,b = rel["a"], rel["b"]
        fa, fb = (a,b) if a<b else (b,a)
        cur.execute("INSERT OR IGNORE INTO faction_relations(faction_a,faction_b,state) VALUES (?,?,?)", (fa, fb, rel.get("state","neutral")))
    for sys in pack.get("systems", []):
        cur.execute("INSERT OR IGNORE INTO systems(id,name,x,y) VALUES (?,?,?,?)", (sys["id"], sys["name"], sys["x"], sys["y"]))
    for pl in pack.get("planets", []):
        cur.execute("INSERT OR IGNORE INTO planets(id,name,system_id) VALUES (?,?,?)", (pl["id"], pl["name"], pl["system_id"]))
    for st in pack.get("stations", []):
        cur.execute("INSERT OR IGNORE INTO stations(id,name,planet_id,faction_id,fuel_price) VALUES (?,?,?,?,?)", (st["id"], st["name"], st["planet_id"], st["faction_id"], st.get("fuel_price", 2)))
    for it in pack.get("items", []):
        cur.execute("INSERT OR IGNORE INTO items(id,name,base_price,type,description) VALUES (?,?,?,?,?)", (it["id"], it["name"], it["base_price"], it["type"], it.get("description","")))
    for m in pack.get("markets", []):
        cur.execute("INSERT OR IGNORE INTO markets(station_id,item_id,quantity,price) VALUES (?,?,?,?)", (m["station_id"], m["item_id"], m["quantity"], m["price"]))
    for s in pack.get("ships", []):
        cur.execute("INSERT OR IGNORE INTO ships(id,name,hull,damage,cargo_capacity,base_price,fuel_capacity,jump_range,efficiency) VALUES (?,?,?,?,?,?,?,?,?)",
                    (s["id"], s["name"], s["hull"], s["damage"], s["cargo_capacity"], s["base_price"], s["fuel_capacity"], s["jump_range"], s["efficiency"]))
    for sm in pack.get("ship_market", []):
        cur.execute("INSERT OR IGNORE INTO ship_market(station_id,ship_id,price,quantity) VALUES (?,?,?,?)", (sm["station_id"], sm["ship_id"], sm["price"], sm["quantity"]))
    for npc in pack.get("npcs", []):
        cur.execute("INSERT OR IGNORE INTO npcs(id,name,station_id,faction_id,role,dialog) VALUES (?,?,?,?,?,?)", (npc["id"], npc["name"], npc["station_id"], npc["faction_id"], npc.get("role","NPC"), npc.get("dialog","...")))
    for q in pack.get("quests", []):
        cur.execute("INSERT OR IGNORE INTO quests(id,title,description,giver_npc_id,target_station_id,reward_credits) VALUES (?,?,?,?,?,?)", (q["id"], q["title"], q["description"], q["giver_npc_id"], q["target_station_id"], q["reward_credits"]))
        cur.execute("INSERT OR IGNORE INTO quest_instances(quest_id,status) VALUES (?,?)", (q["id"], "offered"))
    conn.commit()
    return "Content pack loaded."
