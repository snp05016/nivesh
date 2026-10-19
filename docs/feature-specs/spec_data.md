# Cluster 'data': Data foundation

Roadmap: docs/investigations/2026-10-08_deep-audit/EXPANSION_ROADMAP.md

## Coverage and council handling

| Feature | Status | Verdict handling | Evidence |
|---|---|---|---|
| 23 I16 AMFI mutual-fund universe and NAV history | partial | Simplify, built as the smaller version: one scheduled harvester, no mocks, and NAV history recorded from today with no backfill. Also added, because the list is unusable without them once the mocks are gone: universe upsert from the AMFI category and AMC headers, Direct and Growth by default, category, sub-category and AMC filters, server paging, and no performance sort. Not built: the SIP route (iOS computes it), TER, AUM and riskometer (other sources), and computed 1Y/3Y/5Y returns. Returns are dropped because history starts at launch, so they would stay null for a year, and single-fund returns without a benchmark add SEBI/AMFI presentation exposure. Flag data_mf_universe, default ON. | Fix track: CMON-13 (w3-06, partly landed at HEAD 262042f: SAMPLE_SCHEME_CODES and is_sample exist) makes get_nav_history return [], drops 3Y/5Y and labels sample rows. FAKE-06 (w3-07) seeds mocks only when DEMO_MODE and purges them from prod. ARCH-19 (p3-04, not landed) deletes both unreferenced amfi_nav_harvester copies. ARCH-17 (not landed) moves the router from /api/mutual-funds to /api/v1/mutual-funds and keeps an alias. After the fix track the prod MF catalogue is empty and there is no NAV feed. No engine scope. The money cluster's MF valuation, tax and X-ray read this cluster's AMFI data through services/money_mf_meta.py; it names the package data-amfi-nav, which is data-amfi-backend here. |
| 27 I14 Instrument master keyed by ISIN | partial | Simplify. The smaller version is already covered, so this cluster builds only the 'ISIN columns before I28' delta: a lean instruments table (EQ from NSE EQUITY_L weekly and from the engine EOD export, MF from AMFI), aliases, resolve/resolve_isin, and search that appends series-EQ active instruments missing from the JSON directory. After the review, identity changes are monotonic: data older than a row's last_seen_on never renames it, and alias writes are idempotent. That removes the nightly flip-flop and the UNIQUE collision. Not built: pg_trgm, BSE, instrument_id FKs on legacy tables, and iOS changes. Flag data_instruments, default ON. | Landed: CMKT-15/GH-639 (routers/search.py returns routers.market.search_endpoint's bare list) and ARCH-10 (services/stock_universe.py is the single JSON directory, which StockDatabase.swift also loads; SearchScreen merges backend results over local ones). Planned: IOSCORE-32 removes retired symbols; LLM-21 validates tickers an LLM emits; CMKT-11 and LLM-20 make the NL screener fail closed. In the engine, research routes validate symbols (404 UNKNOWN_SYMBOL) and /analyze* returns 410 at Stage 3. Missing: ISINs for CAS import, a stable key for daily_prices and NAVs, resolution of renamed symbols, and new listings that are searchable without a redeploy. |
| 31 I15 Stored end-of-day prices (daily_prices) | partial | Simplify: 'upsert from today' as a Postgres mirror of a new read-only ml-engine export, so there is one NSE downloader. Review fixes: the export never touches the network and only tests a date with is_holiday (fetch disabled) once the store has moved past that date. While research mode is off, the mirror asks ml-engine for a marketdata-only gap-fill that runs under the engine's run lock, so ingest does not depend on research rollout. A data_eod_display gate (default OFF until legal clears NSE and NSE Indices rights) means EQ and INDEX closes are not returned to user-facing callers, and callers must fall back to their own labelled source on None. corporate_factor is dropped. The legacy download is deleted. Flags data_eod_prices ON and data_eod_display OFF. | ml-marketdata has landed: ml-engine/research/marketdata/store.py, adjust.py and bhavcopy.py are in the worktree. The real signatures are load_panel(start, end, source, data_dir); load_index(name, start, end, data_dir), which returns None without a cache; is_holiday(d, data_dir, fetch), which downloads from NSE when fetch is not given (store.py:732); ensure_sessions(through) gap-fill; and the PANEL_COLUMNS 'event' column (split, override, dividend, ca_unverified), derived from f = prev_close/close_prev with override CSV precedence. Curated rows carry each entity's latest symbol and ISIN. ml-api-deploy (research/api.py and its run lock) has not landed. Nothing writes EOD prices to Postgres. nse_data_provider.download_bhavcopy (line 237, scheduled at 13:30 UTC) feeds a cache that nothing reads. The money cluster prices with yfinance and its own engine routes. |
| 49 I18 Corporate actions: splits and bonuses | partial | Defer. The council's risk is removed on the default path, not only behind the flag. An event auto-applies only when every pre-ex-date ledger row in that group was entered (created_at, IST date) before the ex-date. Ambiguous events are never auto-applied: with data_corp_actions_confirm OFF (the default) they are only recorded, and with it ON (globally or for an allowlisted cohort) they become pending per-(user, group) proposals. Users answer from a Holdings banner with Apply or 'I've already updated it', and Undo within 30 days returns an item to pending. The guard is added to MATH-07's job. Deferral conditions (in DATA_FEEDS.md): C4 per-group replay is live, the iOS sheet is live, the I06 export includes the table, and an internal cohort's proposals have been reviewed. | FIX:MATH-07 (w5-01, not landed) adds fetch_split_events (yfinance, which records bonuses as splits), apply_split_events (per group, an idempotent SPLIT row at 23:59:59 UTC on the day before the ex-date) and a 07:30 IST job that auto-applies every Yahoo event since each trade date. MATH-11, CMON-V1, DB-01 and DB-09 supply trade dates, opening balances and replay. DB-09 replays across groups, and the money cluster's C4 per-group replay fixes that. Transaction has group_id (nullable) and created_at (db_models.py). Missing: typed corporate_actions rows, protection for back-dated manual entries (the council's double-count risk), confirmation, undo and a banner. |
| 53 C15 Incremental ingestion run by the worker | covered_by_fix_track | Not reviewed by the council (n/a), so treated as Build. The fix track builds it, so this cluster ships no code. The first pass's retention job is dropped (review): its only consumer is being retired, and a year of news chunks creates no storage pressure. DATA_FEEDS.md (data-wiring) records the end state. At Stage 3, unschedule REL-21's ingest_new. At Stage 4, delete rag_ingestion, rag_tools and vector_store (and their backup_service reference) and drop nivesh_filings. | FIX:REL-21 (p2-48) removes the boot-time ingest, keys chunk ids by source row id and schedules watermark-based ingest_new in the scheduler leader. FIX:LLM-22 adds content-hash ids and legacy cleanup. FIX:PERF-14 makes sentence-transformers lazy, and FIX:DB-13 leader-gates startup work. The only consumer of the RAG chunks is the legacy orchestrator (via rag_tools), which returns 410 at engine Stage 3 and is deleted at Stage 4. No other cluster plans to use RAG. |
| 55 I17 Point-in-time fundamentals: shareholding | partial | Defer, delivered as documented groundwork only, with no code this wave. Why: the smaller version needs data, and the only terms-respecting sources are a licensed feed (not budgeted) or written exchange permission. The first pass's 'manually verified' CSV import re-opened the council's data-rights risk, because hand-copying exchange tables raises the same terms question as scraping. It is dropped, together with the schema columns, iOS changes and flag. Users already see nothing false (CMKT-14 returns 404, and FAKE-04/CMKT-08 remove fabricated data). DATA_FEEDS.md records the follow-on design: DATE period_end, UNIQUE(ticker, period_end), source columns, optional percentages, Indian-FY labels and a data_shareholding flag defaulting OFF. Its conditions are a licensed vendor or written exchange permission, plus legal sign-off. | FIX:CMKT-14 replaces the RELIANCE-pinned aliases with a ticker-aware /api/v1/fundamentals/shareholding that returns 404 when empty. FIX:FAKE-04 deletes the seeded-random route, and FIX:CMKT-08 nulls fabricated FII/DII/pledge figures. shareholding_patterns has no writer and sorts its text 'quarter' as text. Shareholding is outside engine v1. There is no free source that respects the terms: NSE's website terms bar automated collection, REG-10 forbids nseindia.com/api, and licensed feeds cost about Rs 5-10 lakh a year. |
| 64 I25 Filing-cited results digests and guidance ledger | new | Defer. The smaller version, 'three numbers and a link', is built behind data_results_digest (default OFF), with a per-user cohort allowlist (FEATURE_DATA_RESULTS_DIGEST_USERS). It covers held and watched stocks only. The NSE RSS gives the link and period; yfinance gives revenue, net profit and EPS with YoY change, labelled as Yahoo figures. There is no LLM text, which removes the misquoting risk. The card goes in the Financials tab (IOSUI-08 reserves Forecast). The guidance ledger is not built. Deferral conditions are measurable while the flag is off (review): (a) the feed is verified on the server; (b) legal approves RSS use, filing links and Yahoo figures; (c) in a 4-week cohort, the figures match the filings for at least 90% of a weekly sample. The ledger decision comes afterwards, using I47 data. | No fix item or engine package covers it. The engine allows no LLM text beyond grounded phrasing and is English-only. filings_extractor reads www.nseindia.com/api (REG-10 flags this). NSE publishes an official Financial Results RSS (nsearchives.nseindia.com/content/RSS/Financial_Results.xml) with the company, the period and a filing link. yfinance quarterly statements are an allowed free source for the numbers. |

## Spec

# Data foundation cluster: implementation spec (I16, I14, I15, I18, I25; I17 and C15 as documented groundwork)

Re-grounded in worktree `audit-fixes` at HEAD 262042f (11 Oct 2026). Fix packages are landing while this is written, so each package re-checks signatures when it starts.
- **Landed, used here:**
  - Engine: ml-contract; be-db-ledger (`research_repo.normalize_symbol`, `extra_symbols`); ml-marketdata (`ml-engine/research/marketdata/store.py`, `adjust.py`, `bhavcopy.py`); be-ingest-jobs (`services/research/config.py`, `client.py`, `jobs.py`); be-serve-api.
  - Fix track: CMKT-15/GH-639, ARCH-10 and part of CMON-13.
- **Not landed:**
  - Engine: ml-api-deploy (`research/api.py` and its run lock) and be-wiring.
  - Fix track: MATH-07; REG-10 (`get_user_agent()` still returns a random browser UA); DB-24 (`core/timeutil.py`); ARCH-17; ARCH-19; PERF-19; FAKE-06; FINSEC-03/DB-06 (ERASURE_POLICY).
- Alembic has a single head today: d4e5f6a7b8c9.
- No flag module exists yet. platform-flags and habit-flags both plan `backend/services/feature_flags.py`. This cluster registers keys there and does not create its own.

**Review fixes applied:**
- (critical) Identity updates are monotonic on `last_seen_on`, alias writes are idempotent, and the identity cache is scoped to one date.
- (high) The EOD export never downloads.
- (high) MATH-07's auto-apply gets a `created_at` guard.
- (high) Applications are per (user, group).
- (medium) Undo returns an item to pending, and a dismissal can be undone.
- (medium) The design is grounded on the landed store: `event` is exported, `nse_confirmed` comes from mirrored rows, and `corporate_factor` is dropped.
- (medium) A marketdata-only gap-fill runs while research mode is off.
- (medium) A `data_eod_display` gate is added.
- (medium) The I17 importer and the C15 retention job are dropped.
- (medium) I25 conditions are measurable through a cohort.
- (low) No computed MF returns; new-listing search is EQ-only; routers are mounted before portfolio/stocks with one error envelope; human steps hold only rollout, legal and ops.

## 0. Shared decisions

### 0.1 Flags
- Keys live in the project module `services/feature_flags.py` (platform-flags; habit-flags writes the same path and the integration lead merges them). If the module is missing, data-flags stops; it never creates a second module.
- `services/data_flags.py` wraps it:
  - `enabled(key)`
  - `enabled_for(key, user_id)`: also true for ids in env `FEATURE_<KEY>_USERS`
  - `any_enabled(key)`: flag on or a cohort exists; jobs use this
  - `require(key, user_id=None)`: raises 404 `{'detail':{'code':'FEATURE_DISABLED','feature':key}}`
- **Error envelope** for every new backend route: `HTTPException(status, detail={'code': ...})`. iOS matches the code as a substring.

| Key | Default | Gates |
|---|---|---|
| data_instruments | on | weekly EQUITY_L refresh; new-listing search results |
| data_eod_prices | on | EOD mirror; gap-fill request while research mode is off |
| data_eod_display | **off** | EQ and INDEX closes for user-facing callers (NSE and NSE Indices rights) |
| data_mf_universe | on | AMFI harvest; NAV history |
| data_corp_actions_confirm | **off** (Defer) | proposals for ambiguous events; corporate-actions API |
| data_results_digest | **off** (Defer) | RSS poll, numbers, results-digest API |

### 0.2 Sources (free, terms-respecting)
| Data | Source | Cadence |
|---|---|---|
| EQ EOD rows (OHLC, prev close, volume, turnover, trades, ISIN, entity id, event) | ml-engine `GET /research/v1/eod/{date}` (read-only) | nightly; re-pulls 15 calendar days |
| Missing bhavcopies while research mode is off | ml-engine `POST /research/v1/marketdata/sync`: the engine's own `ensure_sessions` and `refresh_index` under its run lock, throttled, honest UA | each mirror run |
| Nifty 50 close | `store.load_index('NIFTY50')` | nightly |
| EQ names, series, ISINs | NSE `nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | weekly |
| MF universe and NAV | AMFI `www.amfiindia.com/spages/NAVAll.txt` | 23:30, 08:10 IST |
| Results link and period | NSE `nsearchives.nseindia.com/content/RSS/Financial_Results.xml` | :05/:35, 08:00-23:35 IST |
| Results numbers | yfinance `quarterly_income_stmt` (labelled Yahoo) | 22:15 IST, at most 150 calls |
| Splits and bonuses | yfinance (MATH-07), cross-checked with mirrored NSE rows | 07:30 IST (MATH-07) |

Rules:
- The UA is `config.settings.get_user_agent()` after REG-10; packages that fetch stop if REG-10 has not landed.
- Never call `www.nseindia.com/api/`. On 403 or 429, wait for the next run. Never disguise the client.
- No new dependency (stdlib csv, xml.etree, email.utils, zoneinfo; existing requests, httpx, yfinance). XML is capped at 2 MB.

### 0.3 Schema: one migration `05bf6cc1a533`
down_revision is the head at implementation time (today d4e5f6a7b8c9). The upgrade is idempotent and the downgrade is guarded and SQLite-safe. Models are added only in `models/db_models.py`.
- New tables:
  - instruments, with UNIQUE(asset_class, symbol), UNIQUE(amfi_scheme_code), UNIQUE(entity_id) and last_seen_on.
  - instrument_aliases, with UNIQUE(kind, value, instrument_id).
  - daily_prices, PK (instrument_id, trade_date), with a new **event** column, close > 0 and source IN (nse_bhavcopy, amfi, yfinance).
  - corporate_action_applications, with **group_id** (nullable FK), status IN (pending, applied, dismissed) and a unique expression index (user_id, corporate_action_id, coalesce(group_id, 0)).
  - results_digests, with UNIQUE(symbol, period_end).
- Altered: mutual_funds (scheme_type, is_active, track_nav, nav_source) and corporate_actions (action_type, ex_on, ratio, source, nse_confirmed, updated_at; unique (ticker, action_type, ex_on)).
- No shareholding change.
- DPDP: corporate_action_applications is the only per-user table. It cascades on user delete, is mapped 'delete' in ERASURE_POLICY (FINSEC-03's CI test needs every users.id FK mapped), and must be in the I06 export before the I18 flag turns on.

### 0.4 Jobs
`register_data_jobs` adds 7 jobs in Asia/Kolkata with max_instances=1, coalesce and misfire_grace_time=3600:

| Job | IST | Target |
|---|---|---|
| data_eod_mirror_evening | Mon-Fri 21:40 | eod_prices.mirror_recent |
| data_eod_mirror_morning | Tue-Sat 07:40 | eod_prices.mirror_recent |
| data_amfi_nav_night | 23:30 | amfi.harvest |
| data_amfi_nav_morning | 08:10 | amfi.harvest |
| data_equity_master | Sat 08:30 | instruments.refresh_equity_master |
| data_results_feed | :05 and :35, 8-23h | results_digest.poll_feed_job |
| data_results_numbers | 22:15 | results_digest.fill_pending_numbers |

MATH-07 keeps its 07:30 job; §4 changes what it does.

### 0.5 Contracts for other clusters
- `instruments.resolve(symbol=None, isin=None)` and `resolve_isin(isin)`. resolve_isin is the money cluster's CAS entry point.
- Price lookups: `eod_prices.get_close(symbol=None, *, isin=None, on=None, max_age_days=7, for_display=True) -> PriceFact | None`, plus `get_closes(identifiers)` (symbols or ISINs) and `index_close`.
  - With for_display, EQ and INDEX return only while data_eod_display is on. MF NAVs are always returned. Suspect rows are skipped.
  - **Callers must handle None** by keeping their existing source (today yfinance) and labelling what they show.
- `mutual_fund_service.mark_tracked(scheme_codes)` (I28).
- Money cluster `money_mf_meta` (its 'data-amfi-nav' is data-amfi-backend):
  - category is one of Equity, Debt, Hybrid, Solution Oriented or Other.
  - sub_category is AMFI's sub-category, so 'Equity Scheme - ELSS' gives Equity / ELSS.
  - ISINs come from the MF instrument row: isin is growth/payout, isin_alt is reinvestment.
- results_digests and corporate_actions are inputs for I31 Event Radar.

## 1. I14 Instrument master (Simplify)
**Story.** 'A stock that listed last week or was renamed is found; every CAS ISIN maps to the right stock or fund.'
- **Sources.** EQUITY_L weekly, the nightly EOD mirror and AMFI.
- **Renames and ISIN changes** keep the instrument id and write an alias.
- **Search.** `/api/v1/search` appends active series-EQ instruments missing from the JSON directory. Search never returns 500 because of the DB. No iOS change.
- **Identity matching** (`upsert_eq_identity`, shared by every writer), in order: entity_id, then isin or isin_alt, then ISIN alias, then the active row with the same symbol, else insert.
  - **Monotonic:** when seen_on is older than the matched row's last_seen_on, nothing changes.
  - Aliases go through the idempotent `_add_alias`.
  - A symbol held by another row is freed only by newer data.
- **Tests.** test_instruments.py.
- **Risk.** A same-day rename plus ISIN change creates a new row (engine rule 4); aliases allow a manual fix.

## 2. I15 Stored EOD prices (Simplify)
**Story.** 'Calculations using yesterday's close use the same official NSE close as the stock report.'
- **ml-engine `GET /eod/{date}`.** Read-only: no lock, network or writes.
  - Rows for the date give ok.
  - A future date, or a date with no later bhavcopy row within 10 days, gives 404 NOT_INGESTED.
  - Otherwise `is_holiday(d, fetch=<None>)` decides: true gives no_session, false gives NOT_INGESTED.
- **`POST /marketdata/sync`** runs the engine gap-fill in a thread under the run lock. It returns 202, or 409 ENGINE_BUSY.
- **Backend `mirror_recent`:**
  - skips when the flag is off or there is no key;
  - requests a sync only while research mode is off;
  - mirrors 15 calendar days in ascending order, each date in one transaction with a per-date cache;
  - with research off, an evening's data lands by 07:40.
- **Other backend pieces.** Display-gated accessors (§0.5) and a backfill CLI. The legacy download_bhavcopy is deleted.
- **Flags.** data_eod_prices (on) and data_eod_display (off until legal item (a), the same as engine Stage 3).
- **Risk.** The gap-fill downloads from NSE while research is off (legal item (b)); the owner can turn data_eod_prices off.

## 3. I16 AMFI mutual funds (Simplify)
**Story.** 'I browse real funds (Direct by default), filter by category and fund house, and see the official NAV and date, with no best-fund ranking.'
- **Harvester.** One harvester runs at 23:30 and 08:10. It records history from today for open Growth plans and tracked schemes, deactivates schemes missing from the file, skips DEMO codes, and raises when fewer than 5,000 rows parse.
- **API.**
  - The list is paged with plan, option, scheme_type, category, sub_category, amc_name, search, limit and offset. It returns a bare list with X-Total-Count, sorted by name, excluding NAVs older than 90 days.
  - `/filters`.
  - Detail adds the ISINs, history_start and other fields.
  - nav-history comes from daily_prices.
  - **No computed returns:** they would stay null for a year and add performance-presentation exposure without a benchmark. Revisit when history_start is a year old, with benchmark returns.
- **iOS.** Paging, pickers, menus, 350 ms debounce, rows without returns or AUM, source captions, and the empty, error and offline states.

## 4. I18 Corporate actions (Defer)
**Story.** 'Splits on stocks I entered before the ex-date adjust automatically. If I added a stock after an ex-date with an older buy date, Nivesh asks once whether my quantity already includes it, and I can undo within 30 days.'
- **Guard** (default path, flag off or on), per (user, group, event), with effective = 23:59:59 UTC on the day before the ex-date:
  - Skip when any of these hold: an application exists in any state; a SPLIT already exists at effective; nothing was held before effective; all holdings are CAS-only.
  - **Unambiguous** (every pre-effective non-corporate row has a created_at IST date before the ex-date): auto-apply as MATH-07 does.
  - **Ambiguous** (any row created on or after the ex-date, or with no created_at): never auto-applied. A pending application if the flag is on for that user; otherwise the event is only recorded.
- **Trade-off with the flag off.** A back-dated pre-split quantity stays unsplit until the user edits it. This is the safer error than doubling.
- **Records.** Each event becomes a corporate_actions row (SPLIT_OR_BONUS). `nse_confirmed` is true when the ex-date row's event is split or override and prev_close/previous close × ratio is within 2% of 1; it is None without rows.
- **State machine.**
  - pending → applied (SPLIT in that group, then replay) or dismissed.
  - Undo within 30 days returns either to pending, deleting the linked SPLIT first if there is one.
  - The nightly job never re-applies, because the application exists.
- **API.** `/api/v1/portfolio/corporate-actions`: GET, plus POST apply, dismiss and undo. Items carry group_id and group_name. Errors: NOT_FOUND, INVALID_STATE and LEDGER_CONFLICT, in the §0.1 envelope.
- **iOS.** A Holdings banner and a review sheet. The sheet explains why it is asking and offers Apply, 'I've already updated it' and Undo.
- **Deferral conditions:**
  - C4 per-group replay is live (DB-09 replays across groups);
  - the iOS sheet is live;
  - the I06 export includes the table;
  - an internal cohort's proposals have been reviewed.
- **Deploy.** Ship with MATH-07, or before its job first runs in prod. If MATH-07 ran first, DATA_FEEDS.md has a review query.

## 5. I25 Results digest (Defer)
**Story.** 'On results day for a stock I hold or watch, I see revenue, net profit and EPS with YoY change and a filing link, with no AI commentary.'
- **Data.**
  - The RSS poll uses a conditional GET. The period comes from the description; the symbol from a link parameter, otherwise a unique name match. Only held and watched symbols are kept; first item wins.
  - Numbers come from yfinance: the quarter column within 5 days of the period end and the year-ago column within 10 days. YoY only when prev > 0. A row is marked unavailable after 10 days.
  - Jobs run when `any_enabled`. No LLM imports.
- **API.** `GET /api/v1/stocks/{symbol}/results-digest`: 200, 404 NO_DIGEST or 422 INVALID_SYMBOL.
- **iOS.** A LatestResultsCard in Financials, with Lakhs/Crores, '+8.2% YoY', verbatim source text and a 'View filing' link.
- **Compliance.** Numbers only: no adjectives, ratings or targets.
- **Deferral conditions:**
  - (a) the feed is verified on the server;
  - (b) legal approves the RSS, filing links and Yahoo figures;
  - (c) in a 4-week cohort, at least 90% of a weekly sample matches the filings.
  - Then the flag goes on for everyone, and the guidance ledger is decided later with I47 data.

## 6. I17 Shareholding (Defer, docs only)
No code ships. The 'manually verified' import re-opened the data-rights risk and is dropped. DATA_FEEDS.md holds the follow-on design and its conditions: a licensed vendor or written exchange permission, plus legal sign-off.

## 7. C15 (covered by the fix track)
The retention job is dropped. End state: at Stage 3, unschedule ingest_new; at Stage 4, delete the RAG modules and the table.

## 8. Rollout
1. data-flags (after the project flag module), then data-schema (take a backup first).
2. data-instruments, data-ml-eod-api, data-amfi-backend.
3. data-eod-mirror, data-corpactions-backend (with MATH-07), data-results-backend.
4. data-wiring.
5. iOS packages, then ship the build.
6. Defer flags go to a cohort first, then to everyone. data_eod_display waits for legal.

## 9. Skipped, and when to add
- Adopting pre-guard MATH-07 SPLIT rows: only if MATH-07 reached prod first.
- Per-user targeting inside feature_flags: when that module supports it.
- Shareholding importer: when a licence exists.
- MF returns: after a year of history, with a benchmark.
- RAG retention: never (RAG is deleted at Stage 4).

## Owner/ops steps (not for implementers)

- Set BOT_CONTACT_URL (REG-10) in backend/.env and RESEARCH_HTTP_CONTACT in ml-engine.env before the data jobs run. The marketdata gap-fill needs RESEARCH_HTTP_CONTACT even while research mode is off, and the EOD mirror needs ML_ENGINE_API_KEY in backend/.env. If NSE or AMFI blocks the honest UA, do not disguise the client; either drop that feed or buy a licensed vendor feed.
- Legal review, with the outcome recorded in docs/data/DATA_FEEDS.md (the trust cluster's I07 covers third-party data rights): (a) display rights for NSE end-of-day prices and NSE Indices (Nifty 50) closes. This gates data_eod_display and is the same prerequisite as engine Stage 3. (b) Automated download of NSE EQUITY_L.csv, of bhavcopies outside research runs (the marketdata gap-fill) and of the NSE Financial Results RSS, plus linking to filings. Until (b) is cleared you may turn data_eod_prices off. (c) AMFI NAV attribution. (d) Use of Yahoo Finance split events and quarterly figures.
- Ship data-corpactions-backend in the same backend release as FIX:MATH-07, or before MATH-07's 07:30 IST job first runs in production. If MATH-07 has already run in production, run the review query in DATA_FEEDS.md (auto-applied SPLIT rows on holdings entered after the ex-date) and correct the affected holdings with those users before enabling data_corp_actions_confirm.
- Corporate actions (I18): first put internal user ids in FEATURE_DATA_CORP_ACTIONS_CONFIRM_USERS and review their pending rows after a few nights, spot-checking tickers against NSE corporate announcements. Turn data_corp_actions_confirm on for everyone only after all three are true: (1) the money cluster's C4 per-group replay is deployed, (2) the iOS build with the Holdings review sheet is live in the App Store, and (3) the platform cluster's I06 export includes corporate_action_applications.
- Results digest (I25): on the server, fetch https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml once by hand with the honest UA. Confirm that items carry a filing link, a period-end date and either a symbol parameter or a company name, and send a sample item to the implementer if the parser needs adjusting. Once legal items (b) and (d) are cleared and the iOS build is live, put an internal or TestFlight cohort in FEATURE_DATA_RESULTS_DIGEST_USERS for 4 weeks and compare a weekly sample of digests with the filings. Turn data_results_digest on for everyone only if at least 90% match. Decide on the guidance ledger later, using I47 engagement data.
- Shareholding (I17): no code ships in this wave. Before commissioning the follow-on described in DATA_FEEDS.md, contract a licensed shareholding-pattern vendor or obtain written exchange permission, and get legal sign-off. Do not load hand-copied exchange tables.
- Before deploying data-schema: take a database backup with the OPS-03 procedure, run alembic upgrade head, and confirm that alembic heads shows a single head. 05bf6cc1a533 must chain after whichever migration is head at merge time (d4e5f6a7b8c9 today).
- After the first deploy: watch the 23:30 IST AMFI run (more than 10,000 parsed rows and no 'AMFI file too short' telemetry), open the MF screen to confirm real funds appear with NAV dates, and keep DEMO_MODE=false in production. Optionally run the equity master refresh once from an admin shell instead of waiting for Saturday 08:30 IST.
- EOD prices: deploy ml-engine with the research API (engine Stage 0). While research mode is off, each mirror run requests a gap-fill, so an evening's data lands by the 07:40 IST run; in shadow or on, the nightly research runs fill the store. After the engine's historical backfill (python -m research.marketdata.store backfill --start 2018-01-01 on the engine host), run python -m scripts.backfill_daily_prices --start 2018-01-29 --end 2018-02-02, plus any XIRR span the money cluster requests. Turn data_eod_display on only after legal item (a).
- Capacity on the home server: daily_prices grows by about 1.5 million rows a year. Include it in backups, watch disk use, and revisit the history scope if storage becomes a constraint.
- RAG (C15): at engine Stage 3, unschedule REL-21's ingest_new, because nothing reads the chunks once /analyze returns 410. At Stage 4, approve deleting services/rag_ingestion.py, rag_tools.py and vector_store.py (and their backup_service reference) and dropping the nivesh_filings table.
- App Store: this cluster adds no new data types and no purchases, so the privacy manifest and App Privacy answers are unchanged. Mention 'official AMFI NAVs' in the release notes without making performance claims.
