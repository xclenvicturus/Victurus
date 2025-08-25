# Victurus – Living Feature Checklist

## Legend

- 🟩 = verified working in-game
- 🟨 = implemented now (scaffolded or basic behavior present)
- 🟥 = not implemented yet

## Core / App Shell

- 🟩 **PySide6 app entry + MainWindow** (menus, status bar, close handling)
- 🟩 **Settings + window state persistence (Qt)** (save/restore geometry, dock visibility)
- 🟥 **Hotkeys** (global shortcuts mapped to actions)

## Game Loop

- 🟩 **New Game** (dialog, initial save creation, player setup)
- 🟩 **Load Game** (dialog, loading from save file)
- 🟩 **Save Game / Save As** (persisting current game state)
- 🟩 **Travel System** (player can move between systems and locations)
- 🟩 **Fuel Mechanic** (travel consumes fuel)
- 🟥 **Economy / Markets** (buy/sell goods)
- 🟥 **Ship Upgrades** (purchase new ships or components)
- 🟥 **Missions / Quests**

## UI Components

- 🟩 **Galaxy Map** (displays systems)
- 🟩 **System Map** (displays planets, stations within a system)
- 🟩 **Location List** (filterable, sortable list of destinations)
- 🟩 **Status Panel** (shows player, ship, and resource info)
- 🟩 **Log Panel** (displays game messages)
- 🟩 **Leader Line** (visual aid connecting list to map)

## Improvements to pursue next

- **Implement Economy:** The database schema supports markets, but there is no UI to interact with them. A trading screen would be a natural next step.
- **Add Ship Stats:** The `ships` table in the database includes columns for shields, energy, and hull, but these are not yet used in gameplay.
- **Introduce Game Events:** The game world is currently static. Adding random events, such as pirate encounters or fluctuating market prices, would enhance gameplay.

## Possible additions

- **Ship Combat:** A system for ship-to-ship combat.
- **Main Quest:** A central storyline to guide the player through the game.
- **Factions:** Introduce different factions with which the player can build or lose reputation.

Appendix: Inventory & Graph (JSON)

```json
{
  "files": [
    {
      "path": "data/db.py",
      "module": "data.db",
      "symbols": [
        {"name": "_active_db_path_override", "kind": "const", "lines": "13-13", "references": 2},
        {"name": "set_active_db_path", "kind": "func", "lines": "15-17", "references": 1},
        {"name": "get_active_db_path", "kind": "func", "lines": "19-20", "references": 1},
        {"name": "_connection", "kind": "const", "lines": "31-31", "references": 4},
        {"name": "_is_connection_open", "kind": "func", "lines": "33-38", "references": 2},
        {"name": "_open_new_connection", "kind": "func", "lines": "40-46", "references": 1},
        {"name": "get_connection", "kind": "func", "lines": "48-57", "references": 1},
        {"name": "_ensure_schema_and_seed", "kind": "func", "lines": "59-69", "references": 1},
        {"name": "close_active_connection", "kind": "func", "lines": "71-76", "references": 1},
        {"name": "_ensure_icon_column", "kind": "func", "lines": "78-82", "references": 1},
        {"name": "_ensure_system_star_column", "kind": "func", "lines": "84-88", "references": 1},
        {"name": "_assign_location_icons_if_missing", "kind": "func", "lines": "90-112", "references": 1},
        {"name": "_assign_system_star_icons_if_missing", "kind": "func", "lines": "114-129", "references": 1},
        {"name": "get_counts", "kind": "func", "lines": "131-137", "references": 1},
        {"name": "get_systems", "kind": "func", "lines": "139-140", "references": 1},
        {"name": "get_system", "kind": "func", "lines": "142-144", "references": 1},
        {"name": "get_locations", "kind": "func", "lines": "146-148", "references": 1},
        {"name": "get_location", "kind": "func", "lines": "150-152", "references": 1},
        {"name": "get_warp_gate", "kind": "func", "lines": "154-159", "references": 1},
        {"name": "set_player_system", "kind": "func", "lines": "161-164", "references": 1},
        {"name": "set_player_location", "kind": "func", "lines": "166-169", "references": 1},
        {"name": "get_player_full", "kind": "func", "lines": "171-173", "references": 1},
        {"name": "get_player_summary", "kind": "func", "lines": "175-177", "references": 0},
        {"name": "get_player_ship", "kind": "func", "lines": "179-182", "references": 1}
      ],
      "imports": ["random", "sqlite3", "pathlib", "typing", "ui.maps.icons"]
    }
  ],
  "graph": []
}
