# Feature package ai-riskflags-be: Risk flags API: post-trade concentration checks (surveillance added later), at most 3 flags

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 40. I33 Risk flags card

## Files (create or modify)
- backend/services/risk_flags_service.py
- backend/routers/risk_flags.py
- backend/main.py
- backend/tests/test_risk_flags_api.py

## Dependencies
- Feature packages (integrated before you start): ai-flags
- Declared in the plan: ai-flags, ENG:be-db-ledger, ENG:be-wiring. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Concentration checks only; ASM/GSM is added later by the conditional ai-surveillance-data. New backend/services/risk_flags_service.py, new backend/routers/risk_flags.py, and one include line in backend/main.py. Import is_enabled from the project flag module (grep -rn "def require_feature" backend).

Service constants: STOCK_FLAG_PCT = 20.0, SECTOR_FLAG_PCT = 40.0, MAX_FLAGS = 3, PRICE_MAX_AGE_DAYS = 5, _SYMBOL_RE = re.compile(r'^[A-Z0-9&-]{1,20}$').

risk_flags(user_id: int, symbol: str, *, today: date | None = None) -> dict
- sym = research_repo.normalize_symbol(symbol); a sym not matching _SYMBOL_RE raises ValueError. today defaults to the IST date (zoneinfo Asia/Kolkata).
- checks, flags, unavailable = [], [], [].
- If is_enabled('risk_flags_concentration'): checks.append('concentration'); flags += concentration_flags(user_id, sym, today).
- Return {'symbol': sym, 'checks': checks, 'flags': flags[:MAX_FLAGS], 'unavailable': unavailable}. A disabled check adds nothing to unavailable.

concentration_flags(user_id, sym, today) -> list[dict], in one get_session():
1. Holdings: Portfolio rows with user_id, group_name 'holdings' and is_virtual false. Aggregate by normalize_symbol(ticker), because Portfolio stores one row per lot as 'TCS' or 'TCS.NS': shares = sum of shares, invested = sum of shares * buy_price. Drop symbols with summed shares <= 0. If sym is not held, return []: flags are post-trade only, never on a stock the user is just browsing.
2. Latest reports in one query: a subquery of (symbol, max(as_of_date)) over ResearchReportRow for the held symbols, joined back on symbol and as_of_date; per symbol keep the nightly row if present, else the highest id.
3. Per held symbol: close = report_json['snapshot']['last_close'], used only when it is a dict with status == 'ok' and a numeric value > 0; sector = report_json.get('sector'); as_of = row.as_of_date. Guard every missing key.
4. Basis: if every held symbol has a usable close with (today - as_of).days <= PRICE_MAX_AGE_DAYS, the basis is 'current value', value = shares * close and basis_date = the oldest as_of; otherwise the basis is 'amount invested', value = invested and basis_date = None. total = sum of values; total <= 0 returns [].
5. holding_concentration when weight(sym) = value[sym] / total * 100 > 20.0.
6. sector_concentration when sym's sector is known, at least one other held symbol has the same sector, and that sector's summed weight > 40.0.
7. Order: holding_concentration, sector_concentration.

Flag dicts and exact texts
Each flag is {'id', 'title', 'text', 'source', 'source_url', 'as_of'}. Dates use D = f'{d.day} {d:%b %Y}'; percentages have one decimal.
- holding_concentration:
  - title 'Large share of your holdings';
  - current-value basis: '{SYM} is {w}% of your holdings by current value, using closing prices from {D}. This line appears when one stock is above 20%.';
  - invested basis: '{SYM} is {w}% of your holdings by amount invested. This line appears when one stock is above 20%.';
  - source 'Your Nivesh holdings'; source_url None; as_of = basis_date (ISO) or None.
- sector_concentration:
  - title 'Large share in one sector';
  - text '{Sector} stocks are {s}% of your holdings by {current value|amount invested}. This line appears when one sector is above 40%.';
  - same source fields.

Router, backend/routers/risk_flags.py
- router = APIRouter(tags=['Risk flags']).
- @router.get('/api/v1/stocks/{symbol}/risk-flags') def get_risk_flags(symbol: str, user_id: int = Depends(require_auth)). Sync def.
- If neither is_enabled('risk_flags_concentration') nor is_enabled('risk_flags_surveillance'): HTTPException(404, detail={'code': 'FEATURE_DISABLED', 'feature': 'risk_flags'}).
- ValueError becomes HTTPException(422, detail={'code': 'INVALID_SYMBOL'}).
- main.py: `from routers import risk_flags` and app.include_router(risk_flags.router) next to the other includes. routers/stocks.py only has single-segment /{ticker} routes, so there is no path capture.

Edge cases: a held symbol without a report forces the invested basis; an unknown sector gives no sector flag; flag texts never contain advice words. The money cluster's holding page and the ios cluster's C10 stock page may reuse this endpoint.

Tests, backend/tests/test_risk_flags_api.py
Setup: FEATURE_RISK_FLAGS_CONCENTRATION=true unless stated; insert Portfolio and ResearchReportRow rows via get_session with minimal report_json {'snapshot': {'last_close': {'value': X, 'status': 'ok'}}, 'sector': S, 'company_name': N}; delete the rows in teardown.
(a) no token gives 401.
(b) FEATURE_RISK_FLAGS_CONCENTRATION=false with surveillance unset gives 404 FEATURE_DISABLED.
(c) 'BAD SYMBOL!' gives 422.
(d) holdings ABC (value 60) and XYZ (value 40), both sector IT, closes dated yesterday; for ABC: a holding flag with '60.0%' and 'by current value', a sector flag 'IT stocks are 100.0%', and checks == ['concentration'].
(e) two lots of ABC worth 15 each, plus DEF 35 and GHI 35 in other sectors: the ABC holding flag shows '30.0%'.
(f) one held symbol without a report gives 'by amount invested' and as_of null.
(g) a last_close with status 'unavailable' and value null gives the amount-invested basis and no error.
(h) viewing PQR, which the user does not hold, while IT is 100% of their holdings gives flags [].
(i) a single holding ABC gives a holding flag '100.0%' and no sector flag (no other holding in its sector).
(j) at most 3 flags are returned.
(k) no flag text matches \b(buy|sell|hold|should|recommend|avoid|risky|safe)\b (case-insensitive).
(l) with surveillance unset, 'surveillance' is absent from checks and unavailable is [].

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the new files and main.py.
2. test_risk_flags_api.py passes in CI.
3. The endpoint makes no network call and no LLM call, and loads reports in one query per request.
4. main.py gains exactly one include line.
5. With both risk flags off the route returns 404.

## Cluster spec
docs/feature-specs/spec_ai.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
