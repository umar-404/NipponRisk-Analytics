# NipponRisk Analytics
"""FastAPI application entrypoint.

Run with::

    cd backend
    .venv/bin/uvicorn app.main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import TICKER_NAMES, TICKERS

APP_NAME = "NipponRisk Analytics"
VERSION = "0.1.0"

app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description=(
        "Portfolio risk analytics & stress-testing for Japanese equities. "
        "Tickers: " + ", ".join(TICKERS) + ". Benchmark: ^N225."
    ),
)

# CORS: allow the Vite dev server (and its common ports).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    """Tiny root route describing the service."""
    return {
        "name": APP_NAME,
        "version": VERSION,
        "tickers": [{"ticker": t, "name": TICKER_NAMES.get(t, t)} for t in TICKERS],
        "benchmark": "^N225",
        "docs": "/docs",
        "health": "/api/health",
        "analyze": "POST /api/analyze",
    }