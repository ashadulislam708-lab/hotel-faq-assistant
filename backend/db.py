"""Postgres/pgvector connection and schema for storing FAQ chunks and embeddings."""

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from config import DATABASE_URL

# text-embedding-3-small dimension. Changing this requires dropping and
# re-ingesting faq_chunks, since existing vectors aren't compatible with a
# different column width.
EMBEDDING_DIM = 1536


def get_connection():
    """Open a connection to the pgvector-enabled Postgres database."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn


def init_schema():
    """Create the vector extension and the faq_chunks table if they don't exist."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    # The vector extension must exist before register_vector() can run, so this
    # first connection is deliberately plain (not get_connection()).
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS faq_chunks (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
                    question TEXT,
                    category TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS faq_chunks_embedding_idx
                ON faq_chunks USING hnsw (embedding vector_cosine_ops);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_state (
                    id SMALLINT PRIMARY KEY DEFAULT 1,
                    content_hash TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CHECK (id = 1)
                );
                """
            )
        conn.commit()


def get_content_hash() -> str | None:
    """Return the content hash stored from the last successful ingestion, or None."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM ingestion_state WHERE id = 1;")
            row = cur.fetchone()
    return row[0] if row else None


def insert_chunk(text: str, embedding: list[float], metadata: dict | None = None):
    """Insert a single FAQ chunk and its embedding into the store."""
    metadata = metadata or {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO faq_chunks (text, embedding, question, category) VALUES (%s, %s, %s, %s);",
                (text, embedding, metadata.get("question"), metadata.get("category")),
            )
        conn.commit()


def replace_all_chunks(chunks: list[dict], content_hash: str):
    """Atomically replace the entire faq_chunks table with a fresh set of chunks.

    Each chunk dict must have 'text', 'embedding', and optionally 'question'/'category'.
    Truncate, re-insert, and recording content_hash all happen in a single transaction,
    so a failure leaves the previous contents (and hash) intact instead of going out of sync.
    """
    rows = [
        (chunk["text"], chunk["embedding"], chunk.get("question"), chunk.get("category"))
        for chunk in chunks
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE faq_chunks;")
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO faq_chunks (text, embedding, question, category) VALUES %s",
                rows,
            )
            cur.execute(
                """
                INSERT INTO ingestion_state (id, content_hash) VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET content_hash = EXCLUDED.content_hash, updated_at = now();
                """,
                (content_hash,),
            )
        conn.commit()


def search_similar(embedding: list[float], k: int = 5):
    """Return the top-k chunks most similar to the given embedding (cosine similarity)."""
    raise NotImplementedError
