# Billing runbook (App Store, PRO tools)

Owner doc for the growth cluster, features 38 (real billing) and 41 (honest tiering).
Compliance background: [docs/research/COMPLIANCE.md](../research/COMPLIANCE.md). Nivesh is not
registered with SEBI as a research analyst or investment adviser and must never say so.

## a. Status

Wave 1 has shipped:
- the mock purchase routes (`/upgrade`, `/cancel`) and functions are deleted;
- the PRO catalog is `sector_rotation`, `technical_picks`, `ideas_for_profit` (`FEATURE_MIN_TIER`);
- the legacy calibration dashboards are admin-only;
- the valuation and risk-signal routes are auth-only (nothing writes their tables);
- before launch, gates use the stored tier (`entitlement_service.entitled_tier`), so PRO tools are locked.

Wave 2 (the App Store store: schema, JWS verification, billing service, iOS StoreKit 2 core and paywall)
is **not built** until section f records the PRO catalog decision as "sell the tools" and an engine
Stage 3 date. If the decision is "tools free", wave 2 is not built.

v1 limits once wave 2 is built:
- a refund takes effect only when the revoked transaction reaches the server;
- a pre-refund JWS keeps access for at most one paid period, and is a no-op once the refund is recorded;
- Family Sharing and grace period are off;
- Sandbox is accepted in production and recorded per row.

## b. BILLING_ENABLED flip checklist

Do not set `BILLING_ENABLED=true` until every item is done:
- engine Stage 3 with legacy analysis retired (enforced in code, latches);
- `/healthz` shows `billing.effective` true and no problems;
- the C1 golden path is green;
- in-app account deletion is live (FINSEC-03 / I06);
- the section f legal sign-offs: the catalog is not research "for consideration"; paywall and product
  copy; tool outputs under the 30-day price-data lag; the I07 NSE data-licence decision [verify];
- a TestFlight sandbox pass.

### First IAP submission

Why it matters: App Review reviews a first auto-renewable subscription together with a binary whose
purchase UI is reachable. Reviewers buy in Sandbox against the production server, so billing must be
effective, with Sandbox allowed, during review.

1. Attach the product to the version and submit both.
2. Choose one option and record it in section f:
   - (a) Flip `BILLING_ENABLED` at submission. Production users cannot buy until approval, so PRO tools
     stay paywalled for them. While the comp is off nothing changes for them, because the tools are
     already locked. If the comp is on, the flip ends it for everyone at once, so post an in-app notice first.
   - (b) Keep the flag off and submit with review notes and a TestFlight screen recording. Do this only
     if App Review confirms in advance that it accepts it; otherwise expect a rejection for an
     unreachable purchase flow.

No code change either way.

## c. App Store Connect setup

- Sign the Paid Applications Agreement; complete banking and tax; enrol in the Small Business Program [verify 15%].
- Subscription group "Nivesh PRO"; product ids like `saumypatel.stockme.pro.monthly`.
- Council price target: 299 rupees a month. An optional 2,499 rupees a year product can be added later
  through `APPLE_IAP_PRODUCTS` without an app release.
- Family Sharing and Billing Grace Period off for v1.
- Product description lists only the enforced tools: sector rotation analytics, strategy backtester,
  options payoff builder. No research, no performance claims.
- Create Sandbox testers and a review screenshot.
- App Review notes: provide a demo account; PRO is account-based, so reviewers sign in before purchase;
  Restore purchases lives in Settings > Subscription.
- Host Terms of Use and Privacy Policy at public HTTPS URLs; add the privacy URL in App Store Connect;
  update the App Privacy label with Purchases (linked to the user, used for app functionality).

## d. Environment variables (billing_service, wave 2)

| Variable | Default | Effect |
|---|---|---|
| `BILLING_ENABLED` | unset (off) | Owner launch switch. Truthy: 1, true, yes, on. Off: POST returns 404 and gates use the pre-launch policy. |
| `APPLE_BUNDLE_ID` | `saumypatel.stockme` | Must equal the signed transaction's `bundleId`. |
| `APPLE_IAP_PRODUCTS` | `saumypatel.stockme.pro.monthly:monthly` | `id:cycle,id:cycle` (cycle monthly or annual). Malformed entries are skipped. |
| `APPLE_ALLOWED_ENVIRONMENTS` | `Production,Sandbox` | Sandbox is needed for App Review and TestFlight. |
| `APPLE_ROOT_CA_PATH` | `certs/AppleRootCA-G3.cer` | Pinned Apple Root CA G3. Read on every call. |
| `NIVESH_TERMS_URL` | empty | https URL shown on the purchase screen. |
| `NIVESH_PRIVACY_URL` | empty | https URL shown on the purchase screen. |

These come from growth-billing-be and are documented ahead of wave 2.

## e. Sandbox test script

1. Purchase in Sandbox; status shows PRO.
2. Replay the same signed transaction: no change.
3. Restore on a second device: PRO shows there.
4. Issue a Sandbox refund, then replay the pre-refund JWS: no-op (revoked event recorded).
5. Post the same subscription from a second account: 409 `ACCOUNT_MISMATCH`.

## f. Decision record

The owner fills in date, decision and rationale.

| # | Decision | Date | Decision | Rationale |
|---|---|---|---|---|
| 1 | PRO catalog (HUMAN:pro-catalog-decision) **blocking gate for wave 2** | | | |
| 2 | Beta comp (HUMAN:beta-comp-decision), **default OFF** | | | |
| 3 | Engine Stage 3 date (HUMAN:engine-stage3-scheduled) | | | |
| 4 | First IAP submission choice (section b: a or b) | | | |

1. PRO catalog.
   - Option A (proposed): sell the three enforced tools. This deviates from the council, which prefers
     tools free with monthly fresh-run credits. Credits are rejected because the engine makes stock
     reports free and charging for research raises RA "consideration" risk.
   - Option B (council): tools free. Wave 2 is not built. After the tool-output review below, a
     follow-up removes the three `require_entitlement` dependencies together with their keys
     (FIX:AUTH-14 makes a missing key fail at import).
2. Beta comp. Default OFF: before launch, gates use the stored tier, so PRO tools are locked. To turn it on:
   complete the tool-output review, then a reviewed PR uncomments the line in
   `entitlement_service.entitled_tier` and updates `BetaPlanNotice` and `test_prelaunch_uses_stored_tier`.
   If it is ON, record its end date and the user communication before the flip.
3. Engine Stage 3 date.
4. First IAP submission choice.

PRO catalog policy:
- Only tools may be sold; stock reports are always free.
- Each of these needs legal review of the paywall copy and of the tool outputs: adding a
  `FEATURE_MIN_TIER` key, turning on the comp, and option B.
- The review starts with the sector rotation quadrant labels (Leading, Improving, Weakening, Lagging),
  which `services/sector_rotation.py` computes from recent prices. They can read as a sector signal
  under the 30-day price-data lag rule for unregistered persons [verify].
- After the review, update `test_entitlement_policy`.
- Portfolio outcomes from the money cluster are future candidates, through the same review.

## g. Config problems after launch

- The paywall shows "unavailable".
- App Store entitlements keep working and nobody gets free PRO.
- Renewals are still verified, unless the problem is the root CA, bundle id, products or the legacy gate;
  then POST returns 503 and StoreKit retries.
- `/healthz` lists the problem names; fix them within the paid period.

Turning `BILLING_ENABLED` off after launch is for emergencies only. Gates fall back to the pre-launch
policy and renewals are not verified while it is off. Subscribers then lapse at the end of their period
while Apple keeps charging them. Turn the comp on first, or tell subscribers to cancel.

## h. Full-version follow-ups and triggers

- Follow-ups: Notifications V2 webhook, App Store Server API, Family Sharing, grace period, annual SKU.
- Triggers: the first refund or abuse, 100 paying subscribers, or a decision to enable sharing or grace.
- If wave 2 is cancelled, delete the iOS Debug-only mock purchase code (growth-billing-ios-ui steps 2, 6
  and 7) as a standalone change.

## i. Reconciling with App Store Connect

`subscription_events` is append-only: one row per `(transaction_id, kind)` with kind `verified` or
`revoked`, plus product, environment, purchase, expiry and revocation dates (naive UTC) and the source
(purchase, update, sync, restore). To reconcile a month, count `verified` events per `product_id` and
`environment` by purchase date and compare with the Sales and Trends report; every refund in App Store
Connect should have a `revoked` row once the device has reached the server, and any gap is a refund not
yet seen (a known ceiling of v1). Sandbox rows are never revenue.
