# Feature package money-journal-scoring: Journal entries scored vs the Nifty 50 in a background task

Cluster: money (Portfolio and money features); area: backend
Features covered: 58 C16 decision journal

## Files (create or modify)
- backend/services/money_journal_scoring.py
- backend/routers/trade_journal.py
- backend/tests/test_money_journal_scoring.py

## Dependencies
- Feature packages (integrated before you start): money-flags, money-journal-nollm, money-ledger-schema, money-ml-series
- Declared in the plan: money-journal-nollm, money-ml-series, money-ledger-schema, money-flags. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.4. (1) money_journal_scoring.py: HORIZONS = {21: '1 month', 63: '3 months'}; FINAL = {'ok','unknown_symbol','no_data'}. score_pending(user_id, limit=200) -> int: returns 0 unless is_enabled('money_journal_scoring') and display_allowed(); in-process throttle (module dict + Lock) skips a user scored < 600 s ago; selects BUY/SELL rows lacking a final status for some horizon whose IST entry date + ceil(h*7/5) days <= today; items {'key': f'j{id}:{h}', 'symbol': ticker, 'start': entry_date, 'sessions': h}; window_returns None -> 0; writes market_score[str(h)] = {'status','stock_pct','nifty_pct','excess_pp','decision_excess_pp','start_date','end_date','stale_exit'} (2 dp; decision = excess for BUY, -excess for SELL), never overwriting a final entry, assigning a new dict, one commit. market_block(rows, available, reason) -> {'available','reason','benchmark_label','as_of','horizons':[{'sessions','label','scored','pending','favourable','median_decision_excess_pp','by_action':{'BUY':{...},'SELL':{...}}}],'entries':{str(id): market_score}}; scored counts status ok; favourable counts decision_excess_pp > 0; median via statistics.median or null. (2) routers/trade_journal.py trade_journal_stats_endpoint: add background_tasks: BackgroundTasks; build 'market' from stored market_score only (reason flag_off | engine_not_live | engine_unreachable; available when display allowed and any entry is scored or pending; entries empty when not allowed); when allowed and pending entries exist, background_tasks.add_task(score_pending, user_id). Engine unreachable is detected by the last score_pending result cached per user (None -> engine_unreachable). Change nothing else.

## Acceptance checks
test_money_journal_scoring.py (monkeypatched window_returns, display_allowed, flag): BUY stock +3.2 Nifty +1.1 stores decision 2.1; SELL stores -excess; pending not stored and counted; a stored final entry is never overwritten; HOLD/WATCH untouched; flag off or display not allowed -> no calls and market.available false with the right reason; None from the engine writes nothing; the GET response does not wait for scoring (score_pending called only via BackgroundTasks, verified with a TestClient and a spy); throttle prevents a second run within 600 s; another user's entries never scored.

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
