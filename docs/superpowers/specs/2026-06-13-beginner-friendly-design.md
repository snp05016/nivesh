# Beginner-Friendly Nivesh — Design Document

> Date: 13 June 2026 | Status: Design Approved | Author: AI-assisted

## 1. Goal

Make Nivesh extremely beginner-friendly. Every financial term has a tap-to-reveal definition, the AI analysis pipeline is explained in plain language, and every AI signal comes with a "Why?" explanation using financial reasoning (not system internals).

## 2. Architecture — What Changes Where

### New Files
| File | Purpose |
|------|---------|
| `ios/.../Views/GlossaryBrowserView.swift` | Searchable glossary tab with categories |
| `ios/.../Views/AIHowItWorksView.swift` | Animated 6-step pipeline explainer |
| `ios/.../Views/TermDefinitionSheet.swift` | Shared sheet for term definitions (definition + example + related terms) |
| `ios/.../Utilities/ExplainableTermModifier.swift` | Universal `.explainableTerm("P/E RATIO")` ViewModifier |

### Modified Files
| File | Change |
|------|--------|
| `ios/.../Utilities/FinanceTerms.swift` | Expand 31 → 60+ terms, add `category` and `relatedTerms` fields |
| `ios/.../Views/StockActionHubView.swift` | Add `(i)` button next to "AI ANALYSIS" header → `AIHowItWorksView` |
| `ios/.../Views/AnalysisScreen.swift` | Add "Explain This Signal" card before AI Verdict |
| `ios/.../Views/StockProfileView.swift` | Replace inline `GlossaryTermModifier` with universal `.explainableTerm()` |
| `ios/.../Views/ContentView.swift` | Add "Learn" tab (`book.pages`) to TabView |
| All screens with financial terms | Replace existing long-press tooltips with tap-to-reveal |

### Not Touched
- **No backend changes** — all data from existing API responses
- **No new LLM calls** — "Explain This Signal" repurposes `bull_case`, `bear_case`, `confidence_rationale`
- **ChartExplainCard**, **TutorialOverlayView**, **OnboardingScreen** — left as-is

## 3. Tap-to-Reveal Glossary — Universal System

### 3.1 Behavior
Every financial term across the app is tappable. Tap opens a `.medium` detent sheet showing definition, example, and related terms. Replaces both `GlossaryTermModifier` (inline popover) and `TermDefinitionOverlay` (long-press tooltip) with a single universal modifier.

### 3.2 API
```swift
Text("P/E Ratio: 32.5")
    .explainableTerm("P/E RATIO")
```
The modifier:
- Underlines the text with `Theme.securityGold` dotted style
- On tap: presents `TermDefinitionSheet` via `.sheet()`
- Looks up `FinanceTerms.shared.lookup(term)` — returns definition + example + related terms + category

### 3.3 Sheet Layout
```
┌──────────────────────────────┐
│  P/E RATIO                    │  officialStampFont, gold
│                               │
│  Price-to-Earnings ratio      │  engravedSerif, inkPrimary
│  compares a company's share   │
│  price to its earnings per    │
│  share...                     │
│                               │
│  ─────────────────────────────│  GuillocheDivider
│  EXAMPLE                      │  officialStampFont small
│  If Reliance trades at ₹2,500 │  engravedSerif italic
│  and earns ₹100 per share...  │
│                               │
│  RELATED: EPS · Market Cap    │  tappable chips
│  📖 View in Glossary           │  opens GlossaryBrowserView
│                               │
│  👆 Tap anywhere to dismiss   │
└──────────────────────────────┘
```

### 3.4 FinanceTerms Expansion (31 → 60+ terms)
Each entry gains: `category: TermCategory` and `relatedTerms: [String]`.

**Categories:** `.valuation`, `.risk`, `.charts`, `.fundamentals`, `.aiAnalysis`, `.macro`, `.ownership`, `.marketMechanics`

**Coverage checklist by screen:**
- **Stock Profile Overview:** P/E, 52W High/Low, Market Cap, Sector, Beta, EPS, Book Value, Face Value, Dividend Yield, Industry P/E
- **Governance:** Promoter Holding, Promoter Pledging, FII, DII, Institutional Ownership, ASM, GSM, Debt/Equity, Pledged Percentage, Key Officers
- **Macro:** MMI, Brent Crude, USD/INR, India VIX, Repo Rate, Current Account Deficit, WPI, CPI, IIP
- **Financials:** Revenue, PAT, EBITDA, ROE, ROCE, Piotroski Score, Operating Margin, Net Profit Margin, Free Cash Flow
- **AI Results:** Signal, Confidence Score, Target Price, Upside/Downside, Bull Case, Bear Case, Key Risks, Staleness, Analysis Tier, Governance Score
- **Charts:** RSI, MACD, SMA, EMA, 50-DMA, 200-DMA, Candlestick, Volume, Support, Resistance
- **Portfolio:** P&L, XIRR, CAGR, Absolute Return, Unrealized P&L, Realized P&L, NAV

## 4. Glossary Browser — New "Learn" Tab

### 4.1 TabView Addition
New tab `book.pages` labeled "Learn". Tab order: `Dashboard · Portfolio · Search · Learn`.

### 4.2 Layout
- Search bar at top — filters live by term name + definition text
- Horizontal category chip scroll: `[All] [Valuation] [Risk] [Charts] [Fundamentals] [AI Analysis] [Macro]`
- Term rows: `officialStampFont` name, category chip in `labelStyle`, first 50 chars of definition
- Tap row → same `TermDefinitionSheet` as tap-to-reveal
- Bottom section: "Recently Viewed" (persisted to `UserDefaults`, max 10)
- Styling: `DenominationBackground(.twoHundred)`, `GuillocheDivider` between search and list

### 4.3 Edge Cases
- Search returns 0 results → "No terms match — try a different word" with 3 suggested terms
- Term has no example → hide EXAMPLE section, show definition only
- Very long definition (>200 chars) → expandable/collapsible in the sheet
- Related term doesn't exist in dictionary → don't render the RELATED section

## 5. How AI Analysis Works — Pipeline Explainer

### 5.1 Entry Point
`(i)` button next to "AI ANALYSIS" section header in `StockActionHubView`. Opens `AIHowItWorksView` as a NavigationStack push.

### 5.2 Content — 6-Step Pipeline Cards
Each step is a tappable card. Tap to expand → shows 2-3 beginner-friendly sentences.

| Step | Icon | Title | Expand Content |
|------|------|-------|---------------|
| 1 | 📡 | Harvest Data | "First, Nivesh gathers real-time data about this stock: latest price, recent news, company filings, promoter shareholding changes, FII/DII investment flows, and broader market indicators like crude oil and the rupee." |
| 2 | ⚡ | Smart Cache Gate | "If the stock has been analysed recently and nothing major has changed, Nivesh skips the full analysis to save time and deliver results in under a second." |
| 3 | 🤖 | Analyst Committee | "Five specialised AI agents examine the stock from different angles." Sub-cards: Market Analyst (price trends, charts), Sentiment Analyst (news tone, social mood), News Analyst (headlines, earnings calls), Fundamentals Analyst (financials, ratios), Governance Analyst (promoter activity, SEBI actions, insider trading) |
| 4 | 🐂🐻 | Bull vs Bear Debate | "Two opposing researchers debate the stock. The Bull argues for buying, the Bear argues against. The Bear's arguments are given 1.5× weight — this is deliberate: Nivesh is designed to be cautious with your money." Bear weight explanation is tappable → "Why?" sheet. |
| 5 | 🧠 | Portfolio Manager | "An experienced AI 'manager' reviews all five analyst reports plus the debate. It weighs the evidence and decides the final recommendation: BUY, HOLD, or SELL, with a confidence percentage." |
| 6 | ✅ | Reformat & Verify | "The final report is checked for accuracy: all numbers are presented in Indian format (Lakhs/Crores, never Millions), emojis are removed for professionalism, and all required data fields are verified present." |

### 5.3 Below the Pipeline Cards
- **Duration section:** "Standard Analysis: 30-60 seconds · Extreme Analysis: 3-5 minutes"
- **What It Analyses:** bullet list of 20+ factors (promoter behavior, FII/DII flows, governance red flags, insider transactions, sector performance, etc.)

### 5.4 Integration
Every technical term in the explainer (FII, DII, promoter holding, etc.) uses `.explainableTerm()` — all terms are tappable for definitions.

## 6. "Explain This Signal" — Plain-Language Financial Reasoning

### 6.1 Purpose
When a beginner sees a BUY/SELL/HOLD signal, they need to understand WHY in financial terms — not system terms. "Revenue grew 15%, debt is low" not "Bull agent scored +23."

### 6.2 Data Source
Uses EXISTING backend fields from the analysis JSON — no new LLM pass:
- `bull_case` → ✅ What's Going Well
- `bear_case` + `key_risks` → ⚠️ What To Watch
- `confidence_rationale` → 📊 Confidence explanation
- `governance_flags` (from `key_factors.governance_assessment`) → ⚠ Governance Alert row

### 6.3 Card Layout
```
┌──────────────────────────────────┐
│  💡 WHY IS THIS A BUY?           │  officialStampFont
│                                  │
│  In simple terms:                │
│                                  │
│  ✅ WHAT'S GOING WELL            │  bullGreen accent
│  • Revenue grew 15% vs 8% avg   │  from bull_case, de-jargonized
│  • Debt is low at 0.3× equity   │
│  • FIIs increased holdings 2.1% │
│  • Promoter holding stable 51%  │
│                                  │
│  ⚠️ WHAT TO WATCH                │  bearRed accent
│  • P/E of 32 above industry 22  │  from bear_case + key_risks
│  • Raw material costs rising    │
│  • 1 governance flag: pending   │
│    SEBI inquiry                  │
│                                  │
│  📊 CONFIDENCE: 75%              │
│  Reasonably confident but       │  from confidence_rationale
│  uncertain about regulatory     │
│  risk and input costs.          │
│                                  │
│  [Underlined terms are tappable]│
└──────────────────────────────────┘
```

### 6.4 Behavior
- Shown expanded on first view per ticker
- Collapsible to 1-line summary: "Tap to understand this BUY signal"
- Collapse state persisted per-ticker in `UserDefaults`
- All financial terms use `.explainableTerm()` — tap for definition
- Adapts title for all 5 signal types:
  - BUY → "Why Is This a BUY?" (bullGreen)
  - C.BULL → "Why Is This Cautiously Bullish?" (bullGreenLight)
  - HOLD → "Why Is This a HOLD?" (holdAmber)
  - C.BEAR → "Why Is This Cautiously Bearish?" (bearRedLight)
  - BEAR → "Why Is This a SELL?" (bearRed)
- If governance flags exist → dedicated ⚠ GOVERNANCE ALERT row with plain-language explanation
- If no analysis cached → "Run an analysis first to see reasoning" placeholder

### 6.5 De-jargonization
The backend's `bull_case` and `bear_case` often contain technical language. The card renders these as-is but every technical term within them is tappable. No automatic rewriting — the terms themselves become the learning opportunity.

## 7. Implementation Phases

Each phase is one commit:

| Phase | What | Files |
|-------|------|-------|
| 1 | Expand FinanceTerms 31→60+ terms, add category/related | `FinanceTerms.swift` |
| 2 | Build `.explainableTerm()` + `TermDefinitionSheet` | `ExplainableTermModifier.swift`, `TermDefinitionSheet.swift` |
| 3 | Build GlossaryBrowser + "Learn" tab | `GlossaryBrowserView.swift`, `ContentView.swift` |
| 4 | Build AIHowItWorksView + `(i)` button | `AIHowItWorksView.swift`, `StockActionHubView.swift` |
| 5 | Build "Explain This Signal" card | `AnalysisScreen.swift` |
| 6 | Apply `.explainableTerm()` to all screens | `StockProfileView.swift`, `AnalysisScreen.swift`, `DashboardView.swift`, etc. |

## 8. Edge Cases

- Signal card adapts text for all 5 signal types (BUY, C.BULL, HOLD, C.BEAR, BEAR)
- No cached analysis → "Explain This" card hidden, shows "Run analysis" placeholder
- Search returns 0 → suggestion text with 3 random popular terms
- Term has no example → EXAMPLE section hidden
- Definition >200 chars → expandable/collapsible in sheet
- Related term missing from dictionary → RELATED section hidden
- Pipeline explainer terms are all tappable via same `.explainableTerm()` system
- Collapse state per-ticker for Explain card — don't annoy returning users
- "Recently Viewed" glossary max 10 entries, persisted to UserDefaults
