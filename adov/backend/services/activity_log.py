from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

_log: deque[dict] = deque(maxlen=200)
_PST = ZoneInfo("America/Los_Angeles")


def log_event(event_type: str, **data) -> None:
    _log.appendleft({
        "ts": datetime.now(_PST).isoformat(timespec="seconds"),
        "event": event_type,
        **data,
    })


def get_events(limit: int = 50) -> list[dict]:
    return list(_log)[:limit]


def clear_events() -> None:
    _log.clear()
