"""GET /health — liveness + db ping.

Returns 200 with { "status": "ok", "db": "ok", "chunks": <count> } when
healthy. Returns 503 (with detail) when the db is unreachable.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.db import sync_conn

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/health")
def get_health() -> dict:
    try:
        with sync_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.execute("SELECT count(*) FROM chunks")
            chunk_count = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001 — surface db failure as 503
        log.exception("db ping failed")
        raise HTTPException(status_code=503, detail=f"db unavailable: {type(exc).__name__}")

    return {"status": "ok", "db": "ok", "chunks": chunk_count}
