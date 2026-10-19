# Feature package growth-billing-ios-ui: iOS paywall on SubscriptionStoreView, subscription management, runtime upsell and deletion notice

Cluster: growth (Monetization, growth and bold bets); area: ios
Features covered: 38 I43 Real billing with StoreKit 2, 41 I44 Honest tiering and a working paywall funnel

## Files (create or modify)
- ios/StockApp/stockme/stockme/Views/PaywallView.swift
- ios/StockApp/stockme/stockme/ViewModels/SubscriptionViewModel.swift
- ios/StockApp/stockme/stockme/Views/SubscriptionManagementView.swift
- ios/StockApp/stockme/stockme/Components/PremiumUpsellBanner.swift
- ios/StockApp/stockme/stockme/Views/DeleteAccountSheet.swift
- ios/StockApp/stockme/stockme/Models/SubscriptionModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+Subscription.swift
- ios/StockApp/stockme/stockmeTests/PaywallCopyTests.swift

## Dependencies
- Feature packages (integrated before you start): growth-billing-ios-core, growth-billing-mock-removal, growth-tiering-be
- Declared in the plan: growth-billing-ios-core, growth-tiering-be, growth-billing-mock-removal, FIX:UX-11, FIX:CMON-06, FIX:UX-12, FIX:WIP-07, FIX:REG-08, FIX:FINSEC-03, FIX:FINSEC-13, ENG:ios-report-ui. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Wave 2. Uses BillingManager, BillingStatusDTO, PaywallState and BillingFailure from growth-billing-ios-core. No AppConfigStore exists; billing state comes only from BillingManager.status.

1. Views/PaywallView.swift: a full rewrite that keeps the type name, so PremiumUpsellBanner and the management view still compile.
- NavigationStack with title 'Nivesh PRO' and a Close button. It is presented as a sheet, so the stack is not nested.
- Observes BillingManager.shared, and uses @StateObject SubscriptionViewModel for the FIX:UX-12 catalog.
- .task loads entitlements and awaits BillingManager.shared.refreshStatus().
- Switch on PaywallState.evaluate(isLoggedIn: NetworkManager.shared.authToken != nil, status: billing.status, loadFailed: billing.statusLoadFailed):
  - loading: ProgressView;
  - signedOut: 'Sign in to subscribe. PRO is linked to your Nivesh account.';
  - beta: BetaPlanNotice;
  - unavailable: 'Subscriptions aren't available right now. Check your connection and try again.' with a Retry button;
  - ready: struct PaywallStoreView.
- PaywallStoreView is SubscriptionStoreView(productIDs:). Its marketing content is struct PaywallMarketingHeader:
  - 'Nivesh PRO';
  - 'Tools for your own analysis.';
  - 'Stock reports are free for everyone.' (the ENG:ios-report-ui copy, kept);
  - an 'Included with PRO' list of catalog titles from vm.entitlements?.catalog.
- Modifiers on the store view:
  - .inAppPurchaseOptions { _ in [.appAccountToken(token)] };
  - .onInAppPurchaseCompletion { _, result in await BillingManager.shared.handlePurchase(result) };
  - .subscriptionStorePolicyDestination(url: terms, for: .termsOfService), and the same for .privacyPolicy;
  - .storeButton(.hidden, for: .restorePurchases), replaced by our own 'Restore purchases' button that calls BillingManager.restore().
- A message-banner View struct that switches on lastFailure:
  - pending: 'Your purchase is waiting for approval.';
  - notConfirmed: 'Your purchase went through. We'll apply it automatically; you can also tap Restore purchases.';
  - accountMismatch: 'This App Store subscription is linked to another Nivesh account.';
  - purchaseFailed: 'The purchase didn't complete. You have not been charged.'
- When BillingManager.isPro becomes true, show 'PRO is active on this account.' and dismiss after 1.5 s via Task.sleep.
- Delete: the tier cards, the billing toggle, the feature matrix, the mock confirmation dialog, EntitlementFeatureKeyDisplay, the Hindi decoration and every rupee literal.

2. ViewModels/SubscriptionViewModel.swift.
- Keep entitlements, currentTier, isFeatureUnlocked (fail closed, FIX:UX-11) and refreshEntitlements / loadEntitlements.
- Delete plans, billingCycle, visiblePlans, annualDiscountLabel, loadPaywall, upgrade, cancel and the action state.
- Delete currentSubscription and loadCurrentSubscription if grep shows no other user.

3. Views/SubscriptionManagementView.swift.
- Pre-launch (status.entitlement is nil): BetaPlanNotice, with the copy growth-tiering-be or the comp PR left. If hasActiveAppStoreSubscription, add 'Your App Store subscription is still active.' and a 'Manage subscription' button.
- Launched:
  - struct BillingPlanCard shows 'PRO' with 'Current period ends {d MMM yyyy}', plus 'Test purchase (Sandbox)' when environment is Sandbox; otherwise 'Free plan'. The status is plain Theme.inkSecondary text, with no bull or bear colours and no badge.
  - struct BillingActionsCard: 'Manage subscription' via .manageSubscriptionsSheet(isPresented:); 'Restore purchases'; and 'See PRO', shown only when the user is free and status.billingEnabled is true, which presents PaywallView as a sheet.
  - When status.billingEnabled is false, an inline 'Subscriptions aren't available right now.'
- Error: keep the last plan and show the inline 'Couldn't refresh your plan.'
- .task runs refreshStatus and refreshLocalEntitlements.
- Delete the mock cancel dialog and actionsSection. Keep the BetaPlanNotice struct.

4. Components/PremiumUpsellBanner.swift.
- Show the banner when BillingManager.shared.status?.billingEnabled == true && !BillingManager.shared.isPro. This replaces the ReleaseGate.demoFeatures check.
- Delete its own fetchEntitlements .task. Status is loaded at launch and login by stockmeApp, and the banner only appears after a 402.
- Keep the sheet to PaywallView.
- The preview message becomes 'Sector rotation analytics are part of PRO'.

5. Views/DeleteAccountSheet.swift (created by FIX:FINSEC-03).
- .task refreshes billing status when the user is logged in.
- If status?.entitlement?.isAppStore == true or hasActiveAppStoreSubscription, show struct AppStoreSubscriptionNotice: 'Deleting your account does not cancel your App Store subscription. Cancel it first in Manage subscription or in Settings > Apple ID > Subscriptions.'
- The notice has a 'Manage subscription' button using .manageSubscriptionsSheet (App Store 5.1.1(v)).

6. Models/SubscriptionModels.swift.
- Delete SubscriptionPlanDTO, SubscriptionPlanCatalog (the ₹499, ₹4,990, ₹999 and ₹9,990 literals) and SubscriptionUpgradeRequest.
- Delete BillingCycle, SubscriptionTier.tagline, SubscriptionTier.hindi, SubscriptionFeatureRow and rows(from:) if no references remain.
- Delete CurrentSubscriptionDTO and SubscriptionStatus if unreferenced.
- Keep SubscriptionTier (rawValue, displayName, rank).
- Remove the MOCK header comments.

7. NetworkManager+Subscription.swift.
- Delete the #if DEBUG mockUpgradeSubscription and mockCancelSubscription; their routes are gone since growth-billing-mock-removal.
- Delete fetchCurrentSubscription if unreferenced.
- Delete the file if it is left empty.

Rules for all views:
- Theme.* colours and fonts only.
- Helpers longer than 5 lines become View structs.
- No GeometryReader.
- Use the existing EKPressStyle, and call HapticManager.selection() once per tap.

## Acceptance checks
1. swiftc -parse passes on every changed Swift file.
2. grep finds none of 'Mock', 'MOCK', 'UPGRADE (MOCK)', 'Institutional', 'research desk', '₹499', 'super_pro_annual' or 'AppConfigStore' in PaywallView.swift, SubscriptionManagementView.swift, PremiumUpsellBanner.swift or SubscriptionModels.swift.
3. stockmeTests/PaywallCopyTests.swift reads PaywallView.swift, SubscriptionManagementView.swift, PremiumUpsellBanner.swift and DeleteAccountSheet.swift via #filePath, extracts string literals with a regex, and asserts:
- no case-insensitive match of mock, institutional, deep scan, real-time or unlimited;
- no word-boundary match of buy, sell, hold, target, signal, recommend, rating, bullish, bearish, accuracy or confidence;
- PaywallView.swift contains 'Stock reports are free for everyone' and 'Restore purchases';
- DeleteAccountSheet.swift contains 'does not cancel your App Store subscription'.
4. Manual check on TestFlight sandbox, per the runbook:
- a free user with billing on is shown the paywall from the sector rotation 402 banner, completes a purchase, sees 'PRO is active', and the banner disappears;
- Restore on a second device grants PRO;
- Manage subscription opens the Apple sheet.

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
