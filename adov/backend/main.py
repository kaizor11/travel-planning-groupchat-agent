# FastAPI application entry point: initializes the app, adds CORS middleware, and mounts all routers.
import os
from dotenv import load_dotenv

load_dotenv()  # Must run before firebase/anthropic imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import ai, calendar, chat, debug, images, proposals, users

app = FastAPI(title="Adov")

_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
# FRONTEND_URL is set on Render to the Vercel deployment URL (e.g. https://tripmind.vercel.app)
if frontend_url := os.getenv("FRONTEND_URL"):
    _origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(images.router)
app.include_router(users.router)
app.include_router(calendar.router)
app.include_router(proposals.router)
app.include_router(debug.router)

# Required env vars — checked at startup so missing config produces a clear error
# instead of a cryptic failure when the first API call is made.
REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "FIREBASE_ADMIN_PROJECT_ID",
    "FIREBASE_ADMIN_CLIENT_EMAIL",
    "FIREBASE_ADMIN_PRIVATE_KEY",
    "SERPAPI_API_KEY",
    "APIFY_KEY",
    "TASK_URL",
]


@app.on_event("startup")
def check_env_vars() -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file or deployment environment."
        )
