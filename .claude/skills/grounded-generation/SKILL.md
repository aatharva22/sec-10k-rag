---
name: grounded-generation
description: Generate answers grounded in retrieved 10-K chunks with verifiable citations and a strict refusal protocol. Use whenever editing the LLM call, the system prompt, the output schema, the citation flow, or the refusal behavior. Covers Gemini structured output, the two-layer schema trick, and how we defend against hallucinated metadata.
---

# Grounded Generation Pipeline

How a `(question, chunks)` pair becomes an `AnswerWithCitations` the user can trust.

## Pipeline

```
question + retrieved chunks
        │
        ▼
  build user prompt: chunks as numbered list with [chunk_id=N] markers
        │
        ▼
  Gemini generate_content(
      system_instruction=SYSTEM_PROMPT,
      response_schema=_LLMAnswer,          # grammar-constrained JSON
      response_mime_type="application/json",
      temperature=0.1,
  )
        │
        ▼
  _LLMAnswer.model_validate_json(resp.text)   # parse + validate
        │
        ▼
  _build_response(parsed, chunks):
      for each citation:
          look up chunk_id in input set
          drop if unknown (hallucination defense)
          re-derive ticker/year/section/source_url from matched Chunk
        │
        ▼
  AnswerWithCitations (public schema)
```

Any failure path — empty chunks, JSON parse error, Pydantic validation error, API error — funnels to the same `REFUSAL` response with empty citations.

## Where the code lives

| Component | File | Function |
|---|---|---|
| Public entry point | [`api/services/generation.py`](../../../api/services/generation.py) | `generate(question, chunks)` |
| System prompt constant | [`api/services/generation.py`](../../../api/services/generation.py) | `SYSTEM_PROMPT` |
| Refusal constant | [`api/services/generation.py`](../../../api/services/generation.py) | `REFUSAL` |
| LLM-facing schema | [`api/services/generation.py`](../../../api/services/generation.py) | `_LLMAnswer`, `_LLMCitation` |
| Public schemas | [`api/schemas.py`](../../../api/schemas.py) | `AnswerWithCitations`, `Citation`, `Chunk` |
| Gemini call wrapper | [`api/services/generation.py`](../../../api/services/generation.py) | `_call_gemini` |
| Citation hydration / hallucination guard | [`api/services/generation.py`](../../../api/services/generation.py) | `_build_response` |
| Chunk formatter (`[chunk_id=N]` markers) | [`api/services/generation.py`](../../../api/services/generation.py) | `_format_chunks` |
| CLI smoke-tester | [`api/services/generation.py`](../../../api/services/generation.py) | `python -m api.services.generation "<question>"` |

## Constants and why

| Constant | Value | Reason |
|---|---|---|
| `GEN_MODEL` | `gemini-2.5-flash` | Fast (1–3s for 5-chunk prompt), free-tier accessible, plenty good for grounded extraction over curated context. Swap to `gemini-2.5-pro` or `claude-opus-4-7` for multi-step reasoning. |
| `temperature` | `0.1` | Zero temperature with grammar-constrained decoding sometimes truncates mid-sentence on a deterministic end-token. A tiny bit of stochasticity gives the model room to finish, while keeping behavior effectively reproducible. |
| `response_mime_type` | `application/json` | Required alongside `response_schema` to enable grammar-constrained decoding. |
| `response_schema` | `_LLMAnswer` (Pydantic) | The SDK enforces the schema server-side; we just `model_validate_json` on the way back. Eliminates a class of malformed-JSON failures. |

All defined at the top of `api/services/generation.py`.

## The system prompt (verbatim)

```text
You are a careful financial-research assistant answering questions about SEC 10-K filings.

You will be given a question and a numbered list of excerpts from 10-K filings. Each excerpt is tagged with [chunk_id=N] and includes the company ticker, fiscal year, and section. Use ONLY these excerpts to answer.

Rules:
1. Ground every claim in the provided excerpts. Do not use outside knowledge, even if you believe you know the answer.
2. Cite the chunk_id of the excerpt(s) that support each claim. Include a short verbatim quote (≤ 30 words) from that excerpt.
3. If the provided excerpts are insufficient to answer the question, respond with exactly: "I don't have enough information in the provided 10-K excerpts to answer that." and return an empty citations list.
4. If the question is comparative (e.g. "Apple vs Microsoft"), only compare based on what the excerpts actually say. Do not infer missing values.
5. Keep the answer concise — 2-4 sentences for most questions, or a short bulleted list when comparing multiple items.
```

Lives in [`api/services/generation.py`](../../../api/services/generation.py) as `SYSTEM_PROMPT`. Treat this string as load-bearing — observed behavior (refusal triggering, citation quality, answer length) depends on these specific rules. Don't paraphrase casually.

## Output schemas

### What the LLM is asked to return (`_LLMAnswer`, private)

```python
class _LLMCitation(BaseModel):
    chunk_id: int
    quote: str

class _LLMAnswer(BaseModel):
    answer: str
    citations: list[_LLMCitation] = Field(default_factory=list)
```

The model only emits the *minimum* it can produce reliably — the id of the chunk it cited and a short verbatim quote from that chunk.

### What callers see (`AnswerWithCitations`, public, in [`api/schemas.py`](../../../api/schemas.py))

```python
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
```

`_build_response` joins each `_LLMCitation.chunk_id` back to the matched `Chunk` from retrieval and copies `ticker`, `fiscal_year`, `section`, `source_url` from there.

### Why two layers

Asking the LLM to copy metadata for every citation invites silent drift — the model occasionally pluralizes, abbreviates, or paraphrases ("Item 1A" → "Item 1A: Risks", "AAPL" → "Apple"). Re-deriving from the retrieved `Chunk` makes those fields ground-truth by construction. The hallucination guard lives in the same hop: any `chunk_id` the LLM returns that isn't in the input set gets dropped silently — defends against the model inventing ids when uncertain.

## Citation format

A `Citation` carries everything needed to attribute and verify a claim:

- `chunk_id` — id from the `chunks` table; deterministically traceable to a specific text span in a specific filing.
- `ticker`, `fiscal_year`, `section` — human-readable provenance (e.g. `AAPL FY2023 — Item 1A. Risk Factors`).
- `quote` — verbatim excerpt the model is grounding the claim on, ≤ 30 words per the system prompt rule.
- `source_url` — direct link to the SEC EDGAR filing.

The quote is the load-bearing field for trust. A user (or auditor) can grep the quote against the `chunks.text` column to confirm the model didn't paraphrase or invent. If we ever want to enforce this server-side, add a substring check in `_build_response` — if the quote isn't a substring of `Chunk.text`, drop the citation. We don't do this yet; the temperature=0.1 + structured output have been reliable enough in practice.

## Refusal protocol

There is exactly one refusal string, defined as `REFUSAL` in [`api/services/generation.py`](../../../api/services/generation.py):

```text
I don't have enough information in the provided 10-K excerpts to answer that.
```

This string is returned with `citations=[]` whenever:

| Trigger | Where it fires |
|---|---|
| Retrieval returned zero chunks | Top of `generate()` |
| JSON decode failure on LLM response | `except (ValidationError, json.JSONDecodeError, ValueError)` |
| Pydantic validation failure on `_LLMAnswer` | same `except` |
| Unrecoverable API error (auth, quota, network) | broad `except Exception` (logs the type and message) |
| LLM itself chose to refuse (followed rule 3) | The model emits exactly `REFUSAL` as its `answer`, with `citations=[]` |

Critical design point: **the user sees the same string regardless of the underlying cause.** Mixing "no relevant context" with "the LLM provider is down" leaks implementation detail and erodes trust. Cause-specific diagnostics go to stderr for our debugging, not into the response body. Provider health monitoring belongs in `/health` (Phase 6), not bolted into answers.

## Failure modes and how we handle them

| Symptom | Cause | Mitigation |
|---|---|---|
| Empty `chunks` list passed to `generate()` | Retrieval returned nothing (e.g. filter knocked out every row) | Return `REFUSAL` immediately — don't call the LLM. |
| Model returns malformed JSON | Rare with `response_schema` but possible on token cutoff | `model_validate_json` raises; caught and converted to `REFUSAL`. |
| Model invents a `chunk_id` not in the input set | "Anchor seeking" when uncertain | `_build_response` looks up each id and drops the citation if not found. The answer text still goes through. |
| Model copies metadata fields wrong (e.g. AAPL → Apple Inc.) | Cannot happen — we don't ask the model for those fields. | N/A by construction. |
| Model paraphrases the quote | Possible — we don't currently validate substring containment | Live with it for now. Future: substring check in `_build_response`, drop citation on miss. |
| API quota / network failure | 429s, timeouts, transient errors | Broad `except Exception` returns `REFUSAL`. Error type and message logged to stderr. No retry — for interactive use we'd rather refuse fast than hang the user for 60+ seconds of backoff. |
| Zero temperature truncates mid-sentence | Deterministic end-token under grammar constraint | `temperature=0.1` mitigates. |

## Provider swap path

Everything Gemini-specific lives below the `from google import genai` line in [`api/services/generation.py`](../../../api/services/generation.py):

- `_call_gemini` — the only place the SDK appears.
- `GEN_MODEL` — the model identifier.

Swapping in another provider (Anthropic Claude, OpenAI, etc.) is a single-file edit:

1. Replace `_call_gemini` with the new provider's client call.
2. Update `GEN_MODEL`.
3. For providers without grammar-constrained decoding, either (a) use tool-use / function-calling to enforce the schema, or (b) prompt-instruct JSON and add a retry-on-malformed loop. Either keeps the rest of the code untouched.

`generate()`, `_build_response()`, `SYSTEM_PROMPT`, `REFUSAL`, the schemas, and the CLI all stay put.

## Smoke tests

Run these via the CLI to verify after touching generation:

```bash
# Grounded factual — expect a real answer with at least one citation per claim
uv run python -m api.services.generation \
    "What does Apple list as its principal competitive factors?"

# Out-of-corpus — expect the REFUSAL string with empty citations
uv run python -m api.services.generation \
    "What was the GDP of France in 2023?"

# Cross-ticker comparison — expect citations from both tickers
uv run python -m api.services.generation \
    "Compare Tesla and NVIDIA risk factors related to supply chain"

# Single filing — expect tight, on-topic citations from one filing
uv run python -m api.services.generation \
    "What are Apple's biggest risks in 2023?"
```

Each prints `query → parser hints → retrieved N chunks → ANSWER + CITATIONS` so the full pipeline is visible.
