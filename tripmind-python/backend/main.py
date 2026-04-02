# FastAPI application entry point: initializes the app, adds CORS middleware, and mounts all routers.
from dotenv import load_dotenv

load_dotenv()  # Must run before firebase/anthropic imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import ai, chat

app = FastAPI(title="TripMind")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ai.router)
