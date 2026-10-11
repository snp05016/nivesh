## Nivesh Advisor Pipeline — Task Ledger

### Phase 1: Backend
- [x] 1.1 — SQLAlchemy model `AdvisorInsight` added to database.py + table auto-created via init_db
- [x] 1.2 — `services/transcript_engine.py` created with two-layer transcript strategy
- [x] 1.3 — `services/ticker_matcher.py` created with rapidfuzz fuzzy matching
- [x] 1.4 — `services/advisor_harvester.py` created with full ingestion pipeline
- [x] 1.5 — GET `/api/v1/portfolio/advisor-consensus` endpoint wired in main.py
- [x] 1.6 — POST `/analyze` response schema updated with `advisor_matrix` block
- [x] 1.7 — CRON launcher script `run_advisor_harvest.py` created + APScheduler in main.py
- [x] 1.8 — pip dependencies installed and verified (yt-dlp, youtube-transcript-api, faster-whisper, rapidfuzz)

### Phase 2: iOS Frontend
- [x] 2.1 — `AdvisoryConsensusService.swift` networking layer + response models created
- [x] 2.2 — `DalalStreetConsensusCard.swift` Home widget created
- [x] 2.3 — Home screen wired to render consensus card below Morning Brief
- [x] 2.4 — `AdvisoryMatrixCard.swift` Analysis tab component created + StockAnalysis updated
- [x] 2.5 — Analysis screen ANALYSIS tab wired to render advisory matrix

### Phase 3: Verification
- [ ] 3.1 — Manual harvester dry-run (requires YOUTUBE_API_KEY or network access)
- [ ] 3.2 — `/advisor-consensus` endpoint returns valid JSON (requires running server)
- [ ] 3.3 — `/analyze` response includes `advisor_matrix` array (requires running server)
- [x] 3.4 — iOS build: BUILD SUCCEEDED, zero errors
- [ ] 3.5 — git commit with canonical message
