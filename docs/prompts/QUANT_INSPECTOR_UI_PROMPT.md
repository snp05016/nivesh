# QUANTITATIVE INSPECTOR UI - IMPLEMENTATION DIRECTIVE

## THE PHILOSOPHY & UX APPROACH
The user wants complete transparency into how the new Probabilistic ML framework calculates its numbers (Regime, Confidence, Conformal Bounds). However, dumping raw mathematics directly onto the main `AnalysisScreen` will completely clutter the UI and overwhelm retail investors.

**The Solution:** We will introduce a "Quant Inspector" mode. By default, the `AnalysisScreen` remains clean. But if the user taps an info icon `(i)` next to the Confidence Ring or the Target Price, a beautiful, Banknote-themed bottom sheet (`QuantInspectorSheet.swift`) slides up, revealing the exact mathematical breakdown of how the engine arrived at those numbers.

## 1. BACKEND SCHEMA ADDITION
To show the math, the frontend needs to know the exact multipliers used. 
Update the `AnalysisReport` schema and `quant_engine.py` output to include a `confidence_math_breakdown` dictionary.
```python
"confidence_math_breakdown": {
    "base_probability": 0.50,
    "net_shap_adjustment": 0.12,
    "regime_multiplier": 1.10,
    "tail_risk_deduction": 0.0,
    "final_calibrated_confidence": 0.68
}
```

## 2. SWIFT MODEL UPDATE
Update `ios/StockApp/stockme/stockme/Models/StockAnalysis.swift` to include:
```swift
let confidenceMathBreakdown: [String: Double]?
```

## 3. BUILD `QuantInspectorSheet.swift`
Create a new file: `ios/StockApp/stockme/stockme/Views/Analysis/QuantInspectorSheet.swift`.
This sheet will render the math in a clean, tabular format reminiscent of a ledger.

**UI Guidelines for the Sheet:**
- **Background:** `Theme.canvas` with a `DenominationBackground` overlay (very subtle).
- **Header:** "QUANTITATIVE ENGINE LOG" in `Theme.officialStampFont` with `.tracking(2)`.
- **The Ledger:** A `VStack` showing the additive/multiplicative math.
  - "Base Probability ........... 0.50"
  - "SHAP Drivers Adjustment .... +0.12"
  - "Regime Multiplier (Low Vol). x1.10"
  - "Tail Risk Penalties ........ -0.00"
  - `GuillocheDivider()`
  - "Calibrated Confidence ...... 0.68"
- **Typography:** Use `Theme.serialNumberFont` for all numbers to give it a monospaced, terminal/ledger feel. Use `Theme.engravedSerif` for the row labels.
- **Educational Glossary:** Below the ledger, add an accordion or a clean `VStack` that explains what these numbers mean to the user:
  - **Base Probability:** "The mathematical starting point before any market conditions are applied."
  - **SHAP Adjustments:** "How much specific indicators (like P/E ratio or RSI) pushed the score up or down."
  - **Regime Multiplier:** "A mathematical penalty or boost applied based on broader market volatility. High volatility discounts fundamental scores."
  - **Tail Risk Penalties:** "Massive mathematical deductions triggered by severe red flags (like excessive Promoter Pledging or Auditor Resignations)."

## 4. INTEGRATE INTO `AnalysisScreen.swift`
1. Add an `@State private var showQuantInspector = false`.
2. Find the "Mathematically Calibrated Confidence" UI and the "Conformal 90% Bounds" UI.
3. Add a small, elegant `Image(systemName: "info.circle")` button next to their titles.
   - **CRITICAL (Legacy Reports):** Old cached reports in the database will NOT have this mathematical payload (it will be `nil`). You must conditionally hide this `(i)` button if `analysis.confidenceMathBreakdown == nil`.
4. Add `.buttonStyle(EKPressStyle())` and haptic feedback to these info buttons.
5. When tapped, trigger `.sheet(isPresented: $showQuantInspector)` to present the `QuantInspectorSheet`.
   - **Fallback:** If the user somehow opens the sheet on a legacy report, display a beautiful empty state inside the sheet: *"Mathematical breakdown unavailable for legacy reports. Please tap 'Refresh Analysis' to run the new Quantitative Engine."*

## 5. GUARDRAILS (AGENTS.md Compliance)
- Do NOT clutter the main `AnalysisScreen.swift` body with this logic. Keep the sheet in its own file to prevent the `chkstk_darwin` Swift stack overflow crash.
- Ensure the sheet uses proper iOS safe area insets and padding (`Theme.Spacing.screen`).
- Format all target prices in the inspector using `IndianFormatter.price()`.
