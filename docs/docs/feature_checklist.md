# docs/feature_checklist.md

# Victurus – Living Feature Checklist

**Legend**
- 🟨 = implemented now (scaffolded or basic behavior present)
- 🟥 = not implemented yet
- 🟩 = verified working in-game (flip to green once you confirm)

> Maintenance: Update this file whenever you add/verify a feature. Move an item to 🟩 only after you’ve run it in-game and you’re satisfied with the behavior.

---

## Core / App Shell
- 🟨 **PySide6 app entry + MainWindow** (menus, status bar, close handling)
- 🟥 **Settings + window state persistence (Qt)** (save/restore geometry, dock visibility)
- 🟥 **Central event bus (Qt signals)** (decouple UI ↔ services/controllers)
- 🟥 **Hotkeys** (global shortcuts mapped to actions)

## UI (Qt)
- 🟨 **Dock panes**: Actions (left), NPCs (right), Log (bottom) — toggle from **Windows** menu
- 🟨 **Log panel** with Copy All & Clear (context menu)
- 🟨 **NPC panel** (list + selection helper)
- 🟨 **Actions panel** (Travel / Dock / Trade buttons, feature toggles, Talk signal) — logs only
- 🟨 **Galaxy map view**: panning + wheel-zoom; demo star nodes
- 🟥 **Galaxy map from DB/services** (real systems/sectors, owners, tooltips)
- 🟥 **Map interactions** (select system, focus/center, route preview, context actions)
- 🟥 **Dedicated chat window** (NPC dialogue UI)
- 🟥 **Status window** (ship & player stats)
- 🟥 **Cargo window** (holds, transfers, jettison)
- 🟥 **Player window** (skills, perks, reputation summary)
- 🟥 **Market window** (buy/sell; dynamic prices by station/sector)
- 🟥 **Hangar window** (inventory; order/receive ships with build times)
- 🟥 **Quests window** (active/available; accept/turn-in; rewards)

## Saves & Flow
- 🟥 **New / Load / Save / Delete** wired to `SaveManager` (menus currently log only)
- 🟥 **Slot picker dialogs** (create/rename/delete slots with confirmations)

## World / Economy Simulation
- 🟥 **Economy tick** (production, shipments, build progress, price updates)
- 🟥 **Dynamic market pricing** (qty vs desired stock → buy/sell adjust)
- 🟥 **Real-time trading via cargo ships** (no fabrication; shipments move goods)
- 🟥 **Production modules & recipes** (stations/planets produce goods/services)
- 🟥 **Initial seeding** (items across the universe at game start)
- 🟥 **NPC & player needs** (food, fuel, repair mats → ongoing demand)
- 🟥 **Ship building** (BOM-based costs, build time, supply usage)
- 🟥 **Hangar ordering** (browse catalog, place order, build ETA, delivery notice)
- 🟥 **Per-station player hangars** (inventory view scoped to current station)

## Factions / Relations
- 🟥 **Factions ledger** (member count, credits, sectors/locations owned & disputed)
- 🟥 **Faction relations matrix** (rep up/down from help/attacks/kills; events log)
- 🟥 **Ownership & influence** (contested sectors/locations; control effects)

## Controllers (non-UI logic)
- 🟥 **Travel controller** (routing, fuel, jump rules) wired to UI
- 🟥 **Quest controller** (accept/complete, payouts, updates)
- 🟥 **Combat controller** (encounters, outcomes to log/UI)
- 🟥 **Economy controller** (owns QTimer; orchestrates tick + UI refresh)

## Services / DB Layer
- 🟨 **Database files present** (`Database/*.db`)
- 🟨 **Tooling scripts present** (`tools/create_databases.py`, `seed_databases.py`, `migrate_databases.py`, `init_economy.py`)
- 🟥 **World service** (systems/planets/stations queries) **wired into UI/models**
- 🟥 **Market service** (buy/sell ops; price snapshots) **wired into UI/models**
- 🟥 **Cheat service** (real effects; currently logs only)
- 🟥 **Data models / types** (DTOs used end-to-end in services/controllers/UI)

## UX / Polish
- 🟥 **Theming (QSS)** (dark theme, spacing, focus rings)
- 🟥 **Toolbars & icons** (quick-access actions)
- 🟥 **Notifications/toasts** (e.g., “Ship delivered to Hangar at X”)

---

### Verification Rules (when to flip to 🟩)
- Feature runs end-to-end (UI → controller → service/DB) without errors.
- Behavior matches design notes in `docs/ui.md` and `docs/schema.md`.
- State persists if applicable (e.g., geometry, saves).
- You’ve tested at least one happy path and one edge case.

### How to Propose / Track Work
- Add a short note under the feature item when you start work:
  - `(@dev-name, branch: feature/economy-tick, PR #123)`
- When merged and tested manually, change 🟥 → 🟨.
- When verified in a real run (or covered by tests), change 🟨 → 🟩 and add a one-line proof note:
  - `Verified: jumped Sol→Alpha, fuel deducted correctly (2025-08-20).`

---