"""Extract ticker and fiscal-year hints from a free-form question.

Deterministic, no LLM. The goal is just to narrow the candidate set when the
user clearly names a company or year; ambiguity is fine — we fall back to
unfiltered hybrid retrieval over the whole corpus.

Recognized:
- ticker codes: AAPL, MSFT, AMZN, TSLA, NVDA (case-insensitive, word-bounded)
- company names: Apple, Microsoft, Amazon, Tesla, NVIDIA / Nvidia
- 4-digit fiscal year in {2022, 2023, 2024}
"""

from __future__ import annotations

import re

SUPPORTED_TICKERS = {"AAPL", "MSFT", "AMZN", "TSLA", "NVDA"}
SUPPORTED_YEARS = {2022, 2023, 2024}

_NAME_TO_TICKER: dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "nvidia": "NVDA",
}

_TICKER_RE = re.compile(r"\b(" + "|".join(SUPPORTED_TICKERS) + r")\b", re.IGNORECASE)
_NAME_RE = re.compile(r"\b(" + "|".join(_NAME_TO_TICKER) + r")\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def parse(question: str) -> tuple[str | None, int | None]:
    """Return (ticker, fiscal_year) hints, either field possibly None.

    If multiple distinct tickers or years are mentioned we return None for
    that field — caller falls back to corpus-wide retrieval rather than guess.
    """
    return _extract_ticker(question), _extract_year(question)


def _extract_ticker(question: str) -> str | None:
    found: set[str] = set()
    for m in _TICKER_RE.finditer(question):
        found.add(m.group(1).upper())
    for m in _NAME_RE.finditer(question):
        found.add(_NAME_TO_TICKER[m.group(1).lower()])
    if len(found) == 1:
        return next(iter(found))
    return None


def _extract_year(question: str) -> int | None:
    found: set[int] = set()
    for m in _YEAR_RE.finditer(question):
        y = int(m.group(1))
        if y in SUPPORTED_YEARS:
            found.add(y)
    if len(found) == 1:
        return next(iter(found))
    return None
