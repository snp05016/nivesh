# Feature package data-schema: Data-foundation models, one idempotent Alembic migration and the erasure mapping

Cluster: data (Data foundation); area: backend
Features covered: I14, I15, I16, I18, I25

## Files (create or modify)
- backend/models/db_models.py
- backend/migrations/versions/05bf6cc1a533_data_foundation_tables.py
- backend/services/compliance_service.py
- backend/tests/migrations/test_data_foundation_migration.py
- backend/tests/test_data_models.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:be-db-ledger, FIX:FAKE-06, FIX:DB-08, FIX:DB-09, FIX:FINSEC-03, FIX:DB-06. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Migration identifiers:
- revision '05bf6cc1a533';
- down_revision is the single head at implementation time, found by static-parsing migrations/versions (today 'd4e5f6a7b8c9'; fix-track migrations land first);
- test_alembic_health::test_single_migration_head stays green.

Models go only in models/db_models.py. Add Date, BigInteger and text imports if missing. Append new classes and alter existing ones in place.

1) Instrument, table 'instruments'.
- Columns: id PK; asset_class String(8) NOT NULL; symbol String(30) NULL; isin String(12) NULL; isin_alt String(12) NULL; amfi_scheme_code String(20) NULL; entity_id String(24) NULL; name String(200) NOT NULL; series String(4) NULL; listing_date Date NULL; status String(10) NOT NULL (default and server_default 'active'); source String(16) NOT NULL; last_seen_on Date NULL; updated_at DateTime (default/onupdate now UTC).
- Checks: asset_class IN ('EQ','MF','INDEX') ck_instruments_asset_class; status IN ('active','inactive') ck_instruments_status.
- Unique: (asset_class, symbol) uq_instruments_class_symbol; (amfi_scheme_code) uq_instruments_amfi_code; (entity_id) uq_instruments_entity_id.
- Indexes: ix_instruments_isin, ix_instruments_isin_alt.

2) InstrumentAlias, table 'instrument_aliases'.
- Columns: id; instrument_id FK instruments.id CASCADE NOT NULL; kind String(8); value String(30); valid_to Date NULL; created_at.
- Check kind IN ('isin','symbol').
- UniqueConstraint(kind, value, instrument_id) uq_instrument_aliases_kind_value; Index ix_instrument_aliases_lookup(kind, value).

3) DailyPrice, table 'daily_prices'.
- Columns: instrument_id FK CASCADE and trade_date Date (composite PK); open/high/low Numeric(14,4) NULL; close Numeric(14,4) NOT NULL; prev_close Numeric(14,4); volume BigInteger; turnover_inr Numeric(20,2); trades Integer; source String(16) NOT NULL; event String(16) NULL (the engine's split/override/dividend/ca_unverified note); quality_flags String(40); ingested_at DateTime NOT NULL.
- Checks: source IN ('nse_bhavcopy','amfi','yfinance') ck_daily_prices_source; close > 0 ck_daily_prices_close_positive.
- Index ix_daily_prices_trade_date.

4) MutualFund adds: scheme_type String(16); is_active Boolean NOT NULL (default True, server_default '1'); track_nav Boolean NOT NULL (default False, server_default '0'); nav_source String(16); Index ix_mutual_funds_listing(is_active, scheme_type, is_direct_plan, is_growth_plan).

5) CorporateAction adds: action_type String(16); ex_on Date; ratio Numeric(12,6) (2.0 = 1 share became 2); source String(16); nse_confirmed Boolean; updated_at; plus Index('uq_corporate_actions_ticker_type_ex', 'ticker', 'action_type', 'ex_on', unique=True). Keep ex_date and purpose (CMKT-14 reads them).

6) CorporateActionApplication, table 'corporate_action_applications'.
- Columns: id; user_id FK users.id CASCADE NOT NULL; group_id FK portfolio_groups.id CASCADE NULL; corporate_action_id FK CASCADE NOT NULL; status String(12) NOT NULL default 'pending'; shares_before Numeric(18,6); transaction_id Integer NULL (no FK, because undo deletes that row); decided_at DateTime NULL; created_at DateTime NOT NULL.
- Check status IN ('pending','applied','dismissed') ck_ca_applications_status. There is no 'undone' status.
- Index('uq_ca_applications_user_action_group', 'user_id', 'corporate_action_id', text('coalesce(group_id, 0)'), unique=True). This is an expression index because Postgres treats NULLs as distinct.
- Index ix_ca_applications_user_status(user_id, status).

7) ResultsDigest, table 'results_digests'.
- Columns: id; symbol String(30) NOT NULL; period_end Date NOT NULL; filing_url String(500); filing_title String(300); announced_at; revenue_inr, net_profit_inr Numeric(20,2); eps Numeric(12,2); revenue_yoy_pct, net_profit_yoy_pct, eps_yoy_pct Float; numbers_source String(24); numbers_status String(12) NOT NULL default 'pending'; numbers_fetched_at; created_at NOT NULL; updated_at.
- Check numbers_status IN ('pending','ok','unavailable'); UniqueConstraint(symbol, period_end).

No ShareholdingPattern change (I17 is docs only).

8) services/compliance_service.py: add 'corporate_action_applications': 'delete' to ERASURE_POLICY (FINSEC-03/DB-06). If ERASURE_POLICY does not exist, stop and report.

Migration:
- Inspector pattern: create tables, columns and indexes only if absent, with SQLite-portable types matching the models.
- Booleans use server_default '1'/'0'.
- The expression index is created via op.create_index(..., ['user_id','corporate_action_id', sa.text('coalesce(group_id, 0)')], unique=True).
- Downgrade, guarded: drop corporate_action_applications, daily_prices, instrument_aliases, results_digests, instruments (in that order), then the added indexes, then the added columns via batch_alter_table.
- No seed rows.

## Acceptance checks
PYPARSE and PYRIGHT clean.

tests/migrations/test_data_foundation_migration.py (subprocess pattern from test_alembic_health.py, temp SQLite):
- upgrade head, downgrade -1 and upgrade head all return 0
- the 5 tables, the added columns (including daily_prices.event and corporate_action_applications.group_id) and both unique indexes exist

tests/test_data_models.py (in-memory SQLite, foreign_keys=ON):
- a duplicate (instrument_id, trade_date) raises IntegrityError
- asset_class 'XX', close 0 and status 'undone' violate their checks
- two MF instruments with NULL symbol coexist
- (user, action, group 1) and (user, action, group 2) coexist; a second (user, action, NULL group) row is rejected
- deleting an Instrument cascades to daily_prices
- ERASURE_POLICY maps the table to 'delete'

The FINSEC-03 erasure-mapping test and test_alembic_health stay green.

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
