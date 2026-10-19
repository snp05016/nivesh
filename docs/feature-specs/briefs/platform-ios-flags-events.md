# Feature package platform-ios-flags-events: iOS RemoteFlags, EventLogger and platform network calls (flags, events, data export)

Cluster: platform (Platform, operations and privacy); area: ios
Features covered: 36 I47 First-party product analytics, 28 I06 Privacy center: erasure, export, consent, 60 I46 Admin console v2

## Files (create or modify)
- ios/StockApp/stockme/stockme/Utilities/RemoteFlags.swift
- ios/StockApp/stockme/stockme/Utilities/EventLogger.swift
- ios/StockApp/stockme/stockme/NetworkManager+Platform.swift
- ios/StockApp/stockme/stockme/stockmeApp.swift
- ios/StockApp/stockme/stockme/PrivacyInfo.xcprivacy
- ios/StockApp/stockme/stockmeTests/RemoteFlagsTests.swift
- ios/StockApp/stockme/stockmeTests/EventLoggerTests.swift

## Dependencies
- Feature packages (integrated before you start): platform-events-api, platform-flags, platform-privacy-export
- Declared in the plan: platform-flags, platform-events-api, platform-privacy-export, FIX:IOSCORE-04, FIX:FINSEC-06, FIX:IOSCORE-26. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
iOS plumbing for flags (I46, I47), analytics events (I47) and the data-export call (I06).

Backend contracts:
- GET /api/v1/flags returns {'flags': {'analytics': Bool, 'analytics_consented': Bool}, 'analytics_retention_days': Int} (platform-flags, platform-events-api). Decode tolerantly: unknown flag keys are kept, and a missing analytics_retention_days is nil.
- POST /api/v1/events follows the platform-events-api contract.
- GET /api/v1/compliance/my-data returns a JSON file (platform-privacy-export contract). It is never flag-gated.

1. NetworkManager+Platform.swift: extension NetworkManager, using authRequest(_:) and session the same way NetworkManager+Compliance.swift does.
- struct ClientFlagsResponse: Decodable { flags: [String: Bool]; analyticsRetentionDays: Int? } with CodingKeys 'flags' and 'analytics_retention_days'.
- fetchClientFlags() async throws -> ClientFlagsResponse. It sends the Bearer token when one exists, because the server computes analytics_consented per caller.
- postEvents(_ events: [QueuedEvent]) async throws -> EventsAck:
  - POST JSON {'events': [...], 'app_version': CFBundleShortVersionString, 'platform': 'ios'};
  - expect 202 or 200;
  - decode EventsAck {accepted, rejected, reason?}.
- downloadMyData() async throws -> URL:
  - set timeoutInterval to 60;
  - non-2xx: throw NetworkError.serverError(status, nil);
  - remove any previous export file, then write the body to FileManager.default.temporaryDirectory/nivesh-my-data-<NetworkManager.istDateString()>.json with options [.atomic, .completeFileProtection];
  - return the file URL.

2. Utilities/RemoteFlags.swift: @MainActor final class RemoteFlags: ObservableObject with static let shared.
- @Published private(set) var flags: [String: Bool] and @Published private(set) var analyticsRetentionDays: Int?.
- isOn(_ key) -> Bool: unknown keys return false.
- refresh(force: Bool = false) async:
  - skip when the last successful fetch is under 300 s old, unless forced;
  - on success, replace flags, and set analyticsRetentionDays when the response carries it;
  - on failure, keep the last known values.
- Injectable fetch closure (default NetworkManager.shared.fetchClientFlags) and UserDefaults (default .standard).
- Persist as JSON under the UserDefaults key 'nivesh_remoteFlags_v2': the flags minus 'analytics_consented', which is user-specific and never persisted, plus analyticsRetentionDays. init loads that cache.

3. Utilities/EventLogger.swift
- enum AppEvent: String with cases app_open, search, stock_view, report_view, report_compute, alert_create, import_start, import_done, paywall_view, purchase. These must match the server allowlist. Doc comment: never put tickers, holdings or amounts in props.
- struct QueuedEvent: Codable, Equatable {name, props: [String: String], ts: String in ISO-8601 UTC}.
- struct EventsAck: Decodable {accepted: Int, rejected: Int, reason: String?}.
- @MainActor final class EventLogger with static let shared, maxBuffer 200, flushThreshold 20 and maxBatch 50.
- Injectable members:
  - isEnabled, default: RemoteFlags.shared.isOn('analytics') && RemoteFlags.shared.isOn('analytics_consented') && NetworkManager.shared.authToken != nil;
  - send, default: NetworkManager.shared.postEvents;
  - now.
- log(_:_:):
  - do nothing when disabled;
  - otherwise append, drop the oldest beyond 200, and trigger a flush at 20 events.
- flush() async:
  - no-op when already flushing or when the buffer is empty;
  - clear the buffer when disabled (for example right after consent is withdrawn);
  - otherwise send the first 50;
  - on success, remove them; if reason is 'no_consent' or 'disabled', also clear the buffer and call RemoteFlags.shared.refresh(force: true);
  - on error, keep the events for the next flush.
- static func searchBucket(_ count: Int) -> String returns '0', '1-5' or '6+'.

4. stockmeApp.swift (leave the existing lock logic untouched):
- In the boot task: await RemoteFlags.shared.refresh(force: true).
- In .onChange(of: authManager.currentUser?.userId): also call refresh(force: true).
- Add a new @State didLogColdOpen. On scenePhase .active, run Task { await RemoteFlags.shared.refresh(); EventLogger.shared.log(.appOpen, ['launch': didLogColdOpen ? 'warm' : 'cold']); didLogColdOpen = true }.
- On .background: Task { await EventLogger.shared.flush() }.

5. PrivacyInfo.xcprivacy: add NSPrivacyCollectedDataTypeProductInteraction with Linked true, Tracking false and Purposes [NSPrivacyCollectedDataTypePurposeAnalytics]. The App Store Connect privacy label must change in the same submission (human step 3).

## Acceptance checks
- swiftc -parse passes on every touched Swift file.
- PrivacyInfo.xcprivacy is valid plist XML (plutil -lint).
- In CI, stockmeTests/RemoteFlagsTests.swift passes:
  - decodes the contract JSON, including analytics_retention_days, and a payload without it (nil);
  - an unknown key reads false;
  - a failed fetch keeps cached values;
  - analytics_consented is not persisted (a fresh instance on the same UserDefaults suite reads it as false), while analyticsRetentionDays is;
  - refresh is skipped within 300 s unless forced.
- In CI, stockmeTests/EventLoggerTests.swift passes, using fake send and isEnabled:
  - disabled means nothing is buffered;
  - 20 events trigger one send;
  - batches are capped at 50;
  - the buffer is capped at 200 by dropping the oldest;
  - a no_consent ack clears the buffer;
  - flush while disabled clears the buffer without sending;
  - a send error keeps the events;
  - searchBucket maps counts correctly.
- A URLProtocol stub test (AuthRequestTests pattern) asserts that postEvents sends Bearer, X-App-Version and the documented JSON body.

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
