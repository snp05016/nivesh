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
    @State private var showSMA: Set<Int> = [20, 50, 200]
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
            .navigationBarBackButtonHidden(true)  // we provide our own chevron; hide the system one
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
                Text("LATEST NEWS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, Theme.Spacing.small)

                if vm.overviewLoading {
                    skeletonBlock(rows: 5)
                } else if let news = vm.quickInfo?.recentNews, !news.isEmpty {
                    ForEach(news) { item in
                        newsCard(item)
                    }
                } else {
                    emptyState(message: "No recent news for this stock")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchOverview() }
    }

    @ViewBuilder
    private func newsCard(_ item: NewsItem) -> some View {
        Link(destination: URL(string: item.link) ?? URL(string: "https://www.google.com")!) {
            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkTertiary.opacity(0.08))
                    }
                    .frame(width: 64, height: 64)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(item.title)
                        .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                        .multilineTextAlignment(.leading)
                        .lineLimit(3)
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(item.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.securityGold)
                        if let t = item.publishTime {
                            Text("•").foregroundStyle(Theme.inkTertiary)
                            Text(Date(timeIntervalSince1970: TimeInterval(t)), style: .relative)
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
                Spacer(minLength: Theme.Spacing.tight)
                Image(systemName: "arrow.up.right")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
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
            VStack(spacing: Theme.Spacing.xLarge) {
                if vm.chartLoading {
                    skeletonBlock(rows: 3)
                    skeletonBlock(rows: 3)
                    skeletonBlock(rows: 3)
                } else if let hist = vm.history, !hist.prices.isEmpty {
                    InteractivePriceChartView(
                        history: hist.prices,
                        niftyHistory: vm.niftyHistory,
                        ticker: ticker
                    )

                    chartSection_RSI(hist: hist)
                    chartSection_SMA(hist: hist)

                    if !vm.quarterlyFinancials.isEmpty {
                        chartSection_QuarterlyRevenue()
                        chartSection_QuarterlyPAT()
                        chartSection_PATMargin()
                    }

                    if let qInfo = vm.quickInfo {
                        chartSection_Shareholding(qInfo: qInfo)
                        chartSection_Profitability(qInfo: qInfo)
                    }

                    if !vm.promoterHistory.isEmpty {
                        chartSection_PromoterHistory()
                    }
                } else {
                    emptyState(message: "Price history unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchChart() }
        .task { await vm.fetchFinancials() }
    }

    // MARK: - Chart Helpers

    private func computeRSI(_ prices: [OHLCVPoint], period: Int = 14) -> [(date: Date, rsi: Double)] {
        guard prices.count > period else { return [] }
        var gains: [Double] = []
        var losses: [Double] = []
        for i in 1..<prices.count {
            let diff = prices[i].close - prices[i-1].close
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
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

    private func computeSMA(_ prices: [OHLCVPoint], period: Int) -> [(date: Date, value: Double)] {
        guard prices.count >= period else { return [] }
        var result: [(date: Date, value: Double)] = []
        for i in period...prices.count {
            let slice = prices[(i-period)..<i]
            let avg = slice.map(\.close).reduce(0, +) / Double(period)
            result.append((date: prices[i-1].parsedDate, value: avg))
        }
        return result
    }

    // MARK: - Chart 2: RSI Oscillator

    @ViewBuilder
    private func chartSection_RSI(hist: StockHistoryResponse) -> some View {
        let rsiData = computeRSI(hist.prices)
        if !rsiData.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("RSI (14)")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                Chart {
                    ForEach(rsiData, id: \.date) { pt in
                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("RSI", pt.rsi)
                        )
                        .foregroundStyle(Theme.securityGold)
                    }
                    RuleMark(y: .value("Overbought", 70))
                        .foregroundStyle(Theme.bearRed.opacity(0.4))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    RuleMark(y: .value("Oversold", 30))
                        .foregroundStyle(Theme.bullGreen.opacity(0.4))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                }
                .chartYScale(domain: 0...100)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 2)) { _ in
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    }
                }
                .chartYAxis {
                    AxisMarks(values: [0, 30, 50, 70, 100]) { value in
                        AxisValueLabel()
                    }
                }
                .frame(height: UIScreen.main.bounds.height * 0.25)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    // MARK: - Chart 3: Moving Averages

    @ViewBuilder
    private func chartSection_SMA(hist: StockHistoryResponse) -> some View {
        let closes = hist.prices
        let sma20 = computeSMA(closes, period: 20)
        let sma50 = computeSMA(closes, period: 50)
        let sma200 = computeSMA(closes, period: 200)
        let isUp = (closes.last?.close ?? 0) >= (closes.first?.close ?? 0)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("MOVING AVERAGES")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.tight) {
                ForEach([(20, Theme.securityGold), (50, Theme.bearRed), (200, Theme.avatarBlue)], id: \.0) { period, color in
                    Button {
                        HapticManager.selection()
                        if showSMA.contains(period) { showSMA.remove(period) }
                        else { showSMA.insert(period) }
                    } label: {
                        Text("SMA \(period)")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(showSMA.contains(period) ? color : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.medium)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(showSMA.contains(period) ? color.opacity(0.12) : Theme.canvasDeep)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(EKPressStyle())
                }
            }

            Chart {
                ForEach(closes, id: \.date) { pt in
                    AreaMark(
                        x: .value("Date", pt.parsedDate),
                        y: .value("Price", pt.close)
                    )
                    .foregroundStyle(isUp ? Theme.bullGreen.opacity(0.08) : Theme.bearRed.opacity(0.08))
                }
                if showSMA.contains(20) {
                    ForEach(sma20, id: \.date) { pt in
                        LineMark(x: .value("Date", pt.date), y: .value("SMA20", pt.value))
                            .foregroundStyle(Theme.securityGold)
                    }
                }
                if showSMA.contains(50) {
                    ForEach(sma50, id: \.date) { pt in
                        LineMark(x: .value("Date", pt.date), y: .value("SMA50", pt.value))
                            .foregroundStyle(Theme.bearRed)
                    }
                }
                if showSMA.contains(200) {
                    ForEach(sma200, id: \.date) { pt in
                        LineMark(x: .value("Date", pt.date), y: .value("SMA200", pt.value))
                            .foregroundStyle(Theme.avatarBlue)
                    }
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel()
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Chart 4: Quarterly Revenue

    @ViewBuilder
    private func chartSection_QuarterlyRevenue() -> some View {
        let quarters = Array(vm.quarterlyFinancials.prefix(8).reversed())
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY REVENUE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Chart {
                ForEach(quarters, id: \.label) { q in
                    BarMark(
                        x: .value("Quarter", q.label),
                        y: .value("Revenue", q.revenue)
                    )
                    .foregroundStyle(Theme.securityGold.opacity(0.85))

                    if q.revenue > 0 {
                        PointMark(
                            x: .value("Quarter", q.label),
                            y: .value("Revenue", q.revenue)
                        )
                        .symbolSize(30)
                        .foregroundStyle(Theme.securityGold)
                        .annotation(position: .top) {
                            Text(IndianFormatter.priceCompact(q.revenue))
                                .font(Theme.microLabel(size: 8))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
            }
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel()
                }
                AxisMarks { _ in
                    AxisValueLabel(anchor: .top) {
                        Text("₹ Cr")
                    }
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Chart 5: Quarterly PAT

    @ViewBuilder
    private func chartSection_QuarterlyPAT() -> some View {
        let quarters = Array(vm.quarterlyFinancials.prefix(8).reversed())
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY PAT")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .glossaryTerm("PAT", definition: "Profit After Tax — net earnings after all expenses, interest, and taxes are deducted. The bottom-line profit available to shareholders.")

            Chart {
                ForEach(quarters, id: \.label) { q in
                    BarMark(
                        x: .value("Quarter", q.label),
                        y: .value("PAT", q.netProfit)
                    )
                    .foregroundStyle(by: .value("Sign", q.netProfit >= 0 ? "positive" : "negative"))

                    PointMark(
                        x: .value("Quarter", q.label),
                        y: .value("PAT", q.netProfit)
                    )
                    .symbolSize(30)
                    .foregroundStyle(q.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed)
                    .annotation(position: q.netProfit >= 0 ? .top : .bottom) {
                        Text(IndianFormatter.priceCompact(q.netProfit))
                            .font(Theme.microLabel(size: 8))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                RuleMark(y: .value("Zero", 0))
                    .foregroundStyle(Theme.inkTertiary.opacity(0.4))
            }
            .chartForegroundStyleScale(["positive": Theme.bullGreen, "negative": Theme.bearRed])
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel()
                }
                AxisMarks { _ in
                    AxisValueLabel(anchor: .top) {
                        Text("₹ Cr")
                    }
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Chart 6: PAT Margin %

    @ViewBuilder
    private func chartSection_PATMargin() -> some View {
        let quarters = Array(vm.quarterlyFinancials.prefix(8).reversed())
        let margins = quarters.map { q -> (label: String, margin: Double) in
            (q.label, q.revenue > 0 ? (q.netProfit / q.revenue) * 100 : 0)
        }
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PAT MARGIN %")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if !margins.isEmpty {
                Chart {
                    ForEach(margins, id: \.label) { pt in
                        LineMark(
                            x: .value("Quarter", pt.label),
                            y: .value("Margin", pt.margin)
                        )
                        .foregroundStyle(Theme.securityGold)

                        AreaMark(
                            x: .value("Quarter", pt.label),
                            y: .value("Margin", pt.margin)
                        )
                        .foregroundStyle(Theme.securityGold.opacity(0.08))

                        PointMark(
                            x: .value("Quarter", pt.label),
                            y: .value("Margin", pt.margin)
                        )
                        .symbolSize(30)
                        .foregroundStyle(Theme.securityGold)
                    }
                }
                .chartXAxis {
                    AxisMarks { _ in
                        AxisValueLabel()
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisValueLabel() {
                            Text("\(value.as(Double.self)?.formatted(.number.precision(.fractionLength(0))) ?? "")%")
                        }
                    }
                }
                .frame(height: UIScreen.main.bounds.height * 0.25)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Chart 7: Shareholding Breakdown

    @ViewBuilder
    private func chartSection_Shareholding(qInfo: QuickInfo) -> some View {
        let promoter = qInfo.promoterHoldingPct ?? 0
        let fii = qInfo.fiiHoldingPct ?? 0
        let dii = qInfo.diiHoldingPct ?? 0
        let publicHolding = max(0, 100 - promoter - fii - dii)
        guard promoter > 0 || fii > 0 || dii > 0 else {
            EmptyView()
            return
        }

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("SHAREHOLDING PATTERN")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Chart {
                BarMark(x: .value("Pct", promoter), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.securityGold)
                BarMark(x: .value("Pct", fii), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.bullGreen)
                BarMark(x: .value("Pct", dii), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.avatarBlue)
                BarMark(x: .value("Pct", publicHolding), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.inkTertiary.opacity(0.4))
            }
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel() {
                        Text("\($0.as(Double.self)?.formatted(.number.precision(.fractionLength(0))) ?? "")%")
                    }
                }
            }
            .frame(height: 44)

            // Legend
            HStack(spacing: Theme.Spacing.standard) {
                legendDot(color: Theme.securityGold, label: "Promoter", value: promoter)
                legendDot(color: Theme.bullGreen, label: "FII", value: fii)
                legendDot(color: Theme.avatarBlue, label: "DII", value: dii)
                legendDot(color: Theme.inkTertiary.opacity(0.4), label: "Public", value: publicHolding)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func legendDot(color: Color, label: String, value: Double) -> some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text("\(label) \(String(format: "%.1f", value))%")
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    // MARK: - Chart 8: Promoter Holding History

    @ViewBuilder
    private func chartSection_PromoterHistory() -> some View {
        let history = vm.promoterHistory
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER HOLDING HISTORY")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if !history.isEmpty {
                Chart {
                    ForEach(history, id: \.period) { pt in
                        LineMark(
                            x: .value("Period", pt.period),
                            y: .value("Holding", pt.promoter)
                        )
                        .foregroundStyle(Theme.securityGold)

                        AreaMark(
                            x: .value("Period", pt.period),
                            y: .value("Holding", pt.promoter)
                        )
                        .foregroundStyle(Theme.securityGold.opacity(0.08))

                        PointMark(
                            x: .value("Period", pt.period),
                            y: .value("Holding", pt.promoter)
                        )
                        .symbolSize(25)
                        .foregroundStyle(Theme.securityGold)
                    }
                }
                .chartXAxis {
                    AxisMarks { _ in
                        AxisValueLabel()
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisValueLabel() {
                            Text("\(value.as(Double.self)?.formatted(.number.precision(.fractionLength(1))) ?? "")%")
                        }
                    }
                }
                .frame(height: UIScreen.main.bounds.height * 0.25)

                if history.count >= 2 {
                    let latest = history.last?.promoter ?? 0
                    let prev = history[history.count - 2].promoter
                    if latest < prev {
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "arrow.down.right")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(Theme.bearRed)
                            Text("Promoter holding declined from \(String(format: "%.1f", prev))% to \(String(format: "%.1f", latest))%")
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.bearRed)
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: - Chart 9: ROE vs ROCE

    @ViewBuilder
    private func chartSection_Profitability(qInfo: QuickInfo) -> some View {
        let roe = qInfo.roePct
        let roce = qInfo.rocePct
        let pe = qInfo.peRatio
        guard roe != nil || roce != nil || pe != nil else {
            EmptyView()
            return
        }

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROFITABILITY RATIOS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Chart {
                if let roe = roe {
                    BarMark(x: .value("Metric", "ROE"), y: .value("Pct", roe))
                        .foregroundStyle(Theme.bullGreen)
                        .annotation(position: .top) {
                            Text(String(format: "%.1f%%", roe))
                                .font(Theme.microLabel(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                }
                if let roce = roce {
                    BarMark(x: .value("Metric", "ROCE"), y: .value("Pct", roce))
                        .foregroundStyle(Theme.securityGold)
                        .annotation(position: .top) {
                            Text(String(format: "%.1f%%", roce))
                                .font(Theme.microLabel(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                }
                if let pe = pe {
                    BarMark(x: .value("Metric", "P/E"), y: .value("Pct", pe))
                        .foregroundStyle(Theme.avatarBlue)
                        .annotation(position: .top) {
                            Text(String(format: "%.1f", pe))
                                .font(Theme.microLabel(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                }
            }
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel()
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)

            HStack {
                glossaryTermInline("ROE", definition: "Return on Equity — measures how efficiently a company generates profit from shareholders' money. Higher = better capital deployment.")
                Spacer()
                glossaryTermInline("ROCE", definition: "Return on Capital Employed — measures how efficiently a company generates profit from its total capital. Higher = better capital deployment.")
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func glossaryTermInline(_ term: String, definition: String) -> some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle().fill(Theme.securityGold.opacity(0.3)).frame(width: 4, height: 4)
            Text(term)
                .font(Theme.microLabel(size: 9))
                .foregroundStyle(Theme.inkTertiary)
        }
        .glossaryTerm(term, definition: definition)
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
                    if let fScore = data.fScore {
                        let max = data.maxPossible ?? 9
                        Text("\(fScore) / \(max)")
                            .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                            .foregroundStyle(fScore >= 7 ? Theme.bullGreen : fScore >= 4 ? Theme.holdAmber : Theme.bearRed)
                    }
                }
                .glossaryTerm("PIOTROSKI F-SCORE", definition: "A 9-point financial health score. Scores 0–3 indicate weak financials, 4–6 are neutral, and 7–9 indicate strong fundamentals. Developed by Joseph Piotroski to identify financially sound value stocks.")
                Spacer()
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    if let grade = data.grade {
                        let gradeColor: Color = {
                            switch grade {
                            case "STRONG": return Theme.bullGreen
                            case "GOOD": return Theme.bullGreenLight
                            case "DISTRESS": return Theme.bearRed
                            case "WEAK": return Theme.bearRedLight
                            default: return Theme.holdAmber
                            }
                        }()
                        BanknoteSignalBadge(text: grade, color: gradeColor, rotation: -2)
                    }
                    if let confidence = data.confidence {
                        Text(confidence)
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }

            if let checks = data.checks, !checks.isEmpty {
                GuillocheDivider()

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())],
                          spacing: Theme.Spacing.tight) {
                    ForEach(Array(checks.keys.sorted()), id: \.self) { key in
                        HStack(spacing: Theme.Spacing.small) {
                            Circle()
                                .fill(checks[key] == "PASS" ? Theme.bullGreen : Theme.bearRed)
                                .frame(width: 6, height: 6)
                            Text(formatCheckLabel(key))
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(1)
                            Spacer()
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func formatCheckLabel(_ key: String) -> String {
        key.replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.prefix(1).uppercased() + $0.dropFirst().lowercased() }
            .joined(separator: " ")
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
