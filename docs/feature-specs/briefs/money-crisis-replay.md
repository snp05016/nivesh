# Feature package money-crisis-replay: COVID-2020 replay endpoint (own history only)

Cluster: money (Portfolio and money features); area: backend
Features covered: 62 I35 crisis replays

## Files (create or modify)
- backend/services/money_crisis_replay.py
- backend/routers/money_replay.py
- backend/tests/test_money_crisis_replay.py

## Dependencies
- Feature packages (integrated before you start): money-flags, money-holding-api, money-ml-series
- Declared in the plan: money-ml-series, money-holding-api, money-flags. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I35 smaller version (Defer rule), spec 3.9; no nifty_proxy. (1) money_crisis_replay.py: SCENARIOS = {'covid_2020': {'label': 'COVID crash', 'start': date(2020,2,19), 'end': date(2020,3,23), 'sessions': 21}} (21 Feb and 10 Mar 2020 were NSE holidays). replay(user_id, scenario_id): unknown -> ValueError; not display_allowed() -> ReplayUnavailable; open holdings with include_mf=True priced via money_pricing.price_quotes; MF -> not_included 'mutual_fund'; unpriced -> 'unpriced'; EQ items {'key': ticker, 'symbol': ticker, 'start': start, 'sessions': 21} via money_market_series.window_returns (None -> ReplayUnavailable); any ok result whose end_date != 2020-03-23 -> ReplayUnavailable (log 'calendar_mismatch'); ok and not stale -> holding with its return_pct; ok with stale_exit -> 'not_traded_at_window_end'; no_data or unknown_symbol -> 'listed_after_window'; nifty_return_pct from the first ok item (none -> ReplayUnavailable). portfolio_return_pct = value-weighted mean over included holdings; portfolio_change_inr = sum(value * r / 100); covered_value_inr; the three notes exactly; returns 1 dp, rupees 2 dp; disk_cache 24 h keyed by user, scenario and sha1 of sorted (ticker, round(shares, 6)). (2) routers/money_replay.py: APIRouter(prefix='/api/v1/me/portfolio', tags=['Money']); plain def GET /crisis-replay?scenario=covid_2020 with require_auth + require_flag('money_crisis_replay'); 422 UNKNOWN_SCENARIO; ReplayUnavailable -> 503 {'code':'REPLAY_UNAVAILABLE','message':'The replay is not available right now.'} with Retry-After 300. No forecast, risk score or advice.

## Acceptance checks
test_money_crisis_replay.py (monkeypatched window_returns, display_allowed, price_quotes): own-history returns; a stock with no_data is not_included 'listed_after_window' and gets no return; stale exit excluded; MF and unpriced excluded from weights; weighted return and rupee change exact on a 2-stock fixture; end_date mismatch -> 503; window_returns None or display not allowed -> 503; unknown scenario 422; flag off 404; cached second call makes no series call.

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
