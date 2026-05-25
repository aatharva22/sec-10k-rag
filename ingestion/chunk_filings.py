"""
Phase 2: Sub-chunk each section into ~800-token windows with ~10% (80-token) overlap.

Why these numbers (also recorded in DECISIONS.md):
- 800 tokens balances embedding signal (not too diluted) with retrieval precision.
- ~10% overlap reduces the risk of splitting a key sentence at a chunk boundary.
- Top-5 chunks × ~800 tokens ≈ 4K tokens of context, leaving room for the system
  prompt and the user's question within the Gemini context window.

Tokenizer choice: tiktoken cl100k_base as a *proxy*. Gemini's actual tokenizer is
not in tiktoken; cl100k is close enough for sizing chunks and avoids a per-chunk
API call. This is a deliberate approximation, documented in DECISIONS.md.

Each chunk carries metadata: ticker, fiscal_year, section, chunk_index, token_count.

TODO Phase 2:
- chunk_section(text, section_label, ticker, fiscal_year) -> list[Chunk]
- TARGET_TOKENS = 800, OVERLAP_TOKENS = 80
"""
