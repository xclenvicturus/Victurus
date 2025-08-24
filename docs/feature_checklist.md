# /docs/feature_checklist.md

# Victurus – Living Feature Checklist

**Legend**
- 🟨 = implemented now (scaffolded or basic behavior present)
- 🟥 = not implemented yet
- 🟩 = verified working in-game (flip to green once you confirm)

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