# Victurus — Project Structure (updated 2025-08-28)

This document summarizes the repository layout and what each part is responsible for.

## Key modules

- **UI (`ui/`)** — Widgets, panels, and map views (galaxy/solar) built with PySide6.
- **Game (`game/`)** — Player snapshot, ship state, travel math, and game‑flow orchestration.
- **Data (`data/`)** — SQLite schema, seed helpers, and the runtime DB access layer.
- **Save (`save/`)** — Save‑game models, paths, serialization, and lifecycle management.
- **Docs (`docs/`)** — Developer‑facing documentation.
- **Assets (`assets/`)** — Star, planet, station, and other art assets (GIF/PNG) organized by type (e.g., `assets/planets/p01.gif`). The UI selects deterministic assets per system/location so thumbnails match the map.

## Tree

Victurus/
│
├─ `main.py`
├─ `requirements.txt`
│
├─ data/
│  ├─ `db.py`
│  ├─ `schema.sql`
│  ├─ `seed.py`
│  └─ `universal_seed.json`
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
│  ├─ warpgates/
│  │  └─ `w01.gif`
│  ├─ galaxy_backgrounds/
│  │  └─ `default.png`
│  └─ solar_backgrounds/
│     └─ `system_bg_01.png`
│
├─ docs/
│  ├─ `structure.md`
│  └─ `feature_checklist.md`
│
├─ game/
│  ├─ `player_status.py`
│  ├─ `ship_state.py`
│  ├─ `travel.py`
│  └─ `travel_flow.py`
│
├─ save/
│  ├─ `save_manager.py`
│  ├─ `models.py`
│  ├─ `paths.py`
│  ├─ `serializers.py`
│  └─ `icon_paths.py`
│
├─ game_controller/
│  ├─ `__init__.py`
│  ├─ `config.py`
│  ├─ `logging.py`
│  ├─ `newgame_create.py`
│  ├─ `sim_loop.py`
│  └─ `sim_tasks.py`
│
└─ ui/
  ├─ `__init__.py`
  ├─ `main_window.py`
  ├─ `constants.py`
  │
  ├─ controllers/
  │  ├─ `__init__.py`
  │  ├─ `galaxy_location_presenter.py`
  │  ├─ `map_actions.py`
  │  └─ `system_location_presenter.py`
  │
  ├─ dialogs/
  │  ├─ `load_game_dialog.py`
  │  ├─ `new_game_dialog.py`
  │  └─ `save_as_dialog.py`
  │
  ├─ menus/
  │  ├─ `file_menu.py`
  │  └─ `view_menu.py`
  │
  ├─ maps/
  │  ├─ `galaxy.py`
  │  ├─ `icons.py`
  │  ├─ `background.py`
  │  ├─ `solar.py`
  │  ├─ `tabs.py`
  │  ├─ `galaxy_leadline.py`
  │  └─ `system_leadline.py`
  │
  ├─ state/
  │  ├─ `window_state.py`
  │  ├─ `main_window_state.py`
  │  └─ `lead_line_prefs.py`
  │
  ├─ utils/
  │  └─ `docks.py`
  │
  └─ widgets/
    ├─ `galaxy_system_list.py`
    ├─ `status_sheet.py`
    └─ `system_location_list.py`

## Notes

- **main.py** — QApplication startup + MainWindow creation.
- **requirements.txt** — Python dependencies.
- **data/** — SQLite access, schema, and initial seed helpers.
- **data/db.py** — DB access layer (connections, queries, pragmas).
- **data/schema.sql** — Authoritative SQLite schema.
- **data/seed.py** — Initial seed logic (only on fresh DB).
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
- **ui/** — UI (Qt widgets, maps, panels, menus).
- **ui/main_window.py** — Main window, docks, and wiring for all UI components.
- **ui/constants.py** — Centralized UI constants (sizes, fonts, asset roots).
- **ui/controllers/** — UI logic controllers that mediate between widgets and game state.
- **ui/dialogs/** — Qt dialogs (new/load/save).
- **ui/menus/file_menu.py** — File menu actions.
- **ui/menus/view_menu.py** — View/menu toggles.
- **ui/maps/** — Map views and infrastructure.
- **ui/widgets/** — Reusable panels and widgets.

---

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
- `galaxy_backgrounds/`, `solar_backgrounds/` — Parallax/skybox images.

### docs/

- `structure.md` — This document.
- `feature_checklist.md` — Running checklist of implemented/planned features.

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
- `system_location_presenter.py` — Adapts system‑level locations/resources for solar map.

### ui/dialogs/

- `load_game_dialog.py` — Modal for selecting and loading save slots.
- `new_game_dialog.py` — Modal for new game name/seed selection.
- `save_as_dialog.py` — Modal for cloning to a new save slot/name.

### ui/menus/

- `file_menu.py` — File operations (New, Load, Save, Save As, Exit).
- `view_menu.py` — View toggles and developer options.

### ui/maps/

- `galaxy.py` — Galaxy map widget and rendering pipeline.
- `icons.py` — Icon loading/cataloging helpers for map entities.
- `background.py` — Parallax/starfield background loaders (galaxy/solar).
- `solar.py` — System map widget; renders bodies and resource nodes (uses plural resource asset dirs).
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
