# Feature package money-commission-drag: Regular-plan cost data for the X-ray (later wave)

Cluster: money (Portfolio and money features); area: backend
Features covered: 57 I34 commission drag

## Files (create or modify)
- backend/services/money_commission.py
- backend/data/mf_ter_large_amcs.csv
- backend/services/money_xray.py
- backend/tests/test_money_commission.py

## Dependencies
- Feature packages (integrated before you start): money-cas-api, money-xray-api
- Declared in the plan: money-xray-api, money-cas-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Build after money_cas_import is enabled (human step). Spec 3.6. (1) money_commission.py: load the CSV once per process (functools.lru_cache, csv.DictReader); validate rows (both ISINs ^INF[A-Z0-9]{9}$, 0 < TER <= 3, direct <= regular, as_of ISO <= today), log and skip bad rows. commission_drag(funds: list[{'isin','name','value_inr','is_direct'}]) -> no rows -> {'available': False, 'reason': 'ter_data_missing'}; newest as_of > 45 days -> 'ter_data_stale'; else per held fund whose ISIN is a regular_isin: gap_pp and annual_cost_inr (Decimal, 2 dp); uncovered_regular_funds = held regular funds without a row; return the spec block with source and source_url. (2) mf_ter_large_amcs.csv: header only; the owner fills it; never invent TER values. (3) money_xray.py: 'commission_drag' = money_commission.commission_drag(funds) when is_enabled('money_commission_drag'), else None.

## Acceptance checks
test_money_commission.py: the shipped header-only CSV parses and yields ter_data_missing; a temp CSV gives the right gap and cost; stale as_of -> ter_data_stale; invalid rows skipped; direct > regular rejected; X-ray commission_drag null with the flag off and filled with it on.

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
