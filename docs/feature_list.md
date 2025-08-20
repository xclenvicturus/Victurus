Legend: 🟨 = implemented now, 🟥 = not implemented yet, 🟩 = confirmed working

Core / App Shell

🟨 PySide6 app entry + MainWindow (menus, status bar, close handling)

🟥 Settings + window state persistence (geometry/topmost restore in Qt)

🟥 Central event bus (Qt-wired) (signals between services/controllers/UI)

🟥 Hotkeys (global shortcuts mapped to actions)

UI (Qt)

🟨 Dock panes: Actions (left), NPCs (right), Log (bottom) — toggle from “Windows” menu

🟨 Log panel with copy-all & clear context menu

🟨 NPC panel (list + selection helper)

🟨 Actions panel (Travel/Dock/Trade buttons, feature toggles, Talk signal) — logs only

🟨 Galaxy map view: panning + wheel-zoom; demo star nodes

🟥 Galaxy map data from DB/services (real systems/sectors, owners)

🟥 Map interactions (select system, tooltips, focus, route preview)

🟥 Dedicated chat window (NPC dialogue UI)

🟥 Status / Cargo / Player / Market / Hangar / Quests windows (Qt)

Saves & Flow

🟥 New / Load / Save / Delete wired to SaveManager (menus currently log only)

🟥 Slot picker dialogs + confirmations

World / Economy

🟥 Economy tick (production, shipments, pricing, rep decay) — timer exists, logic not wired

🟥 Dynamic market pricing per-station (qty vs desired stock → buy/sell adjust)

🟥 Real-time trading via ships (no fabricating items; shipments consume/produce)

🟥 Production modules & recipes (stations/planets produce goods/services)

🟥 Initial seeding of items across universe at game start (for flow)

🟥 NPC & player needs (food, fuel, repair mats → ongoing demand)

🟥 Ship building (BOM-based costs, build time, supply usage)

🟥 Hangar ordering (view all orderable ships, place order, build progress, delivery notice)

🟥 Per-station player hangars (inventory view is station-scoped)

Factions / Relations

🟥 Factions ledger (member count, credits, sectors/locations owned & disputed)

🟥 Faction relations matrix (rep up/down on help/attacks/kills; events log)

🟥 Ownership & influence (sectors/locations contest & control effects)

Controllers (non-UI logic)

🟥 Travel controller (routing, fuel, jump rules) wired to UI

🟥 Quest controller (accept/complete, payouts, updates)

🟥 Combat controller (encounters, outcomes to log/UI)

🟥 Economy controller (owns QTimer; orchestrates tick + refresh signals)

Services / DB

🟨 Database files present (Database/*.db)

🟨 Tooling scripts present (tools/create_databases.py, seed_databases.py, migrate_databases.py, init_economy.py)

🟥 World service (systems/planets/stations queries) wired into UI/models

🟥 Market service (buy/sell ops; price snapshots) wired into UI/models

🟥 Cheat service (real effects; currently logs only)

🟥 Data models / types (DTOs used end-to-end)

UX polish

🟥 Theming (QSS) (dark theme, spacing, focus rings)

🟥 Toolbars & icons (quick-access actions)

🟥 Notifications/toasts (e.g., “Ship delivered to Hangar at X”)