# Final Review Checklist

## Backend
- [ ] **Typed Schemas**: Endpoints return strict Pydantic models. No bare `dict` dumps.
- [ ] **No Fake Data**: Financial metrics are not fabricated by the LLM.
- [ ] **Missing Data Handling**: `null` or empty arrays are returned securely without 500 errors.
- [ ] **Bank/Non-Bank Resilience**: Schema can handle divergent financial reporting formats.
- [ ] **Test Coverage**: Endpoints covered by `pytest` for valid and invalid queries.

## iOS (SwiftUI)
- [ ] **Controller Size**: `StockProfileView` is not a giant monolith. Tabs are extracted to separate views.
- [ ] **Componentization**: Extracted reusable rows and cards.
- [ ] **State Handling**: Loading, empty, and error states exist for every tab.
- [ ] **Scrolling**: Financial tables scroll horizontally.
- [ ] **Responsiveness**: Small-screen (iPhone SE) layouts are unbroken.
- [ ] **AI Analysis Integrity**: Existing deepseek/claude analysis sections still work flawlessly.
- [ ] **Theme Enforced**: No `.system` fonts, no raw `#hex` colors. Everything uses `Theme.*`.
- [ ] **Previews**: SwiftUI Previews exist and load mock data.

## Product Quality
- [ ] **Readability**: Financials are readable and don't overwhelm the user.
- [ ] **Clarity**: Shareholding summaries are intuitive.
- [ ] **Proportional Warnings**: Risk signals are useful, not overly alarmist or un-actionable.
- [ ] **Retail-Friendly**: The design avoids "Moneycontrol clone" clutter and maintains a premium, focused aesthetic.
