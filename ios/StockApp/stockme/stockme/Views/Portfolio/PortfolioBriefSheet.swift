import SwiftUI

struct PortfolioBriefSheet: View {
    let portfolioValue: Double
    let pnl: Double
    let holdings: [PortfolioHolding]
    @Environment(\.dismiss) var dismiss
    // UX-18: "Hide Portfolio Values" must mask the brief too, not just the Portfolio hero and rows.
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("PORTFOLIO BRIEF")
                            .font(Theme.officialStampFont(size: 10)).tracking(1.5)
                            .foregroundStyle(Theme.securityGold)
                        Text("Your snapshot")
                            .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer()
                    Button(action: { HapticManager.selection(); dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2).foregroundStyle(Theme.inkTertiary)
                    }.buttonStyle(EKPressStyle())
                    .accessibilityLabel("Close")
                }

                GuillocheDivider()

                // Summary
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("VALUE").font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                        Text(hideValues ? "₹ ••••" : IndianFormatter.priceCompact(portfolioValue))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline)).foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("P&L").font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                        // priceCompact keeps the minus ("-₹1.25 L"); only gains need an explicit "+".
                        Text(hideValues ? "₹ ••••" : (pnl > 0 ? "+" : "") + IndianFormatter.priceCompact(pnl))
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                            .foregroundStyle(hideValues ? Theme.inkPrimary : (pnl >= 0 ? Theme.bullGreen : Theme.bearRed))
                    }
                }
                .padding(Theme.Spacing.card).banknoteCard()

                // Gainers and losers never overlap, so a small portfolio cannot list a stock twice.
                let split = Self.performers(holdings)
                if !split.top.isEmpty {
                    GuillocheDivider()
                    Text("TOP PERFORMERS")
                        .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                    ForEach(split.top) { BriefPerformerRow(holding: $0) }
                }
                if !split.attention.isEmpty {
                    GuillocheDivider()
                    Text("NEEDS ATTENTION")
                        .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                    ForEach(split.attention) { BriefPerformerRow(holding: $0) }
                }
            }
            .padding(Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    /// Top 3 gainers (pnl% > 0, best first) and up to 3 losers (pnl% < 0, worst first).
    static func performers(_ holdings: [PortfolioHolding]) -> (top: [PortfolioHolding], attention: [PortfolioHolding]) {
        // Unpriced holdings are valued at cost (P&L 0); keep them out of both lists.
        let sorted = holdings.filter { $0.priceAvailable }.sorted { $0.pnlPercent > $1.pnlPercent }
        return (Array(sorted.filter { $0.pnlPercent > 0 }.prefix(3)),
                Array(sorted.reversed().filter { $0.pnlPercent < 0 }.prefix(3)))
    }
}

private struct BriefPerformerRow: View {
    let holding: PortfolioHolding

    var body: some View {
        HStack {
            Text(holding.stock.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
            Spacer()
            Text(IndianFormatter.percent(holding.pnlPercent))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .font(Theme.serialNumberFont(size: 13))
                .foregroundStyle(holding.pnlPercent >= 0 ? Theme.bullGreen : Theme.bearRed)
        }
        .padding(.vertical, Theme.Spacing.small)
    }
}
