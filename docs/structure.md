# Victurus — Project Structure (updated 2025-08-22)

This document summarizes the repository layout and what each part is responsible for.

**Key modules:**
- **UI (`ui/`)**: Widgets, panels, and map views (galaxy/solar) built with PySide6.
- **Game (`game/`)**: Player snapshot, ship state, travel math, and new/load routines.
- **Data (`data/`, `database/`)**: SQLite schema, seed helpers, and the runtime DB file.
- **Save (`save/`)**: Save-game models, paths, and serialization.
- **Docs (`docs/`)**: Developer-facing documentation.

**Assets (optional):** star/planet/station GIFs are expected under an `assets/` directory parallel to the codebase (e.g., `assets/planets/p01.gif`). The UI selects deterministic GIFs per system/location so list thumbnails match the map.

## Tree

Victurus/
└─ main.py
│ └─ requirements.txt
└─ data/
│ └─ db.py
│ └─ schema.sql
│ └─ seed.py
└─ database/
│ └─ .gitignore  (contains game.db)
└─ docs/
│ └─ structure.md
│ └─ feature_checklist.md
└─ game/
│ └─ load_game.py
│ └─ new_game.py
│ └─ player_status.py
│ └─ ship_state.py
│ └─ starter_locations.py
│ └─ travel.py
│ └─ travel_flow.py
└─ save/
│ └─ manager.py
│ └─ models.py
│ └─ paths.py
│ └─ serializers.py
└─ ui/
  └─ __init__.py
  └─ main_window.py
  └─ constants.py
  └─ controllers/
  │ └─ __init__.py
  │ └─ leadline_controller.py
  │ └─ location_presenter.py
  │ └─ map_actions.py
  └─ dialogs/
  │ └─ load_game_dialog.py
  │ └─ new_game_dialog.py
  │ └─ save_as_dialog.py
  └─ menus/
  │ └─ file_menu.py
  └─ maps/
  │ └─ galaxy.py
  │ └─ highlighting.py
  │ └─ icons.py
  │ └─ leadline.py
  │ └─ panzoom_view.py
  │ └─ solar.py
  │ └─ tabs.py
  └─ state/
  │ └─ window_state.py
  └─ utils/
  │ └─ symbols.py
  └─ widgets/
    └─ location_list.py
    └─ status_sheet.py


## Notes

- **main.py** — QApplication startup + MainWindow creation
- **requirements.txt** — Python dependencies
- **data/** — SQLite access, schema, and initial seed helpers
- **data/db.py** — DB access layer (connection, queries, icon assignment)
- **data/schema.sql** — Authoritative SQLite schema
- **data/seed.py** — Initial seed logic (only on fresh DB)
- **database/** — Generated database files (runtime)
- **database/.gitignore** — Ensures `game.db` is not tracked
- **docs/** — Project documentation
- **game/** — Game logic (status, travel, new/load game)
- **game/player_status.py** — Builds status snapshot; includes temporary ship state override
- **game/ship_state.py** — Holds temporary, visual-only ship state for transitions
- **game/travel.py** — Travel math, costs, and display data
- **game/travel_flow.py** — Orchestrates multi-phase travel with fuel drip and status updates
- **game/new_game.py** — New-game setup routines
- **game/load_game.py** — Load-game routines
- **save/** — Save/load I/O, models, and paths
- **save/manager.py** — Save lifecycle (new/save/save-as/load hooks)
- **save/models.py** — Dataclasses for save state
- **save/paths.py** — Filesystem paths
- **save/serializers.py** — Serialization helpers
- **ui/** — UI (Qt widgets, maps, panels, menus)
- **ui/main_window.py** — Main window, docks, and wiring for all UI components
- **ui/controllers/** — UI logic controllers that mediate between widgets and game state
- **ui/dialogs/** — Qt dialogs (new/load/save)
- **ui/menus/file_menu.py** — File menu actions
- **ui/maps/** — Map views and infrastructure
- **ui/widgets/** — Reusable panels and widgets