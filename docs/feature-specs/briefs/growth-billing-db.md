# Feature package growth-billing-db: Billing schema: App Store columns on user_subscriptions and an append-only subscription_events table

Cluster: growth (Monetization, growth and bold bets); area: backend
Features covered: 38 I43 Real billing with StoreKit 2

## Files (create or modify)
- backend/models/db_models.py
- backend/migrations/versions/b7e2c91a4f06_add_app_store_billing.py
- backend/services/compliance_service.py

## Dependencies
- Feature packages (integrated before you start): growth-docs
- Declared in the plan: HUMAN:pro-catalog-decision, HUMAN:engine-stage3-scheduled, growth-docs, FIX:FINSEC-03, FIX:DB-06, FIX:DB-07, ENG:be-db-ledger. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.
- Owner prerequisites (do NOT block on them; build behind the flag and list them in human_actions): HUMAN:pro-catalog-decision, HUMAN:engine-stage3-scheduled

## Description
Wave 2. Start only after both of these:
- HUMAN:pro-catalog-decision is recorded in docs/billing/RUNBOOK.md §f as 'sell the tools';
- engine Stage 3 is scheduled (HUMAN:engine-stage3-scheduled).

This is the schema for the smaller version of feature 38.
- renews_at is reused as the App Store expiry, so FIX:FINSEC-13's lazy lapse works unchanged.
- There are no auto_renew or revoked_at columns. v1 has no renewal info and no webhook, and replay protection comes from subscription_events.

1. db_models.UserSubscription.
- Add four columns:
  - original_transaction_id = Column(String(64), nullable=True);
  - product_id = Column(String(100), nullable=True);
  - environment = Column(String(16), nullable=True);
  - app_account_token = Column(String(36), nullable=True), the lowercase uuid4 used as the StoreKit appAccountToken.
- Append to __table_args__:
  - UniqueConstraint('original_transaction_id', name='uq_user_subscriptions_original_txn');
  - UniqueConstraint('app_account_token', name='uq_user_subscriptions_app_account_token');
  - a CheckConstraint on `environment IN ('Production','Sandbox') OR environment IS NULL`, named ck_user_subscription_environment.
- Rewrite the class docstring:
  - no MOCK;
  - rows are App Store-verified by services/billing_service.py;
  - renews_at = the expiry of the latest verified transaction;
  - lapse is handled by subscription_service (FINSEC-13).
- Keep the tier CHECK as it is. super_pro stays a valid stored value but is never granted. No data migration.

2. New model SubscriptionEvent (__tablename__ 'subscription_events'), placed after UserSubscription.
- Columns:
  - id: Integer PK, autoincrement;
  - user_id: Integer ForeignKey('users.id'), nullable=True (so erasure can null it), index=True;
  - kind: String(16), not null;
  - transaction_id: String(64), not null;
  - original_transaction_id: String(64), not null;
  - product_id: String(100), not null;
  - environment: String(16), not null;
  - purchase_date: DateTime, not null;
  - expires_date: DateTime, nullable;
  - revocation_date: DateTime, nullable;
  - source: String(16), not null;
  - created_at: DateTime, default lambda: datetime.now(timezone.utc).
- __table_args__:
  - UniqueConstraint('transaction_id', 'kind', name='uq_subscription_events_txn_kind'), which also serves the revoked-event lookup;
  - Index('ix_subscription_events_original_txn', 'original_transaction_id');
  - a CheckConstraint on kind IN ('verified','revoked'), named ck_subscription_events_kind;
  - a CheckConstraint on source IN ('purchase','update','sync','restore'), named ck_subscription_events_source.
- Docstring: append-only; rows are never updated; datetimes are naive UTC.

3. Migration backend/migrations/versions/b7e2c91a4f06_add_app_store_billing.py ('Add App Store billing columns and subscription_events').
- revision 'b7e2c91a4f06'.
- down_revision = the head(s) reported by alembic heads at implementation time. Use a tuple if there are several. Today there are two (36e47c594dc7 and ec35eaf96b81), and fix-track migrations may land first.
- Upgrade follows the house idempotent inspector pattern (o8p9q0r1s2t3, t4u5v6w7x8y9):
  - in op.batch_alter_table('user_subscriptions'), add each missing column and create each missing constraint;
  - create subscription_events with its constraints and index if the table is missing.
- Downgrade drops subscription_events if present, then in batch mode drops the constraints and the four columns if present.
- Constraint names must match the model exactly, so alembic check stays clean.

4. compliance_service.ERASURE_POLICY (from FIX:FINSEC-03 or FIX:DB-06, whichever landed).
- Add 'subscription_events': 'null_user'. If the registry uses DB-06's wording, use 'nullify'.
- The financial event is kept without identity and holds no other personal data.
- user_subscriptions is already 'delete'. That also frees the originalTransactionId binding for a future account.

No API change.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the changed files.
2. FINSEC-03's test_every_user_fk_table_has_policy, or DB-06's equivalent, passes with the new table.
3. CI runs alembic upgrade head && alembic check cleanly.
4. Downgrading to the previous head and upgrading again succeeds. Extend TEST-11's migration test if it exists.
5. No other file changes.

## Cluster spec
docs/feature-specs/spec_growth.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
