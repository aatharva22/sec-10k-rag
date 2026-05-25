# SEC 10-K RAG

Chat with SEC 10-K filings for AAPL, MSFT, AMZN, TSLA, NVDA across fiscal years 2022–2024. Hybrid retrieval (BM25 + vector) fused with Reciprocal Rank Fusion, grounded answers with citations, Gemini for generation.

> The project root is this directory directly (no nested `sec-rag/`). All paths in the implementation plan that reference `sec-rag/<x>` map to `./<x>` here.

## Architecture

```
question ──► query_parser (extract ticker, fiscal_year)
         ──► Postgres metadata filter
         ──► BM25 (tsvector) top-20  ┐
                                      ├── parallel
         ──► Vector (pgvector cosine) top-20 ┘
         ──► RRF fuse (k=60) → top-5
         ──► Gemini gemini-2.5-flash + citation-enforcing system prompt
         ──► { answer, citations[] }
```

## Stack

- **Python 3.11+** with `uv` for env/deps
- **FastAPI** for the backend
- **PostgreSQL 16 + pgvector** for vectors, BM25 (tsvector), and metadata in one place
- **Google Gemini** — `gemini-embedding-001` (768-dim) + `gemini-2.5-flash`
- **Next.js 14** (App Router) + TypeScript + Tailwind for the UI
- **Docker Compose** for Postgres

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Scaffold | ✅ done |
| 1 | Ingestion (15 10-Ks from EDGAR) | ⏳ next |
| 2 | Parse + chunk | — |
| 3 | Embed + store + indexes | — |
| 4 | Retrieval service (hybrid + RRF) | — |
| 5 | Generation service (Gemini, swappable) | — |
| 6 | FastAPI wiring | — |
| 7 | Next.js chat UI | — |
| 8 | README polish + demo script | — |

## Quick start (will be filled in as phases land)

```bash
# 1. Postgres
docker compose up -d

# 2. Python env
uv sync

# 3. Copy env template, fill in GEMINI_API_KEY + SEC_USER_AGENT
cp .env.example .env

# (later phases will add: ingestion, API server, web UI)
```

## Files

- [`DECISIONS.md`](./DECISIONS.md) — every non-obvious choice and why
- [`docker-compose.yml`](./docker-compose.yml) — Postgres + pgvector
- [`pyproject.toml`](./pyproject.toml) — Python deps via uv
- [`sql/001_init.sql`](./sql/001_init.sql) — DB schema (Phase 3)
- `ingestion/` — download → parse → chunk → embed pipeline
- `api/` — FastAPI app and retrieval/generation services
- `web/` — Next.js chat UI (Phase 7)

## Demo (Phase 8)

A scripted 2-minute walkthrough with 5 example questions will live in `demo.md`.
