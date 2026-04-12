"""Small regression tests for trip authorization routes."""

from fastapi.testclient import TestClient
import pytest

from main import app
import routes.calendar as calendar_routes
import routes.chat as chat_routes
import services.auth as auth_service


TRIP_ID = "trip-123"


@pytest.fixture
def store(monkeypatch):
    """In-memory trip/user state so the tests never touch Firebase."""
    state = {
        "trips": {
            TRIP_ID: {"id": TRIP_ID, "memberIds": ["member-1"]},
        },
        "users": {
            "member-1": {"id": "member-1", "budgetMin": 500, "budgetMax": 1500},
            "outsider-1": {"id": "outsider-1", "budgetMin": 900, "budgetMax": 1800},
            "joiner-1": {"id": "joiner-1"},
        },
        "messages": [
            {"id": "msg-1", "senderId": "member-1", "senderName": "Member", "text": "hello", "type": "user"}
        ],
        "added_messages": [],
        "joined_members": [],
        "availability_writes": [],
    }

    tokens = {
        "member-token": {"uid": "member-1", "name": "Member"},
        "outsider-token": {"uid": "outsider-1", "name": "Outsider"},
        "joiner-token": {"uid": "joiner-1", "name": "Joiner"},
    }

    def fake_verify_id_token(token: str) -> dict:
        if token not in tokens:
            raise ValueError("invalid token")
        return dict(tokens[token])

    def fake_get_trip(trip_id: str):
        return state["trips"].get(trip_id)

    def fake_get_messages(trip_id: str):
        assert trip_id == TRIP_ID
        return list(state["messages"])

    def fake_add_message(trip_id: str, msg: dict) -> str:
        state["added_messages"].append((trip_id, dict(msg)))
        return "new-message-id"

    def fake_add_trip_member(trip_id: str, user_id: str) -> None:
        state["joined_members"].append((trip_id, user_id))

    def fake_get_user(user_id: str):
        return state["users"].get(user_id)

    def fake_get_trip_members(trip_id: str):
        trip = state["trips"].get(trip_id)
        return list(trip.get("memberIds", [])) if trip else []

    def fake_store_trip_availability(trip_id: str, windows: list[dict]) -> None:
        state["availability_writes"].append((trip_id, list(windows)))

    async def fake_stream_messages(trip_id: str):
        assert trip_id == TRIP_ID
        yield 'data: {"id":"evt-1","senderId":"ai","text":"hi","type":"ai"}\n\n'

    monkeypatch.setattr(auth_service.firebase_auth, "verify_id_token", fake_verify_id_token)
    monkeypatch.setattr(auth_service, "upsert_user", lambda **kwargs: None)
    monkeypatch.setattr(auth_service, "get_trip", fake_get_trip)

    monkeypatch.setattr(chat_routes, "get_trip", fake_get_trip)
    monkeypatch.setattr(chat_routes, "get_messages", fake_get_messages)
    monkeypatch.setattr(chat_routes, "add_message", fake_add_message)
    monkeypatch.setattr(chat_routes, "add_trip_member", fake_add_trip_member)
    monkeypatch.setattr(chat_routes, "get_user", fake_get_user)
    monkeypatch.setattr(chat_routes, "stream_messages", fake_stream_messages)

    monkeypatch.setattr(calendar_routes, "get_trip_members", fake_get_trip_members)
    monkeypatch.setattr(calendar_routes, "get_user", fake_get_user)
    monkeypatch.setattr(calendar_routes, "store_trip_availability", fake_store_trip_availability)

    return state


@pytest.fixture
def client(store):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# Reading a trip should require trip membership.
def test_member_can_read_trip(client):
    response = client.get(f"/api/trips/{TRIP_ID}", headers=auth_headers("member-token"))

    assert response.status_code == 200
    assert response.json()["trip_id"] == TRIP_ID


def test_non_member_cannot_read_trip(client):
    response = client.get(f"/api/trips/{TRIP_ID}", headers=auth_headers("outsider-token"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not a trip member"}


# Posting a message should require trip membership.
def test_member_can_post_trip_message(client, store):
    response = client.post(
        f"/api/trips/{TRIP_ID}/messages",
        headers=auth_headers("member-token"),
        json={"text": "plain chat message", "sender_name": "Member"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "id": "new-message-id"}
    assert store["added_messages"][0][0] == TRIP_ID
    assert store["added_messages"][0][1]["senderId"] == "member-1"


def test_non_member_cannot_post_trip_message(client, store):
    response = client.post(
        f"/api/trips/{TRIP_ID}/messages",
        headers=auth_headers("outsider-token"),
        json={"text": "plain chat message", "sender_name": "Outsider"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not a trip member"}
    assert store["added_messages"] == []


# The /test_tool branch should store the user message, add its own reply, and stop there.
def test_test_tool_message_returns_early_with_tool_reply(client, store, monkeypatch):
    import routes.ai as ai_routes

    monkeypatch.setattr(chat_routes, "run_test_tool", lambda: "tool reply")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("normal AI routing should not run for /test_tool")

    monkeypatch.setattr(ai_routes, "handle_mention", fail_if_called)
    monkeypatch.setattr(ai_routes, "handle_preference", fail_if_called)
    monkeypatch.setattr(ai_routes, "parse_content", fail_if_called)

    response = client.post(
        f"/api/trips/{TRIP_ID}/messages",
        headers=auth_headers("member-token"),
        json={"text": "/test_tool", "sender_name": "Member"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "id": "new-message-id"}
    assert store["added_messages"] == [
        (
            TRIP_ID,
            {
                "senderId": "member-1",
                "senderName": "Member",
                "text": "/test_tool",
                "type": "user",
            },
        ),
        (
            TRIP_ID,
            {
                "senderId": "ai",
                "text": "tool reply",
                "type": "ai",
            },
        ),
    ]


# Joining should still work for a real trip, but 404 for a missing one.
def test_join_existing_trip_works(client, store):
    response = client.post(f"/api/trips/{TRIP_ID}/join", headers=auth_headers("joiner-token"))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "trip_id": TRIP_ID, "user_id": "joiner-1"}
    assert store["joined_members"] == [(TRIP_ID, "joiner-1")]


def test_join_nonexistent_trip_returns_404(client):
    response = client.post("/api/trips/missing-trip/join", headers=auth_headers("joiner-token"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


# Calendar free/busy should use the same trip-membership check.
def test_member_can_access_calendar_freebusy(client):
    response = client.post(
        "/api/calendar/freebusy",
        headers=auth_headers("member-token"),
        json={
            "trip_id": TRIP_ID,
            "time_min": "2026-05-01T00:00:00Z",
            "time_max": "2026-05-03T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["membersChecked"] == 0


def test_non_member_cannot_access_calendar_freebusy(client):
    response = client.post(
        "/api/calendar/freebusy",
        headers=auth_headers("outsider-token"),
        json={
            "trip_id": TRIP_ID,
            "time_min": "2026-05-01T00:00:00Z",
            "time_max": "2026-05-03T00:00:00Z",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not a trip member"}


# SSE auth is feasible here because the route accepts a token query param.
def test_member_can_open_trip_stream(client):
    with client.stream("GET", f"/api/trips/{TRIP_ID}/stream", params={"token": "member-token"}) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "data:" in body


def test_non_member_cannot_open_trip_stream(client):
    response = client.get(f"/api/trips/{TRIP_ID}/stream", params={"token": "outsider-token"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Not a trip member"}
