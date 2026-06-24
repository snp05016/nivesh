# Prompt Improvements

The current prompt is:
> "Full StockProfileView fundamentals expansion for Nivesh, including Financials, Shareholding, Corporate Actions, Valuation, and Risk Signals using the existing Banknote Aesthetic design system."

**Suggested Patch Additions to the Prompt:**

```markdown
### Edge Cases & Data Normalization
- **Bank vs Non-Bank Formats**: Ensure the backend can normalize Income Statements and Balance Sheets for banking entities (which lack standard COGS but have Interest Expended) versus standard corporate entities.
- **Period Normalization**: Fallback gracefully from Quarterly to Annual data if Quarterly is unavailable.
- **Missing Line Items**: Do not crash or display '0' when data is `null`. Show '-' or omit the row.
- **Restatements**: Ensure the API returns the most recently restated numbers, not the originally reported ones.
- **Units**: Strictly enforce display in Rs. Cr, percentages (%), or per-share values. Do not display raw integer values without unit context.

### Warning Thresholds & Business Logic
- **Promoter Pledging**: Must display a prominent warning (using `Theme.bearRed`) if promoter pledging > 15% or has increased QoQ.
- **Institutional Trends**: Highlight consecutive QoQ drops in FII/DII holdings.

### UI & UX Constraints
- **Horizontal Scrolling**: Financial tables must allow horizontal scrolling without overlapping sibling views. No `GeometryReader` in `ScrollView` or `HStack`.
- **Accessibility**: Support Dynamic Type. Keep components reusable (`.banknoteCard()`).
- **Resilience**: Implement offline/cache fallback and graceful API timeout UI.
- **Backward Compatibility**: Ensure `StockProfileView`'s existing AI Analysis flow and layout are completely unaffected. 
```
