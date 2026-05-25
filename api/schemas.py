"""
Pydantic schemas shared across services and HTTP layer.

These are the *provider-agnostic* shapes — Gemini-specific structures are kept
inside api/services/generation.py so the LLM can be swapped without touching
callers.

TODO Phase 3+ (start when first needed, extend per phase):

    class Chunk(BaseModel):
        id: int
        filing_id: int
        ticker: str
        fiscal_year: int
        section: str
        chunk_index: int
        text: str
        score: float | None = None   # set by retrieval

    class Citation(BaseModel):
        chunk_id: int
        ticker: str
        fiscal_year: int
        section: str
        quote: str
        source_url: str | None = None

    class AnswerWithCitations(BaseModel):
        answer: str
        citations: list[Citation]

    class QueryRequest(BaseModel):
        question: str

    class QueryResponse(BaseModel):
        answer: str
        citations: list[Citation]
"""
