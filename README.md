# SEC 10-K RAG

A grounded chat interface over the 10-K filings of Apple, Microsoft, Amazon, Tesla, and NVIDIA across fiscal years 2022–2024. Every answer is supported by verbatim citations that link directly to the highlighted passage on SEC EDGAR.

**Live demo:** https://sec-10k-rag.vercel.app
**Backend:** https://sec-10k-rag-hg9w.onrender.com (cold start ~30–50s after 15 min idle — free tier)

The retrieval is hybrid (BM25 + dense vector, fused with Reciprocal Rank Fusion); generation is Gemini `gemini-2.5-flash` with grammar-constrained JSON output. The full design rationale is in [`DECISIONS.md`](./DECISIONS.md).

## Architecture

```
question ──► query_parser (extract ticker, fiscal_year)
         ──► Postgres metadata filter
         ──► BM25 (tsvector)         top-20  ┐
                                              ├── RRF fuse (k=60) → top-5
         ──► Vector (pgvector cosine) top-20  ┘
         ──► Gemini gemini-2.5-flash + citation-enforcing system prompt
         ──► { answer, citations[] }
```

The same Postgres database holds vectors (`pgvector` HNSW), full-text (`tsvector` + GIN), and metadata — one store, three SELECTs, no orchestration between systems.

## Stack

| Layer | Tech | Hosted on |
|---|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | Vercel |
| Backend | FastAPI on Python 3.11 + `uv` | Render |
| Database | PostgreSQL 17 + `pgvector` 0.8 | Neon |
| Embeddings | `gemini-embedding-2`, 768-dim (MRL-truncated from 3072) | Google Gemini API |
| Generation | `gemini-2.5-flash`, grammar-constrained JSON | Google Gemini API |
| Local DB | Same Postgres image via Docker Compose | docker |

## Demo

Open the [live demo](https://sec-10k-rag.vercel.app) and try these — each exercises a different code path. (First request after the backend has been idle for 15+ minutes takes ~30s to wake; subsequent answers arrive in ~3–5s.)

| Question | What it tests |
|---|---|
| *"What does Apple list as its principal competitive factors?"* | Single-filing factual lookup. The parser extracts `ticker=AAPL`, hybrid retrieval narrows to AAPL chunks, generation returns one tight answer with 2 verbatim citations. |
| *"How does NVIDIA describe export controls on AI chips?"* | Semantic match. The phrase "export controls" appears across multiple NVDA filings; the vector ranker picks the relevant Risk Factors passages even where wording differs. |
| *"Compare Tesla and NVIDIA risk factors related to supply chain"* | Cross-ticker. The parser returns `ticker=None` (deliberate — two tickers mentioned), retrieval falls back to corpus-wide, and the LLM grounds its comparison in citations from both companies. |
| *"What was the GDP of France in 2023?"* | Refusal path. The LLM is instructed to refuse with a verbatim string when context is insufficient; the UI detects that string and renders a muted refusal bubble with no citations. |

**Citations are deep-linked.** Click any citation card and the SEC filing opens scrolled to (and highlighting) the exact quoted text — uses the browser's [Text Fragment](https://developer.mozilla.org/en-US/docs/Web/Text_fragments) syntax (`#:~:text=…`). Works in Chromium and Safari 16.1+; Firefox lands at the top of the page.

**Inspect the retrieval, not just the answer.** Filter chips above the composer scope every query to a specific ticker or fiscal year. Each assistant message includes a latency badge with a `retrieve/generate` ms breakdown. Hit "Show retrieval details" on any answer to see, per citation, which ranker found it: `BM25 #3 · Vec #1 · RRF 0.0323`. RRF is doing real work; the UI lets you see it.

## Evaluation

See [`eval/`](./eval) for a small grounded-RAG eval harness that runs against the live `/query` endpoint. Four metrics, no LLM judge:

- **Exact grounding** — is each citation a verbatim substring of its cited chunk?
- **Fuzzy grounding** — ≥70% word-set overlap (catches paraphrased-but-correct citations)
- **Refusal rate** — on out-of-corpus questions, did the LLM **choose** to refuse? (distinct from "API call failed", via the response's `refusal_source` field)
- **Citation count distribution** — mean / min / max per answered question

20 hand-curated questions (15 in-corpus across all 5 tickers + 5 out-of-corpus). Run with:

```bash
EVAL_API_URL=http://localhost:8000 uv run python -m eval.run_eval
```

The harness correctly skips upstream errors (e.g. Gemini quota) instead of counting them as test failures — see [`eval/README.md`](./eval/README.md) for the full methodology.

## Quick start (local dev)

You'll need: Docker, [`uv`](https://docs.astral.sh/uv/), Node 20+, and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
# 1. clone + Python env
git clone https://github.com/aatharva22/sec-10k-rag.git
cd sec-10k-rag
uv sync

# 2. start local Postgres (with pgvector)
docker compose up -d

# 3. env vars
cp .env.example .env
# then edit .env to set:
#   GEMINI_API_KEY=...
#   SEC_USER_AGENT="Your Name your.email@example.com"

# 4. ingest the corpus (~25 min on a fresh Gemini free-tier key)
#    re-downloads the 15 10-Ks from EDGAR, parses, chunks, embeds, inserts.
uv run python -m ingestion.download_filings   # populates data/filings/
uv run python -m ingestion.pipeline           # parse → chunk → embed → insert

# 5. backend
uv run uvicorn api.main:app --reload
# → http://localhost:8000  (GET /health, POST /query)

# 6. frontend (in a second terminal)
cd web
npm install
npm run dev
# → http://localhost:3000
```

**One gotcha:** the ingestion step burns ~1,531 Gemini embedding calls. On the free tier (1,000 calls/day) you'll hit the daily quota partway through — the pipeline picks up where it left off when you re-run it after midnight Pacific. The full DECISIONS.md Phase 3 entry has the gory details.

## Smoke tests (after ingestion)

```bash
# pure-vector cosine search
uv run python -m ingestion.search "Apple risk factors" --ticker AAPL --year 2023

# hybrid (BM25 + vector + RRF)
uv run python -m api.services.retrieval "supply chain disruption" --top-k 5

# end-to-end (parser → retrieval → generation)
uv run python -m api.services.generation "What does Apple list as its principal competitive factors?"
```

Each prints the query, the retrieved chunks, and (for the last one) the grounded answer with citations.

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Scaffold | done |
| 1 | Ingestion (15 10-Ks from EDGAR) | done |
| 2 | Parse + chunk (selectolax + canonical-title chunker) | done |
| 3 | Embed + store + indexes | done (15/15 filings, 1,531 chunks) |
| 4 | Retrieval service (hybrid + RRF) | done |
| 5 | Generation service (Gemini, swappable) | done |
| 6 | FastAPI wiring | done |
| 7 | Next.js chat UI | done |
| 8 | README polish + demo script | done |

## Deployment

The three services are independent and on separate providers:

- **Vercel** (frontend) — root directory set to `web/`, `NEXT_PUBLIC_API_URL` env var points at the Render URL.
- **Render** (backend) — `Procfile` defines the start command, build runs `pip install uv && uv sync --frozen`. Env vars: `GEMINI_API_KEY`, `DATABASE_URL` (the Neon **direct** endpoint, not the pooler), and `CORS_ORIGINS` (the Vercel URL).
- **Neon** (database) — pgvector enabled, schema applied from `sql/001_init.sql`, data restored from a `pg_dump --data-only` of the local Postgres. Use the non-pooled endpoint so role-level `search_path` defaults apply.

Free-tier caveats: Render web services sleep after 15 min idle and take ~30–50s to wake. Neon compute suspends after 5 min idle but wakes in 1–2s. Gemini free tier caps at 1,000 embeddings/day.

## Files

- [`DECISIONS.md`](./DECISIONS.md) — every non-obvious choice and the trade-off it cost
- [`docker-compose.yml`](./docker-compose.yml) — local Postgres + pgvector
- [`pyproject.toml`](./pyproject.toml) — Python deps via `uv`
- [`Procfile`](./Procfile) — Render start command
- [`sql/001_init.sql`](./sql/001_init.sql) — DB schema (tables, HNSW + GIN + btree indexes)
- `ingestion/` — `download_filings → parse_filings → chunk_filings → embed_and_store → pipeline`
- `api/` — FastAPI app: `main.py`, `routes/`, `services/{query_parser,retrieval,generation}.py`
- `web/` — Next.js chat UI; entry points at `app/page.tsx` and `components/Chat.tsx`
- `eval/` — grounded-RAG eval harness: `questions.jsonl` + `run_eval.py` + `README.md`
- `.claude/skills/` — domain playbooks for `parse-10k`, `hybrid-retrieval`, `grounded-generation`
