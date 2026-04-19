# Calendar routes: POST /api/calendar/freebusy queries Google Calendar for all trip members,
# finds overlapping free windows, stores them on the trip doc, and returns the result.
# Uses each member's stored Google OAuth access token — tokens expire in ~1 hour.
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from services.auth import get_current_user
from services.firebase import get_trip_members, get_user, store_trip_availability
from services.calendar_service import find_free_windows, query_user_freebusy

router = APIRouter()
logger = logging.getLogger(__name__)

TRIP_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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

    try:
        from googleapiclient.discovery import build  # type: ignore  # noqa: F401
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Google Calendar client not installed. Run: pip install google-api-python-client google-auth",
        )

    busy_intervals_per_user: list[list[tuple[datetime, datetime]]] = []
    members_checked = 0
    members_token_expired = 0
    members_no_token = 0

    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        token = user.get("googleCalendarToken")
        if not token:
            members_no_token += 1
            continue

        intervals = query_user_freebusy(uid, token, time_min, time_max)
        if intervals is None:
            members_token_expired += 1
        else:
            busy_intervals_per_user.append(intervals)
            members_checked += 1

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

    windows = find_free_windows(busy_intervals_per_user, time_min, time_max)
    store_trip_availability(body.trip_id, windows)

    return {
        "windows": windows,
        "membersChecked": members_checked,
        "membersTokenExpired": members_token_expired,
        "membersNoToken": members_no_token,
    }
