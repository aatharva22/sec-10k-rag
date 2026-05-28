"""FastAPI app entrypoint.

Mounts:
- POST /query  → routes/query.py    (the RAG endpoint)
- GET  /health → routes/health.py   (db ping)

Run with:
    uv run uvicorn api.main:app --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, query


def _cors_origins() -> list[str]:
    """Read CORS_ORIGINS env var (comma-separated). Localhost is always
    included so dev never breaks even when the env var is set in prod."""
    extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    return ["http://localhost:3000", *extra]


app = FastAPI(title="SEC 10-K RAG", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
