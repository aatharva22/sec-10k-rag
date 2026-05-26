"""Phase 3 verification tool: pure-vector cosine search over the chunks table.

Phase 4 will add BM25 + RRF in api/services/retrieval.py. This is the minimal
smoke test that proves embedding + indexing + retrieval works end-to-end.

Usage:
    uv run python -m ingestion.search "How does Apple describe AI risk?" \\
        --ticker AAPL --year 2023 --top-k 5
"""

from __future__ import annotations

import argparse
import textwrap

from api.db import sync_conn, vector_literal
from ingestion.embed_and_store import embed_query


def search(question: str, ticker: str | None, year: int | None, top_k: int) -> None:
    qvec = embed_query(question)
    where_clauses = []
    params: list = [vector_literal(qvec)]
    if ticker:
        where_clauses.append("ticker = %s")
        params.append(ticker.upper())
    if year:
        where_clauses.append("fiscal_year = %s")
        params.append(year)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.append(top_k)

    sql = f"""
        SELECT id, ticker, fiscal_year, section, chunk_index,
               1 - (embedding <=> %s::vector) AS cosine_sim,
               left(text, 220) AS preview
        FROM chunks
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    # We need the query vector twice (SELECT + ORDER BY). Insert at the right position.
    params_final = [vector_literal(qvec), *params[1:-1], vector_literal(qvec), params[-1]]

    with sync_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params_final)
        rows = cur.fetchall()

    print(f"\nquery: {question}")
    if ticker or year:
        print(f"filter: ticker={ticker}, year={year}")
    print(f"top {top_k}:\n")
    for rank, (cid, tk, fy, sec, idx, sim, preview) in enumerate(rows, 1):
        print(f"  #{rank}  cos={sim:.3f}  id={cid}  {tk} FY{fy}  {sec[:60]}  (chunk {idx})")
        wrapped = textwrap.fill(preview, width=100, initial_indent="        ", subsequent_indent="        ")
        print(wrapped + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--ticker", help="Filter by ticker (e.g. AAPL)")
    ap.add_argument("--year", type=int, help="Filter by fiscal year (e.g. 2023)")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()
    search(args.question, args.ticker, args.year, args.top_k)
