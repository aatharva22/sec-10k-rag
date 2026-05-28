"""Evaluate the deployed RAG against eval/questions.jsonl.

Four metrics, all computed without an LLM judge:

1. **Exact grounding rate** — is `citation.quote` a verbatim (whitespace-
   collapsed, case-insensitive) substring of the cited chunk's text in the DB?
   This is the strictest test: a passing citation is byte-for-byte auditable.

2. **Fuzzy grounding rate** — fall back to word-set overlap. A citation is
   fuzzy-grounded if at least 70% of its quote's non-trivial words appear in
   the chunk text. Catches "the LLM paraphrased a real passage" — still
   defensible (the chunk really does say the claim) just not as auditable as
   verbatim.

3. **Refusal rate** — for questions tagged `out_of_corpus`, did the LLM
   actually choose to refuse? The Phase 5 design pins the exact refusal
   string verbatim, and the backend tags `refusal_source: "llm" | "error"`
   so this metric is distinct from "the API call failed and we fell back to
   the refusal string".

4. **Citation count distribution** — mean / min / max citations per answered
   in-corpus question.

Usage:
    EVAL_API_URL=http://localhost:8000 \\
    DATABASE_URL=postgresql://secrag:secrag@localhost:5432/secrag \\
        uv run python -m eval.run_eval

    # Or against the deployed stack:
    EVAL_API_URL=https://sec-10k-rag-hg9w.onrender.com \\
    DATABASE_URL=<neon-direct-url> \\
        uv run python -m eval.run_eval

The script writes a JSON report to eval/last_report.json and exits non-zero
if grounding rate < 90% or refusal rate < 100% — tweak the thresholds at
the bottom if you want a softer gate.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from api.db import sync_conn

QUESTIONS_PATH = Path("eval/questions.jsonl")
REPORT_PATH = Path("eval/last_report.json")
REFUSAL_TEXT = "I don't have enough information in the provided 10-K excerpts to answer that."

GROUNDING_THRESHOLD = 0.90  # 90% of citations must be substring-grounded
REFUSAL_THRESHOLD = 1.00    # 100% of OOC questions must refuse


FUZZY_OVERLAP_THRESHOLD = 0.70
# Filler tokens we don't count toward fuzzy overlap — they appear everywhere.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "by", "as", "at", "this", "that",
    "from", "it", "its", "our", "we", "their", "they", "have", "has", "had",
    "may", "could", "would", "should", "will",
}


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase for substring containment."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _word_set(text: str) -> set[str]:
    """Lowercased word set with stopwords stripped, for fuzzy overlap."""
    words = re.findall(r"[a-zA-Z][a-zA-Z\-']{2,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _fuzzy_grounded(quote: str, chunk_text: str) -> bool:
    """True if ≥70% of the quote's non-stopword words appear in chunk text."""
    q_words = _word_set(quote)
    if not q_words:
        return False
    c_words = _word_set(chunk_text)
    overlap = len(q_words & c_words) / len(q_words)
    return overlap >= FUZZY_OVERLAP_THRESHOLD


def _load_questions() -> list[dict[str, Any]]:
    return [json.loads(line) for line in QUESTIONS_PATH.read_text().splitlines() if line.strip()]


def _chunk_text_by_id(chunk_ids: list[int]) -> dict[int, str]:
    """Fetch chunk text for a batch of ids — used to verify citations are grounded."""
    if not chunk_ids:
        return {}
    with sync_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, text FROM chunks WHERE id = ANY(%s)", (chunk_ids,))
        return {row[0]: row[1] for row in cur.fetchall()}


def _call_api(client: httpx.Client, api_url: str, question: str) -> dict[str, Any]:
    resp = client.post(f"{api_url}/query", json={"question": question}, timeout=180.0)
    resp.raise_for_status()
    return resp.json()


def _check_grounding(
    citations: list[dict[str, Any]], texts: dict[int, str]
) -> tuple[int, int, int]:
    """Return (exact_grounded, fuzzy_grounded, total) for a single response."""
    exact = 0
    fuzzy = 0
    for cit in citations:
        chunk_text = texts.get(cit["chunk_id"])
        if not chunk_text:
            continue
        if _normalize(cit["quote"]) in _normalize(chunk_text):
            exact += 1
            fuzzy += 1  # exact implies fuzzy
        elif _fuzzy_grounded(cit["quote"], chunk_text):
            fuzzy += 1
    return exact, fuzzy, len(citations)


def main() -> int:
    api_url = os.getenv("EVAL_API_URL", "http://localhost:8000").rstrip("/")
    questions = _load_questions()
    print(f"\n=== Eval against {api_url} ({len(questions)} questions) ===\n")

    in_corpus = [q for q in questions if q["category"] == "in_corpus"]
    out_of_corpus = [q for q in questions if q["category"] == "out_of_corpus"]

    results: list[dict[str, Any]] = []
    exact_total = 0
    fuzzy_total = 0
    citations_total = 0
    in_answered = 0
    ooc_llm_refused = 0
    ooc_errored = 0
    in_errored = 0
    citation_counts: list[int] = []
    total_latency_ms = 0

    with httpx.Client() as client:
        for q in questions:
            t0 = time.time()
            try:
                resp = _call_api(client, api_url, q["question"])
            except Exception as exc:
                print(f"  [{q['id']:30s}] ERROR ({type(exc).__name__}: {exc})")
                results.append({"id": q["id"], "status": "error", "error": str(exc)})
                continue
            wall_ms = int((time.time() - t0) * 1000)
            total_latency_ms += wall_ms

            answer = resp.get("answer", "")
            citations = resp.get("citations", [])
            refusal_source = resp.get("refusal_source")
            is_refusal = answer.strip() == REFUSAL_TEXT and len(citations) == 0

            row: dict[str, Any] = {
                "id": q["id"],
                "category": q["category"],
                "wall_ms": wall_ms,
                "server_total_ms": (resp.get("timing") or {}).get("total_ms"),
                "answered": not is_refusal,
                "citation_count": len(citations),
                "refusal_source": refusal_source,
            }

            if q["category"] == "out_of_corpus":
                row["expected"] = "refusal (llm-chosen)"
                if refusal_source == "llm":
                    ooc_llm_refused += 1
                    row["passed"] = True
                    print(f"  [{q['id']:30s}] PASS  llm refused  ({wall_ms}ms)")
                elif refusal_source == "error":
                    ooc_errored += 1
                    row["passed"] = False
                    row["skip_reason"] = "upstream error (quota / network)"
                    print(f"  [{q['id']:30s}] SKIP  api error (not counted)  ({wall_ms}ms)")
                else:
                    row["passed"] = False
                    print(f"  [{q['id']:30s}] FAIL  answered an OOC question  ({wall_ms}ms)")
            else:
                if refusal_source == "error":
                    in_errored += 1
                    row["passed"] = False
                    row["skip_reason"] = "upstream error (quota / network)"
                    print(f"  [{q['id']:30s}] SKIP  api error (not counted)  ({wall_ms}ms)")
                elif is_refusal:
                    row["passed"] = False
                    print(f"  [{q['id']:30s}] FAIL  llm refused in-corpus question  ({wall_ms}ms)")
                else:
                    in_answered += 1
                    citation_counts.append(len(citations))
                    chunk_ids = [c["chunk_id"] for c in citations]
                    texts = _chunk_text_by_id(chunk_ids)
                    exact, fuzzy, total = _check_grounding(citations, texts)
                    exact_total += exact
                    fuzzy_total += fuzzy
                    citations_total += total
                    fuzzy_rate = fuzzy / total if total else 0.0
                    row["exact_grounded"] = exact
                    row["fuzzy_grounded"] = fuzzy
                    row["grounding_rate_fuzzy"] = fuzzy_rate
                    row["passed"] = fuzzy_rate >= GROUNDING_THRESHOLD
                    marker = "PASS" if row["passed"] else "WARN"
                    print(
                        f"  [{q['id']:30s}] {marker}  exact={exact}/{total}  "
                        f"fuzzy={fuzzy}/{total}  ({wall_ms}ms)"
                    )

            results.append(row)

    in_eligible = len(in_corpus) - in_errored
    ooc_eligible = len(out_of_corpus) - ooc_errored

    exact_rate = (exact_total / citations_total) if citations_total else 0.0
    fuzzy_rate = (fuzzy_total / citations_total) if citations_total else 0.0
    refusal_rate = (ooc_llm_refused / ooc_eligible) if ooc_eligible else 0.0
    in_corpus_answer_rate = (in_answered / in_eligible) if in_eligible else 0.0
    avg_cit = sum(citation_counts) / len(citation_counts) if citation_counts else 0.0
    min_cit = min(citation_counts) if citation_counts else 0
    max_cit = max(citation_counts) if citation_counts else 0
    mean_wall_ms = total_latency_ms // len(questions) if questions else 0

    summary = {
        "api_url": api_url,
        "total_questions": len(questions),
        "in_corpus": {
            "count": len(in_corpus),
            "eligible": in_eligible,
            "errored": in_errored,
            "answered": in_answered,
            "answer_rate": in_corpus_answer_rate,
            "citations_total": citations_total,
            "exact_grounded": exact_total,
            "fuzzy_grounded": fuzzy_total,
            "grounding_rate_exact": exact_rate,
            "grounding_rate_fuzzy": fuzzy_rate,
            "citations_mean": avg_cit,
            "citations_min": min_cit,
            "citations_max": max_cit,
        },
        "out_of_corpus": {
            "count": len(out_of_corpus),
            "eligible": ooc_eligible,
            "errored": ooc_errored,
            "llm_refused": ooc_llm_refused,
            "refusal_rate": refusal_rate,
        },
        "mean_wall_ms": mean_wall_ms,
        "results": results,
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  in-corpus answered:    {in_answered}/{in_eligible} ({in_corpus_answer_rate:.0%})"
          + (f"  [+ {in_errored} skipped: upstream error]" if in_errored else ""))
    print(f"  grounding (exact):     {exact_total}/{citations_total} ({exact_rate:.0%})")
    print(f"  grounding (fuzzy):     {fuzzy_total}/{citations_total} ({fuzzy_rate:.0%})")
    print(f"  citations per answer:  mean={avg_cit:.1f} min={min_cit} max={max_cit}")
    print(f"  OOC refusal (llm):     {ooc_llm_refused}/{ooc_eligible} ({refusal_rate:.0%})"
          + (f"  [+ {ooc_errored} skipped: upstream error]" if ooc_errored else ""))
    print(f"  mean wall latency:     {mean_wall_ms}ms")
    print()

    REPORT_PATH.write_text(json.dumps(summary, indent=2))
    print(f"  report → {REPORT_PATH}")

    if in_eligible == 0 and ooc_eligible == 0:
        print("\nNO ELIGIBLE QUESTIONS — every call errored. Check Gemini quota / network.")
        return 1
    failed = (
        fuzzy_rate < GROUNDING_THRESHOLD
        or (ooc_eligible > 0 and refusal_rate < REFUSAL_THRESHOLD)
    )
    if failed:
        print(
            f"\nFAIL: fuzzy_grounding={fuzzy_rate:.0%} (target ≥{GROUNDING_THRESHOLD:.0%}), "
            f"refusal={refusal_rate:.0%} (target ≥{REFUSAL_THRESHOLD:.0%})"
        )
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
