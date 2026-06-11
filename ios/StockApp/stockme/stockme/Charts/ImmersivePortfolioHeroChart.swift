import SwiftUI

// MARK: - ImmersiveChartState

@Observable
final class ImmersiveChartState {
    var snapshots: [ValuationSnapshot] = []
    var visibleStartIndex: Int = 0
    var visibleEndIndex: Int = 0
    var scrubIndex: Int? = nil
    var scale: CGFloat = 1.0

    var visibleSnapshots: ArraySlice<ValuationSnapshot> {
        guard !snapshots.isEmpty else { return [] }
        let s = max(0, visibleStartIndex)
        let e = min(snapshots.count - 1, visibleEndIndex)
        guard s <= e else { return [] }
        return snapshots[s...e]
    }

    var displayValue: Double {
        if let idx = scrubIndex, snapshots.indices.contains(idx) {
            return snapshots[idx].totalValue
        }
        return snapshots.last?.totalValue ?? 0
    }

    var displayDate: Date? {
        if let idx = scrubIndex, snapshots.indices.contains(idx) {
            return snapshots[idx].parsedDate
        }
        return snapshots.last?.parsedDate
    }

    var isPositive: Bool {
        (snapshots.last?.totalPnl ?? 0) >= 0
    }

    var displayPnlPct: Double {
        if let idx = scrubIndex, snapshots.indices.contains(idx) {
            return snapshots[idx].pnlPercent
        }
        return snapshots.last?.pnlPercent ?? 0
    }

    func reset(snapshots: [ValuationSnapshot]) {
        self.snapshots = snapshots
        visibleStartIndex = 0
        visibleEndIndex = max(0, snapshots.count - 1)
        scrubIndex = nil
        scale = 1.0
    }
}

// MARK: - ImmersivePortfolioHeroChart

struct ImmersivePortfolioHeroChart: View {
    let snapshots: [ValuationSnapshot]

    @State private var chartState = ImmersiveChartState()

    private let chartHeight: CGFloat = UIScreen.main.bounds.height * 0.28

    var body: some View {
        Group {
            if snapshots.isEmpty {
                EmptyView()
            } else {
                ZStack(alignment: .topLeading) {
                    // Layer 1 — Immersive tint background
                    Color.clear
                        .immersiveChartTint(isPositive: chartState.isPositive)

                    // Layer 2 — Value/date overlay (non-interactive)
                    valueOverlay

                    // Layer 3 — Canvas chart
                    chartCanvas
                        .frame(height: chartHeight)
                        .padding(.horizontal, 0)

                    // Layer 4 — Gesture overlay
                    gestureOverlay
                        .frame(height: chartHeight)
                }
            }
        }
        .onAppear { chartState.reset(snapshots: snapshots) }
        .onChange(of: snapshots.count) { _, _ in chartState.reset(snapshots: snapshots) }
    }

    // MARK: - Value Overlay

    private var valueOverlay: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(IndianFormatter.priceCompact(chartState.displayValue))
                .font(.title.weight(.bold))
                .monospaced()
                .foregroundStyle(Theme.inkPrimary)
                .contentTransition(.numericText())
                .animation(.easeInOut(duration: 0.05), value: chartState.displayValue)

            HStack(spacing: Theme.Spacing.small) {
                if let d = chartState.displayDate {
                    Text(dateString(from: d))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                }
                let pnl = chartState.displayPnlPct
                Text((pnl >= 0 ? "+" : "") + String(format: "%.2f%%", pnl))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundStyle(pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .frame(maxWidth: .infinity, alignment: .leading)
        .allowsHitTesting(false)
    }

    // MARK: - Canvas Chart

    private var chartCanvas: some View {
        Canvas { context, size in
            let vp = Array(chartState.visibleSnapshots)
            guard vp.count > 1 else { return }

            let values = vp.map(\.totalValue)
            let mn = values.min() ?? 0
            let mx = values.max() ?? 1
            let rng = max(mx - mn, 1)
            let pad: CGFloat = 16
            let lineColor = chartState.isPositive ? Theme.bullGreen : Theme.bearRed

            func xFor(_ i: Int) -> CGFloat {
                CGFloat(i) / CGFloat(vp.count - 1) * size.width
            }
            func yFor(_ v: Double) -> CGFloat {
                pad + CGFloat((mx - v) / rng) * (size.height - 2 * pad)
            }

            // Gradient fill under line
            var fillPath = Path()
            fillPath.move(to: CGPoint(x: 0, y: size.height))
            for (i, pt) in vp.enumerated() {
                fillPath.addLine(to: CGPoint(x: xFor(i), y: yFor(pt.totalValue)))
            }
            fillPath.addLine(to: CGPoint(x: size.width, y: size.height))
            fillPath.closeSubpath()
            context.fill(fillPath, with: .color(lineColor.opacity(0.18)))

            // Chart line
            var linePath = Path()
            for (i, pt) in vp.enumerated() {
                let p = CGPoint(x: xFor(i), y: yFor(pt.totalValue))
                if i == 0 { linePath.move(to: p) }
                else { linePath.addLine(to: p) }
            }
            context.stroke(linePath, with: .color(lineColor),
                           style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))

            // Crosshair when scrubbing
            if let si = chartState.scrubIndex,
               chartState.snapshots.indices.contains(si) {
                let localIdx = si - chartState.visibleStartIndex
                guard localIdx >= 0, localIdx < vp.count else { return }
                let cx = xFor(localIdx)
                let cy = yFor(chartState.snapshots[si].totalValue)

                var crosshair = Path()
                crosshair.move(to: CGPoint(x: cx, y: 0))
                crosshair.addLine(to: CGPoint(x: cx, y: size.height))
                context.stroke(crosshair, with: .color(Theme.inkTertiary),
                               style: StrokeStyle(lineWidth: 1, dash: [4, 4]))

                context.fill(
                    Path(ellipseIn: CGRect(x: cx - 4, y: cy - 4, width: 8, height: 8)),
                    with: .color(lineColor)
                )
            }
        }
        .padding(.horizontal, 0)
    }

    // MARK: - Gesture Overlay

    private var gestureOverlay: some View {
        Color.clear
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { value in
                        let vp = Array(chartState.visibleSnapshots)
                        guard !vp.isEmpty else { return }
                        let screenW = UIScreen.main.bounds.width
                        let idx = min(max(Int(value.location.x / screenW * CGFloat(vp.count)), 0), vp.count - 1)
                        let globalIdx = chartState.visibleStartIndex + idx
                        if chartState.scrubIndex != globalIdx {
                            HapticManager.selection()
                            chartState.scrubIndex = globalIdx
                        }
                    }
                    .onEnded { _ in
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                            chartState.scrubIndex = nil
                        }
                    }
            )
            .simultaneousGesture(
                MagnificationGesture()
                    .onChanged { scale in
                        let center = (chartState.visibleStartIndex + chartState.visibleEndIndex) / 2
                        let currentWindow = chartState.visibleEndIndex - chartState.visibleStartIndex
                        let count = chartState.snapshots.count
                        guard count > 1 else { return }
                        let newWindow = max(7, min(count - 1, Int(CGFloat(currentWindow) / scale)))
                        let half = newWindow / 2
                        chartState.visibleStartIndex = max(0, center - half)
                        chartState.visibleEndIndex = min(count - 1, center + half)
                    }
            )
    }

    // MARK: - Helpers

    private func dateString(from date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "d MMM ''yy"
        return f.string(from: date)
    }
}

// MARK: - ImmersiveChartTint ViewModifier

struct ImmersiveChartTint: ViewModifier {
    let isPositive: Bool

    func body(content: Content) -> some View {
        content.overlay(alignment: .top) {
            (isPositive ? Theme.bullGreen : Theme.bearRed)
                .opacity(0.07)
                .frame(height: UIScreen.main.bounds.height * 0.35)
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
