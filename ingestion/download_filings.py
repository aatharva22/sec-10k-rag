"""Re-download the 15 10-K filings recorded in data/filings/manifest.json.

The original bootstrap (Phase 1) was done via parallel Claude Code subagents,
one per ticker × fiscal-year. The manifest is the source-of-truth record of
exactly which filings we used — URL, accession, byte size, and sha256.

This script reads the manifest, GETs each primary_doc_url with the required
SEC User-Agent header, writes to the manifest's local_path, and verifies the
sha256 round-trip. Skips files that already exist with the right hash so the
script is safe to re-run.

Usage:
    SEC_USER_AGENT="Your Name your.email@example.com" \\
        uv run python -m ingestion.download_filings
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

MANIFEST_PATH = Path("data/filings/manifest.json")
SEC_RATE_LIMIT_SLEEP = 0.15  # ~7 req/s, under SEC's 10 req/s ceiling


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _user_agent() -> str:
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua:
        sys.exit(
            "SEC_USER_AGENT env var is required. SEC EDGAR rejects requests "
            'without a contact header. Format: "Your Name your.email@example.com"'
        )
    return ua


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    filings = manifest["filings"]
    ua = _user_agent()

    headers = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}
    downloaded = 0
    skipped = 0
    failed = 0

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for entry in filings:
            tag = f"{entry['ticker']}/{entry['fiscal_year']}"
            local = Path(entry["local_path"])
            expected_sha = entry["sha256"]

            if local.exists() and _sha256(local.read_bytes()) == expected_sha:
                print(f"[{tag}] already present (sha256 ok) — skip")
                skipped += 1
                continue

            print(f"[{tag}] downloading {entry['primary_doc_url']} ... ", end="", flush=True)
            try:
                resp = client.get(entry["primary_doc_url"])
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"FAIL ({type(exc).__name__}: {exc})")
                failed += 1
                continue

            content = resp.content
            actual_sha = _sha256(content)
            if actual_sha != expected_sha:
                print(
                    f"FAIL (sha256 mismatch: got {actual_sha[:12]}…, "
                    f"manifest says {expected_sha[:12]}…)"
                )
                failed += 1
                continue

            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(content)
            print(f"OK ({len(content):,} bytes)")
            downloaded += 1
            time.sleep(SEC_RATE_LIMIT_SLEEP)

    print(
        f"\ndone: {downloaded} downloaded, {skipped} already present, "
        f"{failed} failed (of {len(filings)} total)"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
