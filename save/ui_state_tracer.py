# /save/ui_state_tracer.py

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional

from .paths import get_config_dir

# Set to False to disable UI state debug tracing
ENABLE_TRACING = False

def _trace_path() -> Path:
    return get_config_dir() / "ui_state_trace.log"


def append_event(event: str, detail: Optional[str] = None) -> None:
    if not ENABLE_TRACING:
        return
        
    try:
        p = _trace_path()
        ts = datetime.utcnow().isoformat()
        line = f"{ts} {event}"
        if detail:
            line += f" {detail}"
        line += "\n"
        p.parent.mkdir(parents=True, exist_ok=True)
        # Append small text; ignore any errors to avoid affecting UI
        with p.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Best-effort only; swallow exceptions
        pass
