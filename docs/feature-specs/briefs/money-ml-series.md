# Feature package money-ml-series: Engine series routes sharing the outcomes rule, plus backend client

Cluster: money (Portfolio and money features); area: mixed
Features covered: 58 C16 decision journal, 54 I29 tax engine, 62 I35 crisis replays

## Files (create or modify)
- ml-engine/research/outcomes.py
- ml-engine/research/series.py
- ml-engine/research/api.py
- ml-engine/tests/research/test_series.py
- backend/services/research/client.py
- backend/services/money_market_series.py
- backend/tests/test_money_market_series.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:ml-marketdata, ENG:ml-assembly-pipeline, ENG:ml-api-deploy, ENG:be-ingest-jobs. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.8. ml-engine: (1) outcomes.py: extract score_outcomes' per-item computation (start = px_t on the as_of session; px_exit = last valid px_idx on or before the h-th true session; stale_exit when that row is > 5 sessions old; nifty50_return_pct over the same dates; pending before h sessions; void reasons) into realized_window(entity_rows, index_series, as_of_session, h, calendar) -> dict with no behaviour change; score_outcomes calls it; test_outcomes_live.py passes unchanged. (2) series.py: window_returns(items, *, source='store', data_dir=None) resolves each entity with resolve_entity(symbol=, isin=, as_of=None) (None -> unknown_symbol), picks the last valid px_idx session on or before start (none within 5 sessions -> no_data), loads load_panel once per merged span ([start-15d, start+ceil(h*7/5)+30d]) plus load_panel(today-10d, today) for last_session, and calls realized_window; a void maps to no_data. raw_highs(items): rows in [date-15d, date] with volume > 0 and no 'suspect' flag; last one -> {'status':'ok','date_used','high','close'} raw; none -> no_trade. (3) api.py: pydantic WindowItem(key str <= 64, symbol|None, isin|None, start: date, sessions: int 1..252; exactly one of symbol/isin), WindowRequest(items <= 2000), HighItem(key, symbol, isin, date), HighRequest(items <= 2000); POST /research/v1/series/window-returns and /series/raw-high on the existing router with the X-ML-Engine-Key dependency; responses {'results': [...], 'last_session'}. No fixed-end or index-only mode. Backend: (4) services/research/client.py: MLEngineClient.series_window_returns(items) and series_raw_highs(items) -> body via self._request('POST', path, ok=(200,), timeout=8.0, json={'items': items}). (5) money_market_series.py: window_returns(items) / raw_highs(items) -> {key: result} or None (no key, MLEngineError/MLEngineUnavailable, any exception: log class name only); chunks of 1000; non-pending results cached with services.disk_cache set('money_series', sha1(json.dumps(item, sort_keys=True, default=str)), result, ttl=7*86400), cache checked first; symbols via repositories.research_repo.normalize_symbol; display_allowed() -> services.research.config.CONFIG.mode == 'on' (any exception -> False).

## Acceptance checks
MLTEST tests/research/test_series.py on synthetic panels: split day keeps px_idx continuous; zero-volume NaN day skipped; early stop -> stale_exit; start before listing -> no_data; unknown symbol; window past last_session -> pending; sessions follow the store calendar; window_returns and score_outcomes give identical return_pct and stale_exit for the same (entity, start session, h); two items years apart -> two bounded load_panel calls; raw_highs returns the previous trade when 2018-01-31 has none; API: 503 without key env, 401 wrong key, 422 invalid item, 200 shape. Backend test_money_market_series.py with httpx.MockTransport via MLEngineClient(transport=...): header sent, chunking at 1000, None on 500/timeout/missing key, cache hit skips the call, pending not cached, display_allowed False when CONFIG.mode != 'on'.

## Cluster spec
docs/feature-specs/spec_money.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
