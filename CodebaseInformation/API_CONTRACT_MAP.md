# Nivesh — Full-Stack API Contract & Bridge Map

> **Generated:** June 2026
> **Coverage:** Every `URLSession` call in Swift ↔ Every `@router`/`@app` route in FastAPI
> **Status key:** ✅ Match | ⚠️ Mismatch | 🔴 Missing frontend | ❌ Missing backend

---

## Domain: Auth (`routers/auth.py`)

### 1. Login
- **Swift Caller:** `NetworkManager.login`
- **Backend Receiver:** `login()`
- **Route:** `POST /login`
- **Bridge Status:** ✅ Match

### 2. Register
- **Swift Caller:** `NetworkManager.register`
- **Backend Receiver:** `register()`
- **Route:** `POST /register`
- **Bridge Status:** ✅ Match

---

## Domain: Portfolio (`routers/portfolio.py`)

### 3. Get Portfolio Holdings
- **Swift Caller:** `NetworkManager.getPortfolio`
- **Route:** `GET /portfolio/{user_id}`
- **Bridge Status:** ✅ Match

### 4. Add/Remove/Update Holding
- **Swift Caller:** `NetworkManager.addHolding`, `NetworkManager.removeHolding`, `NetworkManager.updateHolding`
- **Route:** `POST /portfolio`, `DELETE /portfolio/remove`, `PUT /portfolio/update`
- **Bridge Status:** ✅ Match

### 5. Valuation History
- **Swift Caller:** `HomeFeedService.fetchValuationHistory`
- **Route:** `GET /api/v1/portfolio/valuation-history`
- **Bridge Status:** ✅ Match

### 6. Portfolio Charts
- **Backend Route:** `GET /api/v1/portfolio/charts/{user_id}`
- **Bridge Status:** 🔴 Missing frontend (backend exists, no NetworkManager wrapper found)

---

## Domain: Analysis (`routers/analysis.py`)

### 7. Run AI Analysis
- **Swift Caller:** `NetworkManager.analyzeStock`
- **Route:** `POST /api/v1/analyze`
- **Bridge Status:** ✅ Match

### 8. Fetch Analysis History
- **Swift Caller:** `AnalysisEngineManager.fetchHistory`
- **Route:** `GET /api/v1/analysis/history/{user_id}`
- **Bridge Status:** ✅ Match

### 9. Batch Analysis
- **Backend Route:** `POST /api/v1/analyze/batch`
- **Bridge Status:** 🔴 Missing frontend (Batch UI not fully integrated)

### 10. Checkpoints Timeline
- **Backend Route:** `GET /api/v1/analysis/checkpoints/{ticker}`
- **Bridge Status:** 🔴 Missing frontend (Timeline view needed)

---

## Domain: Market Data (`routers/market.py`)

### 11. Search Ticker
- **Swift Caller:** `NetworkManager.search`
- **Route:** `GET /api/v1/market/search`
- **Bridge Status:** ✅ Match

### 12. Quick Info
- **Swift Caller:** `NetworkManager.getQuickInfo`
- **Route:** `GET /api/v1/market/quick-info/{ticker}`
- **Bridge Status:** ✅ Match

### 13. Top Gainers/Losers
- **Swift Caller:** `HomeFeedService.fetchTopMovers`
- **Route:** `GET /api/v1/market/movers`
- **Bridge Status:** ✅ Match

---

## Domain: Quantitative Engines

### 14. PKScreener
- **Backend Route:** `POST /api/v1/pkscreener/run` (`routers/pkscreener_runner.py`)
- **Bridge Status:** 🔴 Missing frontend (`PKScreenerView` needed)

### 15. Macro Modifiers
- **Backend Route:** `GET /api/v1/macro/dashboard` (`routers/macro_modifiers.py`)
- **Bridge Status:** 🔴 Missing frontend (`MacroDashboardView` needed)

### 16. Sector Rotation (RRG)
- **Swift Caller:** `NetworkManager.fetchSectorRotation`
- **Backend Route:** `GET /api/v1/sector-rotation` (`routers/sector_rotation.py`)
- **Bridge Status:** ✅ Match

### 17. Correlation Matrix
- **Swift Caller:** `NetworkManager.fetchCorrelationMatrix`
- **Backend Route:** `GET /api/v1/correlation` (`routers/correlation.py`)
- **Bridge Status:** ✅ Match

### 18. Options Microstructure (PCR/GEX)
- **Backend Route:** `GET /api/v1/microstructure/{ticker}` (`routers/microstructure_engine.py`)
- **Bridge Status:** 🔴 Missing frontend (`OptionsMicrostructureScreen` needed)

### 19. Earnings Surprise
- **Swift Caller:** `NetworkManager.fetchEarningsSurprise`
- **Backend Route:** `GET /api/v1/earnings-surprise` (`routers/earnings_surprise.py`)
- **Bridge Status:** ✅ Match

### 20. Stress Test
- **Swift Caller:** `NetworkManager.runStressTest`
- **Backend Route:** `POST /api/v1/stress-test` (`routers/stress_test.py`)
- **Bridge Status:** ✅ Match

### 21. Natural Language Screener
- **Swift Caller:** `NetworkManager.runNLScreener`
- **Backend Route:** `POST /api/v1/nl-screener` (`routers/nl_screener.py`)
- **Bridge Status:** ✅ Match

---

## Domain: Harvesters & Integrations

### 22. RAG Ingestion (PDF/Docs)
- **Backend Route:** `POST /api/v1/rag/upload` (`routers/rag_ingestion.py`)
- **Bridge Status:** 🔴 Missing frontend (No PDF upload UI in Copilot yet)

### 23. Advisor Video Harvester
- **Backend Route:** `GET /api/v1/harvester/youtube/latest` (`routers/expert_youtube_harvester.py`)
- **Bridge Status:** 🔴 Missing frontend (AdvisorVideoPlayer needed)

### 24. Piotroski Breakdown
- **Backend Route:** `GET /api/v1/piotroski/breakdown/{ticker}` (`routers/piotroski.py`)
- **Bridge Status:** 🔴 Missing frontend (PiotroskiSheet needed)

### 25. Strategy Paper Trading
- **Backend Route:** `GET /api/v1/strategy/mock-trades` (`routers/strategy_engine.py`)
- **Bridge Status:** 🔴 Missing frontend (StrategyExecutionView needed)
