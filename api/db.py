"""
Postgres connection helper.

Used by:
- ingestion/embed_and_store.py (Phase 3) — bulk inserts
- api/services/retrieval.py    (Phase 4) — hybrid search queries
- api/routes/health.py         (Phase 6) — ping

Plan: a process-wide psycopg_pool.AsyncConnectionPool, opened on FastAPI startup
and closed on shutdown. Ingestion CLI scripts use a short-lived sync connection
since they're one-shot.

TODO Phase 3:
- get_async_pool() singleton
- get_sync_conn() for CLI tools
- both read DATABASE_URL from env
"""
