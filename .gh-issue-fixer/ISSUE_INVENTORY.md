#453: bug(backend): 10+ documented hardcoded values — SECTOR_PE_MAP, repo rate, yfinance circuit breaker, user agents, and more
#452: bug(backend): YouTube API quota consistently exceeded — 429 errors daily, advisor harvester dependent on yt-dlp fallback
#451: bug(repository): Direct commit to main bypasses AGENTS.md §6.4 PR workflow — 128 commits across 25 branches in 3 days shows process breakdown
#450: bug(infra): nivesh-harvester/ still has active service — stale duplicate despite backend route porting
#449: bug(backend): jugaad-data fails for all NSE tickers with JSON decode error — downstream BSE/NSE API change
#448: bug(backend): Redis cache set errors with Timestamp keys — pandas Timestamp objects used as dict keys
#447: bug(backend): HF_TOKEN not configured — unauthenticated embedding model downloads with rate limiting
#446: bug(backend): Production semaphore leak at server shutdown — 4 leaked loky semaphore objects
#445: bug(backend): Options scraper returns Unexpected response structure for all NSE tickers — downstream NSE API change
#444: chore(backend): 12 unmerged remote branches and 2 stale merged branches — branch hygiene decay
#443: bug(backend): Hardcoded DEMO API key in deterministic_dcf.py — FRED data uses unauthenticated tier
#442: chore(backend): OpenAPI docs endpoints may be disabled — /docs, /redoc, /openapi.json accessibility unknown
#441: bug(backend): 9 revert commits across branches indicate poor cross-branch synchronization
#440: bug(backend): orchestrator.py is 2283 lines — exteme maintenance burden, violates modular architecture
#439: bug(backend): ErrorTelemetrySystem — warning-level harvest failures not captured by error tracking
#438: bug(backend): Nightly digest may be under-reporting errors — only 4 top_movers errors on Jun 25, zero on Jun 26
#437: bug(repository): Direct commit to main bypasses AGENTS.md §6.4 PR workflow — 'auto update' commit 4b08451
#436: bug(backend): 130/169 endpoints across all routers lack response_model — massive OpenAPI documentation gap
#434: bug(backend): _log_token_usage() swallows all exceptions with bare except — silent token logging failure
#432: bug(backend): Advisor harvester launched 6x concurrently — start_scheduler() lacks re-init guard
#431: bug(backend): Nightly digest silently failed for 11 consecutive days (Jun 14-24) — MarketErrorLog query error
#430: bug(backend): Emoji stripping only applied to morning briefs — not to analysis results, news, or other AI-generated text
#429: bug(backend): ML engine URL hardcoded in ml_signal_service.py and alpha158_task.py — inconsistent configuration
#428: bug(infra): OpenCode scanner cron produces empty logs or truncated output — periodic monitoring blind spot
#427: bug(backend): config/prompts_config.py bare except: silently swallows all exceptions
#425: bug(repository): debug_harvester_sources.py tracked in backend/ — debug script in production code
#424: bug(backend): No global exception handler — unhandled 500 errors may expose stack traces and internal details
#423: bug(repository): 30+ duplicated commits across branches — cherry-pick/worktree duplication pollution
#422: bug(repository): 12 unmerged remote branches and 2 stale merged branches — branch hygiene decay
#421: bug(repository): Root-level empty database.db orphan file — 0-byte SQLite artifact
#419: bug(repository): 6 stale iOS Python backup files (6743 lines) tracked in git — codebase clutter
#418: bug(backend): Business logic violations in routers — LLM clients, yfinance, and DB queries used directly (recurrence)
#417: bug(backend): env.py disables compare_type, compare_server_default, and FK/UC detection — autogenerate blind spots
#416: bug(backend): Unprotected global mutable state in routers — race condition risk in user.py and market.py
#415: bug(backend): 11 revert commits across multiple branches — poor cross-branch synchronization
#414: bug(backend): No log rotation in production — advisor_harvester.log grows unbounded
#413: bug(backend): 20+ files exceed 500 lines — maintenance burden and crash risk (chkstk_darwin for iOS)
#412: bug(backend): API keys exposed in URL query parameters in harvester_expert.py and harvester_sebi.py
#411: bug(backend): Missing _SIGNAL_MAP — AGENTS.md architectural mandate not implemented
#410: bug(backend): String vs int user_id comparison unfixed (BUG-032/033) — 401 errors on portfolio and daily-action endpoints
#409: bug(deployment): update.sh (stale) conflicts with deploy_update.sh (active) — different deployment targets
#408: bug(deployment): deploy_update.sh uses git add -u instead of git add -A — new files never committed
#407: bug(backend): tests_suite/ missing __init__.py — pytest auto-discovery broken (6th recurrence of init.py pattern)
#406: bug(backend): Two ORM models missing Alembic migrations — MarketAnomaly and EarningsSurpriseHistory not tracked
#405: bug(backend): No ondelete cascade on any ForeignKey — orphaned data risk across 15 FK relationships
#404: bug(backend): DataHarvestingError defined twice in helpers.py — duplicate class silently overwrites first
#403: bug(backend): No response_model on 17 analysis endpoints — OpenAPI schema missing typed responses
#402: bug(backend): Swallowed exceptions with bare  in routers — silent failure in production
#401: bug(backend): assert statements in production code (15+ instances) — silently disabled with python -O
#400: bug(security): 12 router files lack authentication guards — unauthenticated access to sensitive endpoints
#399: bug(deployment): Docker HEALTHCHECK endpoint mismatch — claims DB check but returns simple liveness
#398: bug(deployment): No .dockerignore — Docker image bakes .env credentials, .git history, and token logs into production image
#397: bug(backend): Redis unavailable in production — dict fallback means no distributed caching
#396: bug(backend): datetime.now() without timezone in production code — naive datetime objects across 15+ files
#395: bug(backend): 2300+ line main.py with 160 imports — architectural single-file bottleneck
#394: bug(backend): .env.example significantly out of sync with actual .env — missing 8+ variables and 3 stale ones
#393: bug(backend): nest_asyncio dependency in correlation_engine indicates broken async architecture
#392: bug(backend): 4 leaked multiprocessing semaphore objects on every shutdown — resource tracker warning
#391: bug(infra): Unauthenticated HuggingFace requests — no HF_TOKEN set, slower model downloads with rate limits
#390: bug(backend): Dead code — celery_tasks.py completely unused (Celery not in requirements)
#389: bug(deployment): No TLS/SSL on production — credentials and API data sent over HTTP plaintext
#388: bug(backend): RAG ingestion runs on every server startup — 640 news articles re-embedded unnecessarily
#387: bug(backend): 6 SQLite database files across project — data fragmentation and deployment bloat
#386: bug(backend): Multiple tables missing UniqueConstraints — duplicate data risk in fundamentals tables
#385: bug(backend): Missing __init__.py in tests/ root prevents pytest discovery (5th recurrence)
#384: bug(backend): yfinance cache disabled via YF_CACHE_DIR=/dev/null — unnecessary API call overhead
#383: bug(deployment): nivesh.service says --workers 1 but server runs with --workers 4 — configuration drift
#382: bug(infra): CI pipeline still only checks agent guidance sync — no test, lint, type-check, or security scanning (recurrence of #292, #373)
#381: bug(backend): ORM models defined outside db_models.py in harvester_db.py — separate Base + separate DB, no Alembic management
#380: bug(backend): Unprotected global dict caches — race condition risk on concurrent requests
#379: bug(backend): Alembic migration chain broken — 2 migration .py files deleted, fresh DB provisioning impossible
#378: bug(backend): YouTube summary cache writes fail with NOT NULL constraint on url column
#377: bug(backend): Bhavcopy cron job fails daily — NSEArchives.bhavcopy_save() API changed in jugaad-data v0.33.1
#376: bug(backend): fundamentals/{ticker}/valuation returns 404
#375: bug(backend): /api/v1/fundamentals/* routes return 404 — path mismatch with tests
#374: bug(backend): OPTIONS preflight returns 405 instead of 200 on 110+ endpoints
