# Nivesh Architecture Snapshot

> Last verified: 2026-06-16 from local source files. Use this as orientation, not as an enforcement document. `AGENTS.md` remains the architectural authority.

## Product Shape

Nivesh is an Indian equity intelligence app with three main surfaces:

| Surface | Current implementation |
|---|---|
| Backend | FastAPI app in `backend/main.py` with routers in `backend/routers/` |
| Data and AI services | Python services in `backend/services/`, including LangGraph orchestration, market data, screeners, harvesters, and portfolio analytics |
| iOS app | SwiftUI app in `ios/StockApp/stockme/stockme/` with Banknote-themed design tokens and components |

## Backend

The intended architecture is Controller-Service-Repository:

- Routers live under `backend/routers/` and expose HTTP endpoints.
- Services live under `backend/services/` and hold business logic, AI orchestration, deterministic engines, caching, and data fetching.
- Database access is centered on SQLAlchemy models and `get_session()` in `backend/database.py`.
- Several current routers still contain meaningful logic and DB access, so treat the pattern as a target architecture, not a fully achieved invariant.

Important backend entry points:

| Area | Source |
|---|---|
| App setup and router includes | `backend/main.py` |
| Stock analysis jobs | `backend/routers/analysis.py`, `backend/services/orchestrator.py`, `backend/services/job_manager.py` |
| Portfolio and trade journal | `backend/routers/portfolio.py` |
| Market data and dashboards | `backend/routers/market.py` |
| Copilot | `backend/routers/copilot.py`, `backend/services/copilot_service.py` |
| Cache and Redis wrapper | `backend/services/cache_service.py` |
| Canonical LLM constants | `backend/services/llm_utils.py` |

## iOS App

The iOS app is a SwiftUI application using the Banknote design system:

| Area | Source |
|---|---|
| Root tabs and Markets hub | `ContentView.swift` |
| API client | `NetworkManager.swift`, `NetworkManager+Sidebar.swift` |
| Shared models | `Models.swift`, `HomeFeedModels.swift` |
| Theme and formatting | `Utilities/Theme.swift`, `Utilities/IndianFormatter.swift`, `BanknoteDesignSystem.swift` |
| Reusable components | `Components/` |
| Screens | `Views/` |

The bottom tab bar currently has five tabs: Home, Markets, Ideas, News, Portfolio.

## AI Pipeline

The current AI stack uses:

| Tier | Model constant | Source |
|---|---|---|
| Bulk and low-cost tasks | `deepseek-chat` | `services/llm_utils.py` |
| Synthesis | `claude-haiku-4-5-20251001` | `services/llm_utils.py` |
| Tier 3 reformat/export/batch paths | `claude-sonnet-4-6` | `services/llm_utils.py` |

The main analysis flow is job-based:

1. iOS posts to `POST /analyze`.
2. `routers/analysis.py` creates or returns an analysis job.
3. The client polls `GET /analyze/job/{job_id}` and `GET /analyze/active`.
4. `services/orchestrator.py` runs cache checks, LangGraph work, enrichment, reformatting, normalization, and persistence.

## Current Infrastructure Notes

- Redis is used or attempted through `services/cache_service.py` and several cache helpers, with fallback behavior in places.
- Celery exists only as optional/scaffolded support: `backend/services/celery_tasks.py` and a commented dependency in `backend/requirements.txt`.
- APNs-related flows exist in notification routers and iOS `NotificationManager.swift`, but some backend dispatch paths are mock/development oriented.
- `jugaad-data` is present and used by `services/nse_data_provider.py`, with yfinance fallback behavior.

## Useful Verification Commands

Run these from repo root when this directory may be stale:

```bash
rg -n "@(app|router)\.(get|post|put|delete|patch)\(" backend/main.py backend/routers
rg -n "URL\(string:|endpoint =|path =|urlString =" ios/StockApp/stockme/stockme/NetworkManager*.swift ios/StockApp/stockme/stockme/HomeFeedService.swift
rg -n "HAIKU_MODEL|SONNET_MODEL|DEEPSEEK_MODEL" backend/services/llm_utils.py
```
