import SwiftUI

// MARK: - Home dashboard sections

// One view per HomeSectionID. HomeScreen owns the state and passes bindings/closures;
// HomeScreen.renderSection(id:) picks the section.

// MARK: - .top

struct HomeTopSection: View {
    @EnvironmentObject var authManager: AuthManager
    @ObservedObject var viewModel: HomeViewModel
    @Binding var morningBriefShownDate: String
    @Binding var showSearch: Bool
    @Binding var searchText: String
    @FocusState.Binding var searchFocused: Bool
    @Binding var showGlossary: Bool
    let dailyAction: DailyActionResponse?
    let onSelectStock: (StockEntry) -> Void

    private var searchResults: [StockEntry] {
        guard !searchText.trimmingCharacters(in: .whitespaces).isEmpty else { return [] }
        return StockDatabase.search(searchText)
    }

    var body: some View {
        // ── Section 1: Header + Daily Action ─────────────
        Group {
            if let user = authManager.currentUser {
                HStack {
                    // Screen D — greeting header: date + "Hi, Name"
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(Date().formatted(.dateTime.weekday(.wide).day().month(.wide)))
                            .font(Theme.officialStampFont(size: 9)).tracking(0.5)
                            .foregroundStyle(Theme.inkTertiary)
                        Text("Hi, \(user.displayName)")
                            .font(.largeTitle.weight(.bold))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                    Spacer()
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
                                    .frame(width: 44, height: 44)
                                    .background(Theme.securityGold.opacity(isDismissedToday ? 0.05 : 0.12))
                                    .clipShape(Circle())
                                    .overlay(Circle().stroke(Theme.securityGold.opacity(isDismissedToday ? 0.1 : 0.3), lineWidth: 0.5))

                                if isDismissedToday {
                                    MorningBriefMoodBadge(mood: viewModel.morningBriefData?.mood, size: 12)
                                        .overlay(Circle().stroke(Theme.canvasDeep, lineWidth: 2))
                                        .offset(x: 2, y: -2)
                                }
                            }
                        }
                        .buttonStyle(EKPressStyle())
                        .accessibilityLabel("Morning brief")
                        .accessibilityValue(MorningBriefMoodBadge.accessibilityValue(mood: viewModel.morningBriefData?.mood, hiddenToday: isDismissedToday))
                    }

                    Button {
                        HapticManager.selection()
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                            showSearch.toggle()
                            if showSearch { searchFocused = true }
                        }
                    } label: {
                        Image(systemName: "magnifyingglass")
                            .font(.title3.weight(.medium))
                            .foregroundStyle(Theme.securityGold)
                            .frame(width: 44, height: 44)
                            .background(Theme.securityGold.opacity(0.12))
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel(showSearch ? "Close search" : "Search stocks")
                    Button {
                        HapticManager.selection()
                        showGlossary = true
                    } label: {
                        Image(systemName: "book.pages")
                            .font(.title3.weight(.medium))
                            .foregroundStyle(Theme.securityGold)
                            .frame(width: 44, height: 44)
                            .background(Theme.securityGold.opacity(0.12))
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel("Glossary")
                    NavigationLink(destination: AlertsScreen()) {
                        Image(systemName: "bell.badge")
                            .font(.title3.weight(.medium))
                            .foregroundStyle(Theme.securityGold)
                            .frame(width: 44, height: 44)
                            .background(Theme.securityGold.opacity(0.12))
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel("Price alerts")
                    NavigationLink(destination: SettingsScreen()) {
                        ZStack {
                            Circle()
                                .fill(Theme.securityGold)
                                .frame(width: 44, height: 44)
                            Text(String(user.displayName.prefix(1)).uppercased())
                                .font(Theme.serialNumberFont(size: 16, relativeTo: .body).weight(.semibold))
                                .foregroundStyle(Theme.canvas)
                        }
                        .overlay(Circle().stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                    }
                    .accessibilityLabel("Profile and settings")
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.standard)
            }

            // Spotlight-style quick search bar
            if showSearch {
                VStack(spacing: Theme.Spacing.none) {
                    HStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: "magnifyingglass")
                            .font(.body.weight(.medium))
                            .foregroundStyle(Theme.securityGold)
                        TextField("Ticker or company name...", text: $searchText)
                            .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                            .focused($searchFocused)
                            .autocapitalization(.allCharacters)
                        if !searchText.isEmpty {
                            Button {
                                HapticManager.selection()
                                searchText = ""
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.body)
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Clear search")
                        }
                        Button {
                            HapticManager.selection()
                            withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                                showSearch = false
                                searchText = ""
                            }
                        } label: {
                            Text("CANCEL")
                                .font(Theme.officialStampFont(size: 10))
                                .tracking(1.0)
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .buttonStyle(EKPressStyle())
                    }
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.canvasDeep)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.securityGold.opacity(0.25), lineWidth: 0.5))
                    .padding(.horizontal, Theme.screenPadding)

                    // Live search results
                    if !searchResults.isEmpty {
                        VStack(spacing: Theme.Spacing.none) {
                            ForEach(searchResults.prefix(8)) { entry in
                                Button {
                                    HapticManager.selection()
                                    onSelectStock(entry)
                                    withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                                        showSearch = false
                                        searchText = ""
                                    }
                                } label: {
                                    HStack(spacing: Theme.Spacing.standard) {
                                        ZStack {
                                            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                                .fill(entry.ticker.tileColor)
                                                .frame(width: 36, height: 36)
                                            Text(String(entry.ticker.prefix(2)))
                                                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption).weight(.bold))
                                                .foregroundStyle(.white)
                                        }
                                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .body))
                                                .foregroundStyle(Theme.inkPrimary)
                                                .lineLimit(1)
                                            Text("\(entry.ticker) · \(entry.sector)")
                                                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                                                .foregroundStyle(Theme.inkSecondary)
                                                .lineLimit(1)
                                        }
                                        Spacer()
                                        Image(systemName: "arrow.up.forward")
                                            .font(.caption.weight(.semibold))
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                    .padding(.horizontal, Theme.Spacing.card)
                                    .padding(.vertical, Theme.Spacing.standard)
                                }
                                .buttonStyle(EKPressStyle())
                                if entry != searchResults.prefix(8).last {
                                    Rectangle()
                                        .fill(Theme.borderFine)
                                        .frame(height: 0.5)
                                        .padding(.horizontal, Theme.Spacing.card)
                                }
                            }
                        }
                        .background(Theme.canvasDeep)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.borderSage, lineWidth: 0.5))
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, Theme.Spacing.medium)
                        .transition(.move(edge: .top).combined(with: .opacity))
                    }
                }
                .transition(.move(edge: .top).combined(with: .opacity))
            }

            MarketStatusStrip()

            if let action = dailyAction {
                DailyActionCard(response: action)
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
        .id(HomeSectionID.top.rawValue)
    }
}

// MARK: - .portfolio

struct HomePortfolioSection: View {
    let valuationHistory: [PortfolioValuationSnapshot]
    @Binding var portfolioRange: TimeRange

    private var rangedValuationHistory: [PortfolioValuationSnapshot] {
        valuationHistory.ranged(portfolioRange)
    }

    var body: some View {
        // ── Section 2: Portfolio ──────────────────────────
        Group {
            if !valuationHistory.isEmpty {
                ImmersivePortfolioHeroChart(snapshots: rangedValuationHistory)
                TimeRangeSelector(selected: $portfolioRange, ranges: TimeRange.allCases)
                GuillocheDivider()
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
        .id(HomeSectionID.portfolio.rawValue)
    }
}

// MARK: - .indices

struct HomeIndicesSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 3: Market Indices ─────────────────────
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(alignment: .center, spacing: Theme.Spacing.medium) {
                SectionHeader(title: "Market Indices", hindiTitle: "बाजार सूचकांक")
                if viewModel.indicesFetchFailed {
                    Text("DELAYED")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.bearRed)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.bearRed, lineWidth: 0.5))
                }
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(viewModel.indices) { index in
                        let valueStr: String = {
                            if index.ticker == "USDINR=X" {
                                return IndianFormatter.price(index.value)
                            } else {
                                return IndianFormatter.points(index.value)
                            }
                        }()
                        let changeStr = (index.changePct >= 0 ? "+" : "") + String(format: "%.2f%%", index.changePct)
                        IndexChip(
                            name: index.name,
                            value: valueStr,
                            change: changeStr,
                            isPositive: index.changePct >= 0
                        )
                        .shimmerPlaceholder(isLoading: viewModel.indicesLoading)
                    }
                    if viewModel.indices.isEmpty && viewModel.indicesLoading {
                        ForEach(0..<4, id: \.self) { _ in
                            IndexChip(name: "——", value: "——", change: "——", isPositive: true)
                                .shimmerPlaceholder(isLoading: true)
                        }
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
            .scrollIndicators(.hidden)
        }
        .id(HomeSectionID.indices.rawValue)
    }
}

// MARK: - .watchlist

struct HomeWatchlistSection: View {
    @ObservedObject var viewModel: HomeViewModel
    let timeframeConflicts: [TimeframeConflict]

    var body: some View {
        // ── Section 4: Watchlist ──────────────────────────
        VStack(spacing: Theme.Spacing.card) {
            SectionHeader(title: "Watchlist", hindiTitle: "बाज़ार की निगरानी", actionLabel: "SEE ALL →") {
                // Switch to Portfolio tab (tab 4) to show full holdings
                NotificationCenter.default.post(
                    name: Notification.Name("switchToTab"),
                    object: nil,
                    userInfo: ["tab": 4]
                )
            }
            if viewModel.watchlist.isEmpty && !viewModel.isLoading {
                VStack(spacing: Theme.Spacing.card) {
                    Image(systemName: "binoculars")
                        .font(.largeTitle.weight(.light))
                        .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                    Text("NO STOCKS ON WATCHLIST")
                        .font(Theme.officialStampFont(size: 11))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    Text("Add stocks from Search to track them here.")
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.xLarge)
                .padding(.horizontal, Theme.screenPadding)
            } else {
                VStack(spacing: Theme.Spacing.standard) {
                    ForEach(viewModel.watchlist) { stock in
                        NavigationLink(value: StockActionHubDest(ticker: stock.ticker, companyName: stock.companyName, exchange: stock.exchange)) {
                            StockRow(stock: stock)
                        }
                        .ekPressHaptic()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
        .id(HomeSectionID.watchlist.rawValue)

        // Timeframe Conflicts Banner (between watchlist + sectors)
        if !timeframeConflicts.isEmpty {
            TimeframeConflictsBanner(conflicts: timeframeConflicts)
        }
    }
}

// MARK: - .sectors

struct HomeSectorsSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 5: Sector Pulse (vertical grid) ──────
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "Sectors today", hindiTitle: "क्षेत्र प्रदर्शन")
            if !viewModel.sectorData.isEmpty {
                let columns = [
                    GridItem(.flexible(), spacing: Theme.Spacing.standard),
                    GridItem(.flexible(), spacing: Theme.Spacing.standard)
                ]
                LazyVGrid(columns: columns, spacing: Theme.Spacing.standard) {
                    ForEach(viewModel.sectorData) { sector in
                        SectorPill(name: sector.name, change: sector.changePct)
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            } else {
                DashboardLoadingCard(label: "Sector Pulse", isLoading: viewModel.isLoading)
            }
        }
        .id(HomeSectionID.sectors.rawValue)
    }
}

// MARK: - .morning

struct HomeMorningSection: View {
    @ObservedObject var viewModel: HomeViewModel
    @Binding var morningBriefShownDate: String

    private var shouldShowBriefToday: Bool {
        return morningBriefShownDate != WireDate.dayKey(Date()) && viewModel.morningBriefData != nil
    }

    var body: some View {
        if shouldShowBriefToday, let briefData = viewModel.morningBriefData {
            VStack(spacing: Theme.Spacing.none) {
                HStack(alignment: .center, spacing: Theme.Spacing.none) {
                    Rectangle()
                        .fill(Theme.securityGold)
                        .frame(width: 3)
                        .frame(maxHeight: .infinity)

                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        HStack(spacing: Theme.Spacing.tight) {
                            Text("MORNING BRIEF")
                                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                .tracking(1.2)
                                .foregroundStyle(Theme.inkSecondary)
                            Text("·").foregroundStyle(Theme.inkTertiary)
                            Text(Date().formatted(.dateTime.day().month(.abbreviated).hour().minute()))
                                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkTertiary)
                        }

                        // FAKE-22: no mood line when the server could not compute one ("unavailable").
                        if ["positive", "negative", "cautious"].contains(briefData.mood) {
                            Text(briefData.mood == "positive" ? "Market mood: POSITIVE" :
                                 briefData.mood == "negative" ? "Market mood: NEGATIVE" : "Market mood: NEUTRAL")
                                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                                .foregroundStyle(Theme.inkPrimary)
                        }

                        Text(briefData.summary)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(4)
                            .lineLimit(3)

                        if let priority = briefData.priorityItems, !priority.isEmpty {
                            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                ForEach(Array(priority.prefix(2))) { item in
                                    HStack(spacing: Theme.Spacing.small) {
                                        Image(systemName: "exclamationmark.triangle")
                                            .font(.caption2)
                                            .foregroundStyle(Theme.inkTertiary)
                                        Text(item.message)
                                            .font(Theme.engravedSerif(size: 11, weight: .medium, relativeTo: .caption))
                                            .foregroundStyle(Theme.inkPrimary)
                                            .lineLimit(1)
                                    }
                                }
                            }
                        }

                        HStack(spacing: Theme.Spacing.standard) {
                            Button {
                                HapticManager.selection()
                                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                    morningBriefShownDate = WireDate.dayKey(Date())
                                }
                            } label: {
                                Text("READ FULL BRIEF")
                                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                    .tracking(1)
                                    .foregroundStyle(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.small)
                                    .background(Theme.securityGold.opacity(0.1))
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                            }
                            .buttonStyle(EKPressStyle())

                            Button {
                                HapticManager.selection()
                                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                    morningBriefShownDate = WireDate.dayKey(Date())
                                }
                            } label: {
                                Text("DISMISS")
                                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                    .tracking(1)
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                    .padding(Theme.Spacing.card)
                }
                .background(Theme.surfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
                .padding(.horizontal, Theme.screenPadding)
            }
            .id(HomeSectionID.morning.rawValue)
        } else if let briefData = viewModel.morningBriefData {
            VStack(spacing: Theme.Spacing.card) {
                MorningDecreeCard(briefData: briefData)
                    .padding(.horizontal, Theme.screenPadding)
            }
            .id(HomeSectionID.morning.rawValue)
        } else {
            VStack(spacing: Theme.Spacing.card) {
                SectionHeader(title: "Morning Brief", hindiTitle: "Morning Summary")
                DashboardLoadingCard(label: "latest brief", isLoading: viewModel.isLoading)
            }
            .id(HomeSectionID.morning.rawValue)
        }
    }
}

// MARK: - .news

struct HomeNewsSection: View {
    @ObservedObject var feedVM: HomeFeedViewModel
    let onOpenTicker: (String) -> Void

    var body: some View {
        // ── Section 6a: NEWS FEED (vertical list) ────────
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeader(title: "Market News", hindiTitle: "ताज़ा समाचार")
                .padding(.horizontal, Theme.screenPadding)

            if let feed = feedVM.feed {
                VStack(spacing: Theme.Spacing.standard) {
                    ForEach(Array((feed.news + feed.redFlagAlerts).prefix(8).enumerated()), id: \.element.id) { _, article in
                        CompactNewsCell(article: article) { ticker in
                            onOpenTicker(ticker)
                        }
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            } else if feedVM.isLoading {
                VStack(spacing: Theme.Spacing.standard) {
                    ForEach(0..<3, id: \.self) { _ in
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                            .fill(Theme.inkTertiary.opacity(0.08))
                            .frame(maxWidth: .infinity)
                            .frame(height: 100)
                            .shimmerPlaceholder(isLoading: true)
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
        .id(HomeSectionID.news.rawValue)
    }
}

// MARK: - .youtube

struct HomeYouTubeSection: View {
    @ObservedObject var feedVM: HomeFeedViewModel
    @Binding var selectedChannel: String?
    let onOpenTicker: (String) -> Void

    var body: some View {
        // ── Section 6c: YOUTUBE FEED ─────────────────────────
        if let feed = feedVM.feed, feed.youtubeVideos.isEmpty {
            // Empty state: harvest is being populated or no quality videos yet
            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                SectionHeader(title: "Expert Videos", hindiTitle: "विशेषज्ञ विश्लेषण")
                HStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "play.rectangle.on.rectangle")
                        .font(.title2.weight(.light))
                        .foregroundStyle(Theme.securityGold.opacity(0.7))
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("Curating SEBI-Registered Channels")
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Only 50k+ view videos from Pranjal Kamra, SOIC Finance, Capitalmind, and other trusted advisors. Refreshes nightly.")
                            .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                            .foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(2)
                    }
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            }
            .id(HomeSectionID.youtube.rawValue)
        } else if let feed = feedVM.feed, !feed.youtubeVideos.isEmpty {
            let allVideos = Array(feed.youtubeVideos.prefix(15))
            // Unique channel names for filter chips
            let channelNames: [String] = Array(
                NSOrderedSet(array: allVideos.map { $0.channelName })
                .array as? [String] ?? []
            )
            // Apply channel filter
            let videos: [YouTubeVideoItem] = {
                if let ch = selectedChannel {
                    return allVideos.filter { $0.channelName == ch }
                }
                return allVideos
            }()

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    SectionHeader(title: "Expert Videos", hindiTitle: "विशेषज्ञ विश्लेषण")
                }
                .padding(.horizontal, Theme.screenPadding)

                // ── Channel filter chip bar ───────────────
                if channelNames.count > 1 {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Theme.Spacing.medium) {
                            // "All" chip
                            Button {
                                HapticManager.selection()
                                selectedChannel = nil
                            } label: {
                                Text("ALL")
                                    .font(Theme.officialStampFont(size: 9))
                                    .tracking(1.0)
                                    .foregroundStyle(selectedChannel == nil ? Theme.canvas : Theme.inkTertiary)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.medium)
                                    .background(selectedChannel == nil ? Theme.securityGold : Theme.inkTertiary.opacity(0.12))
                                    .clipShape(Capsule())
                                    .overlay(Capsule().stroke(selectedChannel == nil ? Theme.securityGold : Theme.inkTertiary.opacity(0.3), lineWidth: 0.5))
                            }
                            .buttonStyle(EKPressStyle())

                            ForEach(channelNames, id: \.self) { channel in
                                Button {
                                    HapticManager.selection()
                                    selectedChannel = channel
                                } label: {
                                    Text(channel.uppercased())
                                        .font(Theme.officialStampFont(size: 9))
                                        .tracking(1.0)
                                        .foregroundStyle(selectedChannel == channel ? Theme.canvas : Theme.inkTertiary)
                                        .padding(.horizontal, Theme.Spacing.standard)
                                        .padding(.vertical, Theme.Spacing.medium)
                                        .background(selectedChannel == channel ? Theme.securityGold : Theme.inkTertiary.opacity(0.12))
                                        .clipShape(Capsule())
                                        .overlay(Capsule().stroke(selectedChannel == channel ? Theme.securityGold : Theme.inkTertiary.opacity(0.3), lineWidth: 0.5))
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.bottom, Theme.Spacing.medium)
                    }
                    .scrollIndicators(.hidden)
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: Theme.Spacing.card) {
                        ForEach(videos) { video in
                            YouTubeCompactCard(video: video) { ticker in
                                onOpenTicker(ticker)
                            }
                            .frame(width: UIScreen.main.bounds.width * 0.62)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
                .scrollIndicators(.hidden)
            }
            .id(HomeSectionID.youtube.rawValue)
        }
    }
}

// MARK: - .earnings

struct HomeEarningsSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 7: Upcoming Results ───────────────────
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeader(title: "This Week's Results", hindiTitle: "आगामी परिणाम")
            let upcoming = viewModel.earningsEvents.filter { $0.daysAway >= 0 && $0.daysAway <= 14 }
            if !upcoming.isEmpty {
                VStack(spacing: Theme.Spacing.medium) {
                    ForEach(upcoming) { event in
                        NavigationLink(value: event.ticker) {
                            HStack {
                                Text(event.ticker)
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundStyle(Theme.inkPrimary)
                                if viewModel.watchlist.contains(where: { $0.ticker == event.ticker }) {
                                    Text("WATCHLIST")
                                        .font(Theme.officialStampFont(size: 7))
                                        .tracking(0.8)
                                        .foregroundStyle(Theme.securityGold)
                                        .padding(.horizontal, Theme.Spacing.small)
                                        .padding(.vertical, Theme.Spacing.xSmall)
                                        .background(Theme.securityGold.opacity(0.12))
                                        .cornerRadius(Theme.CornerRadius.small)
                                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                                }
                                Spacer()
                                Text(event.daysAway == 0 ? "Today" : "In \(event.daysAway) days")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(event.daysAway <= 3 ? Theme.holdAmber : Theme.inkSecondary)
                                Text("· \(event.earningsDate)")
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                Image(systemName: "chevron.right")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        .buttonStyle(.plain)
                        .ekPressHaptic()
                    }
                }
            } else {
                DashboardLoadingCard(label: "Upcoming Results", isLoading: viewModel.isLoading)
            }
        }
        .id(HomeSectionID.earnings.rawValue)
    }
}

// MARK: - .marketPulse

struct HomeMarketPulseSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 8: Market Pulse ───────────────────────
        VStack(spacing: Theme.Spacing.standard) {
            if let pulse = viewModel.dashboard?.pulse {
                MarketPulseDashCard(pulse: pulse)
                if pulse.advances + pulse.declines > 0 {
                    let ratio = Double(pulse.advances) / Double(pulse.advances + pulse.declines)
                    MarketMoodGauge(ratio: ratio)
                }
            } else {
                SectionHeader(title: "Market Pulse", hindiTitle: "बाजार की नब्ज")
                DashboardLoadingCard(label: "dashboard data", isLoading: viewModel.dashboardLoading)
            }
        }
        .id(HomeSectionID.marketPulse.rawValue)
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - .momentum

struct HomeMomentumSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 9: Momentum ───────────────────────────
        VStack(spacing: Theme.Spacing.standard) {
            if let momentum = viewModel.dashboard?.momentum {
                MomentumDashCard(momentum: momentum)
            } else {
                SectionHeader(title: "Momentum Scan", hindiTitle: "गति विश्लेषण")
                DashboardLoadingCard(label: "signal data", isLoading: viewModel.dashboardLoading)
            }
        }
        .id(HomeSectionID.momentum.rawValue)
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - .macroAlt

struct HomeMacroAltSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 10: Macro & Alternatives ─────────────
        VStack(spacing: Theme.Spacing.standard) {
            if let macro = viewModel.dashboard?.macro {
                MacroDashCard(macro: macro)
            } else {
                SectionHeader(title: "Macro & Alternatives", hindiTitle: "वृहद अर्थव्यवस्था")
                DashboardLoadingCard(label: "Macro Data", isLoading: viewModel.dashboardLoading)
            }
        }
        .id(HomeSectionID.macroAlt.rawValue)
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - .institutional

struct HomeInstitutionalSection: View {
    @ObservedObject var viewModel: HomeViewModel

    var body: some View {
        // ── Section 11: Institutional Flow ───────────────
        VStack(spacing: Theme.Spacing.standard) {
            if let inst = viewModel.dashboard?.institutional {
                InstitutionalDashCard(flow: inst)
            } else {
                SectionHeader(title: "Institutional Allocation", hindiTitle: "संस्थागत प्रवाह")
                DashboardLoadingCard(label: "flow data", isLoading: viewModel.dashboardLoading)
            }
        }
        .id(HomeSectionID.institutional.rawValue)
        .padding(.horizontal, Theme.screenPadding)
    }
}
