import SwiftUI
import Charts
import UIKit

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
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 14))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        HStack(spacing: Theme.Spacing.small) {
                            Text("H").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(p.high)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bullGreen)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        }
                        HStack(spacing: Theme.Spacing.small) {
                            Text("L").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(p.low)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        }
                    }
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("VOL").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.priceCompact(p.volume)).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkSecondary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                    }
                } else if let last = filteredPrices.last {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(ticker.uppercased()).font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.securityGold)
                        Text(IndianFormatter.price(last.close))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 16))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    if let first = filteredPrices.first, first.close != 0 {
                        let returnPct = (last.close - first.close) / first.close * 100
                        let up = returnPct >= 0
                        VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                            Text("PERIOD RETURN").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                            Text(String(format: "%@%.2f%%", up ? "+" : "", returnPct))
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
                        }
                        .explainableTerm("Period Return")
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
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
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
                            DragGesture(minimumDistance: 2)
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
                        .highPriorityGesture(
                            MagnificationGesture()
                                .onChanged { scale in
                                    let newZoom = baseZoom * scale
                                    zoomFactor = max(1.0, min(newZoom, Double(history.count) / 10.0))
                                }
                                .onEnded { _ in baseZoom = zoomFactor }
                        )
                }
            }
            .frame(height: 260)
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
                .frame(height: 36)
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
                    .buttonStyle(EKPressStyle())
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
                .buttonStyle(EKPressStyle())

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
                .buttonStyle(EKPressStyle())
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
    @State private var chartPeriod = "1y"

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
                        // Period selector below hero chart
                        HStack(spacing: Theme.Spacing.tight) {
                            ForEach(Array(zip(["1mo","3mo","6mo","1y","2y","5y","max"], ["1M","3M","6M","1Y","2Y","5Y","ALL"])), id: \.0) { period, label in
                                Button {
                                    HapticManager.selection()
                                    chartPeriod = period
                                    Task { await vm.fetchChart(period: period) }
                                } label: {
                                    Text(label)
                                        .font(Theme.officialStampFont(size: 8))
                                        .tracking(0.8)
                                        .foregroundStyle(chartPeriod == period ? Theme.securityGold : Theme.inkTertiary)
                                        .padding(.horizontal, Theme.Spacing.medium)
                                        .padding(.vertical, Theme.Spacing.small)
                                        .background(chartPeriod == period ? Theme.securityGold.opacity(0.12) : Theme.canvasDeep)
                                        .clipShape(Capsule())
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.bottom, Theme.Spacing.standard)
                    } else if vm.chartLoading {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                            .fill(Theme.inkTertiary.opacity(0.08))
                            .frame(height: 240)
                            .shimmerPlaceholder(isLoading: true)
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.bottom, Theme.Spacing.standard)
                    } else if let info = vm.quickInfo {
                        // Fallback hero — price header from quickInfo when chart data unavailable
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(ticker.uppercased())
                                .font(Theme.officialStampFont(size: 10))
                                .tracking(1.5)
                                .foregroundStyle(Theme.inkTertiary)
                            Text(info.price != nil ? IndianFormatter.price(info.price!) : "—")
                                .font(.largeTitle.weight(.bold))
                                .monospaced()
                                .foregroundStyle(Theme.inkPrimary)
                            let change = info.changePercent ?? 0
                            HStack(spacing: Theme.Spacing.tight) {
                                Text((change >= 0 ? "▲ +" : "▼ ") + String(format: "%.2f%%", abs(change)))
                                    .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote).weight(.semibold))
                                    .foregroundStyle(change >= 0 ? Theme.bullGreen : Theme.bearRed)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.vertical, Theme.Spacing.card)
                        .padding(.bottom, Theme.Spacing.standard)
                        .background(
                            (info.changePercent ?? 0) >= 0
                                ? Theme.bullGreen.opacity(0.06) : Theme.bearRed.opacity(0.06)
                        )
                    } else if let error = vm.stockProfileError {
                        // Detailed error display — copy-paste ready
                        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                            HStack(spacing: Theme.Spacing.tight) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundStyle(Theme.bearRed)
                                Text("STOCK PROFILE ERROR")
                                    .font(Theme.officialStampFont(size: 10))
                                    .tracking(1.5)
                                    .foregroundStyle(Theme.bearRed)
                            }
                            Text(error)
                                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary)
                                .textSelection(.enabled)
                                .fixedSize(horizontal: false, vertical: true)
                            Button {
                                UIPasteboard.general.string = error
                                HapticManager.success()
                            } label: {
                                HStack(spacing: Theme.Spacing.small) {
                                    Image(systemName: "doc.on.doc")
                                        .font(.caption)
                                    Text("COPY ERROR TO CLIPBOARD")
                                        .font(Theme.officialStampFont(size: 9))
                                        .tracking(0.8)
                                }
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.medium)
                                .padding(.vertical, Theme.Spacing.tight)
                                .background(Theme.securityGold.opacity(0.1))
                                .clipShape(Capsule())
                            }
                            .buttonStyle(EKPressStyle())
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(Theme.Spacing.card)
                        .background(Theme.canvasDeep)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
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

                    // Tab content (4 consolidated tabs)
                    TabView(selection: $activeTab) {
                        // 0: Overview = Overview + Chart + Financials
                        ScrollView {
                            LazyVStack(spacing: Theme.sectionSpacing) {
                                OverviewTabView(ticker: ticker, vm: vm)
                                if let hist = vm.history, !hist.prices.isEmpty {
                                    GuillocheDivider()
                                        .padding(.horizontal, Theme.screenPadding)
                                    InteractivePriceChartView(
                                        history: hist.prices,
                                        niftyHistory: vm.niftyHistory,
                                        ticker: ticker
                                    )
                                    .padding(.horizontal, Theme.screenPadding)
                                }
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                                FinancialsTabView(vm: vm)
                            }
                            .padding(.bottom, Theme.sectionSpacing)
                        }
                        .tag(0)

                        // 1: News & Events = News + Updates
                        ScrollView {
                            LazyVStack(spacing: Theme.sectionSpacing) {
                                NewsTabView(vm: vm)
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                                UpdatesTabView()
                            }
                            .padding(.bottom, Theme.sectionSpacing)
                        }
                        .tag(1)

                        // 2: Ownership = Holders + Governance
                        ScrollView {
                            LazyVStack(spacing: Theme.sectionSpacing) {
                                HoldersTabView(vm: vm)
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                                GovernanceTabView(ticker: ticker, vm: vm)
                            }
                            .padding(.bottom, Theme.sectionSpacing)
                        }
                        .tag(2)

                        // 3: Macro Analysis
                        MacroTabView(ticker: ticker, exchange: exchange, vm: vm).tag(3)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                    .animation(.spring(response: 0.35, dampingFraction: 0.85), value: activeTab)
                    .frame(maxHeight: .infinity)
                }
            }
            .crashGuard("StockProfile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text(ticker.uppercased())
                        .font(Theme.officialStampFont(size: 11))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
            .toolbarBackground(Theme.canvas, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        .task { await vm.fetchStockProfile() }
    }

    private var tabItems: [(label: String, icon: String)] {
        [
            ("Overview", "doc.text"),
            ("News & Events", "newspaper"),
            ("Ownership", "person.3"),
            ("Macro", "globe.asia.australia"),
        ]
    }
}
