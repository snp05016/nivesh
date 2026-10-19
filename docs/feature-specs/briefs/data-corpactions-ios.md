# Feature package data-corpactions-ios: iOS corporate-action banner and review sheet on Holdings

Cluster: data (Data foundation); area: ios
Features covered: I18

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/CorporateActionModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+CorporateActions.swift
- ios/StockApp/stockme/stockme/ViewModels/CorporateActionsViewModel.swift
- ios/StockApp/stockme/stockme/Views/CorporateActionsReviewSheet.swift
- ios/StockApp/stockme/stockme/Views/PortfolioScreen.swift
- ios/StockApp/stockme/stockmeTests/CorporateActionTests.swift

## Dependencies
- Feature packages (integrated before you start): data-corpactions-backend
- Declared in the plan: data-corpactions-backend, data-wiring. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Contract:
- GET /api/v1/portfolio/corporate-actions returns {'items':[Item]}.
- POST .../{id}/apply, /dismiss and /undo return {'item', 'holding' {'ticker','shares','avg_price'} or null}.
- Item = {id, ticker, group_id?, group_name?, action_label, ratio, ratio_text, ex_date 'yyyy-MM-dd', status pending|applied|dismissed, shares_before, shares_after, nse_confirmed?, source, decided_at?, undo_until?}.
- Error bodies are {'detail': {'code': ...}}. A 404 containing FEATURE_DISABLED means hide everything; NOT_FOUND or INVALID_STATE means reload.

Models/CorporateActionModels.swift:
- CorporateActionItem (Codable, Identifiable, Equatable, snake_case keys) with isPending and canUndo(today): status applied or dismissed and undo_until on or after today (calendar day, Asia/Kolkata).
- List, mutation and holding types.

NetworkManager+CorporateActions.swift:
- fetchCorporateActions() via _fetchDecode.
- mutateCorporateAction(id:action:): CorporateActionMutation enum (apply, dismiss, undo) gives the path suffix; POST with authRequest and a 15 s timeout; non-2xx throws fetchFailed(endpoint:status:body:).

ViewModels/CorporateActionsViewModel.swift (@MainActor):
- Publishes items, isHidden, isWorking, errorMessage and pendingCount (pending only).
- static isFeatureDisabled(error): 404 with a body containing FEATURE_DISABLED.
- load(): hides on that error and stays silent on others.
- apply, dismiss and undo replace the item from the response (an undone item comes back pending) and call onHoldingsChanged when there is a holding. On failure: 'Couldn't update this holding. Try again.'

Views/CorporateActionsReviewSheet.swift (View structs):
- CorporateActionsBanner(count:onTap:): '1 corporate action to review' or '{n} corporate actions to review'; subtitle 'Splits or bonus issues on your holdings'.
- CorporateActionsReviewSheet: header 'Review corporate actions' and Done. No NavigationStack.
- CorporateActionRow:
  - '{TICKER} · {group_name} · ex-date {d MMM yyyy}' (group omitted when nil); ratio_text.
  - Pending: 'This holding was added after the ex-date, so Nivesh can't tell whether its quantity already includes this split or bonus.' then 'If you held these shares before the ex-date: {before} → {after} shares. Your average price adjusts so the amount you invested stays the same.' Buttons 'Apply' and 'I've already updated it'.
  - Applied: 'Applied {d MMM}.' with Undo while canUndo.
  - Dismissed: 'Marked as already updated on {d MMM}.' with Undo while canUndo.
  - Badge 'Matches NSE closing prices' when nse_confirmed is true; 'Source: {source}'.
- Theme.* colours, Dynamic Type, accessibility labels.

PortfolioScreen.swift:
- @StateObject VM; the banner above the holdings card on tab 0 when not hidden and pendingCount > 0.
- .sheet for review; .task load; onHoldingsChanged triggers the pull-to-refresh reload.
- Nothing else changes.

## Acceptance checks
SWIFTPARSE clean; no NavigationStack or GeometryReader added.

CorporateActionTests covers:
- payloads decode with a null and a present holding, and with nil group fields
- isFeatureDisabled is true for 404 {'detail':{'code':'FEATURE_DISABLED',...}} and false for NOT_FOUND and for 500
- pendingCount counts pending items only
- canUndo is true for applied and for dismissed on the undo_until day, false the next day, and false for pending

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
