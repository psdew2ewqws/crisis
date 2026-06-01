"""Emit events — in v1 without Redis, just log. With Redis, publish to channel."""
from datetime import datetime, timezone

_listeners: list = []


def emit(case_id: str, step: str, event: str, data: dict):
    """Publish a case.step event."""
    frame = {
        "channel": f"case:{case_id}",
        "event": f"{step}.{event}",
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    # In-memory broadcasting (no Redis in v1)
    for listener in _listeners:
        try:
            listener(frame)
        except Exception:
            pass


def add_listener(fn):
    _listeners.append(fn)
