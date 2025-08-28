# /save/models.py

from __future__ import annotations
from dataclasses import dataclass, asdict, fields
from typing import Any, Dict

@dataclass
class SaveMetadata:
    save_name: str
    commander_name: str
    created_iso: str
    last_played_iso: str
    game_version: str = "0.1"
    notes: str = ""
    # Art/Rendering flags
    db_icons_only: bool = True  # when True, renderers must not use runtime fallbacks

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SaveMetadata":
        # Tolerate unknown keys from older/newer versions
        allowed = {f.name for f in fields(SaveMetadata)}
        filtered: Dict[str, Any] = {k: d[k] for k in d.keys() if k in allowed}
        return SaveMetadata(**filtered)
