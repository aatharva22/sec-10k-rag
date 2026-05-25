# Decisions

A running log of non-obvious choices and their tradeoffs. Each entry is honest about what we gave up.

---

## Phase 0 — Scaffold

### Postgres with pgvector for *everything* (vectors, BM25, metadata)
**Choice:** Single Postgres database with the `pgvector` extension. BM25 via `tsvector` + `GIN` index. Metadata in normal columns with `btree` indexes.
**Why:** A dedicated vector DB (Qdrant, Weaviate, Pinecone) is overkill for ~3–5K chunks, and using one store for vectors + BM25 + filters keeps the retrieval SQL honest — we can read the actual query and see exactly what's happening. Hybrid search becomes "two SELECTs and a fusion" instead of orchestrating two systems.
**Tradeoff:** Doesn't scale beyond ~1M vectors gracefully. HNSW in pgvector is a few percentage points behind purpose-built indexes on recall. For an interview demo on 15 filings, the tradeoff is worth it.

### `uv` for Python env / deps
**Choice:** `uv` with `pyproject.toml` + `uv.lock`.
**Why:** Fastest install, deterministic lockfile, single tool replaces `pip` + `venv` + `pip-tools`. This is what new Python projects in 2025/26 should be using by default.
**Tradeoff:** Less familiar than `pip` for tutorial-readers, but `uv sync` / `uv run` are one-liners — the learning cost is minutes.

### `psycopg` v3 directly, no ORM
**Choice:** Raw SQL via `psycopg[binary,pool]`. No SQLAlchemy.
**Why:** Matches the "build the layers manually" intent of the project. The interesting queries (HNSW `<=>`, `ts_rank_cd`, RRF fusion) read most naturally as SQL — an ORM would just hide them. Connection pool is built into psycopg 3.
**Tradeoff:** No automatic migration tool; we'll manage schema by hand via `sql/001_init.sql`. Fine for a 1-schema project.

### Pin Postgres image to `pgvector/pgvector:pg16` (not `latest`)
**Choice:** Specific major-version tag.
**Why:** `latest` will silently upgrade and could change operator semantics (`<=>`, HNSW build options). For a repo I want to come back to in 6 months, that's a footgun.
**Tradeoff:** I have to bump the tag intentionally to pick up improvements. Worth it for reproducibility.

### HTML / iXBRL primary doc (not PDF) for 10-Ks
**Choice:** Parse the canonical HTML 10-K from EDGAR.
**Why:** SEC's primary filing format is iXBRL HTML. It has real DOM structure, real `Item N.` headings, and no OCR noise. PDF renders the same content but tables become messy and we'd need pdfplumber + heuristics.
**Tradeoff:** A small minority of older filings might be malformed; we'll fall back to BeautifulSoup if `selectolax` chokes.

### `gemini-embedding-001` at `output_dimensionality=768` (not 3072)
**Choice:** MRL-truncated 768-dim embeddings, separate `task_type` for query vs document.
**Why:** Matryoshka-trained models let you truncate without much quality loss; 768 dims keeps the HNSW index ~4× smaller and queries faster, at marginal recall cost on a small corpus. Using `RETRIEVAL_DOCUMENT` for chunks and `RETRIEVAL_QUERY` for the user's question is a documented quality improvement — different projections for different sides of the dot product.
**Tradeoff:** Bigger dims would buy a tiny recall improvement on ambiguous queries. Not worth the storage/perf cost at our scale.

### `gemini-2.5-flash` for generation, behind a one-file swappable interface
**Choice:** All Gemini calls live in `api/services/generation.py` behind a `generate(question, chunks) -> AnswerWithCitations` function.
**Why:** Flash is free-tier-friendly and fast enough for an interactive UI. The wrapper means swapping to `claude-sonnet-4-6` later is a single-file edit, not a hunt across the codebase. The `AnswerWithCitations` schema is provider-agnostic.
**Tradeoff:** Flash is weaker than Pro/Opus on multi-step reasoning. For grounded extraction over 5 chunks of curated context, that gap is small.

---

## Phase 1 — Ingestion

### 15 parallel subagents (one per ticker × fiscal_year), not one asyncio script
**Choice:** Fanned out 15 Claude Code subagents in parallel. Each agent independently fetched the submissions JSON, located the 10-K, downloaded the primary HTML, and returned a structured manifest entry.
**Why:** Cheap to try (the user asked for it), each agent has isolated context so a weird per-filing edge case doesn't poison the others, and ~15 independent ~20s downloads complete in roughly the time of one. Aggregation back in the parent is trivial — just parse 15 JSON lines.
**Tradeoff:** Zero HTTP connection reuse across agents, 15× prompt-evaluation overhead, harder to re-run deterministically. For a one-shot bootstrap that's fine; if we ever need to re-download or re-verify, `ingestion/download_filings.py` will become a real `httpx.AsyncClient`-based script that reads `manifest.json` as the source of truth.

### Hardcoded CIKs instead of resolving from `company_tickers.json`
**Choice:** Pass each subagent the CIK directly (e.g. AAPL → 0000320193).
**Why:** CIKs don't change. Skipping the lookup removes one round trip per ticker and one possible failure mode (the company_tickers.json shape isn't great — it's an object keyed by integer strings). Documented in the subagent prompts so the choice is visible.
**Tradeoff:** Adding a new ticker requires editing a constant. Worth it for 5 tickers.

### Match 10-K by `reportDate` year, not by `filingDate` year
**Choice:** "Fiscal year N" = the 10-K whose `reportDate` starts with `N` in the submissions JSON.
**Why:** Filing dates lag fiscal-year-end by 2–3 months and lag varies by company. TSLA FY2022 was filed in Jan 2023; AAPL FY2022 was filed in Oct 2022. Filtering by `filingDate` would mix fiscal years. `reportDate` is the period end — that's the canonical fiscal-year anchor.
**Tradeoff:** Companies that change fiscal-year-end mid-life would confuse this — none of our 5 have done so recently.

### Filename scheme: `data/filings/{TICKER}/{fiscal_year}.html`
**Choice:** Two levels (ticker dir, year file) rather than a flat `AAPL_2023_10K.html`.
**Why:** `ls data/filings/AAPL/` is the natural way to see all of one company's filings. The flat scheme would scatter related files alphabetically and complicate per-ticker globbing in Phase 2.
**Tradeoff:** None meaningful.

### Commit `manifest.json` but gitignore the HTML
**Choice:** `.gitignore` keeps `manifest.json` tracked; the multi-megabyte HTML files stay local-only and are reproducible from the URLs + sha256s in the manifest.
**Why:** The manifest is the *proof* of which exact filings we used — useful for interview review and for anyone re-running the pipeline. The HTML bloats the repo unnecessarily (~55 MB total) and is reproducible.
**Tradeoff:** Someone cloning the repo can't run Phase 2 immediately — they need to re-download. The download script (when implemented) will validate against `manifest.json` sha256s so re-downloads are deterministic.

### NVIDIA fiscal-year naming gotcha
**Note (not a decision per se):** NVIDIA's fiscal year ends in late January. NVIDIA itself calls the 10-K filed in Feb 2024 (reportDate 2024-01-28) "Fiscal 2024". Our convention matches that: we group it under fiscal_year=2024 because reportDate year is 2024. This aligns with NVIDIA's own labeling and avoids confusing users who ask "What did NVIDIA say in FY2024?"



## Phase 2 — Parsing + chunking *(to be appended)*

## Phase 3 — Embedding + storage *(to be appended)*

## Phase 4 — Retrieval *(to be appended)*

## Phase 5 — Generation *(to be appended)*

## Phase 6 — API *(to be appended)*

## Phase 7 — UI *(to be appended)*
