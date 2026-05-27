---
name: hybrid-retrieval
description: Hybrid BM25 + vector retrieval with RRF fusion over Postgres/pgvector. Use whenever retrieving chunks from the SEC 10-K corpus, debugging poor retrieval quality, tuning the pool size or RRF k, or extending the pipeline (new rankers, new metadata filters, async pool).
---

# Hybrid Retrieval Pipeline

The end-to-end flow that turns a free-form question into the top-5 chunks the LLM sees.

## Pipeline

```
question ──► query_parser.parse()        ──► (ticker?, fiscal_year?)
         ──► embed_query()  [Gemini, task_type=RETRIEVAL_QUERY]
         ──► [BM25 SELECT, top-20]   ┐
                                      ├── one psycopg connection, sequential
             [Vector SELECT, top-20]  ┘
         ──► RRF fuse (k=60)
         ──► hydrate top-k to Chunk rows
```

All three SELECTs hit the same `chunks` table — BM25 via `tsv @@ plainto_tsquery + ts_rank_cd`, vector via `embedding <=> qvec` over the HNSW index, and the hydration via `WHERE id = ANY(%s)`.

## Where the code lives

| Component | File | Function |
|---|---|---|
| Public API | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `hybrid_search(question, ticker, fiscal_year, top_k)` |
| BM25 SELECT | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `_bm25_search` |
| Vector SELECT | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `_vector_search` |
| RRF fusion | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `_rrf_fuse` |
| WHERE filter builder | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `_build_where` |
| Hydration | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `_hydrate` |
| Query parser | [`api/services/query_parser.py`](../../../api/services/query_parser.py) | `parse(question)` |
| Query embedding | [`ingestion/embed_and_store.py`](../../../ingestion/embed_and_store.py) | `embed_query` |
| pgvector literal | [`api/db.py`](../../../api/db.py) | `vector_literal` |
| Schema (chunks, indexes) | [`sql/001_init.sql`](../../../sql/001_init.sql) | — |
| CLI smoke-tester | [`api/services/retrieval.py`](../../../api/services/retrieval.py) | `python -m api.services.retrieval "<question>" --ticker X --year Y` |
| Phase 3 vector-only verifier | [`ingestion/search.py`](../../../ingestion/search.py) | — (kept for diffing against hybrid) |

## Constants and why

| Constant | Value | Reason |
|---|---|---|
| `POOL_SIZE` | 20 | Enough overlap for RRF to discriminate. 10 was too tight; 50 added latency without changing top-5. |
| `RRF_K` | 60 | Cormack et al. 2009 published default. No tuning needed at our scale. |
| `top_k` (default arg) | 5 | What we send to Gemini. 5 × 800 tokens ≈ 4K context tokens — comfortable. |
| `task_type` for query | `RETRIEVAL_QUERY` | Different projection than `RETRIEVAL_DOCUMENT` used during ingest. Documented quality improvement. |
| Embedding dim | 768 | MRL-truncated from `gemini-embedding-2`'s native 3072. Matches `vector(768)` column. |
| HNSW operator | `vector_cosine_ops` | Gemini embeddings are roughly unit-norm so cosine ≈ dot product. Same op used at ingest. |

All defined at the top of `api/services/retrieval.py`.

## Metadata filter rules

The query parser returns `(ticker, fiscal_year)`, either possibly `None`:

- **Both set** → narrow to a single filing's chunks (~60–160 candidates).
- **Ticker only** → narrow to one company's 3 fiscal years.
- **Year only** → narrow to 5 companies × 1 year.
- **Neither** → corpus-wide retrieval over all 1,531 chunks.

If the question mentions multiple distinct tickers or years (e.g. "Apple vs Microsoft 2023"), the parser deliberately returns `None` for that field. Don't guess — let the retriever surface chunks from both candidates and let the LLM reason across them.

The filter is composed in `_build_where` and shared by both rankers, so BM25 and vector see the same candidate pool. **Never put the filter only on one ranker** — the fused list would be inconsistent.

## RRF mechanics

```python
score(doc) = sum over rankers of  1 / (RRF_K + rank_in_ranker(doc))
```

A doc that lands at rank #1 in both BM25 and vector scores `2 * 1/61 ≈ 0.0328`. A doc only in the vector list at rank #5 scores `1/65 ≈ 0.0154`. The function only consumes *ranks*, never raw BM25 or cosine scores — so the unit mismatch between the two rankers never matters.

**Why not score-normalize and combine?** BM25 scores are unbounded and depend on document length; cosine distances are 0–2. Linear combination would need to be re-tuned on every corpus change. RRF is parameter-light and survives schema evolution.

## Failure modes and how we handle them

| Symptom | Cause | Mitigation |
|---|---|---|
| BM25 returns zero rows for very short / very generic queries | `plainto_tsquery` produces an empty tsquery on stopword-only input | Vector ranker still returns 20 hits; RRF degrades to vector-only. No special-case needed in code. |
| Question mentions two tickers ("AAPL vs MSFT") | Parser returns `ticker=None` on ambiguity | Caller falls back to corpus-wide retrieval. LLM sees chunks from both — desired. |
| Section label looks wrong (e.g. `Item 2. Properties` content that's actually `Competition`) | Chunker artifact — MSFT-style filings have per-page headers that bleed across section boundaries; see [`ingestion/chunk_filings.py`](../../../ingestion/chunk_filings.py) | Live with it. The chunk *text* is still relevant; the *label* is metadata. Future fix: trust position-in-document over header-derived labels. |
| Same chunk surfaces from both rankers at top | Common for high-quality matches | Working as intended — RRF rewards consensus. |
| Empty result set from `hybrid_search` | All three SELECTs returned nothing (extremely rare — filter knocked out every row) | `hybrid_search` returns `[]`. Caller (route handler) should respond with "no relevant context found" rather than calling the LLM. |
| Gemini embedding 429 on the query | Free-tier rate limit | `embed_query` shares the retry/backoff from `_embed_with_retry` in [`ingestion/embed_and_store.py`](../../../ingestion/embed_and_store.py). Up to 7 attempts, exponential backoff to 64s. For interactive use, surface the error after attempt 2 rather than blocking the user for 2 minutes. |

## Extension points

- **Async pool** — Phase 6 will swap `sync_conn()` for an async psycopg pool. The retrieval logic stays the same; just wrap in `async def` and `await`. Async only saves real time if we add a third ranker; with two SELECTs on one connection, sequential is fine.
- **Third ranker** — Add to the parallel block and the `_rrf_fuse` call. RRF generalizes to N rankers with no parameter changes.
- **Reranker stage** — Insert between RRF and `_hydrate`: pass the top-20 fused ids through a cross-encoder, return top-5. Cross-encoders are slow per-pair so cap at 20 inputs.
- **Per-section boosting** — Either post-RRF score multiplier by section, or filter the BM25 query to specific sections. Avoid baking section preferences into RRF directly — keeps the fusion stage corpus-agnostic.

## Smoke tests

A handful of queries that exercise the pipeline. Run any of these against the CLI to verify after touching retrieval code:

```bash
uv run python -m api.services.retrieval "What are Apple's biggest risks?" --ticker AAPL --year 2023
uv run python -m api.services.retrieval "Tesla lithium-ion battery supply chain"
uv run python -m api.services.retrieval "NVIDIA export controls on AI chips"
uv run python -m api.services.retrieval "Discuss climate change disclosures"   # corpus-wide
```

Expect: filtered queries return chunks only from the named filing(s); the corpus-wide query returns chunks from multiple tickers, with the most semantically relevant on top regardless of vendor.
