# Nivesh — Architecture Blueprint

> **Authority:** Nivesh Architectural Ordinance
> **Generated:** June 2026
> **Scope:** High-level summary of the Nivesh architecture stack.

## Overview

Nivesh is a full-stack Indian stock market intelligence platform. It combines a FastAPI backend with a LangGraph multi-agent AI pipeline and a SwiftUI iOS frontend using a premium "Banknote" design system.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy, PostgreSQL |
| AI Pipeline | LangGraph, Claude Sonnet/Haiku, DeepSeek |
| iOS | SwiftUI, AVFoundation, Charts, WidgetKit |
| Data | yfinance, PKScreener, FinBERT, matplotlib, jugaad-data |
| Infra | DigitalOcean, multiprocessing, Redis, APNs, Celery |

---

## 1. Frontend Architecture (iOS - SwiftUI)

The frontend strictly enforces the **Banknote Aesthetic**, mimicking Indian currency logic through components like `GuillocheDivider`, `EKPressStyle` (haptics), and `BanknoteSignalBadge`.

- **Navigation:** Deeply integrated TabView (Home, Markets, Ideas, News, Portfolio) with a Sidebar (`MarketsView`) mapping to an extensible `MarketSection` enum.
- **Data Flow:** Unidirectional data flow. Extensive use of `@StateObject` ViewModels and global `@EnvironmentObject` (like `AuthManager`).
- **Core Screen Features:** 
  - `AnalysisScreen`: Renders the output of the multi-agent AI debate.
  - `CopilotScreen`: Global AI assistant.
  - Custom data visualization tools (Correlation Matrix, Sector Rotation, Options Strategy).

---

## 2. Backend Architecture (FastAPI)

Built on the **Controller-Service-Repository** pattern.

- **Controllers (`routers/`)**: Validate HTTP requests, manage rate limiting (sliding window), and spawn async/multiprocessing tasks. **No business logic or DB calls are allowed here.**
- **Services (`services/`)**: Orchestrate all LangGraph flows, external data fetching (`nse_data_provider.py`), and mathematical engines (`microstructure_engine.py`, `macro_modifiers.py`).
- **Repository**: Managed via SQLAlchemy `get_session()` context managers to ensure thread-safe database interactions.
- **Global State**: Strictly controlled using `threading.Lock()` for any module-level mutable variables.

---

## 3. AI Pipeline Architecture (LangGraph)

Uses a **Dialectical Asymmetry** model to simulate a hedge fund committee:

1. **Smart Cache Gate**: DeepSeek runs a high-speed check to determine if the fundamental data has shifted enough to warrant a re-run.
2. **Debate Agents**: Bull and Bear researchers analyze the data. The Bear prompt is intentionally longer and carries a 1.5x weight advantage to offset LLM positivity bias.
3. **Committee Review**: Risk Committee and Portfolio Manager agents review the debate and output JSON conforming strictly to Nivesh schemas.
4. **Normalization**: Output is run through `_normalize_response()` and `_ban_western_scale()` to guarantee clean Indian formatting (Lakhs/Crores) before saving to PostgreSQL.
