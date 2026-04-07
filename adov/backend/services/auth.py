# Auth dependency: verifies Firebase ID token and returns decoded user claims.
# Usage: add `current_user: dict = Depends(get_current_user)` to any protected route.
from fastapi import Header, HTTPException
from firebase_admin import auth as firebase_auth

from services.firebase import upsert_user


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Verify Firebase ID token from Authorization header. Returns decoded token dict."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization[7:]
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
