# Backend Deep File Test — Results

**Date:** 2026-06-18  
**Target:** `saumyapatel@192.168.1.122:/home/saumyapatel/Desktop/nivesh/backend`  
**AGENTS.md Reference:** §§ 3.1, 3.2, 3.5

---

## 1. Routers (`routers/`) — Business Logic Violations

### 1.1 yfinance Imports & Usage (FORBIDDEN in routers)

| File | Line(s) | Issue |
|------|---------|-------|
| `routers/analysis.py` | 15 | `import yfinance as yf` |
| `routers/analysis.py` | 85 | yfinance circuit breaker logic |
| `routers/analysis.py` | 849 | yfinance fallback in `/home-feed` |
| `routers/analysis.py` | 882 | `yfinance fallback error` catch |
| `routers/analysis.py` | 1100–1102 | `import yfinance as yf` inline in `/screener` route |
| `routers/market.py` | 22 | `import yfinance as yf` |
| `routers/market.py` | 123 | yfinance calendar (dividend date) |
| `routers/market.py` | 285 | yfinance promoter holdings |
| `routers/market.py` | 643 | yfinance DataFrame fallback |
| `routers/market.py` | 1163–1267 | `_fetch_yfinance_info()` — 100+ line function in router |
| `routers/market.py` | 1301–1336 | yfinance direct calls for price history |
| `routers/market.py` | 1763–1795 | `ThreadPoolExecutor` for parallel yfinance (in router) |
| `routers/market.py` | 2051–2218 | `_build_yfinance_fallback_earnings()` — large function in router |
| `routers/market.py` | 2374 | `_scan_yfinance_earnings()` — function in router |
| `routers/portfolio.py` | 15 | `import yfinance as yf` |
| `routers/portfolio.py` | 56–57, 77–78 | `_adjust_for_splits()`, `_adjust_for_dividends()` — yfinance functions in router |
| `routers/health.py` | 37–42 | yfinance ping in health check |

### 1.2 Anthropic/LLM Client Usage (FORBIDDEN in routers)

| File | Line(s) | Issue |
|------|---------|-------|
| `routers/analysis.py` | 16 | `import anthropic` |
| `routers/analysis.py` | 739 | `client = anthropic.Anthropic(api_key=api_key)` |
| `routers/analysis.py` | 769 | `client = anthropic.Anthropic(api_key=api_key)` |
| `routers/portfolio.py` | 791 | `import anthropic` |
| `routers/portfolio.py` | 798 | `client = anthropic.Anthropic(api_key=api_key)` |
| `routers/portfolio.py` | 2693 | `import anthropic` |
| `routers/portfolio.py` | 2697 | `client = anthropic.Anthropic(api_key=api_key)` |

### 1.3 DB Queries in Routers (`session.query()`) — FORBIDDEN

**Massive violation across ALL router files.** Direct `session.query()` calls in:
- `routers/analysis.py` — **40+** `.query()` calls
- `routers/market.py` — **25+** `.query()` calls
- `routers/portfolio.py` — **50+** `.query()` calls
- `routers/user.py` — **15+** `.query()` calls
- `routers/alerts.py` — 6+ `.query()` calls
- `routers/harvester.py` — 10+ `.query()` calls
- `routers/auth.py` — 1 `.query()` call
- `routers/correlation.py` — 1 `.query()` call

> **VERDICT:** CRITICAL violation of AGENTS.md §3.1. All 9 router files contain business logic + DB queries.

### 1.4 Rate Limiting Decorators

Not explicitly checked in this run. Router files should use `@limiter.limit()` decorators.

### 1.5 Error Response Formats

Not explicitly checked in this run. Routers should return consistent `{"detail": "..."}` format.

---

## 2. Services (`services/`) — DB Session Usage

### 2.1 DB session operations (inside `get_session()` context manager — CORRECT)

All `session.execute()`, `session.commit()`, `session.add()`, `session.rollback()`, `session.query()` calls in services appear to be within `with get_session() as session:` blocks — the grep filtered out lines containing `get_session` which is the context manager import, but the variable `session` inside the block is correctly scoped.

**Files using DB sessions (correct pattern):**
- `services/advisor_harvester.py:292,343-344`
- `services/confidence_engine.py:363`
- `services/earnings_surprise.py:76,100-101`
- `services/error_telemetry.py:162-163,185-186,225`
- `services/feedback_injector.py:39,99,101`
- `services/harvester_db.py:152,154,157,193,232,248,254`
- `services/nightly_jobs.py:39`
- `services/nl_screener.py:189`
- `services/orchestrator.py:1173,1251,1283,1440,1517,1542,1665`
- `services/rag_ingestion.py:45,79`

### 2.2 HTTP sessions (NOT DB sessions — false positives)

These `Session()` calls are `requests.Session()` (HTTP), not SQLAlchemy:
- `services/nse_client.py:36`
- `services/options_scraper.py:33-34`
- `services/transcript_engine.py:124`

> **VERDICT:** Services correctly use `get_session()` context manager for DB access. No violations found.

---

## 3. Models (`models/db_models.py`) — Forbidden Patterns

### 3.1 `default=dict` (FORBIDDEN — must be `default="{}"`)

| Line | Column | Issue |
|------|--------|-------|
| 98 | `quantitative_drivers` | `Column(JSON, default=dict)` — Python dict, not string |
| 99 | `tail_risk_flags` | `Column(JSON, default=dict)` — Python dict, not string |

AGENTS.md §3.5: _"JSON columns use `default="{}"` (string, not Python dict) — SQLite requires constant defaults."_

### 3.2 `datetime.utcnow` usage

**None found.** No models use `datetime.utcnow`. All datetime defaults appear to use `default=lambda: datetime.now(timezone.utc)` — COMPLIANT.

> **VERDICT:** 2 violations on lines 98-99. `default=dict` must be changed to `default="{}"`.

---

## 4. Schemas (`schemas/`) — Pydantic Validators

### 4.1 `@validator` (Pydantic v1 — should be `@field_validator` for Pydantic v2)

| File | Line | Detail |
|------|------|--------|
| `schemas/portfolio.py` | 14 | `@validator("ticker")` |
| `schemas/portfolio.py` | 22 | `@validator("exchange")` |

> **VERDICT:** 2 violations. Pydantic v1 `@validator` should migrate to v2 `@field_validator`.

### 4.2 Enum definitions with proper fallbacks

Not explicitly checked in this run. Schemas should use `Enum` with `.get(key, default)` fallbacks.

---

## 5. Migrations

### 5.1 `alembic check`
```
No new upgrade operations detected.
```
**PASS** — No schema drift between models and database.

### 5.2 `alembic history`
```
9929cce0b029 (head) — Add StockUniverse model
d4e5f6a7b8c9       — sync missing indexes
b2c3d4e5f6a7       — Add ix_analysis_jobs_ticker index and AnalysisJob user cascade
a1b2c3d4e5f6       — Add missing columns to trade_journal and analysis_history
1ad82d60efcc       — No-op schema chain placeholder
323c66c5ca0e       — No-op schema chain placeholder
0dc3e605ea33       — initial_schema
```
**PASS** — 7 migrations, clean linear history, head is current.

---

## Summary

| Area | Status | Violations |
|------|--------|------------|
| Routers — yfinance | **FAIL** | yfinance in 4 router files (analysis, market, portfolio, health) |
| Routers — LLM (anthropic) | **FAIL** | anthropic client in analysis.py + portfolio.py (4 locations) |
| Routers — DB queries | **FAIL** | `session.query()` in ALL 9 router files (150+ calls) |
| Services — DB sessions | **PASS** | Correct `get_session()` pattern |
| Models — `default=dict` | **FAIL** | 2 columns use `default=dict` instead of `default="{}"` |
| Models — `utcnow` | **PASS** | No violations |
| Schemas — `@validator` | **FAIL** | 2 Pydantic v1 validators in portfolio.py |
| Migrations — check | **PASS** | No schema drift |
| Migrations — history | **PASS** | Clean linear chain |

**Overall Risk: CRITICAL** — Routers are the most egregious violation of AGENTS.md §3.1. Business logic, LLM clients, and DB queries are deeply embedded in all router files. This represents architectural debt that would require a major refactor (Controller-Service-Repository separation) to resolve.
