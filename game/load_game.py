# /game/load_game.py

from __future__ import annotations
from pathlib import Path
from save.manager import SaveManager

def load_existing_game(save_dir: Path) -> None:
    SaveManager.load_save(save_dir)
