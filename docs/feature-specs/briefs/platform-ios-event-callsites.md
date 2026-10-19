# Feature package platform-ios-event-callsites: Instrument the ten events on existing screens and rewrite tutorial step 8

Cluster: platform (Platform, operations and privacy); area: ios
Features covered: 36 I47 First-party product analytics, 32 I09 Dedicated worker, one IST scheduler

## Files (create or modify)
- ios/StockApp/stockme/stockme/ViewModels/UniversalSearchViewModel.swift
- ios/StockApp/stockme/stockme/Views/StockProfileView.swift
- ios/StockApp/stockme/stockme/Views/AlertsScreen.swift
- ios/StockApp/stockme/stockme/Views/PaywallView.swift
- ios/StockApp/stockme/stockme/Views/Research/ResearchReportView.swift
- ios/StockApp/stockme/stockme/Views/TutorialOverlayView.swift

## Dependencies
- Feature packages (integrated before you start): platform-ios-flags-events, platform-scheduler-ist
- Declared in the plan: platform-ios-flags-events, platform-scheduler-ist, ENG:ios-report-ui, ENG:ios-legacy-containment. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Adds one-line I47 instrumentation to existing screens and rewrites the I09 tutorial copy.

Every call is EventLogger.shared.log(...) from platform-ios-flags-events. It does nothing unless analytics is on and the user has consented. Props never contain a ticker, company name or amount.

1. ViewModels/UniversalSearchViewModel.swift, in performSearch: after results arrive, call log(.search, ['results': EventLogger.searchBucket(results.count)]). Log once per completed query, not per keystroke; the existing debounce already ensures this.

2. Views/StockProfileView.swift: in the existing .task, call log(.stockView) before fetching. No props.

3. Views/AlertsScreen.swift, in AddAlertSheet: after addAlert succeeds, call log(.alertCreate, ['direction': ...]). Map the sheet's direction value to exactly 'above' or 'below'.

4. Views/PaywallView.swift: in the existing .task, call log(.paywallView).

5. Views/Research/ResearchReportView.swift (ENG:ios-report-ui). Log at most once per appearance of each state:
- When a report renders: log(.reportView, ['state': staleness.state]). Use 'fresh' when the state is absent (contract §6.2 Staleness.state).
- When the not-covered state shows: log(.reportView, ['state': 'not_covered']).
- When the disabled or unavailable state shows: log(.reportView, ['state': 'unavailable']).
- After POST /compute returns: log(.reportCompute, ['result': ...]), where result is 'ok', 'quota' (429), 'unavailable' (503) or 'error'.

6. Views/TutorialOverlayView.swift: change the step 8 body (currently line 91) to 'Set a price alert for any stock. While the market is open we check your alert prices every 5 minutes and notify you when one is crossed.'
- This matches platform-scheduler-ist's 09:00-15:55 IST cron.
- It drops the 'target price' wording, which is research-call vocabulary under the SEBI RA amendments.
- When push is off, alerts land in the inbox, per FIX:REL-09.

Not logged here:
- import_start and import_done are logged by the money cluster's CAS import packages.
- purchase is logged by the growth cluster's StoreKit packages.
Both use the same enum.

## Acceptance checks
- swiftc -parse passes on all six files.
- grep confirms each file contains the expected EventLogger.shared.log(. case: search, stockView, alertCreate, paywallView, reportView and reportCompute.
- grep finds no props dictionary that references a ticker, symbol, companyName or price variable.
- The step 8 copy matches exactly, and grep finds no 'target price' in TutorialOverlayView.swift.
- The existing stockmeTests still compile in CI.

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
