# NIVESH — COMPLETE DARK FINTECH UI OVERHAUL
# Migrate the entire app from the Banknote Aesthetic to the modern dark fintech design
# shown in the 4 reference screenshots. This is a full A–Z design system replacement.
# Paste this entire document into Claude Code as your implementation prompt.

---

```xml
<system>

<identity>
You are migrating the Nivesh iOS app from its current "Banknote Aesthetic" to a modern dark
fintech design language — the same visual identity used in the 4 reference screenshots provided.
This is a complete design system replacement: colors, typography weights, chart style, badge
style, tab bar, card surfaces, dividers, and spacing rhythm all change.

Every file you touch must pass a before/after visual check against the reference screenshots.
Run gitnexus_impact before editing any existing symbol. Run gitnexus_detect_changes before commit.
</identity>

<reference_screenshots>
  Screen A — Watchlist:    Deep near-black bg, blue-tinted stock tiles, green/red sparklines,
                           white bold tickers, gray company names, capsule % badges.
  Screen B — Portfolio:    Hero ₹ value (huge bold mono), green glow line chart full-bleed,
                           two teal pill badges, underline time selector, donut + holdings.
  Screen C — AI Analysis:  Inline nav bar with price+badge, same green chart, confidence ring,
                           3×2 metric card grid, numbered blue circle bullet points.
  Screen D — Home:         Date + "Hi, [name]" greeting, blue avatar circle, NIFTY hero card
                           with embedded mini chart, 3-chip index row, news cards, sector pills.
</reference_screenshots>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE A: NEW COLOR SYSTEM — REPLACE ALL THEME.SWIFT TOKENS
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="A" name="ColorSystemReplacement">

Run gitnexus_impact({target: "Theme", direction: "upstream"}) first.

FILE TO EDIT: ios/StockApp/stockme/stockme/Utilities/Theme.swift

Replace ALL dynamic color properties with the new dark fintech palette.
These are the ONLY authorised color values in the entire app going forward.
Never use raw hex strings in view files — always reference Theme.* tokens.

--- NEW PALETTE (measured from reference screenshots) ---

BACKGROUNDS:
  Theme.canvas        = Color(red: 0.035, green: 0.043, blue: 0.063)   // #090B10 deep navy-black
  Theme.canvasDeep    = Color(red: 0.075, green: 0.082, blue: 0.118)   // #13151E card surface
  Theme.canvasShadow  = Color(red: 0.051, green: 0.059, blue: 0.082)   // #0D0F15 pressed/inset

TEXT:
  Theme.inkPrimary    = Color(red: 0.949, green: 0.941, blue: 0.925)   // #F2F0EC warm white
  Theme.inkSecondary  = Color(red: 0.545, green: 0.557, blue: 0.612)   // #8B8E9C cool gray
  Theme.inkTertiary   = Color(red: 0.290, green: 0.302, blue: 0.361)   // #4A4D5C muted dark

ACCENT (replaces securityGold — now electric blue):
  Theme.securityGold     = Color(red: 0.357, green: 0.565, blue: 0.965) // #5B90F6 electric blue
  Theme.securityGoldLight = Color(red: 0.467, green: 0.655, blue: 0.980) // #77A7FA lighter blue

FINANCIAL SIGNAL COLORS (brighter, more electric):
  Theme.bullGreen        = Color(red: 0.000, green: 0.784, blue: 0.588) // #00C896 electric teal-green
  Theme.bullGreenLight   = Color(red: 0.000, green: 0.784, blue: 0.588).opacity(0.18)
  Theme.bearRed          = Color(red: 1.000, green: 0.302, blue: 0.302) // #FF4D4D electric red
  Theme.bearRedLight     = Color(red: 1.000, green: 0.302, blue: 0.302).opacity(0.18)
  Theme.holdAmber        = Color(red: 0.980, green: 0.702, blue: 0.110) // #FAB31C amber

BORDERS:
  Theme.borderFine    = Theme.inkPrimary.opacity(0.08)   // very subtle white tint
  Theme.borderSage    = Theme.securityGold.opacity(0.20) // blue tint for active borders

--- STEP A.1: Update ThemeManager.swift canvas/accent per theme ---

The ThemeManager canvasColor and accentColor methods must also use the new base values.
For the default darkImmersive theme specifically, the canvas must be:
  Color(red: 0.035, green: 0.043, blue: 0.063)  // #090B10
And accentColor must be:
  Color(red: 0.357, green: 0.565, blue: 0.965)  // #5B90F6

All other 6 banknote themes keep their canvas tints, but their accent colors become
blue-family hues (not gold-family). Update each:
  chocolateBrown:   accent = Color(red: 0.55, green: 0.65, blue: 0.95)  // warm blue
  greenishYellow:   accent = Color(red: 0.30, green: 0.85, blue: 0.65)  // teal
  fluorescentBlue:  accent = Color(red: 0.20, green: 0.55, blue: 1.00)  // pure blue
  lavender:         accent = Color(red: 0.70, green: 0.55, blue: 0.95)  // purple-blue
  brightYellow:     accent = Color(red: 0.95, green: 0.85, blue: 0.20)  // keep yellow-gold
  stoneGrey:        accent = Color(red: 0.65, green: 0.70, blue: 0.80)  // blue-grey

--- STEP A.2: Chart line color update ---

The chart glow line color must be Theme.bullGreen (#00C896) for positive portfolios/periods
and Theme.bearRed (#FF4D4D) for negative. This replaces the previous dark forest green.
The area gradient fill uses: lineColor.opacity(0.15) → lineColor.opacity(0.00) top to bottom.
Update this in: ImmersivePortfolioHeroChart.swift, StockCharts.swift, and any inline canvas chart.

--- STEP A.3: Remove all references to old color names ---

Search for any hardcoded old theme expectations:
  grep -rn "B8973A\|C8A84A\|2D5A3D\|8B3A2A\|5C6B5A\|8A9E80" ios/
Replace each with the appropriate new token.

verify phase A: Launch app. Background should be deep navy-black #090B10. 
No aged-paper/brown tones anywhere. Accent elements (active tab, "See all", links) are blue.
Chart lines are bright teal-green #00C896. Badge backgrounds are tinted (not opaque).
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE B: TYPOGRAPHY MODERNISATION
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="B" name="TypographyModernisation">

The reference screenshots show a cleaner, more modern typography hierarchy.
The heavy serif (Georgia engraved) feel is reduced — the app reads sharper and more digital.

Run gitnexus_impact({target: "Theme", direction: "upstream"}) before editing Theme.swift.

--- STEP B.1: Reduce engravedSerif usage ---

The engravedSerif (Georgia) font was the Banknote Aesthetic's signature. In the new design,
it is retained ONLY for body text, descriptions, and narrative content. It is removed from:
  - Section headers → use officialStampFont (condensed, tracked) instead
  - Section sub-labels → use serialNumberFont (mono) instead
  - News headlines → switch to .headline.weight(.semibold) system font
  - Card labels → officialStampFont or serialNumberFont

The new typography hierarchy:
  Hero numbers  (prices, values):    .largeTitle/.title weight .bold, monospaced()
  Section headers:                   officialStampFont size 12, tracking 1.5, weight .bold
  Section labels / metadata:         officialStampFont size 8-9, tracking 1.2-1.5, inkTertiary
  Ticker symbols:                    serialNumberFont size 13-14, weight .bold
  Company names:                     engravedSerif size 11-12 OR .subheadline, inkSecondary
  Body / description text:           engravedSerif size 13-14, weight .regular
  Numeric data (P/E, ROE, etc.):     serialNumberFont size 13-16, weight .semibold
  Badges / pills:                    serialNumberFont size 10-11, weight .semibold

--- STEP B.2: Remove ALL .font(.system(size:)) calls in view files ---

Search: grep -rn "\.system(size:" ios/StockApp
Every hit in a VIEW file (.swift outside Theme.swift) must be replaced with a Theme.*Font() call.
The ones inside Theme.swift itself (the font builder internals) are fine and must NOT be changed.

Replacement map:
  .system(size: 7)              → Theme.officialStampFont(size: 7)
  .system(size: 8, weight: .bold) → Theme.officialStampFont(size: 8)
  .system(size: 9)              → Theme.officialStampFont(size: 9)
  .system(size: 10)             → Theme.serialNumberFont(size: 10)
  .system(size: 11)             → Theme.serialNumberFont(size: 11)
  .system(size: 12)             → Theme.serialNumberFont(size: 12)
  .system(size: 13)             → Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body)
  .system(size: 14)             → Theme.serialNumberFont(size: 14)

--- STEP B.3: Hero value text weight ---

Every primary portfolio/price value displayed as the hero number on a screen must use:
  .font(.largeTitle.weight(.bold)).monospaced()
  OR for smaller hero contexts:
  .font(.title.weight(.bold)).monospaced()
These match the large bold mono numerals visible in the Portfolio and Watchlist screens.

verify phase B: Zero .system(size:) calls remain in view files. 
Hero prices are large, bold, monospaced. Section labels are tracked officialStamp.
App reads crisper and more modern — less "old document", more "real-time fintech".
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE C: COMPONENT SYSTEM MODERNISATION
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="C" name="ComponentSystemModernisation">

Every shared component must be updated to use the new color tokens and visual language.
FILE: ios/StockApp/stockme/stockme/Components/SharedDarkComponents.swift
Run gitnexus_impact({target: "SharedDarkComponents", direction: "upstream"})

--- STEP C.1: Update ChangeBadge ---

The badge in the reference screenshots has:
  - Capsule shape
  - Background: bullGreen.opacity(0.18) for positive, bearRed.opacity(0.18) for negative
  - Text color: Theme.bullGreen for positive, Theme.bearRed for negative
  - Font: serialNumberFont 11pt, weight .semibold
  - With directional arrow: "▲ +1.24%" (up) or "▼ -0.42%" (down)
  - Padding: horizontal 8pt (Theme.Spacing.medium), vertical 3pt (Theme.Spacing.xSmall + 1)

Replace the entire ChangeBadge implementation:

  struct ChangeBadge: View {
      let value: Double
      var fontSize: CGFloat = 11
      var body: some View {
          let up = value >= 0
          Text((up ? "▲ " : "▼ ") + (up ? "+" : "") + IndianFormatter.percent(abs(value)))
              .font(Theme.serialNumberFont(size: fontSize, relativeTo: .footnote).weight(.semibold))
              .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
              .padding(.horizontal, Theme.Spacing.medium)
              .padding(.vertical, 3)
              .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.18))
              .clipShape(Capsule())
      }
  }

--- STEP C.2: Update TimeRangeSelector ---

The time selector in screenshots uses underline style, NOT a background highlight.
Selected tab: Theme.inkPrimary text + 1.5pt underline in Theme.securityGold (electric blue).
Unselected: Theme.inkTertiary text, no underline.

  struct TimeRangeSelector: View {
      @Binding var selected: TimeRange
      let ranges: [TimeRange]
      var body: some View {
          HStack(spacing: 0) {
              ForEach(ranges, id: \.self) { range in
                  Button(action: { HapticManager.selection(); selected = range }) {
                      VStack(spacing: 3) {
                          Text(range.label)
                              .font(Theme.officialStampFont(size: 11).weight(
                                  selected == range ? .bold : .regular))
                              .foregroundStyle(selected == range ? Theme.inkPrimary : Theme.inkTertiary)
                          Rectangle()
                              .fill(selected == range ? Theme.securityGold : Color.clear)
                              .frame(height: 1.5)
                              .cornerRadius(0.75)
                      }
                      .frame(maxWidth: .infinity)
                      .padding(.vertical, Theme.Spacing.standard)
                      .contentShape(Rectangle())
                  }
                  .buttonStyle(EKPressStyle())
              }
          }
      }
  }

--- STEP C.3: Update card surface (.banknoteCard modifier) ---

The new card surface must match the dark fintech look:
  - Background: Theme.canvasDeep (#13151E)
  - Corner radius: Theme.CornerRadius.large (12pt) for most cards
  - Single border: 0.5pt Theme.inkPrimary.opacity(0.10) — single stroke, no double-border
  - Shadow: Theme.canvas.opacity(0.6) radius 8, y 4 (deeper, softer shadow)
  - NO double-border guilloche effect

Update the .banknoteCard() ViewModifier in Theme.swift:

  func banknoteCard() -> some View {
      self
          .background(Theme.canvasDeep)
          .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
          .overlay(
              RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                  .stroke(Theme.inkPrimary.opacity(0.10), lineWidth: 0.5)
          )
          .shadow(color: Theme.canvas.opacity(0.6), radius: 8, x: 0, y: 4)
  }

--- STEP C.4: GuillocheDivider → subtle line ---

The reference screenshots show NO guilloche wave pattern between sections.
They use a very plain, subtle horizontal line.
Replace GuillocheDivider with a simple styled divider for section breaks:

  struct SectionDivider: View {
      var body: some View {
          Rectangle()
              .fill(Theme.inkPrimary.opacity(0.07))
              .frame(height: 0.5)
              .padding(.horizontal, Theme.screenPadding)
      }
  }

IMPORTANT: Do a global replace of GuillocheDivider() with SectionDivider() across ALL view files.
The GuillocheDivider struct in Theme.swift can remain but should not be used in any view.
Search: grep -rn "GuillocheDivider()" ios/ → replace every instance with SectionDivider()

List row separators (between list items, NOT between sections) remain as:
  Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

--- STEP C.5: Update NiveshBrandChip ---

In the reference screenshots, "Nivesh निवेश" top-right reads:
  "Nivesh" in Theme.inkPrimary weight .semibold, ~12pt
  "निवेश" in Theme.inkSecondary hindi font, ~11pt
No border, no background — plain text chip.

--- STEP C.6: tileColor update ---

The watchlist tile backgrounds in the screenshots appear as blue-navy tinted squares.
Update tileColor to produce blue-family hues that fit the new dark palette:

  var tileColor: Color {
      let hues: [Double] = [0.60, 0.63, 0.58, 0.55, 0.65, 0.68, 0.57, 0.61]
      let saturations: [Double] = [0.50, 0.45, 0.55, 0.42, 0.48, 0.52, 0.46, 0.50]
      let idx = abs(self.hashValue) % hues.count
      return Color(hue: hues[idx], saturation: saturations[idx], brightness: 0.30)
  }

verify phase C: Cards use single-border, no double stroke, no guilloche overlay.
GuillocheDivider gone — replaced by SectionDivider (plain 0.5pt line).
ChangeBadge uses directional arrows, electric green/red. TimeRangeSelector underline style.
Tile backgrounds are blue-family hues.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE D: TAB BAR & NAVIGATION MODERNISATION
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="D" name="TabBarNavigationModernisation">

Run gitnexus_impact({target: "ContentView", direction: "upstream"})

--- STEP D.1: Tab bar visual update ---

The reference screenshots show a clean dark tab bar:
  Background: Theme.canvasDeep with no visible top border (very subtle)
  Active tab:  Icon (filled SF symbol) + label below, color = Theme.securityGold (electric blue)
  Inactive tab: Icon (outline SF symbol), color = Theme.inkTertiary, label visible but smaller

Update the tab bar in ContentView or wherever TabView is configured:

  TabView(selection: $selectedTab) {
      HomeScreen()
          .tabItem {
              Label("Home", systemImage: selectedTab == 0 ? "house.fill" : "house")
          }
          .tag(0)
      WatchlistScreen()
          .tabItem {
              Label("Watchlist", systemImage: selectedTab == 1 ? "list.bullet" : "list.bullet")
          }
          .tag(1)
      PortfolioScreen()
          .tabItem {
              Label("Portfolio", systemImage: selectedTab == 2 ? "briefcase.fill" : "briefcase")
          }
          .tag(2)
      MarketsScreen()
          .tabItem {
              Label("Markets", systemImage: selectedTab == 3 ? "chart.bar.fill" : "chart.bar")
          }
          .tag(3)
      AlertsScreen()
          .tabItem {
              Label("Alerts", systemImage: selectedTab == 4 ? "bell.fill" : "bell")
          }
          .tag(4)
  }
  .tint(Theme.securityGold)  // active tab color = electric blue
  .toolbarBackground(Theme.canvasDeep, for: .tabBar)
  .toolbarBackground(.visible, for: .tabBar)

--- STEP D.2: Navigation bar update ---

Every navigation bar in the app must:
  .navigationBarTitleDisplayMode(.inline)  — NO large titles on detail screens
  .toolbarBackground(Theme.canvas, for: .navigationBar)
  .toolbarBackground(.visible, for: .navigationBar)
  Title text color: Theme.inkPrimary
  Back button tint: Theme.securityGold (electric blue)

  .tint(Theme.securityGold)  — add to every NavigationStack root

Root tab screens (Home, Watchlist, Portfolio, Markets) use LARGE title style with custom header:
  NOT .navigationBarTitleDisplayMode(.large) — use a custom sticky VStack header instead
  because the large system title doesn't allow the subtitle count line above it.

--- STEP D.3: Markets pill tab bar ---

The MarketsTabBar already built — update its colors to match new tokens:
  Active pill: Theme.securityGold (electric blue) background, Theme.canvas text
  Inactive pill: Theme.canvasDeep background, Theme.inkTertiary text
  Border on inactive: Theme.inkPrimary.opacity(0.10)

verify phase D: Active tab icon+label is electric blue. Nav bars dark. Back button blue.
Markets pills use electric blue for active. All transitions smooth.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE E: CHART AESTHETIC OVERHAUL
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="E" name="ChartAestheticOverhaul">

The reference screenshots show a distinctive chart style: glowing neon teal-green line
on a dark background with a soft gradient area fill. This must be consistent across
Portfolio, Stock Detail, Home NIFTY card, and all full-width price charts.

Run gitnexus_impact({target: "ImmersivePortfolioHeroChart", direction: "upstream"})
Run gitnexus_impact({target: "PriceHistoryChart", direction: "upstream"})

--- STEP E.1: Chart line style ---

Every full-width price chart must use:
  Line color:    Theme.bullGreen (#00C896) if chart direction is positive
                 Theme.bearRed (#FF4D4D) if negative
  Line weight:   2pt
  Line cap:      .round
  Line join:     .round
  Area fill:     LinearGradient(
                     colors: [lineColor.opacity(0.20), lineColor.opacity(0.05), lineColor.opacity(0.00)],
                     startPoint: .top, endPoint: .bottom
                 )
  Background:    Theme.canvas — the chart area has NO card background, it floats on screen bg

--- STEP E.2: Scrub interaction (drag gesture) ---

When the user drags on any chart:
  Tooltip card: Theme.canvasDeep background, single 0.5pt border (Theme.inkPrimary.opacity(0.15))
                cornerRadius Theme.CornerRadius.large (12pt)
                "₹X,XX,XXX · DD Mon" — serialNumberFont 12pt, Theme.inkPrimary
  Dashed vertical line: 1pt dashed, color Theme.inkTertiary.opacity(0.5), dash [5,4]
  Dot on line at scrub point: filled circle 7pt diameter, color = lineColor (bullGreen/bearRed)
                              white 1.5pt border ring around the dot

--- STEP E.3: NIFTY hero mini chart (inside Home screen card) ---

The Home screen shows NIFTY with an inline mini area chart at the card bottom.
This chart is 80pt tall, full card width (bleeds to card edges with -Theme.Spacing.card padding).
Same color logic. No axis labels. No interaction. Pure decorative data display.
Canvas drawing only — no Charts framework.

--- STEP E.4: Sparkline update ---

SparklineView for watchlist/screener rows:
  Line weight: 1.5pt
  Line color:  Theme.bullGreen or Theme.bearRed (same electric colors)
  NO area fill for sparklines — line only
  The overall line is smoother — use quadCurve instead of straight line segments:
  
  struct SparklineView: View {
      let values: [Double]
      let color: Color
      var body: some View {
          Canvas { context, size in
              guard values.count > 1 else { return }
              let mn = values.min()!, mx = values.max()!
              let rng = max(mx - mn, 0.001)
              let inset: CGFloat = 1.0
              func pt(_ i: Int) -> CGPoint {
                  let x = inset + CGFloat(i) / CGFloat(values.count - 1) * (size.width - inset*2)
                  let y = inset + (size.height - inset*2) * (1 - CGFloat((values[i] - mn) / rng))
                  return CGPoint(x: x, y: y)
              }
              var path = Path()
              path.move(to: pt(0))
              for i in 1..<values.count {
                  let prev = pt(i - 1), curr = pt(i)
                  let cp1 = CGPoint(x: (prev.x + curr.x) / 2, y: prev.y)
                  let cp2 = CGPoint(x: (prev.x + curr.x) / 2, y: curr.y)
                  path.addCurve(to: curr, control1: cp1, control2: cp2)
              }
              context.stroke(path, with: .color(color),
                             style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
          }
      }
  }

verify phase E: Charts show electric teal-green glow on dark. Area fill subtle gradient.
Sparklines smooth curves. Scrub shows floating price card + dashed line + dot on chart.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE F: SCREEN-BY-SCREEN VISUAL ALIGNMENT
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="F" name="ScreenByScreenAlignment">

After Phases A–E establish the design system, apply it consistently to every screen.
For each screen: run gitnexus_impact on the root view, then update.

--- SCREEN F.1: WATCHLIST ---

Header:
  "X instruments" — officialStampFont 9pt, inkTertiary, tracking 1.5
  "Watchlist" — .largeTitle.weight(.heavy), inkPrimary
  NiveshBrandChip top-right (same as before)

Each row (already partially done — verify all tokens are updated):
  Tile: 40×40pt, tileColor background (blue family), inkPrimary text serialNumberFont 12pt bold
  Ticker: serialNumberFont 14pt bold inkPrimary
  Company: .subheadline.weight(.regular) OR engravedSerif 11pt, inkSecondary
  Sparkline: 60×32pt, smooth curves, electric green/red
  Price: serialNumberFont 14pt bold inkPrimary
  Badge: ChangeBadge(value:) — electric green/red capsule with arrow

Row separator: Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
               .padding(.horizontal, Theme.screenPadding)

--- SCREEN F.2: PORTFOLIO ---

Hero block:
  "Portfolio · current value" officialStampFont 9pt inkTertiary tracking 1.5
  Price: .largeTitle.weight(.bold).monospaced() inkPrimary (e.g. "₹12,48,500")
  Two pills row:
    ChangeBadge(value: totalPnLPercent) — electric green with arrow
    Custom pill: "+₹X,XX,XXX total" — serialNumberFont 12pt bullGreen,
                 bullGreen.opacity(0.18) background, Capsule()

Full-bleed chart (ImmersivePortfolioHeroChart) — electric teal-green, same gradient fill.
TimeRangeSelector — underline style, electric blue underline.

Donut card: .banknoteCard() (single border, no guilloche). 
  Same donut logic but dot colors use the new bright palette.

Holdings: holding rows in single .banknoteCard() container.
  Each row: 8pt colored circle, ticker bold, "X shares" inkTertiary,
            value serialNumberFont bold inkPrimary, ChangeBadge right.
  Row separator: 0.5pt inkPrimary.opacity(0.06)

--- SCREEN F.3: AI STOCK DETAIL (AnalysisScreen) ---

Nav bar: ticker bold .headline inkPrimary, right = price + ChangeBadge, .inline display mode.

Chart: full-bleed electric green (or red), same style.
TimeRangeSelector: underline style.

Confidence ring card:
  .banknoteCard() — single border.
  Ring: Canvas arc, lineWidth 6pt, lineCap .round.
  Track: Theme.canvasShadow
  Progress: Theme.bullGreen (bullish) / Theme.bearRed (bearish) / Theme.holdAmber (hold)
  Center: serialNumberFont 18pt bold inkPrimary for %, officialStampFont 7pt inkTertiary for "CONFIDENCE"
  
  Signal pill: officialStampFont 10pt tracking 1.5
    BULLISH: bullGreen.opacity(0.18) bg, bullGreen text
    BEARISH: bearRed.opacity(0.18) bg, bearRed text
    HOLD:    holdAmber.opacity(0.18) bg, holdAmber text

  Target text: serialNumberFont 14pt inkPrimary
  Upside text: serialNumberFont 12pt bullGreen/bearRed

Metric grid (3-col):
  Each cell: .banknoteCard() individually
  Label: officialStampFont 8pt inkTertiary tracking 1.2
  Value: serialNumberFont 14pt inkPrimary bold

"Why we're bullish/bearish" section:
  Header: .headline.weight(.bold) inkPrimary
  Number badge: Circle 20pt, securityGold.opacity(0.15) bg, securityGold text, serialNumberFont 12pt
  Text: engravedSerif 13pt inkSecondary

--- SCREEN F.4: HOME SCREEN ---

IMPORTANT: DO NOT touch HomeViewModel, NetworkManager, HomeSectionID, or .task {} blocks.
Only update the visual rendering layer.

Greeting header:
  Date: officialStampFont 9pt inkTertiary tracking 0.5
  "Hi, [name]": .largeTitle.weight(.bold) inkPrimary
  Avatar: 36pt circle, securityGold background, canvas text, serialNumberFont 16pt bold

NIFTY hero card (.banknoteCard()):
  "NIFTY 50 · NSE" officialStampFont 9pt inkTertiary tracking 1.5 (left)
  ChangeBadge top-right
  Index value: .title.weight(.bold).monospaced() inkPrimary
  Mini inline chart at card bottom: 80pt tall, full-bleed, electric green area chart

3-chip index row: HStack with 3 × .frame(maxWidth: .infinity) chips (.banknoteCard())
  Each chip:
    Label: officialStampFont 8pt inkTertiary tracking 1.2
    Value: serialNumberFont 16pt inkPrimary bold
    ChangeBadge below value (smaller font 10pt)

Morning Brief section:
  "Morning Brief" .headline.weight(.bold) inkPrimary + "See all" securityGold 13pt
  Each card (.banknoteCard()):
    Icon square: 40×40pt, RoundedRectangle cornerRadius Theme.CornerRadius.medium
                 securityGold.opacity(0.15) background
                 Image(systemName: "bolt.fill") securityGold .title3
    Category pill: officialStampFont 8pt tracking 1.5
                   securityGold.opacity(0.15) bg, securityGold text, Capsule
    Headline: .subheadline.weight(.semibold) inkPrimary, lineLimit(2)

Sectors today section:
  "Sectors today" .headline.weight(.bold) inkPrimary
  Horizontal scroll of SectorPill views:
    struct SectorPill: View {
        let name: String; let change: Double
        var body: some View {
            let up = change >= 0
            Text(name + " " + (up ? "+" : "") + String(format: "%.2f", change) + "%")
                .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote).weight(.semibold))
                .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
                .padding(.horizontal, Theme.Spacing.card - 4)
                .padding(.vertical, Theme.Spacing.tight)
                .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.12))
                .clipShape(Capsule())
        }
    }

--- SCREEN F.5: SETTINGS ---

Update the DENOMINATION THEME section to use new accent color (electric blue).
The active theme checkmark should use Theme.securityGold (now electric blue).
All settings row items: inkPrimary text, inkTertiary labels, canvasDeep backgrounds.
No aged-paper tones anywhere in settings.

--- SCREEN F.6: ALL OTHER SCREENS (Search, Alerts, Screener, etc.) ---

For every screen not explicitly listed above:
  1. Run gitnexus_impact on the root view
  2. Apply the same token replacements:
     - Any warmth/aged-paper tones → Theme.canvas (deep navy-black)
     - Any securityGold usage → still valid (it's now electric blue)
     - Any hardcoded green #2D5A3D or red #8B3A2A → Theme.bullGreen / Theme.bearRed
     - Any GuillocheDivider() → SectionDivider()
     - .banknoteCard() double-border → single-border (handled by updated modifier)
  3. Verify no aged-paper, no warm brown, no serif-heavy layout remains

verify phase F: Every screen matches the reference screenshots.
Background: deep navy-black. Cards: dark lifted surface. Accent: electric blue.
Charts: electric teal-green. Badges: electric green/red arrows.
Typography: bold mono for prices, tracked caps for labels.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE G: SPACING SWEEP — ELIMINATE ALL MAGIC INTEGERS
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="G" name="SpacingSweep">

There are currently 324 magic spacing integers in the codebase. Eliminate all of them.
This is a sweep phase — methodical file-by-file replacement.

Run: grep -rn "spacing: [0-9]" ios/StockApp --include="*.swift" | grep -v Theme.swift | grep -v ".git"

For each hit, replace with the appropriate Theme.Spacing token:

  spacing: 2    → Theme.Spacing.xSmall
  spacing: 4    → Theme.Spacing.small
  spacing: 6    → Theme.Spacing.tight
  spacing: 8    → Theme.Spacing.medium
  spacing: 10   → Theme.Spacing.medium   (round up, 10 is not on the 8pt grid)
  spacing: 12   → Theme.Spacing.standard
  spacing: 14   → Theme.Spacing.standard (round down)
  spacing: 16   → Theme.Spacing.card
  spacing: 20   → Theme.Spacing.screen
  spacing: 24   → Theme.Spacing.large
  spacing: 32   → Theme.Spacing.xLarge

Same sweep for .padding(<int>):
  .padding(4)   → .padding(Theme.Spacing.small)
  .padding(8)   → .padding(Theme.Spacing.medium)
  .padding(12)  → .padding(Theme.Spacing.standard)
  .padding(16)  → .padding(Theme.Spacing.card)
  .padding(20)  → .padding(Theme.screenPadding)

And for cornerRadius(<int>) outside of Theme.swift:
  cornerRadius: 4   → Theme.CornerRadius.small
  cornerRadius: 6   → Theme.CornerRadius.tight
  cornerRadius: 8   → Theme.CornerRadius.medium
  cornerRadius: 12  → Theme.CornerRadius.large
  cornerRadius: 16  → Theme.CornerRadius.card

Run gitnexus_detect_changes() after this phase. Expected: dozens of files changed.
Zero new magic integers introduced.

verify phase G: grep -rn "spacing: [0-9]" ios/StockApp | grep -v Theme.swift → 0 results
               grep -rn "cornerRadius: [0-9]" ios/StockApp | grep -v Theme.swift → 0 results
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE H: DIVIDER SWEEP — REPLACE PLAIN Divider() AND Rectangle DIVIDERS
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="H" name="DividerSweep">

Currently 99 plain Divider() calls and 23 Rectangle().fill() divider patterns exist.

--- RULE ---
Between SECTIONS (major content blocks):     SectionDivider()
Between LIST ROWS (holdings, watchlist, news): Rectangle().fill(Theme.inkPrimary.opacity(0.06))
                                                           .frame(height: 0.5)
NEVER use: Divider() / GuillocheDivider() / Rectangle().fill(.gray)

--- PROCESS ---

1. grep -rn "Divider()" ios/StockApp --include="*.swift" | grep -v ".git"
   For each hit: determine context (is this a section break or a list separator?)
   Section break → replace with SectionDivider()
   List separator → replace with Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

2. grep -rn "Rectangle()\.fill(" ios/StockApp --include="*.swift" | grep -v ".git"
   For each hit: same context determination, same replacement.

verify phase H: grep -rn "Divider()" ios/StockApp → 0 results
               Zero plain gray dividers anywhere. All section breaks use SectionDivider().
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     FINAL VERIFICATION — ALL PHASES
     ═══════════════════════════════════════════════════════════════════════ -->

<final_verification>

AUTOMATED CHECKS — must all return zero before sign-off:

  grep -rn "Color(hex:"           ios/StockApp --include="*.swift" | grep -v ".git"  → 0
  grep -rn "\.system(size:"       ios/StockApp --include="*.swift" | grep -v Theme.swift → 0
  grep -rn "spacing: [0-9]"       ios/StockApp --include="*.swift" | grep -v Theme.swift → 0
  grep -rn "cornerRadius: [0-9]"  ios/StockApp --include="*.swift" | grep -v Theme.swift → 0
  grep -rn "Divider()"            ios/StockApp --include="*.swift" | grep -v ".git"  → 0
  grep -rn "GuillocheDivider()"   ios/StockApp --include="*.swift" | grep -v Theme.swift → 0
  grep -rn "\.foregroundColor("   ios/StockApp --include="*.swift" | grep -v ".git"  → 0
  xcodebuild -scheme stockme -configuration Debug clean build → BUILD SUCCEEDED, 0 errors

VISUAL CHECKS — open app on simulator, compare each screen to reference screenshots:

  [ ] Home:       Deep navy-black bg. Greeting + date + blue avatar. NIFTY hero card with mini chart.
                  3-chip index row. News cards with icon squares. Sector pills horizontal scroll.
  [ ] Watchlist:  "X instruments" + "Watchlist" header. Blue-family tile colors per ticker.
                  Smooth sparklines electric green/red. ChangeBadge with arrows.
  [ ] Portfolio:  Huge bold mono price. Two teal pills. Full-bleed glowing green chart.
                  Underline time selector. Donut + legend card. Holdings in single card.
  [ ] AI Detail:  Inline nav price+badge. Same chart. Confidence ring. 3×2 metric grid.
                  Numbered blue circle bullets. stripEmoji() on all AI text.
  [ ] Markets:    Electric blue active pill. SectionDivider between content.
  [ ] Settings:   Theme picker with electric blue checkmark. No aged-paper tones.

  [ ] Accent color is ELECTRIC BLUE (#5B90F6) everywhere — tabs, links, "See all", active states.
  [ ] Positive financial data is ELECTRIC TEAL-GREEN (#00C896) everywhere.
  [ ] Negative financial data is ELECTRIC RED (#FF4D4D) everywhere.
  [ ] Zero aged-paper, zero warm-brown, zero serif-heavy card surfaces anywhere.
  [ ] All cards: single 0.5pt border, Theme.canvasDeep background, soft deep shadow.
  [ ] All charts: glow line, gradient area fill, dark background, no chart framework UI chrome.

</final_verification>

<execution_order>
Run in order. Do not skip ahead. Each phase must pass its verify step before the next begins.

  Phase A — Color system replacement (Theme.swift + ThemeManager.swift)
  Phase B — Typography modernisation (.system(size:) sweep)
  Phase C — Component system (ChangeBadge, TimeRangeSelector, banknoteCard, SectionDivider)
  Phase D — Tab bar + navigation
  Phase E — Chart aesthetic (line style, sparklines, scrub interaction)
  Phase F — Screen-by-screen alignment (Watchlist, Portfolio, AI, Home, Settings, all others)
  Phase G — Spacing sweep (324 magic integers)
  Phase H — Divider sweep (99 Divider() + 23 Rectangle dividers)
  Final verification
</execution_order>

</system>
```
