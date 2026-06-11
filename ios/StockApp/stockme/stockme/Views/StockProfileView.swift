import SwiftUI
import Charts

// MARK: - Glossary Term System (Phase 4)

struct GlossaryTermModifier: ViewModifier {
    let term: String
    let definition: String
    @State private var showPopover = false

    func body(content: Content) -> some View {
        content
            .onLongPressGesture(minimumDuration: 0.4) {
                HapticManager.impact(.medium)
                showPopover = true
            }
            .popover(isPresented: $showPopover, arrowEdge: .top) {
                GlossaryPopoverView(term: term, definition: definition)
                    .presentationCompactAdaptation(.popover)
            }
    }
}

private struct GlossaryPopoverView: View {
    let term: String
    let definition: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text(term.uppercased())
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.5)
                .foregroundStyle(Theme.securityGold)
            Text(definition)
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: 260)
        .background(Theme.canvasDeep)
    }
}

extension View {
    func glossaryTerm(_ term: String, definition: String) -> some View {
        modifier(GlossaryTermModifier(term: term, definition: definition))
    }
}

// MARK: - Interactive Price Chart (Phase 3)

struct InteractivePriceChartView: View {
    let history: [OHLCVPoint]
    let niftyHistory: [NiftyPricePoint]
    let ticker: String

    @State private var selectedPeriod = "1y"
    @State private var showCandlestick = false
    @State private var selectedPoint: OHLCVPoint? = nil
    @State private var zoomFactor: CGFloat = 1.0
    @State private var baseZoom: CGFloat = 1.0
    @State private var showNifty = true

    private let periods = ["1mo", "3mo", "6mo", "1y", "2y"]
    private let periodLabels = ["1M", "3M", "6M", "1Y", "2Y"]

    private var filteredPrices: [OHLCVPoint] {
        let count = history.count
        guard count > 0 else { return [] }
        let visible = max(10, Int(Double(count) / Double(zoomFactor)))
        return Array(history.suffix(visible))
    }

    private var priceRange: ClosedRange<Double> {
        guard !filteredPrices.isEmpty else { return 0...1 }
        let lo = filteredPrices.map { $0.low }.min()!
        let hi = filteredPrices.map { $0.high }.max()!
        let pad = (hi - lo) * 0.05
        return (lo - pad)...(hi + pad)
    }

    private var niftyNormalized: [NiftyPricePoint] {
        guard !filteredPrices.isEmpty, !niftyHistory.isEmpty, let firstClose = filteredPrices.first?.close, firstClose != 0,
              let firstNifty = niftyHistory.first?.close, firstNifty != 0 else { return [] }
        let stockBase = firstClose
        let niftyBase = firstNifty
        let startDate = filteredPrices.first!.parsedDate
        return niftyHistory.filter { $0.parsedDate >= startDate }.map { pt in
            let normalized = stockBase * (pt.close / niftyBase)
            return NiftyPricePoint(date: pt.date, close: normalized)
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.medium) {
            // Selected point info bar
            HStack(spacing: Theme.Spacing.standard) {
                if let p = selectedPoint {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(p.date).font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.price(p.close))
                            .font(Theme.serialNumberFont(size: 14))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        HStack(spacing: Theme.Spacing.small) {
                            Text("H").font(.caption2).foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(p.high)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bullGreen)
                        }
                        HStack(spacing: Theme.Spacing.small) {
                            Text("L").font(.caption2).foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(p.low)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
                        }
                    }
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("VOL").font(.caption2).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.priceCompact(p.volume)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkSecondary)
                    }
                } else if let last = filteredPrices.last {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(ticker.uppercased()).font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.securityGold)
                        Text(IndianFormatter.price(last.close))
                            .font(Theme.serialNumberFont(size: 16))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    if let first = filteredPrices.first, first.close != 0 {
                        let returnPct = (last.close - first.close) / first.close * 100
                        let up = returnPct >= 0
                        VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                            Text("PERIOD RETURN").font(.caption2).foregroundStyle(Theme.inkTertiary)
                            Text(String(format: "%@%.2f%%", up ? "+" : "", returnPct))
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
                        }
                        .glossaryTerm("Period Return", definition: "Total price change from the first to the last visible bar in the selected time window, expressed as a percentage.")
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .frame(height: 44)

            // Main Chart
            Chart {
                if showCandlestick {
                    // Candlestick: wick line
                    ForEach(filteredPrices) { p in
                        RectangleMark(
                            x: .value("Date", p.parsedDate),
                            yStart: .value("Low", p.low),
                            yEnd: .value("High", p.high),
                            width: 1
                        )
                        .foregroundStyle(p.close >= p.open ? Theme.bullGreen : Theme.bearRed)
                    }
                    // Candlestick: body
                    ForEach(filteredPrices) { p in
                        RectangleMark(
                            x: .value("Date", p.parsedDate),
                            yStart: .value("Open", min(p.open, p.close)),
                            yEnd: .value("Close", max(p.open, p.close)),
                            width: .fixed(CGFloat(max(2, 280 / max(1, filteredPrices.count))))
                        )
                        .foregroundStyle(p.close >= p.open ? Theme.bullGreen : Theme.bearRed)
                    }
                } else {
                    // Line chart
                    ForEach(filteredPrices) { p in
                        LineMark(
                            x: .value("Date", p.parsedDate),
                            y: .value("Price", p.close)
                        )
                        .foregroundStyle(Theme.securityGold)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                        .interpolationMethod(.catmullRom)
                    }
                    // Area gradient
                    ForEach(filteredPrices) { p in
                        AreaMark(
                            x: .value("Date", p.parsedDate),
                            y: .value("Price", p.close)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Theme.securityGold.opacity(0.18), Theme.securityGold.opacity(0.0)],
                                startPoint: .top, endPoint: .bottom
                            )
                        )
                        .interpolationMethod(.catmullRom)
                    }
                }

                // Nifty benchmark overlay
                if showNifty {
                    ForEach(niftyNormalized) { pt in
                        LineMark(
                            x: .value("Date", pt.parsedDate),
                            y: .value("Nifty", pt.close)
                        )
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                    }
                }

                // Crosshair rule
                if let sel = selectedPoint {
                    RuleMark(x: .value("Selected", sel.parsedDate))
                        .foregroundStyle(Theme.securityGold.opacity(0.6))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    PointMark(
                        x: .value("Date", sel.parsedDate),
                        y: .value("Price", sel.close)
                    )
                    .foregroundStyle(Theme.securityGold)
                    .symbolSize(40)
                }
            }
            .chartYScale(domain: priceRange)
            .chartYAxis {
                AxisMarks(position: .trailing, values: .automatic(desiredCount: 5)) { val in
                    AxisValueLabel {
                        if let v = val.as(Double.self) {
                            Text(IndianFormatter.priceCompact(v))
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3)).foregroundStyle(Theme.inkTertiary.opacity(0.2))
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                        .font(Theme.serialNumberFont(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3)).foregroundStyle(Theme.inkTertiary.opacity(0.2))
                }
            }
            .chartOverlay { proxy in
                GeometryReader { geo in
                    Rectangle().fill(.clear).contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 0)
                                .onChanged { val in
                                    guard let frame = proxy.plotFrame else { return }
                                    let x = val.location.x - geo[frame].origin.x
                                    guard let date = proxy.value(atX: x, as: Date.self) else { return }
                                    selectedPoint = filteredPrices.min(by: {
                                        abs($0.parsedDate.timeIntervalSince(date)) < abs($1.parsedDate.timeIntervalSince(date))
                                    })
                                }
                                .onEnded { _ in
                                    withAnimation(.easeOut(duration: 0.2)) { selectedPoint = nil }
                                }
                        )
                        .simultaneousGesture(
                            MagnificationGesture()
                                .onChanged { scale in
                                    let newZoom = baseZoom * scale
                                    zoomFactor = max(1.0, min(newZoom, Double(history.count) / 10.0))
                                }
                                .onEnded { _ in baseZoom = zoomFactor }
                        )
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.30)
            .padding(.horizontal, Theme.Spacing.small)

            // Volume bars mini chart
            if !filteredPrices.isEmpty {
                Chart {
                    ForEach(filteredPrices) { p in
                        BarMark(
                            x: .value("Date", p.parsedDate),
                            y: .value("Volume", p.volume)
                        )
                        .foregroundStyle(p.close >= p.open ? Theme.bullGreen.opacity(0.5) : Theme.bearRed.opacity(0.5))
                    }
                }
                .chartYAxis(.hidden)
                .chartXAxis(.hidden)
                .frame(height: 32)
                .padding(.horizontal, Theme.Spacing.small)
            }

            // Controls: period + toggles
            HStack(spacing: Theme.Spacing.none) {
                // Period selector
                ForEach(Array(zip(periods, periodLabels)), id: \.0) { period, label in
                    Button(label) {
                        HapticManager.selection()
                        selectedPeriod = period
                    }
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.0)
                    .foregroundStyle(selectedPeriod == period ? Theme.securityGold : Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)
                    .background(selectedPeriod == period ? Theme.securityGold.opacity(0.12) : Color.clear)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                }

                Spacer()

                // Candlestick toggle
                Button {
                    HapticManager.selection()
                    showCandlestick.toggle()
                } label: {
                    Image(systemName: showCandlestick ? "chart.bar.fill" : "chart.line.uptrend.xyaxis")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(.horizontal, Theme.Spacing.medium)

                // Nifty benchmark toggle
                Button {
                    HapticManager.selection()
                    showNifty.toggle()
                } label: {
                    Text("NIFTY")
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.0)
                        .foregroundStyle(showNifty ? Theme.inkSecondary : Theme.inkTertiary)
                        .strikethrough(!showNifty, color: Theme.inkTertiary)
                }
                .padding(.trailing, Theme.Spacing.medium)
            }
            .padding(.horizontal, Theme.Spacing.card)
        }
    }
}

// MARK: - Stock Profile View (Phase 2)

struct StockProfileView: View {
    let ticker: String
    let exchange: String

    @StateObject private var vm: StockProfileViewModel
    @State private var activeTab = 0
    @Environment(\.dismiss) var dismiss

    init(ticker: String, exchange: String = "NSE") {
        self.ticker = ticker
        self.exchange = exchange
        _vm = StateObject(wrappedValue: StockProfileViewModel(ticker: ticker, exchange: exchange))
    }

    var body: some View {
        // NOTE: No NavigationStack here — this view is always pushed into a
        // parent stack via navigationDestination. A nested NavigationStack
        // breaks navigation (dark screen → auto-pop) and the back button.
        ZStack {
            DenominationBackground(denomination: .twoHundred)

                VStack(spacing: Theme.Spacing.none) {
                    // Immersive hero chart
                    if let hist = vm.history, !hist.prices.isEmpty {
                        let closes = hist.prices.map(\.close)
                        let dates = hist.prices.map(\.parsedDate)
                        let price = vm.quickInfo?.price ?? closes.last ?? 0
                        let changePct = vm.quickInfo?.changePercent ?? 0
                        ImmersiveStockHeroChart(
                            prices: closes,
                            changePercent: changePct,
                            currentPrice: price,
                            dates: dates
                        )
                        .padding(.bottom, Theme.Spacing.standard)
                    } else if vm.chartLoading {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                            .fill(Theme.inkTertiary.opacity(0.08))
                            .frame(height: UIScreen.main.bounds.height * 0.26)
                            .shimmerPlaceholder(isLoading: true)
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.bottom, Theme.Spacing.standard)
                    }

                    // Tab bar
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Theme.Spacing.none) {
                            ForEach(Array(tabItems.enumerated()), id: \.offset) { idx, item in
                                Button {
                                    HapticManager.selection()
                                    withAnimation(.spring(response: 0.3, dampingFraction: 0.85)) {
                                        activeTab = idx
                                    }
                                } label: {
                                    VStack(spacing: Theme.Spacing.small) {
                                        Text(item.label.uppercased())
                                            .font(Theme.officialStampFont(size: 9))
                                            .tracking(1.0)
                                            .foregroundStyle(activeTab == idx ? Theme.securityGold : Theme.inkTertiary)
                                        Rectangle()
                                            .fill(activeTab == idx ? Theme.securityGold : Color.clear)
                                            .frame(height: 1.5)
                                    }
                                    .padding(.horizontal, Theme.Spacing.card)
                                    .padding(.vertical, Theme.Spacing.standard)
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                    }
                    .background(Theme.canvasDeep)

                    SectionDivider()

                    // Tab content
                    TabView(selection: $activeTab) {
                        overviewTab.tag(0)
                        holdersTab.tag(1)
                        newsTab.tag(2)
                        updatesTab.tag(3)
                        chartTab.tag(4)
                        financialsTab.tag(5)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                    .animation(.spring(response: 0.35, dampingFraction: 0.85), value: activeTab)
                }
            }
            .navigationTitle(ticker.uppercased())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { dismiss() } label: {
                        Image(systemName: "chevron.left")
                            .foregroundStyle(Theme.inkPrimary)
                            .padding(Theme.Spacing.medium)
                            .background(Theme.canvasDeep)
                            .clipShape(Circle())
                    }
                }
            }
        .task { await vm.fetchChart() }
    }

    private var tabItems: [(label: String, icon: String)] {
        [
            ("Overview", "doc.text"),
            ("Holders", "person.3"),
            ("News", "newspaper"),
            ("Updates", "bell"),
            ("Chart", "chart.xyaxis.line"),
            ("Financials", "tablecells"),
        ]
    }

    // MARK: - Tab: Overview

    @ViewBuilder
    private var overviewTab: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                if vm.overviewLoading {
                    skeletonBlock(rows: 6)
                } else if let info = vm.quickInfo {
                    overviewContent(info: info)
                } else {
                    emptyState(message: "Overview unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchOverview() }
    }

    @ViewBuilder
    private func overviewContent(info: QuickInfo) -> some View {
        // Price hero
        VStack(spacing: Theme.Spacing.small) {
            Text(ticker.uppercased())
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            Text(info.price != nil ? IndianFormatter.price(info.price!) : "—")
                .font(Theme.serialNumberFont(size: 32, relativeTo: .largeTitle))
                .foregroundStyle(Theme.inkPrimary)
            let changePct = info.changePercent ?? 0.0
            let up = changePct >= 0
            Text(String(format: "%@%.2f%%", up ? "▲ " : "▼ ", abs(changePct)))
                .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()

        SectionDivider().padding(.horizontal, 0)

        // Key metrics grid
        let metrics: [(String, String, String, String)] = [
            ("P/E Ratio", info.peRatio.map { String(format: "%.1f", $0) } ?? "—", "P/E RATIO", "Price-to-earnings ratio: share price divided by annual earnings per share. Higher = market expects more growth."),
            ("52W High", info.week52High.map { IndianFormatter.price($0) } ?? "—", "52-WEEK HIGH", "The highest price the stock traded at in the past 52 weeks."),
            ("52W Low", info.week52Low.map { IndianFormatter.price($0) } ?? "—", "52-WEEK LOW", "The lowest price the stock traded at in the past 52 weeks."),
            ("Sector", info.sector ?? "—", "SECTOR", "The broad industry segment this company operates in."),
        ]

        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.card) {
            ForEach(metrics, id: \.0) { label, value, glossaryTerm, glossaryDef in
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(label.uppercased())
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.0)
                        .foregroundStyle(Theme.inkTertiary)
                        .financeTerm(label)
                    Text(value)
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.standard)
                .banknoteCard()
                .glossaryTerm(glossaryTerm, definition: glossaryDef)
            }
        }

        // AI Signal badge
        if let signal = info.signal {
            HStack(spacing: Theme.Spacing.standard) {
                BanknoteSignalBadge(text: signal.rawValue, color: signal.color, rotation: -2)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("AI SIGNAL")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    Text("Based on multi-agent Bull/Bear dialectic analysis")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
            }
            .padding(Theme.Spacing.standard)
            .banknoteCard()
            .glossaryTerm("AI SIGNAL", definition: "Signal computed by a dialectical debate between a Bull researcher and a Bear researcher, with Bear findings weighted 1.5× to preserve capital.")
        }
    }

    // MARK: - Tab: Holders

    @ViewBuilder
    private var holdersTab: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                if vm.holdersLoading {
                    skeletonBlock(rows: 5)
                } else if let ratings = vm.analystRatings {
                    holdersContent(ratings: ratings)
                } else {
                    emptyState(message: "Holder data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchHolders() }
    }

    @ViewBuilder
    private func holdersContent(ratings: AnalystRatingsResponse) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("ANALYST CONSENSUS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.top, Theme.Spacing.small)

            HStack(spacing: Theme.Spacing.card) {
                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("\(ratings.buy)")
                        .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                        .foregroundStyle(Theme.bullGreen)
                    Text("BUY").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
                .frame(maxWidth: .infinity)
                .glossaryTerm("BUY", definition: "Analysts recommending to purchase the stock, expecting price appreciation.")

                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("\(ratings.hold)")
                        .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                        .foregroundStyle(Theme.holdAmber)
                    Text("HOLD").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
                .frame(maxWidth: .infinity)

                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("\(ratings.sell)")
                        .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                        .foregroundStyle(Theme.bearRed)
                    Text("SELL").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
                .frame(maxWidth: .infinity)
                .glossaryTerm("SELL", definition: "Analysts recommending to exit the position, expecting price decline or better alternatives.")
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()

            if let consensus = ratings.consensus {
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("ANALYST CONSENSUS")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)
                        Text(consensus.uppercased())
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .title3))
                            .foregroundStyle(Theme.securityGold)
                    }
                    Spacer()
                    BanknoteSignalBadge(text: consensus.uppercased(), color: Theme.securityGold, rotation: 1)
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
        }
    }

    // MARK: - Tab: News

    @ViewBuilder
    private var newsTab: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                Text("NEWS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, Theme.Spacing.small)

                emptyState(message: "Pull news via AI Analysis tab for full sentiment coverage")
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
    }

    // MARK: - Tab: Updates

    @ViewBuilder
    private var updatesTab: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                Text("CORPORATE UPDATES")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, Theme.Spacing.small)

                emptyState(message: "Earnings calendar & corporate actions available via EarningsDashboard")
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
    }

    // MARK: - Tab: Chart

    @ViewBuilder
    private var chartTab: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.standard) {
                if vm.chartLoading {
                    ProgressView().tint(Theme.securityGold).scaleEffect(1.3).padding(40)
                } else if let hist = vm.history, !hist.prices.isEmpty {
                    InteractivePriceChartView(
                        history: hist.prices,
                        niftyHistory: vm.niftyHistory,
                        ticker: ticker
                    )
                    .padding(.vertical, Theme.Spacing.standard)
                } else {
                    emptyState(message: "Price history unavailable")
                }
            }
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchChart() }
    }

    // MARK: - Tab: Financials

    @ViewBuilder
    private var financialsTab: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                if vm.financialsLoading {
                    skeletonBlock(rows: 8)
                } else {
                    if !vm.quarterlyFinancials.isEmpty {
                        financialsTable(quarters: vm.quarterlyFinancials)
                    }
                    if let piotroski = vm.piotroski {
                        piotroskiCard(data: piotroski)
                    }
                    if vm.quarterlyFinancials.isEmpty && vm.piotroski == nil {
                        emptyState(message: "Financial data unavailable")
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchFinancials() }
    }

    @ViewBuilder
    private func financialsTable(quarters: [QuarterlyFinancial]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY FINANCIALS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            let shown = Array(quarters.prefix(8))
            let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding

            // Header
            HStack(spacing: Theme.Spacing.none) {
                Text("QTR").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.28, alignment: .leading)
                Text("REVENUE").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.36, alignment: .trailing)
                Text("PAT").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.36, alignment: .trailing)
            }
            .padding(.horizontal, Theme.Spacing.medium)
            .glossaryTerm("PAT", definition: "Profit After Tax — the net earnings of the company after all expenses and taxes, also called Net Profit.")

            ForEach(shown) { q in
                HStack(spacing: Theme.Spacing.none) {
                    Text(q.label)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.28, alignment: .leading)
                    Text(IndianFormatter.priceCompact(q.revenue))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.36, alignment: .trailing)
                    let profitUp = q.netProfit >= 0
                    Text(IndianFormatter.priceCompact(q.netProfit))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(profitUp ? Theme.bullGreen : Theme.bearRed)
                        .frame(width: colW * 0.36, alignment: .trailing)
                }
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .overlay(Rectangle().fill(Theme.borderFine).frame(height: 0.5), alignment: .bottom)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    @ViewBuilder
    private func piotroskiCard(data: PiotroskiData) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("PIOTROSKI F-SCORE")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    if let score = data.score {
                        Text("\(score) / 9")
                            .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                            .foregroundStyle(score >= 7 ? Theme.bullGreen : score >= 4 ? Theme.holdAmber : Theme.bearRed)
                    }
                }
                .glossaryTerm("PIOTROSKI F-SCORE", definition: "A 9-point financial health score. Scores 0–3 indicate weak financials, 4–6 are neutral, and 7–9 indicate strong fundamentals. Developed by Joseph Piotroski to identify financially sound value stocks.")
                Spacer()
                if let score = data.score {
                    let quality = score >= 7 ? "STRONG" : score >= 4 ? "MODERATE" : "WEAK"
                    BanknoteSignalBadge(
                        text: quality,
                        color: score >= 7 ? Theme.bullGreen : score >= 4 ? Theme.holdAmber : Theme.bearRed,
                        rotation: -2
                    )
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Shared helpers

    @ViewBuilder
    private func skeletonBlock(rows: Int) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            ForEach(0..<rows, id: \.self) { i in
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.08))
                    .frame(maxWidth: .infinity)
                    .frame(height: 20 + CGFloat(i % 2) * 8)
                    .shimmerPlaceholder(isLoading: true)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    @ViewBuilder
    private func emptyState(message: String) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "doc.questionmark")
                .font(.largeTitle)
                .foregroundStyle(Theme.inkTertiary)
            Text(message)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .body))
                .foregroundStyle(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.xLarge)
        .banknoteCard()
    }
}
