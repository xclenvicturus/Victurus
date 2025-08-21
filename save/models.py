from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any

@dataclass
class SaveMetadata:
    save_name: str
    commander_name: str
    created_iso: str
    last_played_iso: str
    game_version: str = "0.1"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SaveMetadata":
        return SaveMetadata(**d)
