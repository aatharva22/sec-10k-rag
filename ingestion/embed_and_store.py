"""Embed chunks with Gemini and bulk-insert into Postgres."""

from __future__ import annotations

import os
import time
from typing import Iterator

from dotenv import load_dotenv
from google import genai
from google.genai import types

from api.db import sync_conn, vector_literal
from ingestion.chunk_filings import Chunk

load_dotenv()

# gemini-embedding-2: free-tier accessible, default 3072-dim with MRL truncation
# to 768 via output_dimensionality. Newer than gemini-embedding-001 (paid-only).
#
# IMPORTANT: embed_content does NOT batch — passing contents=[t1, t2, ...] treats
# the list as multiple "parts" of a SINGLE content and returns one embedding.
# True batching requires the asyncBatchEmbedContent endpoint (async job). For
# our 1,533-chunk corpus a serial loop with rate limiting is simpler.
EMBED_MODEL = "gemini-embedding-2"
EMBED_DIM = 768
MIN_INTERVAL_SEC = 1.5  # ~40 RPM / ~32k TPM @ 800-tok chunks — under free-tier 30k TPM cap
MAX_RETRIES = 7         # 2+4+8+16+32+64=126s of backoff covers rolling-limit recovery


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing from environment")
    return genai.Client(api_key=api_key)


def embed_documents(texts: list[str], client: genai.Client | None = None) -> list[list[float]]:
    """Embed a list of document texts (each ~800 tokens). Returns one vector per input.

    Calls the API once per text (see module note on why batching doesn't work),
    sleeping MIN_INTERVAL_SEC between calls to stay under the free-tier RPM limit.
    """
    client = client or _client()
    cfg = types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT", output_dimensionality=EMBED_DIM
    )
    out: list[list[float]] = []
    last_call_ts = 0.0
    for i, text in enumerate(texts):
        wait = MIN_INTERVAL_SEC - (time.time() - last_call_ts)
        if wait > 0:
            time.sleep(wait)
        vectors = _embed_with_retry(client, [text], cfg)
        last_call_ts = time.time()
        out.append(vectors[0])
        if (i + 1) % 25 == 0 or i + 1 == len(texts):
            print(f"    embedded {i + 1}/{len(texts)}", flush=True)
    return out


def embed_query(text: str, client: genai.Client | None = None) -> list[float]:
    """Embed a single user query. Uses task_type=RETRIEVAL_QUERY."""
    client = client or _client()
    cfg = types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY", output_dimensionality=EMBED_DIM
    )
    vectors = _embed_with_retry(client, [text], cfg)
    return vectors[0]


def _embed_with_retry(
    client: genai.Client, texts: list[str], cfg: types.EmbedContentConfig
) -> list[list[float]]:
    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.embed_content(
                model=EMBED_MODEL, contents=texts, config=cfg
            )
            return [e.values for e in resp.embeddings]
        except Exception as exc:  # noqa: BLE001 — SDK exception types vary; retry on any
            if attempt == MAX_RETRIES:
                raise
            print(f"  embed retry {attempt}/{MAX_RETRIES} ({type(exc).__name__}: {exc})")
            time.sleep(delay)
            delay *= 2


def _batched(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def upsert_filing(
    cik: str,
    ticker: str,
    company_name: str,
    fiscal_year: int,
    filing_date: str,
    report_date: str,
    accession: str,
    source_url: str,
    raw_text_path: str,
) -> int:
    """Insert or update a filings row; return its id."""
    with sync_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO filings (cik, ticker, company_name, fiscal_year, filing_date,
                                 report_date, accession, source_url, raw_text_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, fiscal_year, doc_type) DO UPDATE SET
                accession = EXCLUDED.accession,
                filing_date = EXCLUDED.filing_date,
                report_date = EXCLUDED.report_date,
                source_url = EXCLUDED.source_url,
                raw_text_path = EXCLUDED.raw_text_path
            RETURNING id
            """,
            (cik, ticker, company_name, fiscal_year, filing_date,
             report_date, accession, source_url, raw_text_path),
        )
        return cur.fetchone()[0]


def insert_chunks(filing_id: int, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
    """Bulk-insert chunks. ON CONFLICT DO NOTHING so re-runs are idempotent.

    Returns the number of rows actually inserted.
    """
    assert len(chunks) == len(embeddings), "chunks/embeddings length mismatch"
    rows = [
        (
            filing_id,
            c.ticker,
            c.fiscal_year,
            c.section,
            c.chunk_index,
            c.text,
            c.token_count,
            vector_literal(emb),
        )
        for c, emb in zip(chunks, embeddings)
    ]
    with sync_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (filing_id, ticker, fiscal_year, section, chunk_index,
                                text, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (filing_id, chunk_index) DO NOTHING
            """,
            rows,
        )
        return cur.rowcount
