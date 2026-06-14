# Vector DB & RAG Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ChromaDB-backed RAG to Nivesh's LangGraph pipeline — ingest news articles and advisor transcripts, enable semantic search via `search_filings` tool for Governance and News analysts.

**Architecture:** ChromaDB (SQLite backend, in-process), `all-MiniLM-L6-v2` embeddings (384-dim), RecursiveCharacterTextSplitter chunking, nightly APScheduler ingestion from NewsArticle + AdvisorInsight tables. Tool injected into Governance and News analysts. Bull/bear researchers consume enriched reports.

**Tech Stack:** chromadb, sentence-transformers, langchain-text-splitters, Python 3.12, existing transformers+torch

---

**File Structure:**
| File | Role |
|------|------|
| `backend/services/vector_store.py` (new) | ChromaDB singleton, collection init, upsert, query |
| `backend/services/rag_ingestion.py` (new) | DB queries → chunk → embed → upsert pipeline |
| `backend/services/rag_tools.py` (new) | `search_vector_db()` — embed query, metadata filter, top-K |
| `backend/services/orchestrator.py` (modify) | Replace stub, add search_filings to governance+news tools |
| `backend/tradingagents-core/tradingagents/graph/trading_graph.py` (modify) | Add search_filings to governance+news ToolNodes |
| `backend/requirements.txt` (modify) | Add chromadb + sentence-transformers |

---

### Task 1: Add Dependencies

**Files:** Modify: `backend/requirements.txt`

- [ ] **Step 1: Add chromadb and sentence-transformers**

At the bottom of `backend/requirements.txt`, add:

```
chromadb>=0.5.0
sentence-transformers>=2.7.0
```

- [ ] **Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(backend): add chromadb and sentence-transformers for vector DB RAG"
```

---

### Task 2: Vector Store Service

**Files:** Create: `backend/services/vector_store.py`

- [ ] **Step 1: Create file with ChromaDB client singleton**

```python
"""
Vector Store — ChromaDB singleton for Nivesh RAG pipeline.

AGENTS.md §3.4: Module-level mutable state protected by threading.Lock.
"""
import os
import threading
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "nivesh_filings"
EMBEDDING_DIM = 384
_store_lock = threading.Lock()
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        persist_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
        os.makedirs(persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB client initialised at {persist_dir}")
    return _client


def get_collection() -> chromadb.Collection:
    global _collection
    with _store_lock:
        if _collection is None:
            client = _get_client()
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Collection '{COLLECTION_NAME}' ready")
    return _collection


def upsert_documents(ids: list[str], documents: list[str],
                     metadatas: list[dict], embeddings: list[list[float]]) -> None:
    """Upsert chunks into ChromaDB. All lists must be same length."""
    if not ids:
        return
    collection = get_collection()
    with _store_lock:
        collection.upsert(ids=ids, documents=documents,
                          metadatas=metadatas, embeddings=embeddings)
    logger.debug(f"Upserted {len(ids)} documents")


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
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/vector_store.py
git commit -m "feat(backend): add ChromaDB vector store service with thread-safe singleton"
```

---

### Task 3: RAG Ingestion Pipeline

**Files:** Create: `backend/services/rag_ingestion.py`

- [ ] **Step 1: Create ingestion service**

```python
"""
RAG Ingestion — Chunk, embed, and upsert NewsArticles + AdvisorInsights.

Nightly CRON via APScheduler (registered in main.py).
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
        # Ingest news articles
        articles = session.query(NewsArticle).filter(
            NewsArticle.body_text.isnot(None),
            NewsArticle.body_text != "",
        ).all()
        logger.info(f"Ingesting {len(articles)} news articles")

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

        # Ingest advisor insights
        insights = session.query(AdvisorInsight).all()
        logger.info(f"Ingesting {len(insights)} advisor transcripts")

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

    logger.info(f"Ingestion complete: {total_chunks} chunks total, collection size: {collection_count()}")
    return total_chunks


_last_ingested: str | None = None


def ingest_new() -> int:
    """Nightly CRON — ingest only new documents since last run."""
    global _last_ingested
    logger.info("Starting nightly RAG ingestion")
    # For simplicity, re-run full ingestion (de-duplication handles duplicates)
    # Future optimisation: track last_ingested timestamp and filter by published_at
    count = ingest_all()
    _last_ingested = datetime.now(timezone.utc).isoformat()
    logger.info(f"Nightly ingestion complete: {count} chunks")
    return count
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/rag_ingestion.py
git commit -m "feat(backend): add RAG ingestion pipeline — chunk, embed, upsert news + advisor transcripts"
```

---

### Task 4: RAG Search Tool

**Files:** Create: `backend/services/rag_tools.py`

- [ ] **Step 1: Create search function**

```python
"""
RAG Tools — Semantic search over the vector DB for LangGraph agents.
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
        logger.warning(f"RAG query failed for {ticker}: {e}")
        return "RAG query unavailable at this time."

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return f"No relevant documents found for {ticker}."

    chunks = []
    for i, doc in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        header = f"[{meta.get('date', 'unknown')}] [{meta.get('source', 'unknown')}]"
        chunks.append(f"{header}\n{doc.strip()}\n---")

    return "\n".join(chunks)
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/rag_tools.py
git commit -m "feat(backend): add RAG search tool — embed, filter by ticker, return top-K chunks"
```

---

### Task 5: Wire Into Orchestrator

**Files:** Modify: `backend/services/orchestrator.py:207-217,298,310`

- [ ] **Step 1: Replace the search_filings stub (lines 210-217)**

Replace:
```python
@tool
def search_filings(query: str, ticker: str) -> str:
    """Semantically search the vector DB for earnings calls and SEC/NSE filings."""
    # STUB: RAG architecture for unstructured text using FAISS/Qdrant
    # This tool is intended for Bear/Bull researchers to access unstructured text.
    return f"STUB: 3 most relevant textual chunks for '{query}' on {ticker} from vector DB."
```

With:
```python
@tool
def search_filings(query: str, ticker: str) -> str:
    """Search the vector database for news articles, earnings calls, and advisor
    analysis related to {ticker}. Use this to find qualitative signals like
    management guidance concerns, auditor red flags, promoter issues, or
    governance problems not visible in structured financial data.
    Returns top 3 most relevant text chunks with dates and sources."""
    from services.rag_tools import search_vector_db
    return search_vector_db(query, ticker, limit=3)
```

- [ ] **Step 2: Add search_filings to governance analyst tools (line 298)**

Change:
```python
[get_news, get_insider_transactions],
```
To:
```python
[get_news, get_insider_transactions, search_filings],
```

- [ ] **Step 3: Add search_filings to news analyst tools (line 310)**

Change:
```python
[get_news, get_global_news, get_insider_transactions],
```
To:
```python
[get_news, get_global_news, get_insider_transactions, search_filings],
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/orchestrator.py
git commit -m "feat(backend): wire search_filings RAG tool into governance and news analyst nodes"
```

---

### Task 6: Wire Into Trading Graph

**Files:** Modify: `backend/tradingagents-core/tradingagents/graph/trading_graph.py:183-184,205-206`

- [ ] **Step 1: Add search_filings to governance ToolNode (line 182-184)**

In `_create_tool_nodes()`, change:
```python
"governance": ToolNode(
    [
        get_news,
        get_insider_transactions,
    ]
),
```
To:
```python
"governance": ToolNode(
    [
        get_news,
        get_insider_transactions,
        search_filings,
    ]
),
```

- [ ] **Step 2: Add search_filings to news ToolNode (line 200-206)**

Change:
```python
"news": ToolNode(
    [
        get_news,
        get_global_news,
        get_insider_transactions,
    ]
),
```
To:
```python
"news": ToolNode(
    [
        get_news,
        get_global_news,
        get_insider_transactions,
        search_filings,
    ]
),
```

- [ ] **Step 3: Add import for search_filings at top of trading_graph.py**

At the top of the file (after existing imports), add:
```python
from services.orchestrator import search_filings
```

Note: Check if there are any existing imports from `services.orchestrator` and follow the same pattern. If circular import occurs (orchestrator imports from tradingagents), use lazy import inside `_create_tool_nodes`.

**Check orchestrator.py imports first** — if `orchestrator.py` already imports from `tradingagents.graph.trading_graph`, there would be a circular import. In that case, use this instead inside `_create_tool_nodes`:

```python
def _create_tool_nodes(self) -> Dict[str, ToolNode]:
    from services.orchestrator import search_filings  # lazy import
    return {
        ...
    }
```

- [ ] **Step 4: Commit**

```bash
git add backend/tradingagents-core/tradingagents/graph/trading_graph.py
git commit -m "feat(backend): add search_filings to governance and news ToolNodes"
```

---

### Task 7: Register Nightly CRON in main.py

**Files:** Modify: `backend/main.py` (APScheduler section)

- [ ] **Step 1: Add RAG ingestion to APScheduler startup**

Find the existing APScheduler setup in `main.py` (search for `_start_advisor_scheduler` or `BackgroundScheduler`). Add a new job alongside existing nightly jobs:

```python
from services.rag_ingestion import ingest_new, ingest_all

# In the scheduler startup section:
# Initial full ingestion at startup
try:
    logger.info("Starting initial RAG ingestion...")
    ingest_all()
    logger.info("Initial RAG ingestion complete")
except Exception as e:
    logger.warning(f"Initial RAG ingestion failed (non-blocking): {e}")

# Nightly refresh at 2 AM
scheduler.add_job(ingest_new, "cron", hour=2, minute=0, id="rag_ingestion")
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat(backend): register RAG ingestion at startup and nightly CRON"
```

---

### Task 8: Install Dependencies on Server & Verify

**Files:** None (server-side only)

- [ ] **Step 1: Deploy branch to server**

```bash
git push origin feature/vector-db-rag
ssh root@165.22.221.18 'cd /root/nivesh && git fetch && git checkout feature/vector-db-rag && git pull'
```

- [ ] **Step 2: Install new Python packages**

```bash
ssh root@165.22.221.18 '/root/nivesh/venv/bin/pip install chromadb "sentence-transformers>=2.7.0" langchain-text-splitters'
```

- [ ] **Step 3: Restart and verify**

```bash
ssh root@165.22.221.18 'systemctl restart nivesh && sleep 15 && journalctl -u nivesh --no-pager -n 10 | grep -i "ingestion\|chroma\|rag\|error"'
```

Expected: logs show "Initial RAG ingestion complete" or "collection size: N" with no errors.

- [ ] **Step 4: Commit server changes (if any)**

```bash
# If pip install changed requirements lock file on server, no commit needed — server is ephemeral
echo "Server deployed"
```
