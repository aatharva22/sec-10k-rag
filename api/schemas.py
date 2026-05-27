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
    score: float | None = None


class Citation(BaseModel):
    chunk_id: int
    ticker: str
    fiscal_year: int
    section: str
    quote: str
    source_url: str | None = None


class AnswerWithCitations(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
