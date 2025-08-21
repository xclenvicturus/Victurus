Victurus/
├─ main.py                                 # entry point (boot to idle; File menu enabled only)
├─ requirements.txt
│
├─ assets/                                 # (existing)
│  ├─ galaxy_backgrounds/
│  ├─ solar_backgrounds/
│  ├─ planets/
│  ├─ stars/
│  └─ stations/
│
├─ data/                                   # (mostly existing)
│  ├─ schema.sql                           # authoritative schema
│  ├─ seed.py                              # initial content generator
│  └─ db.py                                # DB layer (refactor to be path-agnostic; uses SaveManager.active_db)
│
├─ save/                                   # NEW — Save Manager & runtime I/O
│  ├─ __init__.py
│  ├─ manager.py                           # SaveManager: new/load/save, active save context, file locks
│  ├─ paths.py                             # Documents/Victurus_game resolution; create dirs; cross-platform
│  ├─ models.py                            # dataclasses (SaveMetadata: name, commander, created, lastPlayed, version)
│  ├─ serializers.py                       # helper to persist meta.json; future snapshots/screens
│  └─ migrations.py                        # optional: schema bumps per save version
│
├─ game/                                   # NEW — game lifecycle glue
│  ├─ __init__.py
│  ├─ new_game.py                          # create per-save DB, run schema+seed, place player at start
│  ├─ load_game.py                         # open existing save, sanity checks
│  └─ starter_locations.py                 # query/compose allowed starting positions for New Game dialog
│
├─ ui/
│  ├─ main_window.py                       # (existing) wire menus, idle state, hook window-state store
│  ├─ menus/                               # NEW — menu wiring separated for clarity
│  │  ├─ __init__.py
│  │  └─ file_menu.py                      # New Game | Save | Save As… | Load Game actions
│  ├─ dialogs/                             # NEW — user prompts
│  │  ├─ __init__.py
│  │  └─ new_game_dialog.py                # Save File Name, Commander Name, Starting Location, Accept/Cancel
│  ├─ state/                               # NEW — UI/window persistence
│  │  ├─ __init__.py
│  │  └─ window_state.py                   # saves per-window geometry & open/closed flags to Documents/
│  └─ maps/                                # (existing)
│     ├─ galaxy.py
│     ├─ solar.py
│     ├─ panzoom_view.py
│     ├─ overlays.py
│     ├─ panels.py
│     ├─ icons.py
│     ├─ symbols.py
│     └─ tabs.py
│
└─ tools/                                   # OPTIONAL — dev utilities
   └─ sample_content.py                     # e.g., generate demo saves (not required for runtime)