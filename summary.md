# Adov — Webapp Codebase Summary

---

## What the App Does

**Adov** is an AI-powered group travel coordinator. Its entire job is the *pre-booking* phase: helping a group of friends align on where and when to go, then handing them off to a booking site (Expedia, Booking.com, Google Flights) to actually purchase tickets.

It does five things autonomously:
1. **Passively collects destinations** from links users share in the chat (Instagram reels, travel blogs, etc.)
2. **Reconciles availability** across members' Google Calendars to find overlapping free windows
3. **Aligns budgets** by collecting each person's private budget range and computing the group overlap
4. **Generates concrete trip proposals** (destination + dates + estimated cost) when the group asks
5. **Facilitates voting** on those proposals and announces the winner

It does NOT book flights, build itineraries, or give travel advice.

---

## Architecture Overview

```
[Browser]
   |
   | HTTP requests (JSON) + SSE (real-time push)
   v
[FastAPI Backend — Python]
   |           |           |           |
   v           v           v           v
[Firestore]  [Claude API] [Google     [SerpAPI /
 (database)  (Anthropic)  Calendar]   Apify]
```

**Frontend** = React app running in the user's browser. It sends HTTP requests to the backend and listens for new messages in real time.

**Backend** = FastAPI Python app. It handles all business logic, talks to the database, and calls external APIs. The browser never talks to Firestore or Claude directly.

**Firestore** = Google's NoSQL cloud database. The backend reads/writes here for messages, users, proposals, etc.

**Claude API** = Anthropic's LLM API. Used for parsing non-social-media travel content, extracting preferences, generating proposals, and answering @adov mentions.

**Google Calendar API** = Checks each member's free/busy slots (calendar content is never read — only "free" or "busy").

**SerpAPI / Apify** = Third-party APIs for Google Flights prices and Instagram data respectively.

---

## Process 1: Authentication

**Files:** `adov/backend/services/auth.py`, `adov/frontend/src/hooks/useAuth.ts`, `adov/frontend/src/pages/LoginPage.tsx`

### How it works

The app uses **Firebase Auth** (Google's authentication service). Users sign in with their Google account.

**Login flow (frontend):**
1. User clicks "Sign in with Google" → browser popup
2. Firebase returns two tokens:
   - **ID token** (expires in 1 hour) — proves who the user is to the backend
   - **Access token** — allows the backend to query the user's Google Calendar
3. The frontend sends the access token to `PUT /api/users/me/calendar-token` so the backend can store it for later calendar queries
4. The frontend stores the ID token in memory and sends it as `Authorization: Bearer <token>` on every API request

**Backend token verification (`auth.py`):**
- Every protected endpoint receives the ID token in the `Authorization` header
- The `get_current_user()` FastAPI dependency verifies the token with Firebase Admin SDK
- If valid, it returns the decoded user info (`uid`, `name`, `email`, `picture`)
- On first login, it creates/updates the user's Firestore document

```python
# Pattern used on every protected endpoint:
async def some_endpoint(user=Depends(get_current_user)):
    uid = user["uid"]
    # uid is now verified
```

**Token refresh:** The frontend refreshes the ID token every 55 minutes (Firebase tokens last 1 hour) via `useAuth.ts`.

---

## Process 2: Real-Time Chat (SSE)

**Files:** `adov/backend/routes/chat.py`, `adov/backend/services/firebase.py` (`stream_messages`), `adov/frontend/src/pages/ChatPage.tsx`

### The problem SSE solves

HTTP is request/response: the browser asks, the server answers. But chat needs the server to *push* new messages to all connected clients without them asking. The solution here is **Server-Sent Events (SSE)** — a one-way streaming connection from server to browser.

### Sending a message

```
Browser → POST /api/trips/{trip_id}/messages → Backend
   1. Verifies Firebase ID token
   2. Writes message to Firestore /trips/{trip_id}/messages
   3. If message contains a URL → fires background AI parsing task
   4. If message contains "@adov" → fires background AI response task
   5. If message contains preference signals → fires background preference extraction
   6. Returns 200 immediately (doesn't wait for background tasks)
```

### Receiving messages (SSE stream)

```
Browser → GET /api/trips/{trip_id}/stream → Backend (long-lived connection)
   Backend polls Firestore every 1 second for new messages
   When new message found → sends to browser as: data: {"id": "...", "text": "..."}\n\n
```

The `stream_messages()` generator in `firebase.py`:
- Starts by loading all existing messages to build a "seen IDs" set
- Records the timestamp of the last message
- Every second, queries Firestore for messages **at or after `last_ts - 1 second`** (1-second overlap to close the race window where a message arrives between timestamp capture and query execution)
- The `seen_ids` set deduplicates any messages already emitted — no double-delivery
- On poll error: emits an SSE `event: error` frame and closes cleanly so the frontend auto-reconnects
- Yields any new ones as SSE events (format: `data: <json>\n\n`)

**Frontend SSE handling (`ChatPage.tsx`):**
- Opens an `EventSource` connection on mount
- On new message: adds it to state (skips own messages already shown optimistically)
- On disconnect: waits 2 seconds and reconnects; refetches full message list and **merges** it with existing state (preserving optimistic messages not yet confirmed by the server)
- **Optimistic updates**: when the user sends a message, it's shown in the UI immediately before the server confirms

### Message types

Each Firestore message has a `type` field that controls how it renders:

| Type | Who sends it | What it looks like |
|------|-------------|-------------------|
| `user` | Humans | Blue/white chat bubble |
| `ai` | Backend AI tasks | Purple bubble with airplane icon |
| `wishpool_confirm` | AI (after URL parse) | AI bubble + "Add to wish pool?" card |
| `proposal` | AI (after @adov proposal trigger) | AI bubble + proposal cards with voting |
| `vote` | AI (vote progress updates) | Purple bubble with vote tally |

---

## Process 3: AI Content Parsing (Wish Pool)

**Files:** `adov/backend/routes/ai.py` (`parse_content`), `adov/backend/services/anthropic_client.py` (`parse_travel_content`), `adov/backend/services/instagram_scraper.py`

### Flow

When a user sends a message containing a URL:

```
POST /api/trips/{tripId}/messages (contains URL)
   ↓
chat.py detects URL with regex
   ↓
background task: parse_content(trip_id, sender_id, url, raw_text)
   ↓
   If Instagram reel URL:
       instagram_scraper.scrapify_reel(url)  ← calls Apify API
       Returns location, caption, hashtags, transcript
   ↓
anthropic_client.parse_travel_content(url, text)  ← calls Claude
   Returns: {destination, tags, estimatedCost, confidence}
   ↓
   If confidence >= 0.7:
       Writes "wishpool_confirm" message to Firestore
       (renders as AI message with "Add to Wish Pool?" / "Skip" buttons)
   Else:
       Writes fallback AI message: "Hmm, I couldn't tell where this is from — is this a place you'd want to visit?"
```

### Wish pool confirmation

When a user clicks "Add":
```
POST /api/trips/{tripId}/wishpool  {action: "add", destination: "...", tags: [...], source_url: "..."}
   ↓
firebase.upsert_wish_pool_entry(trip_id, uid, destination, tags, estimated_cost, source_url)
   If an entry with the same sourceUrl already exists:
       → updates acceptedBy: ArrayUnion([uid])   (idempotent)
   Else:
       → creates new doc with acceptedBy: [uid]
```

When the user clicks "Skip": same endpoint with `action: "skip"` — no Firestore write.

**Deduplication:** the same link clicked by multiple users results in ONE Firestore document, with each user's UID added to `acceptedBy`. Different links pointing to the same city remain as separate entries; vote aggregation happens later at proposal-generation time.

**The wish pool** is a collection of travel destinations the group has confirmed interest in. It's the raw material for proposal generation.

---

## Process 4: Preference Extraction (Silent)

**Files:** `adov/backend/routes/chat.py` (trigger detection), `adov/backend/routes/ai.py` (`handle_preference`), `adov/backend/services/anthropic_client.py` (`extract_preference`)

### Flow

Every message is scanned for preference signals using a regex:
```python
PREFERENCE_SIGNAL_REGEX = re.compile(
    r"\b(i love|i hate|i prefer|i'm into|not a fan|can't stand|obsessed with|...)\b",
    re.IGNORECASE
)
```

If a signal is detected, a **background task** silently calls Claude:
```
extract_preference("I love beach destinations but hate crowds")
   → Claude returns: {"type": "destination", "item": "beach", "sentiment": "positive"}
   → Claude returns: {"type": "vibe", "item": "crowds", "sentiment": "negative"}
```

The result is written to `/trips/{tripId}/preferences/{userId}` in Firestore. **No chat message is sent** — the user never sees this happen. The preferences are later used to inform proposal generation.

---

## Process 5: @adov Mentions (AI Routing)

**Files:** `adov/backend/routes/chat.py` (trigger detection), `adov/backend/routes/ai.py` (`handle_mention`, `handle_proposal_request`), `adov/backend/prompts/agent.py`

### Routing logic

When a message contains `@adov`, the backend decides which AI behavior to invoke:

```python
PROPOSAL_TRIGGER_REGEX = re.compile(
    r"\b(where should we go|trip ideas|give us some ideas|suggest a trip|...)\b",
    re.IGNORECASE
)

if PROPOSAL_TRIGGER_REGEX.search(message_text):
    handle_proposal_request(trip_id, sender_name, message_text)
else:
    handle_mention(trip_id, sender_name, message_text)
```

### Conversational path (`handle_mention`)

Used for questions like "@adov who has connected their calendar?" or "@adov what's our budget looking like?":

1. Fetches last 10 messages for conversation context
2. Fetches trip member status (who has calendar connected, who voted, etc.)
3. Fetches available calendar windows (stored on trip document)
4. Injects real ground-truth data into Claude's system prompt so it gives accurate answers
5. Calls `get_chat_response()` → Claude generates a reply
6. Writes `ai` type message to Firestore

### Proposal trigger path (`handle_proposal_request`)

See **Process 8: Proposal Generation** below.

---

## Process 6: Calendar Reconciliation

**Files:** `adov/backend/routes/calendar.py`, `adov/backend/routes/users.py` (token storage), `adov/frontend/src/components/ProfileDrawer.tsx`

### Connecting a calendar

When a user first signs in, the frontend captures a Google OAuth **access token** and sends it to:
```
PUT /api/users/me/calendar-token  {access_token: "ya29.a0..."}
```
The backend stores this token in Firestore at `/users/{uid}/googleCalendarToken`. It's **never returned** to the frontend or other users.

### Querying free/busy

When the frontend requests availability (from ProfileDrawer or when @adov is asked):
```
POST /api/calendar/freebusy  {trip_id, time_min, time_max}
```

The backend:
1. Fetches all trip member IDs
2. For each member, loads their stored `googleCalendarToken`
3. Calls Google Calendar API: `freeBusy.query()` — returns busy time blocks only (no event titles/content)
4. Runs an **overlap algorithm** to find windows where ALL members are simultaneously free

**Overlap algorithm (`calendar.py`):**
```python
# Start with candidate windows in 1-hour increments across the date range
# For each candidate window:
#   For each busy block from each member's calendar:
#     If the window overlaps with any busy block → mark as not free
# Keep only windows where all_free == True AND duration >= 2 hours
```

5. Stores the resulting free windows on the trip document: `/trips/{tripId}/availableWindows`
6. Returns `{windows: [...], membersChecked: N, tokenExpiredCount: N}`

---

## Process 7: Budget Reconciliation

**Files:** `adov/backend/routes/users.py`, `adov/backend/routes/chat.py` (`get_budget`), `adov/frontend/src/components/ProfileDrawer.tsx`

### How it works

Each user sets their private budget range in their profile:
```
PUT /api/users/me  {budget_min: 500, budget_max: 1500}
```

These values are validated server-side: both must be non-negative and `budget_min` must not exceed `budget_max` (returns HTTP 422 otherwise). They are stored in `/users/{uid}/budgetMin` and `/users/{uid}/budgetMax` and are **never returned to other users**.

When computing the group budget for proposals, the backend:
```python
# Fetch budgets for all trip members
budgets = [(user["budgetMin"], user["budgetMax"]) for user in members if both fields exist]

# Group overlap = most restrictive range that satisfies everyone
group_min = max(b[0] for b in budgets)  # Highest minimum across all members
group_max = min(b[1] for b in budgets)  # Lowest maximum across all members
```

This range is passed to Claude for proposal generation. Individual numbers are never exposed.

The `GET /api/trips/{tripId}/budget` endpoint returns only `{group_min, group_max, members_with_budget}` — no per-person breakdown.

---

## Process 8: Proposal Generation

**Files:** `adov/backend/routes/ai.py` (`handle_proposal_request`), `adov/backend/routes/proposals.py`, `adov/backend/services/anthropic_client.py` (`generate_trip_proposals`), `adov/backend/services/flights_service.py`, `adov/backend/prompts/agent.py` (`PROPOSAL_GENERATION_PROMPT`)

### Prerequisites and gate logic

`_run_proposal_generation(trip_id, force=False)` runs three sequential gates before calling Claude:

**Gate 1 — Destination aggregation (always runs):**
- Each destination string is normalized via `_normalize_destination`, which resolves common aliases using a hardcoded `_CITY_ALIASES` lookup (e.g. "NYC" → "New York City, NY", "Bali" → "Bali, Indonesia") so different shorthand for the same city merges correctly
- Groups all wishpool entries by normalized destination key
- Counts unique acceptors (UIDs across all entries for that destination) and total votes
- Filters to destinations where unique acceptors **> 50% of member count** (strict majority)
- Sorts by total vote count descending; caps at 5
- If no destinations qualify → writes a hardcoded nudge message, returns early

**Gate 2 — Readiness check (skipped when `force=True`):**
- Checks each member's Firestore user doc for `budgetMin`/`budgetMax` and `googleCalendarToken`
- If any member is missing budget or calendar → writes a hardcoded message naming who needs to act, tells group to say `@adov generate anyway` to proceed, returns early

**Force override:** when the trigger text contains `anyway`, `just go`, `go ahead`, `proceed`, `skip`, or `ignore`, `force=True` is set and Gate 2 is skipped. Claude generates with null budget (unconstrained) and empty windows (60-90 day fallback dates).

### Full generation flow

Both the `@adov` trigger path and the `POST /api/trips/{tripId}/proposals/generate` endpoint share a single implementation via `_run_proposal_generation(trip_id, force)` in `routes/proposals.py`.

```
_run_proposal_generation(trip_id, force=False)
   ↓
1. Fetch wish pool + trip doc + budgets + member IDs (concurrent)

2. _aggregate_destinations(wish_pool, member_count)
   → Groups entries by destination, counts unique acceptors + total votes
   → Filters to strict-majority destinations, sorts by votes, caps at 5
   → If empty: write nudge message, return early

3. If not force: _check_proposal_readiness(trip_id, member_ids)
   → For each member: check budgetMin/Max and googleCalendarToken
   → If any missing: write message listing who needs to act, return early

4. _pick_outbound_date(windows) → first future window start, or now+60d fallback

5. For each destination in aggregated list:
   For each member's home airport:
       flights_service.get_cheapest_flight(origin, destination, date)
   flight_estimates[destination] = min price across all origins

6. anthropic_client.generate_trip_proposals(
       aggregated_destinations, windows, budget, member_count, flight_estimates
   )
   → Claude returns JSON array with ONE proposal per destination:
   [
     {
       "destination": "Lisbon, Portugal",
       "suggestedDates": {"start": "2026-06-10", "end": "2026-06-17"},
       "estimatedCostPerPerson": 1200,
       "flightEstimate": 650,
       "rationale": "Saved by both members; matches beach + culture tags",
       "tradeoff": "Long flight from US West Coast"
     },
     ...  // one element per aggregated destination
   ]

7. For each proposal:
   - Add bookingSearchUrl (pre-filled Google Flights link)
   - Write to /trips/{tripId}/proposals/{proposalId} in Firestore

8. Write a "proposal" type message to Firestore chat
   (message contains embedded proposalsData array)

9. log_event("proposals_generated", trip_id, count, destinations)
   (writes to services/activity_log for analytics/debugging)
```

**Error handling:** if `_run_proposal_generation` raises an exception, `handle_proposal_request` writes a hardcoded error message. It no longer falls back to `handle_mention` (which previously caused Claude to generate "Should I lock those in?" confirmation questions).

---

## Process 9: Voting

**Files:** `adov/backend/routes/proposals.py` (`vote_on_proposal`), `adov/frontend/src/components/ProposalCard.tsx`

### Flow

When a user clicks Yes/No/Maybe on a proposal card:
```
POST /api/trips/{tripId}/proposals/{proposalId}/vote  {vote: "yes"}
   ↓
1. Verify Firebase ID token → get uid
2. Write vote to Firestore: /trips/{tripId}/proposals/{proposalId}.votes[uid] = "yes"
3. Fetch all proposals and count votes
4. Write per-proposal progress message to chat:
   - If not all voted: "2 of 4 members have voted on **Tokyo** — waiting on 2 more."
   - If all voted on this proposal: announce this proposal's result (win/tie/tally)
5. Cross-proposal winner check (when multiple proposals exist):
   - If every proposal has been fully voted on by all members:
     → _declare_winning_destination() compares yes-vote counts across all proposals
     → Writes a single winner announcement: "All votes are in! **Tokyo** wins with 3 yes votes."
     → Handles tie: "It's a tie between **Tokyo** and **Bali** with 2 yes votes each."
     → Handles all-no case: "No destination received a yes vote — want to regenerate?"
6. Return {votes, tally} to frontend
```

The frontend updates the proposal card optimistically (shows new vote immediately), then confirms with the server response.

---

## Database Schema (Firestore)

```
/users/{userId}
    name, email, avatarUrl
    budgetMin, budgetMax          (private — never returned to other users)
    homeAirport                   (IATA code or city name)
    googleCalendarToken           (private — never returned to ANY client)
    preferences: [{type, item, sentiment}, ...]
    tripDurationMin, tripDurationMax
    calendarConnected             (computed: True if googleCalendarToken exists)

/trips/{tripId}
    createdBy, createdAt
    memberIds: [uid1, uid2, ...]
    status: "planning" | "voted" | "booked"
    availableWindows: [{start, end}, ...]

/trips/{tripId}/messages/{messageId}
    senderId, senderName
    text
    timestamp
    type: "user" | "ai" | "wishpool_confirm" | "proposal" | "vote"
    attachedUrl           (optional)
    parsedData            (optional — set on wishpool_confirm messages)
    proposalsData: [...]  (optional — set on proposal messages)

/trips/{tripId}/wishPool/{entryId}
    acceptedBy: [userId, ...]   (upserted per-user; replaces old submittedBy field)
    destination, tags
    estimatedCost         ("budget" | "mid-range" | "luxury")
    sourceUrl             (dedup key — same URL → same doc, new uid added to acceptedBy)
    confirmedAt

/trips/{tripId}/proposals/{proposalId}
    destination
    suggestedDates: {start, end}
    estimatedCostPerPerson  (integer USD)
    flightEstimate          (integer USD or null)
    rationale, tradeoff
    bookingSearchUrl
    votes: {userId: "yes"|"no"|"maybe"}
    generatedAt

/trips/{tripId}/preferences/{userId}
    userId
    items: [{type, item, sentiment}, ...]
    updatedAt
```

---

## Configuration & Secrets

All secrets live in `adov/backend/.env`. The app will crash on startup if required vars are missing.

| Variable | What it controls |
|----------|-----------------|
| `ANTHROPIC_API_KEY` | All Claude API calls (parsing, proposals, chat responses, preference extraction) |
| `FIREBASE_ADMIN_PROJECT_ID` | Which Firestore project to read/write |
| `FIREBASE_ADMIN_CLIENT_EMAIL` | Firebase service account identity |
| `FIREBASE_ADMIN_PRIVATE_KEY` | Firebase service account credential (multi-line PEM) |
| `GOOGLE_CLIENT_ID` | Google OAuth (Calendar access) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth (Calendar access) |
| `SERPAPI_API_KEY` | Google Flights price lookups |
| `APIFY_KEY` | Instagram reel scraping |
| `TASK_URL` | Apify task ID for the Instagram scraper |
| `FRONTEND_URL` | Production frontend URL (added to CORS allowlist) |
| `ANTHROPIC_MODEL` | *(optional)* Override the Claude model (defaults to `claude-sonnet-4-6`) |

Frontend secrets are prefixed with `VITE_` and are safe to expose to the browser (Firebase client SDK config, not admin credentials).

---

## Key Files Quick Reference

| Process | Backend File(s) | Frontend File(s) |
|---------|----------------|-----------------|
| App startup & routing | `backend/main.py` | `frontend/src/App.tsx` |
| Authentication | `backend/services/auth.py` | `frontend/src/hooks/useAuth.ts`, `pages/LoginPage.tsx` |
| Chat / SSE | `backend/routes/chat.py`, `services/firebase.py` | `pages/ChatPage.tsx`, `api/client.ts` |
| AI content parsing | `backend/routes/ai.py` (`parse_content`), `services/anthropic_client.py` (`parse_travel_content`), `services/instagram_scraper.py` | `components/WishPoolCard.tsx` |
| Preference extraction | `backend/routes/ai.py` (`handle_preference`), `services/anthropic_client.py` (`extract_preference`) | (invisible to UI) |
| @adov conversational | `backend/routes/ai.py` (`handle_mention`), `services/anthropic_client.py` (`get_chat_response`), `prompts/agent.py` | `components/MessageBubble.tsx` |
| Calendar reconciliation | `backend/routes/calendar.py` | `components/ProfileDrawer.tsx` |
| Budget reconciliation | `backend/routes/users.py`, `backend/routes/chat.py` (`get_budget`) | `components/ProfileDrawer.tsx` |
| Proposal generation | `backend/routes/ai.py` (`handle_proposal_request`), `backend/routes/proposals.py`, `services/anthropic_client.py` (`generate_trip_proposals`), `services/flights_service.py`, `prompts/agent.py` | `components/ProposalCard.tsx` |
| Voting | `backend/routes/proposals.py` (`vote_on_proposal`) | `components/ProposalCard.tsx` |
| Database helpers | `backend/services/firebase.py` | — |
| All Claude prompts | `backend/prompts/agent.py` | — |
| User profile | `backend/routes/users.py` | `components/ProfileDrawer.tsx` |
| Trip join | `backend/routes/chat.py` (`join_trip`, `get_invite`) | `pages/JoinTripPage.tsx` |

---

## How a Typical Session Flows End-to-End

```
1. User A opens the app → Firebase Google sign-in → ID token issued
2. Frontend opens SSE stream to GET /api/trips/test-trip-123/stream
3. User A shares an Instagram reel link in chat
   → Frontend: POST /api/trips/.../messages {text: "check this out https://instagram..."}
   → Backend: saves message, fires background parse_content()
   → Instagram scraper extracts location data
   → Claude parses: {destination: "Bali, Indonesia", tags: ["beach", "temples"], confidence: 0.92}
   → Backend writes wishpool_confirm message to Firestore
   → SSE stream pushes it to all connected browsers
   → User A sees: "Bali, Indonesia — Add to Wish Pool? [Add] [Skip]"
4. User A clicks "Add" → POST /api/trips/.../wishpool
   → upsert_wish_pool_entry: creates doc with acceptedBy: [userA]
5. User B clicks "Add" on the same card
   → upsert_wish_pool_entry: finds existing doc by sourceUrl, updates acceptedBy: [userA, userB]
6. Repeat with more destinations (Paris, Tokyo) — each accepted by both users
7. User B types "@adov where should we go?"
   → Backend detects proposal trigger regex
   → handle_proposal_request() fires (force=False):
       - Fetches wish pool and member list
       - _aggregate_destinations: Bali (2 unique acceptors > 50%), Paris (2), Tokyo (2) → all qualify
       - _check_proposal_readiness: both users have budget + calendar → passes
       - Fetches home airports (LAX, JFK), calls SerpAPI for flight prices
       - Calls Claude → generates 3 proposals (one per destination)
       - Writes proposals to Firestore
       - Writes "proposal" message to chat
   → SSE pushes proposal cards to all browsers
7. Everyone votes yes/no/maybe on proposals
   → Each vote: POST /api/trips/.../proposals/xyz/vote {vote: "yes"}
   → Backend writes progress message to chat
   → When everyone votes: "All voted! Bali wins with 4 yes votes."
```
