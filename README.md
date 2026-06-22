<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="ios/StockApp/stockme/stockme/nivesh_ios_icon.svg">
    <img src="ios/StockApp/stockme/stockme/nivesh_ios_icon.svg" width="180" alt="Nivesh">
  </picture>

  # निवेश · Nivesh

  **AI-Powered Indian Equity Analysis Platform**

  <br>

  [![Platform](https://img.shields.io/badge/iOS-17.0+-000000?style=flat&logo=apple&logoColor=white)](https://developer.apple.com/ios/)
  [![Swift](https://img.shields.io/badge/SwiftUI-F05138?style=flat&logo=swift&logoColor=white)](https://developer.apple.com/xcode/swiftui/)
  [![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-1C3C3C?style=flat&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18+-4169E1?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
  [![pgvector](https://img.shields.io/badge/pgvector-RAG-2C5F2D?style=flat&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
  [![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io)

  <br>

  [Features](#-features) • [Architecture](#-architecture) • [AI Pipeline](#-ai-pipeline) • [Quant Engine](#-quantitative-engines) • [iOS App](#-ios-app) • [Quick Start](#-quick-start) • [Deployment](#-deployment)

  <br>

  <sub>_निवेश · Hindi for "Investment"_</sub>

</div>

---

<div align="center">
  <h3>
    <code>SwiftUI · FastAPI · LangGraph · pgvector · 8-Agent Debate · 14-Scenario Stress Test · ₹ Lakh/Crore</code>
  </h3>
  <br>
  <h4>📈 Institutional-grade analysis for the Indian retail investor</h4>
</div>

---

## ✦ Features

<table>
<tr>
  <td width="50%" valign="top">
    <h3>🧠 Multi-Agent AI Analysis</h3>
    <p>8-agent LangGraph pipeline with dialectical debate — Bull vs Bear researchers, Research Manager synthesis, and Portfolio Manager weighting. Bear findings weighted <strong>1.5×</strong> for conservatism.</p>
    <details>
      <summary><b>Agents</b></summary>
      <ul>
        <li>Bull Researcher — constructs bullish thesis</li>
        <li>Bear Researcher — constructed bearish thesis (longer prompt, more data)</li>
        <li>Research Manager — report synthesis</li>
        <li>3 Debators (Aggressive / Neutral / Conservative)</li>
        <li>Trader — transaction proposals</li>
        <li>Portfolio Manager — final weighted synthesis</li>
        <li>Claude Sonnet — final reformatting pass</li>
      </ul>
    </details>
  </td>
  <td width="50%" valign="top">
    <h3>🤖 Quantitative Pre-Pipeline</h3>
    <p>Deterministic ML runs <em>before</em> any LLM call — regime detection, conformal prediction bounds, SHAP-style feature importance, and confidence calibration with KNN historical analogues.</p>
    <details>
      <summary><b>Engines</b></summary>
      <ul>
        <li>Market Regime Detection (Trending / Ranging / Volatile)</li>
        <li>Conformal Prediction — calibrated target price intervals</li>
        <li>Factor Engine — RSI, MACD, Bollinger, ATR, OBV, SMA/EMA</li>
        <li>Confidence Engine — signal agreement + bear asymmetry</li>
        <li>Piotroski F-Score (9-point fundamental strength)</li>
      </ul>
    </details>
  </td>
</tr>
<tr>
  <td width="50%" valign="top">
    <h3>🧪 Stress Test Engine (Tier 2.5)</h3>
    <p>14 Indian-market scenarios with factor betas, EWMA Vasicek shrinkage, Almgren-Chriss liquidity penalty, and 6-dimensional risk scoring.</p>
    <details>
      <summary><b>Scenarios</b></summary>
      <code>nifty_crash</code> · <code>sensex_crash</code> · <code>midcap_crash</code> · <code>smallcap_crash</code> · <code>oil_shock</code> · <code>rate_hike</code> · <code>rate_cut</code> · <code>fii_exodus</code> · <code>dii_exodus</code> · <code>inflation_shock</code> · <code>currency_crash</code> · <code>global_recession</code> · <code>banking_crisis</code> · <code>policy_shock</code>
    </details>
    <details>
      <summary><b>Risk Scores</b></summary>
      <code>Risk Score</code> · <code>Stress Score</code> · <code>Macro Fragility</code> · <code>Liquidity</code> · <code>Concentration (HHI + MRC)</code> · <code>Tail Risk</code>
    </details>
  </td>
  <td width="50%" valign="top">
    <h3>📊 Portfolio Analytics</h3>
    <p>Comprehensive portfolio tracking with correlation matrix, diversification scoring, sector concentration, MPT mean-variance optimization, and Nifty 50 benchmark comparison.</p>
    <ul>
      <li>Real-time P&L tracking (1D, 1W, 1M, 1Y, All)</li>
      <li>CAGR vs benchmark comparison</li>
      <li>PDF/XLSX portfolio export</li>
      <li>Trade journal with outcome logging</li>
      <li>Daily net worth snapshots</li>
    </ul>
  </td>
</tr>
<tr>
  <td width="50%" valign="top">
    <h3>📡 Data Harvesting & RAG</h3>
    <p>Automated content ingestion from multiple sources with pgvector-based semantic search for agents.</p>
    <ul>
      <li><b>YouTube:</b> Financial advisor videos, transcripts, stance extraction</li>
      <li><b>SEBI filings:</b> Corporate filing governance forensics</li>
      <li><b>News:</b> Multi-source with FinBERT sentiment scoring</li>
      <li><b>AMFI:</b> Mutual fund NAV data</li>
      <li><b>NSE:</b> Bulk/block deals, FII/DII flows</li>
      <li><b>PKScreener:</b> Technical screening signals</li>
      <li><b>RAG:</b> MiniLM → pgvector → agent tool retrieval</li>
    </ul>
  </td>
  <td width="50%" valign="top">
    <h3>📱 iOS App (SwiftUI)</h3>
    <p>Premium Banknote Aesthetic — aged-paper backgrounds, security gold accents, serif typography (Georgia), and haptic feedback throughout.</p>
    <ul>
      <li>7 banknote theme presets (₹10 → ₹500 + Dark)</li>
      <li>Home Screen widgets (WidgetKit)</li>
      <li>Face ID / Touch ID biometric locking</li>
      <li>EventKit earnings calendar reminders</li>
      <li>SFSpeechRecognizer voice search</li>
      <li>Push notifications for price alerts</li>
      <li>60+ screens across 10 feature areas</li>
    </ul>
  </td>
</tr>
<tr>
  <td width="50%" valign="top">
    <h3>🔬 Advanced Analytics</h3>
    <p>Specialized analytical modules covering the full investment lifecycle.</p>
    <details>
      <summary><b>Modules</b></summary>
      <ul>
        <li><b>Stock Screener:</b> Natural language → SQL → 2000+ stock universe</li>
        <li><b>Sector Rotation:</b> Multi-period quadrant analysis with FII/DII flow</li>
        <li><b>Earnings Surprise:</b> Historical patterns + post-price impact tracking</li>
        <li><b>Options Strategy:</b> Multi-leg payoff builder with chart</li>
        <li><b>Market Anomalies:</b> Severity-classified anomaly detection</li>
        <li><b>Correlation Matrix:</b> 11-sector proxy with pairwise NaN handling</li>
        <li><b>Copilot Chat:</b> Conversational AI stock market assistant</li>
        <li><b>Brainstorming:</b> AI-generated investment idea exploration</li>
        <li><b>Strategy Lab:</b> Backtest trading strategies</li>
        <li><b>Crash Lab:</b> Extreme scenario "what-if" analysis</li>
      </ul>
    </details>
  </td>
  <td width="50%" valign="top">
    <h3>🔒 Enterprise-Grade Security</h3>
    <p>JWT-based authentication with role-based access control, rate limiting, and comprehensive error telemetry.</p>
    <ul>
      <li>bcrypt password hashing</li>
      <li>Per-IP rate limiting with per-endpoint configs</li>
      <li>CORS with env-configurable origins</li>
      <li>Security headers (X-Content-Type-Options, etc.)</li>
      <li>4 error telemetry tables (market, earnings, notifications, ideas)</li>
      <li>Correlation ID for request tracing</li>
      <li>Dead-letter queue for failed AI job retry</li>
    </ul>
  </td>
</tr>
</table>

<br>

---

## ✦ Architecture

<div align="center">
<pre>

 ┌─────────────────────────────────────────────────┐
 │                iOS SwiftUI App                  │
 │  Banknote Aesthetic  ·  7 Theme Presets         │
 │  WidgetKit  ·  Face ID  ·  Push Notifications   │
 └──────────────────────┬──────────────────────────┘
                        │ HTTPS / REST
                        ▼
 ┌─────────────────────────────────────────────────┐
 │            FastAPI Backend (6 workers)           │
 │  Auth · Routing · Rate Limit · CORS · Telemetry  │
 └──┬─────────┬──────────┬──────────┬──────────────┘
    │         │          │          │
    ▼         ▼          ▼          ▼
 ┌──────┐ ┌──────┐ ┌────────┐ ┌──────────────┐
 │Routers│ │Service│ │Repos   │ │  ML Engine   │
 │21 APIs│ │Layer │ │   + DB │ │  (port 8001) │
 │       │ │20 svc│ │        │ │ LightGBM/TRA │
 └───────┘ └──┬───┘ └──┬─────┘ └──────────────┘
              │         │
              ▼         ▼
 ┌──────────────────┐ ┌──────────────────┐
 │  AI Pipeline     │ │  PostgreSQL 18   │
 │  LangGraph · 8   │ │  + pgvector RAG  │
 │  agents · Claude │ │  + 24 ORM tables │
 │  DeepSeek · Haiku│ │  + Alembic migr. │
 └──────────────────┘ └──────────────────┘
              │
              ▼
 ┌─────────────────────────────────────────────┐
 │         Data Harvesting Layer                │
 │  YouTube · SEBI · News · NSE · AMFI · PK    │
 │  FinBERT · APScheduler · Celery Nightlies    │
 └─────────────────────────────────────────────┘

</pre>
</div>

### Backend Structure

| Layer | Location | Responsibility |
|-------|----------|---------------|
| **Controller** | `backend/routers/` (21 files) | HTTP validation, rate limiting, multiprocessing spawn |
| **Service** | `backend/services/` (20 files) | Business logic, LLM orchestration, computations |
| **Repository** | `backend/repositories/` + `database.py` | `get_session()` DB access, Alembic migrations |
| **Models** | `backend/models/db_models.py` | 24 centralized ORM classes (never duplicated) |
| **Config** | `backend/config/settings.py` | Sector PE maps, cache TTLs, rate limits |

### Router Inventory

| Router | Lines | Key Endpoints |
|--------|------:|---------------|
| `market.py` | 3,065 | Indices · Nifty history · Option chain · Filings · Sector PE · Institutional flow |
| `portfolio.py` | 2,936 | Holdings CRUD · Net worth · Performance charts · XLSX/PDF export · Trade journal |
| `analysis.py` | 1,600 | Stock analysis (v2 async) · SSE progress · Batch · Screener · Morning brief · Signals |
| `auth.py` | — | Login · Register · JWT token generation |
| `user.py` | — | Profile · Settings · Admin |
| `alerts.py` | — | Price alerts CRUD · Background poller |
| `notifications.py` | — | Device token · APNs push pipeline |
| `dashboard.py` | — | Admin web dashboard (Chart.js) |
| `harvester.py` | — | Content feed · Governance · Search · Trigger scrape |
| `stress_test.py` | — | Portfolio stress test · Job progress |
| `correlation.py` | — | Correlation matrix · Diversification score |
| `sector_rotation.py` | — | Multi-period quadrant · FII/DII flow |
| `earnings_surprise.py` | — | EPS surprise · Historical patterns |
| `nl_screener.py` | — | Natural language → SQL stock filter |
| `options_strategy.py` | — | Multi-leg payoff computation |
| `anomalies.py` | — | Market anomaly detection |
| `brainstorming.py` | — | AI investment idea generation |
| `copilot.py` | — | Conversational AI stock assistant |
| `strategy.py` | — | Trading strategy backtest |
| `health.py` | — | Health checks (zero-dependency + DB-backed) |

<br>

---

## ✦ AI Pipeline

<div align="center">
<pre>

┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│ Smart Cache  │────→│ Quantitative     │────→│   LangGraph Debate   │
│ Gate (0-100) │     │ Pre-Pipeline     │     │   8 Agent Dialectic  │
└──────────────┘     └──────────────────┘     └──────────┬───────────┘
                                                         │
                    ┌────────────────────────────────────┘
                    ▼
        ┌──────────────────────┐     ┌──────────────────┐
        │ Bull Researcher      │     │ Bear Researcher  │
        │ (bullish thesis)     │     │ (bearish thesis) │
        │                      │     │ 1.5× weight      │
        └──────────┬───────────┘     └────────┬─────────┘
                   │                          │
                   ▼                          ▼
        ┌─────────────────────────────────────────────┐
        │         Research Manager (synthesis)         │
        │                             +                │
        │   3 Debators (Aggr / Neutral / Conservative)  │
        └─────────────────────┬───────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │         Portfolio Manager                    │
        │  (weights bear findings 1.5×)                │
        └─────────────────────┬───────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  Claude Sonnet Final Reformatting            │
        │  → _normalize_response() → _ban_western_scale() │
        └─────────────────────────────────────────────┘

</pre>
</div>

### Smart Cache Gate

| Score | Status | Action |
|:-----:|--------|--------|
| 0–19 | **FRESH** | Return cached. No AI run. |
| 20–44 | **AGING** | Optional: DeepSeek Flash only |
| 45–69 | **STALE** | Full refresh: DeepSeek agents |
| 70–100 | **URGENT** | Full multi-agent: DeepSeek + Haiku/Sonnet |

### Language Model Tiers

| Tier | Model | Cost (input) | Role |
|:----:|-------|:------------:|------|
| 1 | `deepseek-chat` | $0.00014/1K | 8 bulk agents |
| 2 | `claude-haiku-4-5-20251001` | — | Research synthesis |
| 3 | `claude-sonnet-4-6` | — | Final reformatting |

<br>

---

## ✦ Quantitative Engines

| Engine | Lines | Description |
|--------|:-----:|-------------|
| **Stress Test** | 413 | 14 scenarios · Factor betas · EWMA shrinkage · Almgren-Chriss liquidity · 6 risk scores |
| **Correlation** | — | MPT mean-variance · 11-sector proxy · Pairwise NaN · Async 1hr TTL cache |
| **Sector Rotation** | — | Multi-period (1m/3m/6m/1y) · Momentum · FII/DII quadrant |
| **Factor Engine** | — | RSI · MACD · Bollinger · ATR · OBV · SMA/EMA crossovers · Volatility regimes |
| **Confidence Engine** | — | Signal agreement · Conformal prediction · KNN analogues · Bear asymmetry |
| **Sentiment Engine** | — | FinBERT (lazy-loaded, HuggingFace) |
| **Piotroski Score** | — | 9-point fundamental strength (profitability · leverage · efficiency) |
| **Options Engine** | — | Multi-leg payoff · CALL/PUT × LONG/SHORT · Full range simulation |
| **Alpha158** | — | Nightly ML feature computation · 158 technical/fundamental factors |
| **Earnings Surprise** | — | EPS surprise · Serial patterns · Post-price impact (1d/5d) |

<br>

---

## ✦ iOS App

<div align="center">
<pre>

┌─────────────────── Banknote Aesthetic ────────────────────┐
│  🏦 Aged charcoal backgrounds                              │
│  ✨ Security gold (#C8A84A) accents                        │
│  🔤 Georgia serif typography (engraved)                    │
│  🎯 EKPressStyle haptic buttons                            │
│  ─── GuillocheDivider section separators                   │
│  🌈 7 theme presets: ₹10/₹20/₹50/₹100/₹200/₹500/Dark      │
└────────────────────────────────────────────────────────────┘

</pre>
</div>

### Key Screens (60+)

| Category | Screens |
|----------|---------|
| **Core** | Home · Portfolio · Analysis · Search · Settings · Login · Sidebar |
| **Portfolio** | Holdings · Net Worth · Performance Charts · Trade Journal · Export |
| **Analysis** | Full View · Core Sections · Extreme Sections · Quant Inspector · Regime Warning · Loading/Error States |
| **Stock Profile** | Overview · Financials · Chart · News · Governance · Macro · Holders · Updates |
| **Analytics** | Stress Test · Correlation Matrix · Sector Rotation · Market Anomalies · Earnings Surprise · Options Strategy |
| **AI Tools** | NL Screener · Brainstorming · Copilot Chat · Strategy Lab · Crash Lab · Technical Momentum |
| **Content** | News & Multimedia · Expert Network · Pre-IPO Marketplace · Advisory Matrix · Dalal Street Consensus |
| **Education** | AI How It Works · Glossary · Tutorials · Onboarding · Feature Help · Term Definitions |

### Design System

```
Theme.canvas        │ #1C1A14  Aged charcoal
Theme.securityGold  │ #C8A84A  Security thread gold
Theme.bullGreen     │ #2D6A4F  Positive (NSE green)
Theme.bearRed       │ #C1292E  Negative (loss)
Theme.inkPrimary    │ #F5F0E8  Ivory text
Spacing             │ 8pt grid (2/4/6/8/12/16/20/24/32)
Typography          │ Georgia serif · Monospaced numbers · Small caps badges
```

<br>

---

## ✦ Database

24 ORM models centralized in `backend/models/db_models.py`; ORM model duplication forbidden.

### Key Tables

| Domain | Models |
|--------|--------|
| **User & Auth** | `User` · `DeviceToken` |
| **Portfolio** | `Portfolio` · `PortfolioValuationHistory` · `NetWorthLedger` · `TradeJournal` |
| **Analysis** | `AnalysisHistory` · `AnalysisJob` · `SignalEvent` · `PriceTarget` |
| **Content** | `NewsArticle` · `YouTubeVideo` · `AdvisorInsight` · `AdvisorBiography` · `TextAdvisoryInsight` |
| **Market** | `StockUniverse` (2000+) · `BlockDeal` · `FIIDIIFlow` · `MacroEvent` · `EarningsAlert` · `EarningsSurpriseHistory` · `MarketAnomaly` |
| **Risk** | `EquityRiskFactor` · `CovarianceMatrix` |
| **ML** | `Alpha158Feature` · `Alpha158Features` |
| **Telemetry** | `MarketErrorLog` · `EarningsErrorLog` · `NotificationErrorLog` · `IdeasErrorLog` |
| **Screening** | `PKScreenerSignal` |

### Migration Policy

All schema changes go through Alembic — never `ALTER TABLE` manually.

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic check            # verify no drift
```

<br>

---

## ✦ Quick Start

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Configure `.env`:
```env
ANTHROPIC_API_KEY=sk-...
GEMINI_API_KEY=...
OPENAI_API_KEY=sk-...        # for DeepSeek
DATABASE_URL=sqlite:///./stockapp.db
REDIS_URL=redis://localhost:6379/0
```

```bash
alembic upgrade head          # create/update tables
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### iOS

```bash
cd ios/StockApp
open stockme.xcodeproj
```

Configure the API URL in `URLSessionAPIClient.swift`, then build & run on iOS 17+.

### ML Engine (optional)

```bash
cd ml-engine
pip install -r requirements.txt
uvicorn ml_api:app --host 0.0.0.0 --port 8001
```

### Testing

```bash
cd backend
pytest tests/                         # full suite (103 files)
./tests/run_integrity_tests.sh        # integrity sub-suites
pytest tests/test_stress_test_engine.py
```

<br>

---

## ✦ Deployment

The production backend runs on a dedicated Fedora server:

| Config | Value |
|--------|-------|
| **API** | `https://api.nivesh.qzz.io` |
| **Server** | 16 CPUs · 14 GB RAM · Fedora |
| **Database** | PostgreSQL 18 + pgvector |
| **Workers** | 4 × uvicorn (prevent OOM) |
| **Timezone** | UAE (UTC+4) |
| **Schedule** | APScheduler for nightly harvests |

### Deploy

```bash
ssh saumyapatel@192.168.1.122
cd /home/saumyapatel/Desktop/nivesh
git pull --ff-only origin main
sudo systemctl restart nivesh
```

### Health

```bash
curl https://api.nivesh.qzz.io/ping    # zero-dependency
curl https://api.nivesh.qzz.io/health  # DB-backed
```

<br>

---

## ✦ Project Stats

```
📁 Backend:    378 Python files  │  21 routers  │  20 services
📱 iOS:        223 Swift files   │  60+ screens │  7 themes
🧪 Tests:      103 test files    │  6 test suites
🗄️  Database:  15 migration files │  24 ORM models
🔧 Scripts:    20+ shell/Python  │  3 Dockerfiles
📊 Stock Universe:  628+ tickers │  12 sectors
```

<br>

---

## ✦ License & Attribution

Built with ❤️ for the Indian investor. Powered by [LangGraph](https://langchain-ai.github.io/langgraph/), [FastAPI](https://fastapi.tiangolo.com/), [pgvector](https://github.com/pgvector/pgvector), and [Claude](https://anthropic.com).

<sub>_Nivesh is a personal project. Always consult a SEBI-registered financial advisor before making investment decisions. Past performance does not guarantee future returns._</sub>
