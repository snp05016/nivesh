import SwiftUI

// MARK: - News & Multimedia Hub (Section 8)

struct NewsMultimediaView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var articles: [NewsArticleItem] = []
    @State private var videos: [YouTubeVideoItem] = []
    @State private var expertTab: Int = 0  // 0=Fundamental, 1=F&O, 2=Commodity
    @State private var isLoading = false

    let expertTabs = ["Fundamental Calls", "F&O Calls & Analysis", "Commodity Calls"]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    pageHeader
                    // 8.1 Horizontal Curated News Carousel
                    newsCarousel
                    // 8.2 Embedded Podcast Network
                    podcastSection
                    // 8.3 Behind-the-News Editorial
                    editorialSection
                    // 8.4 Expert Execution Panel
                    expertPanel
                }
                .padding(.bottom, Theme.Spacing.large)
            }
        }
        .task { await loadFeed() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("समाचार और बुद्धिमत्ता")
                    .font(Theme.hindiFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                Text("NEWS & INTELLIGENCE")
                    .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title2))
                    .foregroundStyle(Theme.inkPrimary)
                Text("Premium Financial Newswire")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
    }

    // MARK: 8.1 Horizontal News Carousel

    private var newsCarousel: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "MACRO UPDATES", hindiTitle: "व्यापक आर्थिक अपडेट")

            ScrollView(.horizontal) {
                HStack(spacing: 12) {
                    if isLoading && articles.isEmpty {
                        ForEach(0..<4, id: \.self) { _ in newsCardPlaceholder }
                    } else {
                        ForEach(articles.prefix(10)) { article in
                            NewsCarouselCard(article: article)
                        }
                    }
                }
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.small)
            }
            .scrollIndicators(.hidden)
        }
    }

    // MARK: 8.2 Podcast Network

    private var podcastSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "MARKET DEEP DIVES", hindiTitle: "गहन विश्लेषण")

            if isLoading && videos.isEmpty {
                HStack(spacing: 12) {
                    ForEach(0..<3, id: \.self) { _ in videoCardPlaceholder }
                }
                .padding(.horizontal, Theme.Spacing.card)
            } else {
                ScrollView(.horizontal) {
                    HStack(spacing: 12) {
                        ForEach(videos.prefix(8)) { video in
                            VideoCard(video: video)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, 4)
                }
                .scrollIndicators(.hidden)
            }
        }
    }

    // MARK: 8.3 Behind-the-News Editorial

    private var editorialSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "DEEP STRUCTURAL ANALYSIS", hindiTitle: "गहन संरचनात्मक विश्लेषण")

            // Long-horizon socioeconomic columns
            let editorials = articles.filter { ($0.summary?.count ?? 0) > 100 }.prefix(4)
            ForEach(Array(editorials)) { article in
                EditorialRow(article: article)
                    .padding(.horizontal, Theme.Spacing.card)
            }

            if editorials.isEmpty && !isLoading {
                Text("No editorial columns available.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.bottom, Theme.Spacing.medium)
            }
        }
    }

    // MARK: 8.4 Expert Execution Panel

    private var expertPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "GET EXPERT ADVICE", hindiTitle: "विशेषज्ञ सलाह")

            // Tab bar
            HStack(spacing: 0) {
                ForEach(Array(expertTabs.enumerated()), id: \.offset) { idx, tab in
                    Button(action: { expertTab = idx }) {
                        Text(tab)
                            .font(.caption2.weight(expertTab == idx ? .bold : .regular))
                            .foregroundStyle(expertTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .multilineTextAlignment(.center)
                            .padding(.vertical, Theme.Spacing.medium)
                            .frame(maxWidth: .infinity)
                            .background(expertTab == idx ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .padding(.horizontal, Theme.Spacing.card)

            // Expert call cards based on selected panel
            expertCallCards(for: expertTab)
                .padding(.horizontal, Theme.Spacing.card)
        }
    }

    private func expertCallPlaceholder(for tab: Int) -> String {
        switch tab {
        case 0: return "Long-horizon corporate intrinsic valuation calls from SEBI-registered fundamental analysts."
        case 1: return "Short-term high-leverage derivative positioning and open interest analysis."
        default: return "Physical resource metrics and hard asset allocation data for commodities."
        }
    }

    @ViewBuilder
    private func expertCallCards(for tab: Int) -> some View {
        Text(expertCallPlaceholder(for: tab))
            .font(.caption)
            .foregroundStyle(Theme.inkSecondary)
            .lineSpacing(4)
            .padding(Theme.Spacing.standard)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
    }

    // MARK: Placeholders

    private var newsCardPlaceholder: some View {
        let cardWidth = UIScreen.main.bounds.width * 0.58
        let cardHeight = UIScreen.main.bounds.height * 0.16
        return VStack(alignment: .leading, spacing: 8) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).fill(Theme.inkTertiary.opacity(0.10)).frame(width: cardWidth - Theme.Spacing.standard * 2, height: cardHeight * 0.40)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: (cardWidth - Theme.Spacing.standard * 2) * 0.8, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: (cardWidth - Theme.Spacing.standard * 2) * 0.55, height: 10)
        }
        .padding(Theme.Spacing.standard)
        .frame(width: cardWidth, height: cardHeight)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var videoCardPlaceholder: some View {
        let cardWidth = UIScreen.main.bounds.width * 0.65
        let thumbHeight = cardWidth * 0.5625  // 16:9
        return VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).fill(Theme.inkTertiary.opacity(0.10)).frame(height: thumbHeight)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: cardWidth * 0.83, height: 12)
        }
        .frame(width: cardWidth)
        .shimmerPlaceholder(isLoading: true)
    }

    // MARK: Data Load

    private func loadFeed() async {
        isLoading = true
        let userId = authManager.currentUser?.userId ?? 0
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/home-feed?user_id=\(userId)") else {
            isLoading = false
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = 20

        if let (data, resp) = try? await URLSession.shared.data(for: req),
           let http = resp as? HTTPURLResponse, http.statusCode == 200,
           let feed = try? JSONDecoder().decode(HomeFeedResponse.self, from: data) {
            articles = feed.news
            videos = feed.youtubeVideos
        }
        isLoading = false
    }
}

// MARK: - 8.1 News Carousel Card

struct NewsCarouselCard: View {
    let article: NewsArticleItem

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private let cardWidth: CGFloat = UIScreen.main.bounds.width * 0.58

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let sentiment = article.sentiment {
                let color: Color = sentiment.lowercased().contains("positive") ? Theme.bullGreen :
                                   sentiment.lowercased().contains("negative") ? Theme.bearRed : Theme.holdAmber
                Text(sentiment.uppercased())
                    .font(.caption2.weight(.bold).monospaced())
                    .tracking(1)
                    .foregroundStyle(color)
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(color.opacity(0.10))
                    .cornerRadius(Theme.CornerRadius.small)
            }

            Text(article.headline)
                .font(.caption.weight(.semibold))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(3)
                .lineSpacing(2)

            Spacer(minLength: 0)

            HStack {
                Text(article.source)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text(timeLabel)
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .frame(width: cardWidth, height: UIScreen.main.bounds.height * 0.16)
        .banknoteCard()
    }
}

// MARK: - 8.2 Video Card

struct VideoCard: View {
    let video: YouTubeVideoItem
    @State private var showPlayer = false

    private let cardWidth: CGFloat = UIScreen.main.bounds.width * 0.65

    var body: some View {
        Button(action: { showPlayer = true }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                // Thumbnail with AsyncImage
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(height: cardWidth * 0.5625)  // 16:9
                                    .clipped()
                                    .cornerRadius(Theme.CornerRadius.tight)
                            case .failure(_), .empty:
                                Rectangle()
                                    .fill(Theme.canvasDeep)
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(height: cardWidth * 0.5625)
                                    .cornerRadius(Theme.CornerRadius.tight)
                                    .overlay(
                                        Image(systemName: "play.circle.fill")
                                            .font(.largeTitle)
                                            .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                                    )
                            @unknown default:
                                EmptyView()
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Theme.canvasDeep)
                            .aspectRatio(16/9, contentMode: .fill)
                            .frame(height: cardWidth * 0.5625)
                            .cornerRadius(Theme.CornerRadius.tight)
                            .overlay(
                                Image(systemName: "play.circle.fill")
                                    .font(.largeTitle)
                                    .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                            )
                    }

                    // Duration badge
                    if video.durationSeconds > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Color.black.opacity(0.65))
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(Theme.Spacing.tight)
                    }
                }

                // Title
                Text(video.title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)
                    .lineSpacing(2)

                // Channel + views footer
                HStack {
                    Text(video.channelName)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                    Text("\(video.formattedViewCount) views")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .frame(width: cardWidth)
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showPlayer) {
            if let url = URL(string: video.videoUrl) {
                SafariSheetView(url: url)
            }
        }
    }
}

// MARK: - 8.3 Editorial Row

struct EditorialRow: View {
    let article: NewsArticleItem

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(article.headline)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(2)

            if let summary = article.summary {
                Text(summary)
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(3)
                    .lineSpacing(3)
            }

            HStack {
                Text(article.source)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                // 8.3 time-elapsed publication marker
                Text(timeLabel)
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}

// MARK: - Safari Sheet (native, no external deps)

import SafariServices

struct SafariSheetView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let config = SFSafariViewController.Configuration()
        config.entersReaderIfAvailable = false
        return SFSafariViewController(url: url, configuration: config)
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// MARK: - Preview

#Preview("News Multimedia Hub") {
    NewsMultimediaView()
        .environmentObject(AuthManager())
}
