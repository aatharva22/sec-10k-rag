"""POST /query — the RAG endpoint.

Flow:
1. query_parser.parse(question)          → (ticker?, year?) hints
2. retrieval.hybrid_search(...)          → top-k chunks
3. generation.generate(question, chunks) → AnswerWithCitations
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.schemas import QueryRequest, QueryResponse
from api.services import generation, query_parser, retrieval

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
def post_query(req: QueryRequest) -> QueryResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must be non-empty")

    try:
        ticker, year = query_parser.parse(question)
        chunks = retrieval.hybrid_search(question, ticker=ticker, fiscal_year=year, top_k=5)
        result = generation.generate(question, chunks)
    except Exception:
        log.exception("unhandled error in /query")
        raise HTTPException(status_code=503, detail="upstream failure — try again")

    return QueryResponse(answer=result.answer, citations=result.citations)
