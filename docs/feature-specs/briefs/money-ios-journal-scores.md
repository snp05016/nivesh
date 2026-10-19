# Feature package money-ios-journal-scores: Journal market card and per-entry lines on iOS

Cluster: money (Portfolio and money features); area: ios
Features covered: 58 C16 decision journal

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/JournalMarketModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+Journal.swift
- ios/StockApp/stockme/stockme/Views/Money/JournalMarketCard.swift
- ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift
- ios/StockApp/stockme/stockmeTests/JournalMarketDecodingTests.swift

## Dependencies
- Feature packages (integrated before you start): money-ios-flags, money-journal-scoring
- Declared in the plan: money-ios-flags, money-journal-scoring. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Spec 3.4 copy is exact; no win/loss or good/bad wording. (1) JournalMarketModels.swift: struct JournalStatsMarketEnvelope: Decodable { let market: JournalMarketStats? }; JournalMarketStats (available, reason?, benchmarkLabel?, asOf?, horizons: [JournalHorizonStats], entries: [String: [String: JournalEntryScore]]?); JournalHorizonStats (sessions, label, scored, pending, favourable, medianDecisionExcessPp?, byAction: [String: JournalActionStats]?); JournalEntryScore (status, stockPct?, niftyPct?, decisionExcessPp?, endDate?, staleExit?). Does not touch PortfolioModels.swift. (2) NetworkManager+Journal.swift: fetchJournalMarket(userId:) -> JournalMarketStats? via _fetchDecode(JournalStatsMarketEnvelope.self, endpoint: '/trade-journal/\(userId)/stats'). (3) JournalMarketCard(market:): BUY/SELL/pending lines per horizon and the footnote. (4) TradeJournalScreen.swift: in the existing load task also fetch the market block (failure hides the card, logged); show the card above entries when FeatureFlags.shared.isOn(.moneyJournalScoring) and market.available; each entry card shows '1 month later: stock +3.2%, Nifty 50 +1.1%' (and the 3-month line) from market.entries[id] when status ok, 'Not scored: not an NSE-listed stock' for unknown_symbol, nothing otherwise.

## Acceptance checks
swiftc -parse clean. JournalMarketDecodingTests decodes a stats payload with a market block and entries map, and one with market null. With the flag off the screen renders as before.

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
