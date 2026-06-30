# Harvester Architecture

## Overview
The Harvester subsystem is responsible for scraping, processing, and storing external financial data, news, and expert opinions. It was originally ported from an external `nivesh-harvester/main.py` script into the main Nivesh backend, but its architectural isolation remains strictly enforced.

## Database Isolation (`harvester.db` vs `stockapp.db`)

One of the most critical design decisions in Nivesh is the absolute separation of the Harvester database (`harvester.db`) from the main backend database (`stockapp.db`).

### Why Isolate?
- **Crash Immunity:** Web scraping is inherently fragile and prone to unstructured data anomalies. If a faulty scrape corrupts the data or a malformed text chunk breaks the SQLite file, the main user-facing Nivesh backend (running on port 8000, relying on `stockapp.db`) remains completely unaffected.
- **Zero Overlap:** The harvester creates a completely separate SQLite file (`harvester.db`) located at the backend root. 
- **Database Bloat Prevention:** Scraping generates massive volumes of text (raw articles, YouTube transcripts, SEBI filings). Keeping this in a separate database prevents `stockapp.db` from bloating to unmanageable sizes, ensuring that core app queries remain fast and efficient.

### Models and Schema
The `harvester.db` schema is defined in `backend/services/harvester_db.py`. It currently consists of two tables:
- **`HarvestedCard`**: Stores one reformatted, credibility-scored card per scraped item. It uses a deterministic hash (`external_id`) of the URL and content to guarantee deduplication.
- **`SourceHealth`**: Tracks per-source scrape health (success/failure rates, error messages, etc.) for the `/harvester/sources` endpoint.

> **CRITICAL RULE FOR FUTURE AGENTS:** 
> Do **NOT** merge the `HarvestedCard` or `SourceHealth` models into the main `models/db_models.py`. They must remain in `backend/services/harvester_db.py` to preserve the isolation of `harvester.db`.

## Background Job Flow

The Harvester operates asynchronously and exposes administrative triggers alongside data-fetching routes via `backend/routers/harvester.py`.

### 1. Scraping and Ingestion
Scheduled background jobs or manual admin triggers (via `POST /harvester/trigger/scrape`) invoke the various scraping modules (e.g., `harvest_sebi_filings`, `scrape_all_expert_sources`, `harvest_youtube_transcripts`).
- Data is pulled and minimally processed.
- A deterministic `external_id` is generated for each item.
- The `upsert_card` function inserts the card into `harvester.db` *only* if the `external_id` is new and its credibility score passes the `MIN_CREDIBILITY` threshold (currently 5). 

### 2. Processing and Formatting
Cards initially inserted may lack a reformatted summary. A background routine (or on-demand process) runs `reformat_pending()`, which:
- Queries `harvester.db` for cards where `reformatted_summary` is NULL.
- Passes the `raw_text` to an LLM-driven formatter (`reformat_single`).
- Updates the card with the `reformatted_summary`, `key_takeaways`, `tickers`, `sentiment`, and adjusted `credibility_score`.

### 3. Serving the Data
The main application accesses harvester data via authenticated endpoints in `backend/routers/harvester.py` (e.g., `GET /harvester/feed`, `GET /harvester/governance/{ticker}`). These endpoints use the isolated `get_session()` from `harvester_db.py`, ensuring that traffic querying scraped data never touches `stockapp.db`.
