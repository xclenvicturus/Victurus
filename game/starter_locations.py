from __future__ import annotations
from typing import List

def list_starting_locations() -> List[str]:
    # Keep aligned with data/seed: systems named Sys-01..Sys-10, planets "Planet 1..6"
    # We present one planet per system for simplicity.
    labels = [f"Sys-{i:02d} • Planet 1" for i in range(1, 11)]
    return labels
