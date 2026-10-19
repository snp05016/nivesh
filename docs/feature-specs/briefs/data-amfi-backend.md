# Feature package data-amfi-backend: AMFI harvester, real MF universe, paged MF API and NAV history from daily_prices

Cluster: data (Data foundation); area: backend
Features covered: I16

## Files (create or modify)
- backend/services/amfi.py
- backend/services/mutual_fund_service.py
- backend/routers/mutual_funds.py
- backend/tests/test_amfi.py
- backend/tests/test_mutual_funds_v2.py
- backend/tests/fixtures/amfi_navall_sample.txt

## Dependencies
- Feature packages (integrated before you start): data-flags, data-instruments, data-schema
- Declared in the plan: data-flags, data-schema, data-instruments, FIX:CMON-13, FIX:FAKE-06, FIX:ARCH-19, FIX:ARCH-17, FIX:REG-10, FIX:DB-24. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
New services/amfi.py replaces both amfi_nav_harvester copies that ARCH-19 deletes; do not revive them. The money cluster calls this package data-amfi-nav and reads MutualFund and the MF instrument rows. AMFI_NAV_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'; MIN_ROWS = 5000; HISTORY_MAX_AGE_DAYS = 7.

fetch_navall(timeout=60): honest UA (after REG-10), raise_for_status, 20 MB cap.

AmfiRow dataclass: scheme_code, isin_growth, isin_reinvest, scheme_name, nav, nav_date, amc_name, category, sub_category, scheme_type, is_direct_plan, is_growth_plan.

parse_navall(text):
- Context lines (no ';'):
  - A heading '(Open Ended|Close Ended|Interval Fund) Schemes(...)' sets scheme_type 'open', 'close' or 'interval'. Split the bracket text on the first ' - '. The left side minus ' Scheme' is the category, normalised to Equity, Debt, Hybrid, Solution Oriented or Other. The right side is sub_category (at most 50 chars). Text without ' - ' gives Other plus the whole text.
  - Any other line is the AMC name.
- Data rows:
  - At least 6 ';' parts, and parts[0] all digits.
  - An ISIN must match ^IN[A-Z0-9]{10}$; '-', 'NA', 'NOTAPP' and '' become None.
  - NAV = float(parts[4] without commas) > 0, skipping 'N.A.' and '#N/A'. Date is %d-%b-%Y.
  - is_direct_plan: the whole word 'direct'. is_growth_plan: 'growth' and none of idcw, dividend or bonus.
  - Rows before any heading get scheme_type None and category Other.

harvest(*, text=None, today=None):
- Flag off: skipped. Fewer than MIN_ROWS: RuntimeError.
- In one session:
  - Preload funds and MF instruments.
  - Skip SAMPLE_SCHEME_CODES.
  - Upsert MutualFund: scheme_name plus legacy fund_name, amc_name plus legacy amc, category, sub_category, scheme_type, plan flags, nav, nav_date (ISO string), nav_source 'amfi', is_active True. Never touch aum, expense, returns, risk or manager.
  - instruments.upsert_mf(..., isin=isin_growth, isin_alt=isin_reinvest, seen_on=today).
  - History rows: open AND (growth OR track_nav) AND nav_date >= today - 7. Insert DailyPrice (source 'amfi') when absent; update close on a restatement.
  - Deactivate absent 'amfi' funds and their instruments.
  - Commit once.
- Return {'parsed','funds_inserted','funds_updated','history_rows','deactivated'}.

mutual_fund_service.py:
- list_funds(*, category, sub_category, amc_name, search, risk_level, plan='direct', option='growth', scheme_type='open', limit=50, offset=0) -> (rows, total)
  - Active rows only. plan and option map to is_direct_plan and is_growth_plan ('all' means no filter). 'open' also keeps NULL types (DEMO rows).
  - Exclude 'amfi' rows with nav_date older than 90 days.
  - search: an ISIN matches the instrument's isin or isin_alt; digits match scheme_code; anything else is ILIKE on the name.
  - Order by lower(scheme_name).
- list_filters() -> {'categories': {cat: [subs]}, 'amcs': [...]}.
- fund_extras(fund):
  - isin_growth and isin_reinvest from the instrument; history_start = MIN(daily_prices.trade_date).
  - No computed returns (review): stored returns_* are kept and are null for AMFI rows.
- get_nav_history(scheme_code, days): None when the fund is missing. Flag on: rows from daily_prices, ascending. Flag off: [].
- mark_tracked(scheme_codes) -> int.

routers/mutual_funds.py (thin; keep ARCH-17's prefix, today /api/mutual-funds):
- GET '/' adds sub_category, plan, option and scheme_type Literals, limit 1..200 (default 50) and offset 0..20000. Set X-Total-Count; the body stays a bare list, so old builds get the first 50.
- GET '/filters', declared before '/{scheme_code}'.
- MutualFundResponse gains optional scheme_type, nav_source, is_active, isin_growth, isin_reinvest and history_start.
- Detail merges fund_extras and calls mark_tracked when track_nav is false.
- nav-history keeps le=365.

## Acceptance checks
PYPARSE and PYRIGHT clean.

test_amfi.py (fixture with the header, an 'Open Ended Schemes(Equity Scheme - Large Cap Fund)' heading, two AMCs, Direct-Growth, Regular-IDCW and '-' ISIN rows, an 'N.A.' NAV, a 2017 row and a 'Close Ended Schemes(Income)' heading) covers:
- parsing gives category Equity, sub_category 'Large Cap Fund', the plan flags and the ISINs
- harvest (MIN_ROWS=1) inserts funds and instruments
- history only for fresh open growth rows
- a rerun is idempotent; a restatement updates the row
- an absent scheme is deactivated
- the sample code is untouched
- flag off skips; a short file raises

test_mutual_funds_v2.py covers:
- the default list is direct, growth, open and active, sorted by name, with X-Total-Count
- paging works; plan=all&option=all widens the set
- ISIN and code search
- /filters shape
- detail has isin_growth and history_start and sets track_nav
- an AMFI detail has null returns even with a NAV 365 days back
- nav-history comes from daily_prices with the flag on and is [] with it off
- days=400 gives 422

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
