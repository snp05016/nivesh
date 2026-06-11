# Stock Profile Expansion — Comprehensive Implementation Prompt
## Target: Claude Code (or any capable AI coding agent)

---

# PROJECT CONTEXT

You are working on **Nivesh** — an iOS fintech app for Indian equity markets built with:
- **Frontend:** SwiftUI (iOS 16+), native Swift Charts, dark Bloomberg-terminal aesthetic
- **Backend:** FastAPI + LangGraph multi-agent AI pipeline, yfinance data sourcing
- **Design system:** All colors via `Theme.*` tokens. No raw hex. No Divider() — use `GuillocheDivider()`/`SectionDivider()`. All prices via `IndianFormatter.price()` / `.priceCompact()`. ₹ prefix, Lakhs/Crores. "Million"/"Billion" FORBIDDEN.
- **Spacing:** Only `Theme.Spacing.*` tokens.
- **Corner radius:** `Theme.CornerRadius.*` only.
- **Cards:** `.banknoteCard()` on every card.
- **Buttons:** `.buttonStyle(EKPressStyle())` + `HapticManager.selection()` on every interactive element.
- **No xcodebuild.**

---

# WHAT ALREADY EXISTS (DO NOT REBUILD)

The Stock Profile screen at `ios/StockApp/stockme/stockme/Views/StockProfileView.swift` currently has 6 tabs:

1. **Overview** — Price hero, key metrics grid (P/E, 52W High, 52W Low, Sector), AI Signal badge
2. **Holders** — Analyst consensus (buy/hold/sell counts)
3. **News** — Recent news cards with images
4. **Updates** — Empty placeholder
5. **Chart** — Interactive Price Chart (candlestick + NIFTY overlay), RSI(14) oscillator, Moving Averages (SMA20/50/200), Quarterly Revenue bars, Quarterly PAT bars, PAT Margin % trend, Shareholding breakdown (Promoter/FII/DII/Public), Promoter Holding history, ROE vs ROCE comparison
6. **Financials** — Quarterly financials table, Piotroski F-Score card

Also already exists in separate screens:
- `AnalysisScreen.swift` — AI deep analysis with bull/bear dialectic, confidence ring, horizon targets
- `EarningsDashboardView.swift` — Earnings calendar and estimates
- `CompareScreen.swift` — Side-by-side stock comparison
- `TechnicalMomentumView.swift` — Technical indicators panel
- `AlertsScreen.swift` — Price alert management
- `DalalStreetConsensusCard.swift` — Cross-ticker advisory consensus
- `ExpertNetworkView.swift` — Advisor biographies and insights
- `TradeJournalScreen.swift` — Trade journaling

Backend endpoints already available (do NOT create duplicates):
- `/quarterly-financials`, `/analyst-ratings`, `/dividends/{ticker}`, `/block-deals/{ticker}`, `/fii-dii-flow`, `/macro-strip`, `/sector-performance`, `/market/sentiment-trend/{ticker}`, `/api/v1/options/chain/{ticker}`, `/api/v1/earnings/estimates`, `/api/v1/market/top-movers`

---

# THE MISSION

Expand the Stock Profile screen from 6 tabs to **12 tabs**, adding **7 new tabs** and **substantially enriching** 2 existing tabs. The goal: make the stock profile the single most comprehensive Indian equity analysis view on iOS — a genuine Trendlyne + Tickertape + Moneycontrol killer.

---

# NEW TABS TO ADD

## Tab 7: Governance 🔴
**Label:** "Governance" | **Icon:** "shield.checkered"

### What to build:

**7a. Red Flags Dashboard**
- Fetch from a NEW backend endpoint: `GET /api/v1/market/governance/{ticker}?exchange=NSE`
- Data model (also new):
```swift
struct GovernanceData: Codable {
    let redFlags: [RedFlag]
    let insiderTrades: [InsiderTrade]
    let pledgedPromoterPct: Double?
    let pledgedPromoterTrend: String? // "improving", "deteriorating", "stable"
    let auditorHistory: [AuditorEvent]
    let sebiSurveillance: Bool?
    let unsolicitedSMS: Bool?
}

struct RedFlag: Codable, Identifiable {
    var id: String { eventDate + category }
    let category: String // "Auditor Resignation", "CFO Departure", "MD Resignation", "Pledged Shares", "SEBI Action", "Insider Selling"
    let title: String
    let eventDate: String
    let severity: String // "critical", "warning", "info"
    let detail: String?
}

struct InsiderTrade: Codable, Identifiable {
    var id: String { "\(personName)-\(tradeDate)-\(transactionType)" }
    let personName: String
    let personDesignation: String
    let transactionType: String // "Buy", "Sell", "Pledge", "Revoke"
    let quantity: Int?
    let valueCrores: Double?
    let tradeDate: String
    let filingDate: String?
}

struct AuditorEvent: Codable, Identifiable {
    var id: String { "\(auditorName)-\(eventDate)" }
    let auditorName: String
    let eventType: String // "Appointed", "Resigned", "Term Changed"
    let eventDate: String
    let reason: String?
}
```

- UI: Red Flags listed as a vertical stack. Critical = deep crimson background (`Theme.bearRed.opacity(0.18)`), warning = amber, info = neutral. Each flag shows: icon + category + title + date. Tappable for detail popover.

**7b. Insider Trading Timeline**
- Vertical timeline UI. Each `InsiderTrade` shown as a dot on a vertical line. Buy = green dot, Sell = red dot. Shows person name, designation, quantity, value in ₹ Crores, date.
- If person is "Promoter" or "Director" — bold the name and add a ⚠️ if selling.

**7c. Promoter Pledged Shares Gauge**
- Circular gauge showing `pledgedPromoterPct` vs total promoter holding.
- Color: <30% = green, 30-50% = amber, >50% = red (existential threat).
- Trend arrow: improving ↓ green, deteriorating ↑ red.
- Label: "PROMOTER PLEDGED SHARES" with glossary explaining why this matters.
- Use `vm.quickInfo?.promoterHoldingPct` for the denominator.

**7d. SEBI Surveillance Status**
- If `sebiSurveillance` or `unsolicitedSMS` is true: show a prominent red warning card:
  "⚠️ This stock is on SEBI's surveillance list / unsolicited SMS watchlist. Exercise extreme caution."
- Otherwise: green checkmark card: "No SEBI surveillance flags detected."

**7e. Auditor History Timeline**
- If `auditorHistory` non-empty: show each auditor event (appointment/resignation).
- Resignations = red highlight. Sudden auditor resignation is the #1 canary in the Indian coal mine.

**Backend work needed:**
Create `GET /api/v1/market/governance/{ticker}` that:
1. Scrapes Trendlyne/BSE for insider trading SAST disclosures
2. Checks SEBI surveillance/unsolicited SMS lists (`_get_asm_gsm_lists()` already exists)
3. Parses recent corporate filings for auditor/CFO/MD resignations
4. Returns the structured `GovernanceData` JSON
5. Caches aggressively (24h TTL) — governance data changes slowly

---

## Tab 8: Macro Impact 🌐
**Label:** "Macro" | **Icon:** "globe.asia.australia"

### What to build:

**8a. FII/DII Flow Context Card**
- Fetch from existing: `GET /fii-dii-flow` (already returns daily FII/DII net buy/sell in Crores)
- Show a mini bar chart: last 10 trading days, green bars = DII net buy, red bars = FII net sell.
- Summary line: "FIIs sold ₹X,XXX Cr this week while DIIs absorbed ₹X,XXX Cr — [domestic accumulation / foreign flight]."
- Color logic: if DIIs buying > FIIs selling → domestic accumulation (bullish). If both selling → bearish.

**8b. Macro-to-Stock Impact Card**
- Fetch from NEW endpoint: `GET /api/v1/market/macro-impact/{ticker}?exchange=NSE`
- Data model:
```swift
struct MacroImpactResponse: Codable {
    let impacts: [MacroImpact]
    let marketMood: MarketMoodData?
}

struct MacroImpact: Codable {
    let macroFactor: String // "Crude Oil", "USD/INR", "RBI Repo Rate", "10Y G-Sec Yield", "CPI Inflation"
    let macroChange: String // "Up 2.3%", "Down 0.5%", "Unchanged at 6.5%"
    let stockImpact: String // "Positive for downstream refining margins", "Negative for import costs"
    let impactDirection: String // "positive", "negative", "neutral"
}

struct MarketMoodData: Codable {
    let mmiScore: Double // 0-100
    let zone: String // "Extreme Fear", "Fear", "Greed", "Extreme Greed"
    let zoneDescription: String
}
```
- UI: Each `MacroImpact` shown as a card with:
  - Macro factor name (small label)
  - Change value (bold)
  - Impact on stock (plain English, `engravedSerif`)
  - Color-coded: green border left for positive, red for negative, neutral for neutral

**8c. Market Mood Index (MMI) Gauge**
- Speedometer-style semi-circle gauge using SwiftUI `Path` + `Arc`.
- Gradient from deep red (0-30 Extreme Fear) → amber (30-50 Fear) → light green (50-70 Greed) → bright green (70-100 Extreme Greed).
- Needle pointing to current MMI score.
- Label below: "Market Mood: Extreme Fear — historically optimal time to deploy capital."
- Animate needle on appear.

**8d. Sector & Peer Context**
- Fetch from existing: `GET /sector-performance`
- Show the stock's sector performance in a mini card.
- If sector is underperforming Nifty: show comparison line. "Your stock's sector is lagging Nifty by X.X% this month."

**Backend work needed:**
Create `GET /api/v1/market/macro-impact/{ticker}` that:
1. Identifies the stock's sector/industry from QuickInfo
2. Maps macro factors (crude, USD/INR, repo rate, etc.) to sector sensitivities using an LLM agent
3. Computes MMI from market internals (PCR ratio, VIX, FII/DII flows, advance-decline ratio, Nifty vs 50DMA, etc.)
4. Returns structured `MacroImpactResponse`

---

## Tab 9: Technicals 📊
**Label:** "Technicals" | **Icon:** "waveform.path.ecg"

### What to build:

**9a. Technical Indicators Summary Grid**
- Compute on-device from `vm.history?.prices` (OHLCV data).
- Show as a 2-column grid of indicator cards:
  - **RSI(14):** Value + "Oversold (<30) / Neutral / Overbought (>70)" + plain English translation
  - **MACD:** MACD line value, Signal line value, Histogram. "Bullish crossover / Bearish crossover / Neutral."
  - **Bollinger Bands:** Current price vs Upper/Middle/Lower band. "%B" value.
  - **52-Week Position:** Current price as % between 52W high and 52W low. "Trading at X% of 52W range."
  - **Volume Analysis:** Current volume vs 20-day avg volume. "X% above/below average."
  - **ATR (14):** Average True Range value. "Typical daily swing is ₹X."

- Each card: `.banknoteCard()`, label + value + one-line plain-English explanation.
- Use existing `computeRSI()` pattern. Add helpers:
```swift
private func computeMACD(_ prices: [OHLCVPoint]) -> (macdLine: Double, signalLine: Double, histogram: Double, signal: String)
private func computeBollingerBands(_ prices: [OHLCVPoint]) -> (upper: Double, middle: Double, lower: Double, percentB: Double)
private func computeATR(_ prices: [OHLCVPoint], period: Int = 14) -> Double
```

**9b. Support & Resistance Levels**
- Compute pivot points from recent OHLCV data.
- Show as horizontal levels on a mini price chart.
- Label: S1, S2 (support), Pivot, R1, R2 (resistance).
- Current price marker.

**9c. Price Performance Table**
- Data from `vm.quickInfo` + computed from `vm.history`.
- Table format:
  | Period | Return % | vs Nifty % |
  |--------|----------|------------|
  | 1 Week | +X.X%   | +X.X%      |
  | 1 Month| +X.X%   | +X.X%      |
  | 3 Month| +X.X%   | +X.X%      |
  | 6 Month| +X.X%   | +X.X%      |
  | 1 Year | +X.X%   | +X.X%      |
  | YTD    | +X.X%   | +X.X%      |

- Green for positive, red for negative. Bold if beating Nifty.

**9d. Moving Average Ribbon**
- Visual ribbon showing SMA5, SMA10, SMA20, SMA50, SMA100, SMA200 as stacked lines.
- Toggle to show/hide individual MAs.
- Existing `showSMA` state already tracks 20/50/200. Extend to support 5/10/100.

---

## Tab 10: Valuations 💎
**Label:** "Valuations" | **Icon:** "dollarsign.circle"

### What to build:

**10a. Valuation Multiples Card**
- Data from `vm.quickInfo` (peRatio, debtToEquity, roePct, rocePct, ebitdaMarginPct already available).
- Show as a horizontal bar comparison vs industry average:
  - P/E Ratio vs Industry P/E (use `peVsAvg` from QuickInfo)
  - EV/EBITDA (compute or fetch)
  - P/B Ratio (fetch or compute)
  - Debt/Equity vs Industry D/E
  - Dividend Yield
- Each bar: colored green if better than industry, red if worse.

**10b. Historical P/E Band Chart**
- Fetch from NEW endpoint or compute from price history + earnings data.
- Chart showing stock price overlaid with P/E bands (e.g., 10×, 15×, 20×, 25×, 30× TTM earnings).
- Shows where the stock is currently trading relative to its historical valuation range.
- This is the signature Trendlyne feature — MUST implement.

**10c. Earnings Yield vs Bond Yield**
- Earnings yield = 1 / P/E ratio.
- Compare to 10Y G-Sec yield.
- If earnings yield > bond yield → stocks are cheaper than bonds → bullish.
- Visual: two horizontal bars side by side.

**10d. DCF Fair Value Estimate (if possible)**
- If backend can provide: show an AI-estimated fair value range.
- "Based on our AI model, fair value range: ₹X,XXX — ₹X,XXX (X% upside/downside)."

---

## Tab 11: Dividends & Corp Actions 💰
**Label:** "Dividends" | **Icon:** "indianrupeesign.circle"

### What to build:

**11a. Dividend History Chart**
- Fetch from existing: `GET /dividends/{ticker}?exchange=NSE`
- Bar chart: dividend per share by year.
- Summary: "5Y Avg Dividend: ₹X | Current Yield: X.X% | Payout Ratio: X%"

**11b. Upcoming Corporate Actions**
- Bonus issues, stock splits, rights issues, buybacks, dividend announcements.
- Table with: Action Type, Ratio/Amount, Announcement Date, Ex-Date, Record Date.
- Color-coded by action type.

**11c. Dividend Growth Rate**
- If 5+ years of dividend data: compute CAGR.
- Show as a stat: "Dividend CAGR (5Y): X.X%"
- Chart: dividend per share trend line with growth rate annotation.

---

## Tab 12: Options Chain (for advanced users) 📈
**Label:** "Options" | **Icon:** "chart.line.flattrend.xyaxis"

### What to build:

**12a. Options Summary Card**
- Fetch from existing: `GET /api/v1/options/chain/{ticker}?exchange=NSE`
- Show:
  - Put/Call Ratio (PCR): current value + interpretation
  - Max Pain strike price
  - Implied Volatility (IV): current IV, IV Rank, IV Percentile
  - Total Call OI vs Total Put OI

**12b. Options Chain Table**
- For the nearest monthly expiry.
- Scrollable horizontal table showing:
  | Strike | Call OI | Call LTP | Call IV | | Put LTP | Put IV | Put OI |
- Color-code: green for high OI buildup, red for low.
- Default: show ±5 strikes around ATM.

**12c. Open Interest Analysis**
- If OI data available: chart showing OI concentration by strike.
- "Resistance at ₹X,XXX (highest Call OI) | Support at ₹X,XXX (highest Put OI)."
- This helps identify key levels options traders are watching.

---

# ENHANCE EXISTING TABS

## Enhance Tab 5: Charts
Add to the existing chart tab:

**Chart 10: Volume Profile (Visible Range)**
- Horizontal histogram on the right side of the price chart showing volume at each price level.
- Helps identify high-volume nodes (support/resistance).

**Chart 11: MACD Panel**
- Below existing price chart: MACD line (blue), Signal line (gold), Histogram (green/red bars).
- Standard layout: price chart on top, MACD below.

**Chart 12: Rate of Change (ROC)**
- Line chart showing 14-day rate of change in %.

## Enhance Tab 1: Overview
Add to overview tab:

**Market Cap & Enterprise Value**
- Show market cap in ₹ Crores/Lakhs.
- Enterprise Value = Market Cap + Debt - Cash.
- Add to metrics grid.

**Key Statistics Grid Upgrade**
- Add: Dividend Yield, Book Value per Share, Face Value, EPS (TTM), P/B Ratio.
- Use data from QuickInfo (extend if needed).

**Company Description**
- If `vm.quickInfo?.description` is non-nil: show a collapsible section with company description in `engravedSerif`.
- Truncated to 3 lines with "Read more" expand button.

---

# BACKEND API ADDITIONS (SUMMARY)

Create these NEW backend endpoints:

1. `GET /api/v1/market/governance/{ticker}?exchange=NSE`
   → Returns `GovernanceData` (red flags, insider trades, pledged shares, auditor history, SEBI status)

2. `GET /api/v1/market/macro-impact/{ticker}?exchange=NSE`
   → Returns `MacroImpactResponse` (macro factor impacts on stock, MMI score)

3. `GET /api/v1/market/pe-band/{ticker}?exchange=NSE`
   → Returns PE band data for historical valuation chart

4. `GET /api/v1/market/corporate-actions/{ticker}?exchange=NSE`
   → Returns upcoming and historical corporate actions (bonus, splits, buybacks, rights)

5. `GET /api/v1/market/technical-summary/{ticker}?exchange=NSE`
   → Returns pre-computed technical indicators to supplement on-device computation (optional — most can be computed on-device)

6. Extend existing `GET /api/v1/market/quick-info/{ticker}` (or QuickInfo model) to include:
   - `market_cap_crores`
   - `enterprise_value_crores`
   - `book_value_per_share`
   - `dividend_yield_pct`
   - `eps_ttm`
   - `face_value`
   - `price_to_book`
   - `industry_pe`
   - `sector_name`

---

# iOS FILES TO CREATE/MODIFY

## New files to create:

| File | Purpose |
|------|---------|
| `ios/StockApp/stockme/stockme/Views/GovernanceTab.swift` | Governance tab (Tab 7) |
| `ios/StockApp/stockme/stockme/Views/MacroImpactTab.swift` | Macro Impact tab (Tab 8) |
| `ios/StockApp/stockme/stockme/Views/TechnicalsTab.swift` | Technicals tab (Tab 9) |
| `ios/StockApp/stockme/stockme/Views/ValuationsTab.swift` | Valuations tab (Tab 10) |
| `ios/StockApp/stockme/stockme/Views/DividendsTab.swift` | Dividends tab (Tab 11) |
| `ios/StockApp/stockme/stockme/Views/OptionsTab.swift` | Options tab (Tab 12) |
| `ios/StockApp/stockme/stockme/Models/GovernanceModels.swift` | Governance data models |
| `ios/StockApp/stockme/stockme/Models/MacroModels.swift` | Macro impact data models |
| `ios/StockApp/stockme/stockme/Models/ValuationModels.swift` | Valuation data models |
| `ios/StockApp/stockme/stockme/Charts/VolumeProfileChart.swift` | Volume Profile chart component |
| `ios/StockApp/stockme/stockme/Charts/PEBandChart.swift` | PE Band chart component |
| `ios/StockApp/stockme/stockme/Charts/MMIGaugeView.swift` | Market Mood Index gauge |
| `ios/StockApp/stockme/stockme/Charts/TechnicalIndicatorCards.swift` | Technical indicator card components |
| `ios/StockApp/stockme/stockme/Utilities/TechnicalCalculations.swift` | Technical indicator computation helpers |

## Existing files to modify:

| File | Changes |
|------|---------|
| `ios/StockApp/stockme/stockme/Views/StockProfileView.swift` | Add 7 new tabs to `tabItems`; add corresponding `@ViewBuilder private var` for each new tab; add `chartSection_VolumeProfile()`, `chartSection_MACD()`, `chartSection_ROC()` to chartTab; enhance `overviewTab` with additional metrics; add new `@State` variables for loading states; add `.task` modifiers for new data fetching |
| `ios/StockApp/stockme/stockme/StockProfileViewModel.swift` | Add `@Published` properties for governance, macro, technical, valuation, dividend, options, corp actions data; add corresponding `fetchXXX()` async methods |
| `ios/StockApp/stockme/stockme/Models.swift` | Add new model structs: `GovernanceData`, `RedFlag`, `InsiderTrade`, `AuditorEvent`, `MacroImpactResponse`, `MacroImpact`, `MarketMoodData`, `CorporateActionsResponse`, `CorporateAction`, `OptionsChainResponse`, `PEBandData`, `TechnicalSummaryResponse`; extend `QuickInfo` with new optional fields |
| `ios/StockApp/stockme/stockme/NetworkManager.swift` | Add API call methods: `fetchGovernance()`, `fetchMacroImpact()`, `fetchPEBand()`, `fetchCorporateActions()`, `fetchOptionsChain()`; extend `quickInfo()` response mapping for new fields |
| `ios/StockApp/stockme/stockme/BanknoteDesignSystem.swift` | Add new color tokens if needed: `governanceRed`, `governanceAmber`, `mmiGradient` |
| `backend/routers/market.py` | Add 5 new endpoints (governance, macro-impact, pe-band, corporate-actions, technical-summary) |
| `backend/services/` | Add `governance_scraper.py`, `macro_impact_agent.py`, `pe_band_calculator.py` |

---

# DESIGN SYSTEM CONSTRAINTS (MANDATORY — VIOLATION = REJECTION)

Every single view, card, text, and chart MUST follow these rules exactly:

## Typography
- Section headers: `Theme.officialStampFont(size: 9).tracking(1.5).foregroundStyle(Theme.inkTertiary)`
- Large values: `Theme.serialNumberFont(size: 28-32, relativeTo: .largeTitle)` for hero numbers; `Theme.serialNumberFont(size: 13-16, relativeTo: .body)` for regular values
- Body text: `Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body)` for explanations
- Micro labels: `Theme.microLabel(size: 8-9).foregroundStyle(Theme.inkTertiary)`
- Tab labels: `Theme.officialStampFont(size: 9).tracking(1.0)` — active = `Theme.securityGold`, inactive = `Theme.inkTertiary`
- NO system fonts, NO `.title`, NO `.body`, NO `.caption` directly — always through Theme

## Colors
- Positive/Bullish: `Theme.bullGreen`
- Negative/Bearish: `Theme.bearRed`
- Warning/Hold: `Theme.holdAmber`
- Gold/Accent: `Theme.securityGold`
- Blue accent: `Theme.avatarBlue`
- Text primary: `Theme.inkPrimary`
- Text secondary: `Theme.inkSecondary`
- Text tertiary: `Theme.inkTertiary`
- Card background: `Theme.canvasDeep` (via `.banknoteCard()`)
- Canvas: `Theme.canvas` (screen background)
- Dividers: `Theme.borderFine` (0.5pt)
- NO raw hex, NO `.blue`, NO `.red`, NO `.green`

## Cards & Layout
- Every content card: `.banknoteCard()` modifier
- Section spacing: `Theme.sectionSpacing` or `Theme.Spacing.xLarge` (32pt) between major sections
- Card internal padding: `Theme.Spacing.card` (16pt)
- Horizontal margins: `Theme.screenPadding` (20pt)
- Row separators between list items: `Theme.borderFine` 0.5pt line, NOT `GuillocheDivider`
- `GuillocheDivider()` only between major conceptual sections
- TabView style: `.page(indexDisplayMode: .never)` with horizontal scroll tab bar
- ScrollView as outer container for each tab

## Charts
- Use native Swift Charts only (iOS 16+)
- Height constraint: `.frame(height: UIScreen.main.bounds.height * 0.25)` for supplementary charts
- Hero charts can be taller: up to `0.28`
- Axis labels: `Theme.microLabel(size: 9)` or `AxisValueLabel()` with default styling
- Grid lines: `AxisGridLine().foregroundStyle(Theme.borderFine)`
- Chart overlay (scrub): dashed vertical line + tooltip card with `Theme.canvasDeep` background

## Emoji & Icons
- SF Symbols for all icons in tab bar and indicator labels
- Strip emoji from all AI-generated text using `stripEmoji()` (already exists in Utilities)
- Emoji allowed ONLY in user-facing severity indicators (⚠️ 🔴) in governance tab — but prefer SF Symbols

## Indian Formatting
- ALL monetary values: `IndianFormatter.price()` or `.priceCompact()` with ₹ prefix
- Lakhs (L) and Crores (Cr) ONLY. Million/Billion/Thousand FORBIDDEN
- Market cap: "₹X,XXX Cr" format
- Volume: comma-separated integers (no decimal for volumes)

---

# IMPLEMENTATION ORDER (MUST FOLLOW)

1. **Models first** — Add all new model structs to `Models.swift` (or new model files). Extend `QuickInfo` with new fields.
2. **Backend endpoints** — Create the 5 new API endpoints with proper caching (Redis/dict cache). Use existing patterns from `market.py`.
3. **NetworkManager** — Add fetch methods for all new endpoints. Follow existing pattern of `NetworkManager.shared.xxx()`.
4. **ViewModel** — Extend `StockProfileViewModel` with new `@Published` properties and `fetchXXX()` methods.
5. **View files** — Create each new tab view file. Then modify `StockProfileView.swift` to integrate them.
6. **Chart components** — Build reusable chart components (VolumeProfile, PEBand, MMIGauge).
7. **Integration & polish** — Wire everything together, test data flow, ensure loading/error/empty states work.

---

# STATE MANAGEMENT

Each new tab follows the same pattern:
```swift
// In StockProfileViewModel:
@Published var governanceData: GovernanceData?
@Published var governanceLoading = false
@Published var macroImpact: MacroImpactResponse?
@Published var macroLoading = false
// ... etc for each tab

func fetchGovernance() async { /* pattern identical to fetchOverview() */ }
func fetchMacroImpact() async { /* pattern identical to fetchOverview() */ }
```

Each tab in StockProfileView:
```swift
governanceTab
    .task { await vm.fetchGovernance() }
```

Loading state: `skeletonBlock(rows: N)` while loading.
Empty state: `emptyState(message: "...")` if data unavailable.
Error state: handled gracefully by `emptyState` (data stays nil).

---

# LOADING STRATEGY

- Overview, Chart, and Financials: load immediately (`.task` on appear) — EXISTING, DO NOT CHANGE
- Holders, News: load on tab switch — EXISTING, DO NOT CHANGE
- Governance, Macro, Technicals, Valuations, Dividends, Options: **lazy-load on first tab visit only** (guard `== nil` before fetch, same pattern as existing tabs)
- Do NOT pre-fetch all tabs — this would flood the backend

---

# EDGE CASES & EMPTY STATES

Every tab must handle:
- **Loading**: `skeletonBlock(rows: N)` shimmer animation
- **Empty**: `emptyState(message: "...")` with appropriate SF Symbol icon
- **Partial data**: Show available sections, skip nil/empty sections gracefully
- **Error**: Treated same as empty (no retry UI in v1; user can switch tabs and come back)
- **Penny stocks / illiquid stocks**: May have no options chain, no analyst coverage, minimal governance data — handle gracefully

---

# CRITICAL "DO NOT" RULES

1. **DO NOT** change the tab bar design or navigation architecture
2. **DO NOT** modify existing tabs (Overview, Holders, News, Updates, Chart, Financials) beyond the specified enhancements — they already work
3. **DO NOT** remove or alter any existing `@ViewBuilder` functions
4. **DO NOT** change the `StockProfileViewModel` init signature
5. **DO NOT** introduce third-party Swift Package dependencies
6. **DO NOT** use Divider() — use `GuillocheDivider()` or `SectionDivider()` or raw `Rectangle().fill(Theme.borderFine).frame(height: 0.5)`
7. **DO NOT** use raw hex colors, `.blue`, `.red`, `.green`, or system font modifiers
8. **DO NOT** use "Million" or "Billion" in any text — Lakhs and Crores only
9. **DO NOT** create a second runtime or provider switcher
10. **DO NOT** emit emoji in AI-generated text — always `stripEmoji()`

---

# SUCCESS CRITERIA

After implementation, a user viewing any stock in the Nivesh app should see:
- **12 tabs** in the horizontal tab bar (6 existing + 6 new, Updates tab gets replaced by one of the new ones or kept as-is depending on space)
- Governance: Red flags, insider trades, pledged shares gauge, auditor history, SEBI status
- Macro: FII/DII flows, macro-to-stock impact cards, Market Mood Index gauge
- Technicals: RSI, MACD, Bollinger Bands, ATR, volume analysis, support/resistance, performance table
- Charts (enhanced): Volume profile, MACD panel, ROC indicator added to the existing 9 charts
- Valuations: PE band chart, valuation multiples vs industry, earnings yield vs bond yield
- Dividends: Dividend history chart, upcoming corporate actions, dividend CAGR
- Options: Options chain table, PCR, max pain, IV metrics
- Overview (enhanced): Additional metrics (market cap, EV, book value, dividend yield, EPS, P/B)

---

# APPENDIX: Complete Tab Structure Reference

```
StockProfileView tabs (final):
0: Overview     (enhanced: +market cap, EV, BV, div yield, EPS, PB, description)
1: Governance   (NEW: red flags, insider trades, pledged shares, auditor history, SEBI)
2: Holders      (existing: analyst consensus)
3: News         (existing: recent news)
4: Macro        (NEW: FII/DII flows, macro impacts, MMI gauge, sector context)
5: Technicals   (NEW: indicators grid, support/resistance, performance table)
6: Charts       (enhanced: +volume profile, MACD panel, ROC)
7: Valuations   (NEW: PE band, multiples vs industry, earnings yield vs bond yield)
8: Dividends    (NEW: dividend history, corp actions, dividend CAGR)
9: Financials   (existing: quarterly table, Piotroski F-Score)
10: Options     (NEW: options chain, PCR, max pain, IV metrics)
```

Note: This is 11 tabs total (not 12). The existing "Updates" tab (index 3, placeholder) gets **replaced** by the Governance tab. The tab order is reorganized to flow logically: Overview → Governance → Holders → News → Macro → Technicals → Charts → Valuations → Dividends → Financials → Options.

---

# ESTIMATED EFFORT

- Backend: ~2,000-3,000 lines of Python (5 endpoints + scrapers + agents)
- iOS Models: ~300-500 lines (new model structs)
- iOS NetworkManager: ~200-400 lines (new API calls)
- iOS ViewModel: ~200-300 lines (new fetch methods + properties)
- iOS Views: ~5,000-8,000 lines (7 new tabs + enhanced existing tabs)
- iOS Charts: ~800-1,500 lines (new chart components)
- iOS Utilities: ~200-400 lines (technical indicator calculations)
- **Total:** ~9,000-14,000 lines of new code

---

# BEGIN IMPLEMENTATION

Start with Step 1 (Models), then proceed sequentially. Commit after each completed step. Do NOT skip steps or implement out of order.
