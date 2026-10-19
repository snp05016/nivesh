import SwiftUI

// MARK: - Design System Constants (Phase 1 redesign — all Theme.* tokens)

private let bullGreen  = Theme.dataPositive
private let bearRed    = Theme.dataNegative
private let goldAccent = Theme.goldPrimary
private let dimText    = Theme.inkSecondary
private let subtleText = Theme.inkTertiary

// MARK: - NiveshBulletRow

struct NiveshBulletRow: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Circle()
                .fill(goldAccent)
                .frame(width: 4, height: 4)
                .padding(.top, Theme.Spacing.tight)

            Text(stripEmoji(text))
                .font(.body)
                .foregroundStyle(.primary.opacity(0.80))
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(3)
        }
    }
}

// MARK: - PriorityPill

struct PriorityPill: View {
    let label: String
    let color: Color

    var body: some View {
        Text(label)
            .font(.caption2.weight(.bold)).monospaced()
            .tracking(1.5)
            .foregroundStyle(color)
            .padding(.horizontal, Theme.Spacing.tight)
            .padding(.vertical, Theme.Spacing.small)
            .background(color.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(color.opacity(0.25), lineWidth: 0.5)
            )
            .cornerRadius(Theme.CornerRadius.small)
    }
}

// MARK: - ADBreathBar

struct ADBreathBar: View {
    let advancing: Int
    let declining: Int

    private var advancingRatio: CGFloat {
        let total = CGFloat(advancing + declining)
        guard total > 0 else { return 0.5 }
        return CGFloat(advancing) / total
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text("ADVANCE / DECLINE BREADTH")
                .font(.caption2.weight(.semibold)).monospaced()
                .tracking(1.5)
                .foregroundStyle(dimText)

            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(bearRed.opacity(0.15))
                    .frame(maxWidth: .infinity)

                BreadthFillShape(ratio: advancingRatio)
                    .fill(
                        LinearGradient(
                            colors: [bullGreen.opacity(0.9), bullGreen.opacity(0.6)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
            }
            .frame(height: Theme.Spacing.medium)
            .cornerRadius(Theme.CornerRadius.small)

            HStack {
                HStack(spacing: Theme.Spacing.small) {
                    Circle().fill(bullGreen).frame(width: 5, height: 5)
                    Text("\(advancing) advancing")
                        .font(.caption)
                        .foregroundStyle(bullGreen)
                }
                Spacer()
                HStack(spacing: Theme.Spacing.small) {
                    Text("\(declining) declining")
                        .font(.caption)
                        .foregroundStyle(bearRed)
                    Circle().fill(bearRed).frame(width: 5, height: 5)
                }
            }
        }
    }
}

private struct BreadthFillShape: Shape {
    let ratio: CGFloat

    func path(in rect: CGRect) -> Path {
        let clamped = min(max(ratio, 0), 1)
        let fillRect = CGRect(
            x: rect.minX,
            y: rect.minY,
            width: rect.width * clamped,
            height: rect.height
        )
        return Path(roundedRect: fillRect, cornerRadius: Theme.CornerRadius.small)
    }
}

// MARK: - IndexRow

struct IndexRow: View {
    let name: String
    let value: String
    let change: Double

    var changeColor: Color { change >= 0 ? bullGreen : bearRed }
    var changeText: String {
        let sign = change >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", change))%"
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(changeColor.opacity(0.7))
                .frame(width: 2, height: 20)

            Text(name)
                .font(.footnote.weight(.medium))
                .foregroundStyle(.primary.opacity(0.85))

            Spacer()

            Text(value)
                .contentTransition(.numericText())
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.85))

            Text(changeText)
                .contentTransition(.numericText())
                .sensoryFeedback(trigger: change) { _, _ in
                    HapticManager.isEnabled() ? (change >= 0 ? SensoryFeedback.increase : SensoryFeedback.decrease) : nil
                }
                .font(.caption.weight(.semibold)).monospaced()
                .foregroundStyle(changeColor)
                .frame(minWidth: 60, alignment: .trailing)
        }
        .padding(.vertical, Theme.Spacing.small)
    }
}

// MARK: - MomentumSectionView

struct MomentumSectionView: View {
    let stance: String
    let stocks: [MomentumTicker]

    var stanceColor: Color { stance == "BULLISH" ? bullGreen : bearRed }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack(spacing: Theme.Spacing.medium) {
                Rectangle()
                    .fill(stanceColor)
                    .frame(width: 3, height: 14)
                    .cornerRadius(1.5)

                Text(stance)
                    .font(.caption2.weight(.bold)).monospaced()
                    .tracking(2.0)
                    .foregroundStyle(stanceColor)

                Spacer()

                Text("\(stocks.count) stocks")
                    .font(.caption2)
                    .foregroundStyle(subtleText)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .background(stanceColor.opacity(0.06))

            VStack(spacing: Theme.Spacing.none) {
                ForEach(stocks) { stock in
                    MomentumStockRow(stock: stock, stanceColor: stanceColor)
                    if stock.id != stocks.last?.id {
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5).padding(.leading, Theme.Spacing.medium)
                    }
                }
            }
        }
        .background(stanceColor.opacity(0.03))
        .cornerRadius(Theme.CornerRadius.large)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .stroke(stanceColor.opacity(0.15), lineWidth: 0.5)
        )
    }
}

// MARK: - SignalBadge

struct SignalBadge: View {
    let label: String

    var isDeathCross: Bool { label.lowercased().contains("death") }
    var badgeColor: Color { isDeathCross ? bearRed : Color.primary.opacity(0.35) }

    var body: some View {
        Text(label)
            .font(.caption2.weight(isDeathCross ? .bold : .medium)).monospaced()
            .tracking(0.5)
            .foregroundStyle(isDeathCross ? bearRed : Color.primary.opacity(0.55))
            .padding(.horizontal, Theme.Spacing.tight)
            .padding(.vertical, Theme.Spacing.small)
            .background(
                isDeathCross
                    ? bearRed.opacity(0.10)
                    : Color.primary.opacity(0.05)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(
                        isDeathCross ? bearRed.opacity(0.3) : Color.primary.opacity(0.12),
                        lineWidth: 0.5
                    )
            )
            .cornerRadius(Theme.CornerRadius.small)
    }
}

// MARK: - MomentumStockRow

struct MomentumStockRow: View {
    let stock: MomentumTicker
    let stanceColor: Color

    var signalText: String {
        switch stock.crossover {
        case "golden_cross": return "Golden Cross"
        case "death_cross": return "Death Cross"
        default:
            return stock.lastPrice > stock.ma50 ? "Above 50MA" : "Below 50MA"
        }
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(stock.ticker)
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.90))
                .frame(minWidth: 80, alignment: .leading)

            Text(IndianFormatter.price(stock.lastPrice))
                .font(.footnote).monospaced()
                .foregroundStyle(.primary.opacity(0.70))

            Spacer()

            SignalBadge(label: signalText)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - MacroGroupView

struct MacroGroupView: View {
    let groupTitle: String
    let rows: [MacroItem]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            Text(groupTitle)
                .font(.caption2.weight(.semibold)).monospaced()
                .tracking(1.8)
                .foregroundStyle(dimText)
                .padding(.bottom, Theme.Spacing.medium)

            VStack(spacing: Theme.Spacing.none) {
                ForEach(rows) { row in
                    MacroRowView(row: row)
                    if row.id != rows.last?.id {
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                    }
                }
            }
        }
    }
}

// MARK: - MacroRowView

struct MacroRowView: View {
    let row: MacroItem

    var changeColor: Color { row.changePct >= 0 ? bullGreen : bearRed }

    var body: some View {
        HStack(alignment: .center, spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(row.name)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.primary.opacity(0.85))
            }

            Spacer()

            Text(String(format: "%.2f", row.price))
                .contentTransition(.numericText())
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.85))
                .frame(minWidth: 70, alignment: .trailing)

            Text("\(row.changePct >= 0 ? "+" : "")\(String(format: "%.2f", row.changePct))%")
                .contentTransition(.numericText())
                .font(.caption.weight(.semibold)).monospaced()
                .foregroundStyle(changeColor)
                .padding(.horizontal, Theme.Spacing.tight)
                .padding(.vertical, Theme.Spacing.xSmall)
                .background(changeColor.opacity(0.08))
                .cornerRadius(Theme.CornerRadius.small)
                .frame(minWidth: 60, alignment: .trailing)
        }
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - FundReturnRow

struct FundReturnRow: View {
    let rank: Int
    let fundName: String
    let returnPercent: Double
    let maxAbsReturn: Double

    var returnColor: Color { returnPercent >= 0 ? bullGreen : bearRed }
    var barWidth: CGFloat {
        guard maxAbsReturn > 0 else { return 0 }
        return CGFloat(abs(returnPercent) / maxAbsReturn)
    }
    var formattedReturn: String {
        let sign = returnPercent >= 0 ? "+" : "-"
        return "\(sign)\(String(format: "%.1f", abs(returnPercent)))%"
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text("\(rank)")
                .font(.caption.weight(.medium)).monospaced()
                .foregroundStyle(subtleText)
                .frame(width: Theme.Spacing.standard)

            Text(fundName)
                .font(.footnote.weight(.medium))
                .foregroundStyle(.primary.opacity(0.85))
                .lineLimit(1)

            Spacer()

            HStack(spacing: Theme.Spacing.tight) {
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Color.primary.opacity(0.06))
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(returnColor.opacity(0.7))
                        .frame(width: UIScreen.main.bounds.width * 0.13 * barWidth)
                }
                .frame(width: UIScreen.main.bounds.width * 0.13, height: 4)

                Text(formattedReturn)
                    .font(.caption.weight(.semibold)).monospaced()
                    .foregroundStyle(returnColor)
                    .frame(minWidth: 40, alignment: .trailing)
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
    }
}

/// Morning-brief mood marker: the arrow/dash shape carries the mood alongside the colour,
/// so it is not conveyed by colour alone (UX-25). VoiceOver reads it via the button's value.
struct MorningBriefMoodBadge: View {
    let mood: String?
    let size: CGFloat

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: size, weight: .bold))
            .foregroundStyle(color)
            .background(Circle().fill(Theme.canvasDeep))
            .accessibilityHidden(true)
    }

    private var symbol: String {
        switch mood {
        case "positive": return "arrowtriangle.up.circle.fill"
        case "negative": return "arrowtriangle.down.circle.fill"
        default: return "minus.circle.fill"
        }
    }

    private var color: Color {
        switch mood {
        case "positive": return Theme.bullGreen
        case "negative": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }

    static func accessibilityValue(mood: String?, hiddenToday: Bool) -> String {
        guard hiddenToday else { return "Shown" }
        switch mood {
        case "positive", "negative", "cautious": return "Hidden today, mood \(mood ?? "")"
        default: return "Hidden today, mood unavailable"
        }
    }
}
