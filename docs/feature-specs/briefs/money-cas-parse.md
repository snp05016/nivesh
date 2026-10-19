# Feature package money-cas-parse: casparser in a killable child process and pure balance mapping

Cluster: money (Portfolio and money features); area: backend
Features covered: 21 I28 CAS import + X-ray

## Files (create or modify)
- backend/requirements.txt
- backend/services/money_cas_parser.py
- backend/services/money_cas_mapping.py
- backend/services/parsers/cams_cas_parser.py
- backend/tests/fixtures/cas_sample.json
- backend/tests/cas_fake_parsers.py
- backend/tests/test_money_cas_mapping.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:ARCH-19, FIX:TEST-14. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.5 parser and plan; no DB, no routes. (1) requirements.txt: casparser==<latest release verified on PyPI at implementation; 1.4.1 in Oct 2026> with no extras and a comment: MIT, Python >= 3.11, pypdfium2 backend; CAS PDFs are password-protected multi-layout statements, so a maintained parser beats a hand-written one. Never install an AGPL/GPL extra; state the PDF backend of the pinned version in the PR. (2) money_cas_parser.py: CASParseError(code in WRONG_PASSWORD, UNSUPPORTED_STATEMENT, DEMAT_CAS_NOT_SUPPORTED, PARSE_TIMEOUT, PARSE_BUSY). _SEM = threading.BoundedSemaphore(2). parse_cas_pdf(data, password, *, target='services.money_cas_parser:_read_and_normalize', timeout=30.0) -> dict: acquire non-blocking else PARSE_BUSY; multiprocessing.get_context('spawn') Process(target=_child, args=(conn, target, data, password), daemon=True) with a one-way Pipe; parent.poll(timeout) false -> terminate(), join(5), kill() if alive, PARSE_TIMEOUT; child sends ('ok', dict) or ('err', code); release in finally. _child: resource.setrlimit(RLIMIT_AS, MB from env MONEY_CAS_PARSE_MEM_MB default 512) inside try (ImportError/ValueError/OSError ignored), resolve 'module:function' target, call, send result or a classified code; never send messages. _read_and_normalize(data, password): casparser.read_cas_pdf(io.BytesIO(data), password, output='dict'); incorrect-password exception -> WRONG_PASSWORD; other parse errors -> UNSUPPORTED_STATEMENT; NSDL/CDSL output -> DEMAT_CAS_NOT_SUPPORTED; returns money_cas_mapping.normalize(cas) so PII never leaves the child. Log class names only. (3) money_cas_mapping.py (pure): normalize(cas) -> {'statement': {'from','to','source','type'}, 'schemes': [{'amc','name','isin','amfi','close','valuation': {'date','nav','value','cost'}}]} with folios combined per ISIN (units and value/cost summed, latest valuation date and nav); drops investor info, PAN, KYC, nominees, advisor, folio numbers and transactions. plan(normalized, existing_cas: dict[isin, date], manual: set[isin]) -> list per ISIN: no ISIN -> skipped isin_missing; in manual -> manual_entries_exist; existing CAS date >= statement to -> older_statement; close <= 0.0005 and not in existing_cas -> zero_balance; else mode 'balance' with adjust {'quantity': round(close, 3), 'price': cost/units, or nav with flag 'cost_unknown' when cost missing/0 (price 0 when closing), 'date': statement to, 'key': 'casbal:' + sha256(f'{isin}|{to}|{close:.3f}').hexdigest()[:48]}. preview_summary(plans) -> {'schemes','balance','skipped','value_inr'}. (4) Delete services/parsers/cams_cas_parser.py (and the package __init__ if empty) unless ARCH-19 already did. (5) Fixtures: cas_sample.json, a synthetic casparser dict (investor 'Test Investor', PAN 'XXXXX0000X') with two folios of one ISIN, a scheme with cost, one without cost, a zero-balance scheme, one without ISIN; cas_fake_parsers.py: module-level sleeper(data, password) and raiser(data, password) targets for the child.

## Acceptance checks
test_money_cas_mapping.py: normalize output has no PAN/name/email/address/mobile/nominee/advisor/folio/transactions keys and no 'XXXXX0000X'; folios combine; plan modes and reasons for every fixture scheme, including older_statement and a zero balance that closes an existing CAS position; keys stable across runs and different when units differ; cost_unknown price = nav; parse_cas_pdf with target 'tests.cas_fake_parsers:sleeper' and timeout 0.5 raises PARSE_TIMEOUT and leaves no live child (multiprocessing.active_children() empty); a third concurrent call gets PARSE_BUSY; a monkeypatched incorrect-password path maps to WRONG_PASSWORD; caplog never contains the password; casparser's installed dependency closure (importlib.metadata requires, recursively) has no licence metadata or classifier containing 'AGPL' or a non-LGPL 'GPL' (skipped if casparser is not installed). pip install -r requirements.txt succeeds in CI.

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
