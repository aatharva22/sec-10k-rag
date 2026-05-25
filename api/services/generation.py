"""
Phase 5: Grounded answer generation.

Single public function — keep ALL provider-specific code below this line so we
can swap to Anthropic Claude by editing this one file only.

    def generate(question: str, chunks: list[Chunk]) -> AnswerWithCitations

Behavior:
- Builds a system prompt that:
    * forbids using outside knowledge
    * requires every claim to map to a provided chunk
    * instructs the model to refuse ("I don't have enough information in the
      provided 10-K excerpts to answer that") when context is insufficient
- Formats the chunks as a numbered list including ticker, fiscal_year, section,
  and the chunk text — so the model can cite by index/id.
- Requests strict JSON output via Gemini's structured output:
    response_mime_type="application/json"
    response_schema=AnswerWithCitations
- Returns the parsed AnswerWithCitations object.

TODO Phase 5:
- google-genai client initialized from GEMINI_API_KEY
- system + user prompt templates
- structured-output schema definition
- JSON parse + validation; on parse failure return a polite refusal
"""
