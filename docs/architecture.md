Victurus/
├─ main.py  — Entrypoint: creates QApplication (PySide6), builds and shows MainWindow.
├─ requirements.txt  — Runtime deps (PySide6, plus anything else you add later).

├─ Database/  — One SQLite file per domain; opened by services with PRAGMA foreign_keys=ON.
│  ├─ world.db     — Systems, planets, stations (coords, ownership links).
│  ├─ factions.db  — Factions, faction_relations matrix, relation_events ledger.
│  ├─ items.db     — Items catalog, per-station markets (qty, desired_stock, buy/sell).
│  ├─ ships.db     — Ships, ship_market, ship_bill_of_materials (BOM).
│  ├─ npcs.db      — NPC roster, station placement, dialog metadata.
│  ├─ quests.db    — Quests (giver, target, rewards), player quest state.
│  └─ economy.db   — Sectors, ownership/influence, modules, recipes, jobs, shipments, hangars.

├─ engine/
│  ├─ __init__.py  — Marks package; keep empty.
│  ├─ app/  — Composition root and core plumbing (no UI widgets here).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  ├─ qt_app.py               — QApplication bootstrap; wires bus/settings; opens MainWindow.
│  │  ├─ app_context.py          — Shared refs (app settings, event bus, save_root, helpers).
│  │  ├─ settings.py             — Settings store + WindowStateManager (geometry/topmost).
│  │  ├─ event_bus.py            — Lightweight pub/sub (Qt signals) to decouple UI and logic.
│  │  └─ app_events.py           — Connects menu actions & hotkeys to controllers / bus.

│  ├─ qtui/  — PySide6 UI layer (replaces legacy Tk UI).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  ├─ main_window.py          — QMainWindow: menus, status bar, docks, central GalaxyMapView.  :contentReference[oaicite:0]{index=0}
│  │  ├─ map/
│  │  │  ├─ __init__.py          — Marks subpackage; keep empty.
│  │  │  ├─ galaxy_scene.py      — QGraphicsScene that renders systems/sectors; sets scene rect.  :contentReference[oaicite:1]{index=1}
│  │  │  └─ galaxy_view.py       — QGraphicsView with pan (ScrollHandDrag) + wheel zoom under mouse.  :contentReference[oaicite:2]{index=2}
│  │  ├─ panels/
│  │  │  ├─ __init__.py          — Marks subpackage; keep empty.
│  │  │  ├─ actions_panel.py     — Left dock: Travel/Dock/Trade buttons; feature toggles; Talk button.
│  │  │  ├─ npc_panel.py         — Right dock: QListView of local NPCs + “Talk” button.
│  │  │  └─ log_panel.py         — Bottom dock: QPlainTextEdit or QListView with copy/clear context menu.
│  │  ├─ models/
│  │  │  ├─ __init__.py          — Marks subpackage; keep empty.
│  │  │  ├─ npc_model.py         — QAbstractListModel (name, faction, role, id) for NPC list.  :contentReference[oaicite:3]{index=3}
│  │  │  ├─ market_model.py      — QAbstractTableModel for market grid (Item/Qty/Desired/Buy/Sell/Delta/Station).  :contentReference[oaicite:4]{index=4}
│  │  │  └─ log_model.py         — QAbstractListModel for log stream (ts/level/text).  :contentReference[oaicite:5]{index=5}
│  │  ├─ resources/
│  │  │  ├─ styles.qss           — Optional Qt stylesheet (dark theme, spacing, focus rings).
│  │  │  └─ icons/               — Toolbar/menu/dock icons (SVG/PNG).

│  ├─ controllers/  — Domain logic (no direct UI imports).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  ├─ travel_controller.py    — Routing, jumps, fuel checks; emits log/worldChanged.
│  │  ├─ quest_controller.py     — Accept/complete quests; grant rewards; quest state updates.
│  │  ├─ combat_controller.py    — Placeholder for encounters; emits outcomes to log/UI.
│  │  └─ economy_controller.py   — Owns QTimer tick; runs production/shipments/pricing; emits refresh.  :contentReference[oaicite:6]{index=6}

│  ├─ services/  — DB I/O layer (enables PRAGMAs, transactions; callable from controllers).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  ├─ save_manager.py         — New/Load/Save/Delete save slots; opens DBs; callback on open.
│  │  ├─ cheat_service.py        — Dev cheats (credits/items/ships) for testing.
│  │  ├─ world_service.py        — Read-only queries: systems/planets/stations by ids/coords.
│  │  └─ market_service.py       — Buy/sell ops; reads/writes to markets; price snapshots.

│  ├─ economy/  — Simulation logic (pure Python; no UI).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  ├─ tick.py                 — Economy step: production, shipments, build progress, price updates.
│  │  ├─ seed.py                 — Defaults (desired stock, starting quantities, sample shipments).
│  │  └─ schema_sql.py           — DDL strings (extra economy tables; used by tools/migrations).

│  ├─ data_models/  — Typed DTOs (optional, helps editor/linters).
│  │  ├─ __init__.py             — Marks package; keep empty.
│  │  └─ types.py                — Dataclasses: Station, Item, MarketRow, Relation, etc.

│  └─ tools/  — One-off CLIs for DB lifecycle.
│     ├─ __init__.py             — Marks package; keep empty.
│     ├─ create_databases.py     — Create empty DBs/tables in /Database.
│     ├─ seed_databases.py       — Seed a tiny universe for testing.
│     ├─ migrate_databases.py    — Add/alter columns safely; backfill defaults.
│     └─ init_economy.py         — Build economy schema + seeds then verify integrity.

├─ assets/  — Non-code game assets.
│  ├─ images/  — Icons, map glyphs, UI art.
│  ├─ fonts/   — Custom fonts (license accordingly).
│  └─ audio/   — SFX/music (optional).

├─ docs/  — Project reference (keep this file list here too).
│  ├─ architecture.md  — High-level structure, module boundaries, event flow.
│  ├─ schema.md        — ERDs and per-table column docs (source of truth).
│  └─ ui.md            — Qt UI design: docks, menus, hotkeys, model/view mapping.

└─ tests/  — Unit tests (focus on services/controllers first).
   ├─ __init__.py                — Marks package; keep empty.
   ├─ test_services_market.py    — Buy/sell behavior; price dynamics; stock adjustments.
   ├─ test_controllers_travel.py — Fuel consumption, routing, docking edge cases.
   └─ test_models_qt.py          — Basic QAbstractItemModel behavior (rowCount/data/roles).