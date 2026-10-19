# Feature package data-eod-mirror: Postgres daily_prices mirror, gap-fill request, display-gated accessors and backfill CLI

Cluster: data (Data foundation); area: backend
Features covered: I15

## Files (create or modify)
- backend/services/research/client.py
- backend/services/eod_prices.py
- backend/scripts/backfill_daily_prices.py
- backend/tests/test_eod_prices.py

## Dependencies
- Feature packages (integrated before you start): data-flags, data-instruments, data-ml-eod-api, data-schema
- Declared in the plan: data-flags, data-schema, data-instruments, data-ml-eod-api, ENG:be-ingest-jobs, FIX:DB-24. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
client.py (landed): add two methods on the existing _request.
- eod(market_date) -> dict | None: GET /eod/{iso}, ok=(200, 404), timeout 30. 404 returns None. Timeouts and 5xx raise MLEngineUnavailable. Never log the key.
- marketdata_sync(through) -> str: POST /marketdata/sync {'through': iso}, ok=(202, 409). Returns 'started' or 'busy'.

New eod_prices.py:
- PriceFact: frozen dataclass (close Decimal, trade_date, source, instrument_id).
- _last_due(now): the IST date if the IST time is >= 21:30, else the previous weekday (core.timeutil).

mirror_date(d, *, client=None) -> int
- payload = client.eod(d). Return 0 when it is None, status != 'ok', or it has fewer than 1000 rows (log a WARNING).
- In one get_session():
  - ids = {} created inside this call, so nothing is cached across dates (review critical).
  - Per row: key = entity_id or isin. If uncached, upsert_eq_identity(session, symbol, isin, entity_id, seen_on=d, source='bhavcopy') and cache inst.id. Its monotonic rule and idempotent aliases make the ascending re-pull safe.
  - DELETE that date's 'nse_bhavcopy' rows, then bulk insert: Decimal(str(x)); skip close None or <= 0; event and quality_flags become None when empty.
  - If NIFTY50 is present: get_or_create_index and replace its (d, 'yfinance') row.
  - Commit and return the number of rows written.

mirror_recent(*, client=None, now=None) -> dict
- Flag off: {'skipped':'flag_off'}.
- cfg = services.research.config.CONFIG, read at call time. No ml_engine_api_key: {'skipped':'ml_engine_unconfigured'}.
- last_due = _last_due(now).
- If cfg.mode == 'off': sync = client.marketdata_sync(last_due). Otherwise sync = 'skipped:research_runs' (research runs gap-fill themselves). With research off, an evening's data lands by the 07:40 run.
- mirror_date each calendar day from last_due - 14 to last_due, ascending.
- MLEngineUnavailable stops the loop: {'error':'ml_engine_unavailable','sync','dates_written'}.
- Otherwise return {'sync','dates_written','rows'}.

get_close(symbol=None, *, isin=None, on=None, max_age_days=7, for_display=True) -> PriceFact | None
- Resolve with instruments.resolve; on defaults to the IST date.
- EQ/INDEX: if for_display and data_flags.enabled('data_eod_display') is off, return None (review). Else the latest row in [on - max_age_days, on] without 'suspect' in quality_flags.
- MF (always served): the latest row in the window, else MutualFund.nav/nav_date inside the window with source 'amfi_latest'.
- Docstring: callers keep their existing source on None and label what they show.

get_closes(identifiers, *, on=None, max_age_days=7, for_display=True) -> dict: an identifier matching ^IN[A-Z0-9]{10}$ is an ISIN, otherwise a symbol; one query; keyed by the caller's strings.

index_close(code='NIFTY50', on=None, max_age_days=7, for_display=True).

No corporate_factor.

scripts/backfill_daily_prices.py:
- --start and --end; end >= start; at most 4000 days.
- Calendar-day loop over mirror_date with one client; print counts and a total.
- Ignores the flag and never requests a sync (older ranges come from the engine's 'store backfill').
- Exit 1 without a key.

Do not touch harvest_worker.py or nse_data_provider.py.

## Acceptance checks
PYPARSE and PYRIGHT clean.

tests/test_eod_prices.py (fake client, conftest SQLite) covers:
- 1,200 rows plus NIFTY50 are written, with event and instruments
- a rerun is idempotent
- None, no_session or 999 rows write nothing
- rename regression (review critical): days 1-4 carry OLD and days 5-10 carry NEW, same entity and ISIN. After mirror_recent the symbol is NEW with exactly one OLD alias; a second mirror_recent raises no IntegrityError and adds no aliases
- mirror_recent returns flag_off and ml_engine_unconfigured; calls marketdata_sync only when CONFIG.mode is 'off'; stops on MLEngineUnavailable
- get_close honours max_age_days, skips suspect rows and resolves an alias. An EQ lookup returns None with display off and for_display=True, and the row with for_display=False. The MF ISIN fallback to mutual_funds.nav works either way
- get_closes accepts a symbol and an ISIN together
- the CLI rejects end < start

## Cluster spec
docs/feature-specs/spec_data.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
