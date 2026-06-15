# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** Definitive technical blueprint of the Nivesh ecosystem.
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), LangGraph (AI Pipeline), and specialized engines.
> **Last Updated:** June 2026.

---

## 1. Project Philosophy & Core Pillars

Nivesh is a Premium AI-First Wealth Intelligence System focused exclusively on the Indian Equity Market.

### Pillar I: The Banknote Aesthetic (Frontend — iOS SwiftUI)

The user interface is designed as a Financial Instrument.
- **Guilloche Logic:** Procedural drawing of sine-wave pairs for borders and dividers (`GuillocheDivider`).
- **Tactile Feedback:** Emil Kowalski-style press interactions (`EKPressStyle`).
- **Design System Architecture:** 
  - `Theme.swift`: Adaptive color system, semantic typography (Georgia serif, Hindi italic).
  - `BanknoteDesignSystem.swift`: Security thread, watermarks, Governor seals.
  - `SharedComponents.swift`: Universal components with strict `IndianFormatter.formatLakhsCrores()` enforcement.

### Pillar II: Dialectical Reasoning (AI Pipeline — LangGraph Multi-Agent)

- **The Debate Architecture:** Bull and Bear researchers attempt to invalidate each other's thesis. 
- **Dialectical Asymmetry:** The Bear researcher gets the epistemic advantage—the burden of proof is on the Bull.
- **Committee Review:** Trader, Risk Committee, and Portfolio Manager agents synthesize the debate.

### Pillar III: Context Stratification (Performance Engineering)

- **Smart Cache Gate:** A DeepSeek pre-flight check determines if fundamental data shifted enough to run the full LangGraph pipeline.
- **Data Integrity:** `jugaad-data` used as primary NSE/BSE fetcher; `yfinance` serves as a fallback. 
- **Response Normalization:** Strict pipeline guarantees clean JSON extraction and format normalization before caching.

---

## 2. Directory Structure

### Backend (`/backend/`)
- `routers/`: Controller layer (e.g. `analysis.py`, `portfolio.py`, `copilot.py`, `nl_screener.py`).
- `services/`: Business logic, LangGraph nodes, and quantitative engines (e.g., `nse_data_provider.py`, `macro_modifiers.py`, `microstructure_engine.py`).
- `schemas/`: Pydantic models for request/response validation.
- `models/`: SQLAlchemy ORM representations (e.g., `BlockDeal`, `FIIDIIFlow`).
- `scripts/`: Generation and automation scripts (e.g., `generate_frontend_prompts.py`).

### Frontend (`/ios/StockApp/stockme/stockme/`)
- `Views/`: SwiftUI View screens mapped to routing enums (`MarketSection`). Includes `AnalysisScreen`, `EarningsDashboardView`, `SectorRotationScreen`, etc.
- `Components/`: Extracted reusable Banknote-themed UI elements.
- `Utilities/`: Formatters, the core `Theme.swift`, and Haptic managers.
- `NetworkManager.swift`: Primary API client interacting with the FastAPI backend.
- `Models.swift`: Swift Codable structures matching backend Pydantic schemas.

---

## 3. Advanced Quantitative Features

- **NL Screener:** NLP to SQL/Rule engine for semantic stock discovery (`nl_screener.py` / `NLScreenerScreen.swift`).
- **Options Microstructure:** Computes Put/Call Ratio (PCR) and Gamma Exposure (GEX) deterministically.
- **Stress Testing:** Macroeconomic shock simulations across user portfolios (`stress_test.py` / `StressTestScreen.swift`).
- **Sector Rotation:** Visualizes capital flow using RRG metrics.
- **Earnings Surprise:** Tracks historical and projected earnings deviations.
- **PKScreener Integration:** Deep technical breakout pattern detection.

## 4. Execution Flows

### AI Analysis Pipeline
1. iOS client requests analysis via `POST /api/v1/analyze`.
2. Backend routes to `analysis.py` → `orchestrator.py`.
3. `staleness.py` gates the request; if cached & valid, returns instantly.
4. If fresh analysis required, a background `multiprocessing.Process` spawns.
5. LangGraph nodes (Market Analyst, Fundamentals Analyst, Bull vs Bear, Risk Committee) execute sequentially.
6. `_normalize_response()` ensures the output JSON adheres to Nivesh schemas and Indian numbering conventions.
7. Result cached in PostgreSQL and returned via SSE or polling.
