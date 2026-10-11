import SwiftUI

// MARK: - ImmersiveStockHeroChart
//
// Full-bleed glow chart for a single stock. Reuses the same visual language as
// ImmersivePortfolioHeroChart — glow line, gradient fill, animated draw-in,
// and finger-tracking scrub tooltip — but works with [Double] closing prices.

struct ImmersiveStockHeroChart: View {
    let prices: [Double]
    let currentPrice: Double
    let dates: [Date]

    @State private var scrubIndex: Int? = nil
    @State private var drawProgress: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let chartHeight: CGFloat = UIScreen.main.bounds.height * 0.26

    /// Change across the plotted series (selected period), not the one-day move.
    private var periodChangePct: Double {
        guard let first = prices.first, let last = prices.last, first > 0 else { return 0 }
        let pct = (last - first) / first * 100
        return pct.isFinite ? pct : 0
    }
    private var isPositive: Bool { periodChangePct >= 0 }
    private var lineColor: Color { isPositive ? Theme.bullGreen : Theme.bearRed }
    private var fillGradient: LinearGradient {
        isPositive ? Theme.chartBullGradient : Theme.chartBearGradient
    }

    private var displayPrice: Double {
        if let i = scrubIndex, prices.indices.contains(i) { return prices[i] }
        return currentPrice
    }
    private var displayDate: Date? {
        if let i = scrubIndex, dates.indices.contains(i) { return dates[i] }
        return dates.last
    }
    private var displayChangePct: Double {
        guard let first = prices.first, first > 0 else { return periodChangePct }
        if let i = scrubIndex, prices.indices.contains(i) {
            return ((prices[i] - first) / first) * 100
        }
        return periodChangePct
    }

    var body: some View {
        Group {
            if prices.count < 2 {
                EmptyView()
            } else {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    valueHeader
                        .padding(.horizontal, Theme.screenPadding)
                    chartBody
                        .frame(height: chartHeight)
                }
            }
        }
        .onAppear { animateIn() }
        .onChange(of: prices.count) { _, _ in
            scrubIndex = nil
            animateIn()
        }
    }

    // MARK: Hero value header

    private var valueHeader: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(IndianFormatter.price(displayPrice))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(.largeTitle.weight(.bold))
                .monospaced()
                .foregroundStyle(Theme.inkPrimary)
                .contentTransition(.numericText())
                .animation(.easeInOut(duration: 0.08), value: displayPrice)

            HStack(spacing: Theme.Spacing.tight) {
                Text((displayChangePct >= 0 ? "▲ +" : "▼ ") + String(format: "%.2f%%", abs(displayChangePct)))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote).weight(.semibold))
                    .foregroundStyle(displayChangePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                if let d = displayDate {
                    Text("·")
                        .foregroundStyle(Theme.inkTertiary)
                    Text(dateString(from: d))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .animation(.easeInOut(duration: 0.08), value: displayChangePct)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Chart body

    private var chartBody: some View {
        GeometryReader { geo in
            let rect = CGRect(origin: .zero, size: geo.size)
            let pts = ImmersiveChartGeometry.points(values: prices, in: rect)

            ZStack {
                GlowAreaShape(values: prices)
                    .fill(fillGradient)
                    .opacity(Double(drawProgress))

                GlowLineShape(values: prices)
                    .trim(from: 0, to: drawProgress)
                    .stroke(lineColor.opacity(0.45),
                            style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round))
                    .blur(radius: 9)

                GlowLineShape(values: prices)
                    .trim(from: 0, to: drawProgress)
                    .stroke(lineColor,
                            style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))

                if let i = scrubIndex, pts.indices.contains(i) {
                    scrubOverlay(point: pts[i], in: geo.size, index: i)
                }
            }
            .contentShape(Rectangle())
            .gesture(scrubGesture(in: geo.size))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Price chart")
        .accessibilityValue(accessibilityValueText)
        .accessibilityHint("Swipe up or down to step through dates.")
        .accessibilityAdjustableAction { direction in
            scrubIndex = ImmersiveChartAccessibility.step(from: scrubIndex, count: prices.count, direction: direction)
        }
    }

    private var accessibilityValueText: String {
        if let i = scrubIndex, prices.indices.contains(i) {
            let date = dates.indices.contains(i) ? "\(dateString(from: dates[i])), " : ""
            return "\(date)\(IndianFormatter.price(prices[i])), \(IndianFormatter.delta(displayChangePct)) since start"
        }
        return ImmersiveChartAccessibility.summary(values: prices, dates: dates,
                                                   format: IndianFormatter.price, dateText: dateString(from:))
    }

    // MARK: Scrub overlay

    @ViewBuilder
    private func scrubOverlay(point pt: CGPoint, in size: CGSize, index i: Int) -> some View {
        Path { p in
            p.move(to: CGPoint(x: pt.x, y: 0))
            p.addLine(to: CGPoint(x: pt.x, y: size.height))
        }
        .stroke(Theme.inkTertiary.opacity(0.55),
                style: StrokeStyle(lineWidth: 1, dash: [5, 4]))

        Circle()
            .fill(lineColor)
            .frame(width: 9, height: 9)
            .overlay(Circle().stroke(Theme.canvas, lineWidth: 1.5))
            .shadow(color: lineColor.opacity(0.6), radius: 4)
            .position(pt)

        if let d = displayDate {
            ScrubTooltipView(price: prices[i], date: d)
                .fixedSize()
                .position(x: clampedTooltipX(pt.x, width: size.width), y: 16)
        }
    }

    private func clampedTooltipX(_ x: CGFloat, width: CGFloat) -> CGFloat {
        let halfTooltip: CGFloat = 70
        return min(max(x, halfTooltip), width - halfTooltip)
    }

    // MARK: Gesture

    private func scrubGesture(in size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 2)
            .onChanged { value in
                guard prices.count > 1, size.width > 0 else { return }
                let ratio = min(max(value.location.x / size.width, 0), 1)
                let idx = Int(round(ratio * CGFloat(prices.count - 1)))
                if scrubIndex != idx {
                    HapticManager.selection()
                    scrubIndex = idx
                }
            }
            .onEnded { _ in
                withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                    scrubIndex = nil
                }
            }
    }

    // MARK: Helpers

    private func animateIn() {
        drawProgress = 0
        if reduceMotion {
            drawProgress = 1
        } else {
            withAnimation(.easeOut(duration: 0.9)) { drawProgress = 1 }
        }
    }

    private static let headerDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "d MMM ''yy"
        return f
    }()

    private func dateString(from date: Date) -> String {
        Self.headerDateFormatter.string(from: date)
    }
}
