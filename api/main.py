"""FastAPI app entrypoint.

Mounts:
- POST /query  → routes/query.py    (the RAG endpoint)
- GET  /health → routes/health.py   (db ping)

Run with:
    uv run uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, query

app = FastAPI(title="SEC 10-K RAG", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
