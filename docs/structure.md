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
│ └─ game.db
└─ docs/
│ └─ structure.md
└─ game/
│ └─ load_game.py
│ └─ new_game.py
│ └─ player_status.py
│ └─ ship_state.py
│ └─ starter_locations.py
│ └─ travel.py
└─ save/
│ └─ manager.py
│ └─ models.py
│ └─ paths.py
│ └─ serializers.py
└─ ui/
└─ init.py
└─ main_window.py
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
│ └─ panzoom_view.py
│ └─ solar.py
│ └─ tabs.py
└─ state/
│ └─ window_state.py
└─ utils/
│ └─ symbols.py
└─ widgets/
└─ location_list_panel.py
└─ overlays.py
└─ status_sheet.py


## Notes

- **main.py** — QApplication startup + MainWindow creation  
- **requirements.txt** — Python dependencies  
- **data/** — SQLite access, schema, and initial seed helpers  
- **data/db.py** — DB access layer (connection, queries, icon assignment)  
- **data/schema.sql** — Authoritative SQLite schema  
- **data/seed.py** — Initial seed logic (only on fresh DB)  
- **database/** — Generated database files (runtime)  
- **database/game.db** — SQLite runtime database  
- **docs/** — Project documentation  
- **docs/structure.md** — This document  
- **game/** — Game logic (status, travel, new/load game)  
- **game/player_status.py** — Builds status snapshot; includes temporary ship state override  
- **game/ship_state.py** — Holds temporary, visual-only ship state for transitions  
- **game/travel.py** — Travel math, costs, and display data + execution  
- **game/new_game.py** — New-game setup routines  
- **game/load_game.py** — Load-game routines  
- **game/starter_locations.py** — Example starter locations (seed helpers)  
- **save/** — Save/load I/O, models, and paths  
- **save/manager.py** — Save lifecycle (new/save/save-as/load hooks)  
- **save/models.py** — Dataclasses / structures for save state  
- **save/paths.py** — Filesystem paths (Documents/Victurus_game/*)  
- **save/serializers.py** — Serialization helpers  
- **ui/** — UI (Qt widgets, maps, panels, menus)  
- **ui/main_window.py** — Main window, docks, log panel and map view wiring  
- **ui/dialogs/** — Qt dialogs (new/load/save)  
- **ui/menus/file_menu.py** — File menu actions  
- **ui/state/window_state.py** — Window size/position persistence  
- **ui/utils/symbols.py** — Icon/symbol utilities  
- **ui/widgets/** — Reusable panels and overlays  
- **ui/widgets/status_sheet.py** — Commander/ship readouts; displays ship_state  
- **ui/widgets/location_list_panel.py** — Right-side list with search/sort, distance/jump/fuel columns  
- **ui/widgets/overlays.py** — Hover leader-line overlay  
- **ui/maps/** — Map views and infrastructure  
- **ui/maps/panzoom_view.py** — Scene/View with starfields + leader line overlay  
- **ui/maps/galaxy.py** — GalaxyMapWidget (star GIFs, parallax background)  
- **ui/maps/solar.py** — SolarMapWidget (star/planet/station GIFs, orbit dynamics, get_entities())  
- **ui/maps/highlighting.py** — Selection/highlight visuals  
- **ui/maps/tabs.py** — Galaxy/Solar tabs + travel sequencing (Undock/Leave → Traveling → Enter/Dock)  
- **Travel status sequence** — When you initiate a jump or intra-system move, the UI drives a temporary ship state: **Un-docking…** (if Docked) or **Leaving Orbit…** (if Orbiting) for 10s → **Traveling** (duration scales with distance) → **Entering Orbit…** (planet/star) or **Docking…** (station) for 10s, then clears to the real state.
