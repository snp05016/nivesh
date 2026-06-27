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
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    pageHeader
                        .padding(.top, Theme.Spacing.standard)
                    // 8.1 Horizontal Curated News Carousel
                    newsCarousel
                    // 8.2 Embedded Podcast Network
                    podcastSection
                    // 8.3 Behind-the-News Editorial
                    editorialSection
                    // 8.4 Expert Execution Panel (promoted above news feed)
                    expertPanel
                    // 8.5 Recent News — truncated with drill-down
                    allNewsSection
                }
                .padding(.bottom, Theme.Spacing.xLarge)
            }
        }
        .task { await loadFeed() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
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
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeader(title: "MACRO UPDATES", hindiTitle: "व्यापक आर्थिक अपडेट")

            ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: Theme.Spacing.card) {
                    if isLoading && articles.isEmpty {
                        ForEach(0..<5, id: \.self) { _ in newsCardPlaceholder }
                    } else {
                        ForEach(articles.prefix(50)) { article in
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

    // MARK: 8.2 Podcast Network (vertical list)

    private var podcastSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeader(title: "MARKET DEEP DIVES", hindiTitle: "गहन विश्लेषण")

            if isLoading && videos.isEmpty {
                ForEach(0..<3, id: \.self) { _ in videoCardPlaceholder }
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                ForEach(videos.prefix(6)) { video in
                    VideoCard(video: video)
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
    }

    // MARK: 8.3 Behind-the-News Editorial

    private var editorialSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeader(title: "DEEP STRUCTURAL ANALYSIS", hindiTitle: "गहन संरचनात्मक विश्लेषण")

            // Long-horizon socioeconomic columns — now expandable
            let editorials = articles.filter { ($0.summary?.count ?? 0) > 100 }.prefix(6)
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

    // MARK: 8.5 Recent News — truncated with drill-down

    @State private var showAllNews = false

    private var allNewsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "RECENT NEWS", hindiTitle: "हाल के समाचार")

            if isLoading && articles.isEmpty {
                ForEach(0..<3, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .fill(Theme.inkTertiary.opacity(0.08))
                        .frame(height: 100)
                        .padding(.horizontal, Theme.screenPadding)
                        .shimmerPlaceholder(isLoading: true)
                }
            } else if articles.isEmpty {
                Text("No news available at this time.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                ForEach(articles.prefix(5)) { article in
                    NewsListRow(article: article)
                        .padding(.horizontal, Theme.screenPadding)
                }

                if articles.count > 5 {
                    Button(action: { HapticManager.selection()
                        showAllNews = true
                    }) {
                        HStack(spacing: Theme.Spacing.small) {
                            Text("SEE ALL \(articles.count) ARTICLES")
                                .font(Theme.officialStampFont(size: 9))
                                .tracking(1.2)
                            Image(systemName: "arrow.right")
                                .font(.caption2)
                        }
                        .foregroundStyle(Theme.securityGold)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.standard)
                        .background(Theme.securityGold.opacity(0.06))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                .stroke(Theme.securityGold.opacity(0.2), lineWidth: 0.5)
                        )
                    }
                    .buttonStyle(EKPressStyle())
                    .padding(.horizontal, Theme.screenPadding)
                    .sheet(isPresented: $showAllNews) {
                        AllNewsSheet(articles: articles)
                    }
                }
            }
        }
    }

    // MARK: 8.5 Expert Execution Panel

    private var expertPanel: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "GET EXPERT ADVICE", hindiTitle: "विशेषज्ञ सलाह")

            // Tab bar
            HStack(spacing: Theme.Spacing.none) {
                ForEach(Array(expertTabs.enumerated()), id: \.offset) { idx, tab in
                    Button(action: { HapticManager.selection(); expertTab = idx }) {
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
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                .fill(Theme.inkTertiary.opacity(0.10))
                .frame(width: 220, height: 48)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.inkTertiary.opacity(0.10))
                .frame(width: 180, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.inkTertiary.opacity(0.10))
                .frame(width: 130, height: 10)
        }
        .padding(Theme.Spacing.standard)
        .frame(width: 260, height: 140)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var videoCardPlaceholder: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                .fill(Theme.inkTertiary.opacity(0.10))
                .frame(width: 160, height: 90)
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.10))
                    .frame(height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.10))
                    .frame(width: 100, height: 10)
            }
        }
        .padding(Theme.Spacing.standard)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
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
        if let token = authManager.currentUser?.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let (data, resp) = try? await URLSession.shared.data(for: req),
           let http = resp as? HTTPURLResponse, http.statusCode == 200,
           let feed = try? JSONDecoder().decode(HomeFeedResponse.self, from: data) {
            articles = feed.news
            videos = feed.youtubeVideos
        }
        isLoading = false
    }
}

// MARK: - 8.1 News Carousel Card (tappable → detail sheet)

struct NewsCarouselCard: View {
    let article: NewsArticleItem
    @State private var showDetail = false

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    /// Freshness badge: ≤ 2h = HOT, ≤ 6h = TRENDING — neutral colors only (no financial red/green)
    private var signalBadge: (label: String, icon: String, color: Color)? {
        if article.isRedFlag { return ("RED FLAG", "exclamationmark.triangle.fill", Theme.bearRed) }
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            let age = Date().timeIntervalSince(date)
            if age < 2 * 3600 { return ("HOT", "flame.fill", Theme.securityGold) }
            if age < 6 * 3600 { return ("TRENDING", "chart.line.uptrend.xyaxis", Theme.securityGold) }
            if age < 12 * 3600 { return ("BREAKING", "dot.radiowaves.left.and.right", Theme.inkSecondary) }
        }
        return nil
    }

    private let cardWidth: CGFloat = 280

    var body: some View {
        Button(action: { HapticManager.selection()
            showDetail = true
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                // Hero image at top of card
                ZStack(alignment: .bottom) {
                    if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image.resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: cardWidth, height: 140)
                                    .clipped()
                            case .failure(_), .empty:
                                Rectangle()
                                    .fill(
                                        LinearGradient(
                                            colors: [Theme.canvasDeep, Theme.canvasShadow],
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        )
                                    )
                                    .frame(width: cardWidth, height: 140)
                                    .overlay(
                                        Image(systemName: "newspaper.fill")
                                            .foregroundStyle(Theme.inkTertiary.opacity(0.3))
                                            .font(.title2)
                                    )
                            @unknown default: EmptyView()
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(
                                LinearGradient(
                                    colors: [Theme.canvasDeep, Theme.canvasShadow],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .frame(width: cardWidth, height: 140)
                            .overlay(
                                Image(systemName: "newspaper.fill")
                                    .foregroundStyle(Theme.inkTertiary.opacity(0.3))
                                    .font(.title2)
                            )
                    }

                    // Gradient scrim
                    LinearGradient(
                        colors: [Theme.inkPrimary.opacity(0.0), Theme.inkPrimary.opacity(0.65)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .frame(height: 60)

                    // Time badge + signal badge row
                    HStack(spacing: Theme.Spacing.tight) {
                        if !timeLabel.isEmpty {
                            Text(timeLabel)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.white.opacity(0.9))
                                .padding(.horizontal, Theme.Spacing.tight)
                                .padding(.vertical, 2)
                                .background(Theme.inkPrimary.opacity(0.5))
                                .cornerRadius(Theme.CornerRadius.small)
                        }

                        Spacer()

                        if let badge = signalBadge {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: badge.icon)
                                    .font(Theme.officialStampFont(size: 8))
                                Text(badge.label)
                                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                                    .tracking(0.8)
                            }
                            .foregroundStyle(badge.color)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, 2)
                            .background(badge.color.opacity(0.2))
                            .cornerRadius(Theme.CornerRadius.small)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.bottom, Theme.Spacing.medium)
                }
                .frame(height: 140)
                .cornerRadius(Theme.CornerRadius.tight)

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    // Sentiment + ticker row
                    HStack(spacing: Theme.Spacing.tight) {
                        if let sentiment = article.sentiment, !sentiment.isEmpty {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Circle()
                                    .fill(sentimentColor)
                                    .frame(width: 6, height: 6)
                                Text(sentiment.uppercased())
                                    .font(.caption2.weight(.bold).monospaced())
                                    .tracking(0.6)
                                    .foregroundStyle(sentimentColor)
                            }
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(sentimentColor.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                        }

                        if let ticker = article.ticker, !ticker.isEmpty {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: "chart.line.uptrend.xyaxis")
                                    .font(Theme.officialStampFont(size: 7))
                                Text(ticker)
                                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                            }
                            .foregroundStyle(Theme.bullGreen)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.bullGreen.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                        }

                        Spacer()
                    }

                    Text(stripEmoji(article.headline))
                        .font(Theme.engravedSerif(size: 13, weight: .semibold, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(4)
                        .lineSpacing(2.5)

                    if let summary = article.summary, !summary.isEmpty {
                        Text(stripEmoji(summary))
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(2)
                            .lineSpacing(1.5)
                    }

                    Spacer(minLength: 0)

                    HStack {
                        Text(article.source.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)
                        Spacer()
                        Image(systemName: "arrow.up.right.square")
                            .font(.caption2)
                            .foregroundStyle(Theme.securityGold.opacity(0.7))
                    }
                }
                .padding(Theme.Spacing.standard)
            }
            .frame(width: cardWidth, height: 320)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showDetail) {
            NewsDetailSheet(article: article)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("News Article: \(article.headline). Published \(timeLabel). Source: \(article.source)")
    }
}

// MARK: - 8.2 Video Card

struct VideoCard: View {
    let video: YouTubeVideoItem
    @State private var showPlayer = false

    var body: some View {
        Button(action: { HapticManager.selection(); showPlayer = true }) {
            HStack(spacing: Theme.Spacing.standard) {
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(width: 160, height: 90)
                                    .clipped()
                                    .cornerRadius(Theme.CornerRadius.tight)
                            case .failure(_), .empty:
                                videoFallbackThumb
                            @unknown default:
                                EmptyView()
                            }
                        }
                    } else {
                        videoFallbackThumb
                    }

                    if (video.durationSeconds ?? 0) > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.inkPrimary.opacity(0.65))
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(Theme.Spacing.small)
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(video.title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .lineSpacing(2)

                    Text(video.channelName)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkSecondary)

                    Text("\(video.formattedViewCount) views")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .padding(Theme.Spacing.standard)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showPlayer) {
            if let url = URL(string: video.videoUrl) {
                SafariSheetView(url: url)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("YouTube Video: \(video.title) by \(video.channelName). \(video.formattedViewCount) views.")
    }

    private var videoFallbackThumb: some View {
        Rectangle()
            .fill(Theme.canvasDeep)
            .frame(width: 160, height: 90)
            .cornerRadius(Theme.CornerRadius.tight)
            .overlay(
                Image(systemName: "play.circle.fill")
                    .font(.title2)
                    .foregroundStyle(Theme.inkTertiary.opacity(0.4))
            )
    }
}

// MARK: - 8.3 Editorial Row — expandable inline

struct EditorialRow: View {
    let article: NewsArticleItem
    @State private var expanded = false
    @State private var showSafari = false

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private var sourceLabel: String {
        article.source.replacingOccurrences(of: "_", with: " ").uppercased()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // ── Always-visible header (tap to expand) ───────────────────
            Button(action: { HapticManager.selection()
                withAnimation(.spring(response: 0.3, dampingFraction: 0.82)) {
                    expanded.toggle()
                }
            }) {
                HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        // Source + time row
                        HStack(spacing: Theme.Spacing.small) {
                            Text(sourceLabel)
                                .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                                .tracking(1.2)
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.tight)
                                .padding(.vertical, 2)
                                .background(Theme.securityGold.opacity(0.10))
                                .cornerRadius(Theme.CornerRadius.small)

                            Text(timeLabel)
                                .font(.caption2.monospaced())
                                .foregroundStyle(Theme.inkTertiary)
                        }

                        Text(stripEmoji(article.headline))
                            .font(Theme.engravedSerif(size: 13, weight: .semibold, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineSpacing(2)
                            .multilineTextAlignment(.leading)
                    }

                    Spacer()

                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.top, Theme.Spacing.xSmall)
                }
            }
            .buttonStyle(.plain)

            // ── Expandable content ───────────────────────────────────────
            if expanded {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    GuillocheDivider()
                        .padding(.top, Theme.Spacing.medium)

                    if let summary = article.summary, !summary.isEmpty {
                        Text(stripEmoji(summary))
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary.opacity(0.88))
                            .lineSpacing(5)
                    }

                    // Ticker chip
                    if let ticker = article.ticker, !ticker.isEmpty {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: "chart.line.uptrend.xyaxis")
                                .font(.caption2)
                            Text(ticker)
                                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                        }
                        .foregroundStyle(Theme.bullGreen)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.bullGreen.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.medium)
                    }

                    Button(action: { HapticManager.selection()
                        showSafari = true
                    }) {
                        HStack {
                            Image(systemName: "safari")
                            Text("READ FULL ARTICLE")
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                .tracking(1.2)
                        }
                        .foregroundStyle(Theme.canvas)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.medium)
                        .background(Theme.inkPrimary)
                        .cornerRadius(Theme.CornerRadius.medium)
                    }
                    .buttonStyle(EKPressStyle())
                }
                .padding(.top, Theme.Spacing.standard)
                .transition(.opacity.combined(with: .move(edge: .top)))
                .sheet(isPresented: $showSafari) {
                    if let url = URL(string: article.articleUrl) {
                        SafariSheetView(url: url)
                    }
                }
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .animation(.spring(response: 0.3, dampingFraction: 0.82), value: expanded)
    }
}

// MARK: - 8.4 News List Row — full vertical list item

struct NewsListRow: View {
    let article: NewsArticleItem
    @State private var showDetail = false

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    /// Freshness badge — neutral colors only (no financial red/green)
    private var signalBadge: (label: String, icon: String, color: Color)? {
        if article.isRedFlag { return ("RED FLAG", "exclamationmark.triangle.fill", Theme.bearRed) }
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            let age = Date().timeIntervalSince(date)
            if age < 2 * 3600 { return ("HOT", "flame.fill", Theme.securityGold) }
            if age < 6 * 3600 { return ("TRENDING", "chart.line.uptrend.xyaxis", Theme.securityGold) }
            if age < 12 * 3600 { return ("BREAKING", "dot.radiowaves.left.and.right", Theme.inkSecondary) }
        }
        return nil
    }

    var body: some View {
        Button(action: { HapticManager.selection()
            showDetail = true
        }) {
            HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                // Thumbnail (square)
                ZStack(alignment: .topTrailing) {
                    if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let img):
                                img.resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 84, height: 84)
                                    .clipped()
                                    .cornerRadius(Theme.CornerRadius.tight)
                            case .failure(_), .empty:
                                fallbackThumb
                            @unknown default: EmptyView()
                            }
                        }
                    } else {
                        fallbackThumb
                    }

                    // HOT/TRENDING indicator dot
                    if let badge = signalBadge {
                        Circle()
                            .fill(badge.color)
                            .frame(width: 10, height: 10)
                            .overlay(Circle().stroke(Theme.canvasDeep, lineWidth: 1.5))
                            .offset(x: 3, y: -3)
                    }
                }

                // Text content
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    // Source + signal badge + time
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(article.source.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(1.0)
                            .foregroundStyle(Theme.securityGold)

                        if let badge = signalBadge {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: badge.icon)
                                    .font(Theme.officialStampFont(size: 7))
                                Text(badge.label)
                                    .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                                    .tracking(0.6)
                            }
                            .foregroundStyle(badge.color)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, 1)
                            .background(badge.color.opacity(0.12))
                            .cornerRadius(Theme.CornerRadius.small)
                        } else if let sentiment = article.sentiment, !sentiment.isEmpty {
                            Text("·")
                                .foregroundStyle(Theme.inkTertiary)
                            Text(sentiment.prefix(3).uppercased())
                                .font(.caption2.weight(.bold).monospaced())
                                .foregroundStyle(sentimentColor)
                        }

                        Spacer()

                        Text(timeLabel)
                            .font(.caption2.monospaced())
                            .foregroundStyle(Theme.inkTertiary)
                    }

                    Text(stripEmoji(article.headline))
                        .font(Theme.engravedSerif(size: 13, weight: .semibold, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .lineSpacing(2)

                    if let summary = article.summary, !summary.isEmpty {
                        Text(stripEmoji(summary))
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(2)
                            .lineSpacing(1.5)
                    }

                    // Ticker chip if available
                    if let ticker = article.ticker, !ticker.isEmpty {
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Image(systemName: "chart.line.uptrend.xyaxis")
                                .font(Theme.officialStampFont(size: 7))
                            Text(ticker)
                                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                        }
                        .foregroundStyle(Theme.bullGreen)
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.bullGreen.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.small)
                    }
                }
            }
            .padding(Theme.Spacing.standard)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showDetail) {
            NewsDetailSheet(article: article)
        }
    }

    private var fallbackThumb: some View {
        Rectangle()
            .fill(Theme.canvasDeep)
            .frame(width: 84, height: 84)
            .cornerRadius(Theme.CornerRadius.tight)
            .overlay(
                Image(systemName: "newspaper.fill")
                    .foregroundStyle(Theme.inkTertiary.opacity(0.3))
                    .font(.title3)
            )
    }
}

// MARK: - All News Sheet (drill-down from truncated list)

struct AllNewsSheet: View {
    let articles: [NewsArticleItem]
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.medium) {
                    ForEach(articles) { article in
                        NewsListRow(article: article)
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.vertical, Theme.Spacing.standard)
            }
            .background(Theme.canvas)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("ALL MARKET NEWS")
                        .font(Theme.officialStampFont(size: 11))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkPrimary)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: { HapticManager.selection(); dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }
            .toolbarBackground(Theme.canvas, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
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
