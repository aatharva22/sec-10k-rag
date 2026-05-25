"""
Phase 2: Parse a downloaded 10-K HTML into a list of (section_label, section_text).

Strategy:
- Primary parser: selectolax — fast, strips iXBRL tags cleanly, preserves block structure.
- Fallback: BeautifulSoup, for filings selectolax can't handle.
- Section detection: regex on '^Item\\s+(\\d+[A-Z]?)\\.?\\s+(.+)$' (case-insensitive, multiline).
  Standard 10-K sections we expect: Items 1, 1A, 1B, 2, 3, 4, 5, 6, 7, 7A, 8, 9, 9A, 9B, 10-15.
- Section label format: "Item 1A. Risk Factors" — used verbatim in citations.

TODO Phase 2:
- parse_html(path: Path) -> str (clean text)
- split_into_sections(text: str) -> list[tuple[str, str]]
- smoke test: parse one filing, print section labels + char counts
"""
