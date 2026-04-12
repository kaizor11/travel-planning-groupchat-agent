# Auth dependency: verifies Firebase ID token and returns decoded user claims.
# Usage: add `current_user: dict = Depends(get_current_user)` to any protected route.
from fastapi import Depends, Header, HTTPException, Query
from firebase_admin import auth as firebase_auth

from services.firebase import get_trip, upsert_user


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return authorization[7:]


def _verify_token(token: str) -> dict:
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    # Upsert user record on every authenticated request (cheap: Firestore merge)
    uid = decoded.get("uid", "")
    name = decoded.get("name", "")
    email = decoded.get("email", "")
    picture = decoded.get("picture", "")
    if uid:
        upsert_user(uid=uid, name=name, email=email, avatar_url=picture)

    return decoded


def require_trip_member(trip_id: str, current_user: dict) -> None:
    trip = get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    member_ids = trip.get("memberIds", [])
    if current_user.get("uid") not in member_ids:
        raise HTTPException(status_code=403, detail="Not a trip member")


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Verify Firebase ID token from Authorization header. Returns decoded token dict."""
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return _verify_token(token)


async def get_current_user_for_stream(
    authorization: str | None = Header(None),
    token: str | None = Query(None),
) -> dict:
    """Verify Firebase ID token for EventSource requests via query param or Authorization header."""
    raw_token = token or _extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    return _verify_token(raw_token)


async def get_current_trip_member(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    require_trip_member(trip_id, current_user)
    return current_user


async def get_current_trip_member_for_stream(
    trip_id: str,
    current_user: dict = Depends(get_current_user_for_stream),
) -> dict:
    require_trip_member(trip_id, current_user)
    return current_user
