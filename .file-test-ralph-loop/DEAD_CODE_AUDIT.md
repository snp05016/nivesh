# Dead Code Audit — Nivesh Backend

**Date:** 2026-06-18  
**Scope:** `/Users/saumya/Desktop/nivesh/backend/` (excluding `.venv/`, `__pycache__/`, `migrations/`, `tradingagents-core/`)  
**Methodology:** PyCompile, AST analysis, cross-reference grep  

---

## 🔴 CRITICAL / HIGH Severity

### 1. Bare `except:` Clauses (Silent Error Swallowing)

AGENTS.md §1.3 (Karpathy) forbids bare `except:`. These 5 instances catch `KeyboardInterrupt`, `SystemExit`, and hide all errors:

| File | Line | Pattern | Context |
|------|------|---------|---------|
| `routers/portfolio.py` | 307 | `except:` | yfinance price fetch in CAGR endpoint |
| `routers/portfolio.py` | 374 | `except:` | yfinance price fetch in stress-test endpoint |
| `routers/portfolio.py` | 435 | `except: pass` | `_nse_session()` silently swallows NSE connection errors |
| `routers/analysis.py` | 399 | `except:` | ASM/GSM surveillance list fetch |
| `services/nse_client.py` | 44 | `except: pass` | `_nse_session()` silently swallows NSE connection errors |

**Fix:** Replace with `except Exception:` (or specific exception type) and at minimum log the error.

---

### 2. Dead Database Tables (Defined, Never Queried)

Two ORM models in `models/db_models.py` have **zero references** in any production code, service, or router outside of the model definition itself and the Alembic migration:

| Table | Model Class | References | Risk |
|-------|-------------|------------|------|
| `covariance_matrices` | `CovarianceMatrix` | 0 (only db_models.py + migration) | Orphan table consuming schema space |
| `equity_risk_factors` | `EquityRiskFactor` | 0 (only db_models.py + migration) | Orphan table consuming schema space |

Neither table is `session.query()`'d, imported, or referenced in any service, router, repository, or script. The migration `9929cce0b029_add_stockuniverse_model.py` creates and drops them — they are vestigial.

**Recommendation:** Either implement the stress-test covariance engine that uses them, or remove them with a new Alembic migration.

---

### 3. Completely Dead Files (Never Imported by Production Code)

| File | Lines | Description |
|------|-------|-------------|
| `services/celery_tasks.py` | 43 | Celery task definitions — never imported. 0 references outside itself. |
| `middleware/request_log.py` | — | Request logging middleware — never imported |
| `middleware/security_headers.py` | — | Security headers middleware — never imported |
| `middleware/__init__.py` | 1 | Empty init |

The `middleware/` package is a **duplicate** of inline classes `_RequestLogMiddleware` and `_SecurityHeadersMiddleware` defined directly in `main.py:299-340`. The middleware package is dead code.

**Relevant files:**
- `main.py:299` — `class _RequestLogMiddleware(BaseHTTPMiddleware)` (inline, active)
- `main.py:317` — `class _SecurityHeadersMiddleware(BaseHTTPMiddleware)` (inline, active)
- `middleware/request_log.py` — dead duplicate
- `middleware/security_headers.py` — dead duplicate

---

### 4. Duplicate Class: `DataHarvestingError`

Defined in **two** places:
- `helpers.py` (used by routers)
- `main.py:275` (used by the exception handler at `main.py:350`)

**Risk:** Only `main.py`'s definition is used by the `@app.exception_handler`. If `helpers.py` ever diverges, you get two different exception classes that won't match. Additionally, `routers/portfolio.py` and `routers/market.py` import `DataHarvestingError` from `main`, not `helpers`.

---

### 5. Duplicate Function: `_nse_session()`

Defined in **two** places:
- `services/nse_client.py:27` (the "canonical" version with User-Agent rotation)
- `routers/portfolio.py:424` (a copy with static User-Agent, bare `except: pass`)

The router copy is stale and less robust. `services/nse_client.py` should be the single source of truth.

---

### 6. Duplicate Function: `_get_asm_gsm_lists()`

Same pattern — defined inline in `routers/portfolio.py` ~line 439 and in `services/nse_client.py:52`. The service version is the canonical one.

---

## 🟡 MEDIUM Severity

### 7. Duplicate Imports in `main.py`

| Line(s) | Import | Issue |
|---------|--------|-------|
| 5 + 6 | `import time` AND `import time as _time` | `_time` is never used independently of `time` |
| 17 + 26 | `from dotenv import load_dotenv` | Duplicated — line 17 loads, line 26 re-imports |

---

### 8. Unused Imports in `main.py`

At least 20+ imports in `main.py` are never referenced after import:

- `sys` (line 2)
- `hashlib` (line 4)
- `io` (line 7)
- `date` (line 8) — only `datetime` is used
- `timedelta` (line 8)
- `Optional` (line 10)
- `_dcache_get`, `_dcache_set`, `_dcache_stats` (line 22) — imported but not called directly (used indirectly through dashboard?)
- `load_dotenv` (line 26) — duplicate
- `multiprocessing` (line 27) — imported but multiprocessing logic is in routers/analysis.py
- `BackgroundTasks` (line 30) — not used
- `StreamingResponse` (line 34) — not used
- `BaseModel` (line 36), `validator` (line 36) — not used directly
- `_Optional` (line 37), `_List` (line 37), `_BaseModel` (line 38) — not used
- `yf` as `yfinance` alias (line 39) — not used in main.py body
- `openpyxl` (line 42), `PatternFill` (line 43), `XLFont` (line 43), `Alignment` (line 43) — used in export endpoints?
- `FPDF` (line 52) — conditionally imported
- `save_analysis`, `get_recent_analyses`, `get_user_by_credentials`, `get_analysis_for_date`, `get_all_ticker_history`, `AdvisorInsight`, `PKScreenerSignal`, `MacroEvent`, `create_access_token`, `verify_access_token`, `is_admin`, `promote_initial_admins` (line 56) — many are used by routers, not by main.py
- `Depends` (line 268) — not used directly
- `get_current_user_id`, `require_auth`, `require_admin` (line 269) — imported but not directly called (used by routers)

---

### 9. Duplicate Tickers in `_NSE_DIRECTORY` (main.py)

Two tickers appear **twice** with identical data:
- `TITAN` — lines 519 and 706
- `ZOMATO` — lines 550 and 764

**Impact:** Wastes memory. The `_NSE_DIR_INDEX` derived from it will have duplicate entries.

---

### 10. Schema Architecture Duplication

| File | Lines | Used By |
|------|-------|---------|
| `schemas.py` (root) | 89 | `main.py` |
| `schemas/__init__.py` | 29 | Tests |
| `schemas/auth.py` | 14 | — |
| `schemas/market.py` | 76 | — |
| `schemas/portfolio.py` | 105 | Tests (e.g., `test_database_integrity_fixes.py`) |

Two competing schema systems exist. The `schemas/` package is primarily used by tests, while `schemas.py` (root) is used by `main.py`. These should be consolidated.

---

### 11. SyntaxWarning in `main.py:1466`

Invalid escape sequence `\d` in inline JavaScript string. Should be `\\d` or use a raw string.

```
function fmtINR(n){...n.toFixed(0).replace(/\\B(?=(\d{3})+(?!\d))/g,',')...}
                                              ^^^^
```

---

### 12. Rate Limiter Duplication

| File | Description |
|------|-------------|
| `core/rate_limiter.py` | The canonical rate limiter — imported by `helpers.py` |
| `services/rate_limiter.py` | Another rate limiter — only referenced in test `test_01_imports_circular.py` |

`services/rate_limiter.py` appears to be a dead/legacy file.

---

## 🟢 LOW Severity / Information

### 13. Standalone Test/Scratch Files in `backend/` Root

These 13 test files and 8 scratch files live at the project root instead of under `tests/`. They are not imported by any production code:

**Test files (should be in tests/):**
- `test_analyze_diagnostic.py`
- `test_analyze_uncached.py`
- `test_cache.py`
- `test_claude.py`
- `test_deep_scan.py`
- `test_deepseek_claude.py`
- `test_new_endpoints.py`
- `test_nse.py`
- `test_run.py`
- `test_watchlist_db.py`
- `test_watchlist.py`
- `test_yf_history.py`
- `test_yf_info.py`

**Scratch/development files:**
- `scratch_dividend.py`
- `scratch_item38.py`
- `scratch_item38_router.py`
- `scratch_item39.py`
- `scratch_item49.py`
- `scratch_middleware.py`
- `scratch_yf_test.py`
- `debug_harvester_sources.py`

---

### 14. Standalone Scripts (Not Part of the Application)

- `run_advisor_harvest.py` — referenced only by its own docstring
- `populate_portfolio.py` — referenced only by its own docstring

These are runnable scripts that are not imported by the application — they are fine as-is but should be in a `scripts/` directory.

---

### 15. Import Check: `services.scraper` — `scraping` is Properly Used

Verified that `services/scraper.py` IS actively used by `main.py`, `routers/market.py`, and multiple test files. This is NOT dead code. Same for `services/options_scraper.py`.

---

## Summary Table

| # | Finding | Severity | Action Required |
|---|---------|----------|-----------------|
| 1 | 5 bare `except:` clauses | 🔴 HIGH | Replace with `except Exception:` + logging |
| 2 | `CovarianceMatrix` + `EquityRiskFactor` dead tables | 🔴 HIGH | Implement or remove with migration |
| 3 | `celery_tasks.py` + `middleware/` dead files | 🔴 HIGH | Remove or integrate |
| 4 | Duplicate `DataHarvestingError` class | 🔴 HIGH | Consolidate to one location |
| 5,6 | Duplicate `_nse_session()` and `_get_asm_gsm_lists()` | 🔴 HIGH | Consolidate to `services/nse_client.py` |
| 7 | Duplicate imports in `main.py` | 🟡 MEDIUM | Clean up |
| 8 | 20+ unused imports in `main.py` | 🟡 MEDIUM | Remove or move to router files |
| 9 | Duplicate tickers `TITAN`, `ZOMATO` in directory | 🟡 MEDIUM | Deduplicate |
| 10 | Schema architecture split | 🟡 MEDIUM | Consolidate `schemas.py` + `schemas/` |
| 11 | SyntaxWarning in `main.py:1466` | 🟡 MEDIUM | Fix escape sequence |
| 12 | `services/rate_limiter.py` duplicate | 🟡 MEDIUM | Remove dead file |
| 13 | 21 stray test/scratch files in root | 🟢 LOW | Move to `tests/` or delete |
| 14 | Standalone scripts in root | 🟢 LOW | Move to `scripts/` |

---

## Compilation Status

All non-test project files compiled successfully with `py_compile` (excluding `tradingagents-core/` which was excluded from scan). Note: The `SyntaxWarning` in `main.py:1466` is a warning, not an error — it will still compile.
