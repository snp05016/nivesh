import SwiftUI
import Combine
import Charts
import UIKit

private struct HoldingNavValue: Hashable {
    let ticker: String
    let userNote: String?
    let purchaseDateStr: String?
    let holding: PortfolioHolding?
    func hash(into hasher: inout Hasher) { hasher.combine(ticker) }
    static func == (l: Self, r: Self) -> Bool { l.ticker == r.ticker }
}

struct PortfolioScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager
    @StateObject private var viewModel = PortfolioScreenViewModel()
    @StateObject private var corporateActions = CorporateActionsViewModel()
    @State private var showCorporateActions = false
    @State private var selectedTab = 0
    @State private var showAddWatchlistSheet = false
    @State private var addSheetSearchText = ""
    @State private var showAddedBanner = false
    @State private var addedBannerTicker = ""
    @State private var showAddHoldingSheet = false
    @State private var showEditHoldingSheet = false
    @State private var editingHolding: PortfolioHolding? = nil
    @State private var showDeleteAlert = false
    @State private var deletingTicker = ""
    @State private var holdingActionError: String? = nil
    @State private var watchlistAddError: String? = nil
    @State private var showNoteEditor = false
    @State private var noteEditingHolding: PortfolioHolding? = nil
    @State private var noteEditorText = ""
    @State private var showExportOptions = false
    @State private var exportedFileURL: URL? = nil
    @State private var showShareSheet = false
    @State private var signalWarnings: [String: SignalWarning] = [:]
    @State private var moneyReloadKey = 0
    @State private var riskAnalysis: RiskAnalysis? = nil
    @State private var redFlags: RedFlagsResponse? = nil

        @State private var showBriefSheet = false

@StateObject private var tagsManager = WatchlistTagsManager()
    @State private var activeWatchlistTag: String? = nil
    @State private var showTagSheet = false
    @State private var taggingTicker = ""

    // Stock tap action sheet (universal)
    @State private var stockTapTicker = ""
    @State private var stockTapCompanyName: String? = nil
    @State private var showStockTapAction = false
    @State private var portfolioNavPath = NavigationPath()
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false

    // Screen B — immersive valuation chart (fetched at view level; ViewModel untouched)
    @State private var snapshots: [PortfolioValuationSnapshot] = []
    @State private var selectedRange: TimeRange = .year

    /// Snapshots filtered to the selected time range (date-based slice of the 730-day series).
    private var rangedSnapshots: [PortfolioValuationSnapshot] {
        snapshots.ranged(selectedRange)
    }

    var body: some View {
        NavigationStack(path: $portfolioNavPath) {
            ZStack {
                DenominationBackground(denomination: .twoThousand)

                VStack(spacing: Theme.Spacing.none) {
                    // Bilingual header
                    HStack {
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("निवेश पोर्टफोलियो")
                                .font(Theme.hindiFont(size: 11, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary)
                            Text("MY PORTFOLIO")
                                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .largeTitle))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        Spacer()
                        HStack(spacing: Theme.Spacing.standard) {
                            Button { HapticManager.selection();  showExportOptions = true } label: {
                                Image(systemName: "square.and.arrow.up")
                                    .foregroundStyle(Theme.inkSecondary)
                                    .padding(Theme.Spacing.medium)
                            }
                            .accessibilityLabel("Export portfolio")
                            Button { HapticManager.selection(); showBriefSheet = true } label: {
                                Image(systemName: "message")
                                    .foregroundStyle(Theme.inkSecondary)
                                    .padding(Theme.Spacing.medium)
                            }
                            .buttonStyle(EKPressStyle())
                            .accessibilityLabel("Portfolio brief")
                            Button { HapticManager.selection(); showAddHoldingSheet = true } label: {
                                ZStack {
                                    Circle().stroke(Theme.borderSage, lineWidth: 0.5).frame(width: 44, height: 44)
                                    Image(systemName: "plus.circle").font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline)).foregroundStyle(Theme.inkPrimary)
                                }
                            }
                            .buttonStyle(EKPressStyle())
                            .accessibilityLabel("Add transaction")
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.standard)
                    .padding(.bottom, Theme.screenPadding)

                    ScrollView {
                        VStack(spacing: Theme.sectionSpacing) {
                            if let loadError = viewModel.loadError {
                                BanknoteErrorCanvas(
                                    title: viewModel.hasLoaded ? "Couldn't refresh your portfolio" : "Couldn't load your portfolio",
                                    detail: loadError,
                                    retryAction: {
                                        if let uid = authManager.currentUser?.userId { await viewModel.fetchData(userId: uid) }
                                    }
                                )
                            }

                            // Screen B — hero value block (price + two pills + brand chip).
                            // Hidden after a failed first load: unknown is not Rs 0.
                            if viewModel.hasLoaded || viewModel.loadError == nil {
                                PortfolioHeroBlock(
                                    value: viewModel.totalValue,
                                    totalPnL: viewModel.totalValue - viewModel.investedValue,
                                    totalPnLPercent: viewModel.investedValue > 0
                                        ? (viewModel.totalValue - viewModel.investedValue) / viewModel.investedValue * 100
                                        : 0,
                                    isLoading: viewModel.isLoading,
                                    hideValues: hidePortfolioValues
                                )
                                .padding(.horizontal, Theme.screenPadding)
                            }

                            // Money rows (flag-gated, spec_money 2.6): portfolio return card, later imports/X-ray/tax.
                            if let user = authManager.currentUser {
                                PortfolioMoneySection(userId: user.userId, reloadKey: moneyReloadKey)
                                    .padding(.horizontal, Theme.screenPadding)
                                    // Every holdings reload (first load, trade saved or deleted, pull to refresh) ends here.
                                    .onChange(of: viewModel.isLoading) { _, loading in
                                        if !loading { moneyReloadKey += 1 }
                                    }
                            }

                            // Screen B — full-bleed immersive valuation chart + underline selector
                            if !rangedSnapshots.isEmpty {
                                VStack(spacing: Theme.Spacing.none) {
                                    ImmersivePortfolioHeroChart(snapshots: rangedSnapshots, showValueHeader: false)
                                    TimeRangeSelector(selected: $selectedRange,
                                                      ranges: [.day, .week, .month, .threeMonths, .sixMonths, .year, .all])
                                        .padding(.horizontal, Theme.screenPadding)
                                        .padding(.top, Theme.Spacing.standard)
                                }
                            }

                            // Screen B — allocation donut
                            if !viewModel.holdings.isEmpty {
                                PortfolioAllocationDonutCard(holdings: viewModel.holdings)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            PortfolioRiskCard(riskAnalysis: riskAnalysis)
                                .padding(.horizontal, Theme.screenPadding)

                            RedFlagsSection(redFlags: redFlags, onTickerTap: { ticker in
                                stockTapTicker = ticker
                                stockTapCompanyName = nil
                                showStockTapAction = true
                            })
                                .padding(.horizontal, Theme.screenPadding)

                            if let user = authManager.currentUser {
                                ValuationCalendarView(userId: user.userId)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            if let user = authManager.currentUser {
                                PortfolioChartsStrip(userId: user.userId)
                                    .padding(.horizontal, Theme.screenPadding)
                                PortfolioToolsCard(userId: user.userId)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            HStack(spacing: Theme.Spacing.none) {
                                TabNoteButton(title: "Holdings", isSelected: selectedTab == 0) { selectedTab = 0 }
                                TabNoteButton(title: "Watchlist", isSelected: selectedTab == 1) { selectedTab = 1 }
                                TabNoteButton(title: "Journal", isSelected: selectedTab == 2) { selectedTab = 2 }
                                TabNoteButton(title: "Inbox", isSelected: selectedTab == 3) { selectedTab = 3 }
                            }
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)

                            if selectedTab == 0 && !corporateActions.isHidden && corporateActions.pendingCount > 0 {
                                CorporateActionsBanner(count: corporateActions.pendingCount) { showCorporateActions = true }
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            if selectedTab == 0 && viewModel.holdings.isEmpty && viewModel.loadError != nil {
                                // The error card above explains it; don't invite adding a "first" holding.
                                EmptyView()
                            } else if selectedTab == 0 && viewModel.holdings.isEmpty && !viewModel.isLoading {
                                EmptyHoldingsView { HapticManager.selection(); showAddHoldingSheet = true }
                                    .padding(.horizontal, Theme.screenPadding)
                            } else if selectedTab == 0 {
                                // Screen B — holdings in a single banknote card, 0.5pt separators
                                VStack(spacing: Theme.Spacing.none) {
                                    ForEach(Array(viewModel.holdings.enumerated()), id: \.element.id) { idx, holding in
                                        NavigationLink(value: HoldingNavValue(ticker: holding.stock.ticker, userNote: holding.notes, purchaseDateStr: holding.purchaseDate, holding: holding)) {
                                            HoldingNoteRow(holding: holding,
                                                           color: allocationPalette[idx % allocationPalette.count],
                                                           signalWarning: signalWarnings[holding.stock.ticker],
                                                           hideValues: hidePortfolioValues)
                                        }
                                        .ekPress()
                                        .contextMenu {
                                            Button("Edit Holding") { HapticManager.selection()
                                                editingHolding = holding
                                                showEditHoldingSheet = true
                                            }
                                            Button("Add Note") { HapticManager.selection()
                                                noteEditingHolding = holding
                                                noteEditorText = holding.notes ?? ""
                                                showNoteEditor = true
                                            }
                                            Button("Remove from Portfolio", role: .destructive) { HapticManager.selection()
                                                deletingTicker = holding.stock.ticker
                                                showDeleteAlert = true
                                            }
                                        }
                                        .accessibilityAction(named: "Edit holding") {
                                            editingHolding = holding
                                            showEditHoldingSheet = true
                                        }
                                        .accessibilityAction(named: "Remove from portfolio") {
                                            deletingTicker = holding.stock.ticker
                                            showDeleteAlert = true
                                        }
                                        if idx != viewModel.holdings.count - 1 {
                                            GuillocheDivider()
                                                .padding(.horizontal, Theme.Spacing.card)
                                        }
                                    }
                                }
                                .banknoteCard()
                                .padding(.horizontal, Theme.screenPadding)
                            } else if selectedTab == 1 {
                                watchlistTabContent
                            } else if selectedTab == 2 {
                                if let user = authManager.currentUser {
                                    TradeJournalScreen(userId: user.userId)
                                        .padding(.horizontal, Theme.screenPadding)
                                }
                            } else if selectedTab == 3 {
                                NotificationInboxView()
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            Spacer(minLength: 100)
                        }
                    }
                    .refreshable {
                        HapticManager.impact(.medium)
                        if let user = authManager.currentUser {
                            let uid = user.userId
                            // .task(id:) guards these loads so tab revisits stay cheap;
                            // pull-to-refresh is their only reload path, so force them here.
                            async let risk = try? NetworkManager.shared.fetchRiskAnalysis(userId: uid)
                            async let flags = try? NetworkManager.shared.fetchRedFlags(userId: uid)
                            async let history = try? NetworkManager.shared.fetchValuationHistory(userId: uid, days: 730)
                            await viewModel.fetchData(userId: uid)
                            await corporateActions.load()
                            await viewModel.fetchWatchlist(userId: uid)
                            let ws = await NetworkManager.shared.getSignalWarnings(userId: uid)
                            signalWarnings = Dictionary(ws.map { ($0.ticker, $0) }, uniquingKeysWith: { _, last in last })
                            // Keep the last good value if a refresh call fails.
                            if let r = await risk { riskAnalysis = r }
                            if let f = await flags { redFlags = f }
                            if let resp = await history { snapshots = resp.snapshots }
                        }
                        HapticManager.success()
                    }
                }

                // Added-to-watchlist banner
                if showAddedBanner {
                    VStack {
                        HStack(spacing: Theme.Spacing.medium) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(Theme.bullGreen)
                            Text("\(addedBannerTicker) added to watchlist")
                                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.vertical, Theme.Spacing.standard)
                        .background(Theme.canvas)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                        .shadow(color: .black.opacity(0.12), radius: Theme.Spacing.medium, x: 0, y: Theme.Spacing.small)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.bullGreen.opacity(0.4), lineWidth: 1))
                        .padding(.top, Theme.screenPadding * 3)
                        Spacer()
                    }
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .zIndex(10)
                    .animation(.spring(response: 0.4), value: showAddedBanner)
                }

                // FAB — always on the left, same horizontal position for all tabs
                if selectedTab == 0 || selectedTab == 1 {
                    VStack {
                        Spacer()
                        HStack {
                            addPortfolioButton
                            Spacer()
                        }
                        .padding(.leading, Theme.screenPadding + Theme.Spacing.standard)
                        .padding(.bottom, Theme.Spacing.standard)
                    }
                }
            }
        }
        .navigationDestination(for: HoldingNavValue.self) { val in
            // C11: the free "My position" page; flag off keeps today's analysis screen.
            if FeatureFlags.shared.isOn(.moneyHoldingDetail) {
                HoldingDetailView(ticker: val.ticker, seed: val.holding, portfolio: viewModel)
            } else {
                AnalysisScreen(ticker: val.ticker, userNote: val.userNote, purchaseDateStr: val.purchaseDateStr, portfolioHolding: val.holding)
            }
        }
        .navigationDestination(for: String.self) { ticker in
            AnalysisScreen(ticker: ticker)
        }
        .navigationDestination(for: StockProfileDest.self) { dest in
            StockProfileView(ticker: dest.ticker, exchange: dest.exchange)
        }
        .navigationDestination(for: StockActionHubDest.self) { dest in
            StockActionHubView(dest: dest, path: $portfolioNavPath)
        }
        .navigationDestination(for: AnalysisDest.self) { dest in
            AnalysisScreen(ticker: dest.ticker, launchMode: dest.mode)
        }
        .onChange(of: showStockTapAction) { _, show in
            if show {
                portfolioNavPath.append(StockActionHubDest(ticker: stockTapTicker, companyName: stockTapCompanyName, exchange: "NSE"))
                showStockTapAction = false
            }
        }
        // Structured, cancellable loads; guards stop tab revisits from re-issuing calls
        // (pull-to-refresh still forces a reload).
        .task(id: authManager.currentUser?.userId) {
            guard let uid = authManager.currentUser?.userId else { return }
            await withTaskGroup(of: Void.self) { group in
                if viewModel.holdings.isEmpty && !viewModel.isLoading {
                    group.addTask { @MainActor in await viewModel.fetchData(userId: uid) }
                }
                if viewModel.watchlistItems.isEmpty && !viewModel.watchlistLoading {
                    group.addTask { @MainActor in await viewModel.fetchWatchlist(userId: uid) }
                }
                if signalWarnings.isEmpty {
                    group.addTask { @MainActor in
                        let ws = await NetworkManager.shared.getSignalWarnings(userId: uid)
                        signalWarnings = Dictionary(ws.map { ($0.ticker, $0) }, uniquingKeysWith: { _, last in last })
                    }
                }
                if riskAnalysis == nil {
                    group.addTask { @MainActor in
                        riskAnalysis = try? await NetworkManager.shared.fetchRiskAnalysis(userId: uid)
                        redFlags = try? await NetworkManager.shared.fetchRedFlags(userId: uid)
                    }
                }
                if snapshots.isEmpty {
                    group.addTask { @MainActor in
                        if let resp = try? await NetworkManager.shared.fetchValuationHistory(userId: uid, days: 730) {
                            snapshots = resp.snapshots
                        }
                    }
                }
            }
        }
        .task(id: authManager.currentUser?.userId) {
            guard let uid = authManager.currentUser?.userId else { return }
            // A decision that changed a holding reloads the holdings, like pull-to-refresh.
            corporateActions.onHoldingsChanged = {
                Task { await viewModel.fetchData(userId: uid) }
            }
            await corporateActions.load()
        }
        .sheet(isPresented: $showCorporateActions) {
            CorporateActionsReviewSheet(vm: corporateActions)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showAddWatchlistSheet) {
            AddWatchlistSheet(
                searchText: $addSheetSearchText,
                onAdd: { entry in
                    guard let user = authManager.currentUser else { return }
                    Task {
                        var added = false
                        do {
                            added = try await NetworkManager.shared.addToWatchlist(
                                userId: user.userId,
                                ticker: entry.ticker,
                                exchange: entry.exchange,
                                companyName: entry.companyName
                            )
                        } catch {
                            // 402 = plan's watchlist cap reached: show the upsell, not a silent close.
                            watchlistAddError = (error as? NetworkError)?.upgradeMessage
                                ?? "\(entry.ticker) wasn't added. Check your connection and try again."
                        }
                        showAddWatchlistSheet = false
                        await viewModel.fetchWatchlist(userId: user.userId)
                        if added {
                            NotificationCenter.default.post(name: .watchlistUpdated, object: nil)
                            addedBannerTicker = entry.ticker
                            withAnimation { showAddedBanner = true }
                            A11y.announce("\(entry.ticker) added to watchlist")
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                            withAnimation { showAddedBanner = false }
                        }
                    }
                }
            )
        }
        .sheet(isPresented: $showAddHoldingSheet) {
            AddHoldingSheet(viewModel: viewModel, authManager: authManager)
        }
        .sheet(item: $editingHolding) { holding in
            EditHoldingSheet(holding: holding, viewModel: viewModel, authManager: authManager)
        }
        .sheet(isPresented: $showNoteEditor) {
            if let holding = noteEditingHolding {
                NoteEditorSheet(holding: holding, noteText: $noteEditorText) { savedNote in
                    if let user = authManager.currentUser {
                        Task {
                            do {
                                try await NetworkManager.shared.saveNote(userId: user.userId, ticker: holding.stock.ticker, note: savedNote)
                            } catch {
                                holdingActionError = "Your note for \(holding.stock.ticker) wasn't saved. \(error.localizedDescription)"
                            }
                            await viewModel.fetchData(userId: user.userId)
                        }
                    }
                }
            }
        }
        .banknoteDialog(
            "Remove \(deletingTicker)?",
            isPresented: $showDeleteAlert,
            message: "This will permanently remove \(deletingTicker) from your portfolio.",
            buttons: [
                .init("Remove", role: .destructive) {
                    if let user = authManager.currentUser {
                        let ticker = deletingTicker
                        Task {
                            do {
                                try await viewModel.removeHolding(ticker: ticker, userId: user.userId)
                            } catch {
                                holdingActionError = "\(ticker) is still in your portfolio. Check your connection and try again."
                            }
                        }
                    }
                },
                .cancel()
            ]
        )
        .sheet(isPresented: $showTagSheet) {
            TaggingSheet(ticker: taggingTicker, tagsManager: tagsManager)
        }
        .banknoteDialog(
            "Couldn't remove stock",
            isPresented: Binding(get: { viewModel.watchlistError != nil }, set: { if !$0 { viewModel.watchlistError = nil } }),
            message: viewModel.watchlistError,
            buttons: [.init("OK")]
        )
        .banknoteDialog(
            "Action failed",
            isPresented: Binding(get: { holdingActionError != nil }, set: { if !$0 { holdingActionError = nil } }),
            message: holdingActionError,
            buttons: [.init("OK")]
        )
        .banknoteDialog(
            "Couldn't add to watchlist",
            isPresented: Binding(get: { watchlistAddError != nil }, set: { if !$0 { watchlistAddError = nil } }),
            message: watchlistAddError,
            buttons: [.init("OK")]
        )
        .banknoteDialog(
            "Export Portfolio",
            isPresented: $showExportOptions,
            // Fix 3.21: only offer export when the portfolio has holdings
            message: viewModel.holdings.isEmpty ? "No holdings to export." : nil,
            buttons: exportDialogButtons
        )
        .sheet(isPresented: $showShareSheet) {
            if let url = exportedFileURL {
                ShareSheet(items: [url])
            }
        }
        .sheet(isPresented: $showBriefSheet) {
            PortfolioBriefSheet(
                portfolioValue: viewModel.totalValue,
                pnl: viewModel.totalValue - viewModel.investedValue,
                holdings: viewModel.holdings
            )
        }
    }

    private var exportDialogButtons: [BanknoteDialogButton] {
        var buttons: [BanknoteDialogButton] = []
        if viewModel.holdings.count > 0 {
            buttons.append(.init("Export as Excel (.xlsx)") {
                if let user = authManager.currentUser {
                    Task { await exportAsExcel(userId: user.userId) }
                }
            })
        }
        buttons.append(.cancel())
        return buttons
    }

    private func exportAsExcel(userId: Int) async {
        do {
            let data = try await NetworkManager.shared.exportPortfolioExcel(userId: userId)
            let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("nivesh_portfolio.xlsx")
            try data.write(to: tempURL)
            exportedFileURL = tempURL
            showShareSheet = true
        } catch {
            holdingActionError = "Couldn't export your portfolio. \(error.localizedDescription)"
        }
    }

    private var addPortfolioButton: some View {
        Button {
            HapticManager.selection()
            if selectedTab == 0 {
                showAddHoldingSheet = true
            } else {
                addSheetSearchText = ""
                showAddWatchlistSheet = true
            }
        } label: {
            ZStack {
                Circle()
                    .fill(Theme.securityGold)
                    .frame(
                        width: Theme.Spacing.xLarge + Theme.Spacing.large,
                        height: Theme.Spacing.xLarge + Theme.Spacing.large
                    )
                    .shadow(color: Theme.securityGold.opacity(0.3), radius: Theme.Spacing.medium, x: 0, y: Theme.Spacing.tight)
                Image(systemName: "plus")
                    .font(.title2.weight(.bold))
                    .foregroundStyle(Theme.canvas)
            }
        }
        .buttonStyle(EKPressStyle())
        .accessibilityLabel(selectedTab == 0 ? "Add holding" : "Add to watchlist")
    }

    // Watchlist "+" — built from scratch to be an exact mirror image of the AI
    @ViewBuilder
    private var watchlistTabContent: some View {
        if viewModel.watchlistLoading {
            VStack(spacing: Theme.Spacing.standard) {
                ForEach(0..<3, id: \.self) { _ in
                    WatchlistSkeletonRow()
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        } else if viewModel.watchlistItems.isEmpty, let loadError = viewModel.watchlistLoadError {
            BanknoteErrorCanvas(title: "Couldn't load your watchlist", detail: loadError, retryAction: {
                if let uid = authManager.currentUser?.userId { await viewModel.fetchWatchlist(userId: uid) }
            })
        } else if viewModel.watchlistItems.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                BanknoteSignalBadge(text: "EMPTY", color: Theme.inkSecondary.opacity(0.4))
                Text("Add stocks to your watchlist to track them here")
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Spacing.xLarge)
                Button {
                    HapticManager.selection()
                    addSheetSearchText = ""
                    showAddWatchlistSheet = true
                } label: {
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: "plus.circle")
                        Text("ADD STOCK")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    }
                    .foregroundStyle(Theme.securityGold)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.vertical, Theme.Spacing.medium)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.securityGold, lineWidth: 1))
                }
            }
            .padding(.top, Theme.screenPadding * 2)
        } else {
            VStack(spacing: Theme.Spacing.standard) {
                // Filter Chips
                let allTags = tagsManager.allUniqueTags
                if !allTags.isEmpty {
                    ScrollView(.horizontal) {
                        HStack(spacing: Theme.Spacing.medium) {
                            ForEach(allTags, id: \.self) { tag in
                                Button {
                                    HapticManager.selection()
                                    activeWatchlistTag = activeWatchlistTag == tag ? nil : tag
                                } label: {
                                    Text(tag.uppercased())
                                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                        .foregroundStyle(activeWatchlistTag == tag ? Theme.canvasDeep : Theme.inkPrimary)
                                        .padding(.horizontal, Theme.Spacing.standard)
                                        .padding(.vertical, Theme.Spacing.tight)
                                        .background(Capsule().fill(activeWatchlistTag == tag ? Theme.securityGold : Theme.canvasDeep))
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                    }
                    .scrollIndicators(.hidden)
                }

                let filteredWatchlist = activeWatchlistTag == nil 
                    ? viewModel.watchlistItems 
                    : viewModel.watchlistItems.filter { tagsManager.tags[$0.ticker]?.contains(activeWatchlistTag!) == true }

                if filteredWatchlist.isEmpty && activeWatchlistTag != nil {
                    VStack {
                        Text("No stocks found with tag '\(activeWatchlistTag!)'")
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                            .padding(.top, Theme.screenPadding)
                    }
                }

                ForEach(filteredWatchlist) { item in
                    Button {
                        HapticManager.selection()
                        stockTapTicker = item.ticker
                        stockTapCompanyName = item.companyName
                        showStockTapAction = true
                    } label: {
                        WatchlistRowView(item: item, tags: tagsManager.tags[item.ticker] ?? [])
                    }
                    .buttonStyle(.plain)
                    // swipeActions only work inside a List; this tab is a plain stack, so long-press it is.
                    .contextMenu {
                        Button("Tag") { HapticManager.selection()
                            taggingTicker = item.ticker
                            showTagSheet = true
                        }
                        Button("Remove from Watchlist", role: .destructive) { HapticManager.selection()
                            guard let user = authManager.currentUser else { return }
                            Task { await viewModel.removeFromWatchlist(ticker: item.ticker, userId: user.userId) }
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
    }
}

struct ShareSheet: UIViewControllerRepresentable {
            let items: [Any]
            func makeUIViewController(context: Context) -> UIActivityViewController {
                UIActivityViewController(activityItems: items, applicationActivities: nil)
            }
            func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
        }
