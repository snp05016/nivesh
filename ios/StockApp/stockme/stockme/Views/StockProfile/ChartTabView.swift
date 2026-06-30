import SwiftUI
import Charts

struct ChartTabView: View {
    let ticker: String
    @ObservedObject var vm: StockProfileViewModel
    @State private var showSMA: Set<Int> = [20, 50, 200]

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.xLarge) {
                if vm.chartLoading {
                    SPSkeletonBlock(rows: 3)
                    SPSkeletonBlock(rows: 3)
                    SPSkeletonBlock(rows: 3)
                } else if let hist = vm.history, !hist.prices.isEmpty {
                    InteractivePriceChartView(
                        history: hist.prices,
                        niftyHistory: vm.niftyHistory,
                        ticker: ticker
                    )

                    RSIChartSectionView(prices: hist.prices)
                    SMASectionView(prices: hist.prices)

                    if !vm.quarterlyFinancials.isEmpty {
                        QuarterlyRevenueSectionView(quarters: vm.quarterlyFinancials)
                        QuarterlyPATSectionView(quarters: vm.quarterlyFinancials)
                        PATMarginSectionView(quarters: vm.quarterlyFinancials)
                    }

                    if let qInfo = vm.quickInfo {
                        ShareholdingSectionView(qInfo: qInfo)
                        ProfitabilitySectionView(qInfo: qInfo)
                    }

                    if !vm.promoterHistory.isEmpty {
                        PromoterHistorySectionView(history: vm.promoterHistory)
                    }
                } else {
                    if let error = vm.stockProfileError {
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
                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                UIPasteboard.general.string = error
                                HapticManager.success()
                            } label: {
                                HStack(spacing: Theme.Spacing.small) {
                                    Image(systemName: "doc.on.doc").font(.caption)
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
                        .banknoteCard()
                    } else {
                        SPEmptyStateView(message: "Price history unavailable")
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchStockProfile() }
    }
}

// MARK: - RSI Chart

struct RSIChartSectionView: View {
    let prices: [OHLCVPoint]

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

    var body: some View {
        let rsiData = computeRSI(prices)
        if !rsiData.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("RSI (14)")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                Chart {
                    ForEach(rsiData, id: \.date) { pt in
                        LineMark(x: .value("Date", pt.date), y: .value("RSI", pt.rsi))
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
                    AxisMarks(values: [0, 30, 50, 70, 100]) { _ in
                        AxisValueLabel()
                    }
                }
                .frame(height: UIScreen.main.bounds.height * 0.25)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

// MARK: - SMA Section

struct SMASectionView: View {
    let prices: [OHLCVPoint]
    @State private var showSMA: Set<Int> = [20, 50, 200]

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

    var body: some View {
        let sma20 = computeSMA(prices, period: 20)
        let sma50 = computeSMA(prices, period: 50)
        let sma200 = computeSMA(prices, period: 200)
        let isUp = (prices.last?.close ?? 0) >= (prices.first?.close ?? 0)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("MOVING AVERAGES")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.tight) {
                ForEach([(20, Theme.securityGold), (50, Theme.bearRed), (200, Theme.avatarBlue)], id: \.0) { period, color in
                    Button { HapticManager.selection(); 
    HapticManager.selection()
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
                ForEach(prices, id: \.date) { pt in
                    AreaMark(x: .value("Date", pt.parsedDate), y: .value("Price", pt.close))
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
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text(IndianFormatter.priceCompact(v)).font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Quarterly Revenue

struct QuarterlyRevenueSectionView: View {
    let quarters: [QuarterlyFinancial]

    var body: some View {
        let shown = Array(quarters.prefix(8).reversed())
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY REVENUE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.standard) {
                if let latest = shown.last {
                    SPCompactChartValue(label: "LATEST", value: IndianFormatter.priceCompact(latest.revenue), color: Theme.securityGold)
                }
                if let first = shown.first, let latest = shown.last, first.revenue != 0 {
                    let growth = ((latest.revenue - first.revenue) / abs(first.revenue)) * 100
                    SPCompactChartValue(label: "8Q CHANGE", value: String(format: "%+.1f%%", growth), color: growth >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }

            Chart {
                ForEach(shown, id: \.label) { q in
                    BarMark(x: .value("Quarter", q.label), y: .value("Revenue", q.revenue))
                        .foregroundStyle(Theme.securityGold.opacity(0.85))
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisValueLabel().font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text(IndianFormatter.priceCompact(v)).font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        }
                    }
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Quarterly PAT

struct QuarterlyPATSectionView: View {
    let quarters: [QuarterlyFinancial]

    var body: some View {
        let shown = Array(quarters.prefix(8).reversed())
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY PAT")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .explainableTerm("PAT")

            HStack(spacing: Theme.Spacing.standard) {
                if let latest = shown.last {
                    SPCompactChartValue(label: "LATEST", value: IndianFormatter.priceCompact(latest.netProfit), color: latest.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                if let first = shown.first, let latest = shown.last, first.netProfit != 0 {
                    let growth = ((latest.netProfit - first.netProfit) / abs(first.netProfit)) * 100
                    SPCompactChartValue(label: "8Q CHANGE", value: String(format: "%+.1f%%", growth), color: growth >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }

            Chart {
                ForEach(shown, id: \.label) { q in
                    BarMark(x: .value("Quarter", q.label), y: .value("PAT", q.netProfit))
                        .foregroundStyle(by: .value("Sign", q.netProfit >= 0 ? "positive" : "negative"))
                }
                RuleMark(y: .value("Zero", 0)).foregroundStyle(Theme.inkTertiary.opacity(0.4))
            }
            .chartForegroundStyleScale(["positive": Theme.bullGreen, "negative": Theme.bearRed])
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisValueLabel().font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text(IndianFormatter.priceCompact(v)).font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        }
                    }
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - PAT Margin

struct PATMarginSectionView: View {
    let quarters: [QuarterlyFinancial]

    var body: some View {
        let shown = Array(quarters.prefix(8).reversed())
        let margins = shown.map { q -> (label: String, margin: Double) in
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
                        LineMark(x: .value("Quarter", pt.label), y: .value("Margin", pt.margin))
                            .foregroundStyle(Theme.securityGold)
                        AreaMark(x: .value("Quarter", pt.label), y: .value("Margin", pt.margin))
                            .foregroundStyle(Theme.securityGold.opacity(0.08))
                        PointMark(x: .value("Quarter", pt.label), y: .value("Margin", pt.margin))
                            .symbolSize(30)
                            .foregroundStyle(Theme.securityGold)
                    }
                }
                .chartXAxis { AxisMarks { _ in AxisValueLabel() } }
                .chartYAxis { AxisMarks { _ in AxisValueLabel() } }
                .frame(height: UIScreen.main.bounds.height * 0.25)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Shareholding

struct ShareholdingSectionView: View {
    let qInfo: QuickInfo

    var body: some View {
        let promoter = qInfo.promoterHoldingPct ?? 0
        let fii = qInfo.fiiHoldingPct ?? 0
        let dii = qInfo.diiHoldingPct ?? 0
        let publicHolding = max(0, 100 - promoter - fii - dii)
        let legendColumns = [GridItem(.flexible(), spacing: Theme.Spacing.standard), GridItem(.flexible(), spacing: Theme.Spacing.standard)]

        if promoter > 0 || fii > 0 || dii > 0 {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("SHAREHOLDING PATTERN")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                Chart {
                    BarMark(x: .value("Pct", promoter), y: .value("Type", "Holding")).foregroundStyle(Theme.securityGold)
                    BarMark(x: .value("Pct", fii), y: .value("Type", "Holding")).foregroundStyle(Theme.bullGreen)
                    BarMark(x: .value("Pct", dii), y: .value("Type", "Holding")).foregroundStyle(Theme.avatarBlue)
                    BarMark(x: .value("Pct", publicHolding), y: .value("Type", "Holding")).foregroundStyle(Theme.inkTertiary.opacity(0.4))
                }
                .chartXAxis { AxisMarks { _ in AxisValueLabel() } }
                .frame(height: UIScreen.main.bounds.height * 0.08)

                LazyVGrid(columns: legendColumns, alignment: .leading, spacing: Theme.Spacing.small) {
                    SPLegendDot(color: Theme.securityGold, label: "Promoter", value: promoter)
                    SPLegendDot(color: Theme.bullGreen, label: "FII", value: fii)
                    SPLegendDot(color: Theme.avatarBlue, label: "DII", value: dii)
                    SPLegendDot(color: Theme.inkTertiary.opacity(0.4), label: "Public", value: publicHolding)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

// MARK: - Promoter History

struct PromoterHistorySectionView: View {
    let history: [PromoterHistoryPoint]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER HOLDING HISTORY")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if !history.isEmpty {
                Chart {
                    ForEach(history, id: \.period) { pt in
                        LineMark(x: .value("Period", pt.period), y: .value("Holding", pt.promoter))
                            .foregroundStyle(Theme.securityGold)
                        AreaMark(x: .value("Period", pt.period), y: .value("Holding", pt.promoter))
                            .foregroundStyle(Theme.securityGold.opacity(0.08))
                        PointMark(x: .value("Period", pt.period), y: .value("Holding", pt.promoter))
                            .symbolSize(25)
                            .foregroundStyle(Theme.securityGold)
                    }
                }
                .chartXAxis { AxisMarks { _ in AxisValueLabel() } }
                .chartYAxis { AxisMarks { _ in AxisValueLabel() } }
                .frame(height: UIScreen.main.bounds.height * 0.25)

                if history.count >= 2 {
                    let latest = history.last?.promoter ?? 0
                    let prev = history[history.count - 2].promoter
                    if latest < prev {
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "arrow.down.right").font(.caption.weight(.bold)).foregroundStyle(Theme.bearRed)
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
}

// MARK: - Profitability

struct ProfitabilitySectionView: View {
    let qInfo: QuickInfo

    var body: some View {
        let roe = qInfo.roePct
        let roce = qInfo.rocePct
        let pe = qInfo.peRatio

        if roe != nil || roce != nil || pe != nil {
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
                                Text(String(format: "%.1f%%", roe)).font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkSecondary)
                            }
                    }
                    if let roce = roce {
                        BarMark(x: .value("Metric", "ROCE"), y: .value("Pct", roce))
                            .foregroundStyle(Theme.securityGold)
                            .annotation(position: .top) {
                                Text(String(format: "%.1f%%", roce)).font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkSecondary)
                            }
                    }
                    if let pe = pe {
                        BarMark(x: .value("Metric", "P/E"), y: .value("Pct", pe))
                            .foregroundStyle(Theme.avatarBlue)
                            .annotation(position: .top) {
                                Text(String(format: "%.1f", pe)).font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkSecondary)
                            }
                    }
                }
                .chartXAxis { AxisMarks { _ in AxisValueLabel() } }
                .chartYAxis { AxisMarks { _ in AxisValueLabel() } }
                .frame(height: UIScreen.main.bounds.height * 0.25)

                HStack {
                    HStack(spacing: Theme.Spacing.small) {
                        Circle().fill(Theme.securityGold.opacity(0.3)).frame(width: 4, height: 4)
                        Text("ROE").font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                    }
                    .explainableTerm("ROE")
                    Spacer()
                    HStack(spacing: Theme.Spacing.small) {
                        Circle().fill(Theme.securityGold.opacity(0.3)).frame(width: 4, height: 4)
                        Text("ROCE").font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                    }
                    .explainableTerm("ROCE")
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}
