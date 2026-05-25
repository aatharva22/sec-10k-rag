"""
Phase 4: Extract ticker and fiscal-year hints from a free-form question.

Deterministic, no LLM. The goal is just to narrow the candidate set when the
user clearly names a company or year; ambiguity is fine — we fall back to
unfiltered search.

Recognized patterns:
- ticker codes: AAPL, MSFT, AMZN, TSLA, NVDA
- company names: Apple, Microsoft, Amazon, Tesla, NVIDIA / Nvidia
- 4-digit years 2022 | 2023 | 2024 (only inside the supported range)

TODO Phase 4:
- parse(question: str) -> tuple[str | None, int | None]
- name → ticker map
- regex for year matching, restricted to the supported set
"""
