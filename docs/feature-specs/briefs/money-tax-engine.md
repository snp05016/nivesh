# Feature package money-tax-engine: Versioned capital-gains rules and FIFO lot engine (pure)

Cluster: money (Portfolio and money features); area: backend
Features covered: 54 I29 tax engine

## Files (create or modify)
- backend/services/money_tax_rules.py
- backend/services/money_tax_lots.py
- backend/tests/test_money_tax_rules.py
- backend/tests/test_money_tax_lots.py

## Dependencies
- Feature packages (integrated before you start): money-ledger-schema
- Declared in the plan: money-ledger-schema, FIX:MATH-11, FIX:MATH-07, FIX:DB-01, FIX:MATH-22. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
No DB, no network, Decimal via Decimal(str(x)). (1) money_tax_rules.py: RULES_VERSION='in-cg-2026.1', FA2024_CUTOFF=date(2024,7,23), GRANDFATHER_LAST_ACQ=date(2018,1,31), NEW_ACT_START=date(2026,4,1); fy_bounds(fy) (regex, consecutive, 2018-19..current IST FY, else ValueError); current_fy; add_months (month-end clamp); is_long_term (sold > add_months(acq, 12)); rate_period; rate_pct (STCG 15/20, LTCG 10/12.5); section (111A/196, 112A/198 by NEW_ACT_START); ltcg_exemption (100000 to FY 2023-24, 125000 after); grandfathered_cost = max(actual, min(fmv_total, sale)). (2) money_tax_lots.py: Row(id, date, type, quantity, price, fees, notes, import_batch_id); Lot(source_id, acquired_on, quantity, unit_cost, uncertain: str|None, review: tuple[str, ...], split_factor_after_2018=1, auto_split=False); Match(sell_id, sold_on, quantity, sale_value, transfer_expenses, lot copy). fifo_match(rows, *, opening_balance_date: date | None = None) -> (matches, open_lots): sort (date, id); dedupe auto splits via ledger_service.dedupe_auto_splits; ADJUST kinds via ledger_service.adjust_kinds. BUY -> Lot(q, (q*p+fees)/q); if ledger_service.is_opening_balance(row): acquired_on = opening_balance_date with review ('user_entered_date','stt_on_acquisition_unverified') when given, else uncertain 'opening_balance' with review ('stt_on_acquisition_unverified',). SELL consumes FIFO, fees pro rata, shortfall -> TaxLedgerError. SPLIT scales lots, factor after 2018-01-31, auto_split when notes start 'auto: corporate action'. BONUS -> Lot(q, 0, date, review=('stt_on_acquisition_unverified',)). ADJUST noop ignored; close clears lots; restate -> one Lot(q, p, date, uncertain 'adjust'). DIVIDEND ignored.

## Acceptance checks
Tests: fy_bounds valid/invalid; BUY 2024-03-01 / SELL 2025-03-01 short, 2025-03-02 long; 31 Jan + 1 month clamps; rates 2024-07-22 vs 23; sections 2026-03-31 vs 2026-04-01; exemptions FY 2023-24 vs 2024-25; grandfathered_cost three cases; FIFO across two buys with fees; split after 2018 scales lots and factor; duplicate auto splits applied once; bonus lot nil cost with review; opening balance with date -> computed lot with user_entered_date, without -> uncertain; legacy backfill row treated as opening balance; noop ADJUST keeps lots; close then BUY starts fresh; restate -> uncertain lot; shortfall raises.

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
