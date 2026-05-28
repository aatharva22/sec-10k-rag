"""Hybrid retrieval — BM25 + vector, fused with Reciprocal Rank Fusion.

Public API:
    hybrid_search(question, ticker=None, fiscal_year=None, top_k=5) -> list[Chunk]

Pipeline:
1. Embed the question with task_type=RETRIEVAL_QUERY.
2. Run two SELECTs against `chunks`:
   - BM25:   ORDER BY ts_rank_cd(tsv, plainto_tsquery(...)) DESC  LIMIT POOL
   - Vector: ORDER BY embedding <=> :qvec                          LIMIT POOL
   Both apply the (ticker, fiscal_year) filter when present.
3. Fuse with RRF: score(d) = sum over rankers of  1 / (k + rank(d, ranker))
   k = 60 (Cormack et al. 2009).
4. Return top_k Chunks ordered by fused score.

We run the two SELECTs sequentially on a single connection — at 1.5K rows
each query is sub-50ms, and going async would double the connection setup
without improving latency. Phase 6 swaps in an async pool for the FastAPI
route; the retrieval logic itself stays synchronous.
"""

from __future__ import annotations

import argparse
import textwrap
from typing import Sequence

from api.db import sync_conn, vector_literal
from api.schemas import Chunk
from ingestion.embed_and_store import embed_query

POOL_SIZE = 20      # per-ranker candidate set before fusion
RRF_K = 60          # Cormack et al. 2009 published default


def hybrid_search(
    question: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> list[Chunk]:
    qvec = embed_query(question)

    where_sql, where_params = _build_where(ticker, fiscal_year)

    with sync_conn() as conn, conn.cursor() as cur:
        bm25_ids = [row[0] for row in _bm25_search(cur, question, where_sql, where_params)]
        vec_ids = [row[0] for row in _vector_search(cur, qvec, where_sql, where_params)]

        fused = _rrf_fuse(bm25_ids, vec_ids)
        if not fused:
            return []

        top_ids = [cid for cid, _ in fused[:top_k]]
        chunks = _hydrate(cur, top_ids)

        # Stamp retrieval debug info onto each chunk.
        bm25_rank_by_id = {cid: i + 1 for i, cid in enumerate(bm25_ids)}
        vec_rank_by_id = {cid: i + 1 for i, cid in enumerate(vec_ids)}
        rrf_score_by_id = dict(fused)
        for c in chunks:
            c.bm25_rank = bm25_rank_by_id.get(c.id)
            c.vector_rank = vec_rank_by_id.get(c.id)
            c.rrf_score = rrf_score_by_id.get(c.id)
        return chunks


def _build_where(ticker: str | None, fiscal_year: int | None) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if ticker:
        clauses.append("ticker = %s")
        params.append(ticker.upper())
    if fiscal_year:
        clauses.append("fiscal_year = %s")
        params.append(fiscal_year)
    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _bm25_search(cur, question: str, where_sql: str, where_params: list) -> list[tuple]:
    sql = f"""
        SELECT id
        FROM chunks
        {where_sql}
        {"AND" if where_sql else "WHERE"} tsv @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', %s)) DESC
        LIMIT %s
    """
    cur.execute(sql, [*where_params, question, question, POOL_SIZE])
    return cur.fetchall()


def _vector_search(cur, qvec: list[float], where_sql: str, where_params: list) -> list[tuple]:
    qlit = vector_literal(qvec)
    sql = f"""
        SELECT id
        FROM chunks
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, [*where_params, qlit, POOL_SIZE])
    return cur.fetchall()


def _rrf_fuse(bm25_ids: Sequence[int], vec_ids: Sequence[int]) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: combine two ranked lists into one.

    Returns (chunk_id, score) pairs sorted by score descending. Callers that
    only care about ids can pull `cid for cid, _ in result`.
    """
    scores: dict[int, float] = {}
    for rank, cid in enumerate(bm25_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    for rank, cid in enumerate(vec_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def _hydrate(cur, ids_in_order: list[int]) -> list[Chunk]:
    """Fetch full chunk rows (with filing source_url) preserving input order."""
    cur.execute(
        """
        SELECT c.id, c.filing_id, c.ticker, c.fiscal_year, c.section,
               c.chunk_index, c.text, f.source_url
        FROM chunks c
        JOIN filings f ON f.id = c.filing_id
        WHERE c.id = ANY(%s)
        """,
        (ids_in_order,),
    )
    by_id = {row[0]: row for row in cur.fetchall()}
    chunks: list[Chunk] = []
    for cid in ids_in_order:
        row = by_id.get(cid)
        if row is None:
            continue
        chunks.append(
            Chunk(
                id=row[0],
                filing_id=row[1],
                ticker=row[2],
                fiscal_year=row[3],
                section=row[4],
                chunk_index=row[5],
                text=row[6],
                source_url=row[7],
            )
        )
    return chunks


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Hybrid (BM25 + vector + RRF) retrieval smoke test.")
    ap.add_argument("question")
    ap.add_argument("--ticker", help="Filter by ticker (e.g. AAPL)")
    ap.add_argument("--year", type=int, help="Filter by fiscal year")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    chunks = hybrid_search(args.question, ticker=args.ticker, fiscal_year=args.year, top_k=args.top_k)
    print(f"\nquery: {args.question}")
    if args.ticker or args.year:
        print(f"filter: ticker={args.ticker}, year={args.year}")
    print(f"top {args.top_k}:\n")
    for rank, c in enumerate(chunks, 1):
        preview = c.text[:220].replace("\n", " ")
        print(f"  #{rank}  id={c.id}  {c.ticker} FY{c.fiscal_year}  {c.section[:60]}  (chunk {c.chunk_index})")
        wrapped = textwrap.fill(preview, width=100, initial_indent="        ", subsequent_indent="        ")
        print(wrapped + "\n")


if __name__ == "__main__":
    _cli()
