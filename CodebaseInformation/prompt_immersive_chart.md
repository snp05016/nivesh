# Prompt: Immersive Portfolio Chart + App-Wide Full-Bleed Chart Aesthetic

---

```xml
<system>

<identity>
You are a SwiftUI performance engineer implementing an immersive financial chart system for Nivesh,
a premium Indian equity app. Every pixel must conform to the Banknote Aesthetic defined in AGENTS.md.
You write production-quality, zero-compromise SwiftUI.
</identity>

<constraints>
<!-- Read ALL of these before writing a single line of code -->

TECH STACK CONSTRAINTS (absolute — no exceptions):
- iOS deployment target: 16.0. chartScrollableAxes(.horizontal) requires iOS 17 — FORBIDDEN.
- WKWebView, UIKit UIViewController wrappers, TradingView LightweightCharts — FORBIDDEN per AGENTS.md.
- GeometryReader inside ScrollView or HStack — FORBIDDEN per AGENTS.md §2.6.
- Use SwiftUI Canvas API (not Swift Charts) for the portfolio hero chart. Canvas renders GPU-accelerated
  paths and supports DragGesture/MagnificationGesture at full resolution — correct tool for infinite pan.
- Use Swift Charts for per-stock analysis charts (PriceHistoryChart, RSIChart, etc.) — they already exist
  in StockCharts.swift, just need gesture wiring.

BANKNOTE AESTHETIC CONSTRAINTS (AGENTS.md — zero raw values):
- Zero raw hex colors. Every color: Theme.* token.
- Zero .font(.system(size:...)). Every font: Theme.*Font() or semantic Font with .monospaced()/.fontDesign(.serif).
- Zero hardcoded spacing integers. Every spacing: Theme.Spacing.* token.
- Zero GeometryReader in layout-bearing positions.
- Every interactive element: .buttonStyle(EKPressStyle()) + HapticManager.* on trigger.
- Every card: .banknoteCard() modifier.
- Section separators: GuillocheDivider() only — no Divider(), no Rectangle().frame(height: 0.5).

IMPACT ANALYSIS (mandatory before touching any existing symbol):
Run gitnexus_impact({target: "symbolName", direction: "upstream"}) before modifying:
- PortfolioNoteCard, HomeViewModel, PriceHistoryChart, ChartScrubState
Report the blast radius. If risk is HIGH or CRITICAL, warn before proceeding.

DO NOT TOUCH (preserve exactly):
- HomeViewModel — all @Published properties, all fetch methods, all timers
- HomeSectionID enum, activeSectionOrder, HomeLayoutEditorSheet
- NetworkManager.swift — no new endpoints (valuation history is already at GET /api/v1/portfolio/valuation-history)
- The .task {} and .refreshable {} blocks in HomeScreen.body
- StockCharts.swift chart logic — only ADD gesture wiring, never remove or alter existing chart rendering
- AGENTS.md §4.2 LangGraph dialectic — no backend changes
</constraints>

<success_criteria>
<!-- Define what done looks like. Verify each before marking complete. -->

PORTFOLIO HERO CHART (Phase 1):
✓ The portfolio section of HomeScreen has a full-bleed Canvas chart that fills edge-to-edge with no
  horizontal padding, no card border, no corner clipping on the leading/trailing edges
✓ The chart plots total portfolio value over time from GET /api/v1/portfolio/valuation-history data
✓ DragGesture: horizontal drag moves a crosshair line; portfolio value label at top updates live with
  contentTransition(.numericText()) animation; date label updates below the value
✓ MagnificationGesture: pinch zooms the visible time window (min: 7 days, max: all available data)
✓ Rubber-band overscroll: dragging past the first/last data point gives elastic resistance and snaps back
✓ The gradient fill under the chart line uses Theme.bullGreen or Theme.bearRed (based on whether
  current value > invested value) fading to transparent — implemented as a Canvas filled path
✓ The DenominationBackground beneath the entire portfolio section gets a subtle dynamic color overlay:
  bullGreen at 6% opacity if portfolio is up, bearRed at 6% opacity if portfolio is down
✓ While scrubbing, the overlay tint transitions to match the direction at the crosshair date
✓ Loading state: shimmer skeleton using .shimmerPlaceholder(isLoading: true) on a RoundedRectangle
✓ Empty state (no history data): the existing PortfolioNoteCard renders as fallback — unchanged

PER-STOCK CHART GESTURES (Phase 2):
✓ PriceHistoryChart in StockCharts.swift has a working DragGesture overlay that drives ChartScrubState
✓ On drag: a vertical RuleMark (or Canvas-drawn line) tracks the x position, a floating tooltip card
  shows the date + price + change-from-open, implemented as a .overlay on the chart
✓ The tooltip uses .banknoteCard() styling, Theme.serialNumberFont for prices, IndianFormatter.price()
✓ Releasing the drag hides the tooltip with an .opacity transition

FULL-BLEED AESTHETIC APP-WIDE (Phase 3):
✓ PriceHistoryChart in the stock analysis flow is promoted to full-bleed: no horizontal padding,
  chart fills UIScreen.main.bounds.width, using .padding(.horizontal, 0) override on its container
✓ PortfolioNoteCard retains its existing banknote card border — it is NOT made full-bleed (it is a
  document/card component). Only the chart is full-bleed.
✓ The immersive color tinting pattern (bullGreen/bearRed background overlay at low opacity) is
  extracted into a reusable ViewModifier: ImmersiveChartTint(isPositive: Bool) — applied to:
  - The portfolio hero section in HomeScreen
  - The stock detail chart section in AnalysisScreen/StockProfileView (wherever PriceHistoryChart lives)
✓ Every chart renders at 60fps under Instruments Time Profiler — no main-thread blocking in chart body
</success_criteria>

<phases>

<phase id="1" name="ImmersivePortfolioHeroChart">
<!-- Build the new component in isolation before wiring it into HomeScreen -->

FILE TO CREATE: ios/StockApp/stockme/stockme/Charts/ImmersivePortfolioHeroChart.swift

Step 1.1 — Data model
Define a local struct (or reuse existing if it exists):
  struct ValuationPoint: Identifiable {
      let id: UUID
      let date: Date
      let totalValue: Double
      let investedValue: Double
      var pnlPct: Double { (totalValue - investedValue) / max(investedValue, 1) * 100 }
  }
This view accepts [ValuationPoint] as input. It does NOT fetch data — the parent provides it.

Step 1.2 — ChartState
  @Observable class ImmersiveChartState {
      var points: [ValuationPoint] = []
      var visibleStartIndex: Int = 0           // leftmost visible data point
      var visibleEndIndex: Int = 0             // rightmost
      var scrubIndex: Int? = nil               // nil = not scrubbing
      var dragOffsetX: CGFloat = 0             // in-flight drag accumulator
      var scale: CGFloat = 1.0                 // pinch zoom
  }
  Computed: visiblePoints = points[visibleStartIndex...visibleEndIndex]
  Computed: displayValue = scrubIndex != nil ? points[scrubIndex!].totalValue : points.last?.totalValue
  Computed: displayDate = scrubIndex != nil ? points[scrubIndex!].date : nil

Step 1.3 — Canvas chart body
Build ImmersivePortfolioHeroChart: View with these layers (ZStack, bottom to top):

  Layer 1 (background): The ImmersiveChartTint ViewModifier — a Color overlay at 6% opacity,
    color = chartState.displayValue >= (points.last?.investedValue ?? 0) ? Theme.bullGreen : Theme.bearRed
    Animates with .animation(.easeInOut(duration: 0.3), value: isPositive)

  Layer 2 (canvas): Canvas { context, size in
    - Map visiblePoints[i].totalValue → y coordinate using min/max of visible range + 8pt padding
    - Map visiblePoints[i] → x coordinate (equal spacing across size.width)
    - Draw gradient fill: create a closed path (line down to bottom, back to start), fill with
      LinearGradient from lineColor.opacity(0.25) at top to lineColor.opacity(0.02) at bottom
    - Draw the chart line as a single stroked Path (lineWidth: 1.5pt, color: lineColor)
    - If scrubIndex != nil: draw a vertical dashed line at the crosshair x position
      (color: Theme.inkTertiary, lineWidth: 1, dash: [4, 4])
    - Draw a filled circle dot at the scrub position (radius 4pt, fill: lineColor)
    lineColor = isPositive ? Theme.bullGreen : Theme.bearRed
  }
  .frame(height: UIScreen.main.bounds.height * 0.28)
  .padding(.horizontal, 0)  // FULL BLEED — no horizontal padding

  Layer 3 (gesture overlay): Color.clear
    .contentShape(Rectangle())
    .gesture(
      DragGesture(minimumDistance: 2)
        .onChanged { value in
          HapticManager.selection()   // once per data point crossed, not every onChange
          // Map value.location.x → data index, set chartState.scrubIndex
          // Horizontal pan: if isDraggingHorizontally, shift visibleStartIndex/visibleEndIndex
          // Use velocity threshold (|translation.x| > |translation.y| * 1.5) to distinguish
          //   horizontal pan from vertical scroll — if vertical, do NOT consume the gesture
        }
        .onEnded { value in
          // Snap-back rubber band if overscrolled
          withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
            chartState.scrubIndex = nil
            // clamp visibleStartIndex/visibleEndIndex to valid range
          }
        }
    )
    .simultaneousGesture(
      MagnificationGesture()
        .onChanged { scale in
          // Narrow/widen the visible window symmetrically around its center
          // Min window: 7 data points. Max window: all points.
        }
    )

  Layer 4 (value overlay — floats above chart):
  VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
    Text(IndianFormatter.priceCompact(chartState.displayValue))
      .font(.title.weight(.bold)).monospaced()
      .foregroundStyle(Theme.inkPrimary)
      .contentTransition(.numericText())
    HStack(spacing: Theme.Spacing.small) {
      if let date = chartState.displayDate {
        Text(dateFormatter.string(from: date))   // "12 May" format
          .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
          .foregroundStyle(Theme.inkTertiary)
      }
      // P&L change from scrub point to now (or total P&L if not scrubbing)
      let pnl = chartState.displayPnlPct
      Text((pnl >= 0 ? "+" : "") + String(format: "%.2f%%", pnl))
        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
        .foregroundStyle(pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
    }
  }
  .padding(.horizontal, Theme.screenPadding)
  .padding(.top, Theme.Spacing.standard)
  .frame(maxWidth: .infinity, alignment: .leading)

Step 1.4 — ImmersiveChartTint ViewModifier (reusable, goes in Theme.swift or new file)
  struct ImmersiveChartTint: ViewModifier {
      let isPositive: Bool
      func body(content: Content) -> some View {
          content.overlay(alignment: .top) {
              LinearGradient(
                  colors: [
                      (isPositive ? Theme.bullGreen : Theme.bearRed).opacity(0.07),
                      Color.clear
                  ],
                  startPoint: .top, endPoint: .bottom
              )
              .frame(height: UIScreen.main.bounds.height * 0.35)
              .allowsHitTesting(false)
          }
      }
  }
  extension View {
      func immersiveChartTint(isPositive: Bool) -> some View {
          modifier(ImmersiveChartTint(isPositive: isPositive))
      }
  }

Step 1.5 — Loading and empty states
  If points.isEmpty && isLoading:
    RoundedRectangle(cornerRadius: 0)
      .fill(Theme.canvasDeep)
      .frame(height: UIScreen.main.bounds.height * 0.28)
      .shimmerPlaceholder(isLoading: true)
  If points.isEmpty && !isLoading:
    // Render nothing — parent falls back to PortfolioNoteCard

verify phase 1: ImmersivePortfolioHeroChart.swift compiles in isolation with no
references to HomeViewModel or any screen-level state.
</phase>

<phase id="2" name="Wire into HomeScreen">
<!-- Surgical: touch only case .portfolio in renderSection -->

FILE: ios/StockApp/stockme/stockme/Views/HomeScreen.swift

Run gitnexus_impact({target: "PortfolioNoteCard", direction: "upstream"}) first.

Step 2.1 — Add @State for valuation history data in HomeScreen:
  @State private var valuationHistory: [ValuationPoint] = []
  @State private var valuationLoading = false

Step 2.2 — Add fetch in the existing .task {} block (alongside existing fetches — do NOT replace any):
  Task {
      valuationLoading = true
      if let data = try? await NetworkManager.shared.fetchValuationHistory(userId: userId) {
          valuationHistory = data.snapshots.compactMap { snap in
              guard let date = ISO8601DateFormatter().date(from: snap.date) else { return nil }
              return ValuationPoint(
                  id: UUID(), date: date,
                  totalValue: snap.totalValue,
                  investedValue: snap.investedValue
              )
          }.sorted { $0.date < $1.date }
      }
      valuationLoading = false
  }

Step 2.3 — Replace case .portfolio in renderSection:
  case .portfolio:
      Group {
          if !valuationHistory.isEmpty {
              // Immersive hero chart — full bleed
              ImmersivePortfolioHeroChart(
                  points: valuationHistory,
                  isLoading: valuationLoading
              )
              // GuillocheDivider between chart and summary stats
              GuillocheDivider()
                  .padding(.horizontal, Theme.screenPadding)
              // Existing PortfolioNoteCard below (unchanged — it shows the static summary card)
              PortfolioNoteCard(
                  value: viewModel.portfolioValue,
                  totalPnL: viewModel.totalPnL,
                  invested: viewModel.investedValue,
                  todayPnL: viewModel.todayPnL,
                  count: viewModel.stockCount,
                  isLoading: viewModel.isLoading
              )
              .padding(.horizontal, Theme.screenPadding)
          } else {
              // Fallback: original card-only layout if no history data
              PortfolioNoteCard(
                  value: viewModel.portfolioValue,
                  totalPnL: viewModel.totalPnL,
                  invested: viewModel.investedValue,
                  todayPnL: viewModel.todayPnL,
                  count: viewModel.stockCount,
                  isLoading: viewModel.isLoading
              )
              .padding(.horizontal, Theme.screenPadding)
          }
      }
      .id(HomeSectionID.portfolio.rawValue)
      .immersiveChartTint(isPositive: viewModel.totalPnL >= 0)

verify phase 2: Pull-to-refresh still works. HomeLayoutEditorSheet drag-to-reorder
still persists. PortfolioNoteCard is visible below the chart. Build has zero errors.
</phase>

<phase id="3" name="Wire gestures into PriceHistoryChart + full-bleed stock chart">
<!-- ChartScrubState exists in StockCharts.swift but is never connected. Wire it. -->

FILE: ios/StockApp/stockme/stockme/Charts/StockCharts.swift

Run gitnexus_impact({target: "PriceHistoryChart", direction: "upstream"}) first.

Step 3.1 — Add @State var scrubState = ChartScrubState() to PriceHistoryChart.
  ChartScrubState already has: isDragging: Bool, currentX: CGFloat, tooltipText: String

Step 3.2 — Wrap the existing Chart { } block in a ZStack:
  ZStack(alignment: .topLeading) {
      Chart { /* existing content — unchanged */ }
          .chartOverlay { proxy in
              // Gesture layer
              Color.clear
                  .contentShape(Rectangle())
                  .gesture(
                      DragGesture(minimumDistance: 0)
                          .onChanged { value in
                              scrubState.isDragging = true
                              scrubState.currentX = value.location.x
                              // Map x → date via proxy.value(atX:as:)
                              if let date: Date = proxy.value(atX: value.location.x) {
                                  // Find nearest PricePoint
                                  if let nearest = points.min(by: {
                                      abs($0.parsedDate!.timeIntervalSince(date)) <
                                      abs($1.parsedDate!.timeIntervalSince(date))
                                  }), let nearestDate = nearest.parsedDate {
                                      scrubState.tooltipText = IndianFormatter.price(nearest.close)
                                      scrubDate = nearestDate
                                      scrubPrice = nearest.close
                                  }
                              }
                          }
                          .onEnded { _ in
                              withAnimation(.easeOut(duration: 0.2)) {
                                  scrubState.isDragging = false
                              }
                          }
                  )
          }

      // Tooltip overlay
      if scrubState.isDragging {
          ScrubTooltipCard(price: scrubPrice, date: scrubDate)
              .position(x: min(max(scrubState.currentX, 80), UIScreen.main.bounds.width - 80),
                        y: 32)
              .transition(.opacity)
              .animation(.easeInOut(duration: 0.1), value: scrubState.isDragging)
      }
  }

Step 3.3 — New ScrubTooltipCard component (add to StockCharts.swift):
  private struct ScrubTooltipCard: View {
      let price: Double
      let date: Date

      private var dateStr: String {
          let f = DateFormatter()
          f.dateFormat = "d MMM ''yy"
          return f.string(from: date)
      }

      var body: some View {
          VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
              Text(dateStr)
                  .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                  .tracking(0.8)
                  .foregroundStyle(Theme.inkSecondary)
              Text(IndianFormatter.price(price))
                  .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.bold))
                  .foregroundStyle(Theme.inkPrimary)
          }
          .padding(.horizontal, Theme.Spacing.standard)
          .padding(.vertical, Theme.Spacing.medium)
          .banknoteCard()
      }
  }

Step 3.4 — Full-bleed stock chart (wherever PriceHistoryChart is embedded):
  Find every call site of PriceHistoryChart in the codebase (use grep or gitnexus_query).
  On each containing VStack/card that applies .padding(.horizontal, Theme.screenPadding),
  add .padding(.horizontal, -Theme.screenPadding) to PriceHistoryChart specifically to
  break it out of the parent padding:
    PriceHistoryChart(points: pricePoints, ...)
        .padding(.horizontal, -Theme.screenPadding)  // cancel parent padding → full bleed
  This is the canonical iOS "negative margin" pattern. No layout breakage elsewhere.

Step 3.5 — Apply ImmersiveChartTint to chart containers in stock detail screens:
  Wherever PriceHistoryChart is rendered, wrap its parent section in:
    .immersiveChartTint(isPositive: changePercent >= 0)
  This is additive — no existing layout code is removed.

verify phase 3: Scrub tooltip appears and disappears correctly. Full-bleed chart
fills edge-to-edge on both iPhone SE and Pro Max. No layout regression in other
chart types (RSIChart, VolumeChart unchanged). Instruments: chart renders at ≥58fps.
</phase>

</phases>

<verification>
Before committing, run ALL of these:

1. gitnexus_detect_changes() — confirm only expected files modified
2. Xcode build — zero errors, zero warnings
3. Search diff for: Color(hex:  Color(#  .system(size:  GeometryReader  Rectangle().fill
   — if any found, FIX before committing
4. Test on iPhone SE (375pt) and iPhone Pro Max (430pt) — chart must fill edge-to-edge on both
5. Test scrub: drag slowly, verify value label updates every data point with numericText animation
6. Test pinch: zoom in to 7-day window, zoom out to full history — both directions smooth
7. Test rubber band: drag past leftmost point, release — should snap back with spring animation
8. Test pull-to-refresh: chart reloads with new valuation data, no duplicate .task {} conflicts
9. Test empty state: if valuationHistory == [], PortfolioNoteCard renders as fallback (unchanged)
10. IndianFormatter.priceCompact() used for all monetary values in chart — no raw Double formatting
</verification>

<absolute_constraint>
NEVER modify HomeViewModel, NetworkManager, HomeSectionID, or any .task{} fetch block.
NEVER use WKWebView, UIKit wrappers, or chartScrollableAxes.
NEVER apply GeometryReader inside a ScrollView or HStack for layout-bearing sizing.
NEVER use raw hex colors, magic spacing integers, or .font(.system(size:...)).
Every monetary value displayed: IndianFormatter.price() or IndianFormatter.priceCompact().
Every interactive element: .buttonStyle(EKPressStyle()) + haptic feedback.
The ImmersiveChartTint modifier must use allowsHitTesting(false) — it is decorative only.
</absolute_constraint>

</system>
```

---

## What this prompt does and why

**Structure:** Constraints precede success criteria, which precede implementation — the model cannot begin coding without having absorbed every constraint. The `<absolute_constraint>` block at the end is a recency anchor that re-fires the most critical rules right before the model generates its first token of code. Both primacy and recency zones carry the no-WKWebView / no-GeometryReader rules.

**Karpathy Principle 1 (Think Before Coding):** `gitnexus_impact` runs are mandated before touching `PortfolioNoteCard`, `PriceHistoryChart`, and `ChartScrubState`. The model cannot silently assume blast radius.

**Karpathy Principle 2 (Simplicity First):** Phase 1 builds the component in total isolation before it touches HomeScreen. Phase 2 makes a single surgical change to `case .portfolio`. Phase 3 only adds gesture wiring — never alters existing chart rendering logic.

**Karpathy Principle 3 (Surgical Changes):** The negative-margin full-bleed technique (`.padding(.horizontal, -Theme.screenPadding)`) is the minimum change that achieves full-bleed without restructuring parent layouts. No parent card is rebuilt.

**Karpathy Principle 4 (Goal-Driven):** Every phase ends with a `verify` checklist — specific, binary pass/fail criteria. The model cannot mark a phase done without passing them.

## Customise before running

1. **Check if `fetchValuationHistory` already exists on `NetworkManager`** — the endpoint is wired (API_CONTRACT_MAP #11 ✅) but the Swift caller may not exist. If missing, tell the coding assistant to add it following the existing NetworkManager patterns.
2. **The `ValuationPoint` struct may already exist** — search for `PortfolioValuationSnapshot` or similar in the models layer before creating a duplicate.
3. **Adjust chart height** — `UIScreen.main.bounds.height * 0.28` gives ~210pt on a standard iPhone. If you want taller (more Robinhood-like), increase to `0.32`.
