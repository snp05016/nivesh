# Feature package money-ios-xray: Portfolio X-ray screen with hidden commission-drag and COVID replay cards

Cluster: money (Portfolio and money features); area: ios
Features covered: 21 I28 CAS import + X-ray, 57 I34 commission drag, 62 I35 crisis replays

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/XRayModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+XRay.swift
- ios/StockApp/stockme/stockme/ViewModels/PortfolioXRayViewModel.swift
- ios/StockApp/stockme/stockme/Views/Money/PortfolioXRayView.swift
- ios/StockApp/stockme/stockme/Views/Money/XRayCards.swift
- ios/StockApp/stockme/stockme/Views/Money/PortfolioMoneySection.swift
- ios/StockApp/stockme/stockmeTests/XRayDecodingTests.swift

## Dependencies
- Feature packages (integrated before you start): money-ios-cas-import, money-xray-api
- Declared in the plan: money-ios-cas-import, money-xray-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
The two optional cards are written against the contracts in spec 3.6 and 3.9 and stay hidden until their flags are on (their backends land later). (1) XRayModels.swift: XRayResponse (asOf, totalValueInr, unpriced, allocation [XRaySlice key/label/valueInr/pct], amcs, plans?, topHoldings, concentration, facts [XRayFact code/text], commissionDrag: CommissionDrag?); CommissionDrag (available, reason?, asOf?, totalAnnualCostInr?, uncoveredRegularFunds?, funds?, source?, sourceUrl?); CrisisReplayResponse (scenario, niftyReturnPct, portfolioReturnPct, portfolioChangeInr, coveredValueInr, holdings, notIncluded, notes). (2) NetworkManager+XRay.swift: fetchXRay() GET /api/v1/me/portfolio/xray; fetchCrisisReplay() GET /api/v1/me/portfolio/crisis-replay?scenario=covid_2020; both _fetchDecode. (3) PortfolioXRayViewModel: @MainActor; loads the X-ray, and the replay only when isOn(.moneyCrisisReplay); states loading, loaded, empty 'Add holdings or import your funds to see an X-ray.', offline, failed (Retry); a replay failure hides only that card. (4) PortfolioXRayView: title 'Portfolio X-ray', as-of footer; AllocationCard (Swift Charts horizontal BarMark, labels; no GeometryReader), AMCCard, PlanMixRow, TopHoldingsCard, FactsCard (server text verbatim), CommissionDragCard when isOn(.moneyCommissionDrag) and commissionDrag.available, CrisisReplayCard when isOn(.moneyCrisisReplay) and loaded, NavigationLink 'Run a stress test (stocks only)' -> StressTestScreen(), 'Unpriced' footnote. (5) XRayCards.swift: the cards as View structs with spec 3.6 and 3.9 copy ('more'/'rose' when positive; 'Mutual funds aren't included.' when a not_included reason is mutual_fund); no switch button; Link 'About expense ratios (AMFI)' to sourceUrl. (6) PortfolioMoneySection: row 'Portfolio X-ray' -> PortfolioXRayView when isOn(.moneyXray).

## Acceptance checks
swiftc -parse clean. XRayDecodingTests: X-ray with commission_drag null, with an available block and with null plans; replay contract with not_included reasons. Manual: flags off -> no row; the X-ray renders at a large Dynamic Type size without horizontal clipping.

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
