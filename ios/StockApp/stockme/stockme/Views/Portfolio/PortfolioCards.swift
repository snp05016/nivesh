import SwiftUI

// MARK: - Portfolio Risk Card

struct PortfolioRiskCard: View {
    let riskAnalysis: RiskAnalysis?

    // NOTE: signalEmerald/signalRuby are scheme-aware (Theme.bullGreen /
    // Theme.bearRed); their >=4.5:1 contrast on every theme canvas is
    // enforced by stockmeTests/ThemeContrastTests.swift.
    var riskColor: Color {
        guard let score = riskAnalysis?.riskScore else { return Theme.securityGold }
        if score <= 4 { return Theme.signalEmerald }
        if score <= 6 { return Theme.securityGold }
        return Theme.signalRuby
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                Text("PORTFOLIO RISK")
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)
                Spacer()
                if let label = riskAnalysis?.riskScoreLabel {
                    Text(label)
                        .font(.caption2)
                        .foregroundStyle(riskColor)
                        .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                        .background(riskColor.opacity(0.15))
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }

            // Risk meter — 10 segments
            if let score = riskAnalysis?.riskScore {
                HStack(spacing: Theme.Spacing.small) {
                    ForEach(1...10, id: \.self) { i in
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(i <= score ? riskColor : Theme.canvasDeep)
                            .frame(height: 8)
                    }
                }
            }

            // Beta
            if let beta = riskAnalysis?.portfolioBeta {
                Text("β \(String(format: "%.2f", beta))")
                    .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .financeTerm("Beta")
            }

            // Concentration warnings
            if let warnings = riskAnalysis?.concentrationRisks, !warnings.isEmpty {
                HStack(spacing: Theme.Spacing.tight) {
                    ForEach(warnings) { w in
                        Text("\(w.ticker) \(String(format: "%.0f", w.pctOfPortfolio))%")
                            .font(.caption2)
                            .foregroundStyle(Theme.onStatus)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.signalRuby)
                            .cornerRadius(Theme.CornerRadius.small)
                    }
                }
            }

            // Correlation warning
            if let pair = riskAnalysis?.highestCorrelationPair, pair.correlation > 0.7 {
                Text("\(pair.tickerA) ↔ \(pair.tickerB) highly correlated")
                    .font(.caption)
                    .foregroundStyle(Theme.securityGold)
            }

            // Summary
            if let summary = riskAnalysis?.riskSummary {
                Text(summary)
                    .font(.caption.italic())
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding()
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

// MARK: - Red Flags Section

struct RedFlagsSection: View {
    let redFlags: RedFlagsResponse?
    let onTickerTap: (String) -> Void
    @State private var isExpanded = false

    var body: some View {
        if let rf = redFlags, rf.totalFlags > 0 {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                // Header
                Button(action: { HapticManager.selection(); withAnimation(.easeInOut(duration: 0.25)) { isExpanded.toggle() } }) {
                    HStack {
                        Text("⚠")
                            .font(.caption)
                        Text("RED FLAGS")
                            .font(Theme.sectionCapsLabel())
                            .tracking(1.5)
                            .foregroundStyle(Theme.signalRuby)
                        Text("\(rf.totalFlags)")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(Theme.onStatus)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.signalRuby)
                            .clipShape(Capsule())
                        Spacer()
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                .buttonStyle(.plain)

                if isExpanded {
                    ForEach(rf.flags) { flag in
                        Button {
                            HapticManager.selection()
                            onTickerTap(flag.ticker)
                        } label: {
                            HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                                Text(flag.severity == "CRITICAL" ? "🔴" : flag.severity == "WARNING" ? "🟡" : "🔵")
                                    .font(.caption)
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    HStack {
                                        Text(flag.ticker)
                                            .font(Theme.monoTabular(size: 12, relativeTo: .caption).weight(.bold))
                                            .foregroundStyle(Theme.inkPrimary)
                                        Text(flag.flagType.replacingOccurrences(of: "_", with: " "))
                                            .font(.caption2)
                                            .foregroundStyle(Theme.inkSecondary)
                                            .tracking(0.5)
                                    }
                                    Text(flag.detail)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .buttonStyle(.plain)
                    }

                    if let summary = rf.summary, !summary.isEmpty {
                        Text(summary)
                            .font(.caption.italic())
                            .foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, Theme.Spacing.small)
                    }
                }
            }
            .padding()
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.signalRuby.opacity(0.3), lineWidth: 0.5))
        }
    }
}

struct TabNoteButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: { HapticManager.selection(); action() }) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(isSelected ? Theme.inkPrimary : Theme.inkTertiary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .background(isSelected ? Theme.inkSecondary.opacity(0.05) : Color.clear)
        }
        .overlay(
            VStack {
                if isSelected {
                    Spacer()
                    Rectangle().fill(Theme.securityGold).frame(height: 2)
                }
            }
        )
    }
}

/// Screen B holding row — colored allocation dot, ticker, shares, value, ChangeBadge.
/// Lives inside a single shared `.banknoteCard()` (no per-row card).
struct HoldingNoteRow: View {
    let holding: PortfolioHolding
    var color: Color = Theme.inkSecondary
    var signalWarning: SignalWarning? = nil
    var hideValues: Bool = false

    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            Circle().fill(color).frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(holding.stock.ticker)
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("\(DecimalText.editable(holding.shares, maxFractionDigits: 4)) shares")
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
                if let note = holding.notes, !note.isEmpty {
                    Text(note)
                        .font(Font.custom("Georgia", size: 12, relativeTo: .caption).italic())
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
                if let warning = signalWarning {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption2)
                        Text(warning.signalFlipped ? "SIGNAL CHANGED" : "BEARISH")
                            .font(Theme.officialStampFont(size: 7))
                    }
                    .foregroundStyle(Theme.inkPrimary)
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                    .background(Theme.bearRed.opacity(0.18))
                    .clipShape(Capsule())
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                if holding.priceAvailable {
                    Text(hideValues ? "₹ ••••" : IndianFormatter.price(holding.currentValue))
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
                        .foregroundStyle(Theme.inkPrimary)
                    if !hideValues { ChangeBadge(value: holding.pnlPercent) }
                    if holding.priceStatus == "stale", let asOf = holding.priceAsOf {
                        Text("as of \(String(asOf.prefix(10)))")
                            .font(Theme.engravedSerif(size: 10, weight: .regular, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                } else {
                    Text("Price unavailable")
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }
}

/// Shared 6-colour allocation palette (donut segments + holding dots), Screen B.
let allocationPalette: [Color] = [
    Theme.bullGreen,
    Theme.securityGold,
    Theme.bearRed.opacity(0.8),
    Color(hue: 0.58, saturation: 0.5, brightness: 0.6),
    Color(hue: 0.72, saturation: 0.4, brightness: 0.65),
    Theme.inkSecondary
]

/// Screen B — hero value block: label, large price, two pills, brand chip.
struct PortfolioHeroBlock: View {
    let value: Double
    let totalPnL: Double
    let totalPnLPercent: Double
    let isLoading: Bool
    var hideValues: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("Portfolio · current value")
                        .font(Theme.officialStampFont(size: 9)).tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(hideValues ? "₹ ••••••" : IndianFormatter.price(value))
                        .font(.largeTitle.weight(.bold)).monospaced()
                        .foregroundStyle(Theme.inkPrimary)
                        .contentTransition(.numericText())
                }
                Spacer()
                NiveshBrandChip()
            }
            if !hideValues {
                HStack(spacing: Theme.Spacing.small) {
                    ChangeBadge(value: totalPnLPercent)
                    let up = totalPnL >= 0
                    Text((up ? "+" : "") + IndianFormatter.priceCompact(totalPnL) + " total")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                        .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.18))
                        .clipShape(Capsule())
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .shimmerPlaceholder(isLoading: isLoading)
    }
}

/// Arc angles (degrees, starting at -90 = 12 o'clock) for an allocation donut.
/// Non-positive values get no arc; the visual gap shrinks for slivers so an arc's
/// end never falls before its start (which would wrap into a near-full ring).
enum DonutGeometry {
    static func segments(values: [Double]) -> [(index: Int, start: Double, end: Double)] {
        let total = values.filter { $0 > 0 }.reduce(0, +)
        guard total > 0 else { return [] }
        var result: [(index: Int, start: Double, end: Double)] = []
        var start = -90.0
        for (i, v) in values.enumerated() where v > 0 {
            let sweep = v / total * 360
            let gap = min(1, sweep / 4)
            if sweep - 2 * gap > 0 {
                result.append((i, start + gap, start + sweep - gap))
            }
            start += sweep
        }
        return result
    }
}

/// Screen B — allocation donut + legend card.
struct PortfolioAllocationDonutCard: View {
    let holdings: [PortfolioHolding]
    private var total: Double { holdings.reduce(0) { $0 + $1.currentValue } }
    private var sorted: [PortfolioHolding] { holdings.sorted { $0.currentValue > $1.currentValue } }

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            ZStack {
                Canvas { ctx, size in
                    let lineW: CGFloat = 14
                    let radius = min(size.width, size.height) / 2 - lineW / 2
                    let center = CGPoint(x: size.width / 2, y: size.height / 2)
                    for seg in DonutGeometry.segments(values: sorted.map(\.currentValue)) {
                        var p = Path()
                        p.addArc(center: center, radius: radius,
                                 startAngle: .degrees(seg.start),
                                 endAngle: .degrees(seg.end), clockwise: false)
                        ctx.stroke(p, with: .color(allocationPalette[seg.index % allocationPalette.count]),
                                   style: StrokeStyle(lineWidth: lineW, lineCap: .butt))
                    }
                }
                .frame(width: UIScreen.main.bounds.width * 0.28, height: UIScreen.main.bounds.width * 0.28)
                VStack(spacing: Theme.Spacing.none) {
                    Text("\(holdings.count)")
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .title3).weight(.bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("STOCKS")
                        .font(Theme.officialStampFont(size: 8)).tracking(1.0)
                        .foregroundStyle(Theme.inkTertiary)
                }
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                ForEach(Array(sorted.prefix(4).enumerated()), id: \.element.id) { i, h in
                    HStack(spacing: Theme.Spacing.small) {
                        Circle().fill(allocationPalette[i % allocationPalette.count]).frame(width: 8, height: 8)
                        Text(h.stock.ticker)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        Text(total > 0 ? String(format: "%.1f%%", h.currentValue / total * 100) : "—")
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                if holdings.count > 4 {
                    Text("+ \(holdings.count - 4) more")
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct WatchlistRowView: View {
    let item: WatchlistItem
    var tags: [String] = []

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            // Left sage-green rule (no P&L signal)
            Rectangle()
                .fill(Theme.borderSage.opacity(0.6))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: item.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(item.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(1)
                    HStack {
                        Text(item.ticker)
                            .font(Theme.serialNumberFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                        if !tags.isEmpty {
                            Text(tags.joined(separator: ", "))
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.securityGold)
                        }
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(item.priceStatus == "unavailable" ? "--" : item.currentPrice.inrFormatted)
                        .contentTransition(.numericText())
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundStyle(Theme.inkPrimary)
                    let changeStr = (item.dayChangePct >= 0 ? "+" : "") + String(format: "%.2f%%", item.dayChangePct)
                    Text(changeStr)
                        .contentTransition(.numericText())
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(item.dayChangePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .banknoteCard()
    }
}

struct WatchlistSkeletonRow: View {
    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        HStack(spacing: Theme.Spacing.card) {
            Circle()
                .fill(Theme.inkTertiary.opacity(0.1))
                .frame(width: 40, height: 40)
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.15)).frame(width: colW * 0.37, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.1)).frame(width: colW * 0.17, height: 9)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.15)).frame(width: colW * 0.20, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.1)).frame(width: colW * 0.11, height: 9)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

struct EmptyHoldingsView: View {
    let onAdd: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No holdings yet")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkPrimary)
            Text("Record a trade to start tracking your portfolio.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundStyle(Theme.inkTertiary)
                .multilineTextAlignment(.center)
            Button(action: onAdd) {
                Text("ADD YOUR FIRST HOLDING")
                    .font(Theme.officialStampFont(size: 11))
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.securityGold)
                    .foregroundStyle(Theme.onAccent)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
            }
            .buttonStyle(EKPressStyle())
            .accessibilityLabel("Add your first holding")
            .padding(.top, Theme.Spacing.small)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
