import SwiftUI
import Combine

// MARK: - Expert Network API Response Models

private struct ExpertListResponse: Decodable {
    let experts: [ExpertDTO]
}

private struct ExpertDTO: Decodable {
    let id: String
    let name: String
    let sebiRegId: String?
    let yearsExperience: Int
    let strategy: String
    let focusTags: [String]
    let postCount: Int
    let isVerified: Bool
    let bio: String
    enum CodingKeys: String, CodingKey {
        case id, name, strategy, bio
        case sebiRegId = "sebi_reg_id"
        case yearsExperience = "years_experience"
        case focusTags = "focus_tags"
        case postCount = "post_count"
        case isVerified = "is_verified"
    }
}

private struct PostListResponse: Decodable {
    let posts: [PostDTO]
}

private struct PostDTO: Decodable {
    let id: String
    let expertId: String
    let expertName: String
    let content: String
    let ticker: String?
    let chartImageUrl: String?
    let publishedAt: String
    let likeCount: Int
    let isPremium: Bool
    enum CodingKeys: String, CodingKey {
        case id, content, ticker
        case expertId = "expert_id"
        case expertName = "expert_name"
        case chartImageUrl = "chart_image_url"
        case publishedAt = "published_at"
        case likeCount = "like_count"
        case isPremium = "is_premium"
    }
}

// MARK: - Expert Network ViewModel

@MainActor
class ExpertNetworkViewModel: ObservableObject {
    @Published var experts: [MarketExpert] = []
    @Published var posts: [ExpertPost] = []
    @Published var advisors: [AdvisorBiography] = []
    @Published var insights: [TextAdvisoryInsight] = []
    @Published var isLoading = false
    @Published var fetchError: String? = nil
    @AppStorage("expert_bookmarks") private var bookmarksRaw: String = ""

    var bookmarkedPostIds: Set<String> {
        get { Set(bookmarksRaw.split(separator: ",").map(String.init)) }
        set { bookmarksRaw = newValue.joined(separator: ",") }
    }

    func load() {
        isLoading = true
        fetchError = nil
        Task {
            async let advisorsFetch = NetworkManager.shared.fetchAdvisors()
            async let insightsFetch = NetworkManager.shared.fetchIdeasFeed()
            let (a, i) = await (advisorsFetch, insightsFetch)
            advisors = a?.advisors ?? []
            insights = i?.insights ?? []

            async let expertsFetch = fetchExperts()
            async let postsFetch = fetchPosts()
            let (e, p) = await (expertsFetch, postsFetch)
            experts = e
            posts = p

            if advisors.isEmpty && insights.isEmpty {
                fetchError = "Couldn't load right now. Please try again."
            }
            isLoading = false
        }
    }

    private func fetchExperts() async -> [MarketExpert] {
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/experts"),
              let (data, resp) = try? await URLSession.shared.data(from: url),
              let http = resp as? HTTPURLResponse, http.statusCode == 200,
              let dto = try? JSONDecoder().decode(ExpertListResponse.self, from: data) else { return [] }
        return dto.experts.map { d in
            MarketExpert(id: d.id, name: d.name, sebiRegId: d.sebiRegId,
                         yearsExperience: d.yearsExperience, strategy: d.strategy,
                         focusTags: d.focusTags, postCount: d.postCount,
                         isVerified: d.isVerified, bio: d.bio)
        }
    }

    private func fetchPosts() async -> [ExpertPost] {
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/expert-posts?limit=40"),
              let (data, resp) = try? await URLSession.shared.data(from: url),
              let http = resp as? HTTPURLResponse, http.statusCode == 200,
              let dto = try? JSONDecoder().decode(PostListResponse.self, from: data) else { return [] }
        let iso = ISO8601DateFormatter()
        return dto.posts.map { d in
            let date = iso.date(from: d.publishedAt) ?? Date()
            return ExpertPost(id: d.id, expertId: d.expertId, expertName: d.expertName,
                              content: d.content, ticker: d.ticker,
                              chartImageUrl: d.chartImageUrl, publishedAt: date,
                              likeCount: d.likeCount, isPremium: d.isPremium)
        }
    }

    func toggleLike(postId: String) {
        guard let idx = posts.firstIndex(where: { $0.id == postId }) else { return }
        posts[idx].isLiked.toggle()
    }

    func toggleBookmark(postId: String) {
        guard let idx = posts.firstIndex(where: { $0.id == postId }) else { return }
        posts[idx].isBookmarked.toggle()
        var bm = bookmarkedPostIds
        if posts[idx].isBookmarked { bm.insert(postId) } else { bm.remove(postId) }
        bookmarkedPostIds = bm
    }
}

// MARK: - Expert Network View

struct ExpertNetworkView: View {
    @StateObject private var vm = ExpertNetworkViewModel()
    @State private var selectedSegment = 0
    private let isSuperpro: Bool = true

    // MARK: - Harvester state
    @State private var harvestedCards: [HarvestedCard] = []
    @State private var showSourcesSheet = false
    @State private var harvesterSources: [HarvesterSourceStatus] = []
    @State private var navTicker: TickerDest? = nil

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: Theme.Spacing.none) {
                pageHeader
                    .padding(.top, Theme.Spacing.standard)

                // Segmented control
                Picker("", selection: $selectedSegment) {
                    Text("Advisory Wire").tag(0)
                    Text("Verified Minds").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)

                if vm.isLoading {
                    Spacer()
                    loadingShimmer
                    Spacer()
                } else if let error = vm.fetchError {
                    ErrorDiagnoserView(
                        error: error,
                        context: ErrorDiagnostic(
                            endpoint: "/api/v1/ideas/feed",
                            classification: "IDEAS_FETCH_FAILURE"
                        ),
                        retryAction: { vm.load() }
                    )
                    Spacer()
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                            // MARK: Market Intelligence section (Harvester) — top
                            if !harvestedCards.isEmpty {
                                marketIntelligenceSection
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            if selectedSegment == 0 {
                                advisoryWireSection
                            } else {
                                verifiedMindsSection
                            }
                        }
                        .padding(.bottom, Theme.Spacing.screen)
                    }
                }
            }
        }
        .task { vm.load() }
        .task { await loadHarvestedCards() }
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { HapticManager.selection(); 
    HapticManager.selection()
                    HapticManager.selection()
                    showSourcesSheet = true
                } label: {
                    Image(systemName: "list.bullet.rectangle")
                        .foregroundStyle(Theme.securityGold)
                }
            }
        }
        .sheet(isPresented: $showSourcesSheet) {
            harvesterSourcesSheet
        }
        .sheet(item: $navTicker) { dest in
            NavigationStack {
                StockProfileView(ticker: dest.ticker)
            }
        }
    }

    // MARK: - Harvester data loading

    private func loadHarvestedCards() async {
        harvestedCards = (try? await NetworkManager.shared.fetchHarvesterFeed(limit: 30)).map { $0.cards } ?? []
    }

    // MARK: - Market Intelligence Section

    private var marketIntelligenceSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                Text("MARKET INTELLIGENCE")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("\(harvestedCards.count) signals")
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.medium)

            ForEach(harvestedCards) { card in
                MarketIntelligenceCard(card: card) { ticker in
                    HapticManager.selection()
                    navTicker = TickerDest(ticker: ticker)
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }

    // MARK: - Sources Sheet

    private var harvesterSourcesSheet: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: Theme.Spacing.medium) {
                        ForEach(harvesterSources) { source in
                            HStack(spacing: Theme.Spacing.standard) {
                                Circle()
                                    .fill(source.isHealthy ? Theme.bullGreen : Theme.bearRed)
                                    .frame(width: 8, height: 8)
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(source.sourceName)
                                        .font(Theme.officialStampFont(size: 12))
                                        .foregroundStyle(Theme.inkPrimary)
                                    if let last = source.lastSuccess {
                                        Text("Last: \(last)")
                                            .font(Theme.serialNumberFont(size: 9))
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                }
                                Spacer()
                                Text("\(source.itemsScraped) items")
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        if harvesterSources.isEmpty {
                            Text("Loading sources…")
                                .font(Theme.officialStampFont(size: 12))
                                .foregroundStyle(Theme.inkTertiary)
                                .padding(.top, Theme.sectionSpacing)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.card)
                }
            }
            .navigationTitle("Intelligence Sources")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                harvesterSources = (try? await NetworkManager.shared.fetchHarvesterSources()) ?? []
            }
        }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("विशेषज्ञ नेटवर्क")
                    .font(Theme.hindiFont(size: 11))
                    .foregroundStyle(Theme.inkSecondary)
                Text("MARKET MINDS")
                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("SEBI-Certified Expert Network")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.medium)
        .background(Theme.canvasDeep)
    }

    // MARK: Advisory Wire Section

    private var advisoryWireSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "ADVISORY WIRE", hindiTitle: "सलाह तार")
                .padding(.top, Theme.Spacing.medium)

            if vm.insights.isEmpty {
                emptyAdvisoryWire
            } else {
                ForEach(vm.insights) { insight in
                    InsightCard(insight: insight)
                        .padding(.horizontal, Theme.Spacing.card)
                }
            }
        }
    }

    private var emptyAdvisoryWire: some View {
        VStack(spacing: Theme.Spacing.medium) {
            Text("No advisory insights available.")
                .font(Theme.officialStampFont(size: 12))
                .foregroundStyle(Theme.inkTertiary)
            Text("Couldn't load right now. Please try again.")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.sectionSpacing)
    }

    // MARK: Verified Minds Section

    private var verifiedMindsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "VERIFIED MINDS", hindiTitle: "प्रमाणित विशेषज्ञ")
                .padding(.top, Theme.Spacing.medium)

            if vm.advisors.isEmpty {
                emptyVerifiedMinds
            } else {
                ForEach(vm.advisors) { advisor in
                    AdvisorBioCard(advisor: advisor)
                        .padding(.horizontal, Theme.Spacing.card)
                }
            }
        }
    }

    private var emptyVerifiedMinds: some View {
        VStack(spacing: Theme.Spacing.medium) {
            Text("No advisor data available.")
                .font(Theme.officialStampFont(size: 12))
                .foregroundStyle(Theme.inkTertiary)
            Text("Couldn't load right now. Please try again.")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.sectionSpacing)
    }

    // MARK: Loading Shimmer

    private var loadingShimmer: some View {
        VStack(spacing: Theme.Spacing.card) {
            ForEach(0..<3, id: \.self) { _ in
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.canvasDeep)
                    .frame(height: 120)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                    )
                    .padding(.horizontal, Theme.Spacing.card)
                    .shimmerPlaceholder(isLoading: true)
            }
        }
    }
}

// MARK: - Advisory Wire Insight Card

private func sentimentColor(for sentiment: String?) -> Color {
    guard let s = sentiment?.uppercased() else { return Theme.inkTertiary }
    if s.contains("BULLISH") || s.contains("POSITIVE") { return Theme.bullGreen }
    if s.contains("BEARISH") || s.contains("NEGATIVE") { return Theme.bearRed }
    return Theme.inkTertiary
}

private func sentimentLabel(for sentiment: String?) -> String {
    guard let s = sentiment?.uppercased() else { return "NEUTRAL" }
    if s.contains("BULLISH") || s.contains("POSITIVE") { return "BULLISH" }
    if s.contains("BEARISH") || s.contains("NEGATIVE") { return "BEARISH" }
    return "NEUTRAL"
}

struct InsightCard: View {
    let insight: TextAdvisoryInsight

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header row: advisor name + timestamp + sentiment badge
            HStack {
                if let name = insight.advisorName, !name.isEmpty {
                    Text(name)
                        .font(Theme.officialStampFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                if let ts = insight.timestamp {
                    Text(ts)
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
                // Sentiment badge
                Text(sentimentLabel(for: insight.extractedSentiment))
                    .font(Theme.serialNumberFont(size: 8))
                    .tracking(0.5)
                    .foregroundStyle(sentimentColor(for: insight.extractedSentiment))
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.small)
                    .background(sentimentColor(for: insight.extractedSentiment).opacity(0.08))
                    .cornerRadius(Theme.CornerRadius.small)
            }

            // Content text (monospaced)
            Text(insight.contentText)
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)

            // Ticker tag
            if let ticker = insight.targetTicker, !ticker.isEmpty {
                HStack(spacing: Theme.Spacing.small) {
                    Text(ticker)
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.small)
                    Spacer()
                }
            }
        }
        .padding(Theme.Spacing.card)
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderSage, lineWidth: 0.5))
        .cornerRadius(Theme.CornerRadius.small)
    }
}

// MARK: - 7.1 / 7.2 Expert Profile Card

struct ExpertProfileCard: View {
    let expert: MarketExpert

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Avatar + compliance badge
            HStack(spacing: Theme.Spacing.medium) {
                ZStack {
                    Circle()
                        .fill(Theme.canvasDeep)
                        .frame(width: 52, height: 52)
                    Circle()
                        .stroke(Theme.securityGold.opacity(0.4), lineWidth: 1.5)
                        .frame(width: 52, height: 52)
                    Text(String(expert.name.prefix(2)).uppercased())
                        .font(Theme.engravedSerif(size: 18, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(expert.name)
                        .font(Theme.officialStampFont(size: 13))
                        .foregroundStyle(Theme.inkPrimary)
                    // 7.1 Regulatory Compliance Badge
                    if expert.isVerified {
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "checkmark.seal.fill")
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.bullGreen)
                            Text("SEBI REGISTERED")
                                .font(Theme.serialNumberFont(size: 8))
                                .tracking(1)
                                .foregroundStyle(Theme.bullGreen)
                        }
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.bullGreen.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.small)
                    }
                }
            }

            // 7.2 Experience + Strategy
            HStack(spacing: Theme.Spacing.tight) {
                Image(systemName: "clock.fill")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
                Text("\(expert.yearsExperience)+ years on Dalal Street")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkSecondary)
            }

            Text(expert.strategy)
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.securityGold)

            // SEBI Reg ID
            if let regId = expert.sebiRegId {
                Text("SEBI: \(regId)")
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }

            // 7.2 Focus tags + post count
            HStack(spacing: Theme.Spacing.small) {
                ForEach(expert.focusTags.prefix(3), id: \.self) { tag in
                    Text(tag)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.borderSage)
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }

            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "doc.text.fill")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
                Text("\(expert.postCount) posts")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
    }
}

// MARK: - 7.3 / 7.4 Expert Post Card

struct ExpertPostCard: View {
    let post: ExpertPost
    let isSuperpro: Bool
    let onLike: () -> Void
    let onBookmark: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header
            HStack(spacing: Theme.Spacing.medium) {
                ZStack {
                    Circle()
                        .fill(Theme.canvasDeep)
                        .frame(width: 36, height: 36)
                    Circle()
                        .stroke(Theme.securityGold.opacity(0.3), lineWidth: 1)
                        .frame(width: 36, height: 36)
                    Text(String(post.expertName.prefix(1)))
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                }
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(post.expertName)
                        .font(Theme.officialStampFont(size: 12))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(IndianFormatter.elapsed(from: post.publishedAt))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                }
                Spacer()
                if let ticker = post.ticker {
                    Text(ticker)
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }

            // 7.3 Chart blur for premium content
            ZStack {
                Text(post.content)
                    .font(Theme.officialStampFont(size: 13))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
                    .blur(radius: post.isPremium && !isSuperpro ? 5 : 0)

                if post.isPremium && !isSuperpro {
                    VStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: "lock.shield.fill")
                            .font(Theme.officialStampFont(size: 20))
                            .foregroundStyle(Theme.securityGold)
                        Text("SUPER PRO REQUIRED")
                            .font(Theme.serialNumberFont(size: 9))
                            .tracking(1.5)
                            .foregroundStyle(Theme.securityGold)
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.canvasDeep.opacity(0.8))
                    .cornerRadius(Theme.CornerRadius.medium)
                }
            }

            // 7.4 Interaction row
            HStack(spacing: Theme.Spacing.card) {
                // Like counter
                Button(action: { HapticManager.selection(); onLike(); HapticManager.impact(.light) }) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: post.isLiked ? "heart.fill" : "heart")
                            .font(Theme.officialStampFont(size: 13))
                            .foregroundStyle(post.isLiked ? Theme.bearRed : Theme.inkTertiary)
                        Text("\(post.likeCount + (post.isLiked ? 1 : 0))")
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                // Bookmark
                Button(action: { HapticManager.selection(); onBookmark(); HapticManager.impact(.light) }) {
                    Image(systemName: post.isBookmarked ? "bookmark.fill" : "bookmark")
                        .font(Theme.officialStampFont(size: 13))
                        .foregroundStyle(post.isBookmarked ? Theme.securityGold : Theme.inkTertiary)
                }
                .accessibilityLabel("Toggle bookmark")

                Spacer()

                if post.isPremium {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "crown.fill")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.securityGold)
                        Text("SUPER PRO")
                            .font(Theme.serialNumberFont(size: 8))
                            .tracking(1)
                            .foregroundStyle(Theme.securityGold.opacity(0.7))
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - TickerDest (Identifiable wrapper for sheet navigation)

private struct TickerDest: Identifiable {
    let ticker: String
    var id: String { ticker }
}

// MARK: - Market Intelligence Card

struct MarketIntelligenceCard: View {
    let card: HarvestedCard
    let onTickerTap: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Credibility badge row
            HStack(spacing: Theme.Spacing.tight) {
                Image(systemName: sourceIcon(for: card.sourceType))
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(credibilityColor(for: card.credibilityScore))
                Text("\(shortSourceLabel(for: card.sourceType)) • Score \(card.credibilityScore)")
                    .font(Theme.serialNumberFont(size: 9))
                    .tracking(0.5)
                    .foregroundStyle(credibilityColor(for: card.credibilityScore))
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.small)
                    .background(credibilityColor(for: card.credibilityScore).opacity(0.1))
                    .cornerRadius(Theme.CornerRadius.small)
                Spacer()
                Text(timeAgoLabel(createdAt: card.createdAt, publishedAt: card.publishedAt))
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }

            // Title
            Text(card.title)
                .font(Theme.engravedSerif(size: 13, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(2)

            // Summary
            if let summary = card.reformattedSummary, !summary.isEmpty {
                Text(summary)
                    .font(Theme.engravedSerif(size: 12, weight: .regular))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(3)
                    .lineSpacing(3)
            }

            // Expert credential
            if let cred = card.expertCredential, !cred.isEmpty {
                Text(cred)
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
            }

            // Key takeaways (first 3)
            if let takeaways = card.keyTakeaways, !takeaways.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    ForEach(takeaways.prefix(3), id: \.self) { item in
                        HStack(alignment: .top, spacing: Theme.Spacing.small) {
                            Text("•")
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.securityGold)
                            Text(item)
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.inkSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }

            // Ticker chips
            if let tickers = card.tickers, !tickers.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Spacing.small) {
                        ForEach(tickers, id: \.self) { ticker in
                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                onTickerTap(ticker)
                            } label: {
                                Text(ticker)
                                    .font(Theme.serialNumberFont(size: 9))
                                    .foregroundStyle(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.medium)
                                    .padding(.vertical, Theme.Spacing.small)
                                    .background(Theme.securityGold.opacity(0.10))
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .ekPress()
        .onTapGesture {
            if let url = URL(string: card.sourceUrl) {
                UIApplication.shared.open(url)
            }
        }
    }

    // MARK: - Helpers

    private func shortSourceLabel(for sourceType: String) -> String {
        switch sourceType.uppercased() {
        case "CRISIL_RATING": return "CRISIL"
        case "ICRA_RATING": return "ICRA"
        case "CARE_RATING": return "CARE"
        case "INDIA_RATINGS": return "India Ratings"
        case "FUND_MANAGER_INTERVIEW": return "CNBC Expert"
        case "EXPERT_COLUMN": return "Columnist"
        case "SEBI_FILING", "EXCHANGE_FILING": return "NSE Filing"
        case "SEBI_RIA_NOTE": return "SEBI RIA"
        case "AMFI_DATA": return "AMFI"
        case "YOUTUBE": return "YouTube"
        default: return sourceType.capitalized
        }
    }

    private func sourceIcon(for sourceType: String) -> String {
        switch sourceType.uppercased() {
        case "SEBI_FILING", "EXCHANGE_FILING": return "building.columns.fill"
        case "CRISIL_RATING", "ICRA_RATING", "CARE_RATING", "INDIA_RATINGS": return "checkmark.shield.fill"
        case "FUND_MANAGER_INTERVIEW": return "person.fill.checkmark"
        case "EXPERT_COLUMN": return "newspaper.fill"
        case "SEBI_RIA_NOTE": return "person.badge.shield.checkmark.fill"
        case "AMFI_DATA": return "chart.bar.doc.horizontal.fill"
        case "YOUTUBE": return "play.rectangle.fill"
        default: return "doc.text.fill"
        }
    }

    private func credibilityColor(for score: Int) -> Color {
        switch score {
        case 10: return Theme.bullGreen
        case 8...9: return Theme.securityGold
        case 6...7: return Theme.inkSecondary
        default: return Theme.inkTertiary
        }
    }

    private func timeAgoLabel(createdAt: String?, publishedAt: String?) -> String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let iso2 = ISO8601DateFormatter()
        iso2.formatOptions = [.withInternetDateTime]
        for raw in [createdAt, publishedAt].compactMap({ $0 }) {
            if let date = iso.date(from: raw) ?? iso2.date(from: raw) {
                return IndianFormatter.elapsed(from: date)
            }
        }
        return ""
    }
}

// MARK: - Preview

#Preview("Expert Network") {
    ExpertNetworkView()
        .environmentObject(AuthManager())
}

#Preview("Expert Post Card") {
    ExpertPostCard(
        post: ExpertPost(
            id: "P1", expertId: "E1", expertName: "Rajesh Palviya",
            content: "Retail Capitulation confirmed at 22,000 Nifty. Institutional accumulation patterns visible in Bank Nifty futures OI.",
            ticker: "NIFTY", chartImageUrl: nil,
            publishedAt: Date().addingTimeInterval(-3600),
            likeCount: 847, isPremium: false
        ),
        isSuperpro: true,
        onLike: {},
        onBookmark: {}
    )
    .padding()
    .background(Theme.canvas)
}
