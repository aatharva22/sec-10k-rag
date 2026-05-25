"""
Phase 4: Hybrid retrieval — BM25 + vector, fused with Reciprocal Rank Fusion.

Public API:
    async def hybrid_search(
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 5,
    ) -> list[Chunk]

Pipeline:
1. Embed the question with gemini-embedding-001, task_type=RETRIEVAL_QUERY.
2. In parallel (asyncio.gather):
   - BM25:    ORDER BY ts_rank_cd(tsv, plainto_tsquery(:q)) DESC LIMIT 20
   - Vector:  ORDER BY embedding <=> :qvec LIMIT 20
   Both apply the (ticker, fiscal_year) WHERE filter if provided.
3. Fuse with RRF:  score(d) = sum over rankers of  1 / (k + rank(d, ranker))
   k = 60 — Cormack et al. 2009 published default.
4. Return top_k Chunks ordered by fused score.

TODO Phase 4:
- write the two SQL queries
- implement RRF (simple dict accumulation)
- expose Chunk via api.schemas
"""
