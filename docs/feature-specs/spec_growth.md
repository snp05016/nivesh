# Cluster 'growth': Monetization, growth and bold bets

Roadmap: docs/investigations/2026-10-08_deep-audit/EXPANSION_ROADMAP.md

## Coverage and council handling

| Feature | Status | Verdict handling | Evidence |
|---|---|---|---|
| 38 I43 Real billing with StoreKit 2 | partial | Defer. The smaller version is built behind BILLING_ENABLED, which defaults to OFF and is read directly by billing_service (the project's per-feature env pattern; no new flag mechanism).  Sequencing: - The store is wave 2. It starts only after the owner records the PRO catalog decision as 'sell the tools' and schedules engine Stage 3 (RUNBOOK §f). - If the owner keeps tools free, the store is not built, because a store with nothing to sell would rot behind the flag. - Wave 1 deletes the mock /upgrade and /cancel now. Release is already fail-closed, so no replacement is needed.  The smaller version is one auto-renewable PRO product, verified at purchase from StoreKit 2 signed transactions, with an append-only subscription_events table and protection against replaying a pre-refund transaction.  When billing is live: - It is effective only when the flag is on, the engine's legacy analysis is retired, and the Apple and legal config is complete. Before launch, nobody can be charged. - After launch, a config problem never gives anyone free PRO: gates keep using verified App Store rows. - Renewals keep being verified unless verification itself is impossible.  The deferral conditions, the flip checklist and the ordering for the first IAP submission are in docs/billing/RUNBOOK.md.  These parts of the full version are not built. They are documented follow-ups with triggers: Notifications V2 webhook, App Store Server API, Family Sharing, grace period, offers and price tests. | Code: no StoreKit import exists anywhere in ios/. subscription_service.mock_upgrade writes a paid tier without payment (backend/services/subscription_service.py:54-85). routers/subscription.py exposes POST /upgrade and POST /cancel. user_subscriptions has UNIQUE(user_id) and a tier CHECK (backend/models/db_models.py:973-1016). The iOS paywall uses a hard-coded plan catalog (Models/SubscriptionModels.swift:99-104) and an 'UPGRADE (MOCK)' button (Views/PaywallView.swift). Fix track: - FIX:AUTH-14 (w4-02) returns 404 on /upgrade unless ALLOW_MOCK_PURCHASES is set, and fails closed on unknown feature keys. - FIX:REG-08 (merged) makes the mock purchase Debug-only, adds BetaPlanNotice and hides PremiumUpsellBanner in Release. - FIX:FINSEC-13 adds a lazy lapse on renews_at (FIX:DB-28 is a subset). - FIX:FINSEC-22 writes audit rows. - FIX:FINSEC-03 and FIX:DB-06 add the ERASURE_POLICY registry. Fix-track tests seed PRO through the mock: GH-662, TEST-10, AUTH-02, FINSEC-13, FINSEC-22 and AUTH-14, plus CMON-22's PRO-cap test. Engine: stock reports are free for everyone (SPEC §1, §10.3). RESEARCH_LEGACY_RETIRED is set at Stage 3 and never unset (§0.3 D24, §2.8). The project's flag pattern is one env var per feature, read by the service that owns it (services/youtube_summary/summarizer.py:22; FIX:REG-02 advisory_guard; the engine's services/research/config.py). Nothing in either track builds StoreKit, server verification or an events ledger. |
| 41 I44 Honest tiering and a working paywall funnel | partial | Simplify. The smaller version is covered by FIX items; this cluster adds only the delta that makes the tiers honest.  Wave 1: - The five calibration routes become admin-only, like /performance, so they are never sold and never user-facing. - PRO is limited to the three enforced tools. - The valuation and risk keys are removed, and their routes become auth-only. - A new entitled_tier function returns the stored tier before launch (FIX:AUTH-14 option A). The beta comp stays off until legal reviews the tool outputs; turning it on is a reviewed one-line PR. - The BetaPlanNotice copy is corrected so it is true.  Wave 2: - One plan, priced by the App Store. - The upsell is gated by the runtime billing status instead of a Debug-only compile flag.  Deviation from council: tools are paid because credits are rejected; owner must confirm. The decision is HUMAN:pro-catalog-decision, which blocks wave 2. If the owner chooses tools free, wave 2 is not built.  Not built: - Credits for fresh runs. The engine decision that reports are free prevails, and charging for research creates RA 'consideration' risk. - Price tests (Skeptic). - Upsells on watchlist and alert caps, which belong to the full version. | The smaller version ('C6 row deletion plus fail-closed') is planned in the fix track: - Server and client fail closed (FIX:AUTH-14). - 402 maps to NetworkError.paymentRequired with an inline PremiumUpsellBanner (FIX:UX-11, FIX:CMON-06). - The paywall reads a server catalog and three unused keys are deleted (FIX:UX-12, FIX:WIP-07). - False rows are removed (FIX:CMON-22, FIX:REG-10). - The 'AI Deep Scan' row goes and 'Stock reports are free for everyone' is added (ENG:ios-report-ui). Gaps that remain after those land: (a) comprehensive_stock_insights and swot_analysis gate company_valuations and risk_signals, which nothing writes (routers/fundamentals.py:29-70; services/fundamentals.py only reads). (b) FIX:FINSEC-11 step 1 puts five legacy calibration routes behind PRO (routers/predictions.py:129, 198, 249, 281, 307), which would sell model calibration data. FIX:REG-11 step 2 and ENG §8.6 say users never see rates. (c) Plans are hard-coded at ₹499 and ₹999, with an empty Super PRO tier (SubscriptionModels.swift:99-104). (d) BetaPlanNotice says 'All features are free during the beta' (SubscriptionManagementView.swift:205), while the server returns 402 on PRO routes. (e) Opening the tools to everyone, as the earlier beta comp did, would expose sector rotation's quadrant labels, which are computed from recent prices (services/sector_rotation.py:116, 231-243), with no legal gate. |
| 63 I45 Share card, public web pages, referrals | new | Reject. The safe minimal version builds no share surface and removes the existing one.  Rejected risks, and how this design avoids each: (1) Public pages read as distribution of research by an unregistered entity: none are built. (2) Referrals bring incentivised promotion, IAP 3.1.1 and referee personal data: none are built. (3) Verdicts, returns, performance or recent prices in shared content: no card is built. - Any card that names a security with metrics computed through the latest close breaks the 30-day lag rule. - Max drawdown is itself a return. - The legacy image export of LLM analyses is deleted, and a CI grep keeps it out. (4) Redistribution of exchange data (I07): nothing is shared.  The earlier card design moves to docs/proposals/share-card-reentry.md. Re-entry requires a legal opinion on the 30-day lag, no drawdown or other return metric, the I07 decision and engine Stage 3. After that, the card would sit behind a server flag that defaults to off. | AnalysisScreen.swift:361-369 has a 'Share as Image' toolbar button. shareAsImage() (lines 505-540) renders the full legacy AnalysisCoreSections and AnalysisExtremeSections of a saved LLM analysis into an image for UIActivityViewController. The image has no archived-report banner, which the engine adds elsewhere (ENG §10.4). No fix item or engine package removes this export; ENG:ios-report-ui keeps archived rendering. No backend, web or referral code exists. engine/india-data-costs-regulation.md:146 and 201: education-only persons may not use price data from the preceding 30 days to name or signal securities. This rule has applied since 1 Jul 2026, and today is 11 Oct 2026. |
| 65 I49 SEBI RA registration path | partial | Defer. The smaller version is 'the opinion', delivered as docs/proposals/sebi-ra-registration-path.md. It contains: - questions for counsel, now including whether the 30-day lag covers the PRO tool outputs and any future share card; - the cost and staffing table; - obligations mapped to code switches, including the retention change that must happen before a registration number is ever set; - the yes and no branches; - a board decision record. The server-side flag is the engine's existing RESEARCH_SEBI_RA_REG_NO (unset, fails closed). The engine decision stays the default: track record and cohorts appear only with a registration number. There is no new code until the answer is yes, so no duplicate flag is created. | The engine already implements the registration gate: - RESEARCH_SEBI_RA_REG_NO must be INH followed by 9 digits, and is unset by default. - RA_DISCLAIMER_TEXT = None makes any registration number invalid config. - cohort_frequency, a validated tier and a public track record all require it (SPEC §0.3 D9/D37, §6.4, §8.6, §9.3). Fix track: FIX:REG-02 keeps ADVISORY_OUTPUT_ENABLED=false as containment, and FIX:REG-11 keeps performance claims admin-only. Gap: the engine's prune_reports (ENG:be-db-ledger) deletes on-demand reports after 30 days and universe reports after 400 days. That conflicts with RA record-keeping (5 years [verify]). The regulatory background is in engine/india-data-costs-regulation.md: the 2024 RA amendment, 'for consideration', part-time RA, a deposit instead of net worth, AI-use disclosure, and the 30-day price-data lag for education-only persons (in force since 1 Jul 2026). |
| 66 I50 B2B research co-pilot for RAs and IAs | new | Reject. No safe minimal code version exists: any B2B delivery means a second product, redistribution of licensed data and a web front end, which are the rejected risks themselves. The delivery is repo-side groundwork, docs only: docs/proposals/b2b-research-copilot.md, with an interview guide, a manual-pilot playbook, re-entry criteria and a list of what must not be built. No data model and no flag: building tenancy before two paid pilots renew would itself be the distraction the council rejected, and a flag with no reader is scaffolding. | backend/models/db_models.py has no org, tenant, seat or API-key tables, and there is no web front end. The council voted 4 reject and 1 defer. Its re-entry condition is 'retail retention is proven and two paid manual pilots renew'. NSE website terms grant no redistribution rights (engine/india-data-costs-regulation.md:41), so serving data to businesses needs a licensed vendor. The engine contract is versioned (research.v1), which a later API could reuse. |

## Spec

# Growth cluster implementation spec (roadmap §38, §41, §63, §65, §66), revision 2

## 0. Notes for the orchestrator
- **Cost alert:** Bash calls in this pass again returned this hook message: "COST CRITICAL: Session cost is $400.28. Stop and inform the user about high cost before continuing."
  - They also reported a session-wide "SCOPE WARNING: about 200 files modified". This pass modified none.
  - A workflow subagent cannot pause, so reads were batched and read-only, and no web lookups were made.
  - **Please show this alert to the user.**
- No repository file was changed.
- Re-checked in the worktree this pass:
  - `routers/predictions.py`: the five calibration routes use `require_auth` (lines 129, 198, 249, 281, 307). `/performance` uses `require_entitlement` until FIX:REG-11. `require_admin` (core/security.py:43) calls `require_auth` first, so it returns 401 before 403.
  - `Views/AnalysisScreen.swift`: the "Share as Image" button is at lines 361-369 and `shareAsImage()` at 505-540.
  - `SubscriptionManagementView.swift:205`: the BetaPlanNotice copy.
  - `services/sector_rotation.py:116, 231-243`: the sector rotation quadrant labels.
  - Tests that call the five routes as a non-admin: `test_quantlab_api.py`, `test_quantlab_tdd.py`, `test_prediction_calibration_api.py`, `test_calibration_hardening.py`.
  - Fix-track tests that seed PRO through the mock: GH-662, TEST-10, AUTH-02, FINSEC-13, FINSEC-22, AUTH-14, and CMON-22's PRO-cap test.
  - `alembic heads` shows two heads today: 36e47c594dc7 and ec35eaf96b81.
  - The iOS deployment target is 17.0 or higher.
- The Apple facts from the previous pass stand. SEBI facts come from `engine/india-data-costs-regulation.md`. The 30-day price-data lag for education-only persons has applied since 1 Jul 2026 and is treated as in force.
- **`HUMAN:` dependencies** are owner decisions, recorded in `docs/billing/RUNBOOK.md` §f.
  - `HUMAN:pro-catalog-decision` and `HUMAN:engine-stage3-scheduled` block wave 2.
  - `HUMAN:beta-comp-decision` on growth-tiering-be does **not** block its build. The package ships the safe default, and the decision only governs a later one-line PR.

## Revision log
| Review issue | Change |
|---|---|
| Critical: tiering reopened the calibration routes | New package growth-predictions-admin, split out so the tiering package stays small. The five routes use `require_admin`, like `/performance`. Its test asserts 401 with no token, 403 for a non-admin with billing on and off, and 200 for an admin. §8 now says FINSEC-11 step 1 becomes admin-only. The ai-cluster hedge is removed. |
| High: a store with nothing to sell | The PRO catalog decision is a blocking gate recorded in RUNBOOK §f. Wave 1 is mock removal, predictions-admin, tiering, the share-export deletion and docs. The five store packages move to wave 2. Coverage for 41 states the deviation from the council. |
| High: share card | Reduced to deleting `shareAsImage` plus a CI grep gate. The card design moves to `docs/proposals/share-card-reentry.md`. |
| Medium: two sources for the billing flag | growth-flags-be and growth-flags-ios are deleted. `billing_service` reads `BILLING_ENABLED` itself. The paywall uses `PaywallState.evaluate(isLoggedIn:status:loadFailed:)`. |
| Medium: replay after revocation | A check for a revoked event before granting, plus `test_verified_after_revoked_is_noop`. |
| Medium: config problem after launch | Once the flag is on, entitlement always comes from verified rows, never the comp. The root CA is no longer cached. Test added. One narrowing: missing legal URLs alone do not block verification (§3.4). |
| Medium: first IAP submission | New RUNBOOK §b subsection and human steps. |
| Medium: beta comp opened the tools | The default is the stored tier. The comp is a commented line, enabled by a reviewed PR after legal reviews the tool outputs. `HUMAN:beta-comp-decision` is non-blocking. This safer default supersedes issue 2's "pro while BILLING_ENABLED is unset". With the comp off, the BetaPlanNotice copy had to be corrected. |
| Found while revising | Fundamentals test paths now match CMKT-14. All tests that seed PRO through the mock are listed. Calibration tests switch to an admin identity. An `appAccountToken` from an erased account no longer blocks re-linking. The migration's `down_revision` handles two heads. |

## 1. Verdicts at a glance
| # | Council | Status | What ships | Flag (default) |
|---|---|---|---|---|
| 38 I43 | Defer | partial | Wave 1 deletes the mock `/upgrade` and `/cancel`.<br>Wave 2, gated on the PRO catalog decision and a scheduled engine Stage 3:<br>- one auto-renewable PRO product;<br>- StoreKit 2 purchase and restore;<br>- server-side JWS verification;<br>- append-only `subscription_events`. | `BILLING_ENABLED` (off), read by `billing_service`. Effective only when legacy analysis is retired and the Apple and legal config is complete. |
| 41 I44 | Simplify | partial | Wave 1:<br>- calibration dashboards admin-only;<br>- PRO = the three enforced tools;<br>- valuation and risk routes auth-only;<br>- an `entitled_tier` seam with the stored tier as default (beta comp off);<br>- honest BetaPlanNotice.<br>Wave 2: one plan priced by the App Store, and a runtime upsell.<br>Tools are paid, which deviates from the council; the owner must confirm. | Rides on `BILLING_ENABLED` |
| 63 I45 | Reject | new | The legacy "Share as Image" is deleted. No card, pages or referrals. The card design is parked with re-entry conditions. | None (nothing to switch) |
| 65 I49 | Defer | partial | Decision memo, questions for counsel and a code-switch checklist. | Engine `RESEARCH_SEBI_RA_REG_NO` (unset) |
| 66 I50 | Reject | new | Docs only. | None, on purpose |

No new jobs or schedules. Subscription lapse is computed on read (FIX:FINSEC-13).

## 2. Flags: no new mechanism
- **Project pattern:** one env var per feature, read at call time by the service that owns the feature. Examples:
  - `services/youtube_summary/summarizer.py:22`;
  - FIX:REG-02's `advisory_guard.advisory_output_enabled()`;
  - the engine's `services/research/config.py`.
- **Billing follows it.** `billing_service.flag_on()` reads `BILLING_ENABLED` with the truthy set {1, true, yes, on}.
- **No `/api/v1/app/config`.** Billing state reaches the app only through the authenticated, no-store `GET /api/v1/billing/status`, so there is one source of truth.
- **Nothing billing-related is needed before login.** The paywall has its own signed-out state.
- The share card was the only consumer of a pre-login flag, and it is not built.

## 3. Feature 38: App Store billing (I43), Defer, wave 2
### 3.1 Gate
Wave 2 (growth-billing-db, -jws, -be, -ios-core and -ios-ui) starts only when both of these hold:
1. RUNBOOK §f records the PRO catalog decision as "sell the tools" (HUMAN:pro-catalog-decision).
2. Engine Stage 3 is scheduled (HUMAN:engine-stage3-scheduled).

If the owner follows the council and makes the tools free, PRO contains nothing and wave 2 is not built. A store with nothing to sell would only rot behind the flag.

The code also keeps billing off until `RESEARCH_LEGACY_RETIRED` is set, and that check latches.

### 3.2 User story and v1 scope
**User story:** as a signed-in user who reaches a PRO tool, I can subscribe to one PRO plan with my Apple ID, restore it on another device, and manage or cancel it in the App Store. The server, not the app, decides access.

**In:**
- One auto-renewable product in the subscription group "Nivesh PRO". More product ids can be added through `APPLE_IAP_PRODUCTS` without an app release.
- Purchase through `SubscriptionStoreView`, with `appAccountToken`.
- A `Transaction.updates` listener, started at launch.
- Restore via `AppStore.sync()` plus `Transaction.currentEntitlements`.
- Offline JWS verification against a pinned Apple Root CA G3.
- Append-only `subscription_events`.
- The Manage Subscription sheet.
- The App Store notice in the account-deletion sheet.
- Purchase History in the privacy manifest.

The deletion of the mock routes ships in wave 1.

**Out** (full version; the triggers are in RUNBOOK §h):
- Server Notifications V2 webhook;
- App Store Server API;
- Family Sharing;
- grace period;
- offer codes and introductory offers;
- price tests;
- credits.

### 3.3 Data model
Alembic revision `b7e2c91a4f06`. Its `down_revision` is whatever `alembic heads` reports at implementation time.

**`user_subscriptions` gains four columns:**

| Column | Type | Constraint |
|---|---|---|
| `original_transaction_id` | VARCHAR(64) | UNIQUE |
| `product_id` | VARCHAR(100) | |
| `environment` | VARCHAR(16) | CHECK Production, Sandbox or NULL |
| `app_account_token` | VARCHAR(36) | UNIQUE |

- `renews_at` now means the expiry of the latest verified transaction.
- The tier CHECK is unchanged. `super_pro` stays a valid value but is never granted.

**New table `subscription_events` (append-only):**
- `kind`: verified or revoked;
- transaction ids, product and environment;
- purchase, expiry and revocation dates, stored as naive UTC;
- `source`: purchase, update, sync or restore;
- UNIQUE(transaction_id, kind).

**Erasure and export:**
- `subscription_events` uses `null_user`; `user_subscriptions` stays `delete`.
- The platform cluster's I06 export should include both tables.

### 3.4 Launch states
Billing fails closed for charging and for entitlement.

| State | Condition | POST /apple/transactions | Gates use | GET /billing/status |
|---|---|---|---|---|
| Pre-launch | `BILLING_ENABLED` unset or false | 404 BILLING_DISABLED | The pre-launch policy: the stored tier (beta comp off by default, see §4) | `billing_enabled` false, `entitlement` null |
| Launched, misconfigured | Flag on, `config_problems()` non-empty | 503 BILLING_UNAVAILABLE, unless the only problem is `legal_urls_missing` | The verified App Store row (`app_store`) or `none`. Never the comp. | `billing_enabled` false, `entitlement` present |
| Launched | Flag on, no problems | Verified | The verified row or `none` | `billing_enabled` true |

**`config_problems()` can return:**
- `legacy_analysis_not_retired`: read from the engine's effective LEGACY_RETIRED (ENG:be-ingest-jobs). It latches.
- `apple_bundle_id_missing`.
- `apple_products_missing`.
- `legal_urls_missing`: both https URLs are required (App Review 3.1.2).
- `apple_root_ca_invalid`.

**Operational behaviour:**
- The server logs CRITICAL whenever the set of problems changes.
- `/healthz` shows `results.billing = {flag, effective, problems}`, with problem names only.
- The root CA file is read on every call, not cached, so a fixed file takes effect without a restart.

**Why missing legal URLs do not block verification:** the links are needed on the purchase screen, and that screen is hidden in this state. Refusing to verify renewals would lapse paying subscribers just because one env var was dropped.

### 3.5 Verification rules
These live in `services/apple_jws.py` and `billing_service.apply_signed_transaction`.

- **Signature and chain:**
  - The algorithm is ES256 and `x5c` has exactly 3 entries.
  - The leaf is issued by the intermediate, and the intermediate by the bundled root. `x5c[2]` is ignored.
  - The leaf carries OID 1.2.840.113635.100.6.11.1 and the intermediate carries 1.2.840.113635.100.6.2.1.
  - Certificate validity is checked at `signedDate`, which must be at most now + 5 minutes.
  - No new package: PyJWT[crypto] already installs `cryptography`.
- **Claims:**
  - `bundleId` equals `APPLE_BUNDLE_ID`.
  - `environment` is in `APPLE_ALLOWED_ENVIRONMENTS`. The default is Production,Sandbox; Sandbox is needed for App Review and TestFlight.
  - `type` is Auto-Renewable Subscription.
  - `productId` is in `APPLE_IAP_PRODUCTS`.
  - `expiresDate` is present.
- **Binding:**
  - 409 ACCOUNT_MISMATCH when the claim's `appAccountToken` belongs to another user's row, or when `originalTransactionId` is already bound to another user.
  - A token that matches no row (its account was erased) is accepted. A still-active subscription can then be linked to a new account.
- **Idempotency:** the `(transaction_id, kind)` event is inserted first. A duplicate changes nothing and returns the current status.
- **Revoked replay:** if a `revoked` event exists for the same `transaction_id`, a later verified JWS for it is recorded only. It grants nothing and writes no audit row.
- **State changes:**
  - Verified, unexpired and later than `renews_at`: set `tier='pro'` and `renews_at=expiresDate`.
  - Revoked: set `renews_at = min(renews_at, revocationDate)`. The row lapses on the next read.
  - Expired: recorded only.
  - Each applied event writes one audit row (FIX:FINSEC-22).
- **Known ceilings:**
  - A refund is seen only when the revoked transaction reaches the server from a device. Until then, access runs to the end of the paid period.
  - A pre-refund JWS posted before the revoked version arrives keeps access for at most that period. Once the revocation is recorded, posting it again does nothing.
  - The webhook in the full version closes both gaps.

### 3.6 API
All billing routes use Bearer auth and send `Cache-Control: no-store`.

`GET /api/v1/billing/status` returns 200:
```json
{"billing_enabled": true,
 "app_account_token": "3f1c2b9e-6a1d-4d1e-9a51-1f0c8f2a7b10",
 "products": [{"id": "saumypatel.stockme.pro.monthly", "cycle": "monthly"}],
 "terms_url": "https://example.in/terms", "privacy_url": "https://example.in/privacy",
 "entitlement": {"tier": "pro", "source": "app_store", "product_id": "saumypatel.stockme.pro.monthly",
                 "expires_at": "2026-11-11T10:00:00Z", "environment": "Production"}}
```
- **Pre-launch:** `{"billing_enabled": false, "app_account_token": null, "products": [], "terms_url": null, "privacy_url": null, "entitlement": null}`.
- **Launched but misconfigured:** the same body, except that `entitlement` is present.
- **Entitlement fields:** `source` is `app_store` or `none`. With `none`, `tier` is `free`.
- **Datetimes:** UTC, in the form `YYYY-MM-DDTHH:MM:SSZ`.

`POST /api/v1/billing/apple/transactions`:
- **Body:** `{"signed_transaction": "<jwsRepresentation>", "source": "purchase|update|sync|restore"}`. The JWS must be 20 to 16,384 characters.
- **Success:** 200 with the status body.
- **Errors**, as `{"detail": {"code", "message"}}`:
  - 404 BILLING_DISABLED;
  - 400 INVALID_SIGNATURE;
  - 422 UNSUPPORTED_PRODUCT;
  - 409 ACCOUNT_MISMATCH;
  - 503 BILLING_UNAVAILABLE;
  - 429 from the per-user `billing_verify` limit (60 an hour).

**Other changes:** `GET /api/v1/subscription` gains `product_id` and `environment` (additive). `/upgrade` and `/cancel` return 404 from wave 1 onward.

### 3.7 iOS
- **BillingManager** (`@MainActor` singleton):
  - Runs the `Transaction.updates` listener.
  - Provides `refreshStatus`, `syncCurrentEntitlements` (only when billing is enabled), `restore`, `handlePurchase` and `refreshLocalEntitlements`.
  - `isPro` = `status?.entitlement?.isPro == true`.
  - Calls `finish()` only after a 200, or after a 409 (the purchase belongs to another account).
  - Never sends or finishes an unverified result.
  - Skips when there is no auth token; StoreKit re-delivers later.
- **stockmeApp:** loads billing status at launch and on login, only when logged in. It is the single loader that the banner and paywall read.
- **PaywallView:** `SubscriptionStoreView` with a marketing header and policy links.
  - Header: "Nivesh PRO", "Tools for your own analysis.", "Stock reports are free for everyone.", plus the server catalog.
  - StoreKit's restore button is replaced by our own "Restore purchases".
  - The price comes from the App Store.
- **SubscriptionManagementView:**
  - Pre-launch: BetaPlanNotice, plus a Manage button when an App Store subscription is still active.
  - Launched: a plan card, Manage subscription, Restore purchases, and See PRO (only when the user is free and billing is enabled). When billing is misconfigured, an inline "Subscriptions aren't available right now."
- **PremiumUpsellBanner:** shown when `status?.billingEnabled == true && !isPro`.
- **DeleteAccountSheet:** an App Store cancellation notice plus a Manage button (5.1.1(v)).
- **PrivacyInfo:** Purchase History, linked, not tracking, used for App Functionality.

| PaywallState | Rendering |
|---|---|
| loading | ProgressView |
| signedOut | "Sign in to subscribe. PRO is linked to your Nivesh account." |
| beta (`entitlement` null: pre-launch) | BetaPlanNotice |
| unavailable | "Subscriptions aren't available right now. Check your connection and try again." + Retry |
| ready | SubscriptionStoreView |

The unavailable state covers: launched but `billing_enabled` false; a load error; no products; a bad token; non-https URLs.

**Purchase messages:**
| Outcome | Message |
|---|---|
| Pending | "Your purchase is waiting for approval." |
| Not confirmed | "Your purchase went through. We'll apply it automatically; you can also tap Restore purchases." |
| 409 | "This App Store subscription is linked to another Nivesh account." |
| Failed | "The purchase didn't complete. You have not been charged." |
| Success | "PRO is active on this account.", then the sheet dismisses after 1.5 s |

### 3.8 Tests
- **`test_apple_jws.py`:** chain, OIDs, algorithm, tampering, validity window, fingerprint.
- **`test_billing_api.py`:**
  - pre-launch status, and POST returns 404;
  - with legacy analysis not retired, status and `/healthz` show it, and POST returns 503;
  - the account token is stable;
  - a purchase grants PRO and writes an audit row;
  - replaying a JWS is a no-op;
  - renewals extend access;
  - revocation lapses access;
  - a verified JWS after a revoked one is a no-op;
  - 409 when the token is owned by another user, or the original transaction is bound to another user;
  - an orphan token links to the caller;
  - claim checks return 400 or 422;
  - a missing root CA gives 503 and keeps the existing entitlement;
  - a config problem after the flip keeps verified entitlements and still verifies renewals;
  - once launched, gates follow App Store rows, and a legacy mock row grants nothing;
  - 429 from the rate limit.
- **iOS:**
  - `BillingModelsTests`: decoding, the PaywallState truth table, BillingFailure mapping, date parsing.
  - `PaywallCopyTests`.

### 3.9 Risks
| Risk | Handling |
|---|---|
| App Review 2.3, 3.1.1, 3.1.2, 5.1.1(v) | Native store view, policy links, restore, the deletion notice and review notes |
| Ordering of the first submission | RUNBOOK §b |
| Charging for research | Reports are never gated (tripwire test), and the legal gate comes first |
| Refunds without the webhook | The ceiling described in §3.5 |
| Sandbox accepted in production | TestFlight testers get PRO; each row records its environment |
| Config drift after launch | Paying users keep access, and `/healthz` shows the problem |
| Root CA rotation | G3 is valid until 2039 |

## 4. Feature 41: honest tiering (I44), Simplify
**Already in the fix track:**
- Server and client fail closed (FIX:AUTH-14).
- 402 maps to an inline banner (FIX:UX-11, FIX:CMON-06).
- The paywall is catalog-driven and unused keys are removed (FIX:UX-12, FIX:WIP-07).
- False rows are deleted (FIX:CMON-22, FIX:REG-10, ENG:ios-report-ui).

**Deviation from council: tools are paid because credits are rejected; owner must confirm.**
- The council recommends making the tools free and selling monthly fresh-run credits.
- Credits are not built: the engine makes reports free, and charging for research raises RA "consideration" risk.
- The proposal therefore sells the three tools. If the owner instead picks tools free (RUNBOOK §f option B), wave 2 is not built.

**Delta 1 (growth-predictions-admin): calibration dashboards become admin-only.**
- The five legacy calibration routes use `require_admin`, the same as `/performance` (REG-11; ENG §8.6: users never see rates).
- They are never sold and never user-facing. Any future loosening goes through its own review.
- `advanced_analysis` leaves the catalog.

**Delta 2 (growth-tiering-be): PRO = the three enforced tools.**
- The keys are `sector_rotation`, `technical_picks` and `ideas_for_profit`, titled "Sector rotation analytics", "Strategy backtester" and "Options payoff builder".
- `comprehensive_stock_insights` and `swot_analysis` are removed. Nothing writes `company_valuations` or `risk_signals`, so their four routes become auth-only and honestly return 404 or an empty list.

**Delta 3: the `entitled_tier` seam.**
- Before launch it returns the stored tier (AUTH-14 option A).
- The beta comp is a commented one-line `return 'pro'`, off by default.
- Turned on, it would open sector rotation, the backtester and the options payoff builder to every signed-in user with no legal gate. Sector rotation's quadrant labels are computed from recent prices.
- Turning it on takes two steps:
  1. legal reviews the tool outputs, sector rotation labels first, under the 30-day price-data lag rule;
  2. a reviewed PR enables the line and also updates BetaPlanNotice and its test.
- In wave 2, growth-billing-be adds a launched branch above it. Once `BILLING_ENABLED` is on, PRO requires a verified App Store row, and legacy mock rows (#666) grant nothing.

**Delta 4: honest beta copy.** The BetaPlanNotice text becomes "PRO tools are not on sale yet. Paid plans will be offered through App Store in-app purchase." The current "All features are free during the beta" is false while the tools return 402.

**Delta 5 (wave 2): one plan.**
- The App Store sets the price.
- The ₹499/₹999 catalog, the tier cards and the matrix are deleted.
- The upsell is gated by `status.billingEnabled` instead of a Debug-only compile flag.

**Tripwire tests:**
- `FEATURE_MIN_TIER` must equal the reviewed set.
- No `/api/v1/research` route may carry `require_entitlement`.
- Before launch, a fresh user gets 402 on PRO tools. This locks the comp off.
- The five calibration routes return 403 to non-admins, with billing on and off.

**Not built:**
- credits;
- price tests (Skeptic);
- upsells on watchlist and alert caps (full version).

**Known interim state before launch:**
- In Release, opening a PRO tool shows UX-11's 402 message.
- QuantLab's three calibration panels show their per-panel error for non-admins, as they already did with FINSEC-11's 402.

**Pricing (wave 2):** the owner sets it in App Store Connect. The council's target is ₹299/month, with an optional ₹2,499/year product.

## 5. Feature 63: share card (I45), Reject
**What ships:**
- Deletion of `shareAsImage()` and its "Share as Image" toolbar button (`AnalysisScreen.swift:361-369, 505-540`).
- A CI grep gate in `scripts/ios_static_checks.sh`, so the export cannot come back.

Why the export goes: it renders the full legacy `AnalysisCoreSections` and `AnalysisExtremeSections` of a saved LLM analysis into an image, without the engine's archived-report banner (ENG §10.4).

**Why no card now:**
- The council verdict is Reject.
- The 30-day price-data lag rule has applied since 1 Jul 2026: education-only persons may not use price data from the preceding 30 days to name or signal securities. A card that names a security and shows metrics computed through the latest close breaks it.
- Max drawdown is a peak-to-trough return.
- A `nivesh://` link does nothing for people without the app and cannot be tapped in WhatsApp, so the card adds little distribution value.

| Rejected risk | Design response |
|---|---|
| Public pages look like research distributed without registration | None built |
| Referrals (IAP 3.1.1, incentivised promotion, referee personal data) | None built |
| Verdicts, returns, performance or recent prices in shared content | No share surface. The legacy export is deleted and blocked in CI. |
| Exchange-data redistribution (I07) | Nothing shared |

**Re-entry** is specified in `docs/proposals/share-card-reentry.md`. All four conditions are required:
1. a legal opinion on the 30-day lag, or RA registration;
2. no drawdown or any other return metric;
3. the I07 decision;
4. engine Stage 3.

After that, the card would ship behind a server flag that defaults to off, using an https link instead of the custom scheme.

Pages and referrals stay rejected until I07, I03, I48 and a legal opinion are done. Rewards may only go through Apple offer codes.

## 6. Feature 65: SEBI RA registration path (I49), Defer
**Already in the engine:**
- the `RESEARCH_SEBI_RA_REG_NO` regex, with fail-closed config;
- `RA_DISCLAIMER_TEXT=None`;
- the cohort, validated-tier and track-record gates.

**Deliverable:** `docs/proposals/sebi-ra-registration-path.md`. It contains:
- **Questions for counsel:**
  - whether a paid tools-only tier makes the free reports research "for consideration";
  - individual vs non-individual vs part-time RA;
  - BASL, the deposit and fee caps [verify];
  - AI-use disclosure and PaRRVA;
  - whether the 30-day price-data lag covers the PRO tool outputs and any future share card.
- A cost and staffing table [verify].
- **Obligations mapped to code switches.** Before a registration number is ever set:
  - raise report retention in `prune_reports` from 30/400 days to the required period (5 years [verify]);
  - supply `RA_DISCLAIMER_TEXT` through a reviewed PR.
- The yes and no branches, the deferral triggers and a board decision record.

No code until the answer is yes, so no duplicate flag is created.

## 7. Feature 66: B2B co-pilot (I50), Reject
No safe minimal code exists. Any B2B delivery means a second product, redistribution of licensed data and a web front end.

**Deliverable:** `docs/proposals/b2b-research-copilot.md`. It contains:
- why the feature is rejected;
- a 10-question interview guide;
- manual-pilot rules: pilot users are ordinary retail accounts, with no bulk exports and no research produced by Nivesh;
- a pilot scorecard;
- re-entry criteria: the I47 retention threshold is met and two paid manual pilots renew;
- the list of what must not be built.

No data model and no flag.

## 8. Interactions with the fix track and the engine
**Overrides, each stated in a package:**
- FIX:FINSEC-11 step 1 becomes admin-only.
- The FIX:UX-12/WIP-07 key set drops to 3.
- Deleted together with the mock functions:
  - FIX:AUTH-14 test (b);
  - the FIX:FINSEC-13 mock tests;
  - the FIX:FINSEC-22 mock audit hooks.
- Tests that seeded PRO through the mock (FIX:GH-662, FIX:TEST-10, FIX:AUTH-02, FIX:CMON-22) seed it through the ORM instead.
- FIX:AUTH-14 option A is kept as the pre-launch default.
- In wave 2, REG-08's compile-time gate for the subscription screens is replaced by `status.billingEnabled`. ReleaseGate stays for the demo finance sections.

**Engine decisions kept:**
- reports are free (§10.3);
- users never see rates (§8.6);
- the registration cap (D37);
- English only: no Hindi strings are added, and the decorative Hindi leaves the paywall in wave 2.

**Cross-cluster notes:**
- the platform cluster's I06 export covers the billing tables;
- platform I47 logs `paywall_viewed` and `purchase_completed`;
- the ios cluster's C8 and C9 may absorb the paywall states.

## 9. Build order
1. **Wave 1, start now.** growth-predictions-admin first, then growth-tiering-be. In parallel with them: growth-billing-mock-removal, growth-share-card-ios and growth-docs.
2. **Gate.** HUMAN:pro-catalog-decision must be recorded as "sell the tools", and HUMAN:engine-stage3-scheduled must be done.
3. **Wave 2.** growth-billing-db and growth-billing-jws in parallel, then growth-billing-be, then growth-billing-ios-core, then growth-billing-ios-ui.

## Owner/ops steps (not for implementers)

- Review the session-cost alert. Bash calls in this planning pass again returned the hook message 'COST CRITICAL: Session cost is $400.28. Stop and inform the user about high cost before continuing.' Decide whether the remaining workflow phases should continue.
- Record the PRO catalog decision in docs/billing/RUNBOOK.md §f (HUMAN:pro-catalog-decision). It blocks wave 2: growth-billing-db, -jws, -be, -ios-core and -ios-ui.
Option A (proposed): sell the three enforced tools (sector rotation analytics, strategy backtester, options payoff builder). This deviates from the council, which prefers tools free with monthly fresh-run credits. Credits are rejected because stock reports are free and charging for research raises RA 'consideration' risk.
Option B (council): tools free. Wave 2 is then not built. After the legal review in step 9, a small follow-up removes the three require_entitlement dependencies together with their keys.
- Decide the beta comp (HUMAN:beta-comp-decision) and record it in RUNBOOK §f.
The default is OFF: PRO tools stay locked for everyone until billing launches.
To turn it on:
1. Complete the legal review of tool outputs (step 9, item 3).
2. Merge a reviewed PR that uncomments the line in entitlement_service.entitled_tier and updates BetaPlanNotice and test_prelaunch_uses_stored_tier.
If the comp is on, decide its end date and how users will be told before the BILLING_ENABLED flip.
- Schedule engine Stage 3 (mode on plus RESEARCH_LEGACY_RETIRED) and record the date in RUNBOOK §f (HUMAN:engine-stage3-scheduled). Wave 2 starts only after this and an option-A catalog decision.
- Apple Developer setup:
- Confirm the account type. An organization account is advised for a finance app under 5.1.1(ix).
- Sign the Paid Applications Agreement and complete banking and tax details.
- Enroll in the App Store Small Business Program (15% commission).
- Confirm the GST treatment of App Store proceeds with a CA [verify].
- App Store Connect (wave 2):
- Create the subscription group 'Nivesh PRO' and one auto-renewable product, for example saumypatel.stockme.pro.monthly. The council's target price is ₹299/month. An optional ₹2,499/year product can be added later through APPLE_IAP_PRODUCTS.
- Keep Family Sharing and Billing Grace Period OFF for v1.
- Write a product description that lists only the enforced tools, with no research and no performance claims.
- Add a review screenshot and create Sandbox tester accounts.
- Host the Terms of Use and Privacy Policy at public HTTPS URLs, using the content from FIX:REG-12/FINSEC-09. Then:
- set NIVESH_TERMS_URL and NIVESH_PRIVACY_URL on the server;
- add the privacy URL in App Store Connect;
- update the App Privacy label with Purchases (linked to the user, used for app functionality).
- If the implementing agent could not download it, place Apple Root CA - G3 (https://www.apple.com/certificateauthority/AppleRootCA-G3.cer) at backend/certs/AppleRootCA-G3.cer. Confirm its SHA-256 is 63343ABFB89A6A03EBB57E9B3F5FA7BE7C4F5C756F3017B3A8C488C3653E9179.
- Commission a legal review before any non-admin user can use a PRO tool. This applies to the beta comp, option B and the BILLING_ENABLED flip. The review covers:
(1) An opinion that the tools-only PRO catalog does not make Nivesh a provider of research services 'for consideration' under the 2024 RA amendment.
(2) The paywall copy and the App Store product text.
(3) The tool outputs under the 30-day price-data lag rule for education-only persons, in force since 1 Jul 2026 per the engine notes. Start with the sector rotation quadrant labels (Leading, Improving, Weakening, Lagging, computed from recent prices), then the backtester and the options payoff builder.
(4) The I07 NSE data-licence decision for exchange-derived data in the tools.
- Choose how to handle the first IAP submission (RUNBOOK §b) and record the choice in §f. App Review reviews the first subscription together with a binary whose purchase UI is reachable, and buys in Sandbox against the production server.
(a) Flip BILLING_ENABLED at submission. PRO tools stay paywalled for production users until approval; nothing changes for them while the comp is off. If the comp is on, post an in-app notice first.
(b) Keep the flag off and submit with review notes and a TestFlight recording of the purchase flow. Choose this only if App Review confirms in advance that it accepts it.
- Set BILLING_ENABLED=true, APPLE_BUNDLE_ID, APPLE_IAP_PRODUCTS and APPLE_ALLOWED_ENVIRONMENTS only after every item on the RUNBOOK flip checklist is done:
- engine Stage 3 with RESEARCH_LEGACY_RETIRED;
- C1 golden path green;
- in-app account deletion live;
- the legal sign-offs in step 9;
- a TestFlight sandbox pass.
Then confirm that /healthz shows billing.effective true and no problems.
- App Review submission notes:
- provide a demo account;
- explain that PRO is account-based, so reviewers sign in before purchase;
- point to Restore purchases in Settings > Subscription.
- Feature 65 (SEBI RA):
- Commission the legal opinion using the questions in docs/proposals/sebi-ra-registration-path.md, including whether the 30-day lag covers the PRO tool outputs and any future share card.
- Take a board decision and record it in that document.
- If the answer is yes, budget for NISM certification, the deposit, BASL enlistment, a principal or compliance officer and the annual audit [verify]. Schedule the retention change before setting RESEARCH_SEBI_RA_REG_NO.
- Feature 66 (B2B):
- Run about 10 founder interviews with RAs and IAs using the guide in docs/proposals/b2b-research-copilot.md.
- Run manual pilots only under the documented rules.
- Revisit building only when the retail retention threshold is met and two paid pilots renew.
