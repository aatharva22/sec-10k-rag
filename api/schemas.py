"""Pydantic schemas shared across services and HTTP layer.

Kept provider-agnostic — Gemini-specific structures live inside
api/services/generation.py so the LLM can be swapped without touching callers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: int
    filing_id: int
    ticker: str
    fiscal_year: int
    section: str
    chunk_index: int
    text: str
    source_url: str | None = None
    # Retrieval debug info — set by hybrid_search, surfaced through Citation.
    bm25_rank: int | None = None      # None if not in BM25 top pool
    vector_rank: int | None = None    # None if not in vector top pool
    rrf_score: float | None = None
    score: float | None = None        # legacy generic score; kept for compatibility


class Citation(BaseModel):
    chunk_id: int
    ticker: str
    fiscal_year: int
    section: str
    quote: str
    source_url: str | None = None
    bm25_rank: int | None = None
    vector_rank: int | None = None
    rrf_score: float | None = None


class Timing(BaseModel):
    embed_ms: int
    retrieve_ms: int
    generate_ms: int
    total_ms: int


class AnswerWithCitations(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    # Distinguishes "LLM chose to refuse" from "LLM call failed and we fell
    # back to the refusal string". User-facing UIs ignore this; eval uses it.
    refusal_source: str | None = None  # "llm" | "error" | None


class QueryRequest(BaseModel):
    question: str
    # Optional explicit filters — override the query_parser when set.
    # Used by the frontend's filter-chip UI so the user can scope without
    # having to type the ticker / year into the question.
    ticker: str | None = None
    fiscal_year: int | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    timing: Timing | None = None
    retrieved_count: int = 0
    refusal_source: str | None = None  # "llm" | "error" | None
