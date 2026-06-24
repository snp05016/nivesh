# Pull Request Plan

### PR 1: Backend DTOs + Endpoints + Tests
- **Branch**: `agent/feat/1-backend-fundamentals-api`
- **Scope**: FastAPI endpoints for financials, shareholding, corp actions, valuation, risks.
- **Files**: `routers/fundamentals.py`, `services/fundamentals.py`, `models/pydantic_fundamentals.py`, `tests/test_fundamentals.py`
- **Test Commands**: `pytest tests/test_fundamentals.py`
- **Rollback Risk**: Low (additive)
- **Review Checklist**: `get_session()` used? No routers business logic?

### PR 2: iOS DTOs + API Client + Mock Data
- **Branch**: `agent/feat/2-ios-fundamentals-client`
- **Scope**: Swift decodable structs, API service extensions, and mock preview data.
- **Files**: `Models/FundamentalsDTOs.swift`, `Services/FundamentalsService.swift`, `Mocks/MockFundamentals.swift`, `Tests/FundamentalsDecodingTests.swift`
- **Test Commands**: iOS unit tests (`xcodebuild` via CI only, do not run locally).
- **Rollback Risk**: Low (additive)
- **Review Checklist**: Structs match backend schema exactly?

### PR 3: Financials + Shareholding UI
- **Branch**: `agent/feat/3-financials-shareholding-ui`
- **Scope**: Financials and Shareholding SwiftUI views. Tab navigation in `StockProfileView`.
- **Files**: `Views/StockProfile/StockProfileView.swift`, `Views/Fundamentals/FinancialsTabView.swift`, `Views/Fundamentals/ShareholdingTabView.swift`
- **Rollback Risk**: Medium (modifying existing core view)
- **Review Checklist**: Indian numbering used? Banknote Aesthetic? Max 3-level navigation?

### PR 4: Corporate Actions + Valuation + Risk Signals UI
- **Branch**: `agent/feat/4-corpactions-valuation-risks-ui`
- **Scope**: The remaining 3 UI tabs.
- **Files**: `Views/Fundamentals/CorporateActionsTabView.swift`, `Views/Fundamentals/ValuationTabView.swift`, `Views/Fundamentals/RiskSignalsTabView.swift`
- **Rollback Risk**: Low
- **Review Checklist**: Haptics included? No hardcoded sizes?

### PR 5: Integration Polish + QA + Docs
- **Branch**: `agent/chore/5-fundamentals-integration-polish`
- **Scope**: Fix any UI bugs, add empty states, verify against existing AI analysis.
- **Files**: Various
- **Rollback Risk**: Low
