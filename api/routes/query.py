"""POST /query — the RAG endpoint.

Flow:
1. query_parser.parse(question)          → (ticker?, year?) hints
   (explicit filters in the request override the parser)
2. retrieval.hybrid_search(...)          → top-k chunks
3. generation.generate(question, chunks) → AnswerWithCitations

Returns timing for each phase so the UI can show "answered in X.Xs"
and surface latency tradeoffs.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from api.schemas import QueryRequest, QueryResponse, Timing
from api.services import generation, query_parser, retrieval

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
def post_query(req: QueryRequest) -> QueryResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must be non-empty")

    t_total = time.perf_counter()
    try:
        # Explicit filters in the request override the parser. Parser still
        # runs so we can fall back if the request didn't specify.
        parsed_ticker, parsed_year = query_parser.parse(question)
        ticker = req.ticker or parsed_ticker
        year = req.fiscal_year or parsed_year

        t = time.perf_counter()
        chunks = retrieval.hybrid_search(question, ticker=ticker, fiscal_year=year, top_k=5)
        # embed_query inside hybrid_search is the dominant retrieval cost,
        # but we don't separate it — surfacing the total retrieve_ms is what
        # the UI cares about.
        retrieve_ms = int((time.perf_counter() - t) * 1000)

        t = time.perf_counter()
        result = generation.generate(question, chunks)
        generate_ms = int((time.perf_counter() - t) * 1000)
    except Exception:
        log.exception("unhandled error in /query")
        raise HTTPException(status_code=503, detail="upstream failure — try again")

    total_ms = int((time.perf_counter() - t_total) * 1000)
    timing = Timing(
        embed_ms=0,  # rolled into retrieve_ms; reserved for a future split
        retrieve_ms=retrieve_ms,
        generate_ms=generate_ms,
        total_ms=total_ms,
    )

    return QueryResponse(
        answer=result.answer,
        citations=result.citations,
        timing=timing,
        retrieved_count=len(chunks),
        refusal_source=result.refusal_source,
    )
