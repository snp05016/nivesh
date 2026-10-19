# Feature package platform-admin-ui: Admin console Flags, Jobs, Audit and Usage pages

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 60 I46 Admin console v2, 30 I08 Observability baseline, 36 I47 First-party product analytics

## Files (create or modify)
- backend/static/admin/index.html
- backend/static/admin/admin.js
- backend/tests/test_admin_ui_static.py

## Dependencies
- Feature packages (integrated before you start): platform-admin-api
- Declared in the plan: platform-admin-api, FIX:AUTH-19, FIX:AUTH-02, FIX:REL-15. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Adds the I46 console pages to the static admin built by FIX:AUTH-19, FIX:AUTH-02 and FIX:REL-15. That admin lives in backend/static/admin/index.html and admin.js. It provides adminFetch(url, opts) and esc(v), plus a delegated listener that maps data-action values to functions and passes them the element.

1. index.html:
- Add four nav tabs: <button class='nav-tab' data-action='showPage' data-arg='flags|jobs|audit|usage'>, labelled Flags, Jobs, Audit and Usage.
- Add four matching sections, <div class='page' id='page-flags|page-jobs|page-audit|page-usage'>, using the existing card, card-header and card-body classes:
  - Flags: table#flags-table and div#flags-msg.
  - Jobs: table#jobs-summary with the overall success %, and table#jobs-failures for the last 20 failed runs.
  - Audit: table#audit-table and a 'Load older' button with data-action='loadAuditOlder'.
  - Usage: table#usage-table, span#usage-active-users labelled 'Active users with analytics on', and the note 'Counts only users who turned on usage analytics.'
- No inline handlers and no inline script.

2. admin.js:
- showPage(name) activates the tab whose data-arg matches; replace the hard-coded navMap if it is still present. For the four new pages it calls loadFlags, loadJobs, loadAudit or loadUsage.
- loadFlags renders each flag's key, description, ON/OFF state and source, plus a button with data-action='toggleFlag', data-arg=esc(key) and data-enabled='1' or '0'.
- toggleFlag(el):
  - asks confirm('Turn ON|OFF <key> for all users?');
  - sends a PUT with JSON {'enabled': bool} and Content-Type application/json;
  - shows the HTTP status on failure;
  - reloads the table.
- loadJobs fetches /api/v1/admin/job-runs/summary?days=7 and /api/v1/admin/job-runs?status=failed&limit=20.
- loadAudit(older) pages with before_id.
- loadUsage fetches /api/v1/admin/analytics/daily?days=14 and shows active_users.
- Every server string goes through esc(). Numbers use the existing formatters. Errors show 'Could not load (<status>)'.

## Acceptance checks
tests/test_admin_ui_static.py passes in CI and checks:
- index.html has the four page ids and four nav tabs with data-action='showPage';
- index.html has no ' on[a-z]+=' attributes and no inline <script> body;
- index.html contains 'Active users with analytics on';
- admin.js references the five admin endpoints and reads active_users;
- every interpolation in the new render functions is wrapped in esc() (assert specific esc(...) usages for flag keys, job names, audit actions and event names);
- toggleFlag contains a confirm( call.
Manual browser check after deploy: the console shows no CSP violations and the new pages load.

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
