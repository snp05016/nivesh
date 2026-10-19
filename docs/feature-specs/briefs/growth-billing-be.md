# Feature package growth-billing-be: Billing service and routes: launch flag, verified entitlement, status, signed-transaction verification with revoked-replay protection, health

Cluster: growth (Monetization, growth and bold bets); area: backend
Features covered: 38 I43 Real billing with StoreKit 2, 41 I44 Honest tiering and a working paywall funnel

## Files (create or modify)
- backend/services/billing_service.py
- backend/routers/billing.py
- backend/services/entitlement_service.py
- backend/services/subscription_service.py
- backend/routers/subscription.py
- backend/main.py
- backend/core/rate_limiter.py
- backend/routers/health.py
- backend/.env.example
- backend/tests/test_billing_api.py

## Dependencies
- Feature packages (integrated before you start): growth-billing-db, growth-billing-jws, growth-billing-mock-removal, growth-tiering-be
- Declared in the plan: growth-billing-db, growth-billing-jws, growth-tiering-be, growth-billing-mock-removal, FIX:AUTH-14, FIX:FINSEC-13, FIX:FINSEC-22, ENG:be-ingest-jobs, ENG:be-wiring. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Wave 2. The HUMAN gates are carried by growth-billing-db and growth-billing-jws.
This is the smaller version of feature 38: one auto-renewable PRO product, verified at purchase from StoreKit 2 signed transactions.
Out of scope here (follow-ups in RUNBOOK §h): the Server Notifications webhook and any App Store Server API call.
There is no flag module and no /app/config route. billing_service reads BILLING_ENABLED itself, following the project's per-feature env pattern (services/youtube_summary/summarizer.py:22; FIX:REG-02 advisory_guard).

1. backend/services/billing_service.py. Read all env at call time; never raise at import.
- _TRUE = frozenset({'1', 'true', 'yes', 'on'}).
- flag_on() -> bool: os.getenv('BILLING_ENABLED', '').strip().lower() in _TRUE. This is the owner's launch switch.
- products() -> dict[str, str]: parses APPLE_IAP_PRODUCTS as 'id:cycle,id:cycle'. cycle must be monthly or annual; malformed entries are skipped.
- allowed_environments() -> set[str]: from APPLE_ALLOWED_ENVIRONMENTS, default 'Production,Sandbox'. Sandbox is needed for App Review and TestFlight.
- bundle_id(): APPLE_BUNDLE_ID.
- terms_url() and privacy_url(): NIVESH_TERMS_URL and NIVESH_PRIVACY_URL, or None unless the value starts with https://.
- _legacy_retired() -> bool:
  - import services.research.config inside try/except Exception;
  - return True only when the engine's effective LEGACY_RETIRED, as exposed by ENG:be-ingest-jobs, is true;
  - never re-read RESEARCH_* env vars;
  - this latches, because the engine never unsets LEGACY_RETIRED.
- _root_der() -> bytes | None: apple_jws.load_root_der(), or None on InvalidJWS. No cache: reading a file of about 1 KB per call is cheap, and a fixed cert file takes effect without a restart.
- config_problems() -> list[str]: any of 'legacy_analysis_not_retired', 'apple_bundle_id_missing', 'apple_products_missing', 'legal_urls_missing', 'apple_root_ca_invalid'.
- billing_enabled() -> bool: flag_on() and not config_problems(). When the flag is on and problems exist, log CRITICAL with the problem names whenever the set differs from the last one logged (keep a module-level tuple).
- entitlement(user_id) -> dict with keys tier, source, product_id, expires_at, environment.
  - It is used whenever flag_on() is true, regardless of config_problems(), so a config problem after launch never gives anyone free PRO.
  - sub = subscription_service.get_or_create_subscription(user_id), which self-heals lapsed rows (FIX:FINSEC-13).
  - If sub['tier'] != 'free' and sub['original_transaction_id'] is set: {'tier': 'pro', 'source': 'app_store', 'product_id': ..., 'expires_at': renews_at formatted as YYYY-MM-DDTHH:MM:SSZ in UTC, 'environment': ...}.
  - Otherwise: {'tier': 'free', 'source': 'none'}, with the other keys None.
  - Legacy mock rows without an original_transaction_id (#666) therefore never grant access once launched.
- get_status(user_id) -> dict, following the contract below.
  - Pre-launch: everything empty, and entitlement None.
  - Launched: entitlement(user_id).
  - When billing_enabled() is also true: the products, the URLs and the app_account_token. If the row has no token, set str(uuid.uuid4()) and commit.
  - When it is false: token None, products [], URLs None.
- class BillingError(Exception) with code, status_code and message.
- apply_signed_transaction(user_id, signed_transaction, source) -> dict:
  (1) Gate.
    - If not flag_on(): BILLING_DISABLED 404.
    - If config_problems() has anything other than 'legal_urls_missing': BILLING_UNAVAILABLE 503.
    - Missing legal URLs hide the paywall, because App Review 3.1.2 needs them on the purchase screen. They must not stop verifying renewals for people already paying.
  (2) claims = apple_jws.verify_signed_payload(signed_transaction, root_der=_root_der()). InvalidJWS becomes INVALID_SIGNATURE 400.
  (3) Check the claims:
    - bundleId must equal bundle_id(), else INVALID_SIGNATURE;
    - environment must be in allowed_environments(), else INVALID_SIGNATURE;
    - type must be 'Auto-Renewable Subscription' and productId must be in products(), else UNSUPPORTED_PRODUCT 422;
    - a missing expiresDate gives INVALID_SIGNATURE.
  (4) Binding. Open one get_session(). Load the caller's UserSubscription with .with_for_update(), creating a free row if it is missing.
    - Raise ACCOUNT_MISMATCH 409 ('This App Store subscription is linked to another Nivesh account.') when another user's row has app_account_token equal to the lowercased claims.appAccountToken.
    - Raise the same error when another user's row has this originalTransactionId.
    - A token that matches no row (its account was erased) is accepted, so a still-active subscription can be linked to a new account.
  (5) Record the event. Add SubscriptionEvent with:
    - kind 'revoked' if revocationDate is present, else 'verified';
    - the transaction ids, product and environment;
    - purchase, expires and revocation dates as naive UTC from ms epoch;
    - source.
    Then flush. An IntegrityError means a replay or a concurrent duplicate: roll back and return get_status(user_id).
  (6) Apply the state.
    - Revoked-replay check first: if kind is 'verified' and a SubscriptionEvent with kind 'revoked' and the same transaction_id exists, commit (so the event is recorded) and return get_status(user_id). No state change and no audit. This stops a pre-refund JWS posted after the refund from granting PRO again.
    - Otherwise, always set original_transaction_id, product_id and environment.
    - billing_cycle = products()[productId].
    - started_at = started_at or originalPurchaseDate.
    - is_active = True and cancelled_at = None.
    - Revoked: renews_at = min(existing renews_at, revocationDate), or revocationDate if there is none. The row lapses on the next read.
    - Not revoked, expiresDate > now, and (renews_at is None or expiresDate > renews_at): tier = 'pro' and renews_at = expiresDate.
    - Expired, non-revoked transactions are recorded with no access change.
    - Add the comment '# ponytail: a revocation cuts the whole original transaction; per-transaction tracking if refunds of older periods appear'.
  (7) Audit and commit.
    - Call audit_service.audit(session, user_id, 'subscription_verified' or 'subscription_revoked', {transaction_id, original_transaction_id, product_id, environment, expires_at, source}) (FIX:FINSEC-22). If audit_service is absent, use compliance_service._log_action.
    - Then commit. An IntegrityError on commit (a race on a unique binding) gives ACCOUNT_MISMATCH.
  (8) Return get_status(user_id).

2. services/entitlement_service.entitled_tier.
- Insert as the first statement, above the beta-comp comment: `if billing_service.flag_on(): return billing_service.entitlement(user_id)['tier']`.
- Once launched, PRO needs a verified App Store row, and the comp line (if a PR enabled it) applies only before launch.
- No other change in this file.

3. subscription_service._to_dict: add original_transaction_id, product_id, environment and app_account_token.

4. routers/subscription.py: SubscriptionResponse gains product_id: Optional[str] = None and environment: Optional[str] = None.

5. routers/billing.py.
- APIRouter(prefix='/api/v1/billing', tags=['Billing']).
- GET /status uses Depends(require_auth).
- POST /apple/transactions takes AppleTransactionRequest(signed_transaction: str = Field(min_length=20, max_length=16384), source: Literal['purchase', 'update', 'sync', 'restore'] = 'sync'). It calls core.rate_limiter._check_rate_limit(f'user:{user_id}', 'billing_verify') before the service.
- BillingError becomes HTTPException(e.status_code, detail={'code': e.code, 'message': e.message}).
- Both routes set Cache-Control: no-store.
- Pydantic models: BillingProduct, BillingEntitlement, BillingStatus (entitlement Optional).
- No ORM work in the router.

6. core/rate_limiter._RATE_LIMITS: add 'billing_verify': {'window': 3600, 'max_requests': 60}.

7. routers/health.py /healthz.
- results['billing'] = {'flag': flag_on(), 'effective': billing_enabled(), 'problems': config_problems() if flag_on() else []}.
- Wrap it in try/except. It never flips overall_ok and shows names only.

8. main.py: include billing.router.

9. .env.example: add a '# App Store billing (docs/billing/RUNBOOK.md)' block:
- BILLING_ENABLED=false
- APPLE_BUNDLE_ID=saumypatel.stockme
- APPLE_IAP_PRODUCTS=saumypatel.stockme.pro.monthly:monthly
- APPLE_ALLOWED_ENVIRONMENTS=Production,Sandbox
- APPLE_ROOT_CA_PATH=certs/AppleRootCA-G3.cer (commented out)
- NIVESH_TERMS_URL=
- NIVESH_PRIVACY_URL=

API CONTRACT. growth-billing-ios-core codes against this. Datetimes are UTC YYYY-MM-DDTHH:MM:SSZ.
- GET /api/v1/billing/status with a Bearer token returns 200: {billing_enabled: bool, app_account_token: uuid or null, products: [{id, cycle: monthly|annual}], terms_url: string or null, privacy_url: string or null, entitlement: null or {tier: free|pro, source: app_store|none, product_id, expires_at, environment: Production|Sandbox|null}}.
  - Pre-launch: billing_enabled false, token null, products [], both URLs null, entitlement null.
  - Launched but misconfigured: the same, except that entitlement is present.
  - No token gives 401.
- POST /api/v1/billing/apple/transactions with a Bearer token and body {signed_transaction, source: purchase|update|sync|restore} returns 200 with the status body.
- Errors are {detail: {code, message}}:
  - 404 BILLING_DISABLED;
  - 400 INVALID_SIGNATURE;
  - 422 UNSUPPORTED_PRODUCT;
  - 409 ACCOUNT_MISMATCH;
  - 503 BILLING_UNAVAILABLE;
  - 429 from the limiter, with Retry-After.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on all changed files.
2. backend/tests/test_billing_api.py is hermetic and uses tests/apple_jws_testkit.py.
- Each test registers a fresh user through /register and /login.
- Fixture billing_on sets BILLING_ENABLED=true, APPLE_BUNDLE_ID=test.bundle, APPLE_IAP_PRODUCTS=test.pro.monthly:monthly, NIVESH_TERMS_URL=https://example.com/terms and NIVESH_PRIVACY_URL=https://example.com/privacy. It also monkeypatches billing_service._legacy_retired to return True and billing_service._root_der to return chain.root_der.
- Gate assertions on the PRO path use a route mounted in-test with Depends(require_entitlement('sector_rotation')), so no market data is fetched.
The tests:
(1) test_status_prelaunch_when_flag_off:
- billing_enabled false, entitlement null, token null;
- POST returns 404 BILLING_DISABLED;
- a fresh user gets 402 from GET /api/v1/market/sector-rotation.
(2) test_flag_on_but_legacy_not_retired_stays_off:
- GET /api/v1/billing/status has billing_enabled false and entitlement free/none;
- /healthz results.billing.problems contains legacy_analysis_not_retired;
- POST returns 503 BILLING_UNAVAILABLE.
(3) test_status_token_is_stable_uuid.
(4) test_purchase_grants_pro:
- entitlement is pro/app_store, and expires_at equals expiresDate to the second;
- the row's original_transaction_id, product_id and environment are set;
- exactly one SubscriptionEvent (verified) and one AuditLogEntry (subscription_verified) exist.
(5) test_replay_is_noop: posting the same JWS twice leaves one event and an unchanged renews_at.
(6) test_renewal_extends_and_older_does_not.
(7) test_revocation_lapses: a revoked event is written, and status shows free/none.
(8) test_verified_after_revoked_is_noop: post the revoked JWS for transactionId T, then the pre-refund verified JWS for T. The tier is free, two events exist for T (revoked and verified), and there is no subscription_verified audit row.
(9) Binding:
- test_token_owned_by_other_user_409;
- test_original_txn_bound_to_other_user_409;
- test_orphan_token_links_to_caller: an appAccountToken that matches no row is accepted.
(10) Claim checks: test_wrong_bundle_400, test_sandbox_rejected_when_only_production_400, test_unknown_product_422, test_non_subscription_type_422, test_bad_signature_400.
(11) test_root_ca_missing_returns_503: with _root_der returning None, problems include apple_root_ca_invalid, POST returns 503, and a previously verified row still gives pro/app_store.
(12) test_config_problem_after_flip_keeps_verified_entitlement, with the flag on and NIVESH_TERMS_URL removed:
- status has billing_enabled false;
- a verified row gives entitlement pro/app_store and passes the gate;
- a fresh free user gives entitlement free/none (present, never null and never comped) and gets 402;
- posting a renewal JWS for the verified user still returns 200.
(13) test_gates_follow_app_store_when_launched, with billing on:
- a fresh user gets 402 with current_tier free;
- a verified row unlocks;
- a pro row with a future renews_at and no original_transaction_id (a legacy mock row) gets 402.
(14) test_rate_limited: with the billing_verify limit monkeypatched to 2, the third POST returns 429.
3. The wave-1 test_entitlement_policy.py still passes with BILLING_ENABLED unset.
4. Tests run in CI.

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
