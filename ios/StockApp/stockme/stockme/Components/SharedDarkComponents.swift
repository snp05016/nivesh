import SwiftUI

// MARK: - Shared dark-redesign components
// Defined once here so every screen (Home, Watchlist, Portfolio, Analysis)
// can reuse them without duplicate-symbol conflicts.

// MARK: - Global UI Consistency Mandate components
// One canonical implementation of each, reused app-wide (AGENTS Global Mandate G2/G3/G5/G6/G10).

/// G2 — the single percentage badge style for the entire app.
struct ChangeBadge: View {
    let value: Double   // percentage
    var body: some View {
        let up = value >= 0
        Text((up ? "▲ " : "▼ ") + IndianFormatter.percent(abs(value)))
            .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote).weight(.semibold))
            .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.18))
            .clipShape(Capsule())
    }
}

/// G5 — the "Nivesh निवेश" identity chip shown top-right on root tab screens.
struct NiveshBrandChip: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Text("Nivesh")
                .font(Theme.engravedSerif(size: 12, weight: .semibold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
            Text("निवेश")
                .font(Theme.hindiFont(size: 11, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
        }
    }
}

/// G6 — per-ticker tile tint (the sole sanctioned Color(hue:) site — see AGENTS §8.3).
extension String {
    var tileColor: Color {
        let hues: [Double]        = [0.60, 0.63, 0.58, 0.55, 0.65, 0.68, 0.57, 0.61]
        let saturations: [Double] = [0.50, 0.45, 0.55, 0.42, 0.48, 0.52, 0.46, 0.50]
        let idx = abs(self.hashValue) % hues.count
        return Color(hue: hues[idx], saturation: saturations[idx], brightness: 0.30)
    }
}

/// G3 — canonical chart time-range domain + underline selector.
enum TimeRange: String, CaseIterable, Hashable {
    case day, week, month, year, all
    var label: String {
        switch self {
        case .day:   return "1D"
        case .week:  return "1W"
        case .month: return "1M"
        case .year:  return "1Y"
        case .all:   return "ALL"
        }
    }
}

struct TimeRangeSelector: View {
    @Binding var selected: TimeRange
    let ranges: [TimeRange]
    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            ForEach(ranges, id: \.self) { range in
                Button(action: { HapticManager.selection(); selected = range }) {
                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text(range.label)
                            .font(Theme.officialStampFont(size: 10)).tracking(0.5)
                            .foregroundStyle(selected == range ? Theme.securityGold : Theme.inkTertiary)
                        Rectangle()
                            .fill(selected == range ? Theme.securityGold : Color.clear)
                            .frame(height: 1.5)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.medium)
                }
                .buttonStyle(EKPressStyle())
            }
        }
    }
}

/// G10 — the canonical scrub tooltip for every scrubbable chart.
struct ScrubTooltipView: View {
    let price: Double
    let date: Date
    var body: some View {
        Text(IndianFormatter.price(price) + " · " + date.formatted(.dateTime.day().month(.abbreviated)))
            .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
            .foregroundStyle(Theme.inkPrimary)
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

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
