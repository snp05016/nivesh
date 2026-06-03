import SwiftUI
import Combine

// MARK: - Expert Network ViewModel

@MainActor
class ExpertNetworkViewModel: ObservableObject {
    @Published var experts: [MarketExpert] = []
    @Published var posts: [ExpertPost] = []
    @Published var isLoading = false
    @AppStorage("expert_bookmarks") private var bookmarksRaw: String = ""

    var bookmarkedPostIds: Set<String> {
        get { Set(bookmarksRaw.split(separator: ",").map(String.init)) }
        set { bookmarksRaw = newValue.joined(separator: ",") }
    }

    // Seed mock experts for offline / preview
    private let mockExperts: [MarketExpert] = [
        MarketExpert(id: "E1", name: "Rajesh Palviya", sebiRegId: "INH100001234",
                     yearsExperience: 19, strategy: "Harmonic Trading Strategy",
                     focusTags: ["Charts", "Currency", "Gold", "Global Markets"],
                     postCount: 3847, isVerified: true,
                     bio: "Senior VP Technical Research at Axis Securities. 19+ years tracking Indian and global derivative markets with proprietary harmonic pattern systems."),
        MarketExpert(id: "E2", name: "Anand James", sebiRegId: "INH200003456",
                     yearsExperience: 14, strategy: "Wyckoff Method",
                     focusTags: ["Charts", "Equity", "Index"],
                     postCount: 2104, isVerified: true,
                     bio: "Chief Market Strategist applying Wyckoff accumulation/distribution methodology to Nifty and Sensex structural pivots."),
        MarketExpert(id: "E3", name: "Neeraj Chadawar", sebiRegId: "INH300005678",
                     yearsExperience: 11, strategy: "Price Action & Volume",
                     focusTags: ["Equity", "Smallcap", "Midcap"],
                     postCount: 1576, isVerified: true,
                     bio: "Head of Research focused on mid and smallcap opportunities using pure price action with volume confirmation."),
    ]

    private let mockPosts: [ExpertPost] = [
        ExpertPost(id: "P1", expertId: "E1", expertName: "Rajesh Palviya",
                   content: "Retail Capitulation confirmed at 22,000 Nifty. Institutional accumulation patterns visible in Bank Nifty futures OI. Expect sharp reversal within 3 sessions.",
                   ticker: "NIFTY", chartImageUrl: nil,
                   publishedAt: Date().addingTimeInterval(-3600),
                   likeCount: 847, isPremium: false),
        ExpertPost(id: "P2", expertId: "E1", expertName: "Rajesh Palviya",
                   content: "HDFC Bank forming a classic Bat harmonic pattern on weekly charts. Target cluster at ₹1,820–1,860. This is a high-probability setup with defined stop at ₹1,620.",
                   ticker: "HDFCBANK", chartImageUrl: nil,
                   publishedAt: Date().addingTimeInterval(-7200),
                   likeCount: 1203, isPremium: false),
        ExpertPost(id: "P3", expertId: "E2", expertName: "Anand James",
                   content: "Nifty50 is in Wyckoff Phase C re-accumulation. Spring below 21,800 tested and held. Composite Operator activity suggests markup phase initiation.",
                   ticker: "NIFTY", chartImageUrl: nil,
                   publishedAt: Date().addingTimeInterval(-14400),
                   likeCount: 634, isPremium: false),
        ExpertPost(id: "P4", expertId: "E3", expertName: "Neeraj Chadawar",
                   content: "Dixon Technologies printing a Cup & Handle breakout on monthly chart. Volume expansion on breakout bar is critical confirmation. Entry on pullback to ₹14,200.",
                   ticker: "DIXON", chartImageUrl: nil,
                   publishedAt: Date().addingTimeInterval(-21600),
                   likeCount: 412, isPremium: false),
    ]

    func load() {
        isLoading = true
        Task {
            // Production: fetch from /api/v1/experts and /api/v1/expert-posts
            experts = mockExperts
            posts = mockPosts
            isLoading = false
        }
    }

    func toggleLike(postId: String) {
        guard let idx = posts.firstIndex(where: { $0.id == postId }) else { return }
        posts[idx].isLiked.toggle()
        // In production: POST /api/v1/expert-posts/{id}/like
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
    private let isSuperpro: Bool = true

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: 0) {
                pageHeader
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // 7.1 Expert Directory
                        expertsSection
                        GuillocheDivider().padding(.horizontal, 16)
                        // 7.4 Posts
                        postsSection
                    }
                    .padding(.bottom, 20)
                }
            }
        }
        .task { vm.load() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("MARKET MINDS")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.securityGold)
                Text("SEBI-Certified Expert Network")
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

    // MARK: 7.1 Experts Section

    private var expertsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("VERIFIED PROFESSIONAL DIRECTORY")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)
                .padding(.top, 16)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(vm.experts) { expert in
                        ExpertProfileCard(expert: expert)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: 7.4 Posts Section

    private var postsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("STRATEGY WRITE-UPS")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, 16)

            ForEach(vm.posts) { post in
                ExpertPostCard(post: post, isSuperpro: isSuperpro,
                               onLike: { vm.toggleLike(postId: post.id) },
                               onBookmark: { vm.toggleBookmark(postId: post.id) })
                .padding(.horizontal, 16)
            }
        }
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
                        .foregroundColor(Theme.inkPrimary)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(expert.name)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(Theme.inkPrimary)
                    // 7.1 Regulatory Compliance Badge
                    if expert.isVerified {
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.seal.fill")
                                .font(.system(size: 10))
                                .foregroundColor(Theme.bullGreen)
                            Text("SEBI REGISTERED")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .tracking(1)
                                .foregroundColor(Theme.bullGreen)
                        }
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Theme.bullGreen.opacity(0.08))
                        .cornerRadius(4)
                    }
                }
            }

            // 7.2 Experience + Strategy
            HStack(spacing: 6) {
                Image(systemName: "clock.fill")
                    .font(.system(size: 9))
                    .foregroundColor(Theme.inkTertiary)
                Text("\(expert.yearsExperience)+ years on Dalal Street")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkSecondary)
            }

            Text(expert.strategy)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(Theme.securityGold)

            // SEBI Reg ID
            if let regId = expert.sebiRegId {
                Text("SEBI: \(regId)")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(Theme.inkTertiary)
            }

            // 7.2 Focus tags + post count
            HStack(spacing: 4) {
                ForEach(expert.focusTags.prefix(3), id: \.self) { tag in
                    Text(tag)
                        .font(.system(size: 8, weight: .semibold))
                        .foregroundColor(Theme.inkSecondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Theme.borderSage)
                        .cornerRadius(4)
                }
            }

            HStack(spacing: 4) {
                Image(systemName: "doc.text.fill")
                    .font(.system(size: 9))
                    .foregroundColor(Theme.inkTertiary)
                Text("\(expert.postCount) posts")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(14)
        .frame(width: 240)
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
                        .foregroundColor(Theme.inkPrimary)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(post.expertName)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.inkPrimary)
                    Text(IndianFormatter.elapsed(from: post.publishedAt))
                        .font(.system(size: 10))
                        .foregroundColor(Theme.inkTertiary)
                }
                Spacer()
                if let ticker = post.ticker {
                    Text(ticker)
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundColor(Theme.securityGold)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(4)
                }
            }

            // 7.3 Chart blur for premium content
            ZStack {
                Text(post.content)
                    .font(.system(size: 13))
                    .foregroundColor(Theme.inkPrimary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
                    .blur(radius: post.isPremium && !isSuperpro ? 5 : 0)

                if post.isPremium && !isSuperpro {
                    VStack(spacing: 6) {
                        Image(systemName: "lock.shield.fill")
                            .font(.system(size: 20))
                            .foregroundColor(Theme.securityGold)
                        Text("SUPER PRO REQUIRED")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .tracking(1.5)
                            .foregroundColor(Theme.securityGold)
                    }
                    .padding(16)
                    .background(Theme.canvasDeep.opacity(0.8))
                    .cornerRadius(8)
                }
            }

            // 7.4 Interaction row
            HStack(spacing: 16) {
                // Like counter
                Button(action: { onLike(); HapticManager.impact(.light) }) {
                    HStack(spacing: 5) {
                        Image(systemName: post.isLiked ? "heart.fill" : "heart")
                            .font(.system(size: 13))
                            .foregroundColor(post.isLiked ? Theme.bearRed : Theme.inkTertiary)
                        Text("\(post.likeCount + (post.isLiked ? 1 : 0))")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.inkTertiary)
                    }
                }

                // Bookmark
                Button(action: { onBookmark(); HapticManager.impact(.light) }) {
                    Image(systemName: post.isBookmarked ? "bookmark.fill" : "bookmark")
                        .font(.system(size: 13))
                        .foregroundColor(post.isBookmarked ? Theme.securityGold : Theme.inkTertiary)
                }

                Spacer()

                if post.isPremium {
                    HStack(spacing: 4) {
                        Image(systemName: "crown.fill")
                            .font(.system(size: 9))
                            .foregroundColor(Theme.securityGold)
                        Text("SUPER PRO")
                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                            .tracking(1)
                            .foregroundColor(Theme.securityGold.opacity(0.7))
                    }
                }
            }
        }
        .padding(14)
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
