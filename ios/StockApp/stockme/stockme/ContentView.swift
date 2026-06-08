import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var tutorialManager: TutorialManager
    @State private var selectedTab = 0

    /// When true, the App-level launch handles the splash screen.
    /// ContentView renders immediately with no internal launch overlay.
    var bypassLaunch: Bool = false

    @State private var showLaunch: Bool
    private let launchOffset: CGFloat = 24

    init(bypassLaunch: Bool = false) {
        self.bypassLaunch = bypassLaunch
        _showLaunch = State(initialValue: !bypassLaunch)

        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(Theme.canvasDeep)
        appearance.shadowColor = UIColor(Theme.inkSecondary).withAlphaComponent(0.15)

        let goldColor = UIColor(Theme.securityGold)
        let mutedColor = UIColor(Theme.inkTertiary)
        let smallFont = UIFont.preferredFont(forTextStyle: .caption2)

        appearance.stackedLayoutAppearance.selected.iconColor = goldColor
        appearance.stackedLayoutAppearance.selected.titleTextAttributes = [
            .foregroundColor: goldColor, .font: smallFont
        ]
        appearance.stackedLayoutAppearance.normal.iconColor = mutedColor
        appearance.stackedLayoutAppearance.normal.titleTextAttributes = [
            .foregroundColor: mutedColor, .font: smallFont
        ]

        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
        UITabBar.appearance().tintColor = goldColor
        UITabBar.appearance().unselectedItemTintColor = mutedColor
    }

    var body: some View {
        ZStack {
            if authManager.isLoggedIn {
                mainTabView
                    .opacity(showLaunch ? 0 : 1)
                    .offset(y: showLaunch ? launchOffset : 0)
                    .animation(.spring(response: 0.55, dampingFraction: 0.82), value: showLaunch)
            } else {
                LoginScreen()
                    .opacity(showLaunch ? 0 : 1)
            }

            if showLaunch {
                LaunchSequenceView {
                    showLaunch = false
                }
                .transition(.opacity)
                .zIndex(10)
            }
        }
    }

    @ViewBuilder
    private var mainTabView: some View {
        TabView(selection: $selectedTab) {
            HomeScreen()
                .tabItem { Label("Home", systemImage: "house.fill") }
                .tag(0)

            MarketsView()
                .tabItem { Label("Markets", systemImage: "chart.bar.fill") }
                .tag(1)

            ExpertNetworkView()
                .tabItem { Label("Ideas", systemImage: "lightbulb.fill") }
                .tag(2)

            NewsMultimediaView()
                .tabItem { Label("News", systemImage: "newspaper.fill") }
                .tag(3)

            PortfolioScreen()
                .tabItem { Label("Portfolio", systemImage: "briefcase.fill") }
                .tag(4)
        }
        .accentColor(Theme.securityGold)
        .modifier(GlobalOverlayModifier(selectedTab: $selectedTab, tutorialManager: tutorialManager))
    }

    @ViewBuilder
    private var tabContent: some View {
        Group {
            switch selectedTab {
            case 0: HomeScreen()
            case 1: MarketsView()
            case 2: ExpertNetworkView()
            case 3: NewsMultimediaView()
            case 4: PortfolioScreen()
            default: HomeScreen()
            }
        }
        .modifier(GlobalOverlayModifier(selectedTab: $selectedTab, tutorialManager: tutorialManager))
    }
}

// MARK: - Global Overlay Modifier
private struct GlobalOverlayModifier: ViewModifier {
    @Binding var selectedTab: Int
    @ObservedObject var tutorialManager: TutorialManager

    func body(content: Content) -> some View {
        content
            .overlay(
                Group {
                    if tutorialManager.isShowingTutorial {
                        TutorialOverlayView()
                    }
                }
            )
            .onChange(of: tutorialManager.currentStep) { _, step in
                guard tutorialManager.isShowingTutorial else { return }
                let tab: Int
                switch step {
                case 2, 3:    tab = 0  // Home tab
                case 4:       tab = 1  // Markets tab (Search/Discover)
                case 5, 6, 7: tab = 4  // Portfolio tab (holdings, red flags, analysis)
                case 8:       tab = 1  // Markets tab (Alerts lives in Markets sub-tab)
                case 9:       tab = 4  // Portfolio tab (Trade Journal is a segment here)
                default:      tab = 0
                }
                selectedTab = tab
            }
            .onReceive(NotificationCenter.default.publisher(for: Notification.Name("switchToTab"))) { notif in
                if let tab = notif.userInfo?["tab"] as? Int {
                    withAnimation(.easeInOut(duration: 0.25)) { selectedTab = tab }
                }
            }
    }
}

// MARK: - Market Section Enum

enum MarketSection: String, Hashable, CaseIterable {
    case earnings  = "earnings"
    case technical = "technical"
    case unlisted  = "unlisted"
    case screener  = "screener"
    case alerts    = "alerts"

    var icon: String {
        switch self {
        case .earnings:  return "chart.bar.doc.horizontal.fill"
        case .technical: return "waveform.path.ecg"
        case .unlisted:  return "building.2.fill"
        case .screener:  return "magnifyingglass.circle.fill"
        case .alerts:    return "bell.badge.fill"
        }
    }
    var hindi: String {
        switch self {
        case .earnings:  return "आय परिणाम"
        case .technical: return "तकनीकी गति"
        case .unlisted:  return "असूचीबद्ध"
        case .screener:  return "शेयर खोज"
        case .alerts:    return "मूल्य चेतावनी"
        }
    }
    var englishTitle: String {
        switch self {
        case .earnings:  return "EARNINGS"
        case .technical: return "TECHNICAL"
        case .unlisted:  return "UNLISTED"
        case .screener:  return "SCREENER"
        case .alerts:    return "ALERTS"
        }
    }
    var subtitle: String {
        switch self {
        case .earnings:  return "Quarterly Results"
        case .technical: return "Momentum Scanner"
        case .unlisted:  return "Pre-IPO Marketplace"
        case .screener:  return "Stock Discovery"
        case .alerts:    return "Price Watch"
        }
    }
    var description: String {
        switch self {
        case .earnings:  return "YoY growth tracking, earnings calendar, beat/miss analysis and post-result movers"
        case .technical: return "OI trends, sector rotation, golden/death cross signals and momentum scanner"
        case .unlisted:  return "OTC price discovery for pre-IPO, SME board and upcoming listing advisory"
        case .screener:  return "Search any NSE or BSE stock by name or ticker, preset screens, quick compare"
        case .alerts:    return "Target price triggers and surveillance flags for your entire watchlist"
        }
    }
    var accentColor: Color {
        switch self {
        case .earnings:  return Theme.securityGold
        case .technical: return Theme.bullGreen
        case .unlisted:  return Theme.holdAmber
        case .screener:  return Theme.inkSecondary
        case .alerts:    return Theme.bearRed
        }
    }
}

// MARK: - Markets View (Section 10: Markets tab hub)

struct MarketsView: View {
    @EnvironmentObject var authManager: AuthManager

    // nil = hub landing; non-nil = full-screen section (no NavigationStack nesting)
    @State private var activeSection: MarketSection? = nil
    @State private var livePulse = false
    @State private var indices: [LiveMarketIndex] = []
    @State private var isLoadingIndices = false

    // Featured section displayed prominently at the top of the hub
    private let featuredSection: MarketSection = .earnings
    // Remaining 4 sections shown in a 2-column grid
    private let gridSections: [[MarketSection]] = [[.technical, .unlisted], [.screener, .alerts]]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            if let section = activeSection {
                sectionShell(section)
                    .transition(.asymmetric(
                        insertion: .move(edge: .trailing).combined(with: .opacity),
                        removal:   .move(edge: .trailing).combined(with: .opacity)
                    ))
            } else {
                hubView
                    .transition(.opacity)
            }
        }
        .animation(.spring(response: 0.38, dampingFraction: 0.84), value: activeSection)
        .task { await loadIndices() }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.1).repeatForever(autoreverses: true)) {
                livePulse = true
            }
        }
    }

    // MARK: - Hub Landing

    private var hubView: some View {
        VStack(spacing: 0) {
            hubHeader
            ScrollView {
                VStack(spacing: Theme.sectionSpacing) {
                    indicesStrip
                        .padding(.top, Theme.Spacing.medium)
                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)
                    // Featured section — full width
                    featuredCard(featuredSection)
                        .padding(.horizontal, Theme.screenPadding)
                    // 2-col grid rows
                    ForEach(gridSections, id: \.first) { row in
                        HStack(alignment: .top, spacing: Theme.Spacing.card) {
                            ForEach(row, id: \.self) { section in
                                gridCard(section)
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                    }
                }
                .padding(.bottom, Theme.sectionSpacing)
            }
            .scrollIndicators(.hidden)
        }
    }

    // MARK: Hub header

    private var hubHeader: some View {
        HStack(alignment: .center, spacing: 0) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("बाज़ार")
                    .font(Theme.hindiFont(size: 11))
                    .foregroundStyle(Theme.inkSecondary)
                Text("MARKETS")
                    .font(Theme.engravedSerif(size: 26, weight: .bold, relativeTo: .title))
                    .foregroundStyle(Theme.inkPrimary)
            }
            Spacer()
            // Live pulse indicator
            HStack(spacing: Theme.Spacing.small) {
                Circle()
                    .fill(Theme.bullGreen)
                    .frame(width: 6, height: 6)
                    .scaleEffect(livePulse ? 1.5 : 0.8)
                    .opacity(livePulse ? 0.5 : 1.0)
                Text("LIVE")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.5)
                    .foregroundStyle(Theme.bullGreen)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.large)
        .padding(.bottom, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
    }

    // MARK: Indices strip

    private var indicesStrip: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("LIVE INDICES")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            if isLoadingIndices || indices.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Spacing.standard) {
                        ForEach(["NIFTY 50", "SENSEX", "BANK NIFTY"], id: \.self) { name in
                            indexPlaceholderChip(name: name)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Spacing.standard) {
                        ForEach(indices.prefix(6)) { index in
                            indexMiniChip(index: index)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
    }

    private func indexMiniChip(index: LiveMarketIndex) -> some View {
        let isPositive = index.changePct >= 0
        let changeStr  = (isPositive ? "+" : "") + String(format: "%.2f%%", index.changePct)
        let valueStr   = index.ticker == "USDINR=X"
            ? String(format: "%.2f", index.value)
            : IndianFormatter.price(index.value)

        return VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(index.name)
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
                .lineLimit(1)
            Text(valueStr)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
                .foregroundStyle(Theme.inkPrimary)
                .monospacedDigit()
            HStack(spacing: Theme.Spacing.xSmall) {
                Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                Text(changeStr)
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
            }
            .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .frame(minWidth: 88, alignment: .leading)
        .banknoteCard()
    }

    private func indexPlaceholderChip(name: String) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(name)
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.inkTertiary.opacity(0.12))
                .frame(width: 72, height: 14)
                .shimmerPlaceholder(isLoading: true)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.inkTertiary.opacity(0.08))
                .frame(width: 48, height: 10)
                .shimmerPlaceholder(isLoading: true)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .frame(minWidth: 88, alignment: .leading)
        .banknoteCard()
    }

    // MARK: Featured card (full width)

    private func featuredCard(_ section: MarketSection) -> some View {
        Button(action: {
            HapticManager.impact(.light)
            withAnimation(.spring(response: 0.38, dampingFraction: 0.84)) { activeSection = section }
        }) {
            HStack(spacing: Theme.Spacing.large) {
                // Icon column
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .fill(section.accentColor.opacity(0.12))
                        .frame(width: 54, height: 54)
                    Image(systemName: section.icon)
                        .font(Theme.serialNumberFont(size: 24, relativeTo: .headline))
                        .foregroundStyle(section.accentColor)
                }

                // Text column
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(section.hindi)
                        .font(Theme.hindiFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(section.englishTitle)
                        .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(section.subtitle)
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                        .tracking(1.2)
                        .foregroundStyle(section.accentColor)
                    Text(section.description)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, Theme.Spacing.xSmall)
                }

                Spacer()

                // Arrow
                Image(systemName: "arrow.right")
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
                    .foregroundStyle(section.accentColor.opacity(0.7))
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
            // Gold accent stripe along leading edge
            .overlay(
                Rectangle()
                    .fill(section.accentColor.opacity(0.8))
                    .frame(width: 3)
                    .clipShape(RoundedRectangle(cornerRadius: 2)),
                alignment: .leading
            )
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: Grid card (half width)

    private func gridCard(_ section: MarketSection) -> some View {
        Button(action: {
            HapticManager.selection()
            withAnimation(.spring(response: 0.38, dampingFraction: 0.84)) { activeSection = section }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                // Icon + arrow row
                HStack(alignment: .top) {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(section.accentColor.opacity(0.12))
                            .frame(width: 36, height: 36)
                        Image(systemName: section.icon)
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .subheadline))
                            .foregroundStyle(section.accentColor)
                    }
                    Spacer()
                    Image(systemName: "arrow.up.right")
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(section.accentColor.opacity(0.6))
                        .padding(.top, Theme.Spacing.xSmall)
                }
                .padding(.top, Theme.Spacing.small)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(section.hindi)
                        .font(Theme.hindiFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(section.englishTitle)
                        .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(section.subtitle)
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.0)
                        .foregroundStyle(section.accentColor)
                }

                Text(section.description)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                    .lineSpacing(2)
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(Theme.Spacing.standard)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Section Shell (fullscreen with back strip)

    @ViewBuilder
    private func sectionShell(_ section: MarketSection) -> some View {
        VStack(spacing: 0) {
            // ← MARKETS branded back strip
            HStack(spacing: Theme.Spacing.standard) {
                Button(action: {
                    HapticManager.selection()
                    withAnimation(.spring(response: 0.38, dampingFraction: 0.84)) { activeSection = nil }
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "chevron.left")
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        Text("MARKETS")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                            .tracking(1.5)
                    }
                    .foregroundStyle(Theme.securityGold)
                    .padding(.leading, Theme.screenPadding)
                    .padding(.vertical, Theme.Spacing.medium)
                }
                .buttonStyle(EKPressStyle())

                Spacer()

                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: section.icon)
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                    Text(section.englishTitle)
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                        .tracking(1.5)
                }
                .foregroundStyle(Theme.inkTertiary)
                .padding(.trailing, Theme.screenPadding)
            }
            .background(Theme.canvasDeep)
            .overlay(
                Rectangle()
                    .fill(section.accentColor.opacity(0.5))
                    .frame(height: 1.5),
                alignment: .bottom
            )

            // The actual section view — unchanged, full screen
            sectionContent(section)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder
    private func sectionContent(_ section: MarketSection) -> some View {
        switch section {
        case .earnings:  EarningsDashboardView()
        case .technical: TechnicalMomentumView()
        case .unlisted:  PreIPOMarketplaceView()
        case .screener:  SearchScreen()
        case .alerts:    AlertsScreen()
        }
    }

    // MARK: - Data

    private func loadIndices() async {
        isLoadingIndices = true
        if let result = try? await NetworkManager.shared.getMarketIndices() {
            indices = result.indices
        }
        isLoadingIndices = false
    }
}
