# Victurus — AI Map (v1)
_Last updated: 2025-08-19 (America/Chicago)_

## Repository
- Name: `Victurus`
- URL: https://github.com/xclenvicturus/Victurus
- Language: Python
- OS target: Windows
- GUI: Tkinter

## Overview
Victurus appears to be a text-based (with Tkinter windows) space RPG. The application logic lives in the `engine/` package with `main.py` as the entry point at the repo root. This Map is a living document: **on each AI-assisted change**, the assistant must re-scan the repository and update this file.

## Discovered Top-Level Files & Folders
- `main.py` — program entry point (run with `python main.py`).  *(Confirmed on GitHub listing)*  
- `__init__.py` — root package shim.  *(Confirmed on GitHub listing)*  
- `engine/` — core package containing game logic and UI components.  *(Folder present; contents could not be enumerated in this session due to GitHub page error)*

> Source: GitHub repo UI successfully shows these top-level entries; inner file bodies did not render in this session.

## Known / Inferred Modules (from local error logs & naming)
- `engine/window_togglers.py` — toggles Tk windows; opens `QuestsWindow` via a dispatcher function (from a Tkinter traceback the user shared previously).
- `QuestsWindow` (class) — a Tkinter window for managing/displaying quests.
- Additional likely modules (to be confirmed on next pass):
  - `engine/windows/` or `engine/ui/` subpackage holding individual Tk windows (`quests.py`, etc.).
  - `engine/state.py` or similar for central game state.
  - `engine/persistence.py` or similar for save/load (autosave).
  - `engine/commands.py` or `engine/input.py` for command parsing / input handling.
  - `engine/entities/` for player/NPC models if the project expands.

**Action:** On the next pass when GitHub renders properly (or with a zip), enumerate `engine/` and replace this bullet list with exact filenames and 1–3 line summaries for each module/class/function.

## Execution & Data Flow (to refine)
1. **Startup**: `python main.py` initializes root Tk context and engine subsystems.
2. **UI**: Tkinter windows are opened/toggled via `window_togglers` helpers; `QuestsWindow` is one such window.
3. **Game Loop/State**: A central state object (or module-level globals) used by windows and systems. *(Confirm exact object names on next pass.)*
4. **Persistence**: Autosave or frequent saves to prevent data loss (design goal). *(Confirm file paths and format.)*

## Dependencies & Environment
- **Python**: Targeting 3.13 (based on your environment). Confirm pinned version if `requirements.txt`/`pyproject.toml` appears.
- **GUI**: Tkinter (standard library).
- **OS**: Windows (paths and focus handling in Tk/Win32).

## Conventions
- Match existing style (imports, naming, formatting).
- Windows-friendly paths.
- Prefer small, well-scoped modules in `engine/`.

## Map Maintenance Checklist (run each AI task)
1. Re-read repo tree (root + `engine/`) and update this file.
2. For each module, document:
   - Purpose
   - Key classes/functions
   - Important imports (internal/external)
3. Update **Run Steps** and **Validation** sections below if they change.

## Run Steps
```bash
python main.py