# Feature package money-xray-api: Portfolio X-ray endpoint

Cluster: money (Portfolio and money features); area: backend
Features covered: 21 I28 CAS import + X-ray

## Files (create or modify)
- backend/services/money_xray.py
- backend/routers/money_xray.py
- backend/tests/test_money_xray.py

## Dependencies
- Feature packages (integrated before you start): money-flags, money-holding-api, money-mf-isolation
- Declared in the plan: money-holding-api, money-mf-isolation, money-flags. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.5 X-ray contract. (1) money_xray.py: build_xray(user_id) loads open holdings (group_name 'holdings', is_virtual false, include_mf=True) with asset_class; prices via money_pricing.price_quotes (unpriced valued at cost and listed); MF metadata via money_mf_meta.scheme_info. Buckets (empty omitted): stocks 'Stocks'; category 'Equity' -> equity_funds 'Equity funds'; 'Debt' -> debt_funds 'Debt funds'; 'Hybrid' -> hybrid_funds 'Hybrid funds'; 'Solution Oriented'/'Other' -> other_funds 'Index funds & other funds'; unknown -> unclassified_funds 'Funds (category unknown)'. amcs (funds only, by value desc); plans from is_direct (True/False/None -> direct/regular/unknown) as % of fund value, null without funds; top_holdings top 10; concentration {largest_ticker, largest_pct, top5_pct}; facts fixed templates: largest_holding_share 'Your largest holding, {name}, is {pct:.0f}% of your portfolio.' (use the scheme name for funds), top5_share 'Your five largest holdings are {pct:.0f}% of your portfolio.' (5+ holdings), regular_plan_share '{pct:.0f}% of your fund value is in regular plans.' (funds held), unpriced_count '{n} holdings have no current price and are counted at cost.'; pcts 1 dp; 'commission_drag': None (money-commission-drag fills it). (2) routers/money_xray.py: APIRouter(prefix='/api/v1/me/portfolio', tags=['Money']); plain def GET /xray with require_auth + require_flag('money_xray'). Registry in routers/money.py already includes it.

## Acceptance checks
test_money_xray.py (monkeypatched price_quotes and scheme_info): mixed stocks and funds give expected buckets, AMC shares, plan mix and facts text; empty portfolio -> zeros, no facts; unpriced holding counted at cost and listed; scheme_info {} -> funds in unclassified_funds and plans unknown; commission_drag null; flag off -> 404.

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
