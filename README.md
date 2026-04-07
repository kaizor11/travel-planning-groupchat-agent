# AI Group Travel Coordinator

A pre-trip coordination tool where an AI agent helps groups align on travel preferences, availability, and budget before anyone opens a booking site.

## Stack

**Backend** — `adov/backend/`
- Python 3.11+ with FastAPI + Uvicorn
- Firebase Admin SDK (Firestore, server-side only)
- Anthropic Claude API (`claude-sonnet-4-6`) for content parsing and proposal generation
- Server-Sent Events (SSE) for real-time message streaming

**Frontend** — `adov/frontend/`
- React 18 + TypeScript + Vite
- TailwindCSS with an iMessage-style design system
- React Router v6

---

## Setup & Running

All commands run from `adov/`.

### 1. Python environment

```bash
cd adov/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Python packages installed (`requirements.txt`):**
| Package | Version | Purpose |
|---|---|---|
| `fastapi` | >=0.115.0 | Web framework |
| `uvicorn[standard]` | >=0.32.0 | ASGI server |
| `firebase-admin` | >=6.6.0 | Firestore + Auth (Admin SDK) |
| `anthropic` | >=0.40.0 | Claude API client |
| `python-dotenv` | >=1.0.0 | Load `.env` secrets |
| `python-multipart` | >=0.0.12 | Form data parsing |
| `sse-starlette` | >=2.1.0 | Server-Sent Events support |

### 2. Environment variables

Create `adov/backend/.env`:

```
ANTHROPIC_API_KEY=sk-...
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

### 3. Frontend dependencies

```bash
cd adov
npm run setup        # installs frontend node_modules
```

**npm packages installed:**
| Package | Purpose |
|---|---|
| `react` + `react-dom` | UI library |
| `react-router-dom` | Client-side routing |
| `vite` | Dev server + bundler |
| `typescript` | Type checking |
| `tailwindcss` + `postcss` + `autoprefixer` | Styling |
| `@vitejs/plugin-react` | Vite React support |
| `concurrently` | Run backend + frontend together |

### 4. Run the app

```bash
# From adov/ — starts backend (:8000) and frontend (:5173) concurrently
npm run dev

# Backend only
cd backend && uvicorn main:app --reload

# Frontend only
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### 5. Run tests (optional)

```bash
# From adov/
npm run test           # Playwright + pytest, headless
npm run test:headed    # Same, with browser visible
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/trips/{trip_id}` | Fetch messages + current user |
| `GET` | `/api/trips/{trip_id}/stream` | SSE real-time message stream |
| `POST` | `/api/trips/{trip_id}/messages` | Send a message (triggers AI parse if URL) |
| `POST` | `/api/trips/{trip_id}/wishpool` | Add/skip a wish pool entry |
| `POST` | `/api/ai/parse-content` | Parse travel content via Claude |
