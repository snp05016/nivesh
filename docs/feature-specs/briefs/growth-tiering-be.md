# Feature package growth-tiering-be: Honest tiering: PRO limited to the three enforced tools, an entitled_tier seam that defaults to the stored tier, honest beta copy

Cluster: growth (Monetization, growth and bold bets); area: mixed
Features covered: 41 I44 Honest tiering and a working paywall funnel

## Files (create or modify)
- backend/services/entitlement_service.py
- backend/core/entitlement_gate.py
- backend/routers/fundamentals.py
- backend/tests/test_entitlement_policy.py
- backend/tests/test_premium_gating.py
- backend/tests/test_entitlement_catalog.py
- ios/StockApp/stockme/stockme/Views/SubscriptionManagementView.swift

## Dependencies
- Feature packages (integrated before you start): growth-predictions-admin
- Declared in the plan: growth-predictions-admin, HUMAN:beta-comp-decision, FIX:AUTH-14, FIX:FINSEC-11, FIX:FINSEC-13, FIX:UX-11, FIX:UX-12, FIX:WIP-07, FIX:CMON-22, FIX:CMKT-14, FIX:REG-08, FIX:GH-662, ENG:be-serve-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.
- Owner prerequisites (do NOT block on them; build behind the flag and list them in human_actions): HUMAN:beta-comp-decision

## Description
Feature 41 is Simplify, and the fix track ships its smaller version. This package removes what would still be dishonest after that. It contains no billing code; billing_service arrives in wave 2.

HUMAN:beta-comp-decision does not block the build.
- The package ships the safe default: the stored tier (FIX:AUTH-14 option A).
- The decision only governs a later reviewed PR that uncomments the comp line in step 1.
- Why the comp is off: it would open sector rotation, the backtester and the options payoff builder to every signed-in user with no legal gate. Sector rotation's quadrant labels (Leading, Improving, Weakening, Lagging; services/sector_rotation.py:116, 231-243) are computed from recent prices. They can read as a sector signal under the 30-day price-data lag rule for unregistered persons.

1. backend/services/entitlement_service.py.
- Set FEATURE_MIN_TIER = {'sector_rotation': 'pro', 'technical_picks': 'pro', 'ideas_for_profit': 'pro'}, with this comment: 'Only tools may be sold. Stock reports are free (research engine §10.3). Adding a key needs the legal review in docs/billing/RUNBOOK.md §f (paywall copy and the tool outputs) and an update to test_entitlement_policy.'
- This removes comprehensive_stock_insights and swot_analysis. They gate company_valuations and risk_signals, tables nothing writes. advanced_analysis already left in growth-predictions-admin.
- Set FEATURE_TITLES to 'Sector rotation analytics', 'Strategy backtester', 'Options payoff builder'.
- Add this function after get_effective_tier:
```python
def entitled_tier(user_id: int) -> str:
    # Tier used by gates, quotas and GET /subscription/entitlements.
    # Pre-launch policy: the stored tier (FIX:AUTH-14 option A). growth-billing-be adds
    # the App Store branch above this comment. get_effective_tier stays the stored truth.
    # Beta comp (HUMAN:beta-comp-decision, docs/billing/RUNBOOK.md §f): enable only by a
    # reviewed PR after legal has reviewed the PRO tool outputs; that PR also updates
    # BetaPlanNotice and test_prelaunch_uses_stored_tier.
    # return 'pro'
    return get_effective_tier(user_id)
```
- Switch has_entitlement, get_all_entitlements and enforce_quota (FIX:CMON-22, if present) from get_effective_tier to entitled_tier. has_entitlement still returns False for an unknown key (AUTH-14).
- Update the module docstring.

2. backend/core/entitlement_gate.py.
- current_tier in the 402 detail comes from entitlement_service.entitled_tier(user_id).
- Keep AUTH-14's import-time ValueError for unknown keys.
- Keep the exact detail shape {message, required_tier, current_tier}, which FIX:UX-11 parses.

3. backend/routers/fundamentals.py.
- Four routes move from require_entitlement to Depends(require_auth) from helpers:
  - /fundamentals/{ticker}/valuation;
  - /fundamentals/{ticker}/risk-signals;
  - router_v1's GET /api/v1/fundamentals/valuation and /api/v1/fundamentals/risk-signals (ticker query, after FIX:CMKT-14).
- Their docstrings say: 'Not sold: nothing writes company_valuations or risk_signals yet, so this returns 404 or an empty list.'
- Remove the require_entitlement import.

4. ios/StockApp/stockme/stockme/Views/SubscriptionManagementView.swift.
- The BetaPlanNotice Text becomes 'PRO tools are not on sale yet. Paid plans will be offered through App Store in-app purchase.'
- The current 'All features are free during the beta' (line 205) is false with the stored-tier default, because PRO tools return 402 in Release.
- Update the comment above the struct. Nothing else changes.

5. Tests. Each test registers a fresh user through /register and /login, because the conftest user is shared across the session.
- New backend/tests/test_entitlement_policy.py:
  (a) test_prelaunch_uses_stored_tier.
    - For a fresh user, GET /api/v1/market/sector-rotation returns 402, with detail.required_tier 'pro' and detail.current_tier 'free'.
    - POST /api/v1/options/payoff with a minimal valid body returns 402.
    - GET /api/v1/subscription/entitlements shows tier 'free' and all three features false.
    - Then, through get_session(), set that user's row (created by the entitlements call) to tier 'pro', is_active True, renews_at now + 1 day.
    - A route mounted on a small in-test FastAPI app with Depends(require_entitlement('sector_rotation')) now returns 200. This is the FIX:GH-662 pattern, so no market data is fetched.
    - Entitlements now show all three features true.
    - Failure message: 'beta comp is off by default (RUNBOOK §f); turning it on needs a reviewed PR that updates this test'.
  (b) test_pro_catalog_is_reviewed_set: set(FEATURE_MIN_TIER) == {'sector_rotation', 'technical_picks', 'ideas_for_profit'}, with a failure message pointing to RUNBOOK §f.
  (c) test_unknown_key_fails_closed: has_entitlement(uid, 'no_such_key') is False.
  (d) test_research_routes_never_gated: for every APIRoute whose path starts with /api/v1/research, walk route.dependant.dependencies recursively. No dependency call may have a __qualname__ containing 'require_entitlement'. Skip if no such route is mounted.
  (e) test_valuation_and_risk_not_sold, for a fresh free user:
    - both valuation routes return 404 or 200, never 402;
    - both risk-signals routes return 200;
    - all four return 401 without a token.
- test_premium_gating.py: PREMIUM_ROUTES becomes {'/api/v1/market/sector-rotation': 'sector_rotation', '/api/v1/options/payoff': 'ideas_for_profit', '/api/v1/analysis/backtest': 'technical_picks', '/analysis/backtest': 'technical_picks'}. The fundamentals entries go.
- test_entitlement_catalog.py (FIX:UX-12): the expected key set and titles are the three above.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the backend files.
2. swiftc -parse passes on SubscriptionManagementView.swift.
3. grep finds no 'All features are free' in SubscriptionManagementView.swift.
4. grep finds no comprehensive_stock_insights or swot_analysis in backend/services or backend/routers.
5. These pass in CI: test_entitlement_policy.py (a) to (e), test_premium_gating.py, test_entitlement_catalog.py.
6. FINSEC-13's and CMON-22's tests still pass unchanged. entitled_tier equals get_effective_tier until growth-billing-be.

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
