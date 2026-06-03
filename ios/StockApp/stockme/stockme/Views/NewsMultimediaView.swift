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
                VStack(alignment: .leading, spacing: 0) {
                    pageHeader
                    // 8.1 Horizontal Curated News Carousel
                    newsCarousel
                    GuillocheDivider().padding(.horizontal, 16).padding(.vertical, 6)
                    // 8.2 Embedded Podcast Network
                    podcastSection
                    GuillocheDivider().padding(.horizontal, 16).padding(.vertical, 6)
                    // 8.3 Behind-the-News Editorial
                    editorialSection
                    GuillocheDivider().padding(.horizontal, 16).padding(.vertical, 6)
                    // 8.4 Expert Execution Panel
                    expertPanel
                }
                .padding(.bottom, 24)
            }
        }
        .task { await loadFeed() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("NEWS & INTELLIGENCE")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.securityGold)
                Text("Premium Financial Newswire")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .background(Theme.canvasDeep)
    }

    // MARK: 8.1 Horizontal News Carousel

    private var newsCarousel: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("MACRO UPDATES")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)
                .padding(.top, 14)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    if isLoading && articles.isEmpty {
                        ForEach(0..<4, id: \.self) { _ in newsCardPlaceholder }
                    } else {
                        ForEach(articles.prefix(10)) { article in
                            NewsCarouselCard(article: article)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: 8.2 Podcast Network

    private var podcastSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("MARKET DEEP DIVES")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)
                .padding(.top, 14)

            if isLoading && videos.isEmpty {
                HStack(spacing: 12) {
                    ForEach(0..<3, id: \.self) { _ in videoCardPlaceholder }
                }
                .padding(.horizontal, 16)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(videos.prefix(8)) { video in
                            VideoCard(video: video)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 4)
                }
            }
        }
    }

    // MARK: 8.3 Behind-the-News Editorial

    private var editorialSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("DEEP STRUCTURAL ANALYSIS")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)
                .padding(.top, 14)

            // Long-horizon socioeconomic columns
            let editorials = articles.filter { ($0.summary?.count ?? 0) > 100 }.prefix(4)
            ForEach(Array(editorials)) { article in
                EditorialRow(article: article)
                    .padding(.horizontal, 16)
            }

            if editorials.isEmpty && !isLoading {
                Text("No editorial columns available.")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.inkTertiary)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)
            }
        }
    }

    // MARK: 8.4 Expert Execution Panel

    private var expertPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("GET EXPERT ADVICE")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)
                .padding(.top, 14)

            // Tab bar
            HStack(spacing: 0) {
                ForEach(Array(expertTabs.enumerated()), id: \.offset) { idx, tab in
                    Button(action: { expertTab = idx }) {
                        Text(tab)
                            .font(.system(size: 10, weight: expertTab == idx ? .bold : .regular))
                            .foregroundColor(expertTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .multilineTextAlignment(.center)
                            .padding(.vertical, 9)
                            .frame(maxWidth: .infinity)
                            .background(expertTab == idx ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            .background(Theme.canvasDeep)
            .cornerRadius(8)
            .padding(.horizontal, 16)

            // Expert call cards based on selected panel
            expertCallCards(for: expertTab)
                .padding(.horizontal, 16)
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
            .font(.system(size: 12))
            .foregroundColor(Theme.inkSecondary)
            .lineSpacing(4)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
    }

    // MARK: Placeholders

    private var newsCardPlaceholder: some View {
        VStack(alignment: .leading, spacing: 8) {
            RoundedRectangle(cornerRadius: 6).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 220, height: 100)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 180, height: 12)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 120, height: 10)
        }
        .padding(12)
        .frame(width: 220)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var videoCardPlaceholder: some View {
        VStack(alignment: .leading, spacing: 8) {
            RoundedRectangle(cornerRadius: 6).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 180, height: 100)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 150, height: 12)
        }
        .padding(10)
        .frame(width: 180)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    // MARK: Data Load

    private func loadFeed() async {
        isLoading = true
        // Production: POST /api/v1/home-feed
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/home-feed") else {
            isLoading = false
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let user = authManager.currentUser {
            req.httpBody = try? JSONEncoder().encode(["user_id": user.userId])
        }
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

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Sentiment badge
            if let sentiment = article.sentiment {
                let color: Color = sentiment.lowercased().contains("positive") ? Theme.bullGreen :
                                   sentiment.lowercased().contains("negative") ? Theme.bearRed : Theme.holdAmber
                Text(sentiment.uppercased())
                    .font(.system(size: 7, weight: .bold, design: .monospaced))
                    .tracking(1)
                    .foregroundColor(color)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(color.opacity(0.10))
                    .cornerRadius(3)
            }

            Text(article.headline)
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(3)
                .lineSpacing(2)

            Spacer(minLength: 0)

            HStack {
                Text(article.source)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(Theme.inkTertiary)
                Spacer()
                // 8.3 Time-elapsed label
                Text(timeLabel)
                    .font(.system(size: 9))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(12)
        .frame(width: 220, height: 130)
        .banknoteCard()
    }
}

// MARK: - 8.2 Video Card

struct VideoCard: View {
    let video: YouTubeVideoItem
    @State private var showPlayer = false

    var body: some View {
        Button(action: { showPlayer = true }) {
            VStack(alignment: .leading, spacing: 8) {
                ZStack {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.canvasDeep)
                        .frame(width: 180, height: 100)
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 28))
                        .foregroundColor(Theme.securityGold.opacity(0.8))
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            Text(video.formattedDuration)
                                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                .foregroundColor(.white)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 2)
                                .background(Color.black.opacity(0.5))
                                .cornerRadius(3)
                                .padding(6)
                        }
                    }
                    .frame(width: 180, height: 100)
                }

                Text(video.title)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(2)
                    .lineSpacing(2)
                    .frame(width: 180, alignment: .leading)

                HStack {
                    Text(video.channelName)
                        .font(.system(size: 9))
                        .foregroundColor(Theme.inkSecondary)
                    Spacer()
                    Text("\(video.formattedViewCount) views")
                        .font(.system(size: 9))
                        .foregroundColor(Theme.inkTertiary)
                }
            }
            .frame(width: 180)
        }
        .buttonStyle(EKPressStyle())
        // 8.2 In-app playback (opens Safari/native — no external SDK needed)
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
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(Theme.inkPrimary)
                .lineSpacing(2)

            if let summary = article.summary {
                Text(summary)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(3)
                    .lineSpacing(3)
            }

            HStack {
                Text(article.source)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(Theme.inkTertiary)
                Spacer()
                // 8.3 time-elapsed publication marker
                Text(timeLabel)
                    .font(.system(size: 9))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(12)
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
