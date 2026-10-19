# Feature package growth-billing-mock-removal: Delete the mock upgrade and cancel routes and functions

Cluster: growth (Monetization, growth and bold bets); area: backend
Features covered: 38 I43 Real billing with StoreKit 2, 41 I44 Honest tiering and a working paywall funnel

## Files (create or modify)
- backend/services/subscription_service.py
- backend/routers/subscription.py
- backend/.env.example
- backend/tests/test_entitlements_fail_closed.py
- backend/tests/test_subscription_lifecycle.py
- backend/tests/test_audit_trail.py
- backend/tests/test_subscription_compliance_api.py
- backend/tests/test_money_control_contracts.py
- backend/tests/test_predictions_performance.py
- backend/tests/test_tier_quotas.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:AUTH-14, FIX:FINSEC-13, FIX:FINSEC-22, FIX:REG-08, FIX:REG-11, FIX:AUTH-02, FIX:GH-662, FIX:TEST-10, FIX:CMON-22. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Roadmap §38's smaller version says '/upgrade deleted'. FIX:AUTH-14 only hid it behind ALLOW_MOCK_PURCHASES.
Release is already fail-closed: AUTH-14 returns 404 and REG-08 hides the purchase UI. So deleting the mock needs no replacement and does not wait for StoreKit. It removes the risk that a misconfigured env grants free PRO.

1. services/subscription_service.py.
- Delete:
  - mock_upgrade and mock_cancel;
  - _MONTHLY_DELTA and _ANNUAL_DELTA;
  - VALID_BILLING_CYCLES, if nothing else uses it;
  - AUTH-14's ALLOW_MOCK_PURCHASES guard;
  - the FINSEC-22 audit calls inside the deleted functions.
- Keep these unchanged:
  - VALID_TIERS;
  - get_or_create_subscription, with FINSEC-13's lapse, the IntegrityError handling and the 'subscription_lapsed' audit;
  - _to_dict.
- Docstring: this module reads, lazily creates and lapses the row; paid tiers will come only from App Store verification (docs/billing/RUNBOOK.md).

2. routers/subscription.py.
- Delete UpgradeRequest, POST /upgrade and POST /cancel.
- Drop MOCK from the docstring.
- GET '' and GET /entitlements are unchanged.

3. backend/.env.example: remove AUTH-14's ALLOW_MOCK_PURCHASES block.

4. Tests. Edit only files that exist.
- First run `grep -rnE 'mock_upgrade|mock_cancel|subscription/(upgrade|cancel)|ALLOW_MOCK_PURCHASES' backend/tests` and fix every hit, including files not listed here.
- Where a test needs a PRO user, create the row with get_or_create_subscription (user_id is UNIQUE), then set it through get_session(): tier 'pro', billing_cycle 'monthly', is_active True, renews_at now + 30 days.
- test_entitlements_fail_closed.py (AUTH-14):
  - keep case (a): POST /upgrade returns 404 and the tier stays free;
  - delete case (b);
  - keep cases (c) to (e);
  - add test_cancel_route_gone: POST /api/v1/subscription/cancel returns 404;
  - add test_no_mock_purchase_code: no 'mock_upgrade', 'mock_cancel' or 'ALLOW_MOCK_PURCHASES' appears in backend/**/*.py outside backend/tests.
- test_subscription_lifecycle.py (FINSEC-13):
  - delete the tests that call mock_upgrade or mock_cancel (repeat upgrade, cancel then upgrade, upgrade to free returns 422);
  - keep the lapse and IntegrityError tests, seeding rows through the ORM.
- test_audit_trail.py (FINSEC-22): drop the plan-upgrade step and its 'subscription_upgraded' assertion.
- test_subscription_compliance_api.py (GH-662): the 402-then-200 gate check seeds PRO through the ORM instead of POST /upgrade.
- test_money_control_contracts.py (TEST-10), entitlement block:
  - replace the POST /upgrade and /cancel steps with ORM seeding: pro, then is_active False with a future renews_at, then a past renews_at, which gives 402;
  - keep whichever route REG-11 left that test using.
- test_predictions_performance.py (AUTH-02 fixture): replace the mock_upgrade fixture with admin_headers, since /performance is admin-only after REG-11.
- test_tier_quotas.py (CMON-22): test_pro_user_higher_cap seeds PRO through the ORM.

The iOS Debug-only mock purchase buttons (REG-08) now get 404 in Debug builds. growth-billing-ios-ui deletes them. If wave 2 is cancelled, RUNBOOK §h describes the standalone cleanup.

## Acceptance checks
1. grep -rnE 'mock_upgrade|mock_cancel|ALLOW_MOCK_PURCHASES' backend --include=*.py finds nothing outside backend/tests. test_no_mock_purchase_code enforces this.
2. POST /api/v1/subscription/upgrade and /cancel return 404.
3. GET /api/v1/subscription and /entitlements still return 200.
4. PYPARSE and PYRIGHT are clean.
5. The updated tests pass in CI.

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
