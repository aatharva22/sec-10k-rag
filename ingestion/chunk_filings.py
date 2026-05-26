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
    # Dedup by Item code: the LAST occurrence is the real section header. Earlier
    # mentions are typically table-of-contents entries or in-text references.
    by_code: dict[str, re.Match[str]] = {}
    for m in matches:
        by_code[m.group(1).upper()] = m
    ordered = sorted(by_code.values(), key=lambda m: m.start())
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(ordered):
        item_code = m.group(1).upper()
        title = m.group(2).strip().rstrip(".")
        label = f"Item {item_code}. {title}"
        start = m.start()
        end = ordered[i + 1].start() if i + 1 < len(ordered) else len(text)
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
