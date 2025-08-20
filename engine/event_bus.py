from __future__ import annotations
from typing import Callable, Dict, List, Any

class EventBus:
    """Tiny pub/sub for decoupling controllers and views."""
    def __init__(self):
        self._handlers: Dict[str, List[Callable[..., None]]] = {}

    def on(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable[..., None]) -> None:
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h is not handler]

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for handler in list(self._handlers.get(event, [])):
            try:
                handler(*args, **kwargs)
            except Exception:
                # Keep the bus resilient; swallow handler errors.
                pass
