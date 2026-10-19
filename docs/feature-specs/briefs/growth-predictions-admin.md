# Feature package growth-predictions-admin: Make the legacy QuantLab calibration dashboards admin-only and drop advanced_analysis from the PRO catalog

Cluster: growth (Monetization, growth and bold bets); area: backend
Features covered: 41 I44 Honest tiering and a working paywall funnel

## Files (create or modify)
- backend/routers/predictions.py
- backend/services/entitlement_service.py
- backend/tests/test_performance_claims_admin_only.py
- backend/tests/test_premium_gating.py
- backend/tests/test_quantlab_api.py
- backend/tests/test_quantlab_tdd.py
- backend/tests/test_prediction_calibration_api.py
- backend/tests/test_calibration_hardening.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:FINSEC-11, FIX:REG-11, FIX:AUTH-02, FIX:AUTH-14, FIX:UX-12, FIX:WIP-07. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Feature 41, delta 1.
Background:
- FIX:FINSEC-11 step 1 gates five legacy QuantLab calibration routes behind PRO ('advanced_analysis'). That would sell model calibration and performance data.
- FIX:REG-11 step 2 says user-facing hit-rate routes in predictions.py must be gated like /performance (require_admin).
- ENG §8.6 says users never see rates.
This package makes the five routes admin-only. It never widens access: before it, they return 402 to everyone in Release.

1. backend/routers/predictions.py.
Apply this to the five routes:
- get_predictions_calibration (GET /api/v1/predictions/calibration)
- get_predictions_pillar_attribution (/api/v1/predictions/pillar-attribution)
- get_predictions_model_versions (/api/v1/predictions/model-versions)
- get_calibration_readiness_health (/api/v1/predictions/calibration/health)
- get_fusion_weight_recommendations_endpoint (/api/v1/predictions/fusion-weight-recommendations)
On each:
- Set the dependency to `user_id: int = Depends(require_admin)`. Use the same require_admin object that /performance imports after FIX:REG-11 (core.security.require_admin).
- Above the decorator, add the comment `# internal QuantLab metric; never sold, never user-facing (REG-11, ENG §8.6)`.
- Make the docstring say 'Admin only.'
Then remove the require_entitlement and require_auth imports if nothing else in the file uses them.

2. backend/services/entitlement_service.py.
- First grep backend/routers for advanced_analysis. After step 1 and REG-11, no route may use it. If one still does, stop and report: FIX:AUTH-14 makes require_entitlement raise ValueError at import for an unknown key.
- Delete 'advanced_analysis' from FEATURE_MIN_TIER and from FEATURE_TITLES (FIX:UX-12).

3. Tests. Edit only files that exist, except the first file below.
- backend/tests/test_performance_claims_admin_only.py (created by FIX:REG-11; create it if absent). Add test_quantlab_dashboards_admin_only.
  - Parametrise it over the five paths, and over BILLING_ENABLED unset and set to 'true' (monkeypatch.delenv / setenv).
  - BILLING_ENABLED has no reader until growth-billing-be. The two cases lock the rule for both future states.
  - With no Authorization header: 401.
  - With auth_headers (a non-admin free user): 403, with detail 'Admin access required'.
  - With admin_headers (a real admin since FIX:AUTH-02): 200.
- test_premium_gating.py (FINSEC-11):
  - Remove every /api/v1/predictions/* entry from PREMIUM_ROUTES.
  - Replace test_free_user_gets_402_on_calibration with test_non_admin_gets_403_on_calibration (a fresh user gets 403).
- test_quantlab_api.py: the calibration, pillar-attribution and model-versions calls use admin_headers instead of auth_headers.
- test_quantlab_tdd.py:
  - The calibration and pillar-attribution calls use admin_headers. AUTH-02 replaced 'Bearer admin' with auth_headers.
  - Keep the assertions that a missing token gives 401.
- test_prediction_calibration_api.py and test_calibration_hardening.py:
  - Their authed_client fixture overrides only helpers.require_auth.
  - Also set `app.dependency_overrides[require_admin] = lambda: MOCK_USER_ID`, keyed on the require_admin object that predictions.py imports.
  - Tests that expect 401 for a missing or invalid token must run without these overrides.
- test_ios_endpoints.py needs no change. require_admin calls require_auth first, so unauthenticated requests still get 401.

No iOS change. QuantLab's three calibration panels (QuantLabViewModel.fetchCalibration, fetchPillarAttribution, fetchModelVersions) will show their own per-panel error for non-admins. They already do that with FINSEC-11's 402.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the changed files.
2. grep -rn advanced_analysis backend/routers backend/services returns nothing.
3. test_quantlab_dashboards_admin_only passes. For all five routes:
- no token gives 401;
- a non-admin gets 403, with BILLING_ENABLED unset and with it set to 'true';
- an admin gets 200.
4. These pass in CI: test_premium_gating.py, test_quantlab_api.py, test_quantlab_tdd.py, test_prediction_calibration_api.py, test_calibration_hardening.py, test_ios_endpoints.py.

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
