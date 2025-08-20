# Marks "engine" as a package and re-exports GameApp for convenient imports.

from .game_app import GameApp

__all__ = ["GameApp"]
