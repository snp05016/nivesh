# Original User Request

## Initial Request — 2026-06-14T01:52:44Z

# Teamwork Project Prompt

Implement a Retrieval-Augmented Generation (RAG) vector database architecture to ingest unstructured financial texts (earnings calls) and allow LangGraph researchers to semantically search them.

Working directory: /Users/saumya/Desktop/nivesh
Integrity mode: development

## Requirements

### R1. Database & Embeddings Setup
Implement a local vector database setup (Qdrant or FAISS) and a lightweight local embedding pipeline (e.g., `sentence-transformers`).

### R2. Data Ingestion Service
Create `backend/services/vector_ingestion.py`. It must include logic to parse, chunk (e.g., via `RecursiveCharacterTextSplitter`), and embed text documents. All vectors must enforce strict metadata tracking (specifically `ticker`, `date`, and `document_type`).

### R3. RAG Search Tool
Create `backend/services/rag_tools.py` with a semantic search tool: `@tool def search_filings(query: str, ticker: str, limit: int = 3)`. It must pre-filter the database by the specific `ticker` before returning the most semantically relevant textual chunks.

### R4. Agent Integration
Wire the new `search_filings` tool into the LangGraph researcher nodes (Bull/Bear) inside `backend/services/orchestrator.py`.

## Acceptance Criteria

### Verification
- [ ] A dummy python test script successfully loads a fake earnings call string, chunks it, ingests it into the vector DB, and retrieves the correct chunk via `search_filings`.
- [ ] The `search_filings` tool correctly filters by ticker metadata.
- [ ] The LangGraph nodes in `orchestrator.py` correctly import and expose the tool.
- [ ] Code passes syntax checks and follows the "Zero magic strings" rule (no hardcoded DB URLs).
