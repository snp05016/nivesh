# NIVESH MEGA EXPANSION — Master Task Ledger
Last updated: 2026-06-03

---

## PHASE 1 — BACKEND: NEWS & YOUTUBE DATA LAYER
- [x] 1.1  DB: `news_articles` table added to database.py
- [x] 1.2  DB: `youtube_videos` table added to database.py
- [x] 1.3  DB: `portfolio_valuation_history` table added to database.py
- [x] 1.4  Alembic migration run for all three new tables
- [x] 1.5  services/news_harvester.py — Moneycontrol deep body scraper
- [x] 1.6  services/news_harvester.py — ET RSS enrichment
- [x] 1.7  services/youtube_harvester.py — yt-dlp metadata + thumbnail scraper
- [x] 1.8  services/portfolio_snapshot.py — nightly portfolio valuation logger
- [x] 1.9  GET /api/v1/home-feed endpoint
- [x] 1.10 GET /api/v1/home-feed/youtube endpoint (included in home-feed)
- [x] 1.11 GET /api/v1/portfolio/valuation-history endpoint
- [x] 1.12 GET /search endpoint — already has in-memory index
- [x] 1.13 Nightly CRON: news_harvester + youtube_harvester + portfolio_snapshot wired
- [x] 1.14 pip dependencies installed (newspaper3k, feedparser)

## PHASE 2 — iOS: HOME FEED REDESIGN
- [x] 2.1  HomeFeedModels.swift — all response structs
- [x] 2.2  HomeFeedService.swift — networking
- [x] 2.3  NewsCardView.swift — interactive tappable news card
- [x] 2.4  YouTubeCardView.swift — video card with thumbnail + deep link
- [x] 2.5  HomeScreen.swift — sidebar hamburger button REMOVED
- [x] 2.6  HomeScreen.swift — news feed section injected
- [x] 2.7  HomeScreen.swift — YouTube section injected
- [x] 2.8  HomeScreen.swift — dead/useless elements pruned
- [x] 2.9  NiveshNavigationSidebar.swift — updated with new section IDs

## PHASE 3 — iOS: PORTFOLIO VALUATION CALENDAR
- [x] 3.1  ValuationCalendarView.swift — full calendar component
- [x] 3.2  ValuationCalendarService.swift — networking
- [x] 3.3  PortfolioScreen.swift — calendar section injected

## PHASE 4 — iOS: SEARCH PERFORMANCE FIX
- [x] 4.1  SearchScreen.swift — debounce increased to 350ms
- [x] 4.2  SearchScreen.swift — local StockDatabase pre-filter before network call
- [x] 4.3  SearchScreen.swift — async task cancellation on keystroke
- [x] 4.4  Backend /search — pre-warmed in-memory index at startup
- [x] 4.5  SearchScreen.swift — skeleton loading state (SearchSkeletonRow)

## PHASE 5 — VERIFICATION
- [x] 5.1  Backend: all new endpoints return valid JSON
- [x] 5.2  iOS: Xcode build zero errors zero warnings
- [ ] 5.3  iOS: simulator — home feed loads news cards
- [ ] 5.4  iOS: simulator — YouTube cards tap to YouTube app
- [ ] 5.5  iOS: simulator — portfolio calendar renders
- [ ] 5.6  iOS: simulator — search no longer freezes app
- [ ] 5.7  git commit both repos
