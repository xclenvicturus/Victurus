# Victurus — Project Structure (updated 2025-09-01)

This document summarizes the repository layout and what each part is responsible for.

## Key modules

- **UI (`ui/`)** — Widgets, panels, and map views (galaxy/system) built with PySide6.
- **Game (`game/`)** — Player snapshot, ship state, travel math, and game‑flow orchestration.
- **Data (`data/`)** — SQLite schema, seed helpers, and the runtime DB access layer.
- **Save (`save/`)** — Save‑game models, paths, serialization, and lifecycle management.
- **Game Controller (`game_controller/`)** — Background simulation and new game creation.
- **Settings (`settings/`)** — Configuration management.
- **Tests (`tests/`)** — Test files and debugging utilities.
- **Docs (`docs/`)** — Developer‑facing documentation.
- **Assets (`assets/`)** — Star, planet, station, and other art assets (GIF/PNG) organized by type (e.g., `assets/planets/p01.gif`). The UI selects deterministic assets per system/location so thumbnails match the map.

Note: resource art lives under the plural resource folders, e.g. `assets/asteroid_fields`, `assets/gas_clouds`, `assets/ice_fields`, `assets/crystal_veins`.

## Tree

```
Victurus/
│
├─ `main.py`
├─ `requirements.txt`
│
├─ data/
│  ├─ `db.py`
│  ├─ `schema.sql`
│  ├─ `seed.py`
│  └─ `universe_seed.json`
│
├─ database/
│  └─ `game.db`
│
├─ assets/
│  ├─ asteroid_fields/
│  │  └─ `a01.gif`
│  ├─ planets/
│  │  └─ `p01.gif`
│  ├─ crystal_veins/
│  │  └─ `c01.gif`
│  ├─ gas_clouds/
│  │  └─ `g01.gif`
│  ├─ ice_fields/
│  │  └─ `i01.gif`
│  ├─ moons/
│  │  └─ `m01.gif`
│  ├─ stars/
│  │  └─ `t01.gif`
│  ├─ stations/
│  │  └─ `s01.gif`
│  ├─ warp_gates/
│  │  └─ `w01.gif`
│  ├─ galaxy_backgrounds/
│  │  └─ `default.png`
│  └─ system_backgrounds/
│     └─ `system_bg_01.png`
│
├─ docs/
│  ├─ `structure.md`
│  ├─ `project_status.md`
│  ├─ `ui_state_management.md`
│  ├─ `error_handling.md`
│  └─ `VIEW_MENU_FIX.md`
│
├─ tests/
│  ├─ `README.md`
│  ├─ `debug_crash.py`
│  ├─ `debug_dialog_step_by_step.py`
│  ├─ `test_error_handler.py`
│  └─ `test_load_multiple_saves.py`
│
├─ game/
│  ├─ `player_status.py`
│  ├─ `ship_state.py`
│  ├─ `travel.py`
│  └─ `travel_flow.py`
│
├─ game_controller/
│  ├─ `__init__.py`
│  ├─ `config.py`
│  ├─ `logging.py`
│  ├─ `newgame_create.py`
│  ├─ `sim_loop.py`
│  └─ `sim_tasks.py`
│
├─ save/
│  ├─ `save_manager.py`
│  ├─ `models.py`
│  ├─ `paths.py`
│  ├─ `serializers.py`
│  ├─ `icon_paths.py`
│  ├─ `ui_config.py`
│  └─ `ui_state_tracer.py`
│
├─ settings/
│  └─ `system_config.py`
│
└─ ui/
  ├─ `__init__.py`
  ├─ `main_window.py`
  ├─ `constants.py`
  ├─ `error_handler.py`
  ├─ `error_utils.py`
  │
  ├─ controllers/
  │  ├─ `__init__.py`
  │  ├─ `galaxy_location_presenter.py`
  │  ├─ `map_actions.py`
  │  └─ `system_location_presenter.py`
  │
  ├─ dialogs/
  │  ├─ `error_reporter_dialog.py`
  │  ├─ `load_game_dialog.py`
  │  ├─ `new_game_dialog.py`
  │  └─ `save_as_dialog.py`
  │
  ├─ maps/
  │  ├─ `background_view.py`
  │  ├─ `galaxy.py`
  │  ├─ `galaxy_leadline.py`
  │  ├─ `icons.py`
  │  ├─ `system.py`
  │  ├─ `system_leadline.py`
  │  └─ `tabs.py`
  │
  ├─ menus/
  │  ├─ `file_menu.py`
  │  └─ `view_menu.py`
  │
  ├─ state/
  │  ├─ `lead_line_prefs.py`
  │  ├─ `main_window_state.py`
  │  ├─ `ui_state_manager.py`
  │  └─ `window_state.py`
  │
  ├─ utils/
  │  └─ `docks.py`
  │
  └─ widgets/
    ├─ `galaxy_system_list.py`
    ├─ `log_panel.py`
    ├─ `status_sheet.py`
    └─ `system_location_list.py`
```

## Notes

- **main.py** — QApplication startup + MainWindow creation.
- **requirements.txt** — Python dependencies.
- **data/** — SQLite access, schema, and initial seed helpers.
- **data/db.py** — DB access layer (connections, queries, pragmas).
- **data/schema.sql** — Authoritative SQLite schema.
- **data/seed.py** — Initial seed logic (only on fresh DB).
- **data/schema.sql** — Authoritative SQLite schema. (Recent change: resource metadata merged into `locations` with columns `resource_type`, `richness`, `regen_rate`; the standalone `resource_nodes` table was removed.)
- **data/seed.py** — Initial seed logic (only on fresh DB). (Recent change: resource entries in the seed are applied directly to `locations`.)
- **database/** — Generated database files (runtime).
- **docs/** — Project documentation.
- **game/** — Game logic (status, travel).
- **game/player_status.py** — Builds status snapshot; includes temporary ship state override.
- **game/ship_state.py** — Holds temporary, visual‑only ship state for transitions.
- **game/travel.py** — Travel math, costs, and display data.
- **game/travel_flow.py** — Orchestrates multi‑phase travel with fuel drip and status updates.
- **save/** — Save/load I/O, models, and paths.
- **save/save_manager.py** — Save lifecycle (new/save/save‑as/load hooks).
- **save/models.py** — Dataclasses for save state.
- **save/paths.py** — Filesystem paths.
- **save/serializers.py** — Serialization helpers.
- **save/icon_paths.py** — Deterministic icons for save slots.

## Notes on save behavior and icons

- New‑save flow runs a deterministic "bake" (`save/icon_paths.py:bake_icon_paths`) after seeding; this populates `systems.icon_path` and `locations.icon_path`, including resource locations (the bake uses `locations.resource_type` when `location_type=='resource'`).
- User-selected icons are persisted into `locations.icon_path` so the same asset is used on subsequent loads.
- **ui/** — UI (Qt widgets, maps, panels, menus).
- **ui/main_window.py** — Main window, docks, and wiring for all UI components.
- **ui/constants.py** — Centralized UI constants and shared values.
- **ui/error_handler.py** — Global error handling and crash reporting system.
- **ui/error_utils.py** — Error handling decorators and utility functions.
- **ui/controllers/** — UI logic controllers that mediate between widgets and game state.
- **ui/dialogs/** — Qt dialogs (new/load/save/error reporting).
- **ui/menus/file_menu.py** — File menu actions (New, Load, Save, Close Game).
- **ui/menus/view_menu.py** — View menu toggles with Show All/Hide All functionality.
- **ui/maps/** — Map views and infrastructure.
- **ui/widgets/** — Reusable panels and widgets.



## Brief per‑file descriptions

### Top level

- `main.py` — Entrypoint; instantiates `QApplication`, applies app‑wide settings, constructs `MainWindow`.
- `requirements.txt` — Pinned third‑party packages (PySide6); keep in sync with supported versions.

### data/

- `db.py` — Creates SQLite connections with `foreign_keys=ON`, `journal_mode=WAL`, `synchronous=NORMAL`; exposes query helpers and transactions.
- `schema.sql` — Source of truth for tables, indexes, and `PRAGMA user_version`.
- `seed.py` — Seeds a fresh DB deterministically from `universal_seed.json`.
- `universal_seed.json` — Declarative seed content shared across tests/new games.

### database/

- `game.db` — The runtime database; not checked in.

### assets/

- `asteroid_fields/` — Sprites for asteroid field nodes.
- `crystal_veins/` — Sprites for crystal vein nodes.
- `ice_fields/` — Sprites for ice field nodes.
- `gas_clouds/` — Sprites for gas cloud nodes.
- `planets/`, `moons/`, `stars/`, `stations/`, `warpgates/` — Body and structure sprites.
- `galaxy_backgrounds/`, `system_backgrounds/` — Parallax/skybox images.

### docs/

- `structure.md` — This document.
- `project_status.md` — Running status of implemented/planned features.  
- `ui_state_management.md` — Documentation of the UI state persistence system.
- `error_handling.md` — Documentation of the global error handling system.
- `VIEW_MENU_FIX.md` — Technical documentation of the View menu Show All/Hide All fix.

### tests/

- `README.md` — Documentation of test files and usage.
- `debug_crash.py` — Debug script to reproduce crashes when loading games with multiple saves.
- `debug_dialog_step_by_step.py` — Step-by-step debug tool for LoadGameDialog creation issues.
- `test_error_handler.py` — Test suite for the global error handling system.
- `test_load_multiple_saves.py` — Test script to verify Load Game Dialog functionality with existing saves.

### game/

- `player_status.py` — Aggregates player/system/ship info for UI consumption.
- `ship_state.py` — Transient ship state for transitions and animations.
- `travel.py` — Computes routes, fuel/time costs, and presentation data.
- `travel_flow.py` — Stepwise travel orchestrator; emits updates for UI.

### save/

- `save_manager.py` — High‑level save/load orchestration; debounces writes; handles Save As and slot management.
- `models.py` — Typed models describing persisted save state.
- `paths.py` — Resolves user‑space directories for saves/config.
- `serializers.py` — (De)serialization helpers for save payloads.
- `icon_paths.py` — Maps save metadata to stable icon file paths.

### game_controller/

- `__init__.py` — Package marker.
- `config.py` — Launch/configuration options consumed by controller & UI.
- `logging.py` — Logging configuration and helpers (no `print()` in operational code).
- `newgame_create.py` — New‑game bootstrap: DB creation + initial entities.
- `sim_loop.py` — Ticks the simulation; coordinates background workers/threads.
- `sim_tasks.py` — Discrete simulation tasks run by the loop/thread‑pool.

### ui/

- `__init__.py` — Package marker.
- `main_window.py` — Main window; docks, menus, map widgets; signal/slot wiring.
- `constants.py` — Paths, sizes, enums used across the UI.

### ui/controllers/

- `__init__.py` — Package marker.
- `galaxy_location_presenter.py` — Adapts galaxy‑level DB rows to widget‑ready models.
- `map_actions.py` — Shared actions/commands for map UIs (zoom, center, selection).
- `system_location_presenter.py` — Adapts system‑level locations/resources for system map.

### ui/dialogs/

- `error_reporter_dialog.py` — Modal dialog for displaying and reporting application errors.
- `load_game_dialog.py` — Modal for selecting and loading save slots.
- `new_game_dialog.py` — Modal for new game name/seed selection.
- `save_as_dialog.py` — Modal for cloning to a new save slot/name.

### ui/menus/

- `file_menu.py` — File operations (New, Load, Save, Save As, Close Game, Exit).
- `view_menu.py` — View toggles and panel visibility controls with Show All/Hide All functionality.

### ui/maps/

- `galaxy.py` — Galaxy map widget and rendering pipeline.
- `icons.py` — Icon loading/cataloging helpers for map entities.
- `background.py` — Parallax/starfield background loaders (galaxy/system).
- `system.py` — System map widget; renders bodies and resource nodes (uses plural resource asset dirs).
- `tabs.py` — Map tab container & tab‑switching logic.
- `galaxy_leadline.py` — Lead lines and selection overlay for galaxy map.
- `system_leadline.py` — Lead lines and selection overlay for system map.

### ui/state/

- `window_state.py` — Persist/restore window geometry and dock layout.
- `main_window_state.py` — Aggregates top‑level UI state; emits change signals.
- `lead_line_prefs.py` — User preferences for lead‑line appearance/behavior.

### ui/utils/

- `docks.py` — Helpers for creating/managing dock widgets.

### ui/widgets/

- `galaxy_system_list.py` — Sidebar tree for systems/locations.
- `status_sheet.py` — Player/ship/system status panel.
- `system_location_list.py` — System‑level location/resource list.
