import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var tutorialManager: TutorialManager
    @State private var selectedTab = 0
    @State private var showLaunch = true

    init() {
        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(Theme.canvasDeep)
        appearance.shadowColor = UIColor(Theme.inkSecondary).withAlphaComponent(0.15)

        let goldColor = UIColor(Theme.securityGold)
        let mutedColor = UIColor(Theme.inkTertiary)
        let smallFont = UIFont.systemFont(ofSize: 9, weight: .medium)

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
                    .offset(y: showLaunch ? 24 : 0)
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

            SearchScreen()
                .tabItem { Label("Directory", systemImage: "magnifyingglass") }
                .tag(1)

            PortfolioScreen()
                .tabItem { Label("Assets", systemImage: "briefcase.fill") }
                .tag(2)

            AlertsScreen()
                .tabItem { Label("Alerts", systemImage: "bell.fill") }
                .tag(3)

            HistoryScreen()
                .tabItem { Label("Archives", systemImage: "doc.text.fill") }
                .tag(4)

            CompareScreen()
                .tabItem { Label("Compare", systemImage: "arrow.left.arrow.right.square.fill") }
                .tag(5)

            SettingsScreen()
                .tabItem { Label("Registry", systemImage: "gearshape.fill") }
                .tag(6)

            TradeJournalScreen(userId: authManager.currentUser?.userId ?? 0)
                .tabItem { Label("Journal", systemImage: "book.pages.fill") }
                .tag(7)
        }
        .accentColor(Theme.securityGold)
        .overlay(
            Group {
                if tutorialManager.isShowingTutorial {
                    TutorialOverlayView()
                        .ignoresSafeArea()
                }
            }
        )
        .onChange(of: tutorialManager.currentStep) { step in
            guard tutorialManager.isShowingTutorial else { return }
            let tab: Int
            switch step {
            case 2, 3:    tab = 0  // Home
            case 4:       tab = 1  // Search/Directory
            case 5, 6, 7: tab = 2  // Portfolio/Assets
            case 8:       tab = 3  // Alerts
            case 9:       tab = 7  // Journal
            default:      tab = 0
            }
            selectedTab = tab
        }
    }
}
