# Feature package platform-ios-privacy-center: iOS Your Data screen and the one-time Home analytics ask

Cluster: platform (Platform, operations and privacy); area: ios
Features covered: 28 I06 Privacy center: erasure, export, consent, 36 I47 First-party product analytics

## Files (create or modify)
- ios/StockApp/stockme/stockme/Views/PrivacyCenterView.swift
- ios/StockApp/stockme/stockme/ViewModels/PrivacyCenterViewModel.swift
- ios/StockApp/stockme/stockme/Views/AnalyticsConsentCard.swift
- ios/StockApp/stockme/stockme/Views/HomeScreen.swift
- ios/StockApp/stockme/stockme/Views/SettingsScreen.swift
- ios/StockApp/stockme/stockmeTests/PrivacyCenterViewModelTests.swift

## Dependencies
- Feature packages (integrated before you start): platform-events-api, platform-ios-flags-events, platform-privacy-export
- Declared in the plan: platform-ios-flags-events, platform-privacy-export, platform-events-api, FIX:FINSEC-03, FIX:FINSEC-04, FIX:FINSEC-09, FIX:UX-30, ENG:ios-legacy-containment. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Builds the I06 'Your Data' screen and the I47 consent surfaces: the toggle, and one neutral in-context ask on Home. It uses RemoteFlags and downloadMyData from platform-ios-flags-events, and the existing NetworkManager+KYC grantConsent(type:granted:) (FIX:FINSEC-09 adds a defaulted policyVersion parameter). The exact copy strings are listed below; write them as Swift string literals.

1. ViewModels/PrivacyCenterViewModel.swift
- protocol PrivacyAPI { downloadMyData() async throws -> URL; setConsent(type: String, granted: Bool) async throws; refreshFlags() async }.
- extension NetworkManager: PrivacyAPI. setConsent wraps grantConsent and ignores the returned DTO. refreshFlags awaits RemoteFlags.shared.refresh(force: true).
- @MainActor final class PrivacyCenterViewModel: ObservableObject:
  - enum ExportState: Equatable { idle, preparing, ready(URL), failed(String) }.
  - @Published properties: exportState = .idle; analyticsOn, initialised from RemoteFlags isOn('analytics_consented'); analyticsBusy; analyticsError: String?.
- exportData(): set preparing, then ready(url) or failed(message). Messages:
  - URLError .notConnectedToInternet or .networkConnectionLost: 'You're offline. Connect and try again.'
  - NetworkError.serverError(429, _): 'You've downloaded your data several times today. Try again tomorrow.'
  - NetworkError.serverError(404, _): 'Data download isn't available right now.'
  - Anything else: 'Couldn't prepare your file. Try again.'
- setAnalytics(on) async -> Bool:
  - set analyticsOn optimistically and analyticsBusy to true;
  - call setConsent(type: 'product_analytics', granted: on), then refreshFlags;
  - on error, revert analyticsOn, set analyticsError to 'Couldn't update this setting. Try again.' and return false;
  - otherwise return true.
  Turning it off makes the server erase recorded events (platform-events-api).
- static func analyticsCaption(retentionDays: Int?) -> String:
  - with N: 'Tells us which screens and features are used. We never record your holdings, stock names or amounts. Kept for N days. You can turn this off at any time; turning it off deletes what was recorded.'
  - with nil: the same text, with 'Kept for N days.' replaced by 'Kept for the period set out in our Privacy Policy.'
- enum AnalyticsAskStore:
  - static func shouldAsk(userKey: String, defaults: UserDefaults = .standard) -> Bool;
  - static func markAnswered(userKey: String, defaults: UserDefaults = .standard);
  - UserDefaults key 'nivesh_analyticsAsk_v1_' + userKey, where userKey is String(describing: authManager.currentUser.userId).

2. Views/PrivacyCenterView.swift
- struct PrivacyCenterView: View, pushed from Settings. No NavigationStack inside.
- .navigationTitle('Your Data'), Theme.canvasDeep background, and a ScrollView of cards using .banknoteCard().
- Every helper longer than 5 lines is its own private View struct. Colours come only from Theme.*. Add accessibility labels to the button and the toggle.
- (a) PrivacyStoredDataCard:
  - heading 'WHAT WE STORE';
  - rows, in this order and exactly as in platform-privacy-export's STORED_DATA_ROWS:
    - 'Your account: username, display name, settings and subscription'
    - 'Holdings, transactions, watchlists, alerts and journal notes you add, and the values and tax reports we calculate from them'
    - 'Loan, deposit, bank-account and finance-tracker records, if you use those features'
    - 'Posts, votes, reports and blocks in the community forum'
    - 'Your device ID and push token, your consent choices and security records, with the IP address on them'
    - 'Your notifications, analyses and AI research requests'
    - 'Usage events, only if you turn on usage analytics'
  - footer 'AI features send stock names and percentage moves to our AI providers only if you allow AI processing.'
- (b) PrivacyExportCard:
  - heading 'DOWNLOAD A COPY', body 'Get a file with the data linked to your account.';
  - button 'Prepare my data file', disabled while preparing;
  - preparing: ProgressView with 'Preparing your file…';
  - ready: ShareLink(item: url) labelled 'Save or share file' with icon square.and.arrow.up;
  - failed: the message in Theme.bearRed, with the button still available.
- (c) PrivacyAnalyticsCard, shown only when RemoteFlags.shared.isOn('analytics'):
  - heading 'USAGE ANALYTICS';
  - Toggle 'Share usage analytics', bound through vm.setAnalytics and disabled while busy;
  - caption PrivacyCenterViewModel.analyticsCaption(retentionDays: RemoteFlags.shared.analyticsRetentionDays);
  - inline error text.
- (d) PrivacyLinksCard:
  - NavigationLink 'AI processing and other consents' to AccountSecurityView();
  - NavigationLink 'Privacy Policy' to DisclosureDetailView(key: .privacyPolicy);
  - Button 'Delete account' in Theme.bearRed, presenting FIX:FINSEC-03's DeleteAccountSheet in a .sheet.

3. Views/AnalyticsConsentCard.swift (new): struct AnalyticsConsentCard: View.
- It observes RemoteFlags.shared, reads @EnvironmentObject authManager, holds @StateObject private var vm = PrivacyCenterViewModel(), and @State private var answered = false.
- It renders only when all of these hold:
  - RemoteFlags isOn('analytics');
  - not isOn('analytics_consented');
  - authManager.isLoggedIn, with a current user id;
  - not answered;
  - AnalyticsAskStore.shouldAsk(userKey:).
  Otherwise it renders EmptyView.
- Content, in .banknoteCard():
  - heading 'HELP IMPROVE NIVESH';
  - body PrivacyCenterViewModel.analyticsCaption(retentionDays: RemoteFlags.shared.analyticsRetentionDays);
  - an HStack of two buttons, 'Allow' and 'Not now', with identical style and size (both .frame(maxWidth: .infinity), the same Theme colours and font). Neither is emphasised or pre-selected.
- Allow: if await vm.setAnalytics(true) succeeds, markAnswered and set answered = true. On failure, show vm.analyticsError in Theme.bearRed and keep the card.
- Not now: markAnswered and set answered = true. Nothing is sent to the server, and the card never returns for that user on this device.
- Accessibility labels on both buttons. No GeometryReader and no NavigationStack.

4. Views/HomeScreen.swift: insert AnalyticsConsentCard() as the first child of the main VStack(spacing: Theme.Spacing.card) inside ScrollView(.vertical, showsIndicators: false), before ForEach(activeSectionOrder, ...). Make no other change.

5. Views/SettingsScreen.swift: add NavRow(icon: 'person.text.rectangle', color: Theme.securityGold, title: 'Your Data', destination: PrivacyCenterView()) as the first row of the DATA & PRIVACY group.
- Show it whenever authManager.isLoggedIn. It is a rights surface, so no flag gates it.
- Do not move FINSEC-03's DELETE ACCOUNT row.

## Acceptance checks
- swiftc -parse passes on all touched Swift files.
- Static checks:
  - no GeometryReader and no NavigationStack in PrivacyCenterView.swift or AnalyticsConsentCard.swift;
  - every colour comes from Theme;
  - grep finds each of the seven stored-data strings in PrivacyCenterView.swift, byte-identical to STORED_DATA_ROWS in backend/services/privacy_export.py;
  - AnalyticsConsentCard.swift contains 'Allow' and 'Not now', and both buttons use the same modifiers;
  - HomeScreen.swift contains exactly one AnalyticsConsentCard();
  - SettingsScreen.swift does not reference RemoteFlags for the Your Data row.
- In CI, stockmeTests/PrivacyCenterViewModelTests.swift passes using a fake PrivacyAPI:
  - export success gives ready(url);
  - 429 gives the rate-limit copy;
  - an offline URLError gives the offline copy;
  - 404 gives the unavailable copy;
  - a successful toggle calls setConsent('product_analytics', true), then refreshFlags, and returns true;
  - a failed toggle reverts, sets the error and returns false;
  - analyticsCaption(180) contains 'Kept for 180 days.', and analyticsCaption(nil) contains 'Privacy Policy';
  - on a test UserDefaults suite, AnalyticsAskStore.markAnswered for user '1' makes shouldAsk false for '1' and leaves it true for '2'.

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
