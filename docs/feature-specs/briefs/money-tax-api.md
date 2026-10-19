# Feature package money-tax-api: FY capital-gains report (listed shares), CSV and routes

Cluster: money (Portfolio and money features); area: backend
Features covered: 54 I29 tax engine

## Files (create or modify)
- backend/services/money_tax_report.py
- backend/routers/money_tax.py
- backend/tests/test_money_tax_report.py

## Dependencies
- Feature packages (integrated before you start): money-flags, money-holding-api, money-ml-series, money-tax-engine
- Declared in the plan: money-tax-engine, money-ml-series, money-holding-api, money-flags. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.7. (1) money_tax_report.py: capital_gains(user_id, fy): EQ ledger rows only (asset_class 'EQ', no DIVIDEND) grouped by ticker; opening_balance_date per ticker = MATH-11 parse_trade_date(Portfolio.purchase_date) when the holdings row exists and parses; fifo_match; keep matches sold within fy_bounds. Not computed: lot.uncertain -> acquisition_date_uncertain; name contains 'ETF' or ticker ends BEES/IETF -> etf_category_unverified ('# ponytail: name heuristic until instruments are typed'). Grandfathering: collect every matched lot acquired <= 2018-01-31 first and make one money_market_series.raw_highs call per report (date 2018-01-31) only when display_allowed(), else fmv_unavailable; fmv_per_unit = high / split_factor_after_2018; cost_used via grandfathered_cost; review fmv_nse_high. Review reasons also: lot.review entries, corporate_action_review (auto_split), possible_intraday (a BUY of the ticker on the sale date). gain = sale - cost_used - transfer expenses; term, rate_period, section. Summary per spec; ltcg_above_exemption_inr = max(0, net LTCG - exemption) with no cross set-off; scope_note 'Listed shares only. Mutual funds are not covered yet.'; exact disclaimer. capital_gains_csv: first line exactly '# Nivesh capital gains working FY {fy} (rules in-cg-2026.1). Listed shares only. Informational only; verify with a chartered accountant.'; header fy,term,section,rate_period,symbol,name,quantity,acquired_on,sold_on,sale_value_inr,cost_of_acquisition_inr,fmv_31jan2018_per_unit,fmv_total_inr,cost_used_inr,transfer_expenses_inr,gain_inr,needs_review,review_reasons; csv module, 2-dp numbers, ISO dates, reasons joined by ';'; computed rows then not-computed rows with empty gain. (2) routers/money_tax.py: APIRouter(prefix='/api/v1/me/tax', tags=['Money']); GET /capital-gains?fy= and /capital-gains.csv?fy= (text/csv, Content-Disposition attachment; filename=nivesh_capital_gains_FY{fy}.csv, Cache-Control no-store); require_auth + require_flag('money_tax_report'); 422 INVALID_FY.

## Acceptance checks
test_money_tax_report.py (seeded ledgers; monkeypatched raw_highs, display_allowed): STCG with fees (BUY 10 @ 1000 fees 20 on 2025-05-10, SELL 10 @ 1200 fees 15 on 2025-12-01 -> gain 1965, 111A); grandfathered ITC (100 @ 500 on 2017-06-01, high 800, sale 100 @ 1000 in FY 2025-26 -> cost_used 80000, gain 20000, fmv_nse_high); split after 2018 (high 2400 / 2); bonus lot split across terms with stt_on_acquisition_unverified; ADJUST-only position not computed; opening balance with purchase_date computed with user_entered_date and without it not computed; ETF heuristic; a 2026-04-15 sale labelled 196/198; FY filter; raw_highs called once for three grandfathered tickers; fmv_unavailable when display not allowed; CSV first two lines exact and row count; 422 INVALID_FY; 404 with the flag off.

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
