# NIVESH — FEATURES BATCH PROMPT
# 8 phases. Execute in order. Each phase is independently verifiable.

---

```xml
<system>

<identity>
You are implementing 8 distinct feature additions and bug fixes across the Nivesh codebase.
Frontend is SwiftUI (iOS 16+), backend is FastAPI + SQLAlchemy. All iOS changes conform to
AGENTS.md — zero raw hex, zero magic spacing, zero .system(size:) fonts, all Theme.* tokens.
Run gitnexus_impact before touching any existing symbol. No exceptions.
</identity>

<absolute_rules>
- gitnexus_impact({target: "symbolName", direction: "upstream"}) before every existing symbol edit
- gitnexus_detect_changes() before every commit
- Zero raw hex / Color(hex:) / Color(hue:) values — Theme.* only
- Zero .font(.system(size:...)) — Theme.*Font() or semantic Font only
- Zero magic spacing integers — Theme.Spacing.* only
- Every card: .banknoteCard(). Every interactive element: .buttonStyle(EKPressStyle()) + haptic
- All monetary values: IndianFormatter — no "Million", no "Billion"
- DO NOT touch HomeViewModel, NetworkManager fetch methods, HomeSectionID, or any .task {} blocks
</absolute_rules>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 0: DATABASE RESET — DELETE SAUMYA PATEL, INJECT MOCK DATA
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="0" name="DatabaseResetAndMockData">

This is a backend-only phase. No iOS changes.

FILE TO CREATE: backend/scripts/reset_mock_user.py

Run this script once with: python backend/scripts/reset_mock_user.py
It deletes all records for email snp050106@gmail.com, then reinserts complete mock data.

--- STEP 0.1: Delete all records ---

Using get_session() from database.py, delete in dependency order:
  ValuationSnapshot → Transaction → Holding → Portfolio → DeviceToken → Alert → User
  Filter by email = "snp050106@gmail.com" or by user_id after lookup.
  Use cascade delete if your ORM supports it, otherwise delete child tables first.

--- STEP 0.2: Recreate the user ---

  email:        snp050106@gmail.com
  name:         Saumya Patel
  password:     hash "StrongPass@123" with the same bcrypt rounds used in auth.py
  created_at:   90 days ago from today

--- STEP 0.3: Mock portfolio (insert into portfolios / holdings tables) ---

Create 1 portfolio for the user. Insert these holdings (buy dates spread over last 90 days):

  Ticker       Exchange  Qty    Avg Buy ₹   Sector
  RELIANCE     NSE       500    2,628.00    Energy
  TCS          NSE       200    3,377.00    IT
  HDFCBANK     NSE       150    1,677.00    Finance
  INFY         NSE       400    1,788.00    IT
  TATAMOTORS   NSE       300    876.00      Auto
  BAJFINANCE   NSE        80    6,950.00    Finance
  ICICIBANK    NSE       250    1,020.00    Finance
  WIPRO        NSE       600    478.00      IT
  AXISBANK     NSE       200    1,087.00    Finance
  MARUTI       NSE        25    10,240.00   Auto
  ADANIENT     NSE       100    2,890.00    Infra
  TITAN        NSE        75    3,320.00    Consumer

--- STEP 0.4: Mock valuation history (90 daily snapshots) ---

Insert 90 rows into valuation_snapshots (or equivalent table), one per calendar day.
Start from today - 90 days. The total_value follows this trajectory:
  Day 1:   ₹7,60,000
  Day 30:  ₹7,95,000  (gradual rise with ±1.2% daily noise)
  Day 60:  ₹8,40,000  (stronger momentum)
  Day 75:  ₹8,20,000  (brief correction)
  Day 90:  ₹8,74,250  (current)
  invested_value stays constant at ₹7,78,830 (sum of qty * avg_buy for all holdings)

Generate the intermediate values with small random daily moves — use Python's random.gauss(0.003, 0.012)
multiplied on the previous day's value, then clamp to keep the overall trajectory above.

--- STEP 0.5: Mock transactions (25 entries over 90 days) ---

Insert BUY transactions matching the holdings above (multiple buy entries per ticker to simulate
DCA behaviour). Add 4 SELL transactions for realism (small partial exits already taken profit on).
Use realistic timestamps spread across trading hours (9:15–15:30 IST weekdays only).

verify phase 0: Run SELECT count(*) queries on each table for the new user_id.
Holdings count = 12, valuation_snapshots count = 90, transactions ≈ 25+.
Login with snp050106@gmail.com + StrongPass@123 via the /auth/login endpoint. Returns 200 + token.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 1: LONG-PRESS FINANCIAL TERM DEFINITIONS (APP-WIDE)
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="1" name="LongPressTermDefinitions">

FILE TO CREATE: ios/StockApp/stockme/stockme/Utilities/FinanceTerms.swift
FILE TO CREATE: ios/StockApp/stockme/stockme/Utilities/TermDefinitionOverlay.swift

Every technical financial term anywhere in the app should show a definition + example on long press.
This is implemented as a ViewModifier applied per term. No network call — definitions are hardcoded.

--- STEP 1.1: Term dictionary ---

Create a struct FinanceTerm with: term: String, definition: String, example: String

Define a singleton FinanceTerms.shared with a [String: FinanceTerm] dictionary.
Keys are lowercase, whitespace-normalized (e.g. "p/e ratio", "rsi", "fii").

Include at minimum these definitions:

  RSI:
    definition: "Relative Strength Index — a momentum oscillator measuring speed and magnitude
                 of recent price changes. Ranges 0–100."
    example: "RSI above 70 = overbought (price may pull back). RSI below 30 = oversold
              (price may bounce). RELIANCE RSI at 74 signals caution."

  MACD:
    definition: "Moving Average Convergence Divergence — tracks the relationship between two
                 exponential moving averages (12-day and 26-day) of a stock's price."
    example: "When the MACD line crosses above the signal line, it's a bullish signal.
              TCS showed a MACD crossover on 3 Jan, rose 8% over the next 3 weeks."

  P/E Ratio:
    definition: "Price-to-Earnings ratio — how much investors pay per rupee of annual profit.
                 Higher P/E = investors expect faster growth."
    example: "HDFCBANK trades at P/E 18×. If it earns ₹100/share, the stock costs ₹1,800.
              NIFTY 50 average P/E is ~22×."

  EPS:
    definition: "Earnings Per Share — the company's net profit divided by total shares outstanding.
                 Higher EPS means more profit for each share you hold."
    example: "TCS EPS ₹122 this quarter. If you hold 10 shares, TCS earned ₹1,220 on your behalf."

  ROE:
    definition: "Return on Equity — how efficiently a company uses shareholder money to generate
                 profit. Expressed as a percentage."
    example: "HDFCBANK ROE 16% means: for every ₹100 of shareholder equity, it earns ₹16 profit.
              Above 15% is generally considered strong."

  EBITDA:
    definition: "Earnings Before Interest, Taxes, Depreciation and Amortisation — a proxy for
                 operating cash flow before financing and accounting decisions."
    example: "RELIANCE EBITDA ₹1.8L Cr means its core businesses generated that much operating
              profit before paying interest and taxes."

  FII:
    definition: "Foreign Institutional Investor — overseas funds (pension funds, hedge funds,
                 mutual funds) that invest in Indian markets."
    example: "FIIs bought ₹8,200 Cr of Indian equities last month. Heavy FII buying often
              signals confidence in India's growth story."

  DII:
    definition: "Domestic Institutional Investor — Indian institutions (LIC, mutual funds, banks)
                 investing in Indian equities."
    example: "When FIIs sell, DIIs often absorb the selling. In Oct 2023, DIIs bought ₹12,000 Cr
              net while FIIs sold ₹8,000 Cr — markets stayed stable."

  Beta:
    definition: "Measures how much a stock moves relative to the market. Beta 1 = moves with
                 NIFTY. Beta > 1 = more volatile. Beta < 1 = more stable."
    example: "TATAMOTORS Beta 1.4 — if NIFTY falls 5%, TATAMOTORS typically falls ~7%.
              HDFCBANK Beta 0.9 — more defensive."

  CAGR:
    definition: "Compound Annual Growth Rate — the steady annual return rate that would take an
                 investment from its starting value to its ending value."
    example: "₹1L invested in INFY 5 years ago is now ₹1.95L. CAGR = 14.3% per year.
              Better than FD (6.5% CAGR) but with higher risk."

  XIRR:
    definition: "Extended Internal Rate of Return — the actual annualised return on your
                 portfolio accounting for the exact timing of every buy and sell."
    example: "Even if a stock is up 40%, your XIRR may be 22% if you added more money at the peak.
              XIRR is the only honest way to measure your personal returns."

  Piotroski Score:
    definition: "A 0–9 scoring system for a company's financial health. Scores 8–9 = financially
                 strong. Scores 0–2 = financially weak. Based on profitability, leverage, and
                 operating efficiency metrics."
    example: "HDFCBANK Piotroski Score 8 — strong earnings, declining debt, growing margins.
              A score of 2 on a stock you hold is a red flag."

  SMA:
    definition: "Simple Moving Average — the arithmetic mean of a stock's closing prices over
                 N days. Smooths out short-term noise."
    example: "50-day SMA for RELIANCE = ₹2,760. Price currently ₹2,847 = trading above its
              50-day average, which is a bullish sign."

  EMA:
    definition: "Exponential Moving Average — like SMA but gives more weight to recent prices,
                 reacting faster to price changes."
    example: "12-day EMA responds faster to new prices than 50-day SMA. MACD is built from
              the difference between 12-day EMA and 26-day EMA."

  52W High:
    definition: "The highest price a stock traded at in the last 52 weeks (1 year)."
    example: "RELIANCE 52W High ₹3,124. Current price ₹2,847 = trading 8.9% below its yearly
              peak. Some investors see this as a discount entry."

  52W Low:
    definition: "The lowest price a stock traded at in the last 52 weeks."
    example: "TATAMOTORS 52W Low ₹802. It has rallied 22% from that bottom. Sustained recovery
              above 52W Low suggests the sell-off phase is over."

  Market Cap:
    definition: "Total market value of a company — current stock price × total shares outstanding.
                 Determines if it's large-cap, mid-cap or small-cap."
    example: "RELIANCE Market Cap ₹19.8L Cr = largest listed company in India. NIFTY 50
              includes only large-cap companies above ~₹20,000 Cr."

  Open Interest:
    definition: "The total number of outstanding derivative contracts (options or futures) that
                 have not been settled. Higher OI = more active participation."
    example: "NIFTY 23,000 Call OI rose 8L contracts. This means more traders are betting NIFTY
              will NOT cross 23,000 — acts as a resistance level."

  Put/Call Ratio:
    definition: "Total Put open interest divided by total Call open interest. A ratio above 1
                 means more bearish bets. Below 1 means more bullish bets."
    example: "PCR 1.3 for BANKNIFTY = more puts than calls, meaning institutional hedges are
              high. Contrarians read this as a bullish signal."

  Circuit Breaker:
    definition: "A regulatory halt triggered when a stock moves up or down by a set percentage
                 in a single session. Upper circuit = price locked at the limit up."
    example: "A small-cap stock hit 20% upper circuit — it cannot trade higher today regardless
              of demand. Check if this is news-driven or operator activity."

  Bulk Deal:
    definition: "A single trade of more than 0.5% of a company's total shares in one session.
                 Must be disclosed to the exchange on the day of the trade."
    example: "LIC bought 1.2% of BAJFINANCE in a bulk deal at ₹6,800. When LIC accumulates,
              it's often read as a long-term confidence signal."

  VIX:
    definition: "India VIX — the 'Fear Index'. Measures expected market volatility over the
                 next 30 days derived from NIFTY options prices."
    example: "VIX at 12 = calm markets. VIX spiking to 25+ = panic buying of puts, expect
              large NIFTY swings. Historically, VIX spikes are buying opportunities."

  Debt/Equity:
    definition: "Total debt divided by shareholders' equity. Lower is generally safer.
                 Shows how leveraged a company is."
    example: "TATAMOTORS D/E 1.8 = it owes ₹1.80 for every ₹1 of equity — highly leveraged.
              INFY D/E 0.02 — virtually debt-free, much safer balance sheet."

  Dividend Yield:
    definition: "Annual dividend per share divided by current share price, expressed as a %.
                 Shows the cash income you earn just for holding the stock."
    example: "ITC pays ₹6.75 dividend. Share price ₹438 → Dividend Yield 1.54%.
              If ITC were a bank FD, you'd compare this to the FD interest rate."

  Free Cash Flow:
    definition: "Cash a company generates after paying for capital expenditure — the actual
                 money left over that can be returned to shareholders or invested."
    example: "RELIANCE generated ₹48,000 Cr FCF last year. This funds Jio expansion, retail
              growth AND share buybacks — without needing to borrow."

  Promoter Pledging:
    definition: "When promoters (founders/major shareholders) pledge their shares as collateral
                 for loans. High pledging is a risk — forced selling if stock falls."
    example: "If a promoter pledges 60% of their holding and the stock drops sharply, lenders
              can sell those shares, causing further price collapse. Always check."

--- STEP 1.2: TermTooltipModifier ViewModifier ---

  struct TermTooltipModifier: ViewModifier {
      let term: String
      @State private var showTooltip = false

      func body(content: Content) -> some View {
          content
              .onLongPressGesture(minimumDuration: 0.5) {
                  HapticManager.impact(.medium)
                  showTooltip = true
              }
              .overlay {
                  if showTooltip, let entry = FinanceTerms.shared.lookup(term) {
                      TermTooltipCard(entry: entry, onDismiss: { showTooltip = false })
                          .transition(.opacity.combined(with: .scale(scale: 0.95, anchor: .center)))
                          .animation(.spring(response: 0.25, dampingFraction: 0.8), value: showTooltip)
                          .zIndex(999)
                  }
              }
      }
  }

  extension View {
      func financeTerm(_ term: String) -> some View {
          modifier(TermTooltipModifier(term: term))
      }
  }

--- STEP 1.3: TermTooltipCard view ---

  struct TermTooltipCard: View {
      let entry: FinanceTerm
      let onDismiss: () -> Void

      var body: some View {
          ZStack(alignment: .topTrailing) {
              VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                  Text(entry.term.uppercased())
                      .font(Theme.officialStampFont(size: 10))
                      .tracking(1.5)
                      .foregroundStyle(Theme.securityGold)

                  Text(entry.definition)
                      .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                      .foregroundStyle(Theme.inkPrimary)
                      .fixedSize(horizontal: false, vertical: true)

                  GuillocheDivider()

                  VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                      Text("EXAMPLE")
                          .font(Theme.officialStampFont(size: 8))
                          .tracking(1.2)
                          .foregroundStyle(Theme.inkTertiary)
                      Text(entry.example)
                          .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                          .foregroundStyle(Theme.inkSecondary)
                          .fixedSize(horizontal: false, vertical: true)
                  }
              }
              .padding(Theme.Spacing.card)
              .banknoteCard()
              .frame(maxWidth: 300)

              Button(action: { HapticManager.selection(); onDismiss() }) {
                  Image(systemName: "xmark.circle.fill")
                      .font(.title3)
                      .foregroundStyle(Theme.inkTertiary)
              }
              .buttonStyle(EKPressStyle())
              .padding(Theme.Spacing.medium)
          }
          .padding(Theme.screenPadding)
          // Tap outside to dismiss
          .background(
              Color.black.opacity(0.4)
                  .ignoresSafeArea()
                  .onTapGesture { onDismiss() }
          )
      }
  }

--- STEP 1.4: Apply .financeTerm() at known term sites ---

Search the codebase (gitnexus_query({query: "technical indicator label"}) then grep) for Text views
displaying these terms and append .financeTerm("term name") to each. Priority locations:

  - Any Text("RSI"), Text("MACD"), Text("P/E"), Text("EPS"), Text("ROE") in StockCharts.swift
  - Piotroski score labels in any analysis or fundamentals view
  - FII / DII labels in InstitutionalDashCard and related views
  - Beta, Market Cap, 52W High/Low labels in stock detail metric grids
  - CAGR, XIRR labels in portfolio views
  - VIX label in MarketPulseDashCard
  - "Open Interest", "Put/Call Ratio" labels in options-related views
  - "Dividend Yield", "Free Cash Flow", "Debt/Equity" in fundamentals views
  - Circuit labels ("Upper Circuit", "Lower Circuit") in market movers

verify phase 1: Long-press "RSI" in any stock chart — tooltip card appears within 0.5s.
Tap outside or X — tooltip dismisses. No crash on terms not in the dictionary (lookup returns nil,
modifier renders nothing). Card uses .banknoteCard() and Theme.* tokens throughout.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 2: SCREENER MINI SPARKLINE CHARTS
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="2" name="ScreenerSparklineCharts">

FILE: Wherever the screener stock list/row is defined. Search with:
  gitnexus_query({query: "screener stock row list"})

Run gitnexus_impact on the screener row component before editing.

The target layout (matching the reference image provided):

  ┌─────────────────────────────────────────────────────────────┐
  │  [RE]  RELIANCE           ∿∿∿∿∿     ₹2,945.60              │
  │        Reliance Industries            +1.24%                │
  └─────────────────────────────────────────────────────────────┘

  - Left: 2-letter ticker abbreviation tile (first 2 chars, uppercase, rounded square,
    background Theme.canvasDeep, text Theme.securityGold, font Theme.serialNumberFont(size: 12))
  - Center-left: ticker + full company name (existing)
  - Center: SparklineView — 60pt wide, 32pt tall, data = last 5 trading days of close prices
    Green line if current > open5d, red line if current < open5d
  - Right: price + % badge (existing, but use IndianFormatter.price() if not already)

--- STEP 2.1: SparklineView (reuse or create) ---

SparklineView already exists in MomentumRowView context. Confirm via:
  gitnexus_context({name: "SparklineView"})
If it exists, import/reference it. If not, create in StockCharts.swift:

  struct SparklineView: View {
      let values: [Double]
      let color: Color

      var body: some View {
          Canvas { context, size in
              guard values.count > 1 else { return }
              let mn = values.min()!, mx = values.max()!, rng = max(mx - mn, 1)
              var path = Path()
              for (i, v) in values.enumerated() {
                  let x = CGFloat(i) / CGFloat(values.count - 1) * size.width
                  let y = size.height - CGFloat((v - mn) / rng) * size.height
                  i == 0 ? path.move(to: CGPoint(x: x, y: y)) : path.addLine(to: CGPoint(x: x, y: y))
              }
              context.stroke(path, with: .color(color), style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))
          }
      }
  }

--- STEP 2.2: Update the screener row ---

In the screener stock row component, update the HStack layout to:

  HStack(spacing: Theme.Spacing.standard) {
      // Ticker tile
      Text(String(ticker.prefix(2)).uppercased())
          .font(Theme.serialNumberFont(size: 12))
          .foregroundStyle(Theme.securityGold)
          .frame(width: 40, height: 40)
          .background(Theme.canvasDeep)
          .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))

      // Name
      VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
          Text(ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
          Text(companyName).font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
              .foregroundStyle(Theme.inkSecondary)
      }

      Spacer()

      // Sparkline
      if !sparklineValues.isEmpty {
          let isUp = (sparklineValues.last ?? 0) >= (sparklineValues.first ?? 0)
          SparklineView(values: sparklineValues, color: isUp ? Theme.bullGreen : Theme.bearRed)
              .frame(width: 60, height: 32)
      }

      // Price + badge
      VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
          Text(IndianFormatter.price(currentPrice))
              .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
          let isUp = changePercent >= 0
          Text(IndianFormatter.percent(changePercent))
              .font(Theme.serialNumberFont(size: 11))
              .foregroundStyle(isUp ? Theme.bullGreen : Theme.bearRed)
              .padding(.horizontal, Theme.Spacing.small)
              .padding(.vertical, Theme.Spacing.xSmall)
              .background((isUp ? Theme.bullGreen : Theme.bearRed).opacity(0.15))
              .cornerRadius(Theme.CornerRadius.small)
      }
  }
  .padding(.horizontal, Theme.screenPadding)
  .padding(.vertical, Theme.Spacing.standard)

--- STEP 2.3: Sparkline data ---

The screener stock model should expose a sparkline: [Double] field (last 5 days closing prices).
If the existing screener model does not have this field, add it to the backend screener endpoint
response and the Swift model. If it's already present but not displayed, just wire it up.

verify phase 2: Screener shows the 2-letter tile, sparkline, price, and badge for every row.
Green sparkline for gainers, red for losers. No layout overflow on iPhone SE (375pt).
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 3: MARKETS SECTION NAVIGATION REDESIGN
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="3" name="MarketsNavigationRedesign">

Run gitnexus_query({query: "markets section navigation"}) to locate the Markets tab/screen.
Run gitnexus_impact on the root Markets view before editing.

GOAL: Replace whatever navigation pattern currently exists in the Markets section with a
modern segmented/tabbed approach that feels premium. Do NOT change the destination views —
only the navigation chrome between them.

--- STEP 3.1: Navigation model ---

Define a MarketsTab enum:
  enum MarketsTab: String, CaseIterable {
      case overview  = "OVERVIEW"
      case indices   = "INDICES"
      case sectors   = "SECTORS"
      case movers    = "MOVERS"
      case fno       = "F&O"
      case global    = "GLOBAL"
  }

Adjust cases to match whatever market sub-sections currently exist in the app.
Use gitnexus_query({query: "markets tab view"}) to see what pages are available.

--- STEP 3.2: Floating pill navigation bar ---

Replace the existing navigation mechanism with a horizontally scrollable pill row:

  struct MarketsTabBar: View {
      @Binding var selected: MarketsTab

      var body: some View {
          ScrollView(.horizontal, showsIndicators: false) {
              HStack(spacing: Theme.Spacing.standard) {
                  ForEach(MarketsTab.allCases, id: \.self) { tab in
                      Button(action: { HapticManager.selection(); selected = tab }) {
                          Text(tab.rawValue)
                              .font(Theme.officialStampFont(size: 10))
                              .tracking(1.0)
                              .foregroundStyle(selected == tab ? Theme.canvas : Theme.inkSecondary)
                              .padding(.horizontal, Theme.Spacing.card)
                              .padding(.vertical, Theme.Spacing.medium)
                              .background(selected == tab ? Theme.securityGold : Theme.canvasDeep)
                              .clipShape(Capsule())
                              .overlay(
                                  Capsule().stroke(
                                      selected == tab ? Theme.securityGold : Theme.borderSage,
                                      lineWidth: 0.5
                                  )
                              )
                      }
                      .buttonStyle(EKPressStyle())
                  }
              }
              .padding(.horizontal, Theme.screenPadding)
              .padding(.vertical, Theme.Spacing.medium)
          }
          .background(Theme.canvas)
      }
  }

--- STEP 3.3: Markets root screen ---

The root MarketsScreen should be structured as:

  struct MarketsScreen: View {
      @State private var selectedTab: MarketsTab = .overview

      var body: some View {
          VStack(spacing: 0) {
              // Sticky tab bar (not inside ScrollView — sticks to top)
              MarketsTabBar(selected: $selectedTab)

              GuillocheDivider()
                  .padding(.horizontal, Theme.screenPadding)

              // Content — switch on selectedTab, render existing destination views
              Group {
                  switch selectedTab {
                  case .overview:  MarketsOverviewView()     // existing — unchanged
                  case .indices:   IndicesView()             // existing — unchanged
                  case .sectors:   SectorView()              // existing — unchanged
                  case .movers:    MarketMoversView()        // existing — unchanged
                  case .fno:       FnOView()                 // existing — unchanged
                  case .global:    GlobalMarketsView()       // existing — unchanged
                  }
              }
              .frame(maxWidth: .infinity, maxHeight: .infinity)
              .transition(.opacity)
              .animation(.easeInOut(duration: 0.18), value: selectedTab)
          }
      }
  }

All existing destination views are rendered INSIDE the switch — their internal navigation,
scroll views, data fetching, and functionality are completely unchanged.

verify phase 3: Tapping each pill switches content with a smooth 0.18s opacity transition.
Pill bar sticks to the top during content scroll. Active pill has securityGold background.
All existing market sub-pages load correctly. NavigationStack depth works as before.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 4: PORTFOLIO MESSAGE + RUPEE ICON FUNCTIONALITY
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="4" name="PortfolioIconFunctionality">

Run gitnexus_query({query: "portfolio header message rupee icon button"}) to locate these icons.
Run gitnexus_impact on the portfolio header view before editing.

The portfolio section has two icon buttons in the header. Give them both real functionality:

--- MESSAGE ICON → Portfolio AI Brief Sheet ---

Tapping the message icon opens a bottom sheet with an AI-generated portfolio brief.
The brief content comes from the existing morning brief or analysis data already fetched —
do NOT make a new network call. Use viewModel.morningBrief or the existing portfolio summary.

  struct PortfolioBriefSheet: View {
      let portfolioValue: Double
      let pnl: Double
      let holdings: [HoldingModel]
      @Environment(\.dismiss) var dismiss

      var body: some View {
          ScrollView {
              VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                  // Header
                  HStack {
                      VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                          Text("PORTFOLIO BRIEF")
                              .font(Theme.officialStampFont(size: 10)).tracking(1.5)
                              .foregroundStyle(Theme.securityGold)
                          Text("Your snapshot")
                              .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                              .foregroundStyle(Theme.inkSecondary)
                      }
                      Spacer()
                      Button(action: { dismiss() }) {
                          Image(systemName: "xmark.circle.fill")
                              .font(.title2).foregroundStyle(Theme.inkTertiary)
                      }.buttonStyle(EKPressStyle())
                  }

                  GuillocheDivider()

                  // Top 3 performers
                  Text("TOP PERFORMERS")
                      .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                  ForEach(holdings.sorted { $0.pnlPercent > $1.pnlPercent }.prefix(3)) { h in
                      HStack {
                          Text(h.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                          Spacer()
                          Text(IndianFormatter.percent(h.pnlPercent))
                              .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.bullGreen)
                      }
                  }

                  GuillocheDivider()

                  // Bottom 3 performers
                  Text("NEEDS ATTENTION")
                      .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                  ForEach(holdings.sorted { $0.pnlPercent < $1.pnlPercent }.prefix(3)) { h in
                      HStack {
                          Text(h.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                          Spacer()
                          Text(IndianFormatter.percent(h.pnlPercent))
                              .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.bearRed)
                      }
                  }
              }
              .padding(Theme.screenPadding)
          }
          .background(Theme.canvas.ignoresSafeArea())
          .presentationDetents([.medium, .large])
          .presentationDragIndicator(.visible)
      }
  }

--- RUPEE ICON → Quick Transaction Sheet ---

Tapping the rupee icon opens a sheet to log a BUY or SELL transaction:

  struct QuickTransactionSheet: View {
      @Environment(\.dismiss) var dismiss
      @State private var transactionType: TransactionType = .buy
      @State private var ticker = ""
      @State private var quantity = ""
      @State private var price = ""
      @State private var isSubmitting = false

      var body: some View {
          NavigationStack {
              VStack(spacing: Theme.Spacing.large) {
                  // BUY / SELL toggle
                  HStack(spacing: 0) {
                      ForEach([TransactionType.buy, .sell], id: \.self) { type in
                          Button(action: { HapticManager.selection(); transactionType = type }) {
                              Text(type == .buy ? "BUY" : "SELL")
                                  .font(Theme.officialStampFont(size: 11)).tracking(1.5)
                                  .foregroundStyle(transactionType == type ? Theme.canvas : Theme.inkSecondary)
                                  .frame(maxWidth: .infinity).padding(.vertical, Theme.Spacing.standard)
                                  .background(
                                      transactionType == type
                                          ? (type == .buy ? Theme.bullGreen : Theme.bearRed)
                                          : Theme.canvasDeep
                                  )
                          }
                          .buttonStyle(EKPressStyle())
                      }
                  }
                  .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                  .padding(.horizontal, Theme.screenPadding)

                  // Ticker field
                  VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                      Text("TICKER SYMBOL")
                          .font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                      TextField("e.g. RELIANCE", text: $ticker)
                          .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                          .textInputAutocapitalization(.characters)
                          .padding(Theme.Spacing.card).banknoteCard()
                  }.padding(.horizontal, Theme.screenPadding)

                  // Quantity + Price fields (side by side)
                  HStack(spacing: Theme.Spacing.standard) {
                      VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                          Text("QTY").font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                          TextField("0", text: $quantity).keyboardType(.numberPad)
                              .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                              .padding(Theme.Spacing.card).banknoteCard()
                      }
                      VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                          Text("PRICE ₹").font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                          TextField("0.00", text: $price).keyboardType(.decimalPad)
                              .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                              .padding(Theme.Spacing.card).banknoteCard()
                      }
                  }.padding(.horizontal, Theme.screenPadding)

                  Spacer()

                  // Submit
                  Button(action: { submitTransaction() }) {
                      Text(isSubmitting ? "LOGGING..." : "LOG \(transactionType == .buy ? "BUY" : "SELL")")
                          .font(Theme.officialStampFont(size: 11)).tracking(1.5)
                          .foregroundStyle(Theme.canvas).frame(maxWidth: .infinity)
                          .padding(Theme.Spacing.card)
                          .background(transactionType == .buy ? Theme.bullGreen : Theme.bearRed)
                          .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                  }
                  .buttonStyle(EKPressStyle())
                  .padding(.horizontal, Theme.screenPadding)
                  .disabled(ticker.isEmpty || quantity.isEmpty || price.isEmpty || isSubmitting)
              }
              .padding(.top, Theme.Spacing.large)
              .background(Theme.canvas.ignoresSafeArea())
              .navigationTitle("Quick Transaction")
              .navigationBarTitleDisplayMode(.inline)
          }
          .presentationDetents([.large])
          .presentationDragIndicator(.visible)
      }

      private func submitTransaction() {
          isSubmitting = true
          HapticManager.impact(.medium)
          // POST to existing transaction endpoint, same pattern as wherever transactions are logged
          // On success: HapticManager.success(), dismiss()
          // On error: HapticManager.error(), show inline error
      }
  }

Wire both sheets using @State booleans in the portfolio header:
  @State private var showBriefSheet = false
  @State private var showTransactionSheet = false
  // messageIcon.onTapGesture → showBriefSheet = true
  // rupeeIcon.onTapGesture → showTransactionSheet = true

verify phase 4: Message icon opens the portfolio brief sheet showing top/bottom performers.
Rupee icon opens the transaction sheet with BUY/SELL toggle. Submit button is disabled until all
3 fields are filled. Successful submission shows HapticManager.success() feedback.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 5: EXPERT VIDEOS + MARKET NEWS NAVIGATION SPACING BUG FIX
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="5" name="NavigationSpacingBugFix">

Bug: In Expert Videos and Market News sections the navigation bar overlaps with the
GuillocheDivider / top content line directly below the section header.

Run gitnexus_query({query: "market news expert videos navigation overlap"}) to confirm locations.
Then run gitnexus_impact on the affected views.

--- FIX: Add explicit top spacing ---

In both the NewsDetailSheet (or full News screen) and the Expert Videos screen, find where the
content ScrollView or VStack begins immediately after the NavigationStack header, and add:

  .padding(.top, Theme.Spacing.standard)

to the first content element (the GuillocheDivider or SectionHeader), OR add

  .navigationBarTitleDisplayMode(.inline)

if it is currently using .large (which causes content to jump when scrolling and overlap on some
iOS 16 device sizes).

If the header uses a custom inline header that sits inside the view body (not via NavigationStack
title modifiers), add:

  Spacer().frame(height: Theme.Spacing.standard)

as the first element in the content VStack, above the GuillocheDivider.

Do this for BOTH the news section view AND the expert videos section view.

verify phase 5: In Expert Videos and Market News, the first content element (GuillocheDivider
or section header) has clear air gap below the navigation bar. No overlap on iPhone 14 (standard)
or iPhone SE. Measure: minimum 8pt visible gap between nav bar bottom and first content element.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 6: BANKNOTE THEME SYSTEM IN SETTINGS
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="6" name="BanknoteThemeSystem">

FILE TO CREATE: ios/StockApp/stockme/stockme/Utilities/ThemeManager.swift
FILE TO EDIT:   ios/StockApp/stockme/stockme/Utilities/Theme.swift
FILE TO EDIT:   Settings screen (find via gitnexus_query({query: "settings screen theme"}))

The app offers 7 theme presets based on Indian rupee banknote series colors.
Theme selection is persisted in UserDefaults. Applied globally via @AppStorage + environment injection.

--- STEP 6.1: AppTheme enum ---

  enum AppTheme: String, CaseIterable, Codable {
      case darkImmersive  = "dark_immersive"   // Current default — deep dark
      case chocolateBrown = "chocolate_brown"  // ₹10 note
      case greenishYellow = "greenish_yellow"  // ₹20 note
      case fluorescentBlue = "fluorescent_blue" // ₹50 note
      case lavender       = "lavender"          // ₹100 note
      case brightYellow   = "bright_yellow"     // ₹200 note
      case stoneGrey      = "stone_grey"        // ₹500 note

      var displayName: String {
          switch self {
          case .darkImmersive:   return "Dark Immersive"
          case .chocolateBrown:  return "₹10 · Chocolate Brown"
          case .greenishYellow:  return "₹20 · Greenish Yellow"
          case .fluorescentBlue: return "₹50 · Fluorescent Blue"
          case .lavender:        return "₹100 · Lavender"
          case .brightYellow:    return "₹200 · Bright Yellow"
          case .stoneGrey:       return "₹500 · Stone Grey"
          }
      }

      // Swatch color shown in the settings picker (the accent/dominant hue of each note)
      var swatchColor: Color {
          switch self {
          case .darkImmersive:   return Color(red: 0.83, green: 0.66, blue: 0.09)  // securityGold
          case .chocolateBrown:  return Color(red: 0.55, green: 0.27, blue: 0.07)  // chocolate
          case .greenishYellow:  return Color(red: 0.60, green: 0.72, blue: 0.13)  // greenish yellow
          case .fluorescentBlue: return Color(red: 0.00, green: 0.40, blue: 0.80)  // fluorescent blue
          case .lavender:        return Color(red: 0.59, green: 0.48, blue: 0.71)  // lavender
          case .brightYellow:    return Color(red: 1.00, green: 0.84, blue: 0.00)  // bright yellow
          case .stoneGrey:       return Color(red: 0.50, green: 0.50, blue: 0.50)  // stone grey
          }
      }
  }

Note: swatchColor is ONLY for the circular color swatch in the settings picker.
It does NOT set any Theme.* token directly. All Theme tokens are remapped in Step 6.2.

--- STEP 6.2: ThemeManager singleton ---

  @Observable class ThemeManager {
      static let shared = ThemeManager()
      @AppStorage("selectedTheme") var selectedTheme: String = AppTheme.darkImmersive.rawValue

      var current: AppTheme {
          get { AppTheme(rawValue: selectedTheme) ?? .darkImmersive }
          set { selectedTheme = newValue.rawValue }
      }

      // Returns the resolved canvas (background) color for the selected theme in dark mode
      var canvasColor: Color {
          switch current {
          case .darkImmersive:   return Color(red: 0.039, green: 0.039, blue: 0.059)
          case .chocolateBrown:  return Color(red: 0.10, green: 0.06, blue: 0.04)
          case .greenishYellow:  return Color(red: 0.05, green: 0.07, blue: 0.04)
          case .fluorescentBlue: return Color(red: 0.02, green: 0.04, blue: 0.10)
          case .lavender:        return Color(red: 0.05, green: 0.04, blue: 0.10)
          case .brightYellow:    return Color(red: 0.08, green: 0.07, blue: 0.02)
          case .stoneGrey:       return Color(red: 0.05, green: 0.05, blue: 0.05)
          }
      }

      var accentColor: Color {
          switch current {
          case .darkImmersive:   return Color(red: 0.83, green: 0.66, blue: 0.09)  // securityGold
          case .chocolateBrown:  return Color(red: 0.80, green: 0.45, blue: 0.18)  // warm amber
          case .greenishYellow:  return Color(red: 0.68, green: 0.82, blue: 0.20)  // lime accent
          case .fluorescentBlue: return Color(red: 0.20, green: 0.60, blue: 1.00)  // electric blue
          case .lavender:        return Color(red: 0.75, green: 0.60, blue: 0.90)  // soft lavender
          case .brightYellow:    return Color(red: 1.00, green: 0.85, blue: 0.10)  // bright gold
          case .stoneGrey:       return Color(red: 0.72, green: 0.72, blue: 0.72)  // stone
          }
      }
  }

--- STEP 6.3: Inject ThemeManager into Theme.swift ---

Update Theme.swift so that the canvas and accent colors reference ThemeManager.shared:

  static var canvas: Color { ThemeManager.shared.canvasColor }
  static var securityGold: Color { ThemeManager.shared.accentColor }
  // canvasDeep, canvasShadow derive from canvas with brightness offset — compute dynamically

Note: bullGreen and bearRed remain constant across themes (semantic meaning must not shift).
Only canvas/background and securityGold/accent change per theme.

Inject ThemeManager.shared into the root app environment so SwiftUI re-renders on change:
  @main struct NiveshApp: App {
      @State private var themeManager = ThemeManager.shared
      var body: some Scene {
          WindowGroup {
              ContentView().environment(themeManager)
          }
      }
  }

--- STEP 6.4: Theme picker in Settings screen ---

Find the Settings screen and add a "THEME" section:

  Section {
      VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
          Text("DENOMINATION THEME")
              .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)

          LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())],
                    spacing: Theme.Spacing.standard) {
              ForEach(AppTheme.allCases, id: \.self) { theme in
                  Button(action: {
                      HapticManager.selection()
                      ThemeManager.shared.current = theme
                  }) {
                      HStack(spacing: Theme.Spacing.medium) {
                          Circle()
                              .fill(theme.swatchColor)
                              .frame(width: 20, height: 20)
                              .overlay(Circle().stroke(Color.white.opacity(0.3), lineWidth: 0.5))
                          Text(theme.displayName)
                              .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                              .foregroundStyle(Theme.inkPrimary)
                              .lineLimit(1)
                          Spacer()
                          if ThemeManager.shared.current == theme {
                              Image(systemName: "checkmark")
                                  .font(.caption.weight(.bold))
                                  .foregroundStyle(Theme.securityGold)
                          }
                      }
                      .padding(Theme.Spacing.standard)
                      .background(ThemeManager.shared.current == theme
                                  ? Theme.securityGold.opacity(0.08) : Theme.canvasDeep)
                      .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                      .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                          .stroke(ThemeManager.shared.current == theme
                                  ? Theme.securityGold.opacity(0.4) : Theme.borderFine, lineWidth: 0.5))
                  }
                  .buttonStyle(EKPressStyle())
              }
          }
      }
      .padding(.vertical, Theme.Spacing.standard)
  }

verify phase 6: Settings shows 7 theme options with color swatches and denomination labels.
Tapping a theme instantly changes the app background and accent color globally.
Selection persists after app restart. Active theme shows a checkmark. bullGreen/bearRed unchanged.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     PHASE 7: PORTFOLIO CARD REDESIGN (HOME SECTION)
     ═══════════════════════════════════════════════════════════════════════ -->

<phase id="7" name="PortfolioCardRedesign">

Run gitnexus_impact({target: "PortfolioNoteCard", direction: "upstream"}) first.

The current PortfolioNoteCard shows a static summary. Redesign it as a data-rich
financial statement card that communicates portfolio health at a glance.

FILE TO EDIT: Wherever PortfolioNoteCard is defined (search with gitnexus_context({name: "PortfolioNoteCard"}))

Replace the entire view body with this layout:

  var body: some View {
      VStack(spacing: 0) {

          // ── Row 1: Portfolio value + today's P&L ──────────────────────────
          HStack(alignment: .top) {
              VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                  Text("PORTFOLIO VALUE")
                      .font(Theme.officialStampFont(size: 8)).tracking(1.5)
                      .foregroundStyle(Theme.inkTertiary)
                  Text(IndianFormatter.priceCompact(value))
                      .font(.title.weight(.bold)).monospaced()
                      .foregroundStyle(Theme.inkPrimary)
                      .contentTransition(.numericText())
              }
              Spacer()
              VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                  Text("TODAY")
                      .font(Theme.officialStampFont(size: 8)).tracking(1.5)
                      .foregroundStyle(Theme.inkTertiary)
                  let todayUp = todayPnL >= 0
                  Text((todayUp ? "+" : "") + IndianFormatter.priceCompact(abs(todayPnL)))
                      .font(Theme.serialNumberFont(size: 15, relativeTo: .subheadline).weight(.semibold))
                      .foregroundStyle(todayUp ? Theme.bullGreen : Theme.bearRed)
                  Text(IndianFormatter.percent(todayPnLPercent))
                      .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote))
                      .foregroundStyle(todayUp ? Theme.bullGreen : Theme.bearRed)
              }
          }
          .padding(Theme.Spacing.card)

          GuillocheDivider()
              .padding(.horizontal, Theme.Spacing.card)

          // ── Row 2: Invested / Returns / Stocks ────────────────────────────
          HStack(spacing: 0) {
              // Invested
              VStack(spacing: Theme.Spacing.xSmall) {
                  Text("INVESTED")
                      .font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                  Text(IndianFormatter.priceCompact(invested))
                      .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                      .foregroundStyle(Theme.inkSecondary)
              }
              .frame(maxWidth: .infinity)

              Rectangle().fill(Theme.borderFine).frame(width: 0.5, height: 32)

              // Total Returns
              VStack(spacing: Theme.Spacing.xSmall) {
                  Text("RETURNS")
                      .font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                  let up = totalPnL >= 0
                  Text((up ? "+" : "") + IndianFormatter.percent(totalPnLPercent))
                      .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline).weight(.semibold))
                      .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
              }
              .frame(maxWidth: .infinity)

              Rectangle().fill(Theme.borderFine).frame(width: 0.5, height: 32)

              // Holdings count
              VStack(spacing: Theme.Spacing.xSmall) {
                  Text("STOCKS")
                      .font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                  Text("\(count)")
                      .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline).weight(.semibold))
                      .foregroundStyle(Theme.inkPrimary)
              }
              .frame(maxWidth: .infinity)
          }
          .padding(.vertical, Theme.Spacing.standard)
          .padding(.horizontal, Theme.Spacing.card)

          GuillocheDivider()
              .padding(.horizontal, Theme.Spacing.card)

          // ── Row 3: P&L progress bar (invested → current) ──────────────────
          VStack(alignment: .leading, spacing: Theme.Spacing.small) {
              let progress = min(max((value - invested) / max(invested, 1) * 5 + 0.5, 0.05), 0.95)
              let isUp = totalPnL >= 0
              GeometryReader { geo in
                  ZStack(alignment: .leading) {
                      RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                          .fill(Theme.canvasShadow).frame(height: 4)
                      RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                          .fill(isUp ? Theme.bullGreen : Theme.bearRed)
                          .frame(width: geo.size.width * progress, height: 4)
                  }
              }
              .frame(height: 4)
              HStack {
                  Text("COST BASIS").font(Theme.officialStampFont(size: 7)).tracking(1).foregroundStyle(Theme.inkTertiary)
                  Spacer()
                  Text("CURRENT VALUE").font(Theme.officialStampFont(size: 7)).tracking(1).foregroundStyle(Theme.inkTertiary)
              }
          }
          .padding(.horizontal, Theme.Spacing.card)
          .padding(.vertical, Theme.Spacing.standard)
      }
      .banknoteCard()
      .shimmerPlaceholder(isLoading: isLoading)
  }

The PortfolioNoteCard parameters it already accepts (value, totalPnL, invested, todayPnL, count,
isLoading) remain unchanged. Add todayPnLPercent and totalPnLPercent as computed properties:
  var totalPnLPercent: Double { (totalPnL / max(invested, 1)) * 100 }
  var todayPnLPercent: Double { (todayPnL / max(value - todayPnL, 1)) * 100 }

verify phase 7: Portfolio card shows all 5 data zones (value + today | invested/returns/stocks |
progress bar). Progress bar is green/red. Loading state triggers shimmer. Layout holds on iPhone SE.
No raw colors, no magic spacing integers, all Theme.* tokens.
</phase>


<!-- ═══════════════════════════════════════════════════════════════════════
     FINAL VERIFICATION — ALL 8 PHASES
     ═══════════════════════════════════════════════════════════════════════ -->

<final_verification>

Run ALL before closing:

  [ ] gitnexus_detect_changes() — expected files only in diff
  [ ] Xcode build: zero errors, zero warnings
  [ ] grep diff: Color(hex:  Color(hue:  .secondary  .system(size:  spacing: 10  Rectangle().fill
      — ZERO hits across all changed files

  PHASE 0: SELECT count(*) FROM holdings WHERE user_id = [new_id] → 12 rows
           SELECT count(*) FROM valuation_snapshots WHERE user_id = [new_id] → 90 rows
           POST /auth/login {email: snp050106@gmail.com} → 200 + valid token

  PHASE 1: Long-press "RSI" label in any chart → tooltip card in 0.5s
           Long-press unknown text → no crash, no tooltip
           Tap outside tooltip → dismisses

  PHASE 2: Screener rows all show 2-letter tile + sparkline + price + badge
           Gainer sparklines green, loser sparklines red

  PHASE 3: Markets tab pills scroll horizontally, switching content with 0.18s fade
           All 6 sub-pages load. Back navigation from deep pages still works.

  PHASE 4: Message icon → portfolio brief sheet with top/bottom performers
           Rupee icon → BUY/SELL transaction sheet
           Submit button disabled when fields empty

  PHASE 5: No navigation bar overlap in Market News or Expert Videos on any device size

  PHASE 6: 7 theme options visible in Settings
           Selecting ₹50 Fluorescent Blue changes canvas + accent immediately
           Selection survives app restart

  PHASE 7: Portfolio card shows value, today P&L, invested, returns %, count, progress bar
           Loading state shows shimmer
           No layout overflow on SE or Pro Max
</final_verification>

</system>
```
