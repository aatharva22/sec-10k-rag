"""
Phase 6: FastAPI app entrypoint.

Mounts routers:
- POST /query  → routes/query.py    (the RAG endpoint)
- GET  /health → routes/health.py   (db ping)

Run with:
    uv run uvicorn api.main:app --reload

TODO Phase 6:
- create FastAPI app
- include routers
- CORS for http://localhost:3000 (the Next.js dev server)
- on startup: load env, init psycopg pool via api.db
"""
