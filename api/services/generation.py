"""Grounded answer generation.

Single public entry point: `generate(question, chunks) -> AnswerWithCitations`.
ALL Gemini-specific code lives below this line; swapping in Anthropic Claude
is a one-file edit.

Behavior:
- System prompt forbids outside knowledge, requires every claim be grounded
  in a provided chunk, and instructs the model to refuse when context is
  insufficient.
- Chunks are passed as a numbered list with [chunk_id=N] markers and metadata
  (ticker, fiscal_year, section) so the model can cite by id.
- Gemini structured output (response_schema) returns JSON we can parse
  directly into AnswerWithCitations.
- After parsing, citation chunk_ids are validated against the input set —
  any unknown id is dropped (defends against hallucinated citations).
- On any failure (empty context, parse error, unrecoverable API error) we
  return a polite refusal instead of raising.
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from api.schemas import AnswerWithCitations, Chunk, Citation

load_dotenv()

GEN_MODEL = "gemini-2.5-flash"
REFUSAL = (
    "I don't have enough information in the provided 10-K excerpts to answer that."
)

SYSTEM_PROMPT = """You are a careful financial-research assistant answering questions about SEC 10-K filings.

You will be given a question and a numbered list of excerpts from 10-K filings. Each excerpt is tagged with [chunk_id=N] and includes the company ticker, fiscal year, and section. Use ONLY these excerpts to answer.

Rules:
1. Ground every claim in the provided excerpts. Do not use outside knowledge, even if you believe you know the answer.
2. Cite the chunk_id of the excerpt(s) that support each claim. Include a short verbatim quote (≤ 30 words) from that excerpt.
3. If the provided excerpts are insufficient to answer the question, respond with exactly: "I don't have enough information in the provided 10-K excerpts to answer that." and return an empty citations list.
4. If the question is comparative (e.g. "Apple vs Microsoft"), only compare based on what the excerpts actually say. Do not infer missing values.
5. Keep the answer concise — 2-4 sentences for most questions, or a short bulleted list when comparing multiple items.
"""


class _LLMCitation(BaseModel):
    """Citation shape the LLM is asked to return (subset of api.schemas.Citation).

    We re-derive ticker/fiscal_year/section/source_url from the matching input
    Chunk rather than trusting the LLM to copy them — eliminates a class of
    drift bugs.
    """

    chunk_id: int
    quote: str


class _LLMAnswer(BaseModel):
    answer: str
    citations: list[_LLMCitation] = Field(default_factory=list)


def generate(question: str, chunks: list[Chunk]) -> AnswerWithCitations:
    if not chunks:
        return AnswerWithCitations(answer=REFUSAL, citations=[], refusal_source="error")

    context = _format_chunks(chunks)
    user_prompt = f"Question: {question}\n\nExcerpts:\n{context}\n\nAnswer using only these excerpts."

    try:
        raw = _call_gemini(user_prompt)
        parsed = _LLMAnswer.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        print(f"  generation: parse failure ({type(exc).__name__}: {exc}) — refusing")
        return AnswerWithCitations(answer=REFUSAL, citations=[], refusal_source="error")
    except Exception as exc:  # noqa: BLE001 — SDK error surface is broad
        print(f"  generation: API failure ({type(exc).__name__}: {exc}) — refusing")
        return AnswerWithCitations(answer=REFUSAL, citations=[], refusal_source="error")

    return _build_response(parsed, chunks)


def _format_chunks(chunks: list[Chunk]) -> str:
    lines: list[str] = []
    for c in chunks:
        lines.append(
            f"[chunk_id={c.id}] {c.ticker} FY{c.fiscal_year} — {c.section}\n{c.text}"
        )
    return "\n\n---\n\n".join(lines)


def _call_gemini(user_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from environment")
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_LLMAnswer,
        temperature=0.1,
    )
    resp = client.models.generate_content(
        model=GEN_MODEL, contents=user_prompt, config=cfg
    )
    return resp.text


def _build_response(parsed: _LLMAnswer, chunks: list[Chunk]) -> AnswerWithCitations:
    by_id = {c.id: c for c in chunks}
    citations: list[Citation] = []
    for raw_cit in parsed.citations:
        src = by_id.get(raw_cit.chunk_id)
        if src is None:
            continue
        citations.append(
            Citation(
                chunk_id=src.id,
                ticker=src.ticker,
                fiscal_year=src.fiscal_year,
                section=src.section,
                quote=raw_cit.quote,
                source_url=src.source_url,
                bm25_rank=src.bm25_rank,
                vector_rank=src.vector_rank,
                rrf_score=src.rrf_score,
            )
        )
    # If the LLM emitted the REFUSAL string with no citations, that's a
    # voluntary refusal (rule 3 in the system prompt). Tag it so eval can tell.
    is_llm_refusal = parsed.answer.strip() == REFUSAL and not citations
    return AnswerWithCitations(
        answer=parsed.answer,
        citations=citations,
        refusal_source="llm" if is_llm_refusal else None,
    )


def _cli() -> None:
    from api.services.query_parser import parse
    from api.services.retrieval import hybrid_search

    ap = argparse.ArgumentParser(description="End-to-end RAG smoke test (parser → retrieval → generation).")
    ap.add_argument("question")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    ticker, year = parse(args.question)
    print(f"\nquery:  {args.question}")
    print(f"parser: ticker={ticker}, year={year}")
    chunks = hybrid_search(args.question, ticker=ticker, fiscal_year=year, top_k=args.top_k)
    print(f"retrieved {len(chunks)} chunks\n")

    result = generate(args.question, chunks)
    print("ANSWER:")
    print(textwrap.fill(result.answer, width=100, initial_indent="  ", subsequent_indent="  "))
    print("\nCITATIONS:")
    for i, cit in enumerate(result.citations, 1):
        print(f"  [{i}] chunk_id={cit.chunk_id}  {cit.ticker} FY{cit.fiscal_year}  {cit.section[:50]}")
        wrapped = textwrap.fill(f'"{cit.quote}"', width=100, initial_indent="      ", subsequent_indent="      ")
        print(wrapped)
        if cit.source_url:
            print(f"      {cit.source_url}")
    print()


if __name__ == "__main__":
    _cli()
