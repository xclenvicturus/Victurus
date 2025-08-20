import os
import sys
from pathlib import Path

# Ensure we can import the local "engine" package when running this file directly.
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the package root (engine/__init__.py re-exports GameApp).
from engine import GameApp

def default_saves_root() -> str:
    """
    Returns Documents/Victurus_Game/Saves (creates it if missing).
    Windows/macOS/Linux friendly.
    """
    home = Path.home()
    docs = home / "Documents"
    if not docs.exists():
        docs = home / "My Documents"
    base = docs / "Victurus_Game" / "Saves"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def main():
    saves_root = default_saves_root()
    # Start the game using per-slot saves rooted at Documents/Victurus_Game/Saves
    app = GameApp(save_root_dir=saves_root, slot_name=None)  # None => show idle UI until New/Load
    app.run()


if __name__ == "__main__":
    main()
