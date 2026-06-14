"""
Vector Store — ChromaDB singleton for Nivesh RAG pipeline.

Provides thread-safe access to a persistent ChromaDB vector store.
AGENTS.md §3.4: All module-level mutable state uses threading.Lock.
"""
import os
import time
import threading
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "nivesh_filings"
EMBEDDING_DIM = 384
_store_lock = threading.Lock()
_client: "chromadb.ClientAPI | None" = None
_collection: "chromadb.Collection | None" = None
_initialised = False


def _get_client() -> "chromadb.ClientAPI":
    global _client
    if _client is None:
        persist_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
        os.makedirs(persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialised at %s", persist_dir)
    return _client


def get_collection() -> "chromadb.Collection":
    global _collection, _initialised
    with _store_lock:
        if _collection is None:
            client = _get_client()
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            _initialised = True
            logger.info("Collection '%s' ready", COLLECTION_NAME)
    return _collection


def init_store() -> bool:
    """Initialise ChromaDB with retry for multi-worker race conditions.
    Returns True if initialisation succeeded, False if it failed after retries."""
    global _initialised
    if _initialised:
        return True
    for attempt in range(5):
        try:
            get_collection()
            return True
        except Exception as e:
            if "table collections already exists" in str(e) or "already exists" in str(e).lower():
                logger.info("ChromaDB init race (attempt %d/5), retrying in 2s...", attempt + 1)
                time.sleep(2)
            else:
                logger.warning("ChromaDB init failed (attempt %d/5): %s", attempt + 1, e)
                return False
    logger.error("ChromaDB init failed after 5 attempts")
    return False


def upsert_documents(ids: list[str], documents: list[str],
                     metadatas: list[dict], embeddings: list[list[float]]) -> None:
    """Upsert chunks into ChromaDB. All lists must be same length."""
    if not ids:
        return
    collection = get_collection()
    with _store_lock:
        collection.upsert(ids=ids, documents=documents,
                          metadatas=metadatas, embeddings=embeddings)
    logger.debug("Upserted %d documents", len(ids))


def query_collection(query_embedding: list[float], ticker: str,
                     limit: int = 3) -> dict:
    """Query ChromaDB with metadata pre-filter on ticker."""
    collection = get_collection()
    with _store_lock:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"ticker": ticker},
            include=["documents", "metadatas", "distances"],
        )
    return results


def collection_count() -> int:
    """Return number of documents in the collection."""
    try:
        return get_collection().count()
    except Exception:
        return 0
