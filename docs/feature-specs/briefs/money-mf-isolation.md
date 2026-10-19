# Feature package money-mf-isolation: One ORM guard that hides mutual-fund rows from every non-money reader

Cluster: money (Portfolio and money features); area: backend
Features covered: 7 C4 ledger integrity, 21 I28 CAS import + X-ray

## Files (create or modify)
- backend/database.py
- backend/services/ticker_matcher.py
- backend/tests/test_mf_isolation.py

## Dependencies
- Feature packages (integrated before you start): money-ledger-schema
- Declared in the plan: money-ledger-schema. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Replaces per-reader asset_class filters (review) with one choke point. (1) database.py, after the models import: from sqlalchemy import event; from sqlalchemy.orm import with_loader_criteria. @event.listens_for(Session, 'do_orm_execute') def _portfolio_eq_only(state): if state.is_select and not state.is_column_load and not state.is_relationship_load and not state.execution_options.get('include_mf', False): state.statement = state.statement.options(with_loader_criteria(Portfolio, Portfolio.asset_class == 'EQ', include_aliases=True)). Docstring: MF rows (ticker = ISIN) are invisible to ORM reads unless the statement opts in; only the allowlisted modules may opt in; Core table selects, text() and bulk UPDATE/DELETE are unaffected, so erasure and the privacy export still see every row. (2) services/ticker_matcher.py raw SQL: add "AND COALESCE(asset_class, 'EQ') = 'EQ'" to the portfolio SELECT. (3) No other reader changes: copilot, analysis, red flags, PDF export, research_repo.extra_symbols, harvesters, charts and admin become stock-only automatically.

## Acceptance checks
test_mf_isolation.py (conftest DB, one EQ and one MF holdings row): session.query(Portfolio).all(), query(Portfolio.ticker).distinct(), query(Portfolio.user_id, Portfolio.ticker), select(Portfolio) and session.get(Portfolio, mf_id) return no MF row; .execution_options(include_mf=True) returns both; an opted-in MF row can be read after commit (refresh); Portfolio.__table__.select() via the session returns both; query(Portfolio).filter(user_id).delete() removes both; repositories.research_repo.extra_symbols(session) contains no ISIN; allowlist test scans backend/**/*.py (excluding tests) for 'include_mf' and fails on any file outside {database.py, services/ledger_service.py, scripts/reconcile_ledger.py, routers/portfolio.py, services/portfolio_snapshot.py, services/money_*.py}; and services/money_*.py contain no import matching deepseek|anthropic|openai|_deepseek_chat|llm (case-insensitive).

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
