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



## Phase 2 — Parsing + chunking

### selectolax with regex preprocessing for iXBRL hidden facts
**Choice:** Strip `<ix:hidden>`, `<ix:header>`, `<ix:references>`, `<ix:resources>` blocks with a regex BEFORE handing the HTML to selectolax, then drop `[style*="display:none"]` via selectolax CSS.
**Why:** SEC iXBRL files start with hundreds of machine-readable XBRL "facts" (`false`, `2023`, `FY`, FASB taxonomy URLs) that aren't visible in a rendered filing but flood the text extraction. selectolax's HTML5 parser doesn't reliably target namespaced tags via CSS, so a regex pre-pass is the most robust way to remove them.
**Tradeoff:** Two parse passes (regex + DOM). Negligible cost — strip cuts AAPL 2023 from 218k chars of mixed noise to 202k chars of real text.

### Section dedup: keep the LAST `Item N.` match per code
**Choice:** When `Item N.` appears more than once in the parsed text, keep only the latest occurrence as the section start.
**Why:** 10-Ks frequently mention "Item 16" or "Item 1A" in the cautionary statements / forward-looking disclaimer at the top, which my regex was mis-identifying as a real section header. The actual section content always comes after the ToC. The simple "last occurrence wins" rule works because real sections appear at the end of the document in document order.
**Tradeoff:** Fails if an Item is mentioned in a later section's body (e.g. Item 7 referencing Item 1A's risk factors) — the in-body reference would steal the section header. In practice modern 10-Ks reference items by full name ("Risk Factors", not "Item 1A.") so this hasn't bitten us across the 15 filings.

### Section labels stay in chunk text, not just metadata
**Choice:** Prepend `[Item 1A. Risk Factors]\n\n` to every chunk's text, in addition to storing the section as a metadata field on the Chunk.
**Why:** Mid-section chunks otherwise have no context about which section they belong to. Adding the label inside the chunk text lets the embedding "see" the section topic, which helps queries like "Apple's risk factors" match chunks that don't contain those exact words. Costs ~10 tokens per chunk — negligible vs. 800-token chunks.
**Tradeoff:** The very first chunk of each section has the heading twice (once prepended, once naturally at the top of the body). Tiny redundancy, not worth special-casing.

### `MIN_SECTION_CHARS = 1000` to filter ToC entries
**Choice:** Sections shorter than 1000 chars are dropped from the section list.
**Why:** Even after dedup, some short fragments survive (e.g. when a heading appears in a copyright disclaimer paragraph). A real 10-K section is at least a few paragraphs (~1000 chars). The threshold drops ToC-like fragments without losing real content (the shortest legitimate section in our 15 filings is ~2000 chars).
**Tradeoff:** If a filing has a genuinely tiny section ("Item 6: Reserved"), it gets dropped. Acceptable — those sections have no information value anyway.

### Chunk math: 800 tokens / 80 overlap / cl100k_base proxy
**Choice:** 800-token chunks with 80-token overlap, measured by `tiktoken cl100k_base`.
**Why:** cl100k_base is not Gemini's tokenizer, but it's a close enough proxy for sizing chunks without per-chunk API calls. The chunk size leaves room for: top-5 chunks × 800 tokens = 4K context tokens, plus the question (~50 tokens), plus the system prompt (~200 tokens) — well within gemini-2.5-flash's 1M-token window with massive headroom for the answer.
**Tradeoff:** Gemini's actual tokenizer counts may be 5–10% different. If we ever want true byte-perfect chunk sizing, we'd batch-call Gemini's `count_tokens`. Not worth the API hit for sizing.

### Smoke-test results across 15 filings
| ticker | year | text chars | sections | chunks |
|---|---|---|---|---|
| AAPL | 2022 | 217k | 10 | 65 |
| AAPL | 2023 | 202k | 10 | 60 |
| AAPL | 2024 | 206k | 13 | 64 |
| AMZN | 2022–2024 | 271k–286k | 10–12 | 81–85 |
| MSFT | 2022 | 394k | 14 | 103 |
| MSFT | 2023 | 442k | 15 | 157 |
| MSFT | 2024 | 462k | 15 | 163 |
| NVDA | 2022–2024 | 309k–343k | 9–10 | 87–96 |
| TSLA | 2022 | 489k | 12 | 162 |
| TSLA | 2023 | 401k | 12 | 119 |
| TSLA | 2024 | 389k | 11 | 115 |
| **total** | | | | **1,533** |



## Phase 3 — Embedding + storage

### Switched embedding model: `gemini-embedding-001` → `gemini-embedding-2`
**Context:** The original spec called for `gemini-embedding-001, free tier, 768 dims`. In practice that model returns 429 RESOURCE_EXHAUSTED on a free-tier API key — it's gated to paid plans. `text-embedding-004` (the obvious fallback) wasn't in the model list for this key either; it's been deprecated. The available free-tier embedding model is `gemini-embedding-2`, which is *newer* than 001 — Google's current general-purpose embedding family.
**Choice:** Use `gemini-embedding-2` with `output_dimensionality=768` (MRL truncation from 3072).
**Why:** Free tier accessible. Matches the existing `vector(768)` column without schema change. Newer architecture than 001. Task-type API (`RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`) works identically.
**Tradeoff:** "Experimental"-adjacent — Google has churned this family fast. If `gemini-embedding-2` is later deprecated, re-embedding is a single-config change and one pipeline re-run. Worth flagging in the README so future readers know why it changed.

### `embed_content` does NOT batch — discovered the hard way
**Bug found:** The google-genai SDK's `client.models.embed_content(contents=[t1, t2, ..., t50])` accepts a list, but the API treats the list as multiple *parts* of a SINGLE Content and returns ONE embedding. My initial "batch of 50" was embedding only the first text and discarding 49 — the assertion `len(chunks) == len(embeddings)` caught it.
**Choice:** Serial loop, one chunk per `embed_content` call, with `MIN_INTERVAL_SEC = 0.5` (~120 RPM ceiling) and exponential backoff on 429.
**Why:** True batching requires `asyncBatchEmbedContent` — an async batch-job endpoint that returns results later via polling. For 1,533 chunks, a 25-minute serial loop with retries is far simpler than orchestrating a batch job.
**Tradeoff:** Slow first-time ingest. On re-runs the `_already_ingested` check skips processed filings, so the only cost is the initial bootstrap.

### Daily free-tier cap hit at chunk 778 (8/15 filings)
**What happened:** Mid-ingest, the pipeline started seeing persistent `RESOURCE_EXHAUSTED` errors that survived the full retry+backoff chain (up to 126s). The error detail revealed the cause: `EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier, limit: 1000`. We've burned through the day's 1000 free-tier embed calls.
**State when stopped:** AAPL × 3, MSFT × 3, AMZN × 2 = 8 filings, 778 chunks in DB. Missing: AMZN 2024, TSLA × 3, NVDA × 3.
**Plan:** Wait for the daily quota to reset (midnight Pacific). Tomorrow: drop the existing chunks (they were embedded with the v1 chunker that had the MSFT bug — see next entry), re-ingest all 15 filings with the fixed chunker. Total cost: ~1,533 embed calls — within the 1,000/day cap *only if* we resume within 24 hours of reset and don't hit the daily cap again. If we do, finish over two days.

### MSFT chunker bug → fix: canonical title lookup + ordering enforcement
**Bug:** The v1 chunker used `Item N.` regex matches + `last-occurrence-wins` dedup. That works for filings like AAPL where Item codes appear only in the ToC and at the real section header. But MSFT's HTML preserves *per-page header repetitions* (`PART I, Item 1. Business` on every printed page), so a single Item code had 10+ matches and `last-occurrence` picked a header *inside* the wrong section. The result: `Item 1. AVAILABLE INFORMATION` as a section label, with the body actually spanning past the real Item 1.
**Fix, in three layers:**
1. **Largest-body wins** instead of last-occurrence. For each Item code, pick the match whose distance to the next match is biggest — real section starts have a long stretch of content, while ToC entries and page-headers are tightly packed.
2. **Canonical title lookup.** SEC mandates the title for each 10-K Item ("Risk Factors" for 1A, "Properties" for 2, etc.). The chunker now uses a hardcoded `_CANONICAL_TITLES` map for the label instead of trying to extract the title from text, which is unreliable across filing layouts. Citations stay clean regardless of HTML quirks.
3. **Canonical-order enforcement.** After picking matches, walk the canonical 10-K Item order (`1, 1A, 1B, 1C, 2, 3, 4, 5, 6, 7, 7A, 8, 9, 9A, 9B, 9C, 10-16`) and keep only matches whose position is strictly increasing. Drops ToC-only "phantom" items (e.g., AAPL's Item 11 appears only in the ToC because Apple references the proxy statement).
**Tradeoff:** If the SEC ever changes the Item layout (e.g., adds a new Item 1D), the canonical title map needs updating. Acceptable — the SEC changes 10-K structure roughly once a decade and the map is one dict.

### Free-tier rate limit observed: ~30-40 RPM
**Note:** With `MIN_INTERVAL_SEC = 0.5` (target 120 RPM), I observed 429 RESOURCE_EXHAUSTED hitting every ~25-30 successful calls. The retry/backoff recovered cleanly each time. Bumping the interval to 1.5-2.0s would eliminate most retries but slow ingest proportionally; the current setting is the right speed/cleanliness trade-off for a one-time bootstrap.

### Per-chunk embedding cost: ~1.1 seconds wall-clock (incl. retries)
**Observation:** AAPL FY2023 (60 chunks) took 66.8s end-to-end. With 1,533 total chunks across 15 filings, expect ~28 minutes for the full ingest.

### pgvector HNSW with `vector_cosine_ops`
**Choice:** `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)`.
**Why:** Gemini embeddings come out roughly unit-normalized, so cosine ≈ dot product. Cosine is the established convention for retrieval embeddings; choosing it over L2 means downstream code can think in terms of similarity (1 - distance) rather than distance. `m=16, ef_construction=64` are pgvector defaults — our 1.5K-row corpus is far too small for tuning to matter.
**Tradeoff:** HNSW uses more memory than IVFFlat at build time. Negligible at our scale.

### `tsvector` as a `GENERATED ALWAYS AS ... STORED` column
**Choice:** Postgres 12+ generated column auto-populates `tsv` from `text`. No INSERT-time work in Python.
**Why:** One less thing to forget on insert. Trigger-based approaches need extra DDL and can desync if disabled. Generated columns are always in sync with the source.
**Tradeoff:** `to_tsvector('english', text)` runs on every insert and update, slightly slowing writes. Imperceptible for our once-per-filing insert.

### Idempotent inserts via `UNIQUE (filing_id, chunk_index)` + `ON CONFLICT DO NOTHING`
**Choice:** The unique constraint on `(filing_id, chunk_index)` is what lets `ON CONFLICT DO NOTHING` work on the chunks table.
**Why:** Re-running the pipeline (after a crash, a model swap, a chunker change) should never duplicate chunks or fail. With the constraint + ON CONFLICT, a partial re-run is safe.
**Tradeoff:** If we re-chunk and the new chunks have the same `chunk_index` as old ones, they're silently skipped. The `--force` flag in `pipeline.py` is the escape hatch (it re-runs anyway; cleanup needs a separate `DELETE FROM chunks WHERE filing_id=...`).

### Skip pre-ingested filings by default
**Choice:** `pipeline.py` checks `SELECT 1 FROM chunks WHERE ticker=$1 AND fiscal_year=$2 LIMIT 1` before each filing; if a chunk exists, the filing is skipped.
**Why:** Embedding is the expensive step (~28 min for the full corpus). Skipping done filings turns a partial-run recovery from "wait 28 minutes again" into "wait for the remaining N".
**Tradeoff:** If a filing was *partially* embedded (e.g. crashed mid-loop), the check still skips it. The `--force` flag re-runs from scratch; for partial states, manually `DELETE FROM chunks WHERE ticker=X AND fiscal_year=Y` first.

### vector literal as a string (`'[0.1,0.2,...]'::vector`) — no pgvector Python package
**Choice:** Serialize embeddings as pgvector text literals in `api/db.py:vector_literal`, cast to `vector` in SQL.
**Why:** Avoids a runtime dep on the `pgvector` Python package and its psycopg adapter. The serialization is trivial (one line) and pgvector parses the literal natively.
**Tradeoff:** A tiny bit of CPU on serialization; readability tradeoff. Worth it for one fewer dep.

### Denormalize `ticker`, `fiscal_year` onto `chunks`
**Choice:** Copy these fields from `filings` to every chunk row, indexed via btree.
**Why:** The retrieval hot path is `WHERE ticker=$1 AND fiscal_year=$2 ORDER BY embedding <=> $qvec LIMIT 20`. Denormalization keeps this single-table; otherwise every search joins through `filings`. With 1,533 rows the join cost is invisible, but the point is keeping the SQL legible.
**Tradeoff:** If a company ever changes ticker (rare), we'd need to rewrite the denormalized columns. Not a concern for our 5 fixed tickers.



### Phase 3 completion — remaining 7 filings ingested after quota reset
**State now:** All 15 filings ingested. 1,531 chunks total in DB (vs. the 1,533 predicted by the smoke-test table — TSLA 2022 and 2024 each landed one chunk shorter on the re-chunk, an artifact of non-deterministic token-boundary nudging at section ends).
**Run observations:** Resume took 1,694s (~28 min) for 7 filings × 753 chunks. Free-tier throttling fired sporadically (429s after streaks of ~25-50 successful calls), but exponential backoff (2→4s waits, never beyond retry 3) absorbed every one — no chunks lost, no quota-day cliff this time. `MIN_INTERVAL_SEC=1.5` ended up well-tuned: aggressive enough to finish in one sitting, conservative enough that the daily 1,000-call cap (now 753 + 778 from yesterday = 1,531 calls across two days) wasn't a risk.
**What's next:** Phase 4 — retrieval. BM25 + vector search SQL is straightforward; the interesting work is the RRF fusion and the query parser that pulls `ticker` / `fiscal_year` filters out of the question.

---

## Phase 4 — Retrieval

### Reciprocal Rank Fusion (k=60) over BM25 + vector top-20 each
**Choice:** Two independent SELECTs against `chunks` — one BM25 (`ts_rank_cd(tsv, plainto_tsquery(...))`), one vector (`embedding <=> qvec`) — each returning the top 20 ids, fused with RRF and re-sliced to top-5.
**Why:** RRF is the standard hybrid-fusion recipe (Cormack et al. 2009) and it sidesteps the score-normalization problem entirely — BM25 returns unbounded ranks, cosine returns 0–2 distances, and trying to linearly combine those is brittle. RRF only consumes ranks: `score = 1 / (k + rank)` per ranker, summed. With `k=60` (the published default), a doc that ranks #1 in both retrievers scores ~0.033; one in only the vector list scores ~0.016 — natural decay, no tuning required for the demo corpus.
**Tradeoff:** RRF discards score magnitudes — a chunk that BM25 rates *much* higher than its neighbors loses that signal. For a corpus of 1.5K chunks and top-20 pools, the loss is invisible. On larger corpora we'd consider weighted-RRF or learned fusion.

### POOL_SIZE = 20 per ranker
**Choice:** Pull 20 from each ranker before fusion, return top-5 to the LLM.
**Why:** 20 gives RRF enough overlap to discriminate (a doc has to appear well-ranked in *at least one* list to even be considered, and ideally ranks well in both). Pool of 10 was too tight — borderline-relevant chunks could miss the cutoff entirely. Pool of 50 added latency without changing top-5 in spot-checks.
**Tradeoff:** With our pre-filter `WHERE tsv @@ plainto_tsquery(...)`, BM25 may return fewer than 20 rows for short questions — RRF handles that fine, but it's worth knowing if you debug a sparse fusion result.

### Sync retrieval, not async
**Choice:** `hybrid_search` is a plain function that runs the two SELECTs sequentially on one psycopg connection. The original docstring said `async def ... asyncio.gather(...)`.
**Why:** On our 1.5K-chunk corpus each SELECT is sub-50ms. Two sequential queries on a warm connection take ~30-80ms total; spinning up async, opening two connections, and gathering would add ~30ms of overhead for ~20ms of theoretical parallelism. We'll revisit when Phase 6 adds the async psycopg pool — at that point the route handler itself is async and parallelism is essentially free, but the retrieval logic stays the same.
**Tradeoff:** If we ever federate retrieval across multiple stores (e.g. add Elasticsearch alongside Postgres) async will be unavoidable. Not the case today.

### Deterministic query parser, no LLM
**Choice:** `query_parser.parse(question) -> (ticker, year)` using compiled regex for the 5 known tickers, 5 company-name keywords, and the 3 valid fiscal years. If multiple tickers or years are mentioned, the field returns None (caller falls back to corpus-wide retrieval).
**Why:** The supported set is tiny and fixed. An LLM call would be ~500ms of latency and a non-deterministic failure mode for a job a regex does in microseconds. Returning None on ambiguity is honest — "Apple vs. Microsoft 2023" really *is* a cross-ticker question.
**Tradeoff:** Misses creative aliases ("the iPhone maker", "Cupertino", "Big Tech"). For a demo where the user is shown the supported tickers, that's acceptable. If we ever broaden the corpus to S&P 500, we'd swap in an entity-recognition step.

### Vector literal trick reused; no pgvector Python adapter
**Note:** Same call as Phase 3 — `vector_literal(qvec)` produces a string and we cast `%s::vector` in SQL. Keeps Phase 4 dep-free.

---

## Phase 5 — Generation

### Gemini structured output (response_schema) over hand-parsing JSON
**Choice:** `GenerateContentConfig(response_mime_type="application/json", response_schema=_LLMAnswer)` where `_LLMAnswer` is a Pydantic model. The SDK enforces the schema server-side; we just `_LLMAnswer.model_validate_json(resp.text)` on return.
**Why:** Without `response_schema`, the model emits free-form JSON-ish text that needs a regex-cleanup + retry-on-malformed pass. The grammar-constrained decoding is essentially free quality and removes a class of "trailing commas / unescaped quotes" parse failures. Pydantic validation catches the remaining drift (wrong field types, missing fields) cheaply.
**Tradeoff:** Tied to providers that support grammar-constrained decoding. Swapping to Anthropic would mean using tool-use for JSON enforcement or going back to instructed-JSON. The generation.py module is the *one* file to touch; everything else stays put.

### Two-layer schema: `_LLMAnswer` (LLM-facing) vs `AnswerWithCitations` (public)
**Choice:** The LLM is asked to return `_LLMAnswer { answer, citations: [{ chunk_id, quote }] }` — just the data only the model can produce. The public `AnswerWithCitations` carries the richer `Citation { chunk_id, ticker, fiscal_year, section, quote, source_url }`. `_build_response` joins the LLM's `chunk_id` back to the retrieved `Chunk` object to populate the extra fields.
**Why:** Asking the LLM to copy ticker/year/section/url for each citation invites drift — the model would occasionally pluralize, abbreviate, or paraphrase metadata, and we'd never trust those fields. Re-deriving from the input `Chunk` makes them ground-truth by construction. We also drop any citation whose `chunk_id` isn't in the input set, which defends against hallucinated ids.
**Tradeoff:** Two schemas instead of one. Trivial cost — the lookup is one dict access per citation.

### System prompt enforces refusal verbatim and forbids outside knowledge
**Choice:** The system prompt lists 5 short rules, including: "ground every claim in the provided excerpts", "respond with exactly: 'I don't have enough information in the provided 10-K excerpts to answer that.' and return an empty citations list" when context is insufficient.
**Why:** A short rule list with one verbatim refusal string is what the model follows most reliably for grounded QA. Verified by the "What was the GDP of France in 2023?" smoke test — the parser pulls `year=2023` and runs corpus-wide retrieval, which surfaces 10-K chunks; the model still refuses because the rules tell it to, even though some text was returned.
**Tradeoff:** A more elaborate prompt with examples might help borderline cases (e.g. partial-coverage questions). For the demo we keep the prompt short — easier to audit, fewer surface bugs.

### `temperature=0.1`, not 0
**Choice:** `temperature=0.1` on the Gemini call.
**Why:** Zero temperature with grammar-constrained decoding can produce truncated answers when the model deterministically picks the highest-probability "end" token. A tiny amount of stochasticity gives the model breathing room to finish a sentence. Still effectively deterministic for a demo.
**Tradeoff:** Two runs of the same question may differ by a word or two. Acceptable.

### Refusal as the universal failure mode
**Choice:** Empty chunks, JSON parse error, validation error, or unrecoverable API error all funnel to the same `REFUSAL` string with empty citations. The API failures log to stderr; the user sees the same polite "I don't have enough information…" message.
**Why:** From the user's perspective the cause doesn't matter — they need an answer they can trust or a clear refusal. Mixing "no context" with "API timed out" responses leaks implementation detail and erodes confidence. Logs preserve the diagnostic info for us.
**Tradeoff:** A persistent provider outage looks the same as repeatedly asking out-of-corpus questions. The `/health` route (Phase 6) will expose provider status separately for monitoring.

### `gemini-2.5-flash` for generation
**Choice:** Same as planned in Phase 0.
**Why:** Fast (~1-3s for the 5-chunk grounded prompt), free-tier accessible, capable enough for grounded extraction over curated context. The `flash` family is tuned for exactly this kind of retrieval-augmented use.
**Tradeoff:** For genuinely tricky multi-step reasoning over the citations, `gemini-2.5-pro` or `claude-opus-4-7` would be stronger. Single-file swap when needed.

---

## Phase 6 — API

### Sync handlers, no async psycopg pool
**Choice:** Both routes are `def post_query` / `def get_health` (not `async def`). They call `retrieval.hybrid_search` and `generation.generate` directly. No connection pool — `sync_conn()` opens a fresh psycopg connection per request inside a `with` block.
**Why:** FastAPI dispatches `def` handlers to its own anyio threadpool, so a slow handler doesn't block the event loop. At our scale (1.5K chunks, single-user demo), one connection open + several queries on the same cursor totals ~30-80ms — connection setup is a small fraction of the LLM call (~1-3s). A pool would shave ~30ms off each request and add a startup/shutdown lifecycle to maintain. We can introduce `psycopg_pool.ConnectionPool` later in a single-file edit to `api/db.py` without touching the routes.
**Tradeoff:** Under genuine concurrent load the threadpool would become the bottleneck (defaults to 40 threads). For a Next.js front-end with one user this is invisible. Don't deploy this as-is to a multi-tenant service.

### `/query` route is a thin pass-through to the three services
**Choice:** `post_query` does five things: validate the question is non-empty (400 on blank), call `query_parser.parse`, call `retrieval.hybrid_search`, call `generation.generate`, return `QueryResponse`. Any unexpected exception logs the traceback and surfaces as a 503 with `"upstream failure — try again"`.
**Why:** The pipeline contract was set in Phases 4 and 5 — the route doesn't need to make further decisions. Hiding the cause behind a generic 503 matches the same trust-preserving principle as the `REFUSAL` constant in generation: don't leak provider state. Logs preserve diagnostics for us.
**Tradeoff:** A clever caller can't distinguish "Gemini quota exhausted" from "Postgres down". `/health` exposes db status separately; provider health is intentionally not surfaced. If we ever need to differentiate, add specific HTTPException raises per failure type — but a single 503 + good logging has been enough so far.

### `/health` does both `SELECT 1` and `SELECT count(*) FROM chunks`
**Choice:** Two queries in the health check — a connectivity probe (`SELECT 1`) and a corpus-presence probe (`SELECT count(*)`).
**Why:** `SELECT 1` proves the connection works; `count(*) FROM chunks` proves the schema is initialized and ingestion ran. A new dev cloning the repo and forgetting to run ingestion sees `"chunks": 0` and knows what to do — without needing to dig into the database.
**Tradeoff:** `count(*)` on a 1.5K row table is microseconds. On a 10M-row chunks table this would slow the health check; we'd switch to a cheaper sentinel (e.g. `EXISTS (SELECT 1 FROM chunks LIMIT 1)`). Not a concern at our scale.

### CORS locked to `http://localhost:3000`, methods `GET, POST`
**Choice:** Only the Next.js dev origin, only the methods we actually expose.
**Why:** No public deployment, no third-party callers. Tight CORS is the default; loosen only if a real use case appears. `allow_credentials=True` is needed for `fetch()` with cookies, even though we don't currently use cookies — keeps the option open without a config change.
**Tradeoff:** Deploying to a custom domain later means adding it to `allow_origins`. One-line edit.

---

## Phase 7 — UI *(to be appended)*
