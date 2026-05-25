"""
Phase 6: GET /health — liveness + db ping.

Returns { "status": "ok", "db": "ok", "chunks": <count> } when healthy.
Returns 503 when the db is unreachable.

TODO Phase 6:
- APIRouter with GET /health
- SELECT 1 + SELECT count(*) FROM chunks
"""
