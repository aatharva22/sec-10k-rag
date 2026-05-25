"""
Download 10-K filings from SEC EDGAR.

Status: initial bootstrap done via parallel Claude Code subagents (see
data/filings/manifest.json for the resulting 15 entries). The source of truth
for which filings we use is manifest.json.

A future single-process implementation should:
1. Read data/filings/manifest.json — the canonical list of (ticker, fiscal_year,
   accession, primary_doc_url, sha256) tuples.
2. For each entry, GET the primary_doc_url with the SEC User-Agent header.
3. Verify the downloaded bytes against the manifest's sha256 — if it matches,
   we know it's the same filing the project was built on.

Constants for re-running from scratch (no manifest):

    TICKERS = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
        "AMZN": "0001018724",
        "TSLA": "0001318605",
        "NVDA": "0001045810",
    }
    FISCAL_YEARS = [2022, 2023, 2024]

Match strategy: form == "10-K" AND reportDate startswith str(fiscal_year).
"""
