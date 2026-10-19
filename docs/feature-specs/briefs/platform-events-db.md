# Feature package platform-events-db: user_events table with erasure registration, configurable retention and a consent backstop

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 36 I47 First-party product analytics, 28 I06 Privacy center: erasure, export, consent

## Files (create or modify)
- backend/models/db_models.py
- backend/migrations/versions/eaa69e058d9a_add_user_events.py
- backend/services/compliance_service.py
- backend/services/retention.py
- backend/tests/test_user_events_model.py

## Dependencies
- Feature packages (integrated before you start): platform-jobruns
- Declared in the plan: platform-jobruns, FIX:FINSEC-03, FIX:PERF-15, FIX:DB-10, FIX:FINSEC-04. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I47 storage and its privacy plumbing. The model and the erasure registration must land in the same package, because FIX:FINSEC-03's CI test fails for any table with a users.id FK that is missing from ERASURE_POLICY.

1. models/db_models.py: append class UserEvent(Base) with __tablename__ 'user_events' and these columns:
- id: Integer, primary key, autoincrement.
- user_id: Integer, ForeignKey('users.id'), NOT NULL.
- event_name: String(40), NOT NULL.
- props: JSON(none_as_null=True), NULL.
- app_version: String(20), NULL.
- platform: String(10), NOT NULL, default 'ios'.
- created_at: DateTime, NOT NULL, default _utcnow. This is the client's event time, clamped by the service.
Add Index('ix_user_events_name_created', 'event_name', 'created_at') and Index('ix_user_events_user_created', 'user_id', 'created_at').
Do not add a DB CHECK on event_name. Put a comment there: 'ponytail: allowlist lives in services/events_service.py; a CHECK would force a migration per new event'.

2. migrations/versions/eaa69e058d9a_add_user_events.py:
- revision 'eaa69e058d9a'.
- down_revision = the head after platform-jobruns (24a2a72cebb6 unless another migration landed between).
- Upgrade: inspector-guarded create of the table with both indexes.
- Downgrade: drop the table only if present.

3. services/compliance_service.py: set ERASURE_POLICY['user_events'] = 'delete' in FIX:FINSEC-03's registry.

4. services/retention.py:
- Add a module constant USER_EVENTS_RETENTION_DAYS, parsed once from env USER_EVENTS_RETENTION_DAYS. A missing, non-integer or < 1 value gives 180 and logs one warning. It is the single source of the retention period: events_service, disclosure_service and routers/flags.py import it (platform-events-api). Comment: 'DPDP Rule 8(3) decision pending; see docs/compliance/DPDP_RUNBOOK.md'.
- Add step 'user_events' to run_retention, in its own session and try/except like the other steps, returning its count. It deletes:
  a. rows whose created_at is older than USER_EVENTS_RETENTION_DAYS days;
  b. rows whose user has no active product_analytics consent. Use SQLAlchemy Core: delete(UserEvent).where(~UserEvent.user_id.in_(select(KYCConsent.user_id).where(KYCConsent.consent_type == 'product_analytics', KYCConsent.granted.is_(True), KYCConsent.revoked_at.is_(None)))). FIX:DB-10 revokes every active grant on withdrawal, so 'has an active grant row' equals has_active_consent. This is the daily backstop for consent withdrawal (DPDP s.6(4)-(6)); platform-events-api adds the immediate erase.
- The step runs inside the existing 03:15 IST retention job.

## Acceptance checks
- AST parse and pyright are clean.
- A static parse of migrations/versions shows a single head; the Alembic cycle passes in CI.
- tests/test_user_events_model.py passes in CI:
  - the table and both indexes exist after metadata creation;
  - FINSEC-03's every-FK-has-a-policy test still passes;
  - erase_user or delete_account removes a seeded user's events;
  - for a user with an active product_analytics consent, run_retention deletes a 181-day-old event and keeps a 1-day-old one;
  - with retention.USER_EVENTS_RETENTION_DAYS monkeypatched to 365, the 181-day-old event is kept;
  - all events of a user who never consented, and of a user whose consent was revoked, are deleted, while the consenting user's recent event stays;
  - an invalid env value falls back to 180.

## Cluster spec
docs/feature-specs/spec_platform.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
