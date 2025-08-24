# /save/serializers.py

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from .models import SaveMetadata

def write_meta(path: Path, meta: SaveMetadata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta.to_dict(), f, indent=2)

def read_meta(path: Path) -> Optional[SaveMetadata]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        d = json.load(f)
    try:
        return SaveMetadata.from_dict(d)
    except Exception:
        return None
