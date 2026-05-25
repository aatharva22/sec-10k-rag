"""
Phase 3: Embed chunks with Gemini and insert into Postgres.

Model: gemini-embedding-001
- output_dimensionality=768  (MRL-truncated for smaller HNSW index, minimal recall loss)
- task_type=RETRIEVAL_DOCUMENT  (matched by RETRIEVAL_QUERY at search time)

Batching: ~100 chunks per request. Backoff on 429.

Inserts go into the `chunks` table defined in sql/001_init.sql. The `tsv` column
for BM25 is populated by a generated column / trigger — no Python work needed.

TODO Phase 3:
- embed_batch(texts: list[str]) -> list[list[float]]
- insert_chunks(filing_id, chunks_with_embeddings) using psycopg COPY or executemany
- idempotency: ON CONFLICT DO NOTHING keyed on (filing_id, chunk_index)
"""
