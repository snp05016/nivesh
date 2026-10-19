# Feature package money-ios-tax: Capital-gains working screen with CSV export on iOS

Cluster: money (Portfolio and money features); area: ios
Features covered: 54 I29 tax engine

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/TaxReportModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+Tax.swift
- ios/StockApp/stockme/stockme/ViewModels/TaxReportViewModel.swift
- ios/StockApp/stockme/stockme/Views/Money/TaxReportView.swift
- ios/StockApp/stockme/stockme/Views/Money/PortfolioMoneySection.swift
- ios/StockApp/stockme/stockmeTests/TaxReportDecodingTests.swift

## Dependencies
- Feature packages (integrated before you start): money-ios-xray, money-tax-api
- Declared in the plan: money-ios-xray, money-tax-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Shown only when moneyTaxReport is on. (1) TaxReportModels.swift: CapitalGainsReport (incl. scopeNote), CapitalGainsSummary, CapitalGainsRow, NotComputedRow; TaxReason.userText: acquisition_date_uncertain 'Purchase date unknown (edited holding or no date entered)'; etf_category_unverified 'ETF: check its tax category'; fmv_unavailable 'Bought before 1 Feb 2018: 31 Jan 2018 price unavailable'; fmv_nse_high 'Uses the NSE high on 31 Jan 2018: verify'; corporate_action_review 'Split or bonus applied: verify'; possible_intraday 'Bought and sold the same day: may be business income'; user_entered_date 'Uses the purchase date you entered: verify'; stt_on_acquisition_unverified 'Check STT was paid when acquired (bonus or pre-app holding)'. (2) NetworkManager+Tax.swift: fetchCapitalGains(fy:) via _fetchDecode; downloadCapitalGainsCSV(fy:) -> URL (authRequest GET .csv, written to temporaryDirectory/nivesh_capital_gains_FY<fy>.csv with .completeFileProtection). (3) TaxReportViewModel: FY list current back to 2018-19; default previous FY from 1 Apr to 31 Jul, else current; states loading, loaded, empty 'No sales recorded in FY 2025-26.', offline, failed; temp CSV deleted on disappear/deinit. (4) TaxReportView: title 'Capital gains'; disclaimer card always on top 'Informational working from your Nivesh transactions. Not tax advice. Verify with a chartered accountant before filing.'; scope note 'Listed shares only. Mutual funds are not covered yet.'; FY Picker; SummaryCard 'Short-term gains (20%)', 'Long-term gains (12.5% above Rs 1.25 lakh)', 15%/10% lines only when non-zero, 'Above the exemption: Rs x'; NotComputedCard; rows by term with 'Needs review' badges; 'Export CSV' ShareLink after download; note 'Set-off of losses, surcharge, cess and your slab rate are not applied.'; View structs, Theme, IndianFormatter. (5) PortfolioMoneySection: row 'Capital gains (tax working)' -> TaxReportView when isOn(.moneyTaxReport). No tax-saving or harvesting prompts.

## Acceptance checks
swiftc -parse clean. TaxReportDecodingTests decodes the contract with null FMV fields and empty rows, checks every reason code has text, and checks the default-FY rule for 15 Jul vs 15 Sep.

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
