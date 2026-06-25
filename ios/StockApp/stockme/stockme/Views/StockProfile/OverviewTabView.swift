import SwiftUI

struct OverviewTabView: View {
    let ticker: String
    @ObservedObject var vm: StockProfileViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                if vm.overviewLoading {
                    SPSkeletonBlock(rows: 6)
                } else if let info = vm.quickInfo {
                    OverviewContentView(ticker: ticker, info: info)
                } else {
                    SPEmptyStateView(message: "Overview unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchOverview() }
    }
}

struct OverviewContentView: View {
    let ticker: String
    let info: QuickInfo

    var body: some View {
        VStack(spacing: Theme.sectionSpacing) {
            // Price hero
            VStack(spacing: Theme.Spacing.small) {
                Text(ticker.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                Text(info.price != nil ? IndianFormatter.price(info.price!) : "—")
                    .font(Theme.serialNumberFont(size: 32, relativeTo: .largeTitle))
                    .foregroundStyle(Theme.inkPrimary)
                let changePct = info.changePercent ?? 0.0
                let up = changePct >= 0
                Text(String(format: "%@%.2f%%", up ? "▲ " : "▼ ", abs(changePct)))
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                    .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(maxWidth: .infinity)
            .padding(Theme.Spacing.card)
            .banknoteCard()

            SectionGuillocheDivider().padding(.horizontal, 0)

            // Key metrics grid
            let metrics: [(String, String, String, String)] = [
                ("P/E Ratio", info.peRatio.map { String(format: "%.1f", $0) } ?? "—", "P/E RATIO", "Price-to-earnings ratio: share price divided by annual earnings per share. Higher = market expects more growth."),
                ("52W High", info.week52High.map { IndianFormatter.price($0) } ?? "—", "52-WEEK HIGH", "The highest price the stock traded at in the past 52 weeks."),
                ("52W Low", info.week52Low.map { IndianFormatter.price($0) } ?? "—", "52-WEEK LOW", "The lowest price the stock traded at in the past 52 weeks."),
                ("Sector", info.sector ?? "—", "SECTOR", "The broad industry segment this company operates in."),
            ]

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.card) {
                ForEach(metrics, id: \.0) { label, value, glossaryTerm, _ in
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text(label.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)
                            .explainableTerm(label)
                        Text(value)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Spacing.standard)
                    .banknoteCard()
                    .explainableTerm(glossaryTerm)
                }
            }

            // AI Signal badge
            if let signal = info.signal {
                HStack(spacing: Theme.Spacing.standard) {
                    BanknoteSignalBadge(text: signal.rawValue, color: signal.color, rotation: -2)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("AI SIGNAL")
                            .font(Theme.officialStampFont(size: 9))
                            .tracking(1.5)
                            .foregroundStyle(Theme.inkTertiary)
                        Text("Based on multi-agent Bull/Bear dialectic analysis")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer()
                }
                .padding(Theme.Spacing.standard)
                .banknoteCard()
                .explainableTerm("Signal")
            }
        }
    }
}
