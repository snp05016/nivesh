import SwiftUI

struct HoldersTabView: View {
    let isLoading: Bool
    let analystRatings: AnalystRatingsResponse?
    let fetchHolders: () async -> Void

    var body: some View {
        LazyVStack(spacing: Theme.Spacing.card) {
            if isLoading {
                SPSkeletonBlock(rows: 5)
            } else if let ratings = analystRatings {
                HoldersContentView(ratings: ratings)
            } else {
                SPEmptyStateView(message: "Holder data unavailable")
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.card)
        .task { await fetchHolders() }
    }
}

struct HoldersContentView: View {
    let ratings: AnalystRatingsResponse

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("ANALYST CONSENSUS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.top, Theme.Spacing.small)

            let total = ratings.buy + ratings.hold + ratings.sell
            if total > 0 {
                HStack(spacing: Theme.Spacing.card) {
                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("\(ratings.buy)")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.bullGreen)
                        Text("BUY").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                    }
                    .frame(maxWidth: .infinity)
                    .explainableTerm("Signal")

                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("\(ratings.hold)")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.holdAmber)
                        Text("HOLD").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                    }
                    .frame(maxWidth: .infinity)

                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("\(ratings.sell)")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.bearRed)
                        Text("SELL").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                    }
                    .frame(maxWidth: .infinity)
                    .explainableTerm("Signal")
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            } else {
                HStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "info.circle")
                        .foregroundStyle(Theme.inkTertiary)
                    Text("No analyst ratings available for this stock")
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }

            if let consensus = ratings.consensus {
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("ANALYST CONSENSUS")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)
                        Text(consensus.uppercased())
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .title3))
                            .foregroundStyle(Theme.securityGold)
                    }
                    Spacer()
                    BanknoteSignalBadge(text: consensus.uppercased(), color: Theme.securityGold, rotation: 1)
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
        }
    }
}
