"""Postgres helpers.

Phase 3 needs a simple sync connection for ingestion CLIs. Phase 6 (FastAPI)
will add an async pool — for now this module exposes only what's needed today.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://secrag:secrag@localhost:5432/secrag")


@contextmanager
def sync_conn() -> Iterator[psycopg.Connection]:
    """Yield a psycopg connection; commits on success, rolls back on exception."""
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def vector_literal(embedding: list[float]) -> str:
    """Format a Python list of floats as a pgvector literal: '[0.1,0.2,...]'.

    Using string formatting avoids a runtime dep on the pgvector Python package;
    pgvector parses this literal when the column is typed `vector(N)`.
    """
    return "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"
