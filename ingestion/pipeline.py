"""
Phase 3: End-to-end ingestion orchestrator.

Wires the per-phase modules together:

    download_filings → parse_filings → chunk_filings → embed_and_store

CLI flags (planned):
    --ticker AAPL          only this ticker
    --year 2023            only this fiscal year
    --skip-download        re-use already-downloaded HTML
    --force                re-embed even if rows already exist for the filing

TODO Phase 3:
- run() function callable from `python -m ingestion.pipeline`
- argparse CLI
- progress logging (which filing, how many chunks, embed batch index)
"""
