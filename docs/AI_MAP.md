# Victurus — AI Map (v0)

_Last updated: {{fill on edit}}_

## Repository
- Name: `Victurus`
- URL: https://github.com/xclenvicturus/Victurus
- Language: Python
- Platform: Windows
- GUI: Tkinter

## High-Level Overview
Victurus is a text-based (with Tkinter windows) space RPG. The application logic lives in the `engine/` package with a `main.py` entry point at the repo root. This map should be **expanded on each AI-assisted change** after re-reading the repository.

## Entry Points
- `main.py` — program entry (invoked via `python main.py`).

## Packages & Modules (initial)
- `engine/` — core package.
  - [TBD expand] Enumerate submodules and their purposes.
  - Known from user logs: UI window toggling via `engine/window_togglers.py` and a `QuestsWindow` class (Tkinter-based).

> Replace each TBD with concrete findings after walking the tree.

## Data Flow (to refine)
- UI layer: Tkinter windows (e.g., Quests UI).
- Game loop/state: [TBD after reading engine modules]
- Persistence: [TBD] (identify any save files, autosave behavior, and I/O)

## Conventions
- Python: 3.13 (adjust if repo pins a different version)
- Style: Match existing import order, naming, and formatting
- OS assumptions: Windows paths in local runs

## Next Actions for AI
1. **Enumerate tree:** List every file and subpackage under `engine/`, `tests/` (if present), and any config/scripts.
2. **Summarize modules:** For each module, jot a 1–3 line summary of its responsibilities and key classes/functions.
3. **Map dependencies:** Capture import relationships between modules.
4. **Record run steps:** Note commands to run (and any required environment setup).
5. **Keep updated:** On each task, refresh this file with any new or changed modules.

## Run / Validation
- Run: `python main.py`
- Quick sanity: [TBD] Add minimal steps (e.g., launch main window, open Quests window, perform an action).