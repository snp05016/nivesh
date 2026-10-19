# Feature package data-amfi-ios: iOS MF discovery and detail on the real AMFI universe (paging, Direct default, no best sort)

Cluster: data (Data foundation); area: ios
Features covered: I16

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/MutualFundModels.swift
- ios/StockApp/stockme/stockme/ViewModels/MutualFundViewModel.swift
- ios/StockApp/stockme/stockme/NetworkManager.swift
- ios/StockApp/stockme/stockme/Views/MutualFundDiscoveryView.swift
- ios/StockApp/stockme/stockme/Views/MutualFundDetailView.swift
- ios/StockApp/stockme/stockmeTests/MutualFundDecodingTests.swift
- ios/StockApp/stockme/stockmeTests/MutualFundQueryTests.swift

## Dependencies
- Feature packages (integrated before you start): data-amfi-backend
- Declared in the plan: data-amfi-backend, FIX:CMON-13, FIX:ARCH-17. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Contract (data-amfi-backend):
- GET <MF base>/?plan&option&category&sub_category&amc_name&search&limit=50&offset=0 returns [MutualFundDTO] plus X-Total-Count.
- GET <MF base>/filters returns {'categories': {String: [String]}, 'amcs': [String]}.
- Detail adds optional scheme_type, nav_source, is_active, isin_growth, isin_reinvest and history_start. Returns are null for AMFI funds.
- <MF base> is the path the existing calls use (ARCH-17 keeps an alias).

Models/MutualFundModels.swift:
- MutualFundDTO gains schemeType, navSource, isActive, isinGrowth, isinReinvest and historyStart (optional, snake_case keys, init defaults nil).
- MutualFundFilters.
- enum MutualFundPlanFilter (direct, regular, all; labels 'Direct', 'Regular', 'All plans') and enum MutualFundOptionFilter (growth, idcw, all; labels 'Growth', 'IDCW', 'All options').
- struct MutualFundQuery: Equatable { search; plan = .direct; option = .growth; category; subCategory; amc; limit = 50; offset = 0; queryItems }. It always emits plan, option, limit and offset; the others only when non-empty (search trimmed).

NetworkManager.swift:
- fetchMutualFunds(query:) async throws -> (funds, totalCount: Int?). Build the URL with URLComponents ('&' in AMC names encoded), use authRequest with a 20 s timeout, and read X-Total-Count (nil means an old backend with one page). Non-2xx throws fetchFailed.
- fetchMutualFundFilters() via _fetchDecode.

ViewModels/MutualFundViewModel.swift:
- Delete MutualFundSortOption and the AUM, returns and risk client filters.
- @MainActor publishes query, funds, totalCount, filters, isLoading, isLoadingMore, loadMoreFailed, errorMessage and isOffline.
- reload(); loadMore() appends at offset funds.count and keeps rows on failure; loadFilters() leaves filters nil on failure (fund-house menu hidden, categories derived from loaded funds); clearFilters().
- canLoadMore = totalCount.map { funds.count < $0 } ?? false.
- isOffline when fetchFailed has status -1.
- The detail VM exposes historyStart.

Views/MutualFundDiscoveryView.swift (View structs):
- MutualFundFilterBar: segmented plan and option pickers, a Category menu with nested sub-categories, a Fund house menu.
- Search debounced 350 ms (cancel the previous Task).
- MutualFundRow: name; 'AMC · sub-category'; 'NAV ₹{4 dp} · {d MMM yyyy}'.
- MutualFundListFooter: 'Show more funds'; 'Couldn't load more. Tap to retry.'; caption 'NAVs are published by AMFI (amfiindia.com) after each business day. For information only, not a recommendation.'
- States: skeleton; 'No funds match these filters.' with 'Clear filters'; 'Couldn't load mutual funds.' with Retry; 'You're offline. Reconnect and try again.' with Retry.
- Keep the SAMPLE stamp. Theme.* only, no GeometryReader, no new NavigationStack.

Views/MutualFundDetailView.swift:
- 'NAV ₹{nav} as of {date} · Source: AMFI' when navSource == 'amfi'; plan and option chips.
- MutualFundISINSection with selectable text.
- Returns only when non-nil (only DEMO rows have them), with the caption 'Point-to-point change in NAV. Past performance does not indicate future returns.' Otherwise: 'Returns appear once Nivesh has recorded at least a year of NAVs for this fund (recording since {historyStart}).' or 'Nivesh hasn't recorded NAV history for this fund yet.'
- Chart empty state: 'Nivesh began recording this fund's NAV on {historyStart}. The chart fills in as AMFI publishes new NAVs.'
- Hide nil AUM, expense and risk rows.

## Acceptance checks
SWIFTPARSE clean on every touched file; no new GeometryReader or NavigationStack.

MutualFundQueryTests covers:
- default items are exactly plan=direct, option=growth, limit=50 and offset=0
- 'L&T Mutual Fund' round-trips through URLComponents
- a whitespace-only search is omitted
- the canLoadMore helper: true, false, and false with a nil total
- the X-Total-Count parser with and without the header

MutualFundDecodingTests decodes the new fields, the legacy minimal payload and MutualFundFilters.

Manual check: against an old backend, one page and no 'Show more funds'.

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
