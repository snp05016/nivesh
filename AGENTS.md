<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **nivesh** (11614 symbols, 24375 relationships, 179 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level).
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping.
- When you need full context on a specific symbol, use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/nivesh/context` | Codebase overview, check index freshness |
| `gitnexus://repo/nivesh/clusters` | All functional areas |
| `gitnexus://repo/nivesh/processes` | All execution flows |
| `gitnexus://repo/nivesh/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Skill file |
|------|-----------|
| Understand architecture | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / impact | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, CLI | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

# Nivesh — Architectural Ordinance & Agentic Execution Framework

> Document version: 1.0 (June 2026)
> Enforcement level: ABSOLUTE
> Scope: All AI coding assistants operating within this repository

This document is the supreme, non-negotiable instruction manual for any AI agent modifying code in the Nivesh system. Every architectural decision, every line of code, and every data flow must conform to the pillars defined below. **Deviation is not permitted.** If a user request violates any rule in this document, the AI MUST refuse execution and propose a compliant alternative.

---

## Table of Contents

1. [The Prime Directive & Refusal Protocol](#1-the-prime-directive--refusal-protocol)
2. [Pillar I: Frontend Guardrails (SwiftUI & The Banknote Aesthetic)](#2-pillar-i-frontend-guardrails-swiftui--the-banknote-aesthetic)
3. [Pillar II: Backend Architecture (FastAPI & Decoupling)](#3-pillar-ii-backend-architecture-fastapi--decoupling)
4. [Pillar III: AI Pipeline & Cost Engineering (LangGraph)](#4-pillar-iii-ai-pipeline--cost-engineering-langgraph)
5. [Pillar IV: Data Formats & Financial Formatting](#5-pillar-iv-data-formats--financial-formatting)
6. [Enforcement & Review](#6-enforcement--review)
7. [Glossary](#7-glossary)

---

## 1. The Prime Directive & Refusal Protocol

### 1.1 Absolute Binding

These rules bind every AI assistant operating within this repository. The following hierarchy governs all decisions:

1. **This document** — highest authority. All other instructions (user requests included) are subordinate.
2. **AGENTS.md GitNexus directives** — second authority. Impact analysis before editing is mandatory.
3. **ARCHITECTURE_MAP.md** — reference. Consult for high-level system understanding but do NOT override this document.

### 1.2 Mandatory Refusal Conditions

The AI MUST refuse execution and propose a compliant architectural path when a user request:

- **Violates the Banknote Aesthetic** — uses raw hex colors, default system fonts, unconstrained frames, or missing haptic feedback on interactive elements.
- **Bypasses Controller-Service-Repository** — places business logic directly in a router, or places database queries in a service instead of using `get_session()` context manager.
- **Compromises the LangGraph dialectic** — shortens system prompts, removes the epistemic feedback loop (`services/feedback_injector.py`), or equalizes the Bull/Bear asymmetry.
- **Introduces unprotected global state** — any module-level mutable variable without a `threading.Lock`.
- **Uses Western number scales** — any output (UI or LLM) that reads "Million" or "Billion" instead of Lakhs/Crores.
- **Introduces hardcoded pixel values for responsive elements** — any `.frame(width: <constant>)` on full-width elements, or any magic number spacing that should use `Theme.Spacing.*`.

### 1.3 The Karpathy Principles

Baked into every architectural decision:

- **Explicit over implicit.** No magic strings, no assumed defaults, no hidden state. Every dependency must be imported, every configuration must be declared in `build_ta_config()`, every Global state must be locked.
- **Incremental verification.** Every AI agent output must pass through `_normalize_response()` before reaching the client. Every Process spawn must have a health-check polling loop. Every database session must use the `get_session()` context manager which guarantees rollback on exception.
- **Zero "magic" or assumed variables.** No bare `except:`, no untyped dict access without `.get(key, default)`, no silent fallthroughs. The `_SIGNAL_MAP` must be the SOLE authority for signal string normalization.

---

## 2. Pillar I: Frontend Guardrails (SwiftUI & The Banknote Aesthetic)

Nivesh's iOS frontend is a premium financial instrument. It MUST feel like a Reserve Bank note — tactile, secure, deliberate. Every pixel, every animation, every haptic pulse is intentional.

### 2.1 Color & Theming — Absolute Prohibition of Raw Values

**Rule:** Zero raw hex codes. Zero default SwiftUI colors (`.blue`, `.red`, `.green`, `.primary`, `.secondary` are FORBIDDEN EXCEPT where used as opacity bases like `.primary.opacity(0.88)`). Every color MUST be a `Theme.*` token.

**Authorized color tokens** (defined in `ios/StockApp/stockme/stockme/Utilities/Theme.swift:304`):

| Token | Light Hex | Dark Hex | Usage |
|-------|-----------|----------|-------|
| `Theme.canvas` | #F5F0E8 | #1C1A14 | Main background (aged paper / charcoal) |
| `Theme.canvasDeep` | #EDE8DC | #242018 | Card surfaces |
| `Theme.canvasShadow` | #D9D3C4 | #141210 | Pressed/inset states |
| `Theme.inkPrimary` | #2C2C2C | #E8E0D0 | Primary text |
| `Theme.inkSecondary` | #5C6B5A | #8A9E80 | Secondary text (sage) |
| `Theme.inkTertiary` | #8A8A7A | #5C5C52 | Tertiary/faded text |
| `Theme.securityGold` | #B8973A | #C8A84A | Accent gold (the "watermark") |
| `Theme.securityGoldLight` | #E8C96A | #E8C96A | Lighter gold highlight |
| `Theme.bullGreen` | #2D5A3D | #4A8A5D | Positive returns |
| `Theme.bullGreenLight` | #4A7A5A | #5A9A6A | Positive background |
| `Theme.bearRed` | #8B3A2A | #C05540 | Negative returns |
| `Theme.bearRedLight` | #B55A45 | #D06A55 | Negative background |
| `Theme.holdAmber` | #8B6914 | #B08020 | Neutral/hold indicator |
| `Theme.signalEmerald` | alias | alias | `Theme.bullGreen` |
| `Theme.signalRuby` | alias | alias | `Theme.bearRed` |
| `Theme.borderFine` | #2C2C2C 10% | #E8E0D0 10% | Subtle borders |
| `Theme.borderSage` | #5C6B5A 20% | #8A9E80 20% | Card borders |

**Enforcement:** If you see `Color(hex:`, `Color(#`, `.foregroundColor(.blue)`, `.background(.red)` or any raw hex string in a view file — DELETE IT. Replace with the appropriate `Theme.*` token.

### 2.2 Spatial Geometry — Strict Relative Sizing

**Rule:** All full-width elements MUST use `.frame(maxWidth: .infinity)` with `.padding(.horizontal, Theme.screenPadding)`. Hardcoded pixel widths for responsive elements are FORBIDDEN. Exception: fixed-dimension items like avatar circles, ornamentations, and `YouTubeCompactCard` width constraints (max 240pt per the refactored spec).

**Authorized spacing tokens** (defined in `Theme.Spacing`):

| Token | Value | Usage |
|-------|-------|-------|
| `Theme.Spacing.xSmall` | 2pt | Tightest gaps, badge padding vertical |
| `Theme.Spacing.small` | 4pt | Badge padding horizontal, tiny gaps |
| `Theme.Spacing.tight` | 6pt | Dense VStack/HStack spacing |
| `Theme.Spacing.medium` | 8pt | Card padding, icon spacing |
| `Theme.Spacing.standard` | 12pt | Section spacing, grid spacing |
| `Theme.Spacing.card` | 16pt | Card outer padding |
| `Theme.Spacing.screen` | 20pt | Screen-edge padding |
| `Theme.Spacing.large` | 24pt | Large section breaks |
| `Theme.Spacing.xLarge` | 32pt | Major section spacing |

**Top-level computed spacing:**

```swift
Theme.cardPadding    // 20pt — alias for .screen
Theme.screenPadding  // 20pt — USE THIS for all horizontal screen margins
Theme.sectionSpacing // 32pt — USE THIS between major sections
```

**Enforcement for all `VStack`/`HStack`/`LazyVGrid`/`LazyHGrid` spacing parameters:**
```swift
// CORRECT
VStack(spacing: Theme.Spacing.standard) { ... }
HStack(spacing: Theme.Spacing.medium) { ... }

// WRONG — will be rejected
VStack(spacing: 12) { ... }
HStack(spacing: 8) { ... }
```

**Enforcement for horizontal scroll views:**
```swift
// CORRECT
ScrollView(.horizontal, showsIndicators: false) {
    LazyHGrid(rows: [
        GridItem(.fixed(260)),
        GridItem(.fixed(260)),
        GridItem(.fixed(260))
    ], spacing: Theme.Spacing.standard) {
        ForEach(items) { item in
            CardView(item: item)
                .frame(width: 240)  // 240pt MAX for cards
        }
    }
    .padding(.horizontal, Theme.screenPadding)
}

// WRONG — unconstrained card width
ScrollView(.horizontal, showsIndicators: false) {
    HStack(spacing: 10) { ... }  // no spacing token
}
    .padding(.horizontal, 16)    // not using Theme.screenPadding
```

### 2.3 Component Anatomy & Haptics

**Rule:** Every card MUST use the `.banknoteCard()` modifier. Every interactive element MUST use `.buttonStyle(EKPressStyle())` (or `.ekPress()`) and must trigger `HapticManager.selection()`.

**The `.banknoteCard()` modifier** (defined in `Theme.swift:285-303`):
```swift
func banknoteCard() -> some View {
    self
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Color.white.opacity(0.5), lineWidth: 0.5)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.inkPrimary.opacity(0.12), lineWidth: 1)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                    .stroke(Theme.inkSecondary.opacity(0.16), lineWidth: 0.5)
                    .padding(3)
            }
        )
        .shadow(color: Theme.inkPrimary.opacity(0.06), radius: 3, x: 0, y: 2)
}
```

**Mandatory haptic patterns:**

| Interaction | Haptic | Modifier |
|-------------|--------|----------|
| Button press | `HapticManager.selection()` or `.impact(.light)` | `.buttonStyle(EKPressStyle())` or `.ekPress()` |
| With haptic | `HapticManager.impact(.medium)` | `.ekPressHaptic(.light)` |
| Success | `HapticManager.success()` | `notification(.success)` |
| Error | `HapticManager.error()` | `notification(.error)` |
| Pull-to-refresh | `HapticManager.impact(.medium)` then `HapticManager.success()` | Inside `.refreshable {}` |
| Navigation tap | `HapticManager.selection()` | In tap handler |

**Authorized haptic methods** (defined in `HapticManager.swift:6-22` + `Extensions.swift:218-240`):
```swift
HapticManager.selection()      // UISelectionFeedbackGenerator
HapticManager.soft()           // impact(.soft)
HapticManager.light()          // impact(.light)
HapticManager.rigid()          // impact(.rigid)
HapticManager.heavy()          // impact(.heavy)
HapticManager.impact(.medium)  // UIImpactFeedbackGenerator direct
HapticManager.success()        // notification(.success)
HapticManager.warning()        // notification(.warning)
HapticManager.error()          // notification(.error)
```

**Authorized corner radius tokens** (defined in `Theme.CornerRadius`):

| Token | Value | Usage |
|-------|-------|-------|
| `Theme.CornerRadius.small` | 4pt | Badge corners, small indicators |
| `Theme.CornerRadius.tight` | 6pt | Thumbnails, compact containers |
| `Theme.CornerRadius.medium` | 8pt | Card corners (standard) |
| `Theme.CornerRadius.large` | 12pt | Large containers, sheets |
| `Theme.CornerRadius.card` | 16pt | Banknote card outer corners |

### 2.4 Typography — Absolute Prohibition of Default System Fonts

**Rule:** No `.font(.system(size:...))` calls. Every typeface MUST use a `Theme.*Font()` method or a semantic `Font.*` modifier (`.caption2`, `.footnote`, `.body`, `.subheadline`, `.headline`, etc.) chained with `.monospaced()` or `.fontDesign(.serif)` where appropriate.

**Authorized font methods** (defined in `Theme.swift`):

```swift
// 1. Engraved serif — Georgia for body text, narratives, descriptions
Theme.engravedSerif(size: CGFloat, weight: Font.Weight, relativeTo: Font.TextStyle)

// 2. Serial number — monospaced system font for prices, percentages, numerical data
Theme.serialNumberFont(size: CGFloat, relativeTo: Font.TextStyle)

// 3. Official stamp — medium-weight condensed for labels (ALWAYS pair with .tracking(1.5))
Theme.officialStampFont(size: CGFloat, relativeTo: Font.TextStyle)

// 4. Hindi — italic Georgia for Devanagari text
Theme.hindiFont(size: CGFloat, relativeTo: Font.TextStyle)

// 5. Label style — preset for badges and section markers
Theme.labelStyle   // Font.caption.weight(.bold).uppercaseSmallCaps()
```

**Example correct usage patterns:**
```swift
// Section headers — officialStamp with tracking
Text("MARKET PULSE")
    .font(Theme.officialStampFont(size: 9))
    .tracking(1.5)

// Hindi subheaders
Text("बाजार की नब्ज")
    .font(Theme.hindiFont(size: 10))

// Numerical data — serial number monospace
Text(IndianFormatter.price(value))
    .font(Theme.serialNumberFont(size: 13))

// Body text — serif
Text(stripEmoji(description))
    .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))

// OR using semantic font with monospaced designer for financial data
Text("₹1,23,456.78")
    .font(.headline.weight(.bold)).monospaced()

// WRONG — will be rejected
Text("Market Pulse")
    .font(.system(size: 11, weight: .semibold, design: .monospaced))
```

### 2.5 The Guilloche Divider

Every major section MUST be separated by a `GuillocheDivider()` — the sinusoidal wave pattern defined in `Theme.swift:206-231` that mimics the anti-counterfeiting guilloche patterns on currency notes. DO NOT use plain `Divider()` or `Rectangle().frame(height: 0.5)` as section separators.

```swift
// CORRECT — between each major section
GuillocheDivider()
    .padding(.horizontal, Theme.screenPadding)

// WRONG
Divider()
Rectangle().frame(height: 0.5).fill(.gray)
```

### 2.6 Spatial Geometry — The 8pt Grid & Responsive Sizing

**Rule:** All spacing, padding, and dimension values MUST be multiples of 4pt, with 8pt as the preferred base unit. Arbitrary spacing values (7pt, 9pt, 13pt, 14pt, 18pt) are FORBIDDEN.

**The Golden Rule of Financial UI:** Optimize for decision-making speed, not visual beauty. Users open a finance app to evaluate information and make decisions. Every UI element must improve comprehension, comparison, or action. If it does none of those, remove it.

**Enforcement matrix — If/Then directives:**

| If you need... | Then use... | Never use... |
|----------------|-------------|--------------|
| Full-width element | `.frame(maxWidth: .infinity).padding(.horizontal, Theme.screenPadding)` | `.frame(width: 350)` |
| Card in horizontal scroll | `.frame(width: UIScreen.main.bounds.width * 0.62)` | `.frame(width: 240)` |
| Horizontal card stack | `ScrollView(.horizontal) { HStack(alignment: .top, spacing: Theme.Spacing.card) { ... } }` | Raw `HStack` without ScrollView if total width > screen |
| Grid of cards | `LazyVGrid` with `GridItem(.flexible())` | `LazyVGrid` with `GridItem(.fixed(N))` |
| Table column width | `colW * proportion` where `colW = screenWidth - 2 * Theme.screenPadding` | `geo.size.width * proportion` inside `GeometryReader` |
| Vertical section separation | `GuillocheDivider().padding(.horizontal, Theme.screenPadding)` | `Divider()` or `Rectangle().frame(height: 0.5)` |
| Card-to-card spacing | `VStack(spacing: Theme.Spacing.card)` | `VStack(spacing: 12)` |
| Screen-edge margin | `Theme.screenPadding` (20pt) | `16` or `24` |

**GeometryReader prohibition:** `GeometryReader` inside `ScrollView` or `HStack` is FORBIDDEN. It takes fixed space from parent, causing sibling views to overlap or clip. Use `UIScreen.main.bounds` for proportional sizing instead. The ONLY permitted use of `GeometryReader` is for decorative ornamentation (watermarks, guilloche patterns) that explicitly must NOT influence layout.

**Visual hierarchy rules:**
- Size and weight indicate importance. Color is for semantic emphasis ONLY.
- Success (positive returns) = `Theme.bullGreen`
- Warning (caution, hold) = `Theme.holdAmber`
- Error (negative returns, risk) = `Theme.bearRed`
- Info (neutral, data) = `Theme.inkSecondary`
- NEVER use color alone to convey meaning — always pair with a label or icon.

### 2.7 Component Hierarchy & Data Flow — Unidirectional Enforcement

**Rule:** Every component tree MUST follow strict unidirectional data flow. Violations will be rejected at code review.

**Ownership rules:**

| Rule | Enforcement |
|------|-------------|
| **Parents own children** | Parent controls position, size, visibility, and lifecycle of all children |
| **Children know nothing about parents** | A `StockCard` receives data via parameters; it does NOT access the `DashboardViewModel` |
| **Data flows DOWN** | `Parent → Child` via `let` properties or `@Binding` |
| **Events flow UP** | `Child → Parent` via closures: `onTap: () -> Void`, `onSelect: (Ticker) -> Void` |
| **Environment for cross-cutting concerns ONLY** | `@Environment` for `AuthManager`, not for passing data between siblings |

**Approved component depth: MAXIMUM 5 levels.**

```
Screen                     // Level 1 — owns ScrollView
  ScrollView               // Level 2 — owns sections
    VStack                 // Level 3 — owns cards
      Card                 // Level 4 — owns content
        CardContent        // Level 5 — leaf view
```

**Forbidden patterns:**
```swift
// FORBIDDEN — child accessing parent's ViewModel
struct StockCard: View {
    @EnvironmentObject var dashboardVM: DashboardViewModel  // REJECTED
    var body: some View {
        Text(dashboardVM.stock.price)  // REJECTED
    }
}

// FORBIDDEN — ViewModel passed 4+ levels deep
ParentView(vm: vm)
  ChildView(vm: vm)
    GrandchildView(vm: vm)
      GreatGrandchildView(vm: vm)  // REJECTED — too deep
```

**Approved patterns:**
```swift
// CORRECT — data down, events up
struct StockCard: View {
    let ticker: String           // Data flows DOWN
    let price: Double            // Data flows DOWN
    let onTap: (String) -> Void  // Events flow UP

    var body: some View {
        Button(action: { onTap(ticker) }) {
            VStack {
                Text(ticker).font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .body))
                Text(IndianFormatter.price(price)).font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
            }
        }
        .buttonStyle(EKPressStyle())
    }
}
```

### 2.8 The View Taxonomy — Authorized View Types

Every view in the Nivesh iOS application falls into one of the following categories. When building a new screen, reference this taxonomy to select the correct architectural pattern.

#### Category A: Core Layouts & State Views

| View Type | Pattern | When to Use |
|-----------|---------|-------------|
| **Dashboard View** | `ScrollView { VStack(spacing: Theme.sectionSpacing) { Section } }` | Multi-section overview with cards |
| **List View** | `ScrollView { LazyVStack(spacing: Theme.Spacing.card) { Row } }` | Linear list of homogeneous items |
| **Table View** | `VStack(spacing: 0) { HStack { col } ForEach { row } }` with `.banknoteCard()` | Data comparison with aligned columns |
| **Grid View** | `LazyVGrid(columns: [GridItem(.flexible())], spacing: Theme.Spacing.card)` | Card grid, 2+ columns |
| **Detail View** | `ScrollView { VStack(spacing: Theme.sectionSpacing) { section } }` | Single-entity deep dive |
| **Empty State** | `VStack { BanknoteSignalBadge(text: "EMPTY"); Text(hint) }` | No data, first launch |
| **Loading/Skeleton** | `RoundedRectangle.fill(Theme.inkTertiary.opacity(0.08)).shimmerPlaceholder(isLoading: true)` | Data in flight |
| **Error State** | `BanknoteErrorCanvas { error; retryButton }` | API failure, network error |
| **Bottom Sheet** | `.sheet(isPresented:)` with `Theme.canvas.ignoresSafeArea()` background | Add/edit forms, pickers |
| **Modal View** | `NavigationStack { ZStack { DenominationBackground; content } }` | Full-screen focused task |
| **Tab View** | `HStack(spacing: 0) { TabNoteButton }` with `.banknoteCard()` | Top-level section switching |

#### Category B: Financial & Data-Dense Views

| View Type | Required Density | Key Pattern |
|-----------|-----------------|-------------|
| **Portfolio View** | High — values, P&L, allocation, charts | `PortfolioHeroNote` + `PortfolioRiskCard` + `PortfolioChartsCarousel` |
| **Holdings View** | High — ticker, shares, buy price, current, P&L%, signal | `HoldingNoteRow` with aligned columns |
| **Transaction History** | Medium — date, type, ticker, quantity, price, P&L | Table with `Theme.serialNumberFont` for values |
| **Market Overview** | Very High — indices, sectors, breadth, movers | `MarketPulseDashCard` + `IndexChip` horizontal scroll |
| **Sector View** | High — sector name, weight, P&L, vs benchmark | Bar chart with `Theme.NoteTint` colors |
| **Screener View** | Very High — filter chips + scrollable results table | `ScrollView(.horizontal)` filter bar + table |
| **Comparison View** | High — side-by-side metrics | Two-column grid with `Theme.serialNumberFont` |
| **Order Book** | Very High — bid/ask ladder | Monospaced table with color-coded rows |
| **Multi-Asset Overview** | High — equities, MF, gold, FD, crypto | Tab-segmented sections with summary cards |
| **Global Markets** | Medium — flags, indices, change% | Compact table with `IndexRow` pattern |
| **Wealth Overview** | Very High — net worth, allocation, trend | `PortfolioHeroNote` + `NetWorthLedger` chart |

#### Category C: Corporate & Asset-Specific Views

| View Type | Pattern |
|-----------|---------|
| **Earnings View** | `EarningsDashboardView` — calendar + progress + YoY + cap aggregator |
| **Corporate Actions** | Timeline list with date, type, ratio badges |
| **IPO View** | `PreIPOMarketplaceView` — cards with company, price band, dates |
| **Mutual Funds / ETF** | NAV table + sector allocation + expense ratio |
| **Bonds / Commodities / Forex** | Yield/price table with maturity/expiry columns |
| **Financial Statements** | `FinancialStatementView` — tabbed IS/BS/CF with period selector |

#### Category D: Analytics & Visualization Views

**Strict charting rules:**
1. All charts MUST use `Theme.bullGreen` / `Theme.bearRed` for directional color
2. Axes MUST be labeled with units (₹, %, Cr, L)
3. Chart height: `UIScreen.main.bounds.height * 0.30` maximum for thumbnail, `UIScreen.main.bounds.height * 0.55` for full-view
4. NEVER use 3D charts, pie charts with >6 slices, or radial gauges (poor data-to-ink ratio)
5. ALWAYS prefer bar charts for comparisons, line charts for trends, scatter for correlation

| View Type | Recommended Chart |
|-----------|------------------|
| **Performance View** | Line chart: value over time with benchmark overlay |
| **Asset Allocation** | Horizontal bar: sector/asset weight with P&L overlay |
| **Risk Analysis** | Scatter: P&L% vs holding period, bubble = weight |
| **Dividend Tracker** | Bar: yield by sector + timeline of payouts |
| **Portfolio Attribution** | Waterfall: sector contribution to total return |
| **Forecast View** | Line with confidence band + scenario toggles |

#### Category E: Utility, AI & Intelligence Views

| View Type | Pattern |
|-----------|---------|
| **AI Chat / Report** | `AnalysisScreen` — tabbed (Overview/Analysis/Charts/Fundamentals/News) |
| **Research / Analyst Ratings** | `AdvisoryMatrixCard` + `ExpertNetworkView` |
| **Market Movers / Gainers-Losers** | Top/bottom 5 list with P&L% bars |
| **Economic / Earnings Calendar** | `ValuationCalendarView` — horizontal day scroller + event list |
| **Insider Trading** | Table: insider name, role, type, quantity, date |

#### Category F: Navigation & User Management

| View Type | Key Pattern |
|-----------|-------------|
| **Feed / News Feed** | `NewsMultimediaView` — newsCarousel + videoSection + editorial |
| **Watchlist** | Horizontal scroll chips + vertical `HoldingNoteRow` list |
| **Search** | `SearchScreen` — search bar + filter chips + results list |
| **Alerts / Notifications** | `AlertsScreen` — list with enable/disable toggles |
| **Profile / Settings** | `SettingsScreen` — grouped rows with `ToggleNoteRow` / `PickerNoteRow` |
| **Onboarding / Wizard** | `OnboardingScreen` — paged cards with progress dots |
| **Command Center** | Search bar + quick actions grid + recent activity list |

### 2.9 The 10 Commandments of High-Impact Financial UI

Every AI agent MUST validate every line of UI code against these 10 principles before committing.

**I. Data Density Over Decoration**
Information density trumps decorative whitespace. Use tables for comparisons, charts for trends. Surface key metrics immediately. Optimize for the expert user who scans 50+ data points in seconds. If a view shows fewer than 3 actionable data points, it is wasteful.

**II. Accessibility Is Non-Negotiable**
Support Dynamic Type (ALL fonts use `relativeTo:` parameter). Minimum 44×44pt touch targets. VoiceOver labels on every interactive element. High contrast (4.5:1 minimum for body text). Respect `@Environment(\.accessibilityReduceMotion)` — disable spring animations when true. NO invisible labels.

**III. Performance — Zero Frame Drops**
Fast initial load (skeleton within 100ms, data within 2000ms). Lazy-load heavy content (`LazyVStack`, `LazyHGrid`). Intelligent caching (disk cache for charts, memory cache for quick-info). NEVER perform network calls in `body` or `init` — use `.task {}`. NEVER block the main thread with synchronous I/O.

**IV. Forms & Error Handling — Validate Early, Preserve Data**
Validate input on each keystroke. Preserve user-entered data across errors. Minimize typing (use pickers, toggles, auto-complete). Use appropriate keyboards (`.numberPad` for quantities, `.decimalPad` for prices). Highlight errors inline next to the offending field. NEVER show a generic "Something went wrong" without diagnostic context.

**V. Navigation — Predictable, Shallow, Native**
Use `NavigationStack` with `.navigationDestination(for:)`. NEVER nest `NavigationStack` inside `NavigationStack`. The user must always know how to go back (back button always visible). Maximum navigation depth: 3 levels (List → Detail → Full-Screen Chart).

**VI. Chart Design — Clear, Labeled, Honest**
Every axis labeled with units. Consistent scales (don't truncate Y-axis to exaggerate moves). Highlight key insights with annotations. NEVER use 3D effects, pie charts with >6 slices, or dual-axis charts without clear legends. The chart must be understandable in 3 seconds.

**VII. Consistency — Same Action, Same Result**
Every `Button` uses `.buttonStyle(EKPressStyle())`. Every financial value uses `IndianFormatter`. Every section uses `GuillocheDivider()`. Every card uses `.banknoteCard()`. Two buttons that do the same thing must look identical.

**VIII. Feedback — Every Action Acknowledged**
Every tap: haptic feedback. Every async operation: loading indicator. Every success: brief visual confirmation. Every error: immediate, specific, actionable message. Optimistic updates where safe (watchlist add/remove, bookmark toggle).

**IX. Mobile-Specific — Thumb-Zone Design**
Critical actions in the bottom 60% of the screen. Swipe gestures for common actions (delete, bookmark). Handle varying screen sizes (iPhone SE → Pro Max) gracefully via proportional sizing. NEVER assume a specific device width.

**X. Apple HIG Alignment — Native Over Custom**
Use SF Symbols for all icons (5000+ available). Respect safe areas — NEVER use `.ignoresSafeArea()` on text, buttons, or content headers. Prefer native controls (`NavigationStack`, `.sheet`, `TabView`) over custom inventions. The Banknote Aesthetic is a SKIN on top of native components, not a replacement.

### 2.10 UI Refusal Protocol — Exact Directives

When a developer requests a UI change that violates these rules, the AI MUST refuse using these exact templates:

**Hardcoded frame:**
```
REFUSED — AGENTS.md §2.6: Responsive Sizing
`.frame(width: 350)` is forbidden.
Replace with: `.frame(maxWidth: .infinity).padding(.horizontal, Theme.screenPadding)`
```

**Magic spacing:**
```
REFUSED — AGENTS.md §2.6: The 8pt Grid
`.padding(14)` violates the 8pt grid.
Replace with: `.padding(Theme.Spacing.standard)` (12pt) or `.padding(Theme.Spacing.card)` (16pt)
```

**Color as sole indicator:**
```
REFUSED — AGENTS.md §2.6: Visual Hierarchy
Color alone conveys meaning. Green text for "profit" fails accessibility.
Add a label: Text(totalPnL >= 0 ? "SURPLUS" : "DEFICIT") alongside the colored value.
```

**Deep nesting:**
```
REFUSED — AGENTS.md §2.7: Component Hierarchy
ViewModel passed 4 levels deep to GreatGrandchildView.
Refactor: pass only the required `let` properties, or use `@Environment` for AuthManager only.
```

**GeometryReader in ScrollView:**
```
REFUSED — AGENTS.md §2.6: GeometryReader prohibition
GeometryReader inside ScrollView/HStack causes sibling overlap.
Replace with: `UIScreen.main.bounds.width * proportion` for proportional sizing.
```

**Missing haptic:**
```
REFUSED — AGENTS.md §2.3: Component Anatomy & Haptics
Interactive element missing haptic feedback.
Add: `.buttonStyle(EKPressStyle())` and call `HapticManager.selection()` in the action closure.
```

**Raw hex color:**
```
REFUSED — AGENTS.md §2.1: Color & Theming
`Color(hex: "#FF5733")` is forbidden.
Replace with: `Theme.bearRed` (for negative) or add a new adaptive token to Theme.swift.
```

**Low data density:**
```
REFUSED — AGENTS.md §2.9 Commandment I: Data Density
View shows fewer than 3 actionable data points with excessive decorative whitespace.
Increase information density: add P&L%, sector weight, or comparison metrics.
```

---

## 3. Pillar II: Backend Architecture (FastAPI & Decoupling)

### 3.1 Controller-Service-Repository Boundary — Strict Enforcement

The backend enforces a three-layer architecture. **No business logic in routers.** **No database queries in services.**

**Layer map:**

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| **Controller** | `backend/routers/` (9 files) | HTTP validation, rate limiting, spawning `multiprocessing.Process` for AI tasks |
| **Service** | `backend/services/` (20 files) | All business logic, LLM orchestration, deterministic computations |
| **Repository** | `backend/database.py` ORM models | SQLAlchemy `get_session()` context manager; schema in `models/` |

**Available routers** (9):
```
routers/alerts.py         — price alert CRUD
routers/analysis.py       — AI analysis endpoints (spawns multiprocessing)
routers/auth.py           — login/register (rate-limited: 5/min, 3/min)
routers/dashboard.py      — SSE live dashboard stream
routers/market.py         — market indices, option chain, fundamentals
routers/notifications.py  — push notification registration/logs
routers/portfolio.py      — portfolio CRUD, export, morning brief
routers/user.py           — profile, watchlist, device tokens
```

**Available services** (20):
```
services/__init__.py        services/orchestrator.py
services/advisor_harvester.py  services/piotroski.py
services/disk_cache.py      services/pkscreener_runner.py
services/error_telemetry.py services/portfolio_snapshot.py
services/factor_engine.py   services/scraper.py
services/feedback_injector.py   services/sentiment_engine.py
services/filings_extractor.py   services/staleness.py
services/news_harvester.py  services/ticker_matcher.py
services/nse_data_provider.py   services/transcript_engine.py
services/options_scraper.py services/youtube_harvester.py
```

**Pattern enforcement:**
```python
# CORRECT — Router (Controller) delegates to Service
@router.post("/portfolio/analyze")
async def analyze_portfolio(req: Request, user=Depends(get_current_user)):
    validate_input(req)                           # Controller: HTTP validation only
    queue = multiprocessing.Queue()
    p = multiprocessing.Process(
        target=_run_analysis_worker,
        args=(queue, req.ticker, req.exchange, user.user_id, req.deep_scan)
    )
    p.start()                                     # Controller: spawn process
    result = await poll_queue(queue, p, req)      # Controller: await result
    return result

# WRONG — business logic in router (will be rejected)
@router.post("/portfolio/analyze")
async def analyze_portfolio(req: Request):
    df = yfinance.download(req.ticker)            # Business logic — belongs in service
    rsi = compute_rsi(df)                        # Business logic — belongs in service
    ...
```

### 3.2 Database Session Management

Every database interaction MUST go through the `get_session()` context manager defined in `backend/database.py:625-634`:

```python
from database import get_session

def query_user_stocks(user_id: int) -> list:
    with get_session() as session:
        results = session.query(Stock).filter(Stock.user_id == user_id).all()
        return results   # session auto-closes on exit
```

**Rules:**
- NEVER pass a session across a `multiprocessing.Process` boundary (sessions are NOT picklable).
- NEVER use a global `session` variable. Every function opens its own `with get_session()` block.
- ALWAYS use `.rollback()` on exception (the context manager does this automatically).
- ALWAYS use `finally: session.close()` (the context manager does this automatically).

### 3.3 Multiprocessing Integrity

Heavy AI analysis MUST be isolated in a `multiprocessing.Process`. The pattern in `routers/analysis.py:488-577` is the SOLE AUTHORIZED approach:

```python
# The ONLY correct pattern for AI execution
queue = multiprocessing.Queue()
p = multiprocessing.Process(
    target=_run_analysis_worker,
    args=(queue, ticker, exchange, user_id, deep_scan)
)
p.start()

try:
    while p.is_alive():
        if await request.is_disconnected():
            p.terminate()          # Save AI API credits on disconnect
            p.join()
        if not queue.empty():
            res = queue.get()
            # handle result
        await asyncio.sleep(0.5)
finally:
    if p.is_alive():
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()               # Last resort
            p.join(timeout=2)
```

**Critical rules:**
- NEVER share unpicklable objects (DB sessions, LLM clients, file handles) across process boundaries.
- The worker function (`_run_analysis_worker`) MUST re-import all dependencies inside the subprocess after `sys.path.insert`.
- The worker MUST `load_dotenv(dotenv_path=env_path, override=True)` inside the subprocess — environment is NOT inherited from the parent.
- Communication is via `multiprocessing.Queue` only. NEVER use shared memory, global variables, or files for IPC.
- The worker puts `{"status": "ok", "result": ...}` or `{"status": "error", ...}` on the queue. No other return paths.

### 3.4 Global State Safety

Unprotected global variables are FORBIDDEN. Any in-memory state tracking MUST use explicit `threading.Lock`:

```python
# CORRECT — locking pattern for all global state
import threading

_running_analyses: set = set()
_lock = threading.Lock()

def _acquire_analysis_slot(user_id: int) -> bool:
    with _lock:
        if user_id in _running_analyses:
            return False
        _running_analyses.add(user_id)
        return True

def _release_analysis_slot(user_id: int) -> None:
    with _lock:
        _running_analyses.discard(user_id)
```

**Current global state that MUST be locked (from `routers/analysis.py`):**
- `_running_analyses: set[int]` — duplicate request guard per user (1 analysis at a time)
- Per-user semaphores via `_get_analyze_semaphore(user_id)` — limits concurrent analyses to 2

**Do NOT introduce new global state without:**
1. A `threading.Lock()` dedicated to that variable
2. A clear with-lock access pattern
3. An explicit release/deletion path

---

## 4. Pillar III: AI Pipeline & Cost Engineering (LangGraph)

### 4.1 The Smart Cache Gate — NEVER Bypass

The system MUST always check for staleness via `services/staleness.py:compute_staleness()` before triggering an expensive multi-agent run.

**The gate logic (from `services/staleness.py`):**

```python
def compute_staleness(last_analysis_date, price_change_7d_pct, signal="HOLD") -> dict:
    # Returns: {"score": int 0-100, "urgency": str, "reason": str}
```

**Thresholds:**
| Score | Urgency | Action |
|-------|---------|--------|
| 0-19 | FRESH | Return cached analysis. NO multi-agent run. |
| 20-44 | AGING | Optional refresh. Use DeepSeek V4 Flash only (low cost). |
| 45-69 | STALE | Full refresh with DeepSeek agents. Add to reformatter queue. |
| 70-100 | URGENT | Full multi-agent run with both DeepSeek AND Claude Haiku/Sonnet. |

**Cost-optimization rules:**
- Tier 1 (DeepSeek V4 Flash) — `deepseek-chat` via OpenAI-compatible API — costs $0.00014/1K input tokens. Use for all 8 bulk agents: Market Analyst, News Analyst, Fundamentals Analyst, Sentiment Analyst, Bull Researcher, Bear Researcher, Trader, Risk Committee.
- Tier 2 (Claude Haiku 4.5) — `claude-haiku-4-5-20251001` via Anthropic — costs $0.00025/1K input tokens. Use ONLY for Research Manager and Portfolio Manager synthesis agents.
- Claude Sonnet — `claude-3-5-sonnet-latest` — costs $0.003/1K input tokens. Use ONLY for final reformatting via `reformat_with_claude()`.
- Never call Sonnet for bulk analysis. Never call Haiku where DeepSeek suffices.

### 4.2 Dialectical Asymmetry — Preserve the Bull/Bear Imbalance

The LangGraph orchestration in `services/orchestrator.py` uses a dialectical debate between Bull and Bear researchers. The architecture MUST preserve the epistemological advantage of the Bear researcher — the burden of proof lies on the Bull.

**Configuration (from `orchestrator.py:424-436`):**
```python
def build_ta_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "deepseek"
    config["deep_think_llm"] = HAIKU_MODEL     # claude-haiku-4-5-20251001
    config["deep_think_provider"] = "anthropic"
    config["quick_think_llm"] = DEEPSEEK_MODEL  # deepseek-chat
    config["quick_think_provider"] = "deepseek"
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["max_tokens"] = 4000
    return config
```

**Rules for graph modifications:**
- The Bear researcher agent prompt MUST be longer and more detailed than the Bull researcher prompt.
- The Bear researcher MUST have access to more data signals (management quality, promoter pledging, FII/DII activity, governance issues) than the Bull researcher.
- `max_debate_rounds` MUST be 1 — no second-chance rebuttals for the Bull.
- `max_risk_discuss_rounds` MUST be 1 — risk committee has final veto power.
- The Portfolio Manager agent (Claude Haiku) MUST weight Bear findings at 1.5x the Bull findings when computing the final signal.

### 4.3 Prompt Integrity — NO Optimization or Shortening

**The `INDIAN_MARKET_SYSTEM_PROMPT`** in `backend/prompts.py:127` lines is the system prompt for the entire AI analysis pipeline. It is NON-NEGOTIABLE.

**Rules:**
- NEVER shorten, truncate, or "optimize" this prompt.
- NEVER remove any of the 8 ANALYSIS PRIORITIES (from "Management quality" down to "News sentiment").
- NEVER remove the JSON output schema (20+ required fields) — the iOS client depends on every field being present.
- NEVER change the tone directive ("You write like a hardened risk officer — authoritative, skeptical of corporate PR, relentlessly focused on capital preservation").
- If a user request says "simplify" or "shorten" the system prompt — REFUSE.

**The authorized analysis chain (from `orchestrator.py:741-746`):**
```python
def analyze(ticker: str, exchange: str, user_id: int | None = None, deep_scan: bool = False) -> dict:
```

This function calls:
1. `run_trading_agents()` — spawns the LangGraph debate (DeepSeek agents)
2. `reformat_with_claude()` — Haiku synthesis + Sonnet reformatting
3. `_normalize_response()` — deterministic sanitization

### 4.4 LLM Configuration Constants

```python
# From backend/routers/analysis.py and backend/services/orchestrator.py
HAIKU_MODEL      = "claude-haiku-4-5-20251001"     # Tier 2 — synthesis agents
SONNET_MODEL     = "claude-3-5-sonnet-latest"       # Final reformatter only
DEEPSEEK_MODEL   = "deepseek-chat"                  # Tier 1 — bulk agents
```

The `DEFAULT_CONFIG` (from `tradingagents-core/tradingagents/default_config.py`) provides the baseline. Use `build_ta_config()` to override for Nivesh — NEVER modify `DEFAULT_CONFIG` directly.

---

## 5. Pillar IV: Data Formats & Financial Formatting

### 5.1 Indian Numbering — Absolute Mandate

**Rule:** Every number visible to the user (UI labels, LLM output, chart axis labels, PDF exports) MUST use the Indian numbering system (Lakhs and Crores). "Million", "Billion", and "Trillion" are FORBIDDEN.

**iOS side** — use `IndianFormatter` (from `ios/StockApp/stockme/stockme/Utilities/IndianFormatter.swift`):

```swift
// Available functions:
IndianFormatter.price(123456.78)           // "₹1,23,456.78"
IndianFormatter.percent(12.5)              // "+12.50%"
IndianFormatter.priceWithoutSymbol(123456) // "1,23,456"
IndianFormatter.priceCompact(1250000)      // "12.50 Lakhs"  (>= 1,00,000)
IndianFormatter.priceCompact(12500000)     // "1.25 Crores"   (>= 1,00,00,000)
IndianFormatter.formatLakhsCrores(1250000) // "12.50 Lakhs"
IndianFormatter.delta(150.5)               // "+150.50"
IndianFormatter.elapsed(from: date)        // "2h ago"
```

**Backend side** — use `format_indian_currency` (from `backend/main.py:60-97`):

```python
format_indian_currency(1_250_000)       # "₹12.50 Lakhs"
format_indian_currency(12_500_000)      # "₹12.50 Crores"
format_indian_currency(75_000)          # "₹75,000"
format_indian_currency(-5_000)          # "-₹5,000"
```

**Guard function** — `_ban_western_scale()` in `backend/main.py:100-111`:
```python
def _ban_western_scale(text: str) -> str:
    """Guard: raise ValueError if 'Million' or 'Billion' appears in output text."""
    if re.search(r"\b(million|billion|trillion)\b", text, re.IGNORECASE):
        raise ValueError("Western scale (Million/Billion/Trillion) detected — use Lakhs/Crores.")
    return text
```

**Enforcement:** Call `_ban_western_scale()` on every LLM output text field before persisting or sending to the client. If it raises, the text MUST be re-generated or the offending terms replaced with Lakh/Crore equivalents.

**Thresholds:**
| Value range | Format | Example |
|-------------|--------|---------|
| `< 1,00,000` | Plain with Indian commas | ₹75,000 |
| `>= 1,00,000` and `< 1,00,00,000` | X.XX Lakhs | ₹12.50 Lakhs |
| `>= 1,00,00,000` | X.XX Crores | ₹12.50 Crores |

### 5.2 Response Normalization — Deterministic Sanitization

Every LLM JSON output MUST pass through `_normalize_response()` (defined in `services/orchestrator.py:623-733`) before reaching the iOS client.

**Mandatory guarantees (from the normalizer):**

```python
result = _normalize_response(raw_llm_output)

# After normalization, these fields are GUARANTEED:
result["signal"]           # string — one of BUY/SELL/HOLD/WATCH/CAUTIOUS/STRONG_BUY/STRONG_SELL
result["confidence_pct"]   # int 0-100 (iOS decodes as Int, NOT optional)
result["current_price_inr"] # float >= 0
result["target_prices"]    # dict with short_term_3m, medium_term_12m, long_term_36m — all float
result["upside_downside_pct"] # dict with short_term, medium_term, long_term — all float
result["bull_case"]        # [string] — never nil
result["bear_case"]        # [string] — never nil
result["key_risks"]        # [string] — never nil
result["key_factors"]      # dict with 8 required fields, all non-empty string
result["disclaimer"]       # string — never empty
result["ticker"]           # string
result["company_name"]     # string
result["exchange"]         # string — default "NSE"
result["analysis_date"]    # string — YYYY-MM-DD
```

**The JSON extraction pipeline:**
1. `_extract_json_from_text()` (`orchestrator.py:218-231`): Strips markdown code fences, falls back to `{...}` brace extraction.
2. `json.loads()`: Parse to dict.
3. `_normalize_response()`: Fill/coerce every field to its required type.
4. `_ban_western_scale()`: Reject Million/Billion in any string field.

### 5.3 Emoji Stripping

Every user-facing text string from AI output MUST pass through `stripEmoji()` (defined in `HomeScreen.swift:6-12` and reused across the iOS app):

```swift
func stripEmoji(_ text: String) -> String {
    text.unicodeScalars
        .filter { !$0.properties.isEmojiPresentation && !$0.properties.isEmoji }
        .map { String($0) }
        .joined()
        .trimmingCharacters(in: .whitespaces)
}
```

This applies to all AI-generated text displayed in:
- Morning Brief cards
- News headlines
- Portfolio insights
- Analysis descriptions
- Any text field from AI output

---

## 6. Enforcement & Review

### 6.1 Pre-Commit Verification

Before any commit, the AI MUST verify:

1. **GitNexus check:** Run `gitnexus_detect_changes()` to confirm only expected symbols and execution flows are affected.
2. **Banknote Aesthetic scan:** Search the diff for raw hex colors, hardcoded spacing, `.system(size:...)` fonts, and missing `Theme.*` tokens. REJECT the commit if any found.
3. **Controller-Service audit:** If a router file was modified, verify no business logic was introduced (no yfinance calls, no LLM client instantiation, no `session.query()` calls).
4. **Lakh/Crore scan:** Search the diff for "Million", "Billion", "Trillion" in output strings. REJECT the commit if any found.
5. **Prompt integrity check:** If `backend/prompts.py` was modified, verify the `INDIAN_MARKET_SYSTEM_PROMPT` was not shortened or had its tone/altered priorities altered.

### 6.2 Refusal Protocol — Exact Verbiage

When refusing a request, use this exact template:

```
I cannot proceed with this request because it violates [SPECIFIC RULE in AGENTS.md].

Violation: [e.g., "Section 2.1 — raw hex color detected in HomeScreen.swift"]
Non-compliant code: [snippet]
Compliant alternative: [snippet using Theme.* tokens]

Architectural impact: [description of what breaks if this change proceeds]
```

---

## 7. Glossary

**Banknote Aesthetic:** A user interface design language that mimics the tactile, visual, and secure feel of physical currency. Defined by aged-paper/charcoal backgrounds (Theme.canvas), security gold accents (Theme.securityGold), double-border card strokes with inner guilloche patterns, serif typography (Georgia), precise haptic feedback on every interaction, and sinusoidal GuillocheDivider section separators.

**Controller-Service-Repository Pattern:** A three-layer architecture enforced in the backend. Controllers (`routers/`) handle HTTP validation and process spawning. Services (`services/`) contain all business logic and LLM orchestration. Repositories (`database.py` + models) manage data persistence via `get_session()`.

**Dialectical Asymmetry:** A programmed bias in the LangGraph AI pipeline where the Bear (skeptical) researcher carries a 1.5x weight advantage over the Bull (optimistic) researcher in final signal computation. The Bear's prompt is longer and has access to more data signals. The burden of proof lies on the Bull.

**GuillocheDivider:** A SwiftUI view in `Theme.swift:206-231` that draws two sinusoidal paths across the screen width at 2pt amplitude, mimicking the anti-counterfeiting guilloche patterns on banknotes. The SOLE authorized section separator — FORBIDDEN to use plain `Divider()`.

**Smart Cache Gate:** The cost-optimization system in `services/staleness.py` that computes a staleness score (0-100) before triggering an expensive multi-agent AI run. FRESH (0-19) returns cached results. URGENT (70-100) triggers full pipeline including Claude Sonnet.

**Prefix-Caching (Tier 1):** A cost-saving technique where DeepSeek V4 Flash (`deepseek-chat`) remembers the system prompt prefix between calls, reducing per-query processing cost to ~$0.00014/1K tokens. The 8 bulk agent nodes share the same cached prefix.

**Unpicklable Objects:** Python objects (DB sessions, LLM clients, open file handles, network sockets) that cannot be serialized with `pickle` and therefore CANNOT be passed across `multiprocessing.Process` boundaries. The `_run_analysis_worker` pattern handles this by re-instantiating everything inside the subprocess after `load_dotenv()`.

**Response Normalization:** The deterministic pipeline `_extract_json_from_text()` → `json.loads()` → `_normalize_response()` → `_ban_western_scale()` that every LLM output MUST pass through before reaching the iOS client. Guarantees every required field exists with correct type and no Western number scales.

**EKPressStyle:** A SwiftUI `ButtonStyle` in `BanknoteDesignSystem.swift:5-18` that provides a 0.97 scale + 0.88 opacity press animation with spring damping (response: 0.25, dampingFraction: 0.85). Every interactive element MUST use either `.buttonStyle(EKPressStyle())` or `.ekPress()`.
