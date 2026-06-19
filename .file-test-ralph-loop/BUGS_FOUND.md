# Bugs Found During 20-Loop File Test

## P0 - Production Critical (3)

| Bug ID | File(s) | Description | Fix Applied |
|--------|---------|-------------|-------------|
| B001 | backend/routers/market.py:2543,2591 | Unprotected `/api/v1/earnings/alerts` POST/DELETE — no auth, anyone can create/delete alerts for any user | Added `Depends(require_auth)` |
| B002 | backend/routers/portfolio.py:2529 | Unprotected `/trade-journal/{user_id}/stats` — leaks trade journal data | Added `Depends(require_auth)` |
| B003 | backend/services/staleness.py:63-64 | Staleness scoring inversion — 3-7 day old analyses scored +45 while 8-14 day scored only +10 (older = cheaper = wasted AI credits) | Fixed tier ordering |

## P1 - High Impact (5)

| Bug ID | File(s) | Description | Fix Applied |
|--------|---------|-------------|-------------|
| B004 | backend/models/db_models.py:98-99 | `default=dict` on JSON columns (not `default="{}"`) — SQLite mute corruption under concurrent writes | Fixed |
| B005 | backend/routers/portfolio.py:307,374,435 | 3 bare `except:` clauses (catches KeyboardInterrupt, SystemExit) | Changed to `except Exception:` |
| B006 | backend/routers/analysis.py:399 | Bare `except:` in ASM/GSM lookup | Changed to `except Exception:` |
| B007 | backend/services/nse_client.py:44 | Bare `except: pass` — swallows all NSE session errors silently | Changed to `except Exception: pass` |
| B008 | backend/main.py:1466 | Invalid `\B` escape in JS regex (corrupts IN₹ formatter in dashboard) | Fixed to `\\B` |

## P2 - Medium (4)

| Bug ID | File(s) | Description | Fix Applied |
|--------|---------|-------------|-------------|
| B009 | backend/main.py, routers/market.py, routers/user.py, 34 files | 110+ `datetime.utcnow()` calls — deprecated in Python 3.12, removed in 3.14 | All replaced with `datetime.now(timezone.utc)` |
| B010 | backend/tradingagents-core/cli/utils.py:461 | Invalid `\`` escape in docstring | Fixed |
| B011 | backend/migrations/versions/9929cce0b029 | Migration tries to create already-existing tables (covariance_matrices, stock_universe) | Stamped as applied |
| B012 | backend/routers/market.py:1, portfolio.py:13 | Missing `Depends` import for auth dependencies | Added |

## P3 - Low (6)

| Bug ID | File(s) | Description | Fix Applied |
|--------|---------|-------------|-------------|
| B013 | backend/tests/test_job_dedup.py:36 | `datetime.now(timezone.utc)` with only `import datetime` (needs `datetime.timezone.utc`) | Fixed |
| B014 | iOS AnalysisScreen.swift:765,932 | `GeometryReader` inside ScrollView — potential view tree corruption per §6.6 | Not fixed (no xcodebuild) |
| B015 | iOS HomeScreen.swift (~3089 lines), PortfolioScreen.swift (~2447 lines) | Massive files with inline `func -> some View` — chkstk_darwin crash risk | Not fixed |
| B016 | iOS 21 force-unwraps (3 high-risk on empty arrays) | Crash potential on edge data | Not fixed |
| B017 | iOS ~250+ non-Theme.spacing padding violations | AGENTS.md §2.2 non-compliance | Not fixed |
| B018 | iOS ~15 VStack-inside-ScrollView (should be LazyVStack) | Performance issue | Not fixed |

## Status Summary
- **Fixed:** 13 bugs
- **Not fixed (no xcodebuild):** 5 iOS bugs
- **Total found:** 18
