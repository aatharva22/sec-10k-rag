"""End-to-end ingestion: manifest → parse → chunk → embed → insert.

Usage:
    uv run python -m ingestion.pipeline                 # ingest all 15 filings
    uv run python -m ingestion.pipeline --ticker AAPL   # only AAPL
    uv run python -m ingestion.pipeline --ticker AAPL --year 2023
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from api.db import sync_conn
from ingestion.chunk_filings import chunk_filing
from ingestion.embed_and_store import embed_documents, insert_chunks, upsert_filing
from ingestion.parse_filings import parse_html


def _already_ingested(ticker: str, fiscal_year: int) -> bool:
    with sync_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM chunks WHERE ticker = %s AND fiscal_year = %s LIMIT 1",
            (ticker, fiscal_year),
        )
        return cur.fetchone() is not None

MANIFEST_PATH = Path("data/filings/manifest.json")

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com, Inc.",
    "TSLA": "Tesla, Inc.",
    "NVDA": "NVIDIA Corporation",
}


def run(ticker: str | None = None, year: int | None = None, force: bool = False) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    filings = manifest["filings"]
    if ticker:
        filings = [f for f in filings if f["ticker"] == ticker.upper()]
    if year:
        filings = [f for f in filings if f["fiscal_year"] == year]
    if not filings:
        print("no filings match filter")
        return

    print(f"ingesting {len(filings)} filing(s)")
    grand_total_chunks = 0
    grand_total_inserted = 0
    skipped = 0
    t_start = time.time()

    for f in filings:
        tag = f"{f['ticker']}/{f['fiscal_year']}"
        if not force and _already_ingested(f["ticker"], f["fiscal_year"]):
            print(f"\n[{tag}] already ingested — skip (use --force to re-embed)")
            skipped += 1
            continue
        print(f"\n[{tag}] parse...", end=" ", flush=True)
        t0 = time.time()
        text = parse_html(Path(f["local_path"]))
        chunks = chunk_filing(f["ticker"], f["fiscal_year"], text)
        print(f"{len(chunks)} chunks ({time.time() - t0:.1f}s)")

        print(f"[{tag}] embed...", end=" ", flush=True)
        t0 = time.time()
        embeddings = embed_documents([c.text for c in chunks])
        assert all(len(e) == 768 for e in embeddings), "unexpected embedding dim"
        print(f"{len(embeddings)} vectors ({time.time() - t0:.1f}s)")

        print(f"[{tag}] insert...", end=" ", flush=True)
        t0 = time.time()
        filing_id = upsert_filing(
            cik=f["cik"],
            ticker=f["ticker"],
            company_name=COMPANY_NAMES[f["ticker"]],
            fiscal_year=f["fiscal_year"],
            filing_date=f["filing_date"],
            report_date=f["report_date"],
            accession=f["accession"],
            source_url=f["primary_doc_url"],
            raw_text_path=f["local_path"],
        )
        inserted = insert_chunks(filing_id, chunks, embeddings)
        print(f"filing_id={filing_id}, {inserted}/{len(chunks)} new ({time.time() - t0:.1f}s)")

        grand_total_chunks += len(chunks)
        grand_total_inserted += inserted

    elapsed = time.time() - t_start
    processed = len(filings) - skipped
    print(
        f"\ndone: {grand_total_inserted}/{grand_total_chunks} chunks inserted across "
        f"{processed} filing(s), {skipped} skipped, in {elapsed:.1f}s"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", help="Only ingest this ticker (e.g. AAPL)")
    ap.add_argument("--year", type=int, help="Only ingest this fiscal year (e.g. 2023)")
    ap.add_argument("--force", action="store_true", help="Re-embed even if already ingested")
    args = ap.parse_args()
    run(ticker=args.ticker, year=args.year, force=args.force)
