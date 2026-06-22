# Nivesh — Credits & Dependencies

> Libraries, models, data sources, and research this project builds on.

---

## Backend Python Packages

| Package | Role |
|---------|------|
| **FastAPI** | ASGI web framework; all 21 routers and middleware |
| **Uvicorn** | ASGI server; 4 workers in production |
| **SQLAlchemy** | ORM layer; 24 centralized models in db_models.py |
| **Alembic** | Database migration tool; 9 migration files |
| **Pydantic** | Request/response validation; all Pydantic v2 models |
| **LangGraph** | Multi-agent orchestration graph; 8-agent debate pipeline |
| **LangChain Anthropic** | LangChain integration for Claude models |
| **anthropic** | Official Anthropic Python SDK; Claude Haiku and Sonnet calls |
| **httpx** | Async HTTP client; ML engine calls, external APIs |
| **yfinance** | Yahoo Finance data client; fallback OHLCV source |
| **jugaad-data** | Primary NSE data source; OHLCV, corporate actions, FII/DII |
| **polars** | Fast columnar data processing in ml-engine |
| **numpy** | Numerical computing; factor computations |
| **torch** | PyTorch; TRA (Temporal Routing Adaptor) model |
| **lightgbm** | Gradient-boosted tree model for Alpha158 cross-sectional ranking |
| **onnxruntime** | ONNX model inference (optional export path) |
| **celery** | Task queue; nightly Alpha158 materialization task |
| **apscheduler** | In-process scheduler; nightly harvest and snapshot jobs |
| **orjson** | Fast JSON serialization (used in orchestrator.py when available) |
| **bcrypt** | Password hashing for user authentication |
| **python-jose** | JWT token generation and verification |
| **python-dotenv** | .env loading at startup and in subprocess workers |
| **transformers** | HuggingFace transformers; FinBERT sentiment model |
| **sentence-transformers** | MiniLM embeddings for RAG ingestion |
| **chromadb** | Local vector store for RAG (dev); pgvector in production |
| **pgvector** | PostgreSQL vector extension for semantic search (prod) |
| **openpyxl** | Portfolio Excel (XLSX) export |
| **fpdf2** | Portfolio PDF export |
| **aiohttp** / **requests** | HTTP clients for various scrapers |
| **beautifulsoup4** | HTML parsing for web scrapers |
| **redis** | Cache backend (optional; disk_cache.py is the primary L2) |

---

## AI Models Used

| Model | Provider | Tier | Role |
|-------|----------|:----:|------|
| `deepseek-chat` | DeepSeek (OpenAI-compatible API) | 1 | 8 bulk analysis agents — Bull/Bear researchers, 3 debaters, Trader, Research Manager, Portfolio Manager |
| `claude-haiku-4-5-20251001` | Anthropic | 2 | Research Manager synthesis and Tier 2 calls |
| `claude-sonnet-4-6` | Anthropic | 3 | Final analysis reformatting pass only |

Cost design: Tier 1 = $0.00014/1K input tokens. Tier 2 and 3 called only when staleness score >= 45.

---

## ML Research

| Research | Attribution |
|----------|-------------|
| **Temporal Routing Adaptor (TRA)** | Architecture adapted from Microsoft Research Qlib: "Temporal Routing Adaptor for Dynamic Stock Market Pattern Modeling" — `ml-engine/models/tra.py` |
| **Alpha158 Feature Set** | 158 technical/fundamental factors from the Qlib Alpha158 benchmark dataset — extracted and reimplemented in `ml-engine/pipeline/feature_computer.py` and `ml-engine/config.py` |
| **Microsoft Qlib** | Research platform reference; Qlib itself is NOT imported in production. The Alpha158 feature formulas and TRA architecture are adapted and run independently in the ml-engine microservice under Python 3.10. |
| **RD-Agent** | Microsoft RD-Agent experimentation framework; used in the air-gapped `ml-engine/sandbox/` environment for research experiments only |

---

## iOS

| Technology | Role |
|-----------|------|
| **SwiftUI** | Declarative UI framework; all 60+ screens |
| **Swift Charts** | Apple's native charting framework; price charts, performance charts |
| **WidgetKit** | Home screen widgets for portfolio and market data |
| **EventKit** | Earnings calendar reminders |
| **SFSpeechRecognizer** | Voice search for stock tickers |
| **UserNotifications / APNs** | Push notifications for price alerts |
| **LocalAuthentication** | Face ID / Touch ID biometric locking |
| **SafariServices** | In-app browser for news and filings links |
| **Combine** | Reactive state management |
| **Banknote Aesthetic** | Custom design system: Theme.swift, BanknoteDesignSystem.swift, GuillocheDivider, EKPressStyle, HapticManager — original work |

---

## Data Sources

| Source | Usage |
|--------|-------|
| **NSE India** | Primary market data: OHLCV, corporate actions, FII/DII institutional flows, bulk/block deals, option chains |
| **jugaad-data** | Open-source Python library wrapping NSE APIs |
| **Yahoo Finance (yfinance)** | Fallback OHLCV data; international stocks |
| **SEBI** | SEBI filings and corporate governance disclosures (harvested via harvester_sebi.py) |
| **YouTube** | Financial advisor videos, transcripts, and stance extraction (youtube_harvester.py, expert_youtube_harvester.py) |
| **AMFI** | Mutual fund NAV data |
| **PKScreener** | Open-source technical screening signals (pkscreener_runner.py) |
| **HuggingFace** | FinBERT model for news sentiment scoring |

---

## Infrastructure

| Component | Technology |
|-----------|-----------|
| **Web Server** | Uvicorn (ASGI), 4 workers in production |
| **ML Engine Container** | Docker (Python 3.10 base image) |
| **Production Server** | Fedora Linux, 16 CPUs, 14 GB RAM |
| **Database (dev)** | SQLite via SQLAlchemy |
| **Database (prod)** | PostgreSQL 18 + pgvector extension |
| **Migrations** | Alembic with render_as_batch=True for SQLite compatibility |
| **Process Isolation** | Python multiprocessing.Process for heavy AI analysis jobs |
| **Scheduling** | APScheduler (AsyncIOScheduler) + Celery (nightly Alpha158) |
| **Service Management** | systemd (backend), Docker (ml-engine) |
| **Monitoring** | Custom admin dashboard at /dashboard; token usage log at token_log.jsonl; 4 telemetry ORM tables |

---

## License and Attribution

Nivesh is a personal project. All financial analysis is for educational purposes only.

- Always consult a SEBI-registered financial advisor before making investment decisions.
- Past performance does not guarantee future returns.
- Alpha158 formulas and TRA architecture are adapted from Microsoft Research Qlib (MIT License).
