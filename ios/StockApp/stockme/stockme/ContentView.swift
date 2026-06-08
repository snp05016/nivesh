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
        // Section 10: Central Global State Navigation Shell — 5 primary tabs
        TabView(selection: $selectedTab) {
            // Home View: portfolio metrics, indices, multimedia, advisory briefs
            HomeScreen()
                .tabItem { Label("Home", systemImage: "house.fill") }
                .tag(0)

            // Markets View: index grids, unlisted marketplace, technical scanners
            MarketsView()
                .tabItem { Label("Markets", systemImage: "chart.bar.fill") }
                .tag(1)

            // Ideas View: expert strategy write-ups, technical charts, research
            ExpertNetworkView()
                .tabItem { Label("Ideas", systemImage: "lightbulb.fill") }
                .tag(2)

            // News View: real-time financial newswire
            NewsMultimediaView()
                .tabItem { Label("News", systemImage: "newspaper.fill") }
                .tag(3)

            // Portfolio View: personal wealth ledger, holdings, P&L
            PortfolioScreen()
                .tabItem { Label("Portfolio", systemImage: "briefcase.fill") }
                .tag(4)
        }
        .accentColor(Theme.securityGold)
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
        // Global tab-switch handler — used by HomeScreen "SEE ALL →" and any
        // child view that needs to jump to a top-level tab without a Binding
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("switchToTab"))) { notif in
            if let tab = notif.userInfo?["tab"] as? Int {
                withAnimation(.easeInOut(duration: 0.25)) { selectedTab = tab }
            }
        }
    }
}

// MARK: - Markets View (Section 10: Markets tab hub)
// Houses: Earnings Dashboard, Pre-IPO Marketplace, Technical Momentum, Alerts, Compare, Search

struct MarketsView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var selectedMarketTab: Int = 0

    let marketTabs = ["Earnings", "Unlisted", "Technical", "Screener", "Alerts"]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            VStack(spacing: 0) {
                // Sub-navigation bar within Markets tab
                ScrollView(.horizontal) {
                    HStack(spacing: Theme.Spacing.small) {
                        ForEach(Array(marketTabs.enumerated()), id: \.offset) { idx, name in
                            Button(action: { selectedMarketTab = idx }) {
                                Text(name)
                                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                                    .tracking(1.5)
                                    .fontWeight(selectedMarketTab == idx ? .bold : .regular)
                                    .foregroundStyle(selectedMarketTab == idx ? Theme.securityGold : Theme.inkTertiary)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.medium)
                                    .background(selectedMarketTab == idx ? Theme.securityGold.opacity(0.10) : Color.clear)
                                    .cornerRadius(Theme.CornerRadius.tight)
                            }
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.standard)
                    .padding(.vertical, Theme.Spacing.medium)
                }
                .scrollIndicators(.hidden)
                .background(Theme.canvasDeep)
                .overlay(Divider(), alignment: .bottom)

                marketTabContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }

    @ViewBuilder
    private var marketTabContent: some View {
        switch selectedMarketTab {
        case 0: EarningsDashboardView()
        case 1: PreIPOMarketplaceView()
        case 2: TechnicalMomentumView()
        case 3: SearchScreen()
        case 4: AlertsScreen()
        default: EmptyView()
        }
    }
}
