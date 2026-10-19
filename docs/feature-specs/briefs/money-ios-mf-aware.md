# Feature package money-ios-mf-aware: iOS: decode asset_class, request funds only on the Portfolio screen, route funds to My position

Cluster: money (Portfolio and money features); area: ios
Features covered: 21 I28 CAS import + X-ray, 20 C11 holding detail

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/PortfolioModels.swift
- ios/StockApp/stockme/stockme/NetworkManager.swift
- ios/StockApp/stockme/stockme/Views/PortfolioScreen.swift
- ios/StockApp/stockme/stockmeTests/PortfolioAssetClassTests.swift

## Dependencies
- Feature packages (integrated before you start): money-ios-holding-detail, money-ios-journal-nollm, money-mf-valuation
- Declared in the plan: money-ios-holding-detail, money-ios-journal-nollm, money-mf-valuation. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Required before money_cas_import can be enabled (enable condition). (1) PortfolioModels.swift: PortfolioHolding gains var assetClass: String = "EQ" (not decoded; set by NetworkManager like priceStatus) and var isMutualFund: Bool { assetClass == "MF" }. (2) NetworkManager.swift: getPortfolio(userId:, includeFunds: Bool = false) sets header 'X-Client-Features: asset_class' only when includeFunds is true; HoldingDTO gains asset_class: String?; the mapping sets assetClass; WidgetSnapshotStore.save(holdings: holdings.filter { !$0.isMutualFund }). Home keeps calling without includeFunds, so Home stays stock-only like the backend. (3) PortfolioScreen.swift: call getPortfolio(userId:, includeFunds: true); MF rows show company name as the primary text and 'Mutual fund' as secondary instead of the ISIN; hero totals use all holdings; stock-only cards/charts on this screen (sector, heatmap, risk, correlation, stress) receive holdings.filter { !$0.isMutualFund }; navigationDestination(for: HoldingNavValue): MF -> HoldingDetailView(ticker:, seed:) regardless of the money_holding_detail flag, never AnalysisScreen.

## Acceptance checks
swiftc -parse clean. PortfolioAssetClassTests: a holding DTO with asset_class 'MF' maps to isMutualFund; a missing field maps to EQ; the widget snapshot excludes MF. Manual on a stub server: the Portfolio request carries the header and the Home request does not; tapping a fund opens My position, never AnalysisScreen.

## Cluster spec
docs/feature-specs/spec_money.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
