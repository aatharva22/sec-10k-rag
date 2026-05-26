"""Section-split + sub-chunk a parsed 10-K.

- Section split: regex on `^Item\\s+N[.A-C]?` (multiline, case-insensitive).
  Each match starts a candidate section; the section body runs to the next match.
  Sections shorter than MIN_SECTION_CHARS are dropped — these are almost always
  table-of-contents entries pointing at the real section that comes later.
- Sub-chunk: tiktoken cl100k_base encoder, TARGET_TOKENS=800 with OVERLAP_TOKENS=80.
  The section label is prepended to every chunk's text so that mid-section chunks
  retain section context for embedding-time matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

import tiktoken

TARGET_TOKENS = 800
OVERLAP_TOKENS = 80
MIN_SECTION_CHARS = 1000

_ITEM_RE = re.compile(
    r"^\s*Item\s+(\d{1,2}[A-C]?)\.?[\s\n]+([^\n]{3,200})$",
    re.IGNORECASE | re.MULTILINE,
)

# SEC-prescribed 10-K Item titles. Used to produce clean citation labels
# regardless of how the filing's HTML lays out the heading visually.
_CANONICAL_TITLES: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
    "6": "[Reserved]",
    "7": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements with Accountants on Accounting and Financial Disclosure",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions That Prevent Inspections",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
    "13": "Certain Relationships and Related Transactions, and Director Independence",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibit and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}

# Canonical document order for a 10-K. Used to drop matches that violate the
# expected sequence (e.g. an "Item 11" matched at the table of contents but
# positioned before "Item 1" in the body).
_CANONICAL_ORDER: list[str] = [
    "1", "1A", "1B", "1C", "2", "3", "4",
    "5", "6", "7", "7A", "8", "9", "9A", "9B", "9C",
    "10", "11", "12", "13", "14", "15", "16",
]

_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass(slots=True)
class Chunk:
    ticker: str
    fiscal_year: int
    section: str
    chunk_index: int
    text: str
    token_count: int


def split_into_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_ITEM_RE.finditer(text))
    if not matches:
        return []
    # Some filings (MSFT especially) embed page-header repetitions like
    # "PART I, Item 1. Business" on every printed page, so a single Item code
    # can match 10+ times. Worse, the ToC at the top lists every Item with its
    # page number, which also matches. The "real" section header is the match
    # with the LARGEST gap to the next match — page headers are tightly packed
    # within a section, and ToC entries are tightly packed near the top.
    matches_sorted = sorted(matches, key=lambda m: m.start())
    with_gap: list[tuple[re.Match[str], int]] = []
    for i, m in enumerate(matches_sorted):
        next_start = (
            matches_sorted[i + 1].start() if i + 1 < len(matches_sorted) else len(text)
        )
        with_gap.append((m, next_start - m.start()))

    best_per_code: dict[str, tuple[re.Match[str], int]] = {}
    for m, gap in with_gap:
        code = m.group(1).upper()
        if code not in best_per_code or gap > best_per_code[code][1]:
            best_per_code[code] = (m, gap)

    # Walk in canonical 10-K order and enforce strictly increasing document
    # positions. A candidate whose position is before the previous accepted
    # item's position is a ToC/header artifact (e.g. "Item 11" matching only
    # at the ToC at position 200 when Item 1 is at position 5000+).
    chosen: list[tuple[re.Match[str], int]] = []
    cursor_pos = -1
    for code in _CANONICAL_ORDER:
        entry = best_per_code.get(code)
        if entry is None:
            continue
        m, _ = entry
        if m.start() <= cursor_pos:
            continue  # out-of-order — likely a ToC fragment
        chosen.append(entry)
        cursor_pos = m.start()

    sections: list[tuple[str, str]] = []
    for i, (m, _) in enumerate(chosen):
        item_code = m.group(1).upper()
        canonical = _CANONICAL_TITLES.get(item_code)
        title = canonical or m.group(2).strip().rstrip(".")
        label = f"Item {item_code}. {title}"
        start = m.start()
        end = chosen[i + 1][0].start() if i + 1 < len(chosen) else len(text)
        body = text[start:end].strip()
        if len(body) >= MIN_SECTION_CHARS:
            sections.append((label, body))
    return sections


def _sub_chunk(text: str) -> Iterator[tuple[str, int]]:
    tokens = _ENC.encode(text)
    step = TARGET_TOKENS - OVERLAP_TOKENS
    start = 0
    while start < len(tokens):
        end = min(start + TARGET_TOKENS, len(tokens))
        window = tokens[start:end]
        yield _ENC.decode(window), len(window)
        if end >= len(tokens):
            break
        start += step


def chunk_filing(ticker: str, fiscal_year: int, parsed_text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for label, body in split_into_sections(parsed_text):
        for chunk_text, tok_count in _sub_chunk(body):
            chunks.append(
                Chunk(
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    section=label,
                    chunk_index=idx,
                    text=f"[{label}]\n\n{chunk_text}",
                    token_count=tok_count,
                )
            )
            idx += 1
    return chunks


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from .parse_filings import parse_html

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/filings/AAPL/2023.html")
    ticker = path.parent.name
    fy = int(path.stem)

    text = parse_html(path)
    sections = split_into_sections(text)
    chunks = chunk_filing(ticker, fy, text)

    print(f"file:        {path}")
    print(f"text chars:  {len(text):,}")
    print(f"sections:    {len(sections)}")
    print(f"chunks:      {len(chunks)}")
    print(f"--- sections found:")
    for label, body in sections:
        print(f"  {len(body):>8,} chars   {label}")
    print(f"--- first chunk preview (chunk_index=0):")
    print(chunks[0].text[:400] if chunks else "(no chunks)")
