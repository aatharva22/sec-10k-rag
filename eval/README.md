# Eval harness

A small grounded-RAG eval that runs against the live `/query` endpoint and produces four metrics — no LLM judge required.

## What it measures

| Metric | How it's computed |
|---|---|
| **Exact grounding rate** | For every citation the LLM returns, is `citation.quote` a verbatim (whitespace-collapsed, case-insensitive) substring of the cited chunk's text in the DB? The strictest test — a passing citation is byte-for-byte auditable. |
| **Fuzzy grounding rate** | Word-set overlap fallback: ≥70% of the quote's non-stopword words appear in the chunk text. Catches "the LLM paraphrased a real passage" — still defensible (the chunk really does say the claim), just not as auditable as verbatim. |
| **Refusal rate (LLM)** | On out-of-corpus questions, did the LLM **choose** to refuse? Distinct from "the API call failed and the backend fell back to the refusal string" — the response payload tags `refusal_source: "llm" \| "error" \| null` so the eval can tell. |
| **Citation count distribution** | Mean / min / max citations per answered in-corpus question. |

The "LLM error" distinction is important: a naive eval would happily count every failed API call as a "successful refusal" because the response shape is identical. The `refusal_source` field exists for this eval; the user-facing UI ignores it.

## Questions

`questions.jsonl` — 20 hand-curated entries:

- **15 in-corpus** (covers each ticker, multiple sections, cross-ticker comparisons, with-year and without-year variants)
- **5 out-of-corpus** (GDP, weather, medical, recipe, recent-event) — designed to test that the refusal protocol holds

Each row has `id`, `category` (`in_corpus` | `out_of_corpus`), `question`, and optional `expected_ticker` / `expected_year` for reference.

## Running

```bash
# against local dev
EVAL_API_URL=http://localhost:8000 \
DATABASE_URL=postgresql://secrag:secrag@localhost:5432/secrag \
    uv run python -m eval.run_eval

# against the deployed stack
EVAL_API_URL=https://sec-10k-rag-hg9w.onrender.com \
DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require&channel_binding=require' \
    uv run python -m eval.run_eval
```

Per-question output and a final SUMMARY are printed; the full report is written to `eval/last_report.json`.

The script exits non-zero if **fuzzy grounding < 90%** or **refusal rate < 100%** (these are CI-friendly defaults — adjust at the top of `run_eval.py`).

## Quota constraint

The Gemini free tier caps `gemini-2.5-flash` at 250 generate calls/day. A single eval run is 20 generate calls, so the harness fits comfortably on its own — but if you've been demoing the live app you may hit the daily cap before eval finishes.

When that happens the eval correctly skips quota-failed questions (`refusal_source: "error"`) rather than counting them as failures. Re-run after midnight Pacific.
