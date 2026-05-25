"""
Phase 6: POST /query — the RAG endpoint.

Request:  { "question": str }
Response: { "answer": str, "citations": [...] }

Flow:
1. parse_query(question)                 → (ticker, year) hints
2. retrieval.hybrid_search(...)          → top-5 chunks
3. generation.generate(question, chunks) → AnswerWithCitations

TODO Phase 6:
- APIRouter with POST /query
- pydantic request/response types from api.schemas
- error path: if retrieval returns zero chunks, return a "no relevant context" answer
"""
