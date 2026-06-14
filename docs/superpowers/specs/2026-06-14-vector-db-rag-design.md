# Vector DB & RAG Architecture — Design Spec

**Date:** 2026-06-14 | **Status:** Approved | **Branch:** feature/vector-db-rag

## 1. Objective

Add Retrieval-Augmented Generation to Nivesh's LangGraph multi-agent pipeline. Ingest unstructured financial text (news articles, advisor transcripts) into a vector database, giving agents semantic search capabilities to detect qualitative red flags during stock analysis.

## 2. Architecture

```
LangGraph Agents (Bear, Bull, Governance)
         │ @tool search_filings(query, ticker)
         ▼
services/rag_tools.py          ← embed query, pre-filter, top-K search
         │
         ▼
services/vector_store.py       ← ChromaDB (SQLite backend, in-process)
         │
         ▼
services/rag_ingestion.py      ← nightly CRON: fetch DB rows, chunk, embed, upsert
```

**Data sources ingested:**
- `NewsArticle` table: body_text from Moneycontrol, ET, Business Standard, Livemint, NDTV Profit
- `AdvisorInsight` table: YouTube advisor transcripts with SEBI-registered analysis

**Agents receiving the tool:** Bull Researcher, Bear Researcher, Governance Analyst

## 3. ChromaDB Collection Schema

```
Collection: nivesh_filings
├── embedding_dim: 384          (all-MiniLM-L6-v2)
├── distance_metric: cosine
├── metadata (filterable):
│   ├── ticker: str             "RELIANCE.NS"
│   ├── date: str               "2025-06-01"
│   ├── doc_type: str           "news_article" | "advisor_transcript"
│   ├── source: str             "moneycontrol" | "et" | advisor_name
│   └── chunk_idx: int          0, 1, 2... for multi-chunk documents
└── document: str               chunked text (800 tokens, 100 overlap)
```

## 4. Data Flow

### Startup
1. `vector_store.py` initializes ChromaDB persistent client (`backend/chroma_db/`)
2. Gets or creates `nivesh_filings` collection (384-dim, cosine)
3. `rag_ingestion.py` queries all NewsArticle rows + AdvisorInsight rows
4. Each doc: RecursiveCharacterTextSplitter (800 tokens, 100 overlap) → embed → upsert
5. De-duplication by composite key `(ticker, date, doc_type, chunk_idx)`

### Agent Runtime
1. Agent calls `search_filings(query, ticker)`
2. Embed query with MiniLM → 384-dim vector
3. ChromaDB: `where={"ticker": ticker}` pre-filter + cosine similarity → top-3
4. Returns formatted string: `[DATE] [SOURCE]\n{chunk_text}\n---`

### Nightly CRON
1. APScheduler triggers `rag_ingestion.ingest_new()`
2. Queries rows where `published_at > last_ingested_timestamp`
3. Chunk → embed → upsert (batches of 50 with gc.collect())

## 5. Error Handling

| Scenario | Behavior |
|----------|----------|
| Embedding fails | Return "RAG query unavailable" string; agent degrades gracefully |
| ChromaDB connection fails | In-memory fallback with warning, re-init on next access |
| Empty query results | Return "No relevant documents found for {ticker}" |
| OOM during batch | Chunk ingestion into batches of 50, gc.collect() between |
| Duplicate ingest | Skip by composite key, no duplicate vectors |

## 6. Files

### New (3)
| File | Purpose |
|------|---------|
| `backend/services/vector_store.py` | ChromaDB client, collection init, get-or-create, upsert, query |
| `backend/services/rag_ingestion.py` | DB queries, chunking (RecursiveCharacterTextSplitter), batch embed, CRON handler |
| `backend/services/rag_tools.py` | `search_vector_db(query, ticker, limit)` — embed, pre-filter, search |

### Modified (3)
| File | Change |
|------|--------|
| `backend/services/orchestrator.py` | Replace `search_filings` stub (line 207) with real impl; add to governance/bull/bear tool lists |
| `backend/requirements.txt` | Add `chromadb>=0.5.0`, `sentence-transformers>=2.7.0` |
| `backend/tradingagents-core/tradingagents/graph/trading_graph.py` | Add `search_filings` to ToolNode entries |

### Not Modified
- `backend/routers/` — no new endpoints needed (RAG is agent-internal)
- iOS — no changes (backend-only feature)
- `backend/main.py` — APScheduler already exists, ingestion job registered there

## 7. Tool Injection Pattern

Following the existing `@tool` pattern from `orchestrator.py`:

```python
# orchestrator.py — replace stub
from services.rag_tools import search_vector_db

@tool
def search_filings(query: str, ticker: str) -> str:
    """Search the vector DB for news, earnings calls, and advisor analysis
    related to {ticker}. Use when investigating governance issues, management
    guidance, red flags, or qualitative signals not in structured data."""
    return search_vector_db(query, ticker, limit=3)
```

Added to agent factories:
- `analyst_factories["governance"]` → `[get_news, get_insider_transactions, search_filings]`
- `analyst_factories["bull"]` → `[...existing, search_filings]`
- `analyst_factories["bear"]` → `[...existing, search_filings]`

## 8. Constraints

- **Server**: 2 GB RAM, 1 CPU, no Docker, Python 3.12, SQLite primary DB
- **Embedding model**: `all-MiniLM-L6-v2` (384-dim, ~80 MB), already have transformers+torch
- **Scale**: < 1000 documents total, ~15s startup batch embed, ~50ms per query
- **Freshness**: Nightly CRON, max 24h staleness
