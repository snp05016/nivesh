"""
RAG Tools — Semantic search over the ChromaDB vector store.

Used by the search_filings LangChain tool (defined in orchestrator.py).
"""
import logging
from sentence_transformers import SentenceTransformer
from services.vector_store import query_collection

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def search_vector_db(query: str, ticker: str, limit: int = 3) -> str:
    """
    Embed a natural language query, pre-filter by ticker, return top-K chunks.

    Returns formatted string for LLM consumption, or a fallback message.
    """
    if not query or not ticker:
        return "No relevant documents found."

    try:
        model = _get_model()
        query_embedding = model.encode([query]).tolist()[0]
        results = query_collection(query_embedding, ticker, limit=limit)
    except Exception as e:
        logger.warning("RAG query failed for %s: %s", ticker, e)
        return "RAG query unavailable at this time."

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return f"No relevant documents found for {ticker}."

    chunks = []
    for i, doc in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        header = "[%s] [%s]" % (meta.get("date", "unknown"), meta.get("source", "unknown"))
        chunks.append("%s\n%s\n---" % (header, doc.strip()))

    return "\n".join(chunks)
