import SwiftUI
import Charts

// Fix 1.4: Native Swift Charts foundation — replaces static matplotlib PNGs.
// Long-press drag gesture with tactile tooltip overlay for X-axis scrubbing.

/// Interactive chart overlay state for long-press scrubbing (Fix 1.4)
struct ChartScrubState {
    var isDragging = false
    var currentX: Double? = nil
    var tooltipText: String = ""
}

// Fix 3.24: Pause chart redraw during Dark/Light mode transitions to avoid
// UIKit structural rendering crashes. Use @Environment(\.colorScheme) in
// parent views and set `chartNeedsRedraw = false` during trait changes.
// Re-enable with `chartNeedsRedraw = true` after a 0.3s debounce.

// MARK: - Chart Explanation Card

private struct ChartExplainCard: View {
    let text: String
    var body: some View {
        Text(text)
            .font(Theme.officialStampFont(size: 13))
            .foregroundStyle(Theme.inkSecondary)
            .lineSpacing(4)
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.inkSecondary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

private struct ChartSectionHeader: View {
    let title: String
    var body: some View {
        Text(title.uppercased())
            .font(Theme.officialStampFont(size: 9))
            .foregroundStyle(Theme.inkPrimary)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - A: Price History Chart

struct PriceHistoryChart: View {
    @State private var xDomainScale: Double = 1.0
    let prices: [PricePoint]
    let ticker: String
    let week52High: Double?
    let week52Low: Double?

    @State private var range: Int = 1 // 0=3M, 1=6M, 2=all

    private var filtered: [PricePoint] {
        let cutoff: Date
        let cal = Calendar.current
        switch range {
        case 0: cutoff = cal.date(byAdding: .month, value: -3, to: Date()) ?? Date()
        case 1: cutoff = cal.date(byAdding: .month, value: -6, to: Date()) ?? Date()
        default: cutoff = Date.distantPast
        }
        return prices.filter { $0.parsedDate >= cutoff }
    }

    private func sma(_ points: [PricePoint], period: Int) -> [(date: Date, value: Double)] {
        guard points.count >= period else { return [] }
        var result: [(date: Date, value: Double)] = []
        for i in (period - 1)..<points.count {
            let slice = points[(i - period + 1)...i]
            let avg = slice.reduce(0.0) { $0 + $1.close } / Double(period)
            result.append((date: points[i].parsedDate, value: avg))
        }
        return result
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Price History")

            Picker("Range", selection: $range) {
                Text("3M").tag(0)
                Text("6M").tag(1)
                Text("All").tag(2)
            }
            .pickerStyle(.segmented)

            if filtered.isEmpty {
                Text("Insufficient price history data")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 160)
            } else {
                let sma50 = sma(filtered, period: min(50, filtered.count))
                // 200 DMA only meaningful when we have enough history
                let sma200 = filtered.count >= 100 ? sma(filtered, period: min(200, filtered.count)) : []
                let closes = filtered.map { $0.close }
                let minClose = closes.min() ?? 0
                let maxClose = closes.max() ?? 1
                let supportTop = minClose + (maxClose - minClose) * 0.10
                let resistBot = minClose + (maxClose - minClose) * 0.90
                let minDate = filtered.first?.parsedDate ?? Date()
                let maxDate = filtered.last?.parsedDate ?? Date()

                Chart {
                    // Support zone
                    RectangleMark(
                        xStart: .value("Start", minDate),
                        xEnd: .value("End", maxDate),
                        yStart: .value("SLow", minClose),
                        yEnd: .value("SHigh", supportTop)
                    )
                    .foregroundStyle(Theme.bullGreen.opacity(0.08))

                    // Resistance zone
                    RectangleMark(
                        xStart: .value("Start", minDate),
                        xEnd: .value("End", maxDate),
                        yStart: .value("RLow", resistBot),
                        yEnd: .value("RHigh", maxClose)
                    )
                    .foregroundStyle(Theme.bearRed.opacity(0.08))

                    // Price line
                    ForEach(filtered) { p in
                        LineMark(
                            x: .value("Date", p.parsedDate),
                            y: .value("Price", p.close)
                        )
                        .foregroundStyle(Theme.inkPrimary)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                        .interpolationMethod(.catmullRom)
                    }
                    .foregroundStyle(by: .value("Series", "Price"))

                    // 50-day SMA
                    ForEach(sma50, id: \.date) { p in
                        LineMark(
                            x: .value("Date", p.date),
                            y: .value("SMA50", p.value)
                        )
                        .foregroundStyle(Theme.securityGold)
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 2]))
                    }
                    .foregroundStyle(by: .value("Series", "50 SMA"))

                    // 200-day DMA (only rendered when data exists)
                    if !sma200.isEmpty {
                        ForEach(sma200, id: \.date) { p in
                            LineMark(
                                x: .value("Date", p.date),
                                y: .value("DMA200", p.value)
                            )
                            .foregroundStyle(Theme.bearRed.opacity(0.7))
                            .lineStyle(StrokeStyle(lineWidth: 1.2, dash: [2, 4]))
                        }
                        .foregroundStyle(by: .value("Series", "200 DMA"))
                    }
                }
                .chartForegroundStyleScale([
                    "Price":   Theme.inkPrimary,
                    "50 SMA":  Theme.securityGold,
                    "200 DMA": Theme.bearRed.opacity(0.7),
                ])
                .chartLegend(position: .bottom, alignment: .leading)
                .frame(height: 180)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) {
                        AxisValueLabel(format: .dateTime.month(.abbreviated))
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) {
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: "Gold dashed = 50-day moving average. Red dashed = 200-day DMA (shown when enough history is available). When price is above the 200 DMA, the long-term trend is positive. Green zone = support, red zone = resistance.")
        }
    }
}

// MARK: - B: RSI Chart

struct RSIChart: View {
    let prices: [PricePoint]

    private func computeRSI(period: Int = 14) -> [(date: Date, rsi: Double)] {
        guard prices.count > period else { return [] }
        var gains: [Double] = []
        var losses: [Double] = []
        for i in 1..<prices.count {
            let diff = prices[i].close - prices[i - 1].close
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        }
        var result: [(date: Date, rsi: Double)] = []
        var avgGain = gains[0..<period].reduce(0, +) / Double(period)
        var avgLoss = losses[0..<period].reduce(0, +) / Double(period)
        for i in period..<gains.count {
            avgGain = (avgGain * Double(period - 1) + gains[i]) / Double(period)
            avgLoss = (avgLoss * Double(period - 1) + losses[i]) / Double(period)
            let rs = avgLoss == 0 ? 100.0 : avgGain / avgLoss
            let rsi = 100 - 100 / (1 + rs)
            result.append((date: prices[i + 1].parsedDate, rsi: rsi))
        }
        return result
    }

    var body: some View {
        let rsiData = computeRSI()
        let currentRSI = rsiData.last?.rsi ?? 50
        let minDate = rsiData.first?.date ?? Date()
        let maxDate = rsiData.last?.date ?? Date()

        let explanation: String = {
            if currentRSI > 70 {
                return "⚠️ Currently overbought at \(Int(currentRSI)). The stock has been bought heavily recently. This sometimes precedes a pullback. Consider waiting before adding more."
            } else if currentRSI < 30 {
                return "💡 Currently oversold at \(Int(currentRSI)). The stock has been sold heavily. This sometimes presents a buying opportunity if the fundamentals are still strong."
            } else {
                return "RSI is at \(Int(currentRSI)) — in the neutral zone. Neither overbought nor oversold. This is a normal reading and doesn't signal urgency either way."
            }
        }()

        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "RSI (14-Period)")

            if rsiData.isEmpty {
                Text("Insufficient price data for RSI")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 120)
            } else {
                Chart {
                    // Overbought zone
                    RectangleMark(
                        xStart: .value("S", minDate), xEnd: .value("E", maxDate),
                        yStart: .value("Y1", 70), yEnd: .value("Y2", 100)
                    ).foregroundStyle(Theme.bearRed.opacity(0.08))

                    // Neutral zone
                    RectangleMark(
                        xStart: .value("S", minDate), xEnd: .value("E", maxDate),
                        yStart: .value("Y1", 30), yEnd: .value("Y2", 70)
                    ).foregroundStyle(Theme.inkSecondary.opacity(0.03))

                    // Oversold zone
                    RectangleMark(
                        xStart: .value("S", minDate), xEnd: .value("E", maxDate),
                        yStart: .value("Y1", 0), yEnd: .value("Y2", 30)
                    ).foregroundStyle(Theme.bullGreen.opacity(0.08))

                    RuleMark(y: .value("OB", 70))
                        .foregroundStyle(Theme.bearRed.opacity(0.5))
                        .lineStyle(StrokeStyle(lineWidth: 0.8, dash: [4, 2]))
                        .annotation(position: .trailing) {
                            Text("OB").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.bearRed)
                        }

                    RuleMark(y: .value("OS", 30))
                        .foregroundStyle(Theme.bullGreen.opacity(0.5))
                        .lineStyle(StrokeStyle(lineWidth: 0.8, dash: [4, 2]))
                        .annotation(position: .trailing) {
                            Text("OS").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.bullGreen)
                        }

                    ForEach(rsiData, id: \.date) { p in
                        LineMark(
                            x: .value("Date", p.date),
                            y: .value("RSI", p.rsi)
                        )
                        .foregroundStyle(currentRSI > 70 ? Theme.bearRed : currentRSI < 30 ? Theme.bullGreen : Theme.securityGold)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                        .interpolationMethod(.catmullRom)
                    }

                    if let last = rsiData.last {
                        PointMark(x: .value("Date", last.date), y: .value("RSI", last.rsi))
                            .foregroundStyle(Theme.securityGold)
                            .symbolSize(40)
                            .annotation(position: .top) {
                                Text(String(format: "%.0f", last.rsi))
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.securityGold)
                            }
                    }
                }
                .chartYScale(domain: 0...100)
                .frame(height: 140)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) {
                        AxisValueLabel(format: .dateTime.month(.abbreviated))
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: [0, 30, 70, 100]) {
                        AxisValueLabel().font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkTertiary)
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: explanation)
        }
    }
}

// MARK: - C: Volume Chart

struct VolumeChart: View {
    let prices: [PricePoint]

    private var avgVolume: Double {
        let vols = prices.compactMap { $0.volume }.prefix(20)
        guard !vols.isEmpty else { return 0 }
        return vols.reduce(0, +) / Double(vols.count)
    }

    var body: some View {
        let avg = avgVolume

        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Volume")

            let hasVol = prices.contains { $0.volume != nil && ($0.volume ?? 0) > 0 }

            if !hasVol {
                Text("Volume data not available")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 100)
            } else {
                Chart {
                    if avg > 0 {
                        RuleMark(y: .value("Avg", avg))
                            .foregroundStyle(Theme.securityGold.opacity(0.7))
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 2]))
                            .annotation(position: .trailing) {
                                Text("Avg").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.securityGold)
                            }
                    }

                    ForEach(prices.indices, id: \.self) { i in
                        let p = prices[i]
                        if let vol = p.volume, vol > 0 {
                            let isUp = i == 0 || p.close >= prices[i - 1].close
                            let isUnusual = avg > 0 && Double(vol) > avg * 2

                            BarMark(
                                x: .value("Date", p.parsedDate),
                                y: .value("Volume", vol)
                            )
                            .foregroundStyle(isUp ? Theme.bullGreen.opacity(0.7) : Theme.bearRed.opacity(0.7))

                            if isUnusual {
                                PointMark(
                                    x: .value("Date", p.parsedDate),
                                    y: .value("Volume", vol)
                                )
                                .foregroundStyle(Theme.securityGold)
                                .annotation(position: .top) {
                                    Text("!")
                                        .font(Theme.officialStampFont(size: 8))
                                        .foregroundStyle(Theme.securityGold)
                                }
                            }
                        }
                    }
                }
                .frame(height: 120)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) {
                        AxisValueLabel(format: .dateTime.month(.abbreviated))
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: "Green bars = up days, red bars = down days. A '!' marks days with more than 2× average volume — unusual activity. High volume on up days shows strong buying conviction; on down days, strong selling.")
        }
    }
}

// MARK: - D: Shareholding Chart

struct ShareholdingChart: View {
    let promoterPct: Double
    let fiiPct: Double
    let diiPct: Double
    let publicPct: Double

    var body: some View {
        let data: [(label: String, value: Double, color: Color)] = [
            ("Promoter", promoterPct, Theme.chartPromoter),
            ("FII", fiiPct, Theme.bullGreen),
            ("DII", diiPct, Theme.securityGold),
            ("Public", publicPct, Theme.inkSecondary)
        ]
        let total = data.reduce(0.0) { $0 + $1.value }

        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Shareholding Pattern")

            if total < 1 {
                Text("Shareholding data not available")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 80)
            } else {
                Chart(data, id: \.label) { d in
                    BarMark(
                        x: .value("Holder", d.label),
                        y: .value("Pct", d.value)
                    )
                    .foregroundStyle(d.color)
                    .annotation(position: .top) {
                        Text(String(format: "%.1f%%", d.value))
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                .frame(height: 140)
                .chartXAxis {
                    AxisMarks {
                        AxisValueLabel().font(Theme.officialStampFont(size: 10)).foregroundStyle(Theme.inkSecondary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: "Promoters are the founders/management holding their own stake. High promoter holding is generally positive — they have skin in the game. FII (foreign institutions) and DII (domestic institutions) buying is a confidence signal from professional investors.")
        }
    }
}

// MARK: - E: Financials Chart

struct FinancialsChart: View {
    let quarters: [QuarterlyFinancial]

    private var yoyGrowthAnnotation: String? {
        guard quarters.count >= 5 else { return nil }
        let latest = quarters[0].revenue
        let yearAgo = quarters[4].revenue
        guard yearAgo > 0 else { return nil }
        let growth = (latest - yearAgo) / yearAgo * 100
        return (growth >= 0 ? "+" : "") + String(format: "%.1f%% YoY", growth)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Quarterly Financials")

            if quarters.isEmpty {
                Text("Quarterly financials not available")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 100)
            } else {
                let shown = Array(quarters.prefix(8).reversed())

                Chart {
                    ForEach(shown) { q in
                        BarMark(
                            x: .value("Quarter", q.label),
                            y: .value("Revenue", q.revenue)
                        )
                        .foregroundStyle(Theme.inkSecondary.opacity(0.5))

                        LineMark(
                            x: .value("Quarter", q.label),
                            y: .value("Net Profit", q.netProfit)
                        )
                        .foregroundStyle(q.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .lineStyle(StrokeStyle(lineWidth: 2))

                        PointMark(
                            x: .value("Quarter", q.label),
                            y: .value("Net Profit", q.netProfit)
                        )
                        .foregroundStyle(q.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .symbolSize(25)
                    }

                    // Mark latest
                    if let latest = shown.last {
                        PointMark(
                            x: .value("Quarter", latest.label),
                            y: .value("Revenue", latest.revenue)
                        )
                        .foregroundStyle(Theme.securityGold)
                        .annotation(position: .top) {
                            VStack(spacing: 1) {
                                Text("Latest")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.securityGold)
                                if let yoy = yoyGrowthAnnotation {
                                    Text(yoy)
                                        .font(Theme.officialStampFont(size: 8))
                                        .foregroundStyle(yoy.hasPrefix("+") ? Theme.bullGreen : Theme.bearRed)
                                }
                            }
                        }
                    }
                }
                .frame(height: 160)
                .chartXAxis {
                    AxisMarks {
                        AxisValueLabel().font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: "Grey bars = revenue (total money earned). Green/red line = net profit (what remained). When both grow consistently, the company is healthy. A single weak quarter is usually not a concern — focus on the overall trend.")
        }
    }
}

// MARK: - F: Price Range Gauge

struct PriceRangeGauge: View {
    let low52w: Double
    let high52w: Double
    let current: Double
    let target12m: Double

    private var position: Double {
        guard high52w > low52w else { return 0.5 }
        return (current - low52w) / (high52w - low52w)
    }

    private var targetPosition: Double {
        let extHigh = max(high52w, target12m)
        guard extHigh > low52w else { return 1.0 }
        return (target12m - low52w) / (extHigh - low52w)
    }

    private var explanation: String {
        if position < 0.33 {
            return "The stock is currently near its 52-week low — you are potentially buying at the lower end of its recent range. This can be an opportunity if fundamentals are intact."
        } else if position > 0.67 {
            return "The stock is near its 52-week high. There is less room before it reaches the target. Make sure the fundamentals justify current levels before adding."
        } else {
            return "The stock is in the middle of its 52-week range — not stretched in either direction. This is a neutral reading from a price-range perspective."
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "52-Week Price Range")

            GeometryReader { geo in
                let w = geo.size.width
                let dotX = w * max(0.02, min(0.98, position))
                let targX = w * max(0.02, min(0.98, targetPosition))

                ZStack(alignment: .leading) {
                    // Track
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.inkSecondary.opacity(0.12))
                        .frame(height: 8)

                    // Filled portion
                    RoundedRectangle(cornerRadius: 3)
                        .fill(
                            LinearGradient(
                                colors: [Theme.bearRed.opacity(0.6), Theme.holdAmber.opacity(0.6), Theme.bullGreen.opacity(0.6)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: dotX, height: 8)

                    // Target diamond
                    Image(systemName: "diamond.fill")
                        .font(.caption)
                        .foregroundStyle(Theme.securityGold)
                        .offset(x: targX - 5, y: -14)

                    // Current price dot
                    Circle()
                        .fill(Theme.inkPrimary)
                        .frame(width: 14, height: 14)
                        .overlay(Circle().stroke(Theme.canvas, lineWidth: 2))
                        .offset(x: dotX - 7, y: -3)
                }

                // Labels
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("52W LOW")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(low52w.inrFormatted)
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.bearRed)
                    }
                    Spacer()
                    VStack(alignment: .center, spacing: 2) {
                        Text("NOW")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(current.inrFormatted)
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("TARGET")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(target12m.inrFormatted)
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.bullGreen)
                    }
                }
                .offset(y: 20)
            }
            .frame(height: 60)

            ChartExplainCard(text: explanation)
        }
    }
}

// MARK: - G: Portfolio Allocation Chart

struct PortfolioAllocationChart: View {
    let holdings: [PortfolioHolding]

    private var totalValue: Double { holdings.reduce(0) { $0 + $1.currentValue } }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Portfolio Allocation")

            if holdings.isEmpty {
                Text("No holdings to display")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else {
                let total = totalValue
                ZStack {
                    Chart(holdings) { h in
                        let pct = total > 0 ? h.currentValue / total * 100 : 0
                        let isGain = h.pnl >= 0
                        let isFlat = abs(h.pnlPercent) < 2

                        SectorMark(
                            angle: .value("Value", h.currentValue),
                            innerRadius: .ratio(0.55),
                            angularInset: 1.5
                        )
                        .foregroundStyle(
                            isFlat ? Theme.holdAmber.opacity(0.7) :
                            isGain ? Theme.bullGreen.opacity(0.7) :
                            Theme.bearRed.opacity(0.7)
                        )
                        .annotation(position: .overlay) {
                            if pct > 5 {
                                VStack(spacing: 1) {
                                    Text(h.stock.ticker)
                                        .font(Theme.officialStampFont(size: 8))
                                        .foregroundStyle(.white)
                                    Text(String(format: "%.0f%%", pct))
                                        .font(Theme.serialNumberFont(size: 7))
                                        .foregroundStyle(.white.opacity(0.8))
                                }
                            }
                        }
                    }
                    .frame(height: 220)

                    // Centre value
                    VStack(spacing: 2) {
                        Text("₹")
                            .font(Theme.engravedSerif(size: 14, weight: .bold))
                            .foregroundStyle(Theme.securityGold)
                        Text(total.shortFormatted)
                            .font(Theme.serialNumberFont(size: 18))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("TOTAL")
                            .font(Theme.officialStampFont(size: 7))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    .background(Theme.canvasDeep.opacity(0.7))
                    .cornerRadius(Theme.CornerRadius.medium)
                }

                // High-concentration warnings
                ForEach(holdings.filter { h in total > 0 && h.currentValue / total > 0.15 }) { h in
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption)
                            .foregroundStyle(Theme.holdAmber)
                        Text("High concentration — \(h.stock.ticker) (\(String(format: "%.0f%%", h.currentValue / total * 100)))")
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.holdAmber)
                    }
                }

                ChartExplainCard(text: "Each slice is one stock sized by its current value. Green = profit, red = loss, amber = near breakeven. Any slice above 15% means that stock has an outsized effect on your overall performance.")
            }
        }
    }
}

// MARK: - H: P&L Waterfall Chart

struct PnLWaterfallChart: View {
    let holdings: [PortfolioHolding]

    var body: some View {
        let sorted = holdings.sorted { $0.pnl > $1.pnl }
        let totalPnL = sorted.reduce(0.0) { $0 + $1.pnl }

        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "P&L Breakdown")

            if sorted.isEmpty {
                Text("No holdings to display")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 120)
            } else {
                Chart(sorted.prefix(10)) { h in
                    BarMark(
                        x: .value("P&L", h.pnl),
                        y: .value("Stock", h.stock.ticker)
                    )
                    .foregroundStyle(h.pnl >= 0 ? Theme.bullGreen.opacity(0.8) : Theme.bearRed.opacity(0.8))
                    .annotation(position: h.pnl >= 0 ? .trailing : .leading) {
                        Text(h.pnl.shortFormatted)
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(h.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                .frame(height: CGFloat(min(sorted.count, 10)) * 32 + 20)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 3)) { _ in
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
                .chartYAxis {
                    AxisMarks {
                        AxisValueLabel().font(Theme.officialStampFont(size: 10)).foregroundStyle(Theme.inkSecondary)
                    }
                }

                HStack {
                    Text("TOTAL P&L")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                    Text(totalPnL.inrFormatted)
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundStyle(totalPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                }

                ChartExplainCard(text: "This shows exactly which stocks are growing your portfolio (green) and which are shrinking it (red). Focus on the red bars — are those stocks still worth holding, or has the investment thesis changed?")
            }
        }
    }
}

// MARK: - I: Stock vs Nifty Chart

struct StockVsNiftyChart: View {
    let stockPrices: [PricePoint]
    let niftyPrices: [NiftyPricePoint]
    let purchaseDate: Date?
    let ticker: String

    private func indexed(prices: [Double], from date: Date?) -> [(Date, Double)] {
        guard !prices.isEmpty else { return [] }
        return prices.enumerated().map { (i, p) in
            let d = Calendar.current.date(byAdding: .day, value: i, to: date ?? Date.distantPast) ?? Date()
            let base = prices.first ?? 1
            return (d, base > 0 ? (p / base) * 100 : 100)
        }
    }

    var body: some View {
        let baseDate = purchaseDate ?? stockPrices.first?.parsedDate ?? Date()
        let filteredStock = stockPrices.filter { $0.parsedDate >= baseDate }
        let filteredNifty = niftyPrices.filter { $0.parsedDate >= baseDate }

        let stockBase = filteredStock.first?.close ?? 1
        let niftyBase = filteredNifty.first?.close ?? 1

        let stockReturn = filteredStock.last.map { ($0.close / stockBase - 1) * 100 } ?? 0
        let niftyReturn = filteredNifty.last.map { ($0.close / niftyBase - 1) * 100 } ?? 0
        let isOutperforming = stockReturn >= niftyReturn

        let explanation: String = {
            if filteredStock.isEmpty || filteredNifty.isEmpty {
                return "Price history required to compare against Nifty."
            }
            if isOutperforming {
                return "\(ticker) has returned \(String(format: "%.1f%%", stockReturn)) since purchase, beating the Nifty 50's \(String(format: "%.1f%%", niftyReturn)) return. Your stock pick has added value over simply buying the index."
            } else {
                return "The Nifty 50 has returned \(String(format: "%.1f%%", niftyReturn)) since you bought \(ticker), which has returned \(String(format: "%.1f%%", stockReturn)). It's worth asking whether the reasons you bought it are still valid."
            }
        }()

        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "\(ticker) vs Nifty 50")

            if filteredStock.isEmpty {
                Text("Price history not available for comparison")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 140)
            } else {
                Chart {
                    RuleMark(y: .value("Base", 100))
                        .foregroundStyle(Theme.inkSecondary.opacity(0.4))
                        .lineStyle(StrokeStyle(lineWidth: 0.8, dash: [4, 2]))
                        .annotation(position: .leading) {
                            Text("Buy").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        }

                    ForEach(filteredStock) { p in
                        let idx = stockBase > 0 ? (p.close / stockBase) * 100 : 100
                        LineMark(
                            x: .value("Date", p.parsedDate),
                            y: .value(ticker, idx)
                        )
                        .foregroundStyle(Theme.securityGold)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                        .interpolationMethod(.catmullRom)
                    }
                    .foregroundStyle(by: .value("Series", ticker))

                    ForEach(filteredNifty) { p in
                        let idx = niftyBase > 0 ? (p.close / niftyBase) * 100 : 100
                        LineMark(
                            x: .value("Date", p.parsedDate),
                            y: .value("Nifty", idx)
                        )
                        .foregroundStyle(Theme.inkSecondary)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                        .interpolationMethod(.catmullRom)
                    }
                    .foregroundStyle(by: .value("Series", "Nifty 50"))
                }
                .chartForegroundStyleScale([ticker: Theme.securityGold, "Nifty 50": Theme.inkSecondary])
                .chartLegend(position: .bottom, alignment: .leading)
                .frame(height: 160)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) {
                        AxisValueLabel(format: .dateTime.month(.abbreviated))
                            .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
            }

            ChartExplainCard(text: explanation)
        }
    }
}

// MARK: - J: Sector Heatmap

struct SectorHeatmapView: View {
    let sectors: [SectorPerformance]

    private func color(for change: Double) -> Color {
        if change > 2 { return Theme.bullGreen }
        else if change > 0 { return Theme.bullGreen.opacity(0.45) }
        else if change > -2 { return Theme.bearRed.opacity(0.45) }
        else { return Theme.bearRed }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChartSectionHeader(title: "Sector Heatmap")

            if sectors.isEmpty {
                Text("Sector data loading…")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, minHeight: 80)
            } else {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                    ForEach(sectors) { sector in
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(color(for: sector.changePct).opacity(0.18))
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(color(for: sector.changePct).opacity(0.35), lineWidth: 0.8)
                            VStack(spacing: 4) {
                                Text(sector.name)
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .multilineTextAlignment(.center)
                                    .lineLimit(2)
                                Text((sector.changePct >= 0 ? "+" : "") + String(format: "%.2f%%", sector.changePct))
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundStyle(color(for: sector.changePct))
                            }
                            .padding(8)
                        }
                        .animation(.easeInOut(duration: 0.3), value: sector.changePct)
                    }
                }

                ChartExplainCard(text: "Green sectors are performing well today. Red sectors are under pressure. If most of your holdings are in red sectors, expect a tough session. This gives you the market mood at a glance.")
            }
        }
    }
}
