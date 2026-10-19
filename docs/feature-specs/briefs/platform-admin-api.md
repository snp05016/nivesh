# Feature package platform-admin-api: Admin API for flags, job runs, audit and usage, plus audit rows on every user-level admin read

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 60 I46 Admin console v2, 30 I08 Observability baseline, 36 I47 First-party product analytics

## Files (create or modify)
- backend/routers/admin_ops.py
- backend/services/audit_service.py
- backend/routers/admin_dashboard.py
- backend/routers/user.py
- backend/routers/dashboard.py
- backend/main.py
- backend/tests/test_admin_ops.py

## Dependencies
- Feature packages (integrated before you start): platform-events-api, platform-flags, platform-jobruns
- Declared in the plan: platform-flags, platform-jobruns, platform-events-api, FIX:FINSEC-22, FIX:REL-15, FIX:GH-689, FIX:AUTH-01, FIX:AUTH-02, FIX:REL-11, FIX:REL-08. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I46 delta plus admin views for I08 and I47.

Every route is a plain def that starts with admin_id = require_admin(authorization). require_admin checks users.is_admin (FIX:AUTH-01). Responses are JSON, and timestamps are ISO-8601 with a trailing Z.

Contract shared with platform-admin-ui (all paths under /api/v1/admin):
- GET /flags returns {'flags': [feature_flags.list_flags() entries]}.
- PUT /flags/{key}, body {'enabled': bool}:
  - returns {'flag': entry};
  - unknown key: 404 'Unknown flag';
  - in the same request, write audit row 'admin_flag_changed' with {'key', 'from', 'to'}.
- GET /job-runs?job_name=&status=&limit=50&before_id=
  - returns {'runs': job_runs.list_runs(...), 'next_before_id': ...};
  - next_before_id is the smallest id when a full page was returned, else null.
- GET /job-runs/summary?days=7 (days 1..90) returns job_runs.summary(days).
- GET /audit?action_prefix=admin_&limit=100&before_id=
  - returns {'entries': [{'id', 'actor_user_id', 'action', 'details', 'created_at', 'ip_address'}], 'next_before_id'};
  - limit 1..200;
  - action_prefix is optional, max 40 chars.
- GET /analytics/daily?days=14 (days 1..31) returns events_service.daily_counts(days): {'days', 'active_users', 'rows'}.

1. routers/admin_ops.py: the routes above, with prefix '/api/v1/admin' and tags ['Admin']. Keep them thin; they call feature_flags, job_runs, events_service and audit_service.

2. services/audit_service.py (FIX:FINSEC-22):
- Add audit_now(user_id, action, details=None, *, min_interval_s=0).
  - Open get_session(), call audit(...) and commit. Let exceptions propagate: this fails closed, so if no audit row is written, no data is returned.
  - When min_interval_s > 0 and this process wrote the same (user_id, action, json.dumps(details, sort_keys=True, default=str)) within min_interval_s seconds, return without writing.
  - Keep the timestamps in a module dict guarded by a threading.Lock, and clear the dict when it exceeds 1000 keys. Record the time only after a successful write.
  - Comment: 'ponytail: per-process throttle; correct for the single worker (FIX:REL-08); move to Redis if workers > 1'.
- Add list_entries(action_prefix=None, limit=100, before_id=None) -> list[dict].

3. Audit every user-level admin read. Call audit_now before building any data:
- GET /dashboard-user-data (routers/admin_dashboard.py after FIX:REL-15): 'admin_viewed_user' with {'target_user_id': user_id}.
- GET /dashboard-data/analysis/{analysis_id} (FIX:GH-689; edit it wherever it lives): 'admin_viewed_analysis' with {'analysis_id': id}.
- GET /users (routers/user.py): 'admin_listed_users' with {}.
- GET /api/v1/admin/error-telemetry (routers/user.py): 'admin_viewed_error_telemetry' with {}.
- GET /api/v1/dashboard/ai-engine (routers/dashboard.py, list): 'admin_listed_jobs' with {'filters': <the route's query parameters>} and min_interval_s=900. The console polls this list every 10 s (loadAIEngine, main.py:1665), and unthrottled auditing would write 360 rows an hour. If ENG:be-cutover has removed the route, skip it.
- GET /api/v1/dashboard/ai-engine/{job_id} (routers/dashboard.py): 'admin_viewed_job' with {'job_id': job_id}.
- Do not audit /dashboard-data, which is a polled aggregate, or the audit list itself.

4. main.py: include admin_ops.router.

## Acceptance checks
- AST parse and pyright are clean.
- tests/test_admin_ops.py passes in CI. It uses the admin_headers fixture from FIX:AUTH-02 and auth_headers for a normal user. Cases:
  - Every new route returns 401 without a token and 403 for a non-admin.
  - PUT on a flag flips is_enabled and writes exactly one admin_flag_changed row with from/to.
  - PUT on an unknown key returns 404.
  - job-runs pagination and filters work over seeded rows.
  - The summary counts are correct.
  - The audit list filters by prefix and paginates.
  - analytics daily returns rows and active_users for seeded events.
  - Each audited read writes exactly one row with the right action and target.
  - Two GET /api/v1/dashboard/ai-engine calls with the same filters within 15 minutes write one 'admin_listed_jobs' row; a call with a different filter writes a second.
  - With audit_now monkeypatched to raise, the read returns 500 and the response contains no user data.

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
