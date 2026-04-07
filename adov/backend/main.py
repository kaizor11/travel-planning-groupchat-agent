# FastAPI application entry point: initializes the app, adds CORS middleware, and mounts all routers.
import os
from dotenv import load_dotenv

load_dotenv()  # Must run before firebase/anthropic imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import ai, calendar, chat, users

app = FastAPI(title="Adov")

_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
# FRONTEND_URL is set on Render to the Vercel deployment URL (e.g. https://tripmind.vercel.app)
if frontend_url := os.getenv("FRONTEND_URL"):
    _origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(users.router)
app.include_router(calendar.router)
