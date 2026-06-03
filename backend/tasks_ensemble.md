# Ensemble Signal Layer — Task Ledger

## Part 1: PKScreener Integration
- [x] 1.1  pip install pkscreener + verify import
- [x] 1.2  DB: `pkscreener_signals` table added to database.py
- [x] 1.3  Alembic migration run
- [x] 1.4  services/pkscreener_runner.py created
- [x] 1.5  CRON job wired in main.py (4:45 PM IST nightly)
- [x] 1.6  GET /api/v1/technical-signals endpoint added to main.py
- [x] 1.7  /analyze POST handler: pkscreener signals injected into agent context (deep_scan gated)
- [ ] 1.8  Dry run: at least one signal row appears in DB for a known holding

## Part 2: FinBERT Sentiment Scoring
- [x] 2.1  pip install transformers torch + verify import
- [x] 2.2  DB: `sentiment_score` + `sentiment_label` columns added to news_articles
- [x] 2.3  Alembic migration run
- [x] 2.4  services/sentiment_engine.py created
- [x] 2.5  news_harvester.py updated to call sentiment engine after each article insert
- [x] 2.6  services/sentiment_engine.py: backfill function for existing rows
- [ ] 2.7  Backfill run on existing news_articles rows
- [x] 2.8  GET /api/v1/home-feed updated to include sentiment_score in response
- [ ] 2.9  Dry run: curl /api/v1/home-feed confirms sentiment_score is a float not null

## Part 3: iOS Deep Scan Toggle
- [x] 3.1  Backend: deep_scan field in AnalyzeRequest
- [x] 3.2  Backend: pkscreener + finbert injection wrapped in deep_scan check
- [x] 3.3  iOS: AnalysisScreen.swift - Deep Scan toggle (alert + loading badge)
- [x] 3.4  iOS: SettingsScreen.swift - default toggle

## Verification
- [x] 4.1  Backend starts without errors after all changes (imports verified)
- [ ] 4.2  /technical-signals returns valid JSON for a portfolio ticker
- [ ] 4.3  /analyze response includes pkscreener_signals block
- [ ] 4.4  news_articles rows have non-null sentiment_score values
- [ ] 4.5  iOS build succeeds
- [ ] 4.6  git commit
