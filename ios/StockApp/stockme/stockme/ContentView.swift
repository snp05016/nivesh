import SwiftUI
import UIKit

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var tutorialManager: TutorialManager
    @EnvironmentObject var engineManager: AnalysisEngineManager
    @State private var selectedTab = 0
    @State private var launchAnimDone = false

    /// When true, the App-level launch handles the splash screen.
    /// ContentView renders immediately with no internal launch overlay.
    var bypassLaunch: Bool = false

    @State private var showLaunch: Bool
    private let launchOffset: CGFloat = UIScreen.main.bounds.height * 0.08
    @AppStorage("selectedTheme") private var selectedTheme: String = AppTheme.darkImmersive.rawValue

    init(bypassLaunch: Bool = false) {
        self.bypassLaunch = bypassLaunch
        _showLaunch = State(initialValue: !bypassLaunch)
        setupTabBarAppearance()
    }

    private func setupTabBarAppearance() {
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
                LaunchSequenceView(isAnimationComplete: $launchAnimDone)
                    .transition(.opacity)
                    .zIndex(10)
            }
        }
        .crashGuard("ContentView")
        .onChange(of: launchAnimDone) { done in
            if done { showLaunch = false }
        }
        .onAppear {
            setupTabBarAppearance()
            engineManager.startWatching()
        }
        .onChange(of: selectedTheme) { _, _ in
            setupTabBarAppearance()
        }
        .withCopilot()
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
        .tint(Theme.securityGold)
        .toolbarBackground(Theme.canvasDeep, for: .tabBar)
        .toolbarBackground(.visible, for: .tabBar)
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
    @EnvironmentObject var engineManager: AnalysisEngineManager
    @State private var showEngineActivity = false

    func body(content: Content) -> some View {
        content
            .overlay(
                Group {
                    // v2 engine — global running pill
                    if engineManager.isRunning {
                        VStack { globalRunningPill; Spacer() }
                    }
                    if tutorialManager.isShowingTutorial {
                        TutorialOverlayView()
                    }
                }
            )
            .sheet(isPresented: $showEngineActivity) {
                EngineActivityView()
            }
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
    @ViewBuilder
    private var globalRunningPill: some View {
        Button {
            HapticManager.selection()
            showEngineActivity = true
        } label: {
            HStack(spacing: Theme.Spacing.tight) {
                Circle()
                    .fill(Theme.securityGold)
                    .frame(width: 6, height: 6)
                    .opacity(0.9)
                Text(engineManager.ticker ?? "ANALYSIS")
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.0)
                    .foregroundStyle(Theme.securityGold)
                if let stage = engineManager.stage {
                    Text("·")
                        .foregroundStyle(Theme.inkTertiary)
                    Text(stage)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(1)
                }
                Spacer()
                Text("\(Int(engineManager.progressPct))%")
                    .font(Theme.serialNumberFont(size: 10))
                    .foregroundStyle(Theme.securityGold)
            }
            .padding(.vertical, Theme.Spacing.tight)
            .padding(.horizontal, Theme.Spacing.standard)
            .background(Theme.securityGold.opacity(0.10))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5)
            )
            .cornerRadius(Theme.CornerRadius.large)
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.tight)
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Markets Tab

enum MarketsTab: String, CaseIterable {
    case overview  = "OVERVIEW"
    case earnings  = "EARNINGS"
    case technical = "TECHNICAL"
    case unlisted  = "UNLISTED"
    case screener  = "SCREENER"
    case alerts    = "ALERTS"
    case strategy  = "STRATEGY LAB"
}

// MARK: - Markets Tab Bar

struct MarketsTabBar: View {
    @Binding var selected: MarketsTab

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Spacing.standard) {
                ForEach(MarketsTab.allCases, id: \.self) { tab in
                    Button(action: { HapticManager.selection(); selected = tab }) {
                        Text(tab.rawValue)
                            .font(Theme.officialStampFont(size: 10))
                            .tracking(1.0)
                            .foregroundStyle(selected == tab ? Theme.canvas : Theme.inkSecondary)
                            .padding(.horizontal, Theme.Spacing.card)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(selected == tab ? Theme.securityGold : Theme.canvasDeep)
                            .clipShape(Capsule())
                            .overlay(
                                Capsule().stroke(
                                    selected == tab ? Theme.securityGold : Theme.borderSage,
                                    lineWidth: 0.5
                                )
                            )
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.medium)
        }
        .background(Theme.canvas)
    }
}

// MARK: - Market Section Enum

enum MarketSection: String, Hashable, CaseIterable {
    case earnings  = "earnings"
    case technical = "technical"
    case unlisted  = "unlisted"
    case screener  = "screener"
    case alerts    = "alerts"
    case strategy  = "strategy"
    case nl_screener = "nl_screener"
    case correlation = "correlation"
    case anomalies = "anomalies"
    case sector_rotation = "sector_rotation"
    case stress_test = "stress_test"
    case earnings_surprise = "earnings_surprise"

    var icon: String {
        switch self {
        case .earnings:  return "chart.bar.doc.horizontal.fill"
        case .technical: return "waveform.path.ecg"
        case .unlisted:  return "building.2.fill"
        case .screener:  return "magnifyingglass.circle.fill"
        case .alerts:    return "bell.badge.fill"
        case .strategy:  return "flask.fill"
        case .nl_screener: return "text.magnifyingglass"
        case .correlation: return "squareshape.split.2x2"
        case .anomalies: return "exclamationmark.triangle.fill"
        case .sector_rotation: return "arrow.triangle.2.circlepath"
        case .stress_test: return "bolt.trianglebadge.exclamationmark"
        case .earnings_surprise: return "sparkles.rectangle"
        }
    }
    var hindi: String {
        switch self {
        case .earnings:  return "आय परिणाम"
        case .technical: return "तकनीकी गति"
        case .unlisted:  return "असूचीबद्ध"
        case .screener:  return "शेयर खोज"
        case .alerts:    return "मूल्य चेतावनी"
        case .strategy:  return "रणनीति प्रयोगशाला"
        case .nl_screener: return "प्राकृतिक भाषा खोज"
        case .correlation: return "सहसंबंध मैट्रिक्स"
        case .anomalies: return "बाज़ार विसंगतियाँ"
        case .sector_rotation: return "सेक्टर रोटेशन"
        case .stress_test: return "पोर्टफोलियो तनाव परीक्षण"
        case .earnings_surprise: return "आय आश्चर्य"
        }
    }
    var englishTitle: String {
        switch self {
        case .earnings:  return "EARNINGS"
        case .technical: return "TECHNICAL"
        case .unlisted:  return "UNLISTED"
        case .screener:  return "SCREENER"
        case .alerts:    return "ALERTS"
        case .strategy:  return "STRATEGY LAB"
        case .nl_screener: return "NL SCREENER"
        case .correlation: return "CORRELATION MATRIX"
        case .anomalies: return "ANOMALIES"
        case .sector_rotation: return "SECTOR ROTATION"
        case .stress_test: return "STRESS TEST"
        case .earnings_surprise: return "EARNINGS SURPRISE"
        }
    }
    var subtitle: String {
        switch self {
        case .earnings:  return "Quarterly Results"
        case .technical: return "Momentum Scanner"
        case .unlisted:  return "Pre-IPO Marketplace"
        case .screener:  return "Stock Discovery"
        case .alerts:    return "Price Watch"
        case .strategy:  return "Backtest Strategies"
        case .nl_screener: return "Search by Natural Language"
        case .correlation: return "Cross-Asset Correlation"
        case .anomalies: return "Market Anomalies"
        case .sector_rotation: return "Sector Capital Flow"
        case .stress_test: return "Portfolio Shock Analysis"
        case .earnings_surprise: return "Earnings Surprise"
        }
    }
    var description: String {
        switch self {
        case .earnings:  return "YoY growth tracking, earnings calendar, beat/miss analysis and post-result movers"
        case .technical: return "OI trends, sector rotation, golden/death cross signals and momentum scanner"
        case .unlisted:  return "OTC price discovery for pre-IPO, SME board and upcoming listing advisory"
        case .screener:  return "Search any NSE or BSE stock by name or ticker, preset screens, quick compare"
        case .alerts:    return "Target price triggers and surveillance flags for your entire watchlist"
        case .strategy:  return "Backtest pre-built and custom trading strategies against historical data"
        case .nl_screener: return "Search stocks using natural language queries powered by AI"
        case .correlation: return "Analyze correlation matrices to diversify portfolio risk"
        case .anomalies: return "Scan the market for unusual volume, price, or order book anomalies"
        case .sector_rotation: return "Track capital flow across different market sectors"
        case .stress_test: return "Simulate portfolio performance under various macroeconomic shocks"
        case .earnings_surprise: return "Track and predict positive and negative earnings surprises"
        }
    }
    var accentColor: Color {
        switch self {
        case .earnings:  return Theme.securityGold
        case .technical: return Theme.bullGreen
        case .unlisted:  return Theme.holdAmber
        case .screener:  return Theme.inkSecondary
        case .alerts:    return Theme.bearRed
        case .strategy:  return Theme.avatarBlue
        case .nl_screener: return Theme.securityGold
        case .correlation: return Theme.avatarBlue
        case .anomalies: return Theme.bearRed
        case .sector_rotation: return Theme.bullGreen
        case .stress_test: return Theme.bearRed
        case .earnings_surprise: return Theme.securityGold
        }
    }
}

// MARK: - Markets View (Section 10: Markets tab hub)

struct MarketsView: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var selectedTab: MarketsTab = .overview
    @State private var activeSection: MarketSection? = nil
    @State private var livePulse = false
    @State private var indices: [LiveMarketIndex] = []
    @State private var isLoadingIndices = false

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
                VStack(spacing: Theme.Spacing.none) {
                    // Sticky tab bar
                    MarketsTabBar(selected: $selectedTab)
                        .background(Theme.canvas)

                    SectionDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    // Content area
                    Group {
                        switch selectedTab {
                        case .overview:
                            overviewContent
                        case .earnings:
                            sectionPage(.earnings)
                        case .technical:
                            sectionPage(.technical)
                        case .unlisted:
                            sectionPage(.unlisted)
                        case .screener:
                            sectionPage(.screener)
                        case .alerts:
                            sectionPage(.alerts)
                        case .strategy:
                            sectionPage(.strategy)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .transition(.opacity)
                    .animation(.easeInOut(duration: 0.18), value: selectedTab)
                }
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

    // MARK: - Overview (formerly hub)

    private var overviewContent: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                // Live indices strip
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
                .padding(.top, Theme.Spacing.standard)

                SectionDivider()
                    .padding(.horizontal, Theme.screenPadding)

                // Section cards
                ForEach(MarketSection.allCases, id: \.self) { section in
                    sectionCard(section)
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.bottom, Theme.sectionSpacing)
        }
        .scrollIndicators(.hidden)
    }

    // MARK: - Section page (tab content for non-overview tabs)

    @ViewBuilder
    private func sectionPage(_ section: MarketSection) -> some View {
        VStack(spacing: Theme.Spacing.none) {
            // Inline header with push button
            HStack(spacing: Theme.Spacing.standard) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(section.hindi)
                        .font(Theme.hindiFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(section.englishTitle)
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)
                }
                Spacer()
                Button(action: {
                    HapticManager.selection()
                    withAnimation(.spring(response: 0.38, dampingFraction: 0.84)) {
                        activeSection = section
                    }
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Text("FULL VIEW")
                            .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                            .tracking(1.2)
                        Image(systemName: "arrow.up.left.and.arrow.down.right")
                            .font(.caption2)
                    }
                    .foregroundStyle(Theme.securityGold)
                    .padding(.horizontal, Theme.Spacing.standard)
                    .padding(.vertical, Theme.Spacing.small)
                    .background(Theme.securityGold.opacity(0.08))
                    .clipShape(Capsule())
                }
                .buttonStyle(EKPressStyle())
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.standard)

            sectionContent(section)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    // MARK: - Index chips

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

    // MARK: - Section card (overview grid card)

    private func sectionCard(_ section: MarketSection) -> some View {
        Button(action: {
            HapticManager.selection()
            withAnimation(.spring(response: 0.38, dampingFraction: 0.84)) { activeSection = section }
        }) {
            HStack(spacing: Theme.Spacing.large) {
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .fill(section.accentColor.opacity(0.12))
                        .frame(width: 48, height: 48)
                    Image(systemName: section.icon)
                        .font(Theme.serialNumberFont(size: 20, relativeTo: .headline))
                        .foregroundStyle(section.accentColor)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(section.hindi)
                        .font(Theme.hindiFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(section.englishTitle)
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(section.description)
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(section.accentColor.opacity(0.5))
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
            .overlay(
                Rectangle()
                    .fill(section.accentColor.opacity(0.8))
                    .frame(width: 3)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)),
                alignment: .leading
            )
        }
        .buttonStyle(EKPressStyle())
    }

// MARK: - Section Shell (fullscreen with back strip)

    @ViewBuilder
    private func sectionShell(_ section: MarketSection) -> some View {
        VStack(spacing: Theme.Spacing.none) {
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
        case .strategy:  StrategyLabScreen()
        case .nl_screener: NLScreenerScreen()
        case .correlation: CorrelationMatrixScreen()
        case .anomalies: MarketAnomalyScreen()
        case .sector_rotation: SectorRotationScreen()
        case .stress_test: StressTestScreen()
        case .earnings_surprise: EarningsSurpriseScreen()
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
