# Nivesh — StockProfileView Charts Expansion Handoff

## Project Context

**App:** Nivesh — Indian fintech iOS app (SwiftUI, dark Bloomberg-terminal aesthetic)  
**Design system:** All colors via `Theme.*` tokens. No raw hex, no `.blue`/`.red`. `.banknoteCard()` on every card. `EKPressStyle()` on every interactive element. `HapticManager.selection()` on every tap.  
**Formatting:** All prices via `IndianFormatter.price()` / `.priceCompact()`. ₹ prefix. Lakhs/Crores. "Million"/"Billion" FORBIDDEN.  
**Spacing:** Only `Theme.Spacing.*` tokens (xSmall=2, small=4, tight=6, medium=8, standard=12, card=16, screen=20, large=24, xLarge=32). `Theme.screenPadding`=20 for horizontal margins.  
**Corner radius:** `Theme.CornerRadius.*` (small=4, tight=6, medium=10, large=12, card=14)  
**No xcodebuild.** No Divider() — use `GuillocheDivider()` or `SectionDivider()`.  

---

## Current State

File: `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`

The **Chart tab** (tab index 4) currently shows ONLY `InteractivePriceChartView` — a single price/volume chart with period selector and NIFTY overlay. The task is to **expand `chartTab`** by adding 7–8 more charts below it in the same `ScrollView`.

The **Financials tab** (tab index 5) already correctly shows `financialsTable` and `piotroskiCard` — do NOT touch those.

### Existing infrastructure (already in file, do not recreate):
- `import Charts` ✅
- `InteractivePriceChartView(history: [OHLCVPoint], niftyHistory: [NiftyPricePoint], ticker: String)` ✅  
- `vm.history: StockHistoryResponse?` — has `.prices: [OHLCVPoint]` (date, open, high, low, close, volume) ✅  
- `vm.niftyHistory: [NiftyPricePoint]` ✅  
- `vm.quarterlyFinancials: [QuarterlyFinancial]` — has `.label: String`, `.revenue: Double`, `.netProfit: Double` ✅  
- `vm.piotroski: PiotroskiData?` (already rendered in Financials tab) ✅  
- `vm.fundamentals: FundamentalsSnapshot?` — has `peRatio`, `promoterHoldingPct`, `fiiHoldingPct`, `diiHoldingPct`, `ebitdaMarginPct`, `roePct`, `rocePct`, `debtToEquity` ✅  
- `vm.promoterHistory: [PromoterHistoryPoint]` from `QuarterlyFinancialsResponse.promoterHistory` ✅  

### Data model reference:
```swift
struct OHLCVPoint: Codable, Identifiable {
    let date: String; let open, high, low, close, volume: Double
    var parsedDate: Date { /* yyyy-MM-dd parser */ }
}
struct QuarterlyFinancial: Codable, Identifiable {
    let label: String; let revenue: Double; let netProfit: Double
    // CodingKeys: label, revenue, net_profit
}
struct FundamentalsSnapshot: Codable {
    let peRatio: Double?; let debtToEquity: Double?
    let promoterHoldingPct: Double?; let fiiHoldingPct: Double?; let diiHoldingPct: Double?
    let revenueTtmCrores: Double?; let ebitdaMarginPct: Double?
    let patTtmCrores: Double?; let roePct: Double?; let rocePct: Double?
    let marketCapCrores: Double?
}
```

---

## Task: Expand chartTab with 8 additional charts

### Target `chartTab` structure:

```
ScrollView {
  VStack(spacing: Theme.Spacing.xLarge) {
    
    // 1. EXISTING — Price + Volume (InteractivePriceChartView)
    //    Period selector 1M/3M/6M/1Y/2Y, NIFTY overlay toggle, candlestick toggle
    //    Tap to scrub. Already done — keep as-is.
    
    // 2. NEW — RSI Oscillator
    // 3. NEW — Moving Averages (SMA20 / SMA50 / SMA200)
    // 4. NEW — Quarterly Revenue Bars
    // 5. NEW — Quarterly PAT (Net Profit) Bars
    // 6. NEW — EBITDA Margin % Trend
    // 7. NEW — Shareholding Breakdown (Promoter / FII / DII)
    // 8. NEW — Promoter Holding History
    // 9. NEW — ROE vs ROCE Comparison
    
  }
  .padding(.horizontal, Theme.screenPadding)
  .padding(.vertical, Theme.Spacing.card)
}
.task { await vm.fetchChart() }     // already triggers vm.history load
.task { await vm.fetchFinancials() } // ADD THIS so quarterly/fundamentals load too
```

---

## Chart Specs

All charts follow these rules:
- Wrap in `.banknoteCard()` with a section label above
- Section label style: `.font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)`
- Positive = `Theme.bullGreen`, negative = `Theme.bearRed`, neutral = `Theme.securityGold`
- Axis labels: `Theme.microLabel(size: 9)` in `Theme.inkTertiary`
- Max height thumbnails: `UIScreen.main.bounds.height * 0.28`
- Empty/nil guard: show `emptyState(message: "...")` if no data
- `import Charts` already present

---

### Chart 2 — RSI Oscillator (14-day)

**Data source:** Compute from `vm.history?.prices` on device.  
**Computation:** Standard RSI-14 formula on `.close` prices.  
**Chart type:** `LineMark` Swift Charts line chart.  
**Y-axis:** 0–100 fixed domain. Rule marks at 70 (bearRed opacity 0.4) and 30 (bullGreen opacity 0.4).  
**Color:** RSI line = `Theme.securityGold`. Fill between 30–70 = `Theme.securityGold.opacity(0.05)`.  
**X-axis:** Date labels for first and last point only (reduce clutter).  
**Interactive:** `chartOverlay` drag gesture → `selectedRSI` state → tooltip bubble showing date + RSI value.  
**Label:** "RSI (14)" section header.  

```swift
// RSI computation helper (place as private func in StockProfileView or a helper extension):
private func computeRSI(_ prices: [OHLCVPoint], period: Int = 14) -> [(date: Date, rsi: Double)] {
    guard prices.count > period else { return [] }
    var gains: [Double] = []; var losses: [Double] = []
    for i in 1..<prices.count {
        let diff = prices[i].close - prices[i-1].close
        gains.append(max(diff, 0)); losses.append(max(-diff, 0))
    }
    var avgGain = gains.prefix(period).reduce(0, +) / Double(period)
    var avgLoss = losses.prefix(period).reduce(0, +) / Double(period)
    var result: [(date: Date, rsi: Double)] = []
    for i in period..<prices.count {
        avgGain = (avgGain * Double(period - 1) + gains[i - 1]) / Double(period)
        avgLoss = (avgLoss * Double(period - 1) + losses[i - 1]) / Double(period)
        let rs = avgLoss == 0 ? 100.0 : avgGain / avgLoss
        result.append((date: prices[i].parsedDate, rsi: 100 - (100 / (1 + rs))))
    }
    return result
}
```

---

### Chart 3 — Moving Averages (SMA20 / SMA50 / SMA200)

**Data source:** Compute from `vm.history?.prices` on device.  
**Chart type:** `LineMark` overlays for each SMA on top of `AreaMark` price fill.  
**Colors:**  
- Price fill: `Theme.bullGreen.opacity(0.08)` if last >= first, else `Theme.bearRed.opacity(0.08)`  
- SMA20 line: `Theme.securityGold`  
- SMA50 line: `Theme.avatarBlue` (Color(uiColor: "4B7BEC"))  
- SMA200 line: `Theme.bearRed`  
**Toggle:** Three `Toggle`-style chip buttons (SMA20/SMA50/SMA200) above the chart, `@State private var showSMA: Set<Int>`.  
**Interactive:** chartOverlay drag → vertical rule + price label.  
**Y-axis:** `.chartYAxis` with ₹ prefix on labels using `IndianFormatter.price()`.  
**Label:** "MOVING AVERAGES" section header.  

```swift
private func computeSMA(_ prices: [OHLCVPoint], period: Int) -> [(date: Date, value: Double)] {
    guard prices.count >= period else { return [] }
    return (period...prices.count).map { i in
        let slice = prices[(i-period)..<i]
        return (date: prices[i-1].parsedDate, value: slice.map(\.close).reduce(0,+) / Double(period))
    }
}
```

---

### Chart 4 — Quarterly Revenue Bars

**Data source:** `vm.quarterlyFinancials` (up to last 8 quarters, `.prefix(8)`, reversed so oldest left).  
**Chart type:** `BarMark(x: .value("Quarter", q.label), y: .value("Revenue", q.revenue))`.  
**Color:** `Theme.securityGold` fill with `.opacity(0.85)`.  
**Y-axis:** `.chartYAxisLabel("₹ Crores")` + `IndianFormatter.priceCompact()` on tick marks.  
**Interactive:** `.chartOverlay` tap → selected quarter annotation showing exact value.  
**Annotation on bar top:** `Text(IndianFormatter.priceCompact(q.revenue))` in `Theme.microLabel(size: 8)`.  
**Label:** "QUARTERLY REVENUE" section header.  
**Empty guard:** `if vm.quarterlyFinancials.isEmpty { emptyState(...) }`.

---

### Chart 5 — Quarterly PAT (Net Profit) Bars

**Data source:** Same `vm.quarterlyFinancials`.  
**Chart type:** `BarMark` same as Chart 4 but `.netProfit` field.  
**Color:** Per-bar: `q.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed`. Use `.foregroundStyle(by: .value("Sign", q.netProfit >= 0 ? "positive" : "negative"))` + `.chartForegroundStyleScale(["positive": Theme.bullGreen, "negative": Theme.bearRed])`.  
**Y-axis:** Rule mark at y=0 in `Theme.inkTertiary.opacity(0.4)`.  
**Label:** "QUARTERLY PAT" section header.  
**Tip:** Long-press glossary `.glossaryTerm("PAT", definition: "Profit After Tax...")` on the header.

---

### Chart 6 — EBITDA Margin % Trend

**Data source:** Compute from `vm.quarterlyFinancials` — `margin = netProfit / revenue * 100` (rough PAT margin proxy since EBITDA isn't in the quarterly model; label it "PAT MARGIN %").  
**Alternative:** If `vm.fundamentals?.ebitdaMarginPct` is non-nil, show it as a single horizontal rule annotation on the chart.  
**Chart type:** `LineMark` + `AreaMark` fill.  
**Color:** Line = `Theme.securityGold`. Fill = `Theme.securityGold.opacity(0.08)`.  
**Y-axis:** `"%"` suffix on tick labels. Domain auto (let Swift Charts pick).  
**Points:** `PointMark` at each quarter, `symbolSize: 30`.  
**Label:** "PAT MARGIN %" section header.

---

### Chart 7 — Shareholding Breakdown

**Data source:** `vm.fundamentals` — `promoterHoldingPct`, `fiiHoldingPct`, `diiHoldingPct`. Derive "Public" = `100 - promoter - fii - dii`.  
**Chart type:** Horizontal `BarMark` stacked (single bar) — `SectorMark` (pie) available in iOS 17+ but a stacked horizontal bar is simpler and more readable.

```swift
// Use stacked bar:
Chart {
    BarMark(x: .value("Pct", promoter), y: .value("Type", "Holding"))
        .foregroundStyle(Theme.securityGold)
    BarMark(x: .value("Pct", fii), y: .value("Type", "Holding"))
        .foregroundStyle(Theme.bullGreen)
    BarMark(x: .value("Pct", dii), y: .value("Type", "Holding"))
        .foregroundStyle(Theme.avatarBlue)
    BarMark(x: .value("Pct", public_), y: .value("Type", "Holding"))
        .foregroundStyle(Theme.inkTertiary.opacity(0.4))
}
.chartXAxis { AxisMarks { AxisValueLabel(format: .percent) } }
.frame(height: 40)
```

Below the chart: legend row `HStack` with color dot + label + `"\(value, specifier: "%.1f")%"` for each segment.  
**Label:** "SHAREHOLDING PATTERN" section header.  
**Empty guard:** Check `fundamentals?.promoterHoldingPct != nil`.

---

### Chart 8 — Promoter Holding History

**Data source:** `vm.promoterHistory: [PromoterHistoryPoint]` (from `QuarterlyFinancialsResponse.promoterHistory`). Each point has `date: String` and `holdingPct: Double` (check exact field names in `Models.swift` around line 360–380).  
**Chart type:** `LineMark` + `AreaMark`.  
**Color:** `Theme.securityGold` line. Fill = `Theme.securityGold.opacity(0.08)`.  
**Y-axis:** `"%"` suffix. Fixed domain based on data min/max ± 2%.  
**Annotation:** If latest promoter holding < previous, show `Theme.bearRed` downward arrow annotation.  
**Label:** "PROMOTER HOLDING HISTORY" section header.  
**Empty guard:** `if vm.promoterHistory.isEmpty`.

---

### Chart 9 — ROE vs ROCE Comparison

**Data source:** `vm.fundamentals` — `roePct`, `rocePct`.  
**Chart type:** Two `BarMark` side by side (grouped).  

```swift
Chart {
    BarMark(x: .value("Metric", "ROE"), y: .value("Pct", roe))
        .foregroundStyle(Theme.bullGreen)
    BarMark(x: .value("Metric", "ROCE"), y: .value("Pct", roce))
        .foregroundStyle(Theme.securityGold)
}
```

Add P/E ratio as a third bar if `peRatio` is non-nil (different color: `Theme.avatarBlue`).  
Add annotation above each bar: `Text("\(value, specifier: "%.1f")%")` in `Theme.microLabel(size: 9)`.  
**Label:** "PROFITABILITY RATIOS" section header.  
Glossary: `.glossaryTerm("ROCE", definition: "Return on Capital Employed — measures how efficiently a company generates profit from its total capital. Higher = better capital deployment.")`.

---

## Critical implementation notes

1. **Do NOT fetch new endpoints.** All data already loads from `vm.fetchChart()` (history) and `vm.fetchFinancials()` (quarterly + piotroski + fundamentals). Just add `.task { await vm.fetchFinancials() }` to chartTab alongside the existing `.task { await vm.fetchChart() }`.

2. **Respect `vm.chartLoading` and `vm.financialsLoading`** — wrap each section in an `if vm.chartLoading { skeletonBlock(rows: 3) } else { ... }` guard where appropriate.

3. **All computed values (RSI, SMA) are `private func` inside StockProfileView** — do not create new files.

4. **Each chart is its own `@ViewBuilder private func chartSection_XXX() -> some View`** — keeps `chartTab` body clean.

5. **`PromoterHistoryPoint` field names** — check `Models.swift` around line 360–380 before using. The struct may use `date`/`holdingPct` or different keys. Read before coding.

6. **Period filtering** — charts 3–9 don't need period selectors; they show all available data. Only Chart 1 (existing `InteractivePriceChartView`) has period selector.

7. **Height constraint** — each supplementary chart: `.frame(height: UIScreen.main.bounds.height * 0.25)`.

8. **After implementation** — run `gitnexus_detect_changes()` per AGENTS.md §6.1, then commit: `Add StockProfileView: 8-chart analytics suite`.

---

## Files to modify

| File | Change |
|------|--------|
| `ios/StockApp/stockme/stockme/Views/StockProfileView.swift` | Expand `chartTab` body; add `computeRSI()`, `computeSMA()` private helpers; add 8 `@ViewBuilder` chart section functions |

No new files. No backend changes needed for charts (all data already fetched).

---

## Do NOT touch

- `financialsTab` — already correct (shows `financialsTable` + `piotroskiCard`)
- `piotroskiCard` — already implemented with `fScore`/`grade`/`confidence`/`checks`
- `InteractivePriceChartView` — keep exactly as-is at top of chartTab
- `AnalysisScreen.swift`, `StockActionHubView.swift`, `HomeScreen.swift` — unrelated to this task
