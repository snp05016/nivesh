# Risk Register

1. **Massive View Controllers (SwiftUI)**
   - *Risk*: `StockProfileView` becomes unmaintainably large.
   - *Mitigation*: Strictly componentize into `FinancialsTabView`, `ShareholdingTabView`, etc. Keep ViewModel bindings shallow.

2. **Data Source Inconsistencies (Backend)**
   - *Risk*: Financial APIs return different schemas for Banks vs. Non-Banks.
   - *Mitigation*: Backend endpoints must handle polymorphic financial schemas or normalize them to a unified format.

3. **Western Numbering Creep**
   - *Risk*: AI or external API defaults to Millions/Billions.
   - *Mitigation*: Ensure `_ban_western_scale()` is enforced. Use `IndianFormatter` across all iOS views.

4. **UI Performance on Mobile**
   - *Risk*: Rendering large tables inside ScrollViews causes lag.
   - *Mitigation*: Use `LazyVStack` and `LazyHGrid`. Implement pagination or limits if necessary.

5. **Navigation Depth**
   - *Risk*: Deeply nested `NavigationStacks` causing runtime warnings or broken back-buttons.
   - *Mitigation*: Adhere to the max 3-level depth rule. No nested `NavigationStacks`.
