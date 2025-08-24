# docs/feature_checklist.md

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
- 🟨 **Travel System** (player can move between systems and locations)
- 🟨 **Fuel Mechanic** (travel consumes fuel)
- 🟥 **Economy / Markets** (buy/sell goods)
- 🟥 **Ship Upgrades** (purchase new ships or components)
- 🟥 **Missions / Quests**

## UI Components
- 🟩 **Galaxy Map** (displays systems)
- 🟩 **System Map** (displays planets, stations within a system)
- 🟩 **Location List** (filterable, sortable list of destinations)
- 🟩 **Status Panel** (shows player, ship, and resource info)
- 🟩 **Log Panel** (displays game messages)
- 🟨 **Leader Line** (visual aid connecting list to map)

## Improvements to pursue next
- **Implement Economy:** The `markets` table exists but there is no UI to interact with it. Building a trade screen would be the next logical feature.
- **Flesh out Ship Stats:** The `ships` table has stats like shields and energy, but they are not used in gameplay yet. Travel is the only core mechanic implemented.
- **Add Game Events:** The universe is static. Adding random events, pirate encounters, or dynamic market prices would make the game more engaging.
- **Refine UI State Saving:** The `save/manager.py` now supports saving UI state per-save file. This should be expanded to include things like the last selected item in the location list or map zoom levels.

## Possible additions
- **Ship Combat:** A turn-based or real-time combat system.
- **Storyline:** A main quest to guide the player through the galaxy.
- **Factions:** Different groups with reputations that the player can influence.
- **Crafting/Mining:** Allow players to gather resources and build items.