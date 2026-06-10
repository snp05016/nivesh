# NIVESH — MEGA UI OVERHAUL PROMPT
# Copy-paste this entire file into your coding assistant. Execute phases in order. Ship it.

---

```xml
<system>

<identity>
You are implementing the Nivesh Dark Immersive Redesign. The brief is simple: same Banknote DNA
(guilloche patterns, haptics, double-stroke cards, IndianFormatter throughout), upgraded to a
deep-dark premium aesthetic — think Bloomberg Terminal meets Robinhood's night mode. You write
production-quality SwiftUI. You do not hedge. You do not skip steps. You ship clean code.
</identity>

<non_negotiables>
<!-- Burn these into memory before writing a single line -->

ARCHITECTURE LAW (AGENTS.md — non-negotiable):
- Run gitnexus_impact({target: "symbolName", direction: "upstream"}) BEFORE touching ANY existing
  symbol. Report blast radius. STOP if risk is CRITICAL — warn the user before proceeding.
- Run gitnexus_detect_changes() before every commit. Only expected symbols in the diff.
- NEVER edit a symbol without impact analysis. No exceptions.

TECH CONSTRAINTS (absolute):
- iOS 16.0 deployment target. chartScrollableAxes — FORBIDDEN (iOS 17+).
- WKWebView, UIKit UIViewController wrappers, TradingView embeds — FORBIDDEN.
- GeometryReader inside ScrollView or HStack — FORBIDDEN. Use UIScreen.main.bounds.width instead.
- SwiftUI Canvas API for the portfolio hero chart (GPU-accelerated, gesture-compatible).
- Swift Charts for per-stock charts (PriceHistoryChart, RSIChart, etc. in StockCharts.swift).

BANKNOTE AESTHETIC (AGENTS.md §2 — zero raw values anywhere):
- Zero raw hex / Color(hex:) / Color(hue:) values. Every color: Theme.* token only.
- Zero .font(.system(size:...)). Every font: Theme.*Font() or semantic Font + .monospaced().
- Zero magic spacing integers. Every gap: Theme.Spacing.* token.
- Every card: .banknoteCard() modifier.
- Every interactive element: .buttonStyle(EKPressStyle()) + HapticManager.* on trigger.
- Section separators: GuillocheDivider() only. Never Divider(), never Rectangle().frame(height:).
- All monetary output: IndianFormatter.price() or IndianFormatter.priceCompact(). No "Million",
  no "Billion" — call _ban_western_scale() on every LLM text field.

DO NOT TOUCH (preserve exactly as-is):
- HomeViewModel — all @Published, all fetch methods, all timers
- HomeSectionID enum, activeSectionOrder, HomeLayoutEditorSheet
- The .task {} and .refreshable {} blocks in HomeScreen.body
- NetworkManager.swift — no new endpoints (valuation history exists at GET /api/v1/portfolio/valuation-history)
- StockCharts.swift chart rendering logic — only ADD gesture wiring on top, never alter existing
- AGENTS.md §4.2 LangGraph dialectic — zero backend changes
- feedVM: HomeFeedViewModel bindings, authManager, navigationPath
</non_negotiables>

<success_criteria>
<!-- These are your shipped = done criteria. Every checkbox must pass before you commit. -->

PHASE 0 — Dark Immersive Token Update:
✓ Theme.swift dark mode color values updated to the new deep-dark palette
✓ Light mode values unchanged (daytime users unaffected)
✓ Every view in the app picks up the new palette automatically via Token.* references
✓ Zero new raw hex values introduced — all changes are inside Theme.swift adaptive Color definitions

PHASE 1 — HomeScreen Violations Purged:
✓ No .foregroundStyle(.secondary) in news or YouTube section headers
✓ No Rectangle().fill(...).frame(height: 0.5) inside any card body
✓ No hardcoded cornerRadius: 16 — replaced with Theme.CornerRadius.card
✓ No magic spacing integers (10, 2, 14) — all Theme.Spacing.* tokens
✓ No Color(hue:saturation:brightness:) — replaced with Theme.holdAmber
✓ No GeometryReader inside ScrollView or HStack

PHASE 2 — Hidden Data Surfaced:
✓ MarketMoodGauge renders in .marketPulse section (it was built but never shown)
✓ MarketStatusStrip renders in .top section (NSE OPEN/CLOSED badge + IST time)
✓ Earnings rows show "WATCHLIST" badge for holdings in the user's watchlist
✓ A/D count labels ("247 Advancing / 183 Declining") appear below ADBreathBar
✓ Zero new network calls — all data from existing HomeViewModel properties

PHASE 3 — ImmersivePortfolioHeroChart Built:
✓ New file: ios/StockApp/stockme/stockme/Charts/ImmersivePortfolioHeroChart.swift
✓ Full-bleed Canvas chart (zero horizontal padding, edge-to-edge)
✓ DragGesture: crosshair + live value label with .contentTransition(.numericText())
✓ MagnificationGesture: pinch zoom (min 7 days, max full history)
✓ Rubber-band snap-back on overscroll
✓ Color fill under line: bullGreen if portfolio up, bearRed if down
✓ ImmersiveChartTint ViewModifier: section bg tints bullGreen/bearRed at 6% opacity
✓ Loading: shimmerPlaceholder skeleton. Empty: PortfolioNoteCard fallback (unchanged)

PHASE 4 — Chart Wired into HomeScreen:
✓ case .portfolio: hero chart above GuillocheDivider above existing PortfolioNoteCard
✓ Pull-to-refresh still works. HomeLayoutEditorSheet drag-to-reorder still persists.
✓ .immersiveChartTint(isPositive: viewModel.totalPnL >= 0) applied to portfolio section

PHASE 5 — PriceHistoryChart Gets Gestures:
✓ ChartScrubState connected to DragGesture via chartOverlay proxy
✓ ScrubTooltipCard floats above chart on drag, disappears on release
✓ PriceHistoryChart full-bleed via .padding(.horizontal, -Theme.screenPadding) at call sites
✓ .immersiveChartTint applied to stock detail chart containers
</success_criteria>

<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 0: DARK IMMERSIVE TOKEN UPDATE
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="0" name="DarkImmersiveTokenUpdate">

FILE: ios/StockApp/stockme/stockme/Utilities/Theme.swift

Run gitnexus_impact({target: "Theme", direction: "upstream"}) first.
This has maximum blast radius — every view inherits from Theme. That is the POINT.
All changes are dark-mode values only. Light mode stays unchanged.

Update the dark mode Color definitions (the second parameter in Color(light:dark:) or the
adaptive color initializer, whichever pattern Theme.swift uses internally) to these values:

  // Backgrounds — deep dark (charcoal-black, not blue-black)
  Theme.canvas          dark: #0A0A0F    // Main background — near black, slightly warm
  Theme.canvasDeep      dark: #131318    // Card surfaces — 1 step lighter than canvas
  Theme.canvasShadow    dark: #060609    // Pressed/inset states — deepest layer

  // Text — warm white hierarchy (not pure white — too harsh against deep dark)
  Theme.inkPrimary      dark: #F0EDE5    // Primary text — warm white
  Theme.inkSecondary    dark: #8A9A82    // Secondary text — sage, same family as current
  Theme.inkTertiary     dark: #4E5A4A    // Faded/disabled text

  // Accents — sharper, more electric than current warm gold
  Theme.securityGold      dark: #D4A817  // Primary accent — electric amber
  Theme.securityGoldLight dark: #E8C040  // Lighter highlight

  // Directional — vivid, high-contrast against deep dark
  Theme.bullGreen       dark: #00C896    // Positive returns — electric teal-green
  Theme.bullGreenLight  dark: #0E2A1C    // Positive background tint
  Theme.bearRed         dark: #FF4444    // Negative returns — vivid red
  Theme.bearRedLight    dark: #2A0E0E    // Negative background tint
  Theme.holdAmber       dark: #D4A217    // Neutral/hold

  // Borders — very subtle at dark backgrounds
  Theme.borderFine      dark: white at 6% opacity   // Subtle card border
  Theme.borderSage      dark: #8A9A82 at 12% opacity // Card borders

These are drop-in replacements. Token NAMES stay identical. Every .foregroundStyle(Theme.bullGreen),
every .background(Theme.canvasDeep), every .fill(Theme.bearRed) in the entire codebase automatically
picks up the new values in dark mode without a single other file change.

verify phase 0: Build the app in dark mode. Every screen should show a deep-dark premium aesthetic.
No raw colors introduced. gitnexus_detect_changes() shows ONLY Theme.swift modified.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 1: PURGE ALL AGENTS.md VIOLATIONS IN HomeScreen.swift
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="1" name="HomeScreenViolationsPurged">

FILE: ios/StockApp/stockme/stockme/Views/HomeScreen.swift

Run gitnexus_impact({target: "HomeScreen", direction: "upstream"}) first.

--- FIX 1.1: .foregroundStyle(.secondary) in news and YouTube headers ---

Location: renderSection(id:) extension, case .news (~line 2460) and case .youtube (~line 2553)

Both headers use the forbidden .foregroundStyle(.secondary) system color. Replace BOTH
with the bilingual SectionHeader pattern used in every other section. Remove the manually
placed GuillocheDivider() after each header — SectionHeader already handles its own styling.

WRONG (both sections have this pattern):
  VStack(alignment: .leading, spacing: 2) {
      Text("ताज़ा समाचार").font(.caption2).foregroundStyle(.secondary)
      Text("MARKET NEWS").font(.caption.weight(.semibold)).monospaced().tracking(2.0).foregroundStyle(.secondary)
  }
  .padding(.bottom, Theme.Spacing.standard).padding(.horizontal, Theme.screenPadding)
  GuillocheDivider().padding(.horizontal, Theme.screenPadding).padding(.bottom, Theme.Spacing.standard)

CORRECT for case .news:
  SectionHeader(title: "Market News", hindiTitle: "ताज़ा समाचार")
      .padding(.horizontal, Theme.screenPadding)

CORRECT for case .youtube:
  SectionHeader(title: "Expert Videos", hindiTitle: "विशेषज्ञ विश्लेषण")
      .padding(.horizontal, Theme.screenPadding)


--- FIX 1.2: Rectangle() thin-rule dividers inside card bodies ---

Locations:
  - MarketPulseDashCard (~line 1291): Rectangle().fill(Color.primary.opacity(0.08)).frame(height: 0.5)
  - MacroDashCard (~line 1462): same pattern

WRONG:
  Rectangle().fill(Color.primary.opacity(0.08)).frame(height: 0.5).padding(.horizontal, cardHPad).padding(.vertical, Theme.Spacing.standard)

CORRECT (inside cards, not between page sections — Divider, not GuillocheDivider):
  Divider().opacity(0.08).padding(.horizontal, cardHPad).padding(.vertical, Theme.Spacing.standard)


--- FIX 1.3: Hardcoded cornerRadius in InstitutionalDashCard ---

Location: InstitutionalDashCard (~line 2255)

WRONG:
  .clipShape(RoundedRectangle(cornerRadius: 16))
  .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.borderFine, lineWidth: 0.5))

CORRECT:
  .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
  .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderFine, lineWidth: 0.5))


--- FIX 1.4: Magic spacing integers ---

Fix every one of these in-place, no exceptions:

  DashboardSection VStack (~line 2215):          spacing: 10           → spacing: Theme.Spacing.standard
  TimeframeConflictsBanner HStack (~line 1153):  spacing: 10           → spacing: Theme.Spacing.standard
  MomentumDashCard Spacer (~line 1378):          .frame(height: 10)    → .frame(height: Theme.Spacing.standard)
  MarketMoodGauge VStack (~line 1515):           spacing: 10           → spacing: Theme.Spacing.standard
  MarketPulseDashCard header VStack (~line 1266): spacing: 2           → spacing: Theme.Spacing.xSmall
  MomentumDashCard header VStack (~line 1350):   spacing: 2            → spacing: Theme.Spacing.xSmall


--- FIX 1.5: Raw color in CompactNewsCell signal badge ---

Location: CompactNewsCell.signalBadge (~line 1746)

WRONG:
  if age < 2 * 3600 { return ("HOT", "flame.fill", Color(hue: 0.05, saturation: 0.9, brightness: 0.95)) }

CORRECT:
  if age < 2 * 3600 { return ("HOT", "flame.fill", Theme.holdAmber) }


--- FIX 1.6: GeometryReader inside ScrollView/HStack ---

IndexCardView (~line 1605) — card is inside a horizontal ScrollView → HStack:

WRONG:
  var body: some View {
      GeometryReader { idxGeo in
          VStack(alignment: .leading, spacing: Theme.Spacing.medium) { ... }
          .frame(width: idxGeo.size.width * 0.35).banknoteCard()
      }
  }

CORRECT:
  var body: some View {
      VStack(alignment: .leading, spacing: Theme.Spacing.medium) { ... }
      .frame(width: UIScreen.main.bounds.width * 0.32).banknoteCard()
  }

MomentumRowView (~line 1652) — sparkline inside a list item:

WRONG:
  var body: some View {
      GeometryReader { momGeo in
          HStack(spacing: Theme.Spacing.standard) {
              ...
              SparklineView(values: ticker.sparkline, color: signalColor)
                  .frame(width: momGeo.size.width * 0.14, height: momGeo.size.width * 0.08)
          }.padding(...)
      }
  }

CORRECT:
  var body: some View {
      HStack(spacing: Theme.Spacing.standard) {
          ...
          if !ticker.sparkline.isEmpty {
              SparklineView(values: ticker.sparkline, color: signalColor)
                  .frame(width: 48, height: 28)
          }
      }
      .padding(.horizontal, Theme.Spacing.standard)
      .padding(.vertical, Theme.Spacing.standard)
  }

verify phase 1: grep the diff for: Rectangle().fill  Color(hue:  .secondary  GeometryReader
spacing: 10  spacing: 2  cornerRadius: 16  — ZERO hits. Build: zero errors, zero warnings.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 2: SURFACE HIDDEN DATA (no new network calls)
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="2" name="SurfaceHiddenData">

FILE: ios/StockApp/stockme/stockme/Views/HomeScreen.swift

All data referenced below is ALREADY in HomeViewModel or feedVM. Zero new endpoints.


--- 2.1: MarketMoodGauge — it exists, it's never rendered. Fix that. ---

MarketMoodGauge is fully implemented at line 1492. It has never been added to renderSection.
Add it to case .marketPulse, below MarketPulseDashCard.

Also remove the DashboardSection wrapper from .marketPulse, .momentum, .macroAlt, and
.institutional — these cards already have their own SecurityThread + GuillocheDivider + bilingual
headers baked in. The DashboardSection wrapper creates a duplicate header. Kill it.

Replace case .marketPulse:
  case .marketPulse:
      VStack(spacing: Theme.Spacing.standard) {
          if let pulse = viewModel.dashboard?.pulse {
              MarketPulseDashCard(pulse: pulse)
              if pulse.advances + pulse.declines > 0 {
                  let ratio = Double(pulse.advances) / Double(pulse.advances + pulse.declines)
                  MarketMoodGauge(ratio: ratio)
              }
          } else {
              DashboardLoadingCard(label: "Market Pulse", isLoading: viewModel.dashboardLoading)
          }
      }
      .padding(.horizontal, Theme.screenPadding)
      .id(HomeSectionID.marketPulse.rawValue)

Apply the same DashboardSection removal pattern to case .momentum, case .macroAlt, case .institutional
(wrap with VStack + padding + .id — the inner cards provide their own headers):

  case .momentum:
      VStack {
          if let momentum = viewModel.dashboard?.momentum { MomentumDashCard(momentum: momentum) }
          else { DashboardLoadingCard(label: "Momentum Scan", isLoading: viewModel.dashboardLoading) }
      }
      .padding(.horizontal, Theme.screenPadding).id(HomeSectionID.momentum.rawValue)

  case .macroAlt:
      VStack {
          if let macro = viewModel.dashboard?.macro { MacroDashCard(macro: macro) }
          else { DashboardLoadingCard(label: "Macro Data", isLoading: viewModel.dashboardLoading) }
      }
      .padding(.horizontal, Theme.screenPadding).id(HomeSectionID.macroAlt.rawValue)

  case .institutional:
      VStack {
          if let inst = viewModel.dashboard?.institutional { InstitutionalDashCard(flow: inst) }
          else { DashboardLoadingCard(label: "Institutional Flow", isLoading: viewModel.dashboardLoading) }
      }
      .padding(.horizontal, Theme.screenPadding).id(HomeSectionID.institutional.rawValue)


--- 2.2: MarketStatusStrip — NSE open/closed badge + IST time in the .top section ---

Add this private struct before the renderSection extension. Pure computed property, zero network:

  private struct MarketStatusStrip: View {
      private var isMarketOpen: Bool {
          let cal = Calendar(identifier: .gregorian)
          let comps = cal.dateComponents(in: TimeZone(identifier: "Asia/Kolkata")!, from: Date())
          guard let weekday = comps.weekday, weekday != 1, weekday != 7 else { return false }
          let total = (comps.hour ?? 0) * 60 + (comps.minute ?? 0)
          return total >= 555 && total < 930  // 9:15–15:30 IST
      }
      private var statusLabel: String { isMarketOpen ? "NSE OPEN" : "NSE CLOSED" }
      private var statusColor: Color { isMarketOpen ? Theme.bullGreen : Theme.bearRed }
      private var istTimeString: String {
          let f = DateFormatter()
          f.timeZone = TimeZone(identifier: "Asia/Kolkata")
          f.dateFormat = "EEE, d MMM · HH:mm IST"
          return f.string(from: Date()).uppercased()
      }
      var body: some View {
          HStack(spacing: Theme.Spacing.standard) {
              HStack(spacing: Theme.Spacing.small) {
                  Circle().fill(statusColor).frame(width: 6, height: 6)
                  Text(statusLabel)
                      .font(Theme.officialStampFont(size: 9)).tracking(1.2).foregroundStyle(statusColor)
              }
              .padding(.horizontal, Theme.Spacing.standard).padding(.vertical, Theme.Spacing.medium)
              .background(statusColor.opacity(0.08))
              .cornerRadius(Theme.CornerRadius.small)
              .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                  .stroke(statusColor.opacity(0.25), lineWidth: 0.5))
              Text(istTimeString)
                  .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                  .foregroundStyle(Theme.inkTertiary)
              Spacer()
          }
          .padding(.horizontal, Theme.screenPadding).padding(.bottom, Theme.Spacing.small)
      }
  }

In case .top, insert MarketStatusStrip() between the branding HStack and the Quick Nav ScrollView:

  case .top:
      Group {
          if let user = authManager.currentUser {
              HStack { /* existing branding + avatar — DO NOT CHANGE */ }
                  .padding(.horizontal, Theme.screenPadding).padding(.top, Theme.Spacing.standard)
          }
          MarketStatusStrip()          // ← NEW
          ScrollView(.horizontal) { /* existing Quick Nav — DO NOT CHANGE */ }
          if let action = dailyAction { /* existing DailyActionCard — DO NOT CHANGE */ }
      }
      .id(HomeSectionID.top.rawValue)


--- 2.3: Earnings section — WATCHLIST badge on holdings ---

In case .earnings ForEach loop, add a "WATCHLIST" badge next to the ticker if it's in the watchlist:

  HStack(spacing: Theme.Spacing.small) {
      Text(event.ticker)
          .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
      if viewModel.watchlist.contains(where: { $0.ticker == event.ticker }) {
          Text("WATCHLIST")
              .font(Theme.officialStampFont(size: 7)).tracking(0.8)
              .foregroundStyle(Theme.securityGold)
              .padding(.horizontal, Theme.Spacing.small).padding(.vertical, Theme.Spacing.xSmall)
              .background(Theme.securityGold.opacity(0.12))
              .cornerRadius(Theme.CornerRadius.small)
              .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                  .stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
      }
  }


--- 2.4: A/D count labels below ADBreathBar in MarketPulseDashCard ---

After the ADBreathBar(advancing: pulse.advances, declining: pulse.declines) call, add:

  HStack {
      HStack(spacing: Theme.Spacing.xSmall) {
          Image(systemName: "arrow.up").font(.caption2.weight(.bold)).foregroundStyle(Theme.bullGreen)
          Text("\(pulse.advances) Advancing")
              .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2)).foregroundStyle(Theme.bullGreen)
      }
      Spacer()
      HStack(spacing: Theme.Spacing.xSmall) {
          Text("\(pulse.declines) Declining")
              .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2)).foregroundStyle(Theme.bearRed)
          Image(systemName: "arrow.down").font(.caption2.weight(.bold)).foregroundStyle(Theme.bearRed)
      }
  }
  .padding(.horizontal, cardHPad).padding(.top, Theme.Spacing.xSmall).padding(.bottom, Theme.Spacing.small)


--- 2.5: Watchlist empty state — upgrade from plain text to a card ---

In case .watchlist, replace the existing plain-text empty state with:

  VStack(spacing: Theme.Spacing.card) {
      Image(systemName: "binoculars").font(.largeTitle.weight(.light))
          .foregroundStyle(Theme.inkTertiary.opacity(0.4))
      Text("NO STOCKS ON WATCHLIST")
          .font(Theme.officialStampFont(size: 11)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
      Text("Add stocks from Search to track them here.")
          .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
          .foregroundStyle(Theme.inkSecondary).multilineTextAlignment(.center)
  }
  .frame(maxWidth: .infinity).padding(.vertical, Theme.Spacing.xLarge).padding(.horizontal, Theme.screenPadding)

verify phase 2: MarketMoodGauge visible in marketPulse. MarketStatusStrip visible in header.
Earnings with watchlist tickers show the gold "WATCHLIST" badge. A/D counts visible below breath bar.
No new @StateObject, no new .task {} blocks, no new network calls.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 3: BUILD ImmersivePortfolioHeroChart (new file, isolated)
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="3" name="BuildImmersivePortfolioHeroChart">

FILE TO CREATE: ios/StockApp/stockme/stockme/Charts/ImmersivePortfolioHeroChart.swift

Build this component in total isolation. Zero references to HomeViewModel, HomeScreen,
or any screen-level state. It is a pure data-in, pixels-out component.


--- Step 3.1: Data model ---

  struct ValuationPoint: Identifiable {
      let id: UUID
      let date: Date
      let totalValue: Double
      let investedValue: Double
      var pnlPct: Double { (totalValue - investedValue) / max(investedValue, 1) * 100 }
  }

Search the codebase for PortfolioValuationSnapshot or similar before creating this —
if it already exists and carries date/totalValue/investedValue, reuse it.


--- Step 3.2: Chart state ---

  @Observable class ImmersiveChartState {
      var points: [ValuationPoint] = []
      var visibleStartIndex: Int = 0
      var visibleEndIndex: Int = 0
      var scrubIndex: Int? = nil
      var dragOffsetX: CGFloat = 0
      var scale: CGFloat = 1.0

      var visiblePoints: ArraySlice<ValuationPoint> { points[visibleStartIndex...visibleEndIndex] }
      var displayValue: Double { scrubIndex.map { points[$0].totalValue } ?? points.last?.totalValue ?? 0 }
      var displayDate: Date? { scrubIndex.map { points[$0].date } }
      var isPositive: Bool { (points.last?.totalValue ?? 0) >= (points.last?.investedValue ?? 1) }
      var displayPnlPct: Double {
          guard let idx = scrubIndex else { return points.last?.pnlPct ?? 0 }
          return points[idx].pnlPct
      }
  }


--- Step 3.3: Canvas chart layers (ZStack, bottom → top) ---

Layer 1 — ImmersiveChartTint background overlay (see Step 3.5 for the modifier definition):
  Color.clear
      .immersiveChartTint(isPositive: chartState.isPositive)

Layer 2 — Canvas drawing:
  Canvas { context, size in
      let vp = Array(chartState.visiblePoints)
      guard vp.count > 1 else { return }
      let mn = vp.map(\.totalValue).min()!, mx = vp.map(\.totalValue).max()!
      let rng = max(mx - mn, 1)
      let pad: CGFloat = 12
      let lineColor = chartState.isPositive ? Theme.bullGreen : Theme.bearRed

      func xFor(_ i: Int) -> CGFloat { CGFloat(i) / CGFloat(vp.count - 1) * size.width }
      func yFor(_ v: Double) -> CGFloat { pad + CGFloat((mx - v) / rng) * (size.height - 2 * pad) }

      // Gradient fill path
      var fillPath = Path()
      fillPath.move(to: CGPoint(x: 0, y: size.height))
      for (i, pt) in vp.enumerated() { fillPath.addLine(to: CGPoint(x: xFor(i), y: yFor(pt.totalValue))) }
      fillPath.addLine(to: CGPoint(x: size.width, y: size.height))
      fillPath.closeSubpath()
      context.fill(fillPath, with: .color(lineColor.opacity(0.18)))

      // Chart line
      var linePath = Path()
      for (i, pt) in vp.enumerated() {
          let p = CGPoint(x: xFor(i), y: yFor(pt.totalValue))
          i == 0 ? linePath.move(to: p) : linePath.addLine(to: p)
      }
      context.stroke(linePath, with: .color(lineColor), style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))

      // Crosshair (when scrubbing)
      if let si = chartState.scrubIndex {
          let cx = xFor(si - chartState.visibleStartIndex)
          let cy = yFor(chartState.points[si].totalValue)
          var crosshair = Path()
          crosshair.move(to: CGPoint(x: cx, y: 0)); crosshair.addLine(to: CGPoint(x: cx, y: size.height))
          context.stroke(crosshair, with: .color(Theme.inkTertiary),
                         style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
          context.fill(Path(ellipseIn: CGRect(x: cx - 4, y: cy - 4, width: 8, height: 8)),
                       with: .color(lineColor))
      }
  }
  .frame(height: UIScreen.main.bounds.height * 0.28)
  .padding(.horizontal, 0)  // FULL BLEED — no horizontal padding, ever

Layer 3 — Gesture overlay:
  Color.clear
      .contentShape(Rectangle())
      .gesture(
          DragGesture(minimumDistance: 2)
              .onChanged { [self] value in
                  let vp = Array(chartState.visiblePoints)
                  guard !vp.isEmpty else { return }
                  let idx = min(max(Int(value.location.x / UIScreen.main.bounds.width * CGFloat(vp.count)), 0), vp.count - 1)
                  let globalIdx = chartState.visibleStartIndex + idx
                  if chartState.scrubIndex != globalIdx {
                      HapticManager.selection()
                      chartState.scrubIndex = globalIdx
                  }
              }
              .onEnded { _ in
                  withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                      chartState.scrubIndex = nil
                  }
              }
      )
      .simultaneousGesture(
          MagnificationGesture()
              .onChanged { scale in
                  let center = (chartState.visibleStartIndex + chartState.visibleEndIndex) / 2
                  let currentWindow = chartState.visibleEndIndex - chartState.visibleStartIndex
                  let newWindow = max(7, min(chartState.points.count - 1, Int(CGFloat(currentWindow) / scale)))
                  chartState.visibleStartIndex = max(0, center - newWindow / 2)
                  chartState.visibleEndIndex = min(chartState.points.count - 1, center + newWindow / 2)
              }
      )

Layer 4 — Value/date overlay (floats top-leading above the chart):
  VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
      Text(IndianFormatter.priceCompact(chartState.displayValue))
          .font(.title.weight(.bold)).monospaced().foregroundStyle(Theme.inkPrimary)
          .contentTransition(.numericText())
          .animation(.easeInOut(duration: 0.05), value: chartState.displayValue)
      HStack(spacing: Theme.Spacing.small) {
          if let d = chartState.displayDate {
              Text(DateFormatter().then { $0.dateFormat = "d MMM ''yy" }.string(from: d))
                  .font(Theme.serialNumberFont(size: 11, relativeTo: .caption)).foregroundStyle(Theme.inkTertiary)
          }
          let pnl = chartState.displayPnlPct
          Text((pnl >= 0 ? "+" : "") + String(format: "%.2f%%", pnl))
              .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
              .foregroundStyle(pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
      }
  }
  .padding(.horizontal, Theme.screenPadding).padding(.top, Theme.Spacing.standard)
  .frame(maxWidth: .infinity, alignment: .leading)
  .allowsHitTesting(false)


--- Step 3.4: Loading and empty states ---

  if points.isEmpty && isLoading {
      RoundedRectangle(cornerRadius: 0)
          .fill(Theme.canvasDeep)
          .frame(height: UIScreen.main.bounds.height * 0.28)
          .shimmerPlaceholder(isLoading: true)
  }
  // If points.isEmpty && !isLoading → render nothing, parent renders PortfolioNoteCard fallback


--- Step 3.5: ImmersiveChartTint ViewModifier ---

Add to Theme.swift or a new ThemeModifiers.swift file:

  struct ImmersiveChartTint: ViewModifier {
      let isPositive: Bool
      func body(content: Content) -> some View {
          content.overlay(alignment: .top) {
              (isPositive ? Theme.bullGreen : Theme.bearRed).opacity(0.07)
                  .frame(height: UIScreen.main.bounds.height * 0.35)
                  .allowsHitTesting(false)
                  .animation(.easeInOut(duration: 0.3), value: isPositive)
          }
      }
  }
  extension View {
      func immersiveChartTint(isPositive: Bool) -> some View {
          modifier(ImmersiveChartTint(isPositive: isPositive))
      }
  }

verify phase 3: ImmersivePortfolioHeroChart.swift compiles in isolation.
Zero references to HomeViewModel or any screen. DragGesture drives crosshair.
MagnificationGesture zooms window. ImmersiveChartTint modifier visible in both build targets.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 4: WIRE CHART INTO HomeScreen (one surgical case change)
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="4" name="WireChartIntoHomeScreen">

FILE: ios/StockApp/stockme/stockme/Views/HomeScreen.swift

Run gitnexus_impact({target: "PortfolioNoteCard", direction: "upstream"}) first.

--- Step 4.1: Add two @State vars at the top of HomeScreen ---

  @State private var valuationHistory: [ValuationPoint] = []
  @State private var valuationLoading = false

--- Step 4.2: Add fetch inside existing .task {} block (add alongside, do NOT replace anything) ---

  Task {
      valuationLoading = true
      if let data = try? await NetworkManager.shared.fetchValuationHistory(userId: userId) {
          valuationHistory = data.snapshots.compactMap { snap in
              guard let date = ISO8601DateFormatter().date(from: snap.date) else { return nil }
              return ValuationPoint(id: UUID(), date: date,
                                   totalValue: snap.totalValue, investedValue: snap.investedValue)
          }.sorted { $0.date < $1.date }
      }
      valuationLoading = false
  }

If NetworkManager.fetchValuationHistory does not yet exist, add it following the existing
NetworkManager patterns — GET /api/v1/portfolio/valuation-history, decode to the matching
response model. Check the network layer before adding to avoid duplicates.

--- Step 4.3: Replace ONLY case .portfolio in renderSection --- 

  case .portfolio:
      Group {
          if !valuationHistory.isEmpty {
              ImmersivePortfolioHeroChart(points: valuationHistory, isLoading: valuationLoading)
              GuillocheDivider().padding(.horizontal, Theme.screenPadding)
              PortfolioNoteCard(
                  value: viewModel.portfolioValue, totalPnL: viewModel.totalPnL,
                  invested: viewModel.investedValue, todayPnL: viewModel.todayPnL,
                  count: viewModel.stockCount, isLoading: viewModel.isLoading
              )
              .padding(.horizontal, Theme.screenPadding)
          } else {
              PortfolioNoteCard(
                  value: viewModel.portfolioValue, totalPnL: viewModel.totalPnL,
                  invested: viewModel.investedValue, todayPnL: viewModel.todayPnL,
                  count: viewModel.stockCount, isLoading: viewModel.isLoading
              )
              .padding(.horizontal, Theme.screenPadding)
          }
      }
      .id(HomeSectionID.portfolio.rawValue)
      .immersiveChartTint(isPositive: viewModel.totalPnL >= 0)

verify phase 4: Pull-to-refresh triggers chart reload. HomeLayoutEditorSheet drag-to-reorder
still persists correctly. PortfolioNoteCard visible below chart. Build: zero errors.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 5: WIRE GESTURES INTO PriceHistoryChart
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="5" name="PriceHistoryChartGesturesAndFullBleed">

FILE: ios/StockApp/stockme/stockme/Charts/StockCharts.swift

Run gitnexus_impact({target: "PriceHistoryChart", direction: "upstream"}) first.

--- Step 5.1: Add @State vars to PriceHistoryChart ---

  @State private var scrubState = ChartScrubState()
  @State private var scrubPrice: Double = 0
  @State private var scrubDate: Date = Date()

ChartScrubState is already defined in this file: isDragging, currentX, tooltipText.

--- Step 5.2: Wrap the existing Chart { } in a ZStack, add gesture overlay ---

  ZStack(alignment: .topLeading) {
      Chart { /* existing content — DO NOT TOUCH */ }
          .chartOverlay { proxy in
              Color.clear
                  .contentShape(Rectangle())
                  .gesture(
                      DragGesture(minimumDistance: 0)
                          .onChanged { value in
                              scrubState.isDragging = true
                              scrubState.currentX = value.location.x
                              if let date: Date = proxy.value(atX: value.location.x),
                                 let nearest = points.min(by: {
                                     abs(($0.parsedDate?.timeIntervalSince(date) ?? .infinity)) <
                                     abs(($1.parsedDate?.timeIntervalSince(date) ?? .infinity))
                                 }), let nd = nearest.parsedDate {
                                  scrubState.tooltipText = IndianFormatter.price(nearest.close)
                                  scrubDate = nd
                                  scrubPrice = nearest.close
                              }
                          }
                          .onEnded { _ in
                              withAnimation(.easeOut(duration: 0.2)) { scrubState.isDragging = false }
                          }
                  )
          }

      if scrubState.isDragging {
          ScrubTooltipCard(price: scrubPrice, date: scrubDate)
              .position(x: min(max(scrubState.currentX, 80), UIScreen.main.bounds.width - 80), y: 32)
              .transition(.opacity)
              .animation(.easeInOut(duration: 0.1), value: scrubState.isDragging)
      }
  }

--- Step 5.3: New ScrubTooltipCard (add to StockCharts.swift) ---

  private struct ScrubTooltipCard: View {
      let price: Double
      let date: Date
      private var dateStr: String {
          let f = DateFormatter(); f.dateFormat = "d MMM ''yy"; return f.string(from: date)
      }
      var body: some View {
          VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
              Text(dateStr)
                  .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                  .tracking(0.8).foregroundStyle(Theme.inkSecondary)
              Text(IndianFormatter.price(price))
                  .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.bold))
                  .foregroundStyle(Theme.inkPrimary)
          }
          .padding(.horizontal, Theme.Spacing.standard).padding(.vertical, Theme.Spacing.medium)
          .banknoteCard()
      }
  }

--- Step 5.4: Full-bleed PriceHistoryChart at every call site ---

Grep the codebase for "PriceHistoryChart(" — find every call site.
On each one, break out of the parent's horizontal padding using the negative-margin pattern:

  PriceHistoryChart(points: pricePoints, ...)
      .padding(.horizontal, -Theme.screenPadding)   // cancel parent → full bleed

This is additive. Nothing is removed from parent layouts.

--- Step 5.5: Apply ImmersiveChartTint at stock detail chart containers ---

Wherever PriceHistoryChart is rendered, wrap its parent section container with:
  .immersiveChartTint(isPositive: changePercent >= 0)

This is decoration-only (.allowsHitTesting(false)) — no layout impact.

verify phase 5: Scrub tooltip appears on drag and hides on release.
Chart fills edge-to-edge on iPhone SE (375pt) AND Pro Max (430pt).
RSIChart, VolumeChart, ShareholdingChart — all unchanged, no regression.
Instruments Time Profiler: chart renders at ≥58fps on a real device.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     FINAL VERIFICATION — ALL PHASES COMPLETE
     ═══════════════════════════════════════════════════════════════════════ -->

<final_verification>
Run ALL of these before closing the PR. Every item must be a clean pass:

STATIC ANALYSIS — grep the diff, expect zero hits:
  Color(hex:        Color(hue:       .foregroundStyle(.secondary)
  .font(.system(    GeometryReader   Rectangle().fill
  spacing: 10       spacing: 2       cornerRadius: 16
  "Million"         "Billion"        "Trillion"

GITNEXUS:
  [ ] gitnexus_detect_changes() — only Theme.swift, HomeScreen.swift,
      StockCharts.swift, ImmersivePortfolioHeroChart.swift (new) in diff

BUILD:
  [ ] Xcode build: zero errors, zero warnings, zero SwiftUI runtime warnings in console

DEVICE TESTS:
  [ ] Dark mode: every screen shows the new deep-dark palette
  [ ] Light mode: no visual regression
  [ ] iPhone SE (375pt): chart edge-to-edge, no clipping
  [ ] iPhone Pro Max (430pt): chart edge-to-edge, no overflow
  [ ] MarketMoodGauge visible in market pulse section
  [ ] MarketStatusStrip visible in dashboard header
  [ ] Portfolio chart drag: value updates live on every data point crossed
  [ ] Portfolio chart pinch: smooth zoom between 7-day and full-history window
  [ ] Portfolio chart rubber-band: overscroll snaps back with spring animation
  [ ] Pull-to-refresh: chart reloads, no duplicate task conflicts
  [ ] Empty state (valuationHistory == []): PortfolioNoteCard renders alone (fallback)
  [ ] HomeLayoutEditorSheet: drag-to-reorder sections still persists correctly
  [ ] watchlist earnings badges show on correct tickers
  [ ] A/D count labels visible below ADBreathBar
  [ ] Scrub tooltip: appears on stock chart drag, disappears on release
  [ ] All monetary values use IndianFormatter — no raw Double.formatted() or String(format:)

PERFORMANCE:
  [ ] Instruments: ImmersivePortfolioHeroChart renders at ≥58fps on device (not simulator)
  [ ] No main-thread blocking: chart body contains zero synchronous I/O or heavy computation
</final_verification>

<absolute_constraint>
<!-- Recency anchor — re-read this before generating your first token of code -->

NEVER modify HomeViewModel, NetworkManager, HomeSectionID, or any .task{} fetch block.
NEVER use WKWebView, UIKit wrappers, or chartScrollableAxes (iOS 17+ forbidden).
NEVER put GeometryReader inside a ScrollView or HStack for layout-bearing sizing.
NEVER use raw hex colors, magic spacing integers, or .font(.system(size:...)).
NEVER display money without IndianFormatter. NEVER output "Million" or "Billion".
EVERY interactive element needs .buttonStyle(EKPressStyle()) + haptic feedback.
EVERY card needs .banknoteCard(). EVERY section separator is GuillocheDivider().
ImmersiveChartTint MUST use .allowsHitTesting(false) — it is visual decoration only.
Run gitnexus_impact before touching ANY existing symbol. Report blast radius. No exceptions.
</absolute_constraint>

</system>
```
