# Victurus — AI Map (v2)
_Last updated: 2025-08-19 (America/Chicago)_

## Repository
- Name: `Victurus`
- URL: https://github.com/xclenvicturus/Victurus
- Language: Python
- OS target: Windows
- GUI: Tkinter

## Overview
Victurus is a Tkinter-backed, text-forward space RPG. `main.py` launches `GameApp`, which composes core services, event bus, persistence, UI windows, and gameplay controllers.

## Top-Level
- **main.py** — entry point
- **engine/** — core package (controllers, UI windows, persistence, world/models)
- **docs/** — project docs (this file)
- **.chatgpt/** — AI assistant configuration
- **AI_CONTRIBUTING.md** — rules for AI contributions
- *(vcs/artifacts omitted)*

## Module Map
### Entry Point
- **main.py** — functions: default_saves_root, main
  - Imports: internal —; external os, pathlib, sys

### Composition Root
- **engine/game_app.py** — classes: GameApp
  - Imports internal: actions_panel, app_context, app_events, cheats, controllers.combat_controller, controllers.quest_controller, controllers.travel_controller, event_bus, save_manager, settings, ui_builder, window_togglers
  - Imports external: __future__, pathlib, sqlite3, tkinter, typing
  - Role: Creates Tk root, wires Settings/WindowStateManager, EventBus, AppContext; initializes SaveManager, UI, togglers, Actions panel, App events, Cheats; builds controllers on save open.

### engine/settings.py
- classes: Settings, WindowStateManager
- functions: user_settings_path, on_configure, on_close_cb
- imports: internal —; external tkinter, typing, pathlib, json, os

### engine/event_bus.py
- classes: EventBus
- functions: —
- imports: internal —; external typing

### engine/app_context.py
- classes: AppContext
- functions: —
- imports: internal event_bus, settings; external tkinter, sqlite3, typing

### engine/app_events.py
- classes: AppEvents
- functions: —
- imports: internal app_context, window_togglers, actions_panel; external tkinter, typing

### engine/ui_builder.py
- classes: UIBuilder
- functions: show_menu
- imports: internal app_context, window_togglers, actions_panel, app_events; external tkinter, typing

### Persistence
- **engine/db_manager.py** — classes: DBManager; functions: —
- **engine/save_manager.py** — classes: SaveManager; functions: on_accept, do_open, do_clone, do_delete
- **engine/save_schema.py** — classes: —; functions: (schema helpers)

### World & Models
- **engine/models.py** — classes: Faction, System, Planet, Station, Item, Ship, NPC, Quest, StartStation; functions: —
- **engine/world.py** — classes: —; functions: get_player, player_ship, get_system, system_of_station, distance_between_systems, get_location_name, map_data, station_detail, update_player_location, adjust_player, set_active_ship, player_cargo, set_player_cargo, quests_at_station, accept_quest, complete_quest_if_applicable, rep_with, adjust_rep, relation_between

### Simulation
- **engine/sim.py** — classes: —; functions: _clamp, economy_tick, faction_skirmish_tick, wars_tick, _jitter

### Actions & Cheats
- **engine/actions.py** — classes: —; functions: get_player, player_ship, buy_item, sell_item, buy_ship, sell_ship, set_active_ship (and more)
- **engine/cheats.py** — classes: CheatService; functions: —

### Content Loading
- **engine/loader.py** — classes: —; functions: load_content_pack

### Controllers
- **engine/controllers/combat_controller.py** — classes: CombatController; functions: —
- **engine/controllers/quest_controller.py** — classes: QuestController; functions: —
- **engine/controllers/route_controller.py** — classes: RouteStep, RoutePlan, RouteController; functions: —
- **engine/controllers/travel_controller.py** — classes: TravelController; functions: —

### UI Windows & Panels
- **engine/ui/cargo_window.py** — classes: CargoWindow; functions: —
- **engine/ui/hangar_window.py** — classes: HangarWindow; functions: —
- **engine/ui/log_panel.py** — classes: LogPanel; functions: —
- **engine/ui/map_window.py** — classes: MapWindow; functions: —
- **engine/ui/market_window.py** — classes: MarketWindow; functions: —
- **engine/ui/player_window.py** — classes: PlayerWindow; functions: —
- **engine/ui/quests_window.py** — classes: QuestsWindow; functions: —
- **engine/ui/status_window.py** — classes: StatusWindow; functions: —
- **engine/actions_panel.py** — classes: ActionsPanel; functions: add_btn
- **engine/window_togglers.py** — classes: WindowTogglers; functions: _toggle_top (plus `_open_*` helpers)

### Game Events
- **engine/events.py** — classes: —; functions: _ensure_player_events, log_event, combat_turn

## Data Flow (high-level)
1. **Startup**: `python main.py` → constructs `GameApp` with a save directory under Documents/Victurus_Game/Saves.
2. **Composition**: `GameApp` creates Tk root, loads `Settings` & `WindowStateManager`, initializes `EventBus` & `AppContext`.
3. **Persistence**: `SaveManager` mediates creating/opening/cloning/deleting save slots; `DBManager` wraps sqlite; `save_schema` declares tables and migrations.
4. **UI**: `WindowTogglers` opens/toggles singletons for each `Toplevel` window: Map, Hangar, Market, Status, Cargo, Player, Quests, plus `LogPanel`.
5. **Controllers**: Gameplay orchestration via `QuestController`, `TravelController` (Tk-aware), `RouteController`, `CombatController`.
6. **World/Models**: Entities defined in `models.py`; helpers in `world.py` retrieve/adjust player, ship, factions, reputation.
7. **Simulation**: `sim.py` advances economy, skirmishes, and wars.
8. **Events**: `events.py` provides helpers like `log_event` and `combat_turn`; `app_events.py` wires app-level commands and menu items.
9. **Actions/Cheats**: `actions.py` contains game verbs (trade, buy/sell, ship mgmt.); `CheatService` exposes debug/admin actions.

## Database Schema (from engine/save_schema.py)
- player
- hangar_ships
- player_cargo
- quest_instances
- player_events
- events_log
- station_economy

## Conventions
- Python 3.13 (adjust if repo pins a version)
- Keep modules narrow; prefer Tk `Toplevel` per window; centralize toggle logic in `WindowTogglers`.
- Use the `EventBus` for decoupled notifications.

## Run Steps
```bash
python main.py
