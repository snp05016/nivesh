import SwiftUI

// MARK: - Chart geometry helpers
//
// Shared point-projection used by the line shape, area shape, and scrub overlay
// so the curve, the fill, the dashed crosshair and the dot all align perfectly.

enum ImmersiveChartGeometry {
    /// Vertical breathing room so peaks/troughs, the glow and the scrub dot never clip.
    static let verticalInset: CGFloat = 22

    /// Projects a value series into view-space points. Line runs full-bleed edge to edge.
    static func points(values: [Double], in rect: CGRect) -> [CGPoint] {
        guard values.count > 1 else {
            guard values.first != nil else { return [] }
            return [CGPoint(x: rect.minX, y: rect.midY),
                    CGPoint(x: rect.maxX, y: rect.midY)]
        }
        // Non-finite values sit on the midline (indices stay aligned with the scrubbed data);
        // a flat series is centred instead of hugging the bottom edge.
        let finite = values.filter(\.isFinite)
        let mn = finite.min() ?? 0
        let mx = finite.max() ?? 0
        let rng = mx - mn
        let usableH = rect.height - verticalInset * 2
        let step = rect.width / CGFloat(values.count - 1)
        return values.enumerated().map { i, v in
            let x = rect.minX + CGFloat(i) * step
            guard v.isFinite, rng > 1e-9 else { return CGPoint(x: x, y: rect.midY) }
            let y = rect.minY + verticalInset + (1 - CGFloat((v - mn) / rng)) * usableH
            return CGPoint(x: x, y: y)
        }
    }

    /// Smooth the polyline with horizontal-tangent cubic Béziers (same easing as the sparkline).
    static func smoothLine(_ pts: [CGPoint]) -> Path {
        var path = Path()
        guard pts.count > 1 else { return path }
        path.move(to: pts[0])
        for i in 1..<pts.count {
            let prev = pts[i - 1]
            let curr = pts[i]
            let midX = (prev.x + curr.x) / 2
            path.addCurve(to: curr,
                          control1: CGPoint(x: midX, y: prev.y),
                          control2: CGPoint(x: midX, y: curr.y))
        }
        return path
    }
}

// MARK: - Shapes

/// The glowing price curve. Trimmable so it can draw itself in on appear.
struct GlowLineShape: Shape {
    let values: [Double]
    func path(in rect: CGRect) -> Path {
        ImmersiveChartGeometry.smoothLine(ImmersiveChartGeometry.points(values: values, in: rect))
    }
}

/// The gradient area beneath the curve (line + closed baseline at the bottom edge).
struct GlowAreaShape: Shape {
    let values: [Double]
    func path(in rect: CGRect) -> Path {
        let pts = ImmersiveChartGeometry.points(values: values, in: rect)
        guard pts.count > 1 else { return Path() }
        var path = ImmersiveChartGeometry.smoothLine(pts)
        path.addLine(to: CGPoint(x: pts.last!.x, y: rect.maxY))
        path.addLine(to: CGPoint(x: pts.first!.x, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}

// MARK: - ImmersivePortfolioHeroChart
//
// Full-bleed dark-fintech glow chart. Smooth neon line with a soft gradient fill,
// animated draw-in, and a finger-tracking scrub tooltip with a dashed crosshair + ringed dot.
// Public API preserved: `ImmersivePortfolioHeroChart(snapshots:)`.

struct ImmersivePortfolioHeroChart: View {
    let snapshots: [PortfolioValuationSnapshot]
    /// When false the static value header is omitted (e.g. Portfolio, where
    /// `PortfolioHeroBlock` is already the resting hero). The scrub tooltip still appears.
    var showValueHeader: Bool = true

    @State private var scrubIndex: Int? = nil
    @State private var drawProgress: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let chartHeight: CGFloat = UIScreen.main.bounds.height * 0.26

    // MARK: Derived data

    private var values: [Double] { snapshots.map(\.totalValue) }
    /// P&L change over the shown range (not lifetime P&L), so the colour matches the curve.
    private var isPositive: Bool { snapshots.pnlChangeIsPositive }
    private var lineColor: Color { isPositive ? Theme.bullGreen : Theme.bearRed }
    private var fillGradient: LinearGradient {
        isPositive ? Theme.chartBullGradient : Theme.chartBearGradient
    }

    private var displayValue: Double {
        if let i = scrubIndex, snapshots.indices.contains(i) { return snapshots[i].totalValue }
        return snapshots.last?.totalValue ?? 0
    }
    private var displayDate: Date? {
        if let i = scrubIndex, snapshots.indices.contains(i) { return snapshots[i].parsedDate }
        return snapshots.last?.parsedDate
    }
    private var displayPnlPct: Double {
        if let i = scrubIndex, snapshots.indices.contains(i) { return snapshots[i].pnlPercent }
        return snapshots.last?.pnlPercent ?? 0
    }

    var body: some View {
        Group {
            if snapshots.count < 2 {
                EmptyView()
            } else {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    if showValueHeader {
                        valueHeader
                            .padding(.horizontal, Theme.screenPadding)
                    }
                    chartBody
                        .frame(height: chartHeight)
                }
            }
        }
        .onAppear { animateIn() }
        .onChange(of: snapshots.count) { _, _ in
            scrubIndex = nil
            animateIn()
        }
    }

    // MARK: Hero value header

    private var valueHeader: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(IndianFormatter.priceCompact(displayValue))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(.largeTitle.weight(.bold))
                .monospaced()
                .foregroundStyle(Theme.inkPrimary)
                .contentTransition(.numericText())
                .animation(.easeInOut(duration: 0.08), value: displayValue)

            HStack(spacing: Theme.Spacing.tight) {
                Text((displayPnlPct >= 0 ? "▲ +" : "▼ ") + String(format: "%.2f%%", abs(displayPnlPct)))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote).weight(.semibold))
                    .foregroundStyle(displayPnlPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                if let d = displayDate {
                    Text("·")
                        .foregroundStyle(Theme.inkTertiary)
                    Text(dateString(from: d))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .animation(.easeInOut(duration: 0.08), value: displayPnlPct)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Chart body (fill + glow line + scrub overlay)

    private var chartBody: some View {
        GeometryReader { geo in
            let rect = CGRect(origin: .zero, size: geo.size)
            let pts = ImmersiveChartGeometry.points(values: values, in: rect)

            ZStack {
                // Gradient area fill — fades in with the draw-in.
                GlowAreaShape(values: values)
                    .fill(fillGradient)
                    .opacity(Double(drawProgress))

                // Soft outer glow — a wide blurred copy of the curve.
                GlowLineShape(values: values)
                    .trim(from: 0, to: drawProgress)
                    .stroke(lineColor.opacity(0.45),
                            style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round))
                    .blur(radius: 9)

                // Crisp neon line.
                GlowLineShape(values: values)
                    .trim(from: 0, to: drawProgress)
                    .stroke(lineColor,
                            style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))

                // Scrub crosshair + dot + floating tooltip.
                if let i = scrubIndex, pts.indices.contains(i) {
                    scrubOverlay(point: pts[i], in: geo.size, index: i)
                }
            }
            .contentShape(Rectangle())
            .gesture(scrubGesture(in: geo.size))
        }
    }

    // MARK: Scrub overlay

    @ViewBuilder
    private func scrubOverlay(point pt: CGPoint, in size: CGSize, index i: Int) -> some View {
        // Dashed vertical crosshair.
        Path { p in
            p.move(to: CGPoint(x: pt.x, y: 0))
            p.addLine(to: CGPoint(x: pt.x, y: size.height))
        }
        .stroke(Theme.inkTertiary.opacity(0.55),
                style: StrokeStyle(lineWidth: 1, dash: [5, 4]))

        // Dot on the line with a white ring.
        Circle()
            .fill(lineColor)
            .frame(width: 9, height: 9)
            .overlay(Circle().stroke(Theme.canvas, lineWidth: 1.5))
            .shadow(color: lineColor.opacity(0.6), radius: 4)
            .position(pt)

        // Floating price tooltip, clamped within the chart width.
        if let d = displayDate {
            ScrubTooltipView(price: snapshots[i].totalValue, date: d)
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
                guard values.count > 1, size.width > 0 else { return }
                let ratio = min(max(value.location.x / size.width, 0), 1)
                let idx = Int(round(ratio * CGFloat(values.count - 1)))
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

// MARK: - Range slicing

extension Array where Element == PortfolioValuationSnapshot {
    /// Date-based slice (ascending snapshots) so "1Y" is one year even when two years are fetched.
    /// Always keeps at least two points so the chart can draw.
    func ranged(_ range: TimeRange) -> [PortfolioValuationSnapshot] {
        guard let lastDate = last?.parsedDate else { return [] }
        let cal = Calendar.current
        let cutoff: Date?
        switch range {
        case .day:         cutoff = cal.date(byAdding: .day, value: -1, to: lastDate)
        case .week:        cutoff = cal.date(byAdding: .day, value: -7, to: lastDate)
        case .month:       cutoff = cal.date(byAdding: .month, value: -1, to: lastDate)
        case .threeMonths: cutoff = cal.date(byAdding: .month, value: -3, to: lastDate)
        case .sixMonths:   cutoff = cal.date(byAdding: .month, value: -6, to: lastDate)
        case .year:        cutoff = cal.date(byAdding: .year, value: -1, to: lastDate)
        case .all:         cutoff = nil
        }
        guard let cutoff else { return self }
        let slice = filter { $0.parsedDate >= cutoff }
        return slice.count >= 2 ? slice : Array(suffix(2))
    }

    /// True when P&L ended the range at or above where it started.
    var pnlChangeIsPositive: Bool {
        guard let first = first, let last = last else { return true }
        return last.totalPnl - first.totalPnl >= 0
    }
}

// MARK: - ImmersiveChartTint ViewModifier
//
// Soft top-anchored colour wash behind a hero chart so the screen background
// subtly picks up the bullish / bearish tone. Used by Home and Analysis screens.

struct ImmersiveChartTint: ViewModifier {
    let isPositive: Bool

    func body(content: Content) -> some View {
        content.overlay(alignment: .top) {
            (isPositive ? Theme.bullGreen : Theme.bearRed)
                .opacity(0.07)
                .frame(height: UIScreen.main.bounds.height * 0.35)
                .blur(radius: 40)
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
