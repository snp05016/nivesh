"""
Vector Store — pgvector (PostgreSQL) singleton for Nivesh RAG pipeline.

Replaces ChromaDB with PostgreSQL + pgvector extension.
AGENTS.md §3.4: Module-level mutable state uses threading.Lock.
"""
import os
import threading
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from pgvector.psycopg2 import register_vector

logger = logging.getLogger(__name__)

TABLE_NAME = "nivesh_filings"
EMBEDDING_DIM = 384
_store_lock = threading.Lock()
_conn: "psycopg2.extensions.connection | None" = None
_initialised = False


def _get_conn() -> "psycopg2.extensions.connection":
    """Retrieves or creates a singleton PostgreSQL connection for pgvector.

    Returns:
        psycopg2.extensions.connection: The active database connection.

    Raises:
        RuntimeError: If the RAG_DB_PASS environment variable is not set.
    """
    global _conn
    if _conn is None or _conn.closed:
        db_name = os.getenv("RAG_DB_NAME", "nivesh")
        db_user = os.getenv("RAG_DB_USER", "saumyapatel")
        db_pass = os.getenv("RAG_DB_PASS", "")
        if not db_pass:
            raise RuntimeError("RAG_DB_PASS environment variable must be set")
        db_host = os.getenv("RAG_DB_HOST", "127.0.0.1")
        _conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host
        )
        _conn.autocommit = True
        register_vector(_conn)
        logger.info("pgvector connection established to %s", db_name)
    return _conn


def init_store() -> bool:
    """Initialises the pgvector table and indices.

    Returns:
        bool: True on successful initialization or if already initialized, False on failure.
    """
    global _initialised
    if _initialised:
        return True
    try:
        conn = _get_conn()
        with _store_lock, conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    chunk_idx INTEGER NOT NULL,
                    embedding VECTOR({EMBEDDING_DIM}),
                    document TEXT NOT NULL
                )
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_ticker
                ON {TABLE_NAME} (ticker)
            """)
            _initialised = True
            logger.info("pgvector table '%s' ready", TABLE_NAME)
        return True
    except Exception as e:
        logger.error("pgvector init failed: %s", e)
        return False


def upsert_documents(ids: list[str], documents: list[str],
                     metadatas: list[dict], embeddings: list[list[float]]) -> None:
    """Upserts document chunks into the pgvector table.

    All input lists must be the same length.

    Args:
        ids (list[str]): List of unique identifiers for the chunks.
        documents (list[str]): List of document text strings.
        metadatas (list[dict]): List of metadata dictionaries for each chunk.
        embeddings (list[list[float]]): List of embedding vectors.
    """
    if not ids:
        return
    conn = _get_conn()
    with _store_lock, conn.cursor() as cur:
        rows = []
        for i in range(len(ids)):
            m = metadatas[i] if i < len(metadatas) else {}
            emb = embeddings[i] if i < len(embeddings) else None
            rows.append((
                ids[i],
                m.get("ticker", ""),
                m.get("date", ""),
                m.get("doc_type", ""),
                m.get("source", ""),
                m.get("chunk_idx", 0),
                emb,
                documents[i] if i < len(documents) else "",
            ))
        execute_values(cur, f"""
            INSERT INTO {TABLE_NAME} (id, ticker, date, doc_type, source, chunk_idx, embedding, document)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                date = EXCLUDED.date,
                doc_type = EXCLUDED.doc_type,
                source = EXCLUDED.source,
                chunk_idx = EXCLUDED.chunk_idx,
                embedding = EXCLUDED.embedding,
                document = EXCLUDED.document
        """, rows)
    logger.debug("Upserted %d documents", len(ids))


def query_collection(query_embedding: list[float], ticker: str,
                     limit: int = 3) -> dict:
    """Queries pgvector with a ticker filter and cosine similarity.

    Args:
        query_embedding (list[float]): The embedding vector of the query.
        ticker (str): The ticker symbol to filter by.
        limit (int, optional): The maximum number of results to return. Defaults to 3.

    Returns:
        dict: A dictionary containing lists of 'documents', 'metadatas', and 'distances',
            formatted to match the expected interface of ChromaDB.
    """
    conn = _get_conn()
    with _store_lock, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            SELECT ticker, date, doc_type, source, chunk_idx, document,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {TABLE_NAME}
            WHERE ticker = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, ticker, query_embedding, limit))
        rows = cur.fetchall()

    documents = [r["document"] for r in rows] if rows else []
    metadatas = [{
        "ticker": r["ticker"], "date": r["date"],
        "doc_type": r["doc_type"], "source": r["source"],
        "chunk_idx": r["chunk_idx"],
    } for r in rows] if rows else []

    return {
        "documents": [documents],
        "metadatas": [metadatas],
        "distances": [[round(1 - r["similarity"], 4) for r in rows]] if rows else [[]],
    }


def collection_count() -> int:
    """Returns the total number of documents in the pgvector table.

    Returns:
        int: The number of rows in the table, or 0 if an error occurs.
    """
    try:
        conn = _get_conn()
        with _store_lock, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            return cur.fetchone()[0]
    except Exception:
        return 0
