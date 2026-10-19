# Feature package money-docs: Money docs: flags and deferral conditions, ledger and MF isolation, CAS privacy notice, tax methodology

Cluster: money (Portfolio and money features); area: docs
Features covered: 7 C4 ledger integrity, 21 I28 CAS import + X-ray, 54 I29 tax engine, 57 I34 commission drag, 58 C16 decision journal, 61 I36 family portfolios (groundwork only), 62 I35 crisis replays

## Files (create or modify)
- docs/money/FEATURE_FLAGS.md
- docs/money/LEDGER.md
- docs/money/CAS_IMPORT_PRIVACY.md
- docs/money/TAX_METHODOLOGY.md

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: none. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Written from this spec for the owner, legal and a CA. (1) FEATURE_FLAGS.md: the eight flags (env var, default, verdict, what each hides, exact enable/deferral conditions from spec 2.1); how to switch (edit backend/.env, restart); a section 'I36 Family portfolios: not built, Phase 3 per council (Reject)' with the rejected risk and the constraints in spec 3.10; note that the X-ray's commission card waits for CAS import. (2) LEDGER.md: single-writer rule; transaction types and replay semantics; auto-split dedupe; opening-balance and legacy-backfill detection and re-dating; ADJUST kinds (noop/close/restate) and how they drive returns and tax; asset_class, MF tickers as ISINs, and the ORM guard (include_mf allowlist; which screens show funds in v1); CAS balance rows (import_batch_id, casbal keys, restatement, undo); full-history import as phase 2; why multi_asset_transactions was retired; Float per DB-25; reconcile_ledger.py runbook (restored backup first, review CSV, prod after backup, what --apply does per kind). (3) CAS_IMPORT_PRIVACY.md: notice cas-v1 verbatim; data flow (streamed JSON upload -> memory -> spawn child with memory cap -> PII stripped in the child -> preview_json <= 24 h -> ledger); retained vs discarded fields; no AI processors receive imported funds (and the test that enforces it); retention (previews 24 h, batches until undo or erasure); purpose limitation; DPDP mapping (consent per batch with version and time, erasure via DB-06, export via the platform privacy center, breach logging via the platform track); legal sign-off item: whether the notice must also be offered in an Eighth Schedule language before enabling (v1 English, per the engine's English-only decision); App Store privacy label (Financial Info); versioning rule (any change -> cas-v2 + constant). (4) TAX_METHODOLOGY.md: rules version and legal basis (111A/112A, s.55(2)(ac), Finance (No. 2) Act 2024 from 23 Jul 2024, Income-tax Act 2025 ss.196/198 from 1 Apr 2026); scope listed shares only; FIFO note; every not-computed and review reason; limitations (no set-off, no slab income, no funds in v1, FIFO across accounts, NSE-only FMV, bonus vs split, user-entered purchase dates, the 112A/198 STT-on-acquisition condition and its notified exceptions); the worked examples with inputs and expected outputs as a CA sign-off checklist.

## Acceptance checks
Markdown renders. Every flag, route and reason code matches the package descriptions. No claim of SEBI registration, no advice, no performance claims.

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
