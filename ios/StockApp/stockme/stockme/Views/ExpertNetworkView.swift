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

    private static let fallbackExperts: [MarketExpert] = [
        MarketExpert(id: "E1", name: "Rajesh Palviya", sebiRegId: nil,
                     yearsExperience: 19, strategy: "Harmonic Trading Strategy",
                     focusTags: ["Charts", "Currency", "Gold"],
                     postCount: 0, isVerified: true,
                     bio: "Senior VP Technical Research tracking Indian and global derivative markets."),
        MarketExpert(id: "E2", name: "Anand James", sebiRegId: nil,
                     yearsExperience: 14, strategy: "Wyckoff Method",
                     focusTags: ["Charts", "Equity", "Index"],
                     postCount: 0, isVerified: true,
                     bio: "Chief Market Strategist applying Wyckoff methodology to Nifty structural pivots."),
    ]

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
            experts = e.isEmpty ? Self.fallbackExperts : e
            posts = p

            if advisors.isEmpty && insights.isEmpty {
                fetchError = "No advisor data available. Check backend connection."
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

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: 0) {
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
                        VStack(alignment: .leading, spacing: 12) {
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
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
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
        .padding(.top, 14)
        .padding(.bottom, 10)
        .background(Theme.canvasDeep)
    }

    // MARK: Advisory Wire Section

    private var advisoryWireSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "ADVISORY WIRE", hindiTitle: "सलाह तार")
                .padding(.top, 8)

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
            Text("Check backend connection.")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }

    // MARK: Verified Minds Section

    private var verifiedMindsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "VERIFIED MINDS", hindiTitle: "प्रमाणित विशेषज्ञ")
                .padding(.top, 8)

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
            Text("Check backend connection.")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
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
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, 3)
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
                        .padding(.horizontal, 7).padding(.vertical, 3)
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
        VStack(alignment: .leading, spacing: 12) {
            // Avatar + compliance badge
            HStack(spacing: 10) {
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
                        .padding(.vertical, 3)
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
                        .padding(.vertical, 3)
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
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack(spacing: 8) {
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
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                }
                Spacer()
                if let ticker = post.ticker {
                    Text(ticker)
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, 7).padding(.vertical, 3)
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
                Button(action: { onLike(); HapticManager.impact(.light) }) {
                    HStack(spacing: 5) {
                        Image(systemName: post.isLiked ? "heart.fill" : "heart")
                            .font(Theme.officialStampFont(size: 13))
                            .foregroundStyle(post.isLiked ? Theme.bearRed : Theme.inkTertiary)
                        Text("\(post.likeCount + (post.isLiked ? 1 : 0))")
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                // Bookmark
                Button(action: { onBookmark(); HapticManager.impact(.light) }) {
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
