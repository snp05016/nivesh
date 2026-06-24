# GitHub Issues Plan

## Issue 1: StockProfileView Navigation and Tab Integration
- **Objective**: Add a segmented control or tab system to `StockProfileView` for the new fundamentals sections.
- **Labels**: `frontend`, `iOS`, `stock-profile`
- **Acceptance Criteria**: Tabs seamlessly switch between Financials, Shareholding, etc., without breaking the existing AI Analysis flow.
- **Risk**: Low

## Issue 2: Financials Tab UI
- **Objective**: Implement the UI for Income Statement, Balance Sheet, and Cash Flow.
- **Labels**: `frontend`, `iOS`, `design`
- **Acceptance Criteria**: Uses Banknote Aesthetic, horizontal scrolling for periods, Indian Numbering.

## Issue 3: Shareholding Tab UI
- **Objective**: Display promoter, FII, DII, and public holding patterns.
- **Labels**: `frontend`, `iOS`
- **Acceptance Criteria**: Clear visual summaries (e.g., bar comparisons), warnings for promoter pledging.

## Issue 4: Corporate Actions Tab
- **Objective**: UI for dividends, bonuses, stock splits.
- **Labels**: `frontend`, `iOS`
- **Acceptance Criteria**: Chronological list of events with Banknote styling.

## Issue 5: Valuation Tab
- **Objective**: Display key valuation metrics.
- **Labels**: `frontend`, `iOS`
- **Acceptance Criteria**: Card-based grid for PE, PB, ROE, debt-to-equity.

## Issue 6: Risk Signals Tab
- **Objective**: Show identified risks (governance, pledging).
- **Labels**: `frontend`, `iOS`
- **Acceptance Criteria**: Use `Theme.bearRed` and warning haptics for critical risks.

## Issue 7-11: Backend Endpoints (Financials, Shareholding, Corp Actions, Valuation, Risk Signals)
- **Objective**: Create 5 dedicated FastAPI endpoints.
- **Labels**: `backend`, `API`
- **Acceptance Criteria**: Use `get_session()`, return Pydantic models, strictly format numbers to Lakhs/Crores. Handles missing data gracefully.

## Issue 12: Swift DTOs and API Client Integration
- **Objective**: Define `Decodable` structs in Swift and add API client methods.
- **Labels**: `iOS`, `API`

## Issue 13: Loading/Empty/Error States
- **Objective**: Ensure all new tabs handle network latency or failures gracefully.
- **Labels**: `frontend`, `iOS`, `design`

## Issue 14: Mock Data and Swift Previews
- **Objective**: Create local JSON/Swift mocks to enable isolated UI development.
- **Labels**: `iOS`, `testing`

## Issue 15: Backend Endpoint Schema Tests
- **Objective**: Add `pytest` coverage for the 5 new endpoints.
- **Labels**: `backend`, `testing`

## Issue 16: iOS Decoding Tests
- **Objective**: Add `XCTest` cases to ensure Swift DTOs parse backend JSON correctly.
- **Labels**: `iOS`, `testing`

## Issue 17: QA Pass on Existing AI Analysis Flow
- **Objective**: Ensure the new features don't break the existing deepseek/claude analysis pipeline.
- **Labels**: `testing`

## Issue 18: Visual Polish Using Banknote Aesthetic Tokens
- **Objective**: Final pass to ensure no raw hex colors, missing haptics, or system fonts sneaked in.
- **Labels**: `design`, `frontend`
