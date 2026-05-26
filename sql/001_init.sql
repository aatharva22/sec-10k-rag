-- Phase 3 schema for SEC 10-K RAG.
-- Loaded by docker-compose at first container start (mounted into
-- /docker-entrypoint-initdb.d). To re-apply later, drop the DB or apply manually.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS filings (
    id            SERIAL PRIMARY KEY,
    cik           TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    company_name  TEXT NOT NULL,
    fiscal_year   INT  NOT NULL,
    filing_date   DATE NOT NULL,
    report_date   DATE NOT NULL,
    doc_type      TEXT NOT NULL DEFAULT '10-K',
    accession     TEXT NOT NULL,
    source_url    TEXT NOT NULL,
    raw_text_path TEXT,
    UNIQUE (ticker, fiscal_year, doc_type)
);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    filing_id    INT NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    ticker       TEXT NOT NULL,                -- denormalized for fast metadata filter
    fiscal_year  INT  NOT NULL,                -- denormalized for fast metadata filter
    section      TEXT NOT NULL,
    chunk_index  INT  NOT NULL,
    text         TEXT NOT NULL,
    token_count  INT  NOT NULL,
    embedding    vector(768),
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    metadata     jsonb DEFAULT '{}'::jsonb,
    UNIQUE (filing_id, chunk_index)
);

-- HNSW for vector search (cosine). m=16, ef_construction=64 are pgvector defaults;
-- our corpus (~1.5K chunks) is far below the size where tuning would matter.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN on tsvector for BM25-style full-text search.
CREATE INDEX IF NOT EXISTS chunks_tsv_gin
    ON chunks USING gin (tsv);

-- btree on (ticker, fiscal_year) for metadata pre-filtering.
CREATE INDEX IF NOT EXISTS chunks_ticker_year
    ON chunks (ticker, fiscal_year);
