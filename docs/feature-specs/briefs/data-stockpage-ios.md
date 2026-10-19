# Feature package data-stockpage-ios: iOS Latest results card in the Financials tab

Cluster: data (Data foundation); area: ios
Features covered: I25

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/ResultsDigestModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+Results.swift
- ios/StockApp/stockme/stockme/Views/StockProfile/LatestResultsCard.swift
- ios/StockApp/stockme/stockme/Views/StockProfileView.swift
- ios/StockApp/stockme/stockmeTests/ResultsDigestTests.swift

## Dependencies
- Feature packages (integrated before you start): data-results-backend
- Declared in the plan: data-results-backend, data-wiring, FIX:IOSUI-08, FIX:IOSCORE-15. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Contract: GET /api/v1/stocks/{symbol}/results-digest returns {symbol, period_end, period_label, filing_url, filing_title, announced_at, numbers_status ok|pending|unavailable, revenue_inr, revenue_yoy_pct, net_profit_inr, net_profit_yoy_pct, eps, eps_yoy_pct, numbers_source_text}. Error bodies are {'detail': {'code': ...}}; a 404 containing FEATURE_DISABLED or NO_DIGEST hides the card. No shareholding changes (I17 is docs only).

Models/ResultsDigestModels.swift:
- ResultsDigest (Codable, Equatable, snake_case, all numbers optional).
- static yoyText(Double?): '+8.2% YoY'; negatives use U+2212 ('−3.1% YoY'); nil gives '—'.
- isPending and isUnavailable.

NetworkManager+Results.swift: fetchResultsDigest(symbol:) via _fetchDecode, with the symbol percent-encoded as a path segment.

Views/StockProfile/LatestResultsCard.swift:
- View struct LatestResultsCard(ticker:) with @State phase: loading, hidden, loaded or failed; .task loads.
- The hide codes render EmptyView. Other errors show 'Couldn't load latest results.' with Retry.
- Loaded:
  - header 'LATEST RESULTS' plus period_label;
  - View struct ResultsMetricRow for Revenue, Net profit and EPS (IndianFormatter.formatLakhsCrores; EPS as ₹ with 2 dp; yoyText);
  - pending: 'Figures will appear once our data source publishes them.';
  - numbers_source_text verbatim, and Link('View filing') when present.
- Theme.* colours, no GeometryReader, no AI text.

StockProfileView.swift: place LatestResultsCard(ticker:) directly below FinancialsTabView in the Financials tab. If IOSUI-08 or C10 restructured the tabs, place it in the Financials content.

## Acceptance checks
SWIFTPARSE clean; no GeometryReader in the new files.

ResultsDigestTests covers:
- full, pending and unavailable payloads decode
- yoyText(8.24) == '+8.2% YoY'; yoyText(-3.1) contains U+2212; yoyText(nil) == '—'
- the hide rule is true for 404 bodies with NO_DIGEST and FEATURE_DISABLED, and false for 500

## Cluster spec
docs/feature-specs/spec_data.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
