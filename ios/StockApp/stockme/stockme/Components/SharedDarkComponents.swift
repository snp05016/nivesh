import SwiftUI

// MARK: - Shared dark-redesign components
// Defined once here so every screen (Home, Watchlist, Portfolio, Analysis)
// can reuse them without duplicate-symbol conflicts.

/// Pill badge for +/-% or +/-₹ values — green or red tinted.
struct SignalBadgePill: View {
    let value: Double
    let isPercent: Bool

    private var isPositive: Bool { value >= 0 }
    private var label: String {
        let prefix = isPositive ? "+" : ""
        return isPercent
            ? "\(prefix)\(String(format: "%.2f", value))%"
            : "\(prefix)\(IndianFormatter.priceWithoutSymbol(value))"
    }

    var body: some View {
        Text(label)
            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
            .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.small)
            .background((isPositive ? Theme.bullGreen : Theme.bearRed).opacity(0.1))
            .clipShape(Capsule())
    }
}

/// Simple line chart with green/red glow fill — no axes, pure visual.
/// Reusable for hero charts, portfolio charts, and list-row sparklines.
struct GlowLineChart: View {
    let dataPoints: [Double]
    let isPositive: Bool
    var lineWidth: CGFloat = 2

    private var lineColor: Color { isPositive ? Theme.bullGreen : Theme.bearRed }
    private var fillGradient: LinearGradient {
        isPositive ? Theme.chartBullGradient : Theme.chartBearGradient
    }

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let pts = normalizedPoints(in: CGSize(width: w, height: h))
            ZStack {
                if pts.count > 1 {
                    // Fill area
                    Path { path in
                        path.move(to: CGPoint(x: pts[0].x, y: h))
                        path.addLine(to: pts[0])
                        for pt in pts.dropFirst() { path.addLine(to: pt) }
                        path.addLine(to: CGPoint(x: pts.last!.x, y: h))
                        path.closeSubpath()
                    }
                    .fill(fillGradient)

                    // Line
                    Path { path in
                        path.move(to: pts[0])
                        for pt in pts.dropFirst() { path.addLine(to: pt) }
                    }
                    .stroke(lineColor, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round, lineJoin: .round))
                    .shadow(color: lineColor.opacity(0.5), radius: 8, x: 0, y: 2)
                }
            }
        }
    }

    private func normalizedPoints(in size: CGSize) -> [CGPoint] {
        guard dataPoints.count > 1 else { return [] }
        let minV = dataPoints.min()!
        let maxV = dataPoints.max()!
        let range = maxV - minV
        let step = size.width / CGFloat(dataPoints.count - 1)
        guard range > 0 else {
            // Flat series — draw a centered horizontal line
            return dataPoints.enumerated().map { i, _ in
                CGPoint(x: CGFloat(i) * step, y: size.height / 2)
            }
        }
        return dataPoints.enumerated().map { i, v in
            CGPoint(
                x: CGFloat(i) * step,
                y: size.height - CGFloat((v - minV) / range) * size.height * 0.88 - size.height * 0.06
            )
        }
    }
}
