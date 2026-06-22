# Feature Blueprint: Vector Database & RAG Architecture for Unstructured Financial Data

## 1. Objective
Design and implement a Vector Database architecture (Retrieval-Augmented Generation) to ingest, chunk, and embed unstructured financial text (Earnings Call Transcripts, NSE/BSE Corporate Disclosures, News). This will grant the LangGraph researchers semantic search capabilities to detect qualitative red flags (e.g., auditor resignations, poor management guidance).

---

## 2. Technical Requirements

### 2.1 Database Selection & Setup
- **Technology:** Use `Qdrant` (or `pgvector` if PostgreSQL is already heavily relied upon) for the vector store due to its speed and lightweight local/docker capabilities.
- **Embedding Model:** Implement a lightweight local embedding model using `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) or OpenAI/DeepSeek embeddings. Ensure the embedding dimension matches the Vector DB collection initialization.

### 2.2 Data Ingestion Pipeline (`services/vector_ingestion.py`)
Create a new service dedicated to ingesting documents:
1. **Document Parsers:** Build functions to parse scraped earnings call transcripts and NSE PDF disclosures into raw text.
2. **Semantic Chunking:** Use LangChain's `RecursiveCharacterTextSplitter` to chunk the text into manageable blocks (e.g., 500-1000 tokens) with a 100-token overlap to preserve context.
3. **Metadata Attachment:** Every vector must have strict metadata: `{"ticker": "RELIANCE.NS", "date": "2025-06-01", "document_type": "earnings_call"}` to allow precise pre-filtering before semantic search.

### 2.3 The RAG Tool (`services/rag_tools.py`)
Implement the actual callable tool that the `TradingAgentsGraph` will use:
- **`search_filings(query: str, ticker: str, limit: int = 3)`**: Embeds the natural language query, pre-filters the DB by the specific `ticker`, and returns the top `limit` most relevant textual chunks.

### 2.4 Agent Integration (`services/orchestrator.py`)
- Wire the `search_filings` tool into the LangGraph setup so the **Bear Researcher** and **Bull Researcher** can dynamically query the Vector DB during their analysis if they suspect governance or guidance issues.

---

## 3. Agentic Execution Framework (Strict Enforcement)

This is a massive architectural addition. You **MUST** deploy a team of subagents to execute this sequentially:

1. **The Planner Agent:** 
   - Analyzes the current codebase.
   - Decides whether to use `Qdrant` (memory/docker) or `FAISS` (local file) based on the server setup.
   - Drafts a clear schema for the Vector DB collections.

2. **The Builder Agent:** 
   - Writes `services/vector_ingestion.py` (chunking and embedding logic).
   - Writes `services/rag_tools.py` (the semantic search tool).
   - Injects the tool into the existing LangGraph researcher nodes in `orchestrator.py`.

3. **The Reviewer Agent:** 
   - Performs a rigorous code quality review.
   - Verifies the Karpathy Principles: No magic strings for DB URLs, ensures exceptions are handled explicitly during embedding failures, and ensures the embedding vector size aligns mathematically with the DB schema.

4. **The Verifier/Tester Agent:** 
   - Writes a quick test script to ingest one fake earnings call transcript, queries it semantically, and verifies that the correct textual chunk is returned.
