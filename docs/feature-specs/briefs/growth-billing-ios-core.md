# Feature package growth-billing-ios-core: iOS StoreKit 2 core: BillingManager, billing API client, models, launch and login wiring, privacy manifest

Cluster: growth (Monetization, growth and bold bets); area: ios
Features covered: 38 I43 Real billing with StoreKit 2

## Files (create or modify)
- ios/StockApp/stockme/stockme/BillingManager.swift
- ios/StockApp/stockme/stockme/NetworkManager+Billing.swift
- ios/StockApp/stockme/stockme/Models/BillingModels.swift
- ios/StockApp/stockme/stockme/stockmeApp.swift
- ios/StockApp/stockme/stockme/PrivacyInfo.xcprivacy
- ios/StockApp/stockme/stockmeTests/BillingModelsTests.swift

## Dependencies
- Feature packages (integrated before you start): growth-billing-be
- Declared in the plan: growth-billing-be, FIX:IOSCORE-27, FIX:CMON-20. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Wave 2.
API CONTRACT (from growth-billing-be; datetimes are UTC YYYY-MM-DDTHH:MM:SSZ):
- GET /api/v1/billing/status with a Bearer token returns {billing_enabled: bool, app_account_token: uuid string or null, products: [{id, cycle}], terms_url or null, privacy_url or null, entitlement: null or {tier: free|pro, source: app_store|none, product_id or null, expires_at or null, environment: Production|Sandbox|null}}.
  - entitlement is null before launch (BILLING_ENABLED off).
  - billing_enabled false with a non-null entitlement means launched, but purchases are unavailable.
- POST /api/v1/billing/apple/transactions with {signed_transaction, source: purchase|update|sync|restore} returns the same body.
- Errors are {detail: {code, message}}: 404 BILLING_DISABLED, 400 INVALID_SIGNATURE, 422 UNSUPPORTED_PRODUCT, 409 ACCOUNT_MISMATCH, 503 BILLING_UNAVAILABLE, 429.
This status is the only source of billing state; there is no app-config fetch.

1. Models/BillingModels.swift (new), with explicit snake_case CodingKeys.
- struct BillingStatusDTO: Codable, Equatable, with billingEnabled: Bool, appAccountToken: String?, products: [BillingProductDTO], termsURL: String?, privacyURL: String? and entitlement: BillingEntitlementDTO?.
- struct BillingProductDTO with id and cycle.
- struct BillingEntitlementDTO with tier, source, productID: String?, expiresAt: String? and environment: String?. Computed properties:
  - isPro is true when tier is pro;
  - isAppStore is true when source is app_store;
  - expiresDate: Date? parsed with ISO8601DateFormatter.
- struct AppleTransactionRequest: Encodable, with signedTransaction and source.
- enum BillingFailure: Equatable, with cases disabled, invalid, unsupported, accountMismatch, unavailable, rateLimited, network, pending, purchaseFailed, notConfirmed and other. Add static func from(_ error: Error) -> BillingFailure:
  - for NetworkError.fetchFailed(_, status, body) or .serverError(status, msg): status < 0 gives network, and 429 gives rateLimited;
  - otherwise parse detail.code from the body with JSONSerialization (BILLING_DISABLED, INVALID_SIGNATURE, UNSUPPORTED_PRODUCT, ACCOUNT_MISMATCH, BILLING_UNAVAILABLE);
  - if there is no code, fall back on the status (404, 400, 422, 409, 503);
  - anything else is other.
- enum PaywallState: Equatable, with cases loading, signedOut, beta, unavailable and ready(productIDs: [String], token: UUID, terms: URL, privacy: URL). Add static func evaluate(isLoggedIn: Bool, status: BillingStatusDTO?, loadFailed: Bool) -> PaywallState, checked in this order:
  - not logged in gives signedOut;
  - status nil gives unavailable after a failure, else loading;
  - status.entitlement nil gives beta (pre-launch);
  - billingEnabled false gives unavailable;
  - empty products, a token that is not a UUID, or terms or privacy that is not https gives unavailable;
  - otherwise ready.

2. NetworkManager+Billing.swift (new).
- fetchBillingStatus() via _fetchDecode(BillingStatusDTO.self, endpoint /api/v1/billing/status, timeout 15).
- postAppleTransaction(signedTransaction:source:) via FIX:IOSCORE-27's _sendDecode (method POST, endpoint /api/v1/billing/apple/transactions, body AppleTransactionRequest, timeout 20). If _sendDecode does not exist, use authRequest + session.data + ensureOK (FIX:CMON-20).

3. BillingManager.swift (new, import StoreKit): @MainActor final class BillingManager: ObservableObject.
- Properties:
  - static let shared;
  - @Published private(set) var status: BillingStatusDTO?;
  - statusLoadFailed = false;
  - lastFailure: BillingFailure?;
  - hasActiveAppStoreSubscription = false;
  - var isPro: Bool { status?.entitlement?.isPro == true }.
- start(): only once, spawn a Task that loops for await result in Transaction.updates and calls deliver(result, source update, finish true). Apple recommends starting this at launch so renewals, Ask to Buy approvals and refunds are not missed.
- refreshStatus() async: on success, set status and statusLoadFailed = false. On error, keep the old status and set statusLoadFailed = true.
- refreshLocalEntitlements() async: hasActiveAppStoreSubscription = whether any verified Transaction.currentEntitlements entry has productType == .autoRenewable and revocationDate == nil. No server call; this lets the pre-launch screen still offer Manage subscription.
- syncCurrentEntitlements() async: guard status?.billingEnabled == true. Deliver every Transaction.currentEntitlements result with source sync and finish false, then call refreshStatus().
- restore() async: try await AppStore.sync(); on error set lastFailure = .network and return. Then call syncCurrentEntitlements() and refreshLocalEntitlements().
- handlePurchase(_ result: Result<Product.PurchaseResult, Error>) async:
  - .success(.success(v)) delivers with source purchase and finish true;
  - .success(.pending) sets .pending;
  - .success(.userCancelled) does nothing;
  - .failure sets .purchaseFailed;
  - @unknown default does nothing.
- reset(): clears status, lastFailure and hasActiveAppStoreSubscription.
- private deliver(_ result: VerificationResult<Transaction>, source: String, finish: Bool) async:
  - guard case .verified(let tx). Unverified results are never sent and never finished.
  - guard NetworkManager.shared.authToken != nil. StoreKit re-delivers unfinished transactions after login.
  - status = try await postAppleTransaction(signedTransaction: result.jwsRepresentation, source:). If finish is true, await tx.finish().
  - On error, map with BillingFailure.from.
  - accountMismatch sets lastFailure and finishes the transaction when finish is true, because the purchase belongs to another account.
  - Any other error leaves the transaction unfinished so it retries. It sets lastFailure = .notConfirmed only when source is purchase or update.

4. stockmeApp.swift.
- In the existing boot path, always call BillingManager.shared.start(); the listener is harmless.
- If logged in, await refreshStatus(), then syncCurrentEntitlements(), which returns early unless billing is enabled.
- Always await refreshLocalEntitlements().
- Add .onChange(of: authManager.isLoggedIn): true runs the same refresh in a Task; false calls reset().
- This is the only place status is loaded at launch and login. PremiumUpsellBanner and the paywall read it.

5. PrivacyInfo.xcprivacy: add an NSPrivacyCollectedDataTypes entry for NSPrivacyCollectedDataTypePurchaseHistory, with Linked true, Tracking false and purpose NSPrivacyCollectedDataTypePurposeAppFunctionality.

No UI in this package. No third-party dependency: StoreKit is an Apple framework. SubscriptionStoreView, used in the UI package, needs iOS 17, and the deployment target is 17.0 or higher.

## Acceptance checks
1. swiftc -parse passes on the Swift files.
2. plutil -lint passes on PrivacyInfo.xcprivacy.
3. stockmeTests/BillingModelsTests.swift checks:
- decoding of the three contract samples: pre-launch (entitlement null), launched but unavailable, and launched;
- the PaywallState.evaluate truth table, at least 8 cases, including: signed out; entitlement nil gives beta; billingEnabled false with an entitlement gives unavailable; a non-https terms URL gives unavailable; a load failure with no status gives unavailable;
- BillingFailure.from mapping: 409 with an ACCOUNT_MISMATCH body gives accountMismatch; status -1 gives network; 404 with BILLING_DISABLED gives disabled; 503 gives unavailable; 429 gives rateLimited;
- expiresDate parses 2026-11-11T10:00:00Z.
4. No Theme or UI code, and no AppConfigStore anywhere.
5. Tests run in CI.

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
