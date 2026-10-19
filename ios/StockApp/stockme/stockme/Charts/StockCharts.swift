import SwiftUI
import Charts
import Combine

// Fix 1.4: Native Swift Charts foundation — replaces static matplotlib PNGs.
// Long-press drag gesture with tactile tooltip overlay for X-axis scrubbing.

/// Interactive chart overlay state for drag scrubbing (Fix 1.4)
@MainActor
final class ChartScrubState: ObservableObject {
    @Published var isDragging = false
    @Published var currentX: CGFloat = 0
    @Published var scrubDate: Date? = nil
    @Published var scrubPrice: Double = 0
}

// MARK: - Scrub Tooltip

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
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .banknoteCard()
    }
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

    // Fix 1.4: drag-scrub overlay state
    @StateObject private var scrubState = ChartScrubState()
    @State private var scrubDate = Date()
    @State private var scrubPrice: Double = 0

    private var displayCutoff: Date {
        let cal = Calendar.current
        switch range {
        case 0: return cal.date(byAdding: .month, value: -3, to: Date()) ?? Date()
        case 1: return cal.date(byAdding: .month, value: -6, to: Date()) ?? Date()
        default: return Date.distantPast
        }
    }

    private var filtered: [PricePoint] {
        let cutoff = displayCutoff
        return prices.droppingUndated.filter { $0.parsedDate >= cutoff }
    }

    /// Simple moving average with the true period; empty when there are fewer points than `period`.
    static func sma(_ points: [PricePoint], period: Int) -> [(date: Date, value: Double)] {
        guard period > 0 else { return [] }
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
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
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
                // SMAs use the full history and the true period, then crop to the visible window,
                // so "200 DMA" only appears when 200 points exist.
                let full = prices.droppingUndated
                let cutoff = displayCutoff
                let sma50 = Self.sma(full, period: 50).filter { $0.date >= cutoff }
                let sma200 = Self.sma(full, period: 200).filter { $0.date >= cutoff }
                let closes = filtered.map { $0.close }
                let minClose = closes.min() ?? 0
                let maxClose = closes.max() ?? 1
                let supportTop = minClose + (maxClose - minClose) * 0.10
                let resistBot = minClose + (maxClose - minClose) * 0.90
                let minDate = filtered.first?.parsedDate ?? Date()
                let maxDate = filtered.last?.parsedDate ?? Date()

                ZStack(alignment: .topLeading) {
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
                .frame(height: UIScreen.main.bounds.height * 0.30)
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
                .chartOverlay { proxy in
                    Color.clear
                        .contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 0)
                                .onChanged { value in
                                    scrubState.isDragging = true
                                    scrubState.currentX = value.location.x
                                    if let date: Date = proxy.value(atX: value.location.x, as: Date.self) {
                                        if let nearest = filtered.min(by: {
                                            abs($0.parsedDate.timeIntervalSince(date)) < abs($1.parsedDate.timeIntervalSince(date))
                                        }) {
                                            scrubDate = nearest.parsedDate
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

                if scrubState.isDragging {
                    ScrubTooltipCard(price: scrubPrice, date: scrubDate)
                        .position(
                            x: min(max(scrubState.currentX, 80), UIScreen.main.bounds.width - 80),
                            y: 36
                        )
                        .transition(.opacity)
                        .animation(.easeInOut(duration: 0.1), value: scrubState.isDragging)
                }
                } // end ZStack

            }

            ChartExplainCard(text: "Gold dashed = 50-day moving average. Red dashed = 200-day DMA (shown when enough history is available). When price is above the 200 DMA, the long-term trend is positive. Green zone = support, red zone = resistance.")
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}

// MARK: - SparklineView

/// A compact sparkline chart drawn on Canvas. Used in screener rows and watchlist cards.
/// Renders a polyline from the given values, auto-scaled to fit.
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
                let x = inset + CGFloat(i) / CGFloat(values.count - 1) * (size.width - inset * 2)
                let y = inset + (size.height - inset * 2) * (1 - CGFloat((values[i] - mn) / rng))
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
