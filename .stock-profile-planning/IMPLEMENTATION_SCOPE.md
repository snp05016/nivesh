# Implementation Scope

## Objective
Full `StockProfileView` fundamentals expansion for Nivesh, including Financials, Shareholding, Corporate Actions, Valuation, and Risk Signals using the existing Banknote Aesthetic design system.

## In-Scope
1. **Financials Tab**: Income statement, balance sheet, cash flow.
2. **Shareholding Tab**: Promoter, FII, DII, Public breakdown.
3. **Corporate Actions Tab**: Dividends, splits, bonuses.
4. **Valuation Tab**: Key metrics (PE, PB, ROE).
5. **Risk Signals Tab**: Red flags (promoter pledging, governance).
6. **Backend**: Endpoints to fetch, normalize, and serve the above data using Indian scales.
7. **iOS Integration**: DTOs, API client extension, mock data for Previews, and UI implementation.

## Out-of-Scope
- Direct editing of the QuantLab or existing AI Analysis flow.
- Modifying the core architecture or creating new theme tokens (unless explicitly required and missing).
- Fetching unrelated data.
