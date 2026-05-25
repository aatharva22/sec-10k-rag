"""
Phase 1: Download 10-K filings from SEC EDGAR.

Inputs: hardcoded list of (ticker, cik, fiscal_year) tuples for the 15 filings.
Outputs:
- data/filings/{TICKER}/{fiscal_year}.html   (primary 10-K HTML doc)
- data/filings/manifest.json                  (one entry per filing)

The Phase 1 driver spawns one subagent per (ticker, fiscal_year). Each subagent:
1. fetches the company's submissions JSON (data.sec.gov/submissions/CIK{cik}.json)
2. finds the 10-K accession matching the target fiscal year (by reportDate)
3. fetches the filing index, identifies the primary HTML doc
4. downloads it, verifies non-empty
5. returns a manifest entry: ticker, cik, fiscal_year, accession, filing_date,
   primary_doc_url, local_path, byte_size, sha256

TODO Phase 1:
- TICKERS = [("AAPL", "0000320193"), ("MSFT", "0000789019"), ("AMZN", "0001018724"),
             ("TSLA", "0001318605"), ("NVDA", "0001045810")]
- FISCAL_YEARS = [2022, 2023, 2024]
- function download_one(ticker, cik, fiscal_year) -> ManifestEntry
- aggregator that writes data/filings/manifest.json
"""
