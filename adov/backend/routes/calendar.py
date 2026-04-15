# Calendar routes: POST /api/calendar/freebusy queries Google Calendar for all trip members,
# finds overlapping free windows, stores them on the trip doc, and returns the result.
# Uses each member's stored Google OAuth access token — tokens expire in ~1 hour.
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from services.auth import get_current_user
from services.firebase import clear_user_calendar_token, get_trip_members, get_user, store_trip_availability

router = APIRouter()
logger = logging.getLogger(__name__)

TRIP_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _find_free_windows(
    busy_intervals_per_user: list[list[tuple[datetime, datetime]]],
    time_min: datetime,
    time_max: datetime,
    min_hours: int = 2,
) -> list[dict]:
    """
    Given busy intervals for N users, return free windows where ALL users are free.
    Windows shorter than min_hours are excluded.
    Returns list of {start, end} dicts with ISO strings.
    """
    # Collect all boundary points
    points: set[datetime] = {time_min, time_max}
    for user_busy in busy_intervals_per_user:
        for start, end in user_busy:
            if time_min <= start <= time_max:
                points.add(start)
            if time_min <= end <= time_max:
                points.add(end)

    sorted_points = sorted(points)
    free_windows: list[dict] = []

    for i in range(len(sorted_points) - 1):
        window_start = sorted_points[i]
        window_end = sorted_points[i + 1]

        # Guard against zero-duration windows (e.g. two event boundaries align exactly)
        if window_end <= window_start:
            continue

        duration_hours = (window_end - window_start).total_seconds() / 3600

        if duration_hours < min_hours:
            continue

        # Check if any user is busy during this window
        all_free = True
        for user_busy in busy_intervals_per_user:
            for busy_start, busy_end in user_busy:
                # Overlap check: window_start < busy_end AND window_end > busy_start
                if window_start < busy_end and window_end > busy_start:
                    all_free = False
                    break
            if not all_free:
                break

        if all_free:
            free_windows.append({
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            })

    return free_windows


class FreeBusyBody(BaseModel):
    trip_id: str
    time_min: str  # ISO8601, e.g. "2025-06-01T00:00:00Z"
    time_max: str  # ISO8601, e.g. "2025-06-30T23:59:59Z"

    @field_validator("trip_id")
    @classmethod
    def validate_trip_id(cls, v: str) -> str:
        if not TRIP_ID_RE.match(v):
            raise ValueError("trip_id must be 1–64 alphanumeric, hyphen, or underscore characters")
        return v


@router.post("/api/calendar/freebusy")
async def get_freebusy(
    body: FreeBusyBody,
    current_user: dict = Depends(get_current_user),
):
    try:
        time_min = datetime.fromisoformat(body.time_min.replace("Z", "+00:00"))
        time_max = datetime.fromisoformat(body.time_max.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {exc}") from exc

    member_ids = get_trip_members(body.trip_id)
    if not member_ids:
        return {"windows": [], "membersChecked": 0, "note": "No members found for trip"}

    # Collect busy intervals from each member's Google Calendar
    busy_intervals_per_user: list[list[tuple[datetime, datetime]]] = []
    members_checked = 0
    members_token_expired = 0
    members_no_token = 0

    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.errors import HttpError  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Google Calendar client not installed. Run: pip install google-api-python-client google-auth",
        )

    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        token = user.get("googleCalendarToken")
        if not token:
            members_no_token += 1
            continue  # skip members who haven't connected Calendar

        try:
            creds = Credentials(token=token)
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            result = service.freebusy().query(body={
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "items": [{"id": "primary"}],
            }).execute()

            busy_raw = result.get("calendars", {}).get("primary", {}).get("busy", [])
            intervals: list[tuple[datetime, datetime]] = []
            for item in busy_raw:
                s = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
                e = datetime.fromisoformat(item["end"].replace("Z", "+00:00"))
                intervals.append((s, e))

            busy_intervals_per_user.append(intervals)
            members_checked += 1
        except HttpError as exc:
            # Use typed exception status codes instead of fragile string matching
            if exc.resp.status in (401, 403):
                members_token_expired += 1
                logger.info(f"[Calendar] token expired for uid={uid} (HTTP {exc.resp.status})")
                try:
                    clear_user_calendar_token(uid)
                except Exception:
                    pass
            else:
                logger.error(
                    f"[Calendar] HttpError for uid={uid}: {exc.resp.status} — {exc.error_details}",
                    exc_info=True,
                )
        except Exception as exc:
            logger.error(f"[Calendar] Unexpected error for uid={uid}: {exc}", exc_info=True)

    if members_checked == 0:
        if members_token_expired > 0:
            note = (
                f"{members_token_expired} member(s) have an expired calendar token — "
                "they need to reconnect Google Calendar from their profile."
            )
        else:
            note = "No members have connected Google Calendar"
        return {
            "windows": [],
            "membersChecked": 0,
            "membersTokenExpired": members_token_expired,
            "membersNoToken": members_no_token,
            "note": note,
        }

    windows = _find_free_windows(busy_intervals_per_user, time_min, time_max)
    store_trip_availability(body.trip_id, windows)

    return {
        "windows": windows,
        "membersChecked": members_checked,
        "membersTokenExpired": members_token_expired,
        "membersNoToken": members_no_token,
    }
