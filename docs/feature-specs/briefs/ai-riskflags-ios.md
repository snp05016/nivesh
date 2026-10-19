# Feature package ai-riskflags-ios: Risk flags card on the stock Overview; one ASM/GSM source on screen

Cluster: ai (AI cost architecture and research surfaces); area: ios
Features covered: 40. I33 Risk flags card

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/RiskFlagsModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+RiskFlags.swift
- ios/StockApp/stockme/stockme/Views/StockProfile/RiskFlagsCard.swift
- ios/StockApp/stockme/stockme/Views/StockProfileView.swift
- ios/StockApp/stockme/stockme/Views/StockProfile/GovernanceTabView.swift
- ios/StockApp/stockme/stockmeTests/RiskFlagsDecodingTests.swift

## Dependencies
- Feature packages (integrated before you start): ai-riskflags-be
- Declared in the plan: ai-riskflags-be, ENG:ios-legacy-containment, FIX:IOSCORE-33. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Contract: GET /api/v1/stocks/{symbol}/risk-flags with a Bearer token returns 200 {'symbol', 'checks': [String], 'flags': [{'id', 'title', 'text', 'source', 'source_url': String?, 'as_of': 'YYYY-MM-DD'?}], 'unavailable': [...]}. It returns 404 when both risk flags are off, plus 401 and 422. checks lists the server checks that ran: 'concentration', and 'surveillance' once ai-surveillance-data is live.

1. Models/RiskFlagsModels.swift
- struct RiskFlagsDTO: Decodable, Equatable { let symbol: String; let checks: [String]?; let flags: [RiskFlagDTO] }. 'unavailable' is ignored on iOS; checks is optional so older servers decode.
- struct RiskFlagDTO: Decodable, Equatable, Identifiable { let id: String; let title: String; let text: String; let source: String; let sourceUrl: String?; let asOf: String? }, with CodingKeys source_url and as_of.

2. NetworkManager+RiskFlags.swift: func fetchRiskFlags(symbol: String) async throws -> RiskFlagsDTO?
- percent-encode the path segment with .urlPathAllowed, which keeps '&' for M&M;
- authRequest(url), timeoutInterval 10;
- 404 returns nil;
- other non-2xx throws NetworkError.fromHTTP(status:data:endpoint:);
- a decode failure throws NetworkError.decodingError.

3. Views/StockProfile/RiskFlagsCard.swift
struct RiskFlagsCard: View { let ticker: String }
- @State private var flags: [RiskFlagDTO] = []; @State private var selected: RiskFlagDTO?
- .task(id: ticker) { flags = (try? await NetworkManager.shared.fetchRiskFlags(symbol: ticker))?.flags ?? [] }
- Renders nothing while flags is empty. Loading, error, offline, flags off and no flags all render nothing; it never says 'no risks found'.
- Otherwise: a .banknoteCard() with header 'RISK FLAGS' (Theme.sectionCapsLabel()) and one RiskFlagRow per flag. Tapping a row sets selected, and .sheet(item: $selected) presents RiskFlagDetailSheet(flag:).
struct RiskFlagRow: View
- exclamationmark.triangle in Theme.holdAmber;
- title in Theme.engravedSerif(size: 14, weight: .bold);
- stripEmoji(text) with lineLimit(2) in Theme.inkSecondary;
- a chevron;
- .accessibilityElement(children: .combine) and .accessibilityHint('Shows the source and date').
struct RiskFlagDetailSheet: View, with no NavigationStack:
- title and full text;
- 'Source: {source}';
- 'As of {d MMM yyyy}' when as_of parses (DateFormatter with locale en_US_POSIX and format 'yyyy-MM-dd');
- a button 'Open the NSE page', shown only when SafeURL.web(flag.sourceUrl) != nil, which calls SafeURL.open(flag.sourceUrl) (FIX:IOSCORE-33); concentration flags have no URL, so they show no button;
- a 'Done' button;
- .presentationDetents([.medium, .large]).

4. Views/StockProfileView.swift: in the Overview case (case 0), insert `RiskFlagsCard(ticker: ticker).padding(.horizontal, Theme.screenPadding)` directly after OverviewTabView(...). If the ios cluster's C10 package has restructured the page, put it at the top of the Overview content.

5. Views/StockProfile/GovernanceTabView.swift (one surveillance source at a time): add `@State private var riskFlagsCoverSurveillance = false` and `.task { riskFlagsCoverSurveillance = (try? await NetworkManager.shared.fetchRiskFlags(symbol: ticker))?.checks?.contains("surveillance") ?? false }`, and render GovernanceSurveillanceBannerView(info: info) only when it is false. The banner shows /quick-info's status, which comes from NSE's private endpoints. Once the server's surveillance check is on, ASM/GSM appears only on the Overview card (from NSE's public file), so two sources can never disagree on screen. Delete the banner when FIX:REG-10's vendor decision removes those endpoints.

6. Tests, stockmeTests/RiskFlagsDecodingTests.swift
- decode a two-flag sample with checks ['concentration'], where one flag has source_url null and as_of null;
- a body without the checks key decodes with checks == nil;
- an empty flags array;
- unknown extra keys are ignored.

Constraints: Theme tokens only; Dynamic Type fonts; no GeometryReader; no NavigationStack; server text shown as-is with stripEmoji.

## Acceptance checks
1. swiftc -parse succeeds on the five Swift files and the test.
2. StockProfileView.swift contains 'RiskFlagsCard(ticker: ticker)' exactly once.
3. GovernanceTabView.swift renders GovernanceSurveillanceBannerView only when riskFlagsCoverSurveillance is false.
4. No NavigationStack or GeometryReader in RiskFlagsCard.swift.
5. RiskFlagsDecodingTests run in CI.
6. Manual: with both risk flags off, the Overview and Governance tabs are unchanged; with a test portfolio where one held stock is above 20%, that stock's Overview shows one row, and the row opens a sheet with source and date.

## Cluster spec
docs/feature-specs/spec_ai.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
