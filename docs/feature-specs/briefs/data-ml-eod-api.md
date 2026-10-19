# Feature package data-ml-eod-api: ml-engine read-only EOD export and marketdata-only gap-fill route

Cluster: data (Data foundation); area: ml-engine
Features covered: I15

## Files (create or modify)
- ml-engine/research/marketdata/eod.py
- ml-engine/research/api.py
- ml-engine/tests/research/test_eod.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:ml-marketdata, ENG:ml-api-deploy. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Use the landed store functions in research/marketdata/store.py: load_panel(start, end, source, data_dir), load_index(name, start, end, data_dir) (None without a cache), is_holiday(d, *, data_dir, fetch), ensure_sessions(through, *, data_dir, fetch, yf), refresh_index(name, *, data_dir, yf), YFinance.

New eod.py:
- class NotIngested(Exception).
- EXPORT_COLUMNS = ['symbol','isin','entity_id','open','high','low','close','prev_close','volume','turnover_inr','trades','event','quality_flags'].
- _no_fetch(_d) returns None. It is the only fetch this module ever passes.

eod_rows(market_date, *, data_dir=None, today=None, panel_loader=store.load_panel, index_loader=store.load_index, holiday_check=None) -> dict
1. today defaults to the Asia/Kolkata date; a future date raises NotIngested.
2. panel = panel_loader(market_date, market_date + 10 days, source='store', data_dir=data_dir). Curated rows already carry event and quality_flags, so no lookback is needed.
3. Rows with date == market_date and source 'nse_bhavcopy' (yfinance fallback rows are never exported):
   - map to EXPORT_COLUMNS: NaN -> None; volume and trades -> int; floats unrounded; '' kept;
   - symbol and isin are the entity's latest identifiers, exported as they are;
   - index_closes = {'NIFTY50': last} only if index_loader('NIFTY50', d, d, data_dir=data_dir) is non-empty and its last date == d;
   - return {'market_date','status':'ok','rows','index_closes'}.
4. If no bhavcopy row has date > market_date in the panel, raise NotIngested (the store has not moved past this date).
5. holiday_check defaults to lambda d: store.is_holiday(d, data_dir=data_dir, fetch=_no_fetch). True returns status 'no_session' with empty rows; False raises NotIngested, so the mirror retries. This function must never download (review high).

sync_marketdata(through, *, data_dir=None, ensure=store.ensure_sessions, refresh_index=store.refresh_index, yf_factory=store.YFinance) -> dict:
- yf = yf_factory(); r = ensure(through, data_dir=data_dir, yf=yf). This is the research run's own gap-fill: the 15-day window, the throttled downloader and the honest UA (needs RESEARCH_HTTP_CONTACT).
- Then refresh_index('NIFTY50', data_dir=data_dir, yf=yf); any exception is logged and recorded as index_error.
- Return {'through','added','no_session','failed','index_error'}.
- BhavcopySchemaError propagates.

research/api.py, on the existing router (prefix '/research/v1'; the key dependency gives 503 when unset and 401 when wrong):
- GET '/eod/{market_date}' (typed date, so bad input gives 422) calls eod.eod_rows(market_date, data_dir=config.DATA_DIR).
  - NotIngested returns JSONResponse(404, {'code':'NOT_INGESTED'}) (engine style).
  - No lock, no network, no writes.
- POST '/marketdata/sync' with body {'through': date}:
  - 422 if through is after the IST date.
  - Acquire the module lock POST /runs uses, with blocking=False; if it is held, return 409 {'code':'ENGINE_BUSY'}.
  - Otherwise start a daemon thread that runs sync_marketdata, logs the result and releases the lock in finally; return 202 {'status':'started','through': iso}.
  - While a sync holds the lock, /runs answers its 409 with run_id 'marketdata-sync' and market_date null (adapt to how ml-api-deploy records the active run). The backend kick then marks engine_busy and retries at the next kick.
  - The backend calls this route only while research mode is off.

Contract: 200 {'market_date':'2026-10-09','status':'ok','rows':[{'symbol':'RELIANCE','isin':'INE002A01018','entity_id':'EINE002A01018','open':2890.0,'high':2911.5,'low':2876.1,'close':2902.35,'prev_close':2885.4,'volume':5123456,'turnover_inr':14870000000.0,'trades':182345,'event':'','quality_flags':''}],'index_closes':{'NIFTY50':25123.45}}; 200 'no_session'; 404 NOT_INGESTED; sync 202, 409 or 422.

## Acceptance checks
MLTEST passes locally for tests/research/test_eod.py (no network):
- a fake panel with two dates, three symbols, one yfinance row and a NaN volume: only that date's bhavcopy rows, NaN as None, event present
- no rows on the date: with later rows and no zip or index bar it returns no_session; with an index bar, NotIngested; with no later rows, NotIngested; a future date, NotIngested
- monkeypatch store.Downloader with a class whose fetch raises AssertionError: eod_rows with the real is_holiday on a temp dir returns no_session and nothing raises
- the index is included or omitted correctly
- sync_marketdata reports index_error without raising
- TestClient on a fresh FastAPI() with the router: 200; 404 NOT_INGESTED; 401; 503; 422 for '2026-13-40'; sync 202 when free (target monkeypatched), 409 ENGINE_BUSY while the test holds the lock, 422 for a future date

The existing research tests stay green; PYRIGHT clean.

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
