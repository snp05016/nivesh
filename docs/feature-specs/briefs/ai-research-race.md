# Feature package ai-research-race: Fix the on-demand research report insert race (IntegrityError returns 500)

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 14. I22 Analysis cache correctness

## Files (create or modify)
- backend/repositories/research_repo.py
- backend/tests/test_research_repo_race.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:be-db-ledger, ENG:be-serve-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Engine bug found while planning I22: research_repo.insert_on_demand_report calls _existing_report and then inserts. Two concurrent on-demand computes for one symbol therefore race, and the loser's commit raises sqlalchemy.exc.IntegrityError on UNIQUE(symbol, as_of_date, engine_version, origin), so the request returns 500. This is a standalone package so it survives any cut of feature work. The engine track may take it instead as a one-line note; if research_repo.py already handles IntegrityError in this function when you start, mark the package done.

Change in backend/repositories/research_repo.py (owned by ENG:be-db-ledger):
- add `from sqlalchemy.exc import IntegrityError`;
- in insert_on_demand_report, after session.add(row), wrap the commit: try: session.commit(); except IntegrityError: session.rollback(); existing = _existing_report(session, row); if existing is None: raise; return existing. Then return row as today.
No other change.

Tests, backend/tests/test_research_repo_race.py (SQLite; the unique constraints exist in the model):
(a) pre-insert a row with the same (symbol, as_of_date, engine_version, origin='on_demand') but a different report_id; monkeypatch research_repo._existing_report to return None on its first call only, then call through. insert_on_demand_report returns the pre-inserted row (same id), and the table holds one row for that key.
(b) monkeypatch _existing_report to always return None with the same pre-inserted row: IntegrityError is re-raised.
(c) the normal path with no existing row still inserts and returns the new row.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean.
2. The new tests, plus the engine's test_research_repo.py and test_research_api.py, pass in CI.
3. The diff touches only insert_on_demand_report and the import.

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
