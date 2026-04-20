# calendar_service.py — shared free/busy computation used by both the calendar route
# and the AI agent's inline availability check.
import logging
from datetime import datetime, timezone, timedelta

from services.firebase import (
    clear_user_calendar_token,
    get_trip_members,
    get_user,
    store_trip_availability,
)

logger = logging.getLogger(__name__)


def find_free_windows(
    busy_intervals_per_user: list[list[tuple[datetime, datetime]]],
    time_min: datetime,
    time_max: datetime,
    min_hours: int = 2,
) -> list[dict]:
    """Return windows where ALL users are simultaneously free (>= min_hours long)."""
    points: set[datetime] = {time_min, time_max}
    for user_busy in busy_intervals_per_user:
        for start, end in user_busy:
            if time_min <= start <= time_max:
                points.add(start)
            if time_min <= end <= time_max:
                points.add(end)

    free_windows: list[dict] = []
    for i, window_start in enumerate(sorted(points)[:-1]):
        window_end = sorted(points)[i + 1]
        if window_end <= window_start:
            continue
        if (window_end - window_start).total_seconds() / 3600 < min_hours:
            continue
        all_free = all(
            not (window_start < busy_end and window_end > busy_start)
            for user_busy in busy_intervals_per_user
            for busy_start, busy_end in user_busy
        )
        if all_free:
            free_windows.append({"start": window_start.strftime("%Y-%m-%d"), "end": window_end.strftime("%Y-%m-%d")})

    return free_windows


def query_user_freebusy(
    uid: str,
    token: str,
    time_min: datetime,
    time_max: datetime,
) -> list[tuple[datetime, datetime]] | None:
    """
    Query Google Calendar freebusy for a single user token.

    Returns a list of busy intervals on success (possibly empty), or None on any
    auth/token failure. On auth failure the stale token is cleared from Firestore.
    Callers should treat None as a token failure (expired or invalid).

    Raises ImportError if the Google client libraries are not installed.
    """
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.errors import HttpError  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
    from google.auth.exceptions import RefreshError  # type: ignore

    try:
        creds = Credentials(token=token)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        result = service.freebusy().query(body={
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": "primary"}],
        }).execute()
        busy_raw = result.get("calendars", {}).get("primary", {}).get("busy", [])
        return [
            (
                datetime.fromisoformat(item["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(item["end"].replace("Z", "+00:00")),
            )
            for item in busy_raw
        ]
    except RefreshError:
        logger.info(f"[calendar_service] no refresh token for uid={uid} — clearing stale access token")
        try:
            clear_user_calendar_token(uid)
        except Exception:
            pass
        return None
    except HttpError as exc:
        if exc.resp.status in (401, 403):
            logger.info(f"[calendar_service] token expired for uid={uid} — clearing")
            try:
                clear_user_calendar_token(uid)
            except Exception:
                pass
            return None
        else:
            logger.error(f"[calendar_service] HttpError for uid={uid}: {exc}", exc_info=True)
            return None
    except Exception as exc:
        logger.error(f"[calendar_service] error for uid={uid}: {exc}", exc_info=True)
        return None


def fetch_and_store_freebusy(trip_id: str, days: int = 90) -> list[dict]:
    """
    Query Google Calendar for all trip members, compute overlapping free windows,
    persist them on the trip doc, and return the windows list.

    Returns an empty list if the Google client libraries are not installed or if
    no members have valid calendar tokens.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore  # noqa: F401
    except ImportError:
        logger.warning("[calendar_service] google-api-python-client not installed — skipping freebusy fetch")
        return []

    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=days)

    member_ids = get_trip_members(trip_id)
    busy_intervals_per_user: list[list[tuple[datetime, datetime]]] = []

    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        token = user.get("googleCalendarToken")
        if not token:
            continue

        intervals = query_user_freebusy(uid, token, time_min, time_max)
        if intervals is not None:
            busy_intervals_per_user.append(intervals)

    # Skip members whose tokens failed; compute availability for remaining connected members.
    # If all members failed, busy_intervals_per_user is empty and we return nothing.
    if not busy_intervals_per_user:
        return []

    windows = find_free_windows(busy_intervals_per_user, time_min, time_max)
    store_trip_availability(trip_id, windows)
    return windows
