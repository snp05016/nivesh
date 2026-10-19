# Feature package platform-privacy-export: GET /api/v1/compliance/my-data JSON export with owner-column filtering, stored-data groups, non-FK user columns in erasure, DPDP runbook

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 28 I06 Privacy center: erasure, export, consent

## Files (create or modify)
- backend/services/privacy_export.py
- backend/routers/compliance.py
- backend/services/compliance_service.py
- backend/core/rate_limiter.py
- backend/tests/test_privacy_export.py
- docs/compliance/DPDP_RUNBOOK.md

## Dependencies
- Feature packages (integrated before you start): platform-events-api, platform-events-db
- Declared in the plan: platform-events-api, platform-events-db, FIX:FINSEC-03, FIX:DB-06, FIX:FINSEC-22, FIX:FINSEC-04, FIX:FINSEC-09, FIX:DB-10, FIX:LLM-02, FIX:WIP-05, ENG:be-db-ledger. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I06 delta. platform-ios-flags-events and platform-ios-privacy-center build against this contract.

Contract: GET /api/v1/compliance/my-data, Bearer required.
- Not behind a flag: it is the DPDP s.11 access right, like FINSEC-03's delete. A faulty export is fixed with a backend hotfix.
- 200: application/json with Content-Disposition attachment; filename='nivesh-my-data-YYYY-MM-DD.json' (IST date) and Cache-Control no-store.
- 404 {'detail': 'Not available'} only when the user row is missing or deleted.
- 429 after 5 exports in 24 h for the user.
- 401 without a valid token.
- Body: {'schema_version': 'nivesh-export.v1', 'generated_at': ISO-Z, 'user': {users row without secrets}, 'tables': {table_name: {'group': row text, 'rows': [...], 'truncated': bool}}, 'purposes': CONSENT_PURPOSES, 'processors': PROCESSORS, 'notes': [...]}.

1. services/privacy_export.py: build_user_export(user_id) -> dict.
- Load the users row. Raise LookupError if it is missing or deleted_at is set.
- user_columns(table): the columns with a ForeignKey to users.id, plus that table's column from compliance_service.EXTRA_USER_COLUMNS.
- EXPORT_OWNER_COLUMN: dict[str, str] = {'user_blocks': 'blocker_user_id'}.
- Owner column per table: the EXPORT_OWNER_COLUMN entry if present, else the single user column. A table with two or more user columns and no entry is skipped with a logged warning; test (b) below fails for it first. Skip tables with no user column.
- Walk Base.metadata.sorted_tables, excluding users. For each table, select rows where owner_column == user_id only, never 'any user column'. Order by primary key descending, with limit ROW_CAP + 1 (ROW_CAP = 5000). Set truncated when the extra row comes back.
- In every output row, set each user column other than the owner column to None. A user therefore never sees who blocked or reported them, and a blocker's export shows the block without the blocked user's id.
- Convert row values:
  - datetime and date to isoformat; naive values get a 'Z';
  - Decimal to str;
  - bytes and memoryview to the string '<omitted: binary>';
  - str longer than 20000 chars cut, ending in '...[truncated]'.
- Drop SECRET_COLUMNS: password_hash, token_version, refresh_token_hash.
- Columns named 'token' or ending in '_token' keep only their last 4 characters, prefixed by '...'.
- STORED_DATA_ROWS: a tuple of the seven 'WHAT WE STORE' strings, exactly as platform-ios-privacy-center shows them:
  1 'Your account: username, display name, settings and subscription'
  2 'Holdings, transactions, watchlists, alerts and journal notes you add, and the values and tax reports we calculate from them'
  3 'Loan, deposit, bank-account and finance-tracker records, if you use those features'
  4 'Posts, votes, reports and blocks in the community forum'
  5 'Your device ID and push token, your consent choices and security records, with the IP address on them'
  6 'Your notifications, analyses and AI research requests'
  7 'Usage events, only if you turn on usage analytics'
- TABLE_GROUPS: dict[str, int] maps every exported table to a row number (users itself is row 1):
  - 1: user_preferences, user_subscriptions;
  - 2: portfolio, portfolio_groups, portfolio_transactions, multi_asset_transactions, watchlists, price_targets, earnings_alerts, trade_journal, dividend_ledger, tax_reports, portfolio_valuation_history, net_worth_ledger;
  - 3: linked_bank_accounts, loan_applications, loan_disbursements, fixed_deposit_bookings, finance_tracker_accounts;
  - 4: forum_threads, forum_posts, forum_votes, forum_reports, user_blocks;
  - 5: device_tokens, device_bindings, device_binding_attempts, kyc_consents, audit_log_entries, data_deletion_requests;
  - 6: in_app_notifications, analysis_history, analysis_jobs, research_reports, llm_usage;
  - 7: user_events.
  Each table's export entry carries 'group': STORED_DATA_ROWS[n - 1].
- PROCESSORS is a structured constant. Each entry has name, country, purpose, data and legal_basis:
  - DeepSeek (PRC): AI text for AI features, only with the 'ai_processing' consent; shares tickers, company names, percentage moves and chat text; basis 'consent'.
  - Anthropic (USA): same as DeepSeek.
  - Apple Push Notification service (USA): push delivery; shares the device token and notification text; basis 'consent'.
  - 'Operations alert relay (owner-chosen)':
    - country: 'depends on the relay the owner configures; a self-hosted relay keeps it in India';
    - purpose: 'alerting the operator when a scheduled job fails';
    - data: 'scrubbed error text only, at most 300 characters';
    - legal_basis: 'not applicable: no personal data is intended; errors are scrubbed before sending'.
- notes explain retention:
  - backups keep data up to 14 days after erasure;
  - consent and audit records are kept after erasure without IP;
  - usage events are deleted when usage analytics is turned off.

2. services/compliance_service.py
- Add EXTRA_USER_COLUMNS: dict[str, tuple[str, str]] = {'research_reports': ('requested_by_user_id', 'null_user'), 'llm_usage': ('user_id', 'null_user')}. These are user-linked columns without a FK (ENG:be-db-ledger, FIX:LLM-02).
- In erase_user (FIX:FINSEC-03), after the FK tables and before tombstoning, apply each entry whose table exists in Base.metadata:
  - 'null_user': UPDATE table SET column = NULL WHERE column = user_id;
  - 'delete': DELETE those rows.

3. routers/compliance.py: GET /my-data, plain def, user_id = Depends(require_auth).
- Call _check_rate_limit(f'user:{user_id}', 'privacy_export').
- Build the export.
- In one session, call audit_service.audit(session, user_id, 'data_exported', {'tables': n, 'rows': m}) (FIX:FINSEC-22) and commit.
- Return a JSONResponse with the headers above. Map LookupError to 404.
- There is no flag check.

4. core/rate_limiter.py: add _RATE_LIMITS['privacy_export'] = {'window': 86400, 'max_requests': 5}.

5. docs/compliance/DPDP_RUNBOOK.md, with these sections:
- Scope and dates:
  - the Act (2023) and the Rules G.S.R. 846(E) of 13 Nov 2025;
  - Rules 3, 5-16, 22 and 23 (including 6, 7, 8 and 14) apply from 13 May 2027 under the 18-month tranche;
  - MeitY has proposed shortening that window; 12 months would mean 13 Nov 2026. Nothing has been notified as of Oct 2026, so confirm in the Gazette.
- Rights handling:
  - access: in-app export, with a manual fallback by email;
  - correction: profile edit;
  - erasure: in-app delete per FINSEC-03, plus what is retained;
  - consent withdrawal: toggles enforced by the server immediately; analytics events are erased on withdrawal and by the daily backstop;
  - grievance contact and response time: left for the owner to fill in.
- Breach response per Rule 7:
  - detect through OPS alerts, job_runs and logs; contain; assess;
  - tell affected users without delay, in plain language, through the in-app inbox or push;
  - tell the Data Protection Board without delay;
  - send the Board a detailed report within 72 h of becoming aware, covering nature, extent, timing, location, likely impact, causes, mitigation, findings on the responsible party, and the notices sent;
  - an incident-log template.
- Rule 8(3) retention decision:
  - What the rule says: a fiduciary keeps personal data, associated traffic data and processing logs for at least one year from processing, for the Seventh Schedule purposes, then erases them unless another law requires retention.
  - (a) Narrow reading: the floor binds only processing for Seventh Schedule purposes (State uses, legal obligations, SDF assessment). user_events keep USER_EVENTS_RETENTION_DAYS=180 and are erased on withdrawal; this is what is built.
  - (b) Broad reading: a one-year floor for all personal data and logs. Set USER_EVENTS_RETENTION_DAYS=365. Change on_consent_withdrawn to set event_name to 'withdrawn' (and props to null) instead of deleting; exclude those rows from ingest counts, daily_counts and QUERIES.md; delete them once a year has passed.
  - Either way, audit_log_entries and access logs are kept for at least one year, including rows of users erased under FINSEC-03.
  - A 'Decision' line for the owner and legal: reading, date and signer.
- Retention schedule:
  - user_events: USER_EVENTS_RETENTION_DAYS (180 d by default), and erased on withdrawal;
  - job_runs: 90 d;
  - news: 90 d;
  - backups: 14 d;
  - audit_log_entries and access logs: at least 1 year (Rules 6 and 8(3));
  - kyc_consents: kept.
- Processors list, mirroring PROCESSORS, including the operations alert relay.

## Acceptance checks
- AST parse and pyright are clean.
- tests/test_privacy_export.py passes in CI:
  - The export of a seeded user has their portfolio and kyc_consents rows and none of another user's rows.
  - User B blocks user A. A's export has tables['user_blocks']['rows'] == [], and no column named user_id or ending in _user_id anywhere in A's export equals B's id. B's export contains the block row with blocked_user_id None.
  - No password_hash or token_version appears anywhere.
  - The device token is masked.
  - Long text is truncated.
  - With ROW_CAP monkeypatched to 2, truncated is true.
  - Every table with a users FK appears without raising, and each carries a 'group' from STORED_DATA_ROWS; empty rows are allowed.
  - The export works with no feature_flags rows and with FEATURE_ANALYTICS=0.
  - The sixth export within 24 h gives 429.
  - A 'data_exported' audit row is written.
  - The Content-Disposition header is present.
  - PROCESSORS contains the operations alert relay.
  - Completeness guards, each failure naming the table or column:
    (a) every column in Base.metadata named user_id or ending in _user_id that has no FK to users is listed in EXTRA_USER_COLUMNS;
    (b) every table with two or more user columns has an EXPORT_OWNER_COLUMN entry naming one of them;
    (c) every exported table has a TABLE_GROUPS entry in 1..7. The failure message says: add it to TABLE_GROUPS; if no row describes it, add a row here and in PrivacyCenterView.swift;
    (d) if ios/StockApp/stockme/stockme/Views/PrivacyCenterView.swift exists (resolved from the repository root, Path(__file__).resolve().parents[2]), it contains each STORED_DATA_ROWS string; otherwise the test is skipped.
  - erase_user nulls research_reports.requested_by_user_id, and llm_usage.user_id when that table exists.
- FINSEC-03's existing erasure tests still pass.
- DPDP_RUNBOOK.md contains a 'Rule 8(3)' section with both readings and a Decision line.

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
