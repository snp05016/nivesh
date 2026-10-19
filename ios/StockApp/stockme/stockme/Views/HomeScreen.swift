import SwiftUI
import Combine
import SafariServices

// MARK: - Emoji Stripper (global fix for AI-generated text)

func stripEmoji(_ text: String) -> String {
    // Use only isEmojiPresentation — isEmoji is true for digits 0-9 (keycap sequences)
    // which would strip all numbers from financial text.
    text.unicodeScalars
        .filter { !$0.properties.isEmojiPresentation }
        .map { String($0) }
        .joined()
        .trimmingCharacters(in: .whitespaces)
}

struct HomeScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var viewModel = HomeViewModel()
    @StateObject private var feedVM = HomeFeedViewModel()
    @State private var timeframeConflicts: [TimeframeConflict] = []
    @State private var dailyAction: DailyActionResponse? = nil
    @State private var scrollTarget: String?
    @State private var navigationPath = NavigationPath()
    @AppStorage("homeSectionOrderData") private var sectionOrderData: Data = Data()
    @State private var showingEditLayout = false

    /// Decoded once per layout change, not on every body evaluation (PERF-24).
    @State private var activeSectionOrder: [HomeSectionID] = HomeSectionID.allCases

    private static func sectionOrder(from sectionOrderData: Data) -> [HomeSectionID] {
        let base: [HomeSectionID]
        if !sectionOrderData.isEmpty, let saved = try? JSONDecoder().decode([HomeSectionID].self, from: sectionOrderData) {
            var merged = saved
            for sec in HomeSectionID.allCases {
                if !merged.contains(sec) { merged.append(sec) }
            }
            base = merged
        } else {
            base = HomeSectionID.allCases
        }
        var seen = Set<HomeSectionID>()
        return base.filter { seen.insert($0).inserted }
    }

    // Item 7: YouTube channel filter
    @State private var selectedChannel: String? = nil

    @State private var valuationHistory: [PortfolioValuationSnapshot] = []
    @State private var valuationLoading = false
    @State private var portfolioRange: TimeRange = .month

    @AppStorage("homeAutoRefreshSeconds") private var homeAutoRefreshSeconds: String = "0"

    // Spotlight-style quick search
    @State private var showSearch: Bool = false
    @State private var searchText: String = ""
    @FocusState private var searchFocused: Bool
    @AppStorage("morningBriefShownDate") private var morningBriefShownDate = ""

    @State private var showGlossary = false

    // Stock tap action sheet (universal)
    @State private var stockTapTicker = ""
    @State private var stockTapCompanyName: String? = nil
    @State private var showStockTapAction = false

    var body: some View {
        NavigationStack(path: $navigationPath) {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                ScrollViewReader { proxy in
                    ScrollView(.vertical, showsIndicators: false) {
                        // Lazy: off-screen sections are built when scrolled to (PERF-24).
                        LazyVStack(spacing: Theme.Spacing.card) {
                            AnalyticsConsentCard()

                            ForEach(activeSectionOrder, id: \.self) { sectionId in
                                renderSection(id: sectionId)
                            }


                            Button(action: { HapticManager.selection(); showingEditLayout = true }) {
                                HStack(spacing: Theme.Spacing.medium) {
                                    Image(systemName: "slider.horizontal.3")
                                    Text("CUSTOMIZE LAYOUT")
                                        .font(Theme.officialStampFont(size: 11))
                                }
                                .foregroundStyle(Theme.inkPrimary)
                                .padding()
                                .frame(maxWidth: .infinity)
                                .background(Theme.canvasDeep)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSage, lineWidth: 1))
                            }
                            .padding(.horizontal, Theme.screenPadding)

                            Spacer(minLength: 100)
                        }
                        .frame(maxWidth: UIScreen.main.bounds.width)
                    }
                    .refreshable {
                        HapticManager.impact(.medium)
                        if let user = authManager.currentUser {
                            await viewModel.fetchData(userId: user.userId)
                            await viewModel.fetchIndices()
                            viewModel.fetchSectors()
                            feedVM.fetch(userId: user.userId, forceRefresh: true)
                        }
                        HapticManager.success()
                    }
                    .onChange(of: scrollTarget) {
                        guard let id = scrollTarget else { return }
                        withAnimation(.spring(response: 0.45, dampingFraction: 0.82, blendDuration: 0)) {
                            proxy.scrollTo(id, anchor: .top)
                        }
                        scrollTarget = nil
                    }
                    .safeAreaInset(edge: .bottom) {
                        Color.clear.frame(height: 90)
                    }
                }
            }
            .navigationDestination(for: String.self) { ticker in
                AnalysisScreen(ticker: ticker)
            }
            .navigationDestination(for: StockProfileDest.self) { dest in
                StockProfileView(ticker: dest.ticker, exchange: dest.exchange)
            }
            .navigationDestination(for: StockActionHubDest.self) { dest in
                StockActionHubView(dest: dest, path: $navigationPath)
            }
            .navigationDestination(for: AnalysisDest.self) { dest in
                AnalysisScreen(ticker: dest.ticker, launchMode: dest.mode)
            }
            // Auto-refresh loop: restarts only when the setting changes, not on every re-render.
            .task(id: homeAutoRefreshSeconds) {
                guard let seconds = Double(homeAutoRefreshSeconds), seconds > 0 else { return }
                while !Task.isCancelled {
                    try? await Task.sleep(for: .seconds(seconds))
                    guard !Task.isCancelled, let user = authManager.currentUser else { continue }
                    await viewModel.fetchData(userId: user.userId)
                    await viewModel.fetchIndices()
                    viewModel.fetchSectors()
                    feedVM.fetch(userId: user.userId, forceRefresh: true)
                }
            }
            // Deep link / push tap: pop to root and open the stock's action hub.
            // receive(on:) delivers asynchronously, so clearing the value here is not re-entrant.
            .onReceive(DeepLinkRouter.shared.$pendingTicker.compactMap { $0 }.receive(on: DispatchQueue.main)) { ticker in
                DeepLinkRouter.shared.pendingTicker = nil
                navigationPath = NavigationPath()
                navigationPath.append(StockActionHubDest(ticker: ticker))
            }
            .onReceive(NotificationCenter.default.publisher(for: .watchlistUpdated)) { _ in
                guard let user = authManager.currentUser else { return }
                Task {
                    do {
                        try await viewModel.fetchWatchlist(userId: user.userId)
                    } catch {
                        print("Home watchlist refresh error: \(error)")
                    }
                }
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if viewModel.morningBriefData != nil {
                        let isDismissedToday = morningBriefShownDate == WireDate.dayKey(Date())
                        Button {
                            HapticManager.selection()
                            if isDismissedToday {
                                morningBriefShownDate = ""
                            }
                        } label: {
                            ZStack(alignment: .topTrailing) {
                                Image(systemName: "newspaper")
                                    .font(.title3.weight(.medium))
                                    .foregroundStyle(isDismissedToday ? Theme.inkTertiary : Theme.securityGold)
                                    .frame(width: 28, height: 28)

                                if isDismissedToday {
                                    MorningBriefMoodBadge(mood: viewModel.morningBriefData?.mood, size: 9)
                                        .offset(x: 4, y: -4)
                                }
                            }
                            .minTapTarget()
                        }
                        .buttonStyle(EKPressStyle())
                        .accessibilityLabel("Morning brief")
                        .accessibilityValue(MorningBriefMoodBadge.accessibilityValue(mood: viewModel.morningBriefData?.mood, hiddenToday: isDismissedToday))
                    }
                }
            }
            .toolbarBackground(Theme.canvasDeep, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .navigationBarTitleDisplayMode(.inline)
        }
        .crashGuard("HomeScreen")

        .sheet(isPresented: $showingEditLayout) {
            HomeLayoutEditorSheet(activeOrder: activeSectionOrder) { newOrder in
                if let data = try? JSONEncoder().encode(newOrder) {
                    sectionOrderData = data
                }
            }
        }
        .sheet(isPresented: $showGlossary) {
            NavigationStack {
                GlossaryBrowserView()
            }
        }
        .onChange(of: showStockTapAction) { _, show in
            if show {
                navigationPath.append(StockActionHubDest(ticker: stockTapTicker, companyName: stockTapCompanyName, exchange: "NSE"))
                showStockTapAction = false
            }
        }
        .task {
            // Market-wide fetches; run alongside the user-keyed task below.
            viewModel.fetchSectors()
            viewModel.fetchEarnings()
            viewModel.fetchDashboard()
            viewModel.startIndicesTimer()
            await viewModel.fetchIndices()
        }
        // Single user-data entry point. Keyed on userId so it re-runs when the signed-in
        // account changes (login, logout, switch); guards keep revisits cheap.
        .task(id: authManager.currentUser?.userId) {
            guard let uid = authManager.currentUser?.userId else { return }
            if viewModel.stockCount == 0 && !viewModel.isLoading {
                await viewModel.fetchData(userId: uid)
            }
            feedVM.fetch(userId: uid)
            // Retry indices after portfolio loads — backend may need warmup on cold start
            if viewModel.indicesFetchFailed || viewModel.indices.isEmpty {
                await viewModel.fetchIndices()
            }
            if timeframeConflicts.isEmpty,
               let resp = try? await NetworkManager.shared.fetchTimeframeConflicts(userId: uid) {
                timeframeConflicts = resp.conflicts
            }
            if dailyAction == nil {
                dailyAction = await NetworkManager.shared.fetchDailyAction(userId: uid)
            }
            // Portfolio valuation history for the immersive hero chart
            if valuationHistory.isEmpty {
                valuationLoading = true
                if let data = try? await HomeFeedService.shared.fetchValuationHistory(userId: uid, days: 365) {
                    valuationHistory = data.snapshots.sorted { $0.parsedDate < $1.parsedDate }
                }
                valuationLoading = false
            }
        }
        .onAppear {
            activeSectionOrder = Self.sectionOrder(from: sectionOrderData)
        }
        .onChange(of: sectionOrderData) { _, data in
            activeSectionOrder = Self.sectionOrder(from: data)
        }
        .onDisappear {
            viewModel.stopIndicesTimer()
        }
    }
}

// MARK: - HomeScreen renderSection

extension HomeScreen {
    /// One section view per HomeSectionID (Views/Home/HomeSectionViews.swift); state stays here.
    @ViewBuilder
    func renderSection(id: HomeSectionID) -> some View {
        switch id {
        case .top:
            HomeTopSection(
                viewModel: viewModel,
                morningBriefShownDate: $morningBriefShownDate,
                showSearch: $showSearch,
                searchText: $searchText,
                searchFocused: $searchFocused,
                showGlossary: $showGlossary,
                dailyAction: dailyAction
            ) { entry in
                stockTapTicker = entry.ticker
                stockTapCompanyName = entry.companyName
                showStockTapAction = true
            }
        case .portfolio:
            HomePortfolioSection(valuationHistory: valuationHistory, portfolioRange: $portfolioRange)
        case .indices:
            HomeIndicesSection(viewModel: viewModel)
        case .watchlist:
            HomeWatchlistSection(viewModel: viewModel, timeframeConflicts: timeframeConflicts)
        case .sectors:
            HomeSectorsSection(viewModel: viewModel)
        case .morning:
            HomeMorningSection(viewModel: viewModel, morningBriefShownDate: $morningBriefShownDate)
        case .news:
            HomeNewsSection(feedVM: feedVM) { ticker in navigationPath.append(ticker) }
        case .youtube:
            HomeYouTubeSection(feedVM: feedVM, selectedChannel: $selectedChannel) { ticker in navigationPath.append(ticker) }
        case .earnings:
            HomeEarningsSection(viewModel: viewModel)
        case .marketPulse:
            HomeMarketPulseSection(viewModel: viewModel)
        case .momentum:
            HomeMomentumSection(viewModel: viewModel)
        case .macroAlt:
            HomeMacroAltSection(viewModel: viewModel)
        case .institutional:
            HomeInstitutionalSection(viewModel: viewModel)
        }
    }
}

// MARK: - Section 15: SwiftUI Preview Environment

#Preview("HomeScreen") {
    HomeScreen()
        .environmentObject(AuthManager())
        .environmentObject(LocalReportManager())
}
