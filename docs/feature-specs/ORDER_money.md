# Build order for cluster money

Build in this order; each package lists the packages it builds on (all earlier in this list).

- money-mf-isolation: One ORM guard that hides mutual-fund rows from every non-money reader (deps: none)
- money-journal-nollm: Remove the paid LLM call from trade-journal stats (deps: none)
- money-ios-journal-nollm: Fix the iOS trade-journal stats decode (top_keywords) (deps: none)
- money-ml-series: Engine series routes sharing the outcomes rule, plus backend client (deps: none)
- money-journal-scoring: Journal entries scored vs the Nifty 50 in a background task (deps: money-journal-nollm, money-ml-series)
- money-ios-journal-scores: Journal market card and per-entry lines on iOS (deps: money-journal-scoring)
- money-cas-parse: casparser in a killable child process and pure balance mapping (deps: none)
- money-cas-api: CAS import API: streamed upload, preview, commit, cancel, undo, list (deps: money-cas-parse, money-mf-isolation)
- money-mf-valuation: MF rows valued at NAV in the portfolio list and snapshots, served only to MF-aware clients (deps: money-mf-isolation)
- money-ios-mf-aware: iOS: decode asset_class, request funds only on the Portfolio screen, route funds to My position (deps: money-ios-journal-nollm, money-mf-valuation)
- money-ios-cas-import: CAS import flow and import history on iOS (deps: money-cas-api, money-ios-mf-aware)
- money-xray-api: Portfolio X-ray endpoint (deps: money-mf-isolation)
- money-ios-xray: Portfolio X-ray screen with hidden commission-drag and COVID replay cards (deps: money-ios-cas-import, money-xray-api)
- money-commission-drag: Regular-plan cost data for the X-ray (later wave) (deps: money-cas-api, money-xray-api)
- money-tax-engine: Versioned capital-gains rules and FIFO lot engine (pure) (deps: none)
- money-tax-api: FY capital-gains report (listed shares), CSV and routes (deps: money-ml-series, money-tax-engine)
- money-ios-tax: Capital-gains working screen with CSV export on iOS (deps: money-ios-xray, money-tax-api)
- money-crisis-replay: COVID-2020 replay endpoint (own history only) (deps: money-ml-series)
- money-docs: Money docs: flags and deferral conditions, ledger and MF isolation, CAS privacy notice, tax methodology (deps: none)
