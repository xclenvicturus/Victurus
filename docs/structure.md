# Victurus — Folder & File Structure

This structure groups code by responsibility: **UI**, **game logic**, **persistence**, **assets**, and **documentation**. UI is further split into dialogs, menus, panels (dockable widgets), maps (map-related widgets), and state helpers. Save management is isolated in `save/`. Database schema + seed live under `database/` and `data/`.

Victurus/
├─ app/ # (optional) App bootstrap/launcher if present
│ └─ main.py # QApplication startup & MainWindow creation
├─ ui/
│ ├─ init.py
│ ├─ main_window.py # QMainWindow (menu bar, docks, central map)
│ ├─ dialogs/
│ │ └─ new_game_dialog.py # "New Game" dialog (save name, commander, start loc)
│ ├─ menus/
│ │ └─ file_menu.py # File menu: New, Save, Save As, Load
│ ├─ panels/
│ │ └─ status_sheet.py # Status dock (player/ship readouts, text gauges)
│ ├─ maps/
│ │ ├─ tabs.py # MapView and tab orchestration
│ │ ├─ solar.py # Solar/system map & location list(s)
│ │ └─ highlighting.py # Selection list “current location” highlighter
│ └─ state/
│ ├─ init.py # Persist/restore helpers package marker
│ └─ window_state.py # Persist/restore window geometry, dock visibility
├─ game/
│ ├─ new_game.py # New game creation flow (DB + initial placement)
│ └─ starter_locations.py # Starting location labels/ids
├─ save/
│ ├─ manager.py # Save lifecycle: new/save/save-as/load hooks
│ └─ paths.py # Filesystem paths (Documents/Victurus_game/*)
├─ data/
│ ├─ db.py # DB access layer (connection, queries, status snapshot)
│ └─ seed.py # Initial seed logic (invoked on empty DB)
├─ database/
│ └─ schema.sql # Authoritative schema for SQLite
├─ assets/
│ ├─ planets/ # Optional images for location icons
│ ├─ stations/ # Optional images for location icons
│ └─ stars/ # Optional images for system star icons
└─ docs/
├─ STRUCTURE.md # This document
└─ CHANGELOG.md # (optional) Curated changes per feature set