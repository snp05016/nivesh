import SwiftUI

struct NewsTabView: View {
    @ObservedObject var vm: StockProfileViewModel

    var body: some View {
        LazyVStack(spacing: Theme.Spacing.card) {
            Text("LATEST NEWS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, Theme.Spacing.small)

            if vm.overviewLoading {
                SPSkeletonBlock(rows: 5)
            } else if let news = vm.quickInfo?.recentNews, !news.isEmpty {
                ForEach(news) { article in
                    SPNewsCardView(article: article)
                }
            } else {
                SPEmptyStateView(message: "No recent news for this stock")
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.card)
        .task { await vm.fetchOverview() }
    }
}

struct SPNewsCardView: View {
    let article: NewsItem

    var body: some View {
        Link(destination: URL(string: article.link) ?? URL(string: "https://www.google.com")!) {
            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                if let urlStr = article.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkTertiary.opacity(0.08))
                    }
                    .frame(width: UIScreen.main.bounds.width * 0.16, height: UIScreen.main.bounds.width * 0.16)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(article.title)
                        .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                        .multilineTextAlignment(.leading)
                        .lineLimit(3)
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(article.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.securityGold)
                        if let t = article.publishTime {
                            Text("•").foregroundStyle(Theme.inkTertiary)
                            Text(Date(timeIntervalSince1970: TimeInterval(t)), style: .relative)
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
                Spacer(minLength: Theme.Spacing.tight)
                Image(systemName: "arrow.up.right")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
    }
}
