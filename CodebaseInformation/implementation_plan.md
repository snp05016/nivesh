# NIVESH — MASTER IMPLEMENTATION PLAN
# Builds on `prompt_features_batch.md` (Phases 0–7). Do not remove or alter those phases.
# This document adds Phases 8–13 and a global UI Consistency Mandate derived from
# a detailed pixel-level analysis of 4 reference screenshots.

---

## SCREENSHOT ANALYSIS — GROUND TRUTH

Before writing a single line of code, internalise every detail below.
These screenshots are the law. When any existing view conflicts with them, the screenshot wins.

---

### SCREEN A — WATCHLIST

```
Background:       Near-black, slight blue-navy tint. Approximately Theme.canvas in dark mode.
Header:           "6 instruments" — small muted caption (Theme.inkTertiary, officialStampFont ~9pt)
                  "Watchlist" — large bold title (Theme.inkPrimary, ~28pt, heavy weight)
                  "Nivesh निवेश" — top-right, small, Theme.inkSecondary
Row anatomy:
  [TILE 40×40pt]  [TICKER bold 13pt + Company name 11pt muted]  [SPARKLINE 60×32pt]
                  [PRICE 14pt right] + [% BADGE capsule]

TILE COLOR RULE:  Each ticker tile has a UNIQUE teal-blue tint, NOT a flat canvasDeep.
                  The tile background is a per-ticker color derived algorithmically:
                    func tileColor(for ticker: String) -> Color {
                        let hues: [Double] = [0.55, 0.58, 0.62, 0.48, 0.52, 0.65, 0.50, 0.57]
                        let idx = abs(ticker.hashValue) % hues.count
                        return Color(hue: hues[idx], saturation: 0.45, brightness: 0.35)
                    }
                  Letter color: Theme.inkPrimary (white), font: serialNumberFont size 12, weight .semibold

SPARKLINE:        60pt wide, 32pt tall. Green line (Theme.bullGreen) for gainers.
                  Red line (Theme.bearRed) for losers. Line weight 1.5pt. No area fill.
                  Clean crisp anti-aliased — Canvas API only.

% BADGE:          Capsule shape. Green background (Theme.bullGreen.opacity(0.18)) for gainers,
                  red (Theme.bearRed.opacity(0.18)) for losers.
                  Font: serialNumberFont size 11, bold. Color matches background theme color.
                  Padding: 4pt horizontal, 3pt vertical.

ROW SEPARATOR:    Very faint 0.5pt line between rows. Theme.borderFine. NOT a GuillocheDivider.
                  GuillocheDivider is for SECTION breaks only, not between list items.

BOTTOM TAB BAR:   5 tabs: Home, Watchlist, Portfolio, Markets, Alerts.
                  Active tab: icon + label, Theme.securityGold color.
                  Inactive: icon only shown (label present but muted), Theme.inkTertiary.
                  Tab bar background: Theme.canvasDeep with 0.5pt top border (Theme.borderFine).
```

---

### SCREEN B — PORTFOLIO

```
HERO VALUE BLOCK:
  "Portfolio · current value" — officialStampFont 9pt, Theme.inkTertiary, tracking 1.5
  "₹12,48,500" — .largeTitle.weight(.bold).monospaced(), Theme.inkPrimary
  Pill row below hero: Two adjacent capsule pills
    Pill 1: "▲ +1.15%" — Theme.bullGreen background (0.18 opacity), Theme.bullGreen text
    Pill 2: "+₹2,68,500total" — same style
    Both use serialNumberFont 12pt. Pills have 8pt horizontal padding, 4pt vertical.

IMMERSIVE CHART:
  Full screen width. NO horizontal padding. Negative margin to bleed to edges.
  Green glowing line: Theme.bullGreen, lineWidth 2pt.
  Subtle area fill beneath line: linear gradient Theme.bullGreen opacity 0.12 → 0.0 top-to-bottom.
  Chart height: UIScreen.main.bounds.height * 0.28
  Background: pure Theme.canvas (no card background — chart floats directly on screen bg)

SCRUB TOOLTIP (when user drags on chart):
  Format: "₹X,XX,XXX · DD Mon"
  Floating dark card: Theme.canvasDeep, cornerRadius Theme.CornerRadius.medium
  Font: serialNumberFont 12pt, Theme.inkPrimary
  Vertical dashed line from tooltip to x-axis: Theme.inkTertiary 0.5pt dashed
  Small filled circle on the chart line at scrub point: Theme.bullGreen 6pt diameter

TIME RANGE SELECTOR:
  5 options: 1D  1W  1M  1Y  ALL
  Layout: HStack evenly spaced (NOT pills — these are plain text buttons)
  Selected: Theme.securityGold text + 1.5pt underline in Theme.securityGold
  Unselected: Theme.inkTertiary text, no underline
  Font: officialStampFont 10pt, tracking 0.5
  The selector row sits BELOW the chart with 12pt top padding.

DONUT CHART + LEGEND CARD:
  Dark card (.banknoteCard()) below time selector.
  Left: Donut chart — colored segments, center text "6\nSTOCKS" (count\nlabel)
    Center font: serialNumberFont 18pt for count, officialStampFont 8pt for "STOCKS"
  Right: VStack of holding rows
    Each row: colored circle 8pt, ticker 13pt inkPrimary, percentage right-aligned inkSecondary
    Max 4 rows shown. If more, show "+ N more" in inkTertiary.
  Segment colors are PROGRAMMATIC — use a fixed palette of 6-8 colors cycling:
    [Theme.bullGreen, Theme.securityGold, Theme.bearRed.opacity(0.8),
     Color(hue:0.58, saturation:0.5, brightness:0.6),
     Color(hue:0.72, saturation:0.4, brightness:0.65),
     Theme.inkSecondary]

HOLDINGS SECTION:
  "Holdings" — sectionHeader style (officialStampFont 11pt, tracking 1.5, inkPrimary)
  Each holding row:
    Left: Colored dot 8pt (same color as donut segment)
    Center: ticker bold 14pt inkPrimary, "X shares" 11pt inkTertiary below
    Right: value 14pt inkPrimary bold (IndianFormatter.price), % pill below
  Subtle 0.5pt row separator (Theme.borderFine) between holding rows
  NO .banknoteCard() per row — they sit in a single .banknoteCard() container
```

---

### SCREEN C — AI DEEP ANALYSIS (STOCK DETAIL)

```
NAVIGATION BAR:
  Back chevron + "RELIANCE" bold title (inkPrimary, headline weight)
  Right: price (serialNumberFont 14pt inkPrimary) + % badge (same capsule pill style as watchlist)
  The nav bar title and right item are INLINE — navigationBarTitleDisplayMode(.inline)

CHART:
  Identical to Portfolio chart — full-bleed, glowing green line, same scrub behaviour.
  When chart shows a LOSS period (bearRed scenario): line becomes Theme.bearRed, area fill bearRed.
  The chart direction detection: if values.last < values.first → bearRed, else bullGreen.

TIME RANGE SELECTOR: Identical to Portfolio (underline style, not pills).

CONFIDENCE RING CARD:
  .banknoteCard() container
  Left section:
    Circular progress ring: 72pt diameter
    Ring background: Theme.canvasShadow (track)
    Ring foreground: Theme.bullGreen for bullish, Theme.bearRed for bearish, Theme.holdAmber for hold
    Ring lineWidth: 6pt, lineCap: .round
    Center: "78%" serialNumberFont 18pt bold inkPrimary
            "CONFIDENCE" officialStampFont 7pt tracking 1.5 inkTertiary
  Right section:
    Signal pill: "BULLISH" / "BEARISH" / "HOLD" in capsule
      BULLISH: Theme.bullGreen bg (0.18 opacity), Theme.bullGreen text
      BEARISH: Theme.bearRed bg, Theme.bearRed text
      HOLD: Theme.holdAmber bg, Theme.holdAmber text
    Font: officialStampFont 10pt, tracking 1.5
    Below pill:
      "Target ₹X,XXX" — serialNumberFont 14pt Theme.inkPrimary
      "+X.X% upside · Low risk" — engravedSerif 12pt Theme.bullGreen
        Risk text: "Low risk" = bullGreen, "Medium risk" = holdAmber, "High risk" = bearRed

METRIC GRID (3 columns × 2 rows):
  LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())],
             spacing: Theme.Spacing.standard)
  Each cell: .banknoteCard() individually
    Label: officialStampFont 8pt inkTertiary tracking 1.2
    Value: serialNumberFont 14pt inkPrimary bold
  Apply .financeTerm() to EACH label (Mkt Cap, P/E, ROE, Div Yield, Debt/Eq, Book Val)

"WHY WE'RE BULLISH" / "WHY WE'RE BEARISH" SECTION:
  Section header: "Why we're bullish" — engravedSerif 16pt inkPrimary heavy
  Numbered items:
    Number badge: Circle 20pt diameter, Theme.securityGold bg (0.15 opacity), theme.securityGold text
                  For bearish: Theme.bearRed bg/text
    Font: officialStampFont 10pt, tracking 1.2
    Text: engravedSerif 13pt inkSecondary, multiline
    Each item in a VStack, HStack(alignment: .top) for number + text
  Strip emoji from all AI text (stripEmoji() applied to every String field)
```

---

### SCREEN D — HOME SCREEN

```
STATUS LINE:
  "Tuesday, 10 June" — officialStampFont 9pt inkTertiary, tracking 0.5
  Below: "Hi, [Name]" — .largeTitle weight .bold inkPrimary
  Top right: Avatar circle — 36pt diameter, Theme.securityGold background,
             first initial in canvas color, serialNumberFont 16pt

NIFTY HERO CARD:
  Full-width .banknoteCard()
  Inside: VStack(alignment: .leading)
    "NIFTY 50 · NSE" — officialStampFont 9pt inkTertiary tracking 1.5
    Index value — .title.weight(.bold).monospaced() inkPrimary
    % badge (same capsule style) — top-right aligned in HStack
    Mini area chart: 80pt tall, full card width, Theme.bullGreen/bearRed with gradient fill
                     This is NOT a separate view — it's an inline Canvas at the bottom of the card

INDEX CHIP ROW:
  3 chips in HStack (NOT LazyVGrid — exactly 3, equal width)
  Each chip: .banknoteCard()
    Label: officialStampFont 8pt inkTertiary tracking 1.2 (e.g. "SENSEX")
    Value: serialNumberFont 14pt inkPrimary bold
    % badge: same capsule style but smaller (font size 10pt)
  HStack(spacing: Theme.Spacing.standard)
  Each chip: .frame(maxWidth: .infinity)

MORNING BRIEF SECTION:
  Header row: "Morning Brief" engravedSerif 16pt inkPrimary + "See all" Theme.securityGold 12pt right
  Cards: Each news item in a .banknoteCard()
    Left: Icon square — 40×40pt, Theme.securityGold.opacity(0.15) background,
          RoundedRectangle cornerRadius Theme.CornerRadius.medium
          SF Symbol "bolt.fill" in Theme.securityGold
    Center-right: Category pill (e.g. "POLICY", "EARNINGS") — officialStampFont 8pt tracking 1.5
                  Theme.securityGold.opacity(0.12) bg, Theme.securityGold text
                  Headline: engravedSerif 13pt inkPrimary, 2 lines max, lineLimit(2)

SECTORS TODAY SECTION:
  Header: "Sectors today" engravedSerif 16pt inkPrimary
  ScrollView(.horizontal, showsIndicators: false)
    HStack(spacing: Theme.Spacing.standard)
      Each sector: Capsule with
        Text("Auto +1.80%") — serialNumberFont 11pt
        Background: Theme.bullGreen.opacity(0.12) for positive, Theme.bearRed.opacity(0.12) for negative
        Text color: Theme.bullGreen / Theme.bearRed
        Padding: 10pt horizontal, 6pt vertical
```

---

## GLOBAL UI CONSISTENCY MANDATE

These rules apply to EVERY view in the entire app. Run gitnexus_query({query: "all views"}) and
audit each one. Any view that violates the rules below must be fixed before its phase is closed.

### G1 — CHART CONSISTENCY
Every price chart in the app (Portfolio, Stock Detail, Home NIFTY card, Watchlist sparklines)
MUST use the same visual language:
- Gainers: Theme.bullGreen line (2pt weight for full charts, 1.5pt for sparklines)
- Losers: Theme.bearRed line
- Area fill: linear gradient from line color at 0.12 opacity to 0.0, top to bottom
- Canvas API only — NO Charts framework SwiftUI charts
- Full-bleed charts: negative horizontal margin `.padding(.horizontal, -Theme.screenPadding)`
- Sparklines: no fill, line only

### G2 — BADGE / PILL CONSISTENCY
One and only one badge style in the entire app:
```swift
struct ChangeBadge: View {
    let value: Double   // percentage
    var body: some View {
        let up = value >= 0
        Text((up ? "▲ " : "▼ ") + IndianFormatter.percent(abs(value)))
            .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote).weight(.semibold))
            .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.18))
            .clipShape(Capsule())
    }
}
```
Replace ALL existing percentage badges across the entire app with `ChangeBadge(value: changePercent)`.
No exceptions. Search: gitnexus_query({query: "percent badge change indicator"}).

### G3 — TIME RANGE SELECTOR CONSISTENCY
Every time range selector in the app (Portfolio, Stock Detail) MUST use the underline style:
```swift
struct TimeRangeSelector: View {
    @Binding var selected: TimeRange
    let ranges: [TimeRange]
    var body: some View {
        HStack(spacing: 0) {
            ForEach(ranges, id: \.self) { range in
                Button(action: { HapticManager.selection(); selected = range }) {
                    VStack(spacing: 2) {
                        Text(range.label)
                            .font(Theme.officialStampFont(size: 10)).tracking(0.5)
                            .foregroundStyle(selected == range ? Theme.securityGold : Theme.inkTertiary)
                        Rectangle()
                            .fill(selected == range ? Theme.securityGold : Color.clear)
                            .frame(height: 1.5)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.medium)
                }
                .buttonStyle(EKPressStyle())
            }
        }
    }
}
```
NO pill-style time range selectors anywhere. Replace all existing ones.

### G4 — SECTION SEPARATOR RULES
- Between SECTIONS (e.g. "Morning Brief" → "Sectors Today"): `GuillocheDivider()`
- Between LIST ROWS (holdings, watchlist items, news items): `Divider().overlay(Theme.borderFine)` at 0.5pt — NOT GuillocheDivider
- GuillocheDivider ONLY between major content sections, never in lists

### G5 — AVATAR / IDENTITY CHIP
The "Nivesh निवेश" branding in the top right of Watchlist and Portfolio screens must be:
```swift
struct NiveshBrandChip: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Text("Nivesh")
                .font(Theme.engravedSerif(size: 12, weight: .semibold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
            Text("निवेश")
                .font(Theme.hindiFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
        }
    }
}
```

### G6 — TILE COLOR SYSTEM (for watchlist, screener, holding rows)
Never use Theme.canvasDeep for all tiles uniformly. Use `tileColor(for:)`:
```swift
extension String {
    var tileColor: Color {
        let hues: [Double] = [0.55, 0.58, 0.62, 0.48, 0.52, 0.65, 0.50, 0.57]
        let idx = abs(self.hashValue) % hues.count
        return Color(hue: hues[idx], saturation: 0.45, brightness: 0.35)
    }
}
// Usage: background(ticker.tileColor)
```
Apply to: Watchlist rows, Screener rows, Holdings rows (dots use same hue at full brightness).

### G7 — NAVIGATION BAR RULES
Every screen with a navigation bar MUST:
- Use `.navigationBarTitleDisplayMode(.inline)` — no large titles in detail views
- Never use `.navigationBarTitleDisplayMode(.large)` except on root tab screens (Watchlist, Portfolio, Home)
- Right bar button on stock detail: price + ChangeBadge in an HStack
- NEVER show navigation bar overlap on content — `.toolbarBackground(.visible, for: .navigationBar)` with `Theme.canvas` background

### G8 — BOTTOM TAB BAR
The tab bar across all 5 tabs MUST be consistent:
- Background: Theme.canvasDeep
- Active tab: icon (filled SF symbol) + label, Theme.securityGold
- Inactive: icon (outline SF symbol), Theme.inkTertiary, label present but small/muted
- Top border: 0.5pt Rectangle.fill(Theme.borderFine)
- Haptic: HapticManager.selection() on every tab switch
- Tab icons: house.fill / list.bullet / briefcase.fill / chart.bar.fill / bell.fill

### G9 — LOADING / SKELETON STATES
Every data-driven view must show a shimmer skeleton while loading:
- Use `.shimmerPlaceholder(isLoading: isLoading)` on card containers
- Skeleton blocks: `RoundedRectangle.fill(Theme.inkTertiary.opacity(0.08)).shimmerPlaceholder(isLoading: true)`
- Never show an empty view while data is in flight — ALWAYS show skeleton shape

### G10 — SCRUB TOOLTIP VISUAL CONTRACT
Every chart that supports scrubbing must render a scrub tooltip with this exact structure:
```swift
struct ScrubTooltipView: View {
    let price: Double
    let date: Date
    var body: some View {
        Text(IndianFormatter.price(price) + " · " + date.formatted(.dateTime.day().month(.abbreviated)))
            .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
            .foregroundStyle(Theme.inkPrimary)
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.borderFine, lineWidth: 0.5))
    }
}
```
The vertical dashed line under the tooltip:
```swift
Rectangle()
    .fill(Theme.inkTertiary.opacity(0.4))
    .frame(width: 0.5)
    .overlay(Rectangle().stroke(style: StrokeStyle(lineWidth: 0.5, dash: [4, 3])).foregroundStyle(Theme.inkTertiary))
```

---

## PHASE 8: RENDERING AUDIT & BUG FIXES (SYSTEMATIC)

Run before all other new phases. Fix every rendering bug found.

```
STEP 8.1 — Run full Xcode build. Collect ALL warnings. Fix every warning before proceeding.
           Zero tolerance for "result of call to ... is unused" or deprecated API warnings.

STEP 8.2 — RENDERING BUG HUNT. For each screen, launch on:
             - iPhone SE (375pt) — smallest supported
             - iPhone 16 Pro Max (430pt) — largest
             - iPad mini if the app supports it
           Test each screen in DARK MODE ONLY (the reference screenshots are dark mode).

Known rendering issues to hunt and fix:

  [BUG-01] Navigation bar overlap:
    Symptom: Content (GuillocheDivider, section header, chart) visible under the nav bar.
    Cause: Missing .navigationBarTitleDisplayMode(.inline) or missing .toolbarBackground.
    Fix: Add to every NavigationStack child:
         .navigationBarTitleDisplayMode(.inline)
         .toolbarBackground(Theme.canvas, for: .navigationBar)
         .toolbarBackground(.visible, for: .navigationBar)

  [BUG-02] Tab bar overlap:
    Symptom: Bottom content clipped or hidden behind the tab bar.
    Cause: Missing .safeAreaInset(edge: .bottom) or incorrect ignoresSafeArea usage.
    Fix: Never use .ignoresSafeArea() on content views. Only on background Color/Image fills.

  [BUG-03] GeometryReader layout collapse:
    Symptom: Cards with zero height, or charts that take up the whole screen.
    Cause: GeometryReader inside LazyVStack or ScrollView.
    Fix: Replace with UIScreen.main.bounds.width for all proportional width calculations.
         Replace GeometryReader-based height with fixed proportional values like
         UIScreen.main.bounds.height * 0.28.

  [BUG-04] Font not rendering (blank text):
    Symptom: Text views showing empty/blank in certain cells.
    Cause: .system(size:) font with weight/design combo that fails on older iOS.
    Fix: Replace with Theme.*Font() calls throughout.

  [BUG-05] Sparkline clipping:
    Symptom: Sparkline line cut off at top or bottom edge.
    Cause: Canvas drawing without inset padding for stroke width.
    Fix: In SparklineView Canvas, inset the drawing bounds by strokeWidth/2:
         let inset = strokeWidth / 2
         let drawRect = CGRect(x: inset, y: inset,
                               width: size.width - inset*2, height: size.height - inset*2)
         Recalculate x/y using drawRect dimensions.

  [BUG-06] ScrollView horizontal overscroll showing white/gray:
    Symptom: Horizontal scroll areas showing system default background at edges.
    Fix: .scrollContentBackground(.hidden) on all ScrollViews.
         .background(Theme.canvas) on the ScrollView container.

  [BUG-07] LazyVStack/LazyHStack memory pressure:
    Symptom: Holdings list or news feed stuttering when scrolling.
    Fix: Ensure all list containers use LazyVStack(spacing: Theme.Spacing.card) NOT VStack.
         Apply .id(item.id) to every ForEach item to enable proper recycling.

  [BUG-08] Missing haptic on ALL interactive elements:
    Search for: Button { ... } without .buttonStyle(EKPressStyle())
                .onTapGesture without HapticManager call
    Fix: Every tappable element MUST have EKPressStyle + haptic. Audit every file.

  [BUG-09] Safe area status bar overlap on Home:
    Symptom: "Hi, [Name]" title too close to status bar or notch.
    Fix: Ensure the home screen ScrollView has adequate top padding or uses
         .safeAreaPadding(.top) correctly. Never hardcode status bar height.

  [BUG-10] Donut chart segment gap rendering:
    Symptom: Donut segments have jagged edges or missing gap between them.
    Fix: Use Canvas with explicit arc drawing. Add 2° gap between segments using
         startAngle: baseAngle + .degrees(1), endAngle: nextAngle - .degrees(1)

STEP 8.3 — AGENTS.md violations sweep. grep across EVERY .swift file in ios/:
  Color(hex:          → Replace with Theme.* token
  Color(hue:          → Replace with Theme.* token (EXCEPT the tileColor function)
  .foregroundColor(.  → Replace with .foregroundStyle(Theme.*)
  .background(.blue)  → Replace with .background(Theme.*)
  .system(size:       → Replace with Theme.*Font()
  spacing: [0-9]+\b   → Replace with Theme.Spacing.*
  cornerRadius: [0-9] → Replace with Theme.CornerRadius.*
  Rectangle().fill(   → In section contexts, replace with GuillocheDivider()
                        In list contexts, replace with Divider at 0.5pt
  Divider()           → In section contexts, replace with GuillocheDivider()
  "Million"           → Replace with Lakhs/Crores via IndianFormatter
  "Billion"           → Replace with Crores via IndianFormatter

STEP 8.4 — Verify 0 violations remain. If any found, DO NOT proceed to Phase 9.
```

---

## PHASE 9: WATCHLIST SCREEN — FULL UI ALIGNMENT

Reference: Screen A analysis above.

```
Run gitnexus_impact({target: "WatchlistView", direction: "upstream"})

STEP 9.1 — Header
  The watchlist screen header must show:
    Top row: "X instruments" (count of items) in officialStampFont 9pt inkTertiary tracking 1.5
             NiveshBrandChip() on the right (see G5)
    Below: "Watchlist" in .largeTitle.weight(.bold) foreground inkPrimary
  Use a custom header — NOT navigationTitle() — because large title causes
  the "X instruments" count to disappear on scroll.
  Pattern: sticky VStack at top of the screen, NOT inside NavigationStack title.

STEP 9.2 — Row redesign
  Every watchlist row must match Screen A exactly:
  HStack(alignment: .center, spacing: Theme.Spacing.standard) {
      // Tile
      Text(String(ticker.prefix(2)).uppercased())
          .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote).weight(.semibold))
          .foregroundStyle(Theme.inkPrimary)
          .frame(width: 40, height: 40)
          .background(ticker.tileColor)
          .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
      // Names
      VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
          Text(ticker)
              .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.bold))
              .foregroundStyle(Theme.inkPrimary)
          Text(companyName)
              .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
              .foregroundStyle(Theme.inkTertiary)
      }
      Spacer()
      // Sparkline — 60×32
      SparklineView(values: sparklineValues,
                    color: (sparklineValues.last ?? 0) >= (sparklineValues.first ?? 0)
                           ? Theme.bullGreen : Theme.bearRed)
          .frame(width: 60, height: 32)
      // Price + badge
      VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
          Text(IndianFormatter.price(currentPrice))
              .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
              .foregroundStyle(Theme.inkPrimary)
          ChangeBadge(value: changePercent)
      }
  }
  .padding(.horizontal, Theme.screenPadding)
  .padding(.vertical, Theme.Spacing.standard)

STEP 9.3 — Row separator (NOT GuillocheDivider)
  Between each row:
  Rectangle()
      .fill(Theme.borderFine)
      .frame(height: 0.5)
      .padding(.horizontal, Theme.screenPadding)

STEP 9.4 — Empty state
  If watchlist is empty:
  VStack(spacing: Theme.Spacing.large) {
      Image(systemName: "list.star")
          .font(.system(size: 44)).foregroundStyle(Theme.inkTertiary)
      Text("YOUR WATCHLIST IS EMPTY")
          .font(Theme.officialStampFont(size: 11)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
      Text("Add stocks to track them here.")
          .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
          .foregroundStyle(Theme.inkSecondary)
  }
  .frame(maxWidth: .infinity, maxHeight: .infinity)

verify phase 9: Watchlist header shows count + NiveshBrandChip. Every row has unique tile color,
sparkline, price, ChangeBadge. 0.5pt row separators between items, NOT GuillocheDividers.
```

---

## PHASE 10: PORTFOLIO SCREEN — FULL UI ALIGNMENT

Reference: Screen B analysis above.

```
Run gitnexus_impact({target: "PortfolioScreen", direction: "upstream"})

STEP 10.1 — Hero value block
  VStack(alignment: .leading, spacing: Theme.Spacing.small) {
      HStack {
          VStack(alignment: .leading, spacing: 2) {
              Text("Portfolio · current value")
                  .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
              Text(IndianFormatter.price(portfolioValue))
                  .font(.largeTitle.weight(.bold)).monospaced().foregroundStyle(Theme.inkPrimary)
                  .contentTransition(.numericText())
          }
          Spacer()
          NiveshBrandChip()
      }
      HStack(spacing: Theme.Spacing.small) {
          // Delta pill
          ChangeBadge(value: totalPnLPercent)
          // Absolute pill
          Text("+" + IndianFormatter.priceCompact(totalPnL) + " total")
              .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
              .foregroundStyle(Theme.bullGreen)
              .padding(.horizontal, Theme.Spacing.medium)
              .padding(.vertical, Theme.Spacing.xSmall)
              .background(Theme.bullGreen.opacity(0.18))
              .clipShape(Capsule())
      }
  }
  .padding(.horizontal, Theme.screenPadding)
  .padding(.top, Theme.Spacing.card)

STEP 10.2 — Immersive chart
  Replace any existing portfolio chart with ImmersivePortfolioHeroChart (from prompt_mega_ui_overhaul.md Phase 3).
  Confirm it is full-bleed (negative horizontal margin), height = UIScreen.main.bounds.height * 0.28,
  no card background, glowing green line, area fill, scrub with ScrubTooltipView.

STEP 10.3 — Time range selector
  Replace any pill-style or segmented control with TimeRangeSelector (from G3 above).
  Ranges: [.day, .week, .month, .year, .all] → labels ["1D", "1W", "1M", "1Y", "ALL"]
  Default selected: .year (matching screenshot)

STEP 10.4 — Allocation donut card
  struct AllocationCard: View — implement as described in Screen B analysis.
  Canvas-based donut chart. 6 hardcoded palette colors cycling.
  "6\nSTOCKS" center text.
  Legend on the right showing top 4 holdings by weight.
  .banknoteCard() on the containing card.

STEP 10.5 — Holdings list
  Section header "Holdings" — engravedSerif 16pt inkPrimary heavy, padding(.horizontal, Theme.screenPadding)
  Wrap all holdings rows in a single .banknoteCard() container:
  VStack(spacing: 0) {
      ForEach(holdings) { holding in
          HoldingNoteRow(holding: holding, color: allocationColor(for: holding))
          if holding.id != holdings.last?.id {
              Rectangle().fill(Theme.borderFine).frame(height: 0.5)
                  .padding(.horizontal, Theme.Spacing.card)
          }
      }
  }
  .banknoteCard()
  .padding(.horizontal, Theme.screenPadding)

  struct HoldingNoteRow: View {
      let holding: HoldingModel
      let color: Color
      var body: some View {
          HStack {
              Circle().fill(color).frame(width: 8, height: 8)
              VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                  Text(holding.ticker)
                      .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.bold))
                      .foregroundStyle(Theme.inkPrimary)
                  Text("\(holding.quantity) shares")
                      .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                      .foregroundStyle(Theme.inkTertiary)
              }
              Spacer()
              VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                  Text(IndianFormatter.price(holding.currentValue))
                      .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
                      .foregroundStyle(Theme.inkPrimary)
                  ChangeBadge(value: holding.pnlPercent)
              }
          }
          .padding(.horizontal, Theme.Spacing.card)
          .padding(.vertical, Theme.Spacing.standard)
      }
  }

verify phase 10: Hero value shows IndianFormatter price + two pills. Chart is full-bleed immersive.
Time range underline selector. Donut shows allocation. Holdings in single card with dot + rows.
```

---

## PHASE 11: AI STOCK DETAIL SCREEN — FULL UI ALIGNMENT

Reference: Screen C analysis above.

```
Run gitnexus_impact({target: "AnalysisScreen", direction: "upstream"})

STEP 11.1 — Navigation bar
  Title: ticker symbol, bold, .headline, inkPrimary
  Right item: HStack { Text(price); ChangeBadge(value: changePercent) }
  .navigationBarTitleDisplayMode(.inline)
  .toolbarBackground(Theme.canvas, for: .navigationBar)
  .toolbarBackground(.visible, for: .navigationBar)

STEP 11.2 — Chart (same as Portfolio — reuse ImmersivePortfolioHeroChart or equivalent)
  Chart must respond to the stock's direction: bearRed if down, bullGreen if up.
  Full-bleed. Same ScrubTooltipView. Same TimeRangeSelector.

STEP 11.3 — Confidence ring card
  Implement ConfidenceRingCard as described in Screen C analysis.
  The circular ring uses Canvas API:
  Canvas { context, size in
      let center = CGPoint(x: size.width/2, y: size.height/2)
      let radius = size.width/2 - 4
      // Track ring
      var trackPath = Path()
      trackPath.addArc(center: center, radius: radius,
                       startAngle: .degrees(-90), endAngle: .degrees(270), clockwise: false)
      context.stroke(trackPath, with: .color(Theme.canvasShadow),
                     style: StrokeStyle(lineWidth: 6, lineCap: .round))
      // Progress ring
      let endDeg = -90 + 360 * confidence / 100
      var progressPath = Path()
      progressPath.addArc(center: center, radius: radius,
                          startAngle: .degrees(-90), endAngle: .degrees(endDeg), clockwise: false)
      context.stroke(progressPath, with: .color(ringColor),
                     style: StrokeStyle(lineWidth: 6, lineCap: .round))
  }
  .frame(width: 72, height: 72)
  Center overlay: ZStack { Text("\(confidence)%")... + Text("CONFIDENCE")... }

STEP 11.4 — Metric grid
  LazyVGrid with 3 flexible columns.
  Each metric cell: .banknoteCard() individually.
  Apply .financeTerm(metricName) to each metric label text.
  Values formatted: prices → IndianFormatter.priceCompact, ratios → plain decimal.

STEP 11.5 — Bull/Bear reasons section
  title: "Why we're bullish" or "Why we're bearish" depending on signal.
  Numbered items as described in Screen C analysis.
  Apply stripEmoji() to all AI-generated text.
  Apply .financeTerm() to any financial terms embedded in the text — this requires
  scanning the text for known terms from FinanceTerms.shared and wrapping matched substrings.
  Implement a helper: Text.markFinanceTerms(_ text: String) → AttributedString with tappable ranges.

verify phase 11: Nav bar shows ticker + price + badge inline. Chart full-bleed with direction color.
Confidence ring animates on appear. Metric grid 3-column with financeTerm tooltips.
Bull/Bear reasons use numbered circle badges. All emoji stripped.
```

---

## PHASE 12: HOME SCREEN — FULL UI ALIGNMENT

Reference: Screen D analysis above.

```
Run gitnexus_impact({target: "HomeScreen", direction: "upstream"})
NOTE: DO NOT touch HomeViewModel, NetworkManager, HomeSectionID, or .task {} blocks.

STEP 12.1 — Greeting header
  VStack(alignment: .leading, spacing: 2) {
      Text(Date().formatted(.dateTime.weekday(.wide).day().month(.wide)))
          .font(Theme.officialStampFont(size: 9)).tracking(0.5).foregroundStyle(Theme.inkTertiary)
      Text("Hi, \(userName)")
          .font(.largeTitle.weight(.bold)).foregroundStyle(Theme.inkPrimary)
  }
  Avatar in top-right (HStack with Spacer):
  Circle()
      .fill(Theme.securityGold)
      .frame(width: 36, height: 36)
      .overlay(Text(String(userName.prefix(1).uppercased()))
                   .font(Theme.serialNumberFont(size: 16, relativeTo: .body).weight(.semibold))
                   .foregroundStyle(Theme.canvas))

STEP 12.2 — NIFTY hero card
  NiftyHeroCard must include:
  - "NIFTY 50 · NSE" label row with ChangeBadge(value: niftyChange) on right
  - Index value in .title.weight(.bold).monospaced()
  - Mini inline area chart at card bottom: 80pt tall, full card width, Canvas-drawn
    The mini chart data = last 20 intraday points for NIFTY
    Same color logic: bullGreen if up, bearRed if down. Area fill at 0.08 opacity.
  - .banknoteCard() on the whole card
  - NO inner padding on the chart — it bleeds to card edges (negative padding: -Theme.Spacing.card)

STEP 12.3 — Index chips row
  3 fixed chips (SENSEX, BANK NIFTY, NIFTY IT) in HStack, each .frame(maxWidth: .infinity)
  Each chip: .banknoteCard()
    "SENSEX" officialStampFont 8pt inkTertiary tracking 1.2
    Value serialNumberFont 14pt inkPrimary bold
    ChangeBadge(value: change) — small version (font 10pt)
  NO LazyVGrid for this — it's always exactly 3 chips in 1 row.

STEP 12.4 — Morning Brief section
  Header HStack: "Morning Brief" engravedSerif 16pt heavy + Spacer + "See all" securityGold 12pt
  Each news card HStack:
    Icon square (40×40pt rounded, securityGold.opacity(0.15) bg, "bolt.fill" SF symbol securityGold)
    VStack:
      Category pill (officialStampFont 8pt tracking 1.5, securityGold bg 0.12, securityGold text)
      Headline engravedSerif 13pt inkPrimary .lineLimit(2)
  Card in .banknoteCard(), tap → navigate to news detail

STEP 12.5 — Sectors today section
  Header: "Sectors today" engravedSerif 16pt inkPrimary heavy
  Horizontal scroll of sector pills as described in Screen D analysis.
  ChangeBadge is NOT used here — sectors use a custom sector pill:
  struct SectorPill: View {
      let name: String; let change: Double
      var body: some View {
          let up = change >= 0
          Text(name + " " + IndianFormatter.percent(change))
              .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote))
              .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
              .padding(.horizontal, Theme.Spacing.card - 4)
              .padding(.vertical, Theme.Spacing.tight)
              .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.12))
              .clipShape(Capsule())
      }
  }

verify phase 12: Greeting header shows date + name + avatar. NIFTY card has inline mini chart.
3 index chips equal width. Morning Brief cards have icon + category pill + headline.
Sectors row scrolls horizontally. All theme tokens, no magic values.
```

---

## PHASE 13: RETHINK & STRATEGIC IMPLEMENTATION REVIEW

This phase is a deliberate pause-and-audit before finalising. Execute this AFTER all other phases.

```
STEP 13.1 — ARCHITECTURE CONSISTENCY AUDIT

Run gitnexus_query({query: "all ViewModels"}) and verify:
  - Every screen has one and only one ViewModel
  - No ViewModel is shared across screens (except AuthManager via @Environment)
  - No ViewModel contains SwiftUI View code
  - No View contains business logic (only formatting and layout)
  - All network calls are in .task {} blocks, not in body or init

STEP 13.2 — DATA FLOW AUDIT

Run gitnexus_query({query: "data binding state environment"}) and verify:
  - Data flows DOWN via let and @Binding only
  - Events flow UP via closures (onTap: () -> Void, onSelect: (Ticker) -> Void)
  - No child view accesses a parent ViewModel via @EnvironmentObject (except AuthManager)
  - No ViewModel is passed more than 2 levels deep

STEP 13.3 — PERFORMANCE AUDIT

  For each of the 5 main screens, verify:
  [ ] Initial render time: skeleton visible within 100ms
  [ ] Data visible: within 2000ms from screen appear
  [ ] No .task {} blocks on non-root views (only root screen-level views)
  [ ] All image loading is async with placeholder
  [ ] LazyVStack used for all lists of >5 items
  [ ] All Chart Canvas drawing happens off-main-thread where possible

STEP 13.4 — UI REGRESSION CHECKLIST

  For every screen, confirm ALL of the following on iPhone SE (375pt) AND Pro Max (430pt):
  [ ] No text truncated unexpectedly (use .lineLimit with appropriate values)
  [ ] No buttons with tap targets < 44×44pt
  [ ] No content hidden behind navigation bar or tab bar
  [ ] No horizontal overflow (no subview wider than screen)
  [ ] All cards have consistent padding and corner radii via Theme tokens
  [ ] All chart tooltips render within screen bounds (don't overflow off-screen)
  [ ] Pull-to-refresh works and shows haptic (impact(.medium) start, success() complete)

STEP 13.5 — CROSS-SCREEN VISUAL CONSISTENCY CHECK

  Open every screen back-to-back and verify these are identical across all screens:
  [ ] Background color (Theme.canvas — same shade everywhere)
  [ ] Section header font and size (engravedSerif 16pt heavy)
  [ ] Section label font and size (officialStampFont 9pt tracking 1.5 inkTertiary)
  [ ] Card appearance (.banknoteCard() — same corner radius, border, shadow everywhere)
  [ ] Badge appearance (ChangeBadge — same capsule, same opacity, same fonts everywhere)
  [ ] Chart line style (same weight, same color logic, same area fill everywhere)
  [ ] Time range selector (underline style, same fonts, same active/inactive colors everywhere)
  [ ] Tab bar (identical across all 5 tabs — same background, same icon style)

STEP 13.6 — FINAL CONFLICT RESOLUTION

  Identify any symbol that was modified in multiple phases (e.g. PortfolioScreen touched in
  Phase 7, 10, and 13). Consolidate into the final version — no duplicate implementations.
  Run gitnexus_detect_changes() to see the complete diff.
  Resolve any merge conflicts. Ensure no phase regressed a previous phase's changes.

STEP 13.7 — SIGN-OFF BUILD

  [ ] xcodebuild -scheme stockme -configuration Debug clean build → BUILD SUCCEEDED
  [ ] Zero errors. Zero warnings.
  [ ] grep -rn "Color(hex:" ios/ → 0 results
  [ ] grep -rn "\.system(size:" ios/ → 0 results  
  [ ] grep -rn "spacing: [0-9]" ios/ → 0 results (except comments)
  [ ] grep -rn "cornerRadius: [0-9]" ios/ → 0 results (except tileColor function)
  [ ] grep -rn "Million\|Billion\|Trillion" backend/ → 0 results in output strings
  [ ] Login with snp050106@gmail.com → home screen loads with mock data
  [ ] All 5 tabs navigable. No crash on any navigation path.
```

---

## EXECUTION ORDER

```
Phase 8  (Rendering Audit)       ← DO THIS FIRST — fixes all existing bugs
Phase 9  (Watchlist UI)          ← Simple list screen
Phase 10 (Portfolio UI)          ← Chart + allocation card
Phase 11 (AI Detail UI)          ← Confidence ring + metric grid
Phase 12 (Home UI)               ← Hero card + sections
Phase 13 (Strategic Review)      ← Final audit + sign-off

Then execute the original phases (in order):
Phase 0  (Database reset)
Phase 1  (Long-press terms)
Phase 2  (Screener sparklines)
Phase 3  (Markets navigation)
Phase 4  (Portfolio icons)
Phase 5  (Nav spacing fix)
Phase 6  (Theme system)
Phase 7  (Portfolio card redesign)

Phase 13 Step 13.6 (Final conflict resolution + sign-off build)
```

---

## WHAT NOT TO TOUCH

```
DO NOT MODIFY:
  HomeViewModel (any ViewModel actually)
  NetworkManager (any fetch/load method)
  HomeSectionID enum
  Any .task {} block
  INDIAN_MARKET_SYSTEM_PROMPT in prompts.py
  build_ta_config() in orchestrator.py
  _normalize_response() in orchestrator.py
  DEFAULT_CONFIG in tradingagents-core
  Any multiprocessing.Process spawn pattern in routers/
  get_session() in database.py
  Any existing auth.py rate limiting logic
```
