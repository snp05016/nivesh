"""
RAG Ingestion — Chunk, embed, and upsert NewsArticles + AdvisorInsights.

Run once at startup for initial load, then nightly via APScheduler.
"""
import gc
import logging
from datetime import datetime, timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from database import get_session, NewsArticle, AdvisorInsight
from services.vector_store import upsert_documents, collection_count

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("MiniLM embedding model loaded")
    return _model


def _make_chunk_id(ticker: str, date_str: str, doc_type: str, chunk_idx: int) -> str:
    return f"{ticker}_{date_str}_{doc_type}_chunk{chunk_idx}"


def ingest_all() -> int:
    """Ingest all existing NewsArticles and AdvisorInsights. Returns count of chunks upserted."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    model = _get_embedding_model()
    total_chunks = 0

    with get_session() as session:
        articles = session.query(NewsArticle).filter(
            NewsArticle.body_text.isnot(None),
            NewsArticle.body_text != "",
        ).all()
        logger.info("Ingesting %d news articles", len(articles))

        for article in articles:
            if not article.ticker or not article.body_text:
                continue
            chunks = splitter.split_text(article.body_text)
            date_str = article.published_at.strftime("%Y-%m-%d") if article.published_at else "unknown"
            source = article.article_url or "news"

            for batch_start in range(0, len(chunks), 50):
                batch_end = min(batch_start + 50, len(chunks))
                batch_ids = []
                batch_docs = []
                batch_metas = []
                for i in range(batch_start, batch_end):
                    cid = _make_chunk_id(article.ticker, date_str, "news_article", i)
                    batch_ids.append(cid)
                    batch_docs.append(chunks[i])
                    batch_metas.append({
                        "ticker": article.ticker,
                        "date": date_str,
                        "doc_type": "news_article",
                        "source": source,
                        "chunk_idx": i,
                    })
                embeddings = model.encode(batch_docs).tolist()
                upsert_documents(batch_ids, batch_docs, batch_metas, embeddings)
                total_chunks += len(batch_ids)
                gc.collect()

        insights = session.query(AdvisorInsight).all()
        logger.info("Ingesting %d advisor transcripts", len(insights))

        for insight in insights:
            transcript = insight.raw_snippet or ""
            if not insight.ticker or not transcript:
                continue
            chunks = splitter.split_text(transcript)
            date_str = insight.published_at.strftime("%Y-%m-%d") if insight.published_at else "unknown"

            for batch_start in range(0, len(chunks), 50):
                batch_end = min(batch_start + 50, len(chunks))
                batch_ids = []
                batch_docs = []
                batch_metas = []
                for i in range(batch_start, batch_end):
                    cid = _make_chunk_id(insight.ticker, date_str, "advisor_transcript", i)
                    batch_ids.append(cid)
                    batch_docs.append(chunks[i])
                    batch_metas.append({
                        "ticker": insight.ticker,
                        "date": date_str,
                        "doc_type": "advisor_transcript",
                        "source": insight.advisor_name or "advisor",
                        "chunk_idx": i,
                    })
                embeddings = model.encode(batch_docs).tolist()
                upsert_documents(batch_ids, batch_docs, batch_metas, embeddings)
                total_chunks += len(batch_ids)
                gc.collect()

    logger.info("Ingestion complete: %d chunks total, collection size: %d", total_chunks, collection_count())
    return total_chunks


_last_ingested: str | None = None


def ingest_new() -> int:
    """Nightly CRON — re-ingest all (de-duplication handled by ChromaDB upsert)."""
    global _last_ingested
    logger.info("Starting nightly RAG ingestion")
    count = ingest_all()
    _last_ingested = datetime.now(timezone.utc).isoformat()
    logger.info("Nightly ingestion complete: %d chunks", count)
    return count
