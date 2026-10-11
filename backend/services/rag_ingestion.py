"""
RAG Ingestion — chunk, embed, and upsert NewsArticles + AdvisorInsights into pgvector.

Incremental: scheduled once a day by the leader-only scheduler (harvest_worker job
'rag_ingest'). Each doc type resumes after the highest source-row id already in the
vector store, rows are streamed in small id-ordered batches, and no DB session is held
while embedding — a run with no new rows does zero embedding work.
"""
import logging
from datetime import datetime, timezone
import os
import threading
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from database import get_session, NewsArticle, AdvisorInsight
from services.vector_store import (
    upsert_documents, collection_count, max_ingested_row_id, delete_legacy_chunks,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
FETCH_BATCH = 200   # source rows per DB round-trip
EMBED_BATCH = 50    # chunks per model.encode call
DOC_TYPES = ("news_article", "advisor_transcript")

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def _get_embedding_model() -> SentenceTransformer:
    """Retrieve the singleton SentenceTransformer model, initializing it if necessary.

    Returns:
        SentenceTransformer: The instantiated MiniLM embedding model.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer("all-MiniLM-L6-v2", token=os.getenv("HF_TOKEN"))
                logger.info("MiniLM embedding model loaded")
    return _model


def _make_chunk_id(doc_type: str, row_id: int, chunk_idx: int) -> str:
    """Chunk id '<doc_type>:<source row id>:<chunk idx>'.

    Including the source row id keeps same-ticker, same-day articles from overwriting
    each other; vector_store.max_ingested_row_id() parses it back as the watermark.
    """
    return f"{doc_type}:{row_id}:{chunk_idx}"


def _fetch_batch(doc_type: str, after_id: int, limit: int = FETCH_BATCH) -> list[tuple[int, str, str, str, str]]:
    """Next `limit` rows with id > after_id as plain (id, ticker, text, date_str, source)
    tuples, ordered by id. Uses its own short session and only the needed columns."""
    with get_session() as session:
        if doc_type == "news_article":
            query = session.query(
                NewsArticle.id, NewsArticle.ticker, NewsArticle.body_text,
                NewsArticle.published_at, NewsArticle.article_url,
            ).filter(
                NewsArticle.id > after_id,
                NewsArticle.body_text.isnot(None),
                NewsArticle.body_text != "",
            ).order_by(NewsArticle.id)
            default_source = "news"
        else:
            query = session.query(
                AdvisorInsight.id, AdvisorInsight.ticker, AdvisorInsight.raw_snippet,
                AdvisorInsight.published_at, AdvisorInsight.advisor_name,
            ).filter(AdvisorInsight.id > after_id).order_by(AdvisorInsight.id)
            default_source = "advisor"
        rows = query.limit(limit).all()
        return [
            (
                row_id, ticker or "", text or "",
                published.strftime("%Y-%m-%d") if published else "unknown",
                source or default_source,
            )
            for row_id, ticker, text, published, source in rows
        ]


_last_ingested: str | None = None


def ingest_new() -> int:
    """Embed and upsert rows added since the last run. Returns the number of chunks upserted.

    ponytail: the watermark is the max ingested row id, so a row whose text is filled in
    after a later row was ingested is not picked up; add an updated_at watermark if needed.
    """
    global _last_ingested
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    model = None  # loaded lazily: a run with nothing new never loads MiniLM
    total_chunks = 0

    for doc_type in DOC_TYPES:
        last_id = max_ingested_row_id(doc_type)
        if last_id is None:
            # First run on the new id scheme: drop colliding legacy chunks, embed from scratch.
            removed = delete_legacy_chunks(doc_type)
            if removed:
                logger.info("Removed %d legacy %s chunks", removed, doc_type)
            last_id = 0

        while True:
            rows = _fetch_batch(doc_type, last_id)
            if not rows:
                break
            ids: list[str] = []
            docs: list[str] = []
            metas: list[dict] = []
            for row_id, ticker, text, date_str, source in rows:
                if not ticker or not text:
                    continue
                for i, chunk in enumerate(splitter.split_text(text)):
                    ids.append(_make_chunk_id(doc_type, row_id, i))
                    docs.append(chunk)
                    metas.append({
                        "ticker": ticker,
                        "date": date_str,
                        "doc_type": doc_type,
                        "source": source,
                        "chunk_idx": i,
                    })
            for start in range(0, len(ids), EMBED_BATCH):
                if model is None:
                    model = _get_embedding_model()
                end = start + EMBED_BATCH
                embeddings = model.encode(docs[start:end]).tolist()
                upsert_documents(ids[start:end], docs[start:end], metas[start:end], embeddings)
            total_chunks += len(ids)
            last_id = rows[-1][0]

    _last_ingested = datetime.now(timezone.utc).isoformat()
    logger.info("RAG ingestion complete: %d new chunks, collection size: %d",
                total_chunks, collection_count())
    return total_chunks
