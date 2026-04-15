# User profile routes: GET/PUT current user's profile (budget, preferences) and calendar token.
# Budget fields (budgetMin, budgetMax) are stored but NEVER returned in group/trip contexts.
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from services.auth import get_current_user
from services.firebase import get_user, set_user_calendar_token, update_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/api/users/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    profile = get_user(uid) or {}
    # Expose whether calendar is connected, then strip the token itself
    profile["calendarConnected"] = bool(profile.get("googleCalendarToken"))
    profile.pop("googleCalendarToken", None)
    return profile


class UpdateProfileBody(BaseModel):
    budget_min: int | None = None
    budget_max: int | None = None
    preferences: list[str] | None = None  # e.g. ["beach", "hiking", "city"]
    trip_duration_min: int | None = None  # days
    trip_duration_max: int | None = None  # days
    home_airport: str | None = None  # IATA code or city name, e.g. "LAX" or "Los Angeles"

    @model_validator(mode="after")
    def validate_budget_range(self) -> "UpdateProfileBody":
        if self.budget_min is not None and self.budget_min < 0:
            raise ValueError("budget_min must be non-negative")
        if self.budget_max is not None and self.budget_max < 0:
            raise ValueError("budget_max must be non-negative")
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min must be less than or equal to budget_max")
        return self


@router.put("/api/users/me")
async def update_my_profile(
    body: UpdateProfileBody,
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    fields: dict = {}
    if body.budget_min is not None:
        fields["budgetMin"] = body.budget_min
    if body.budget_max is not None:
        fields["budgetMax"] = body.budget_max
    if body.preferences is not None:
        fields["preferences"] = body.preferences
    if body.trip_duration_min is not None:
        fields["tripDurationMin"] = body.trip_duration_min
    if body.trip_duration_max is not None:
        fields["tripDurationMax"] = body.trip_duration_max
    if body.home_airport is not None:
        fields["homeAirport"] = body.home_airport.strip().upper() if len(body.home_airport.strip()) == 3 else body.home_airport.strip()
    if fields:
        update_user(uid, fields)
        logger.info(f"[audit] user={uid} action=update_profile fields={list(fields.keys())}")
    return {"ok": True}


# ── Calendar token ────────────────────────────────────────────────────────────

class CalendarTokenBody(BaseModel):
    access_token: str


@router.put("/api/users/me/calendar-token")
async def store_calendar_token(
    body: CalendarTokenBody,
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    set_user_calendar_token(uid, body.access_token)
    logger.info(f"[audit] user={uid} action=store_calendar_token")
    return {"ok": True}
