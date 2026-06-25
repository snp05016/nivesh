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

class WatchlistTagsManager: ObservableObject {
    @Published var tags: [String: [String]] = [:] {
        didSet {
            if let encoded = try? JSONEncoder().encode(tags) {
                UserDefaults.standard.set(encoded, forKey: "watchlistTags")
            }
        }
    }
    
    init() {
        if let data = UserDefaults.standard.data(forKey: "watchlistTags"),
           let decoded = try? JSONDecoder().decode([String: [String]].self, from: data) {
            tags = decoded
        }
    }

    func addTag(_ tag: String, to ticker: String) {
        let cleanTag = tag.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanTag.isEmpty else { return }
        var current = tags[ticker] ?? []
        if !current.contains(cleanTag) {
            current.append(cleanTag)
            tags[ticker] = current
        }
    }

    func removeTag(_ tag: String, from ticker: String) {
        var current = tags[ticker] ?? []
        current.removeAll { $0 == tag }
        if current.isEmpty {
            tags.removeValue(forKey: ticker)
        } else {
            tags[ticker] = current
        }
    }

    var allUniqueTags: [String] {
        let all = tags.values.flatMap { $0 }
        return Array(Set(all)).sorted()
    }
}

@MainActor
class PortfolioViewModel: ObservableObject {
    @Published var holdings: [PortfolioHolding] = []
    @Published var totalValue: Double = 0
    @Published var investedValue: Double = 0
    @Published var todayPnL: Double = 0
    @Published var isLoading = false

    @Published var watchlistItems: [WatchlistItem] = []
    @Published var watchlistLoading = false

    func fetchData(userId: Int) async {
        isLoading = true
        do {
            let data = try await NetworkManager.shared.getPortfolio(userId: userId)
            holdings = data
            totalValue = holdings.reduce(0) { $0 + $1.currentValue }
            investedValue = holdings.reduce(0) { $0 + $1.investedValue }
            todayPnL = holdings.reduce(0) { $0 + ($1.stock.currentPrice * $1.shares * ($1.stock.changePercent/100)) }
        } catch {
            print("Portfolio fetch error: \(error)")
        }
        isLoading = false
    }

    func fetchWatchlist(userId: Int) async {
        watchlistLoading = true
        do {
            watchlistItems = try await NetworkManager.shared.getWatchlist(userId: userId)
        } catch {
            print("Watchlist fetch error: \(error)")
        }
        watchlistLoading = false
    }

    func removeFromWatchlist(ticker: String, userId: Int) async {
        do {
            try await NetworkManager.shared.removeFromWatchlist(userId: userId, ticker: ticker)
            await fetchWatchlist(userId: userId)
            NotificationCenter.default.post(name: .watchlistUpdated, object: nil)
        } catch {
            print("Watchlist remove error: \(error)")
        }
    }

    func addHolding(userId: Int, ticker: String, companyName: String, shares: Double, buyPrice: Double, purchaseDate: Date, notes: String, targetPrice: Double) async throws {
        try await NetworkManager.shared.addHolding(userId: userId, ticker: ticker, companyName: companyName, shares: shares, buyPrice: buyPrice, purchaseDate: purchaseDate, notes: notes, targetPrice: targetPrice)
        await fetchData(userId: userId)
    }

    func removeHolding(ticker: String, userId: Int) async throws {
        try await NetworkManager.shared.removeHolding(userId: userId, ticker: ticker)
        await fetchData(userId: userId)
    }

    func updateHolding(userId: Int, ticker: String, shares: Double, buyPrice: Double) async throws {
        try await NetworkManager.shared.updateHolding(userId: userId, ticker: ticker, shares: shares, buyPrice: buyPrice)
        await fetchData(userId: userId)
    }
}

struct PortfolioScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager
    @StateObject private var viewModel = PortfolioViewModel()
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
    @State private var showNoteEditor = false
    @State private var noteEditingHolding: PortfolioHolding? = nil
    @State private var noteEditorText = ""
    @State private var showExportOptions = false
    @State private var exportedFileURL: URL? = nil
    @State private var showShareSheet = false
    @State private var signalWarnings: [String: SignalWarning] = [:]
    @State private var riskAnalysis: RiskAnalysis? = nil
    @State private var redFlags: RedFlagsResponse? = nil

        @State private var showBriefSheet = false
    @State private var showTransactionSheet = false

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

    /// Snapshots filtered to the selected time range (tail of the 90-day series).
    private var rangedSnapshots: [PortfolioValuationSnapshot] {
        guard !snapshots.isEmpty else { return [] }
        let n: Int
        switch selectedRange {
        case .day:         n = 2
        case .week:        n = 7
        case .month:       n = 30
        case .threeMonths: n = 90
        case .sixMonths:   n = 180
        case .year:        n = snapshots.count
        case .all:         n = snapshots.count
        }
        return Array(snapshots.suffix(max(n, 2)))
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
                            Button { showExportOptions = true } label: {.buttonStyle(EKPressStyle())
                                Image(systemName: "square.and.arrow.up")
                                    .foregroundStyle(Theme.inkSecondary)
                                    .padding(Theme.Spacing.medium)
                            }
                            Button { HapticManager.selection(); showBriefSheet = true } label: {.buttonStyle(EKPressStyle())
                                Image(systemName: "message")
                                    .foregroundStyle(Theme.inkSecondary)
                                    .padding(Theme.Spacing.medium)
                            }
                            .buttonStyle(EKPressStyle())
                            Button { HapticManager.selection(); showTransactionSheet = true } label: {.buttonStyle(EKPressStyle())
                                ZStack {
                                    Circle().stroke(Theme.borderSage, lineWidth: 0.5).frame(width: 44, height: 44)
                                    Text("₹").font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline)).foregroundStyle(Theme.inkPrimary)
                                }
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.standard)
                    .padding(.bottom, Theme.screenPadding)

                    ScrollView {
                        VStack(spacing: Theme.sectionSpacing) {
                            // Screen B — hero value block (price + two pills + brand chip)
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
                            }

                            HStack(spacing: Theme.Spacing.none) {
                                TabNoteButton(title: "Holdings", isSelected: selectedTab == 0) { selectedTab = 0 }
                                TabNoteButton(title: "Watchlist", isSelected: selectedTab == 1) { selectedTab = 1 }
                                TabNoteButton(title: "Journal", isSelected: selectedTab == 2) { selectedTab = 2 }
                            }
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)

                            if selectedTab == 0 {
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
                                            Button("Edit Holding") {
                                                editingHolding = holding
                                                showEditHoldingSheet = true
                                            }
                                            Button("Add Note") {
                                                noteEditingHolding = holding
                                                noteEditorText = holding.notes ?? ""
                                                showNoteEditor = true
                                            }
                                            Button("Remove from Portfolio", role: .destructive) {
                                                deletingTicker = holding.stock.ticker
                                                showDeleteAlert = true
                                            }
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
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: Theme.Spacing.medium) {
                                        ForEach(tagsManager.allUniqueTags, id: \.self) { tag in
                                            Button {
    HapticManager.selection()
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
                                ScrollView(.horizontal) {
                                    HStack(spacing: Theme.Spacing.standard) {
                                        ForEach(viewModel.watchlistItems.filter { item in
                                            activeWatchlistTag == nil || (tagsManager.tags[item.ticker]?.contains(activeWatchlistTag!) ?? false)
                                        }) { item in
                                            Button {
    HapticManager.selection()
                                                HapticManager.selection()
                                                stockTapTicker = item.ticker
                                                stockTapCompanyName = item.companyName
                                                showStockTapAction = true
                                            } label: {
                                                WatchlistRowView(item: item, tags: tagsManager.tags[item.ticker] ?? [], onRemove: {
                                                    guard let user = authManager.currentUser else { return }
                                                    Task { await viewModel.removeFromWatchlist(ticker: item.ticker, userId: user.userId) }
                                                }, onTag: {
                                                    taggingTicker = item.ticker
                                                    showTagSheet = true
                                                })
                                                .frame(width: UIScreen.main.bounds.width * 0.62)
                                            }
                                            .buttonStyle(.plain)
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                }
                                .scrollIndicators(.hidden)
                            } else if selectedTab == 2 {
                                if let user = authManager.currentUser {
                                    TradeJournalScreen(userId: user.userId)
                                        .padding(.horizontal, Theme.screenPadding)
                                }
                            }

                            Spacer(minLength: 100)
                        }
                    }
                    .refreshable {
                        HapticManager.impact(.medium)
                        if let user = authManager.currentUser {
                            await viewModel.fetchData(userId: user.userId)
                            await viewModel.fetchWatchlist(userId: user.userId)
                            let ws = await NetworkManager.shared.getSignalWarnings(userId: user.userId)
                            signalWarnings = Dictionary(ws.map { ($0.ticker, $0) }, uniquingKeysWith: { _, last in last })
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

                // FAB — Holdings "+" sits bottom-right, just left of the AI
                // chatbot FAB. Watchlist "+" is a mirror image of that chatbot
                // FAB on the opposite (left) edge, on the same vertical plane.
                if selectedTab == 0 {
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            addPortfolioButton
                                .padding(.trailing, Theme.Spacing.xLarge + Theme.Spacing.large + Theme.Spacing.standard)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.bottom, Theme.Spacing.standard)
                    }
                } else if selectedTab == 1 {
                    VStack {
                        Spacer()
                        HStack {
                            addWatchlistButton
                            Spacer()
                        }
                        .padding(.bottom, Theme.Spacing.standard)
                    }
                }
            }
        }
        .navigationDestination(for: HoldingNavValue.self) { val in
            AnalysisScreen(ticker: val.ticker, userNote: val.userNote, purchaseDateStr: val.purchaseDateStr, portfolioHolding: val.holding)
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
        .onAppear {
            guard let user = authManager.currentUser else { return }
            if viewModel.holdings.isEmpty && !viewModel.isLoading {
                Task { await viewModel.fetchData(userId: user.userId) }
            }
            if viewModel.watchlistItems.isEmpty && !viewModel.watchlistLoading {
                Task { await viewModel.fetchWatchlist(userId: user.userId) }
            }
            Task {
                let ws = await NetworkManager.shared.getSignalWarnings(userId: user.userId)
                signalWarnings = Dictionary(ws.map { ($0.ticker, $0) }, uniquingKeysWith: { _, last in last })
            }
            Task {
                let uid = user.userId
                riskAnalysis = try? await NetworkManager.shared.fetchRiskAnalysis(userId: uid)
                redFlags = try? await NetworkManager.shared.fetchRedFlags(userId: uid)
            }
            Task {
                if let resp = try? await NetworkManager.shared.fetchValuationHistory(userId: user.userId, days: 730) {
                    snapshots = resp.snapshots
                }
            }
        }
        .sheet(isPresented: $showAddWatchlistSheet) {
            AddWatchlistSheet(
                searchText: $addSheetSearchText,
                onAdd: { entry in
                    guard let user = authManager.currentUser else { return }
                    Task {
                        let added = (try? await NetworkManager.shared.addToWatchlist(
                            userId: user.userId,
                            ticker: entry.ticker,
                            exchange: entry.exchange,
                            companyName: entry.companyName
                        )) ?? false
                        showAddWatchlistSheet = false
                        await viewModel.fetchWatchlist(userId: user.userId)
                        if added {
                            NotificationCenter.default.post(name: .watchlistUpdated, object: nil)
                            addedBannerTicker = entry.ticker
                            withAnimation { showAddedBanner = true }
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
                            try? await NetworkManager.shared.saveNote(userId: user.userId, ticker: holding.stock.ticker, note: savedNote)
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
                        Task {
                            try? await viewModel.removeHolding(ticker: deletingTicker, userId: user.userId)
                        }
                    }
                },
                .cancel()
            ]
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
            print("Excel export error: \(error)")
        }
    }

    private func shareToWhatsApp() {
        let totalVal = viewModel.totalValue.inrFormatted
        let investedVal = viewModel.investedValue.inrFormatted
        let rawPnl = viewModel.totalValue - viewModel.investedValue
        let pnl = rawPnl.inrFormatted
        
        let text = """
        My Nivesh Portfolio 📈
        Total Value: ₹\(totalVal)
        Invested: ₹\(investedVal)
        P&L: \(rawPnl >= 0 ? "+" : "")\(pnl)
        """
        
        if let encoded = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
           let url = URL(string: "whatsapp://send?text=\(encoded)") {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url)
            }
        }
    }

    private var addPortfolioButton: some View {
        Button {
    HapticManager.selection()
            HapticManager.impact(.medium)
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
    }

    // Watchlist "+" — built from scratch to be an exact mirror image of the AI
    // chatbot FAB (CopilotFloatingButtonModifier): same icon-padded circle, same
    // edge inset, anchored to the opposite (left) edge on the same vertical plane.
    private var addWatchlistButton: some View {
        Button {
    HapticManager.selection()
            HapticManager.impact(.medium)
            addSheetSearchText = ""
            showAddWatchlistSheet = true
        } label: {
            Image(systemName: "plus")
                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.canvas)
                .padding(Theme.Spacing.card)
                .background(Theme.securityGold)
                .clipShape(Circle())
                .shadow(color: Theme.securityGold.opacity(0.4), radius: Theme.Spacing.medium, x: 0, y: Theme.Spacing.small)
        }
        .buttonStyle(EKPressStyle())
        .padding(.leading, Theme.screenPadding + Theme.Spacing.standard)
    }

    @ViewBuilder
    private var watchlistTabContent: some View {
        if viewModel.watchlistLoading {
            VStack(spacing: Theme.Spacing.standard) {
                ForEach(0..<3, id: \.self) { _ in
                    WatchlistSkeletonRow()
                }
            }
            .padding(.horizontal, Theme.screenPadding)
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
                        HapticManager.selection()
                        stockTapTicker = item.ticker
                        stockTapCompanyName = item.companyName
                        showStockTapAction = true
                    } label: {
                        WatchlistRowView(item: item, tags: tagsManager.tags[item.ticker] ?? [], onRemove: {
                            guard let user = authManager.currentUser else { return }
                            Task { await viewModel.removeFromWatchlist(ticker: item.ticker, userId: user.userId) }
                        }, onTag: {
                            taggingTicker = item.ticker
                            showTagSheet = true
                        })
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, activeWatchlistTag == nil || tagsManager.allUniqueTags.isEmpty ? Theme.screenPadding : 0) // adjusted padding since scrollview needs full width
            .sheet(isPresented: $showTagSheet) {
                TaggingSheet(ticker: taggingTicker, tagsManager: tagsManager)
            }
        }
    }
}

private struct TaggingSheet: View {
    let ticker: String
    @ObservedObject var tagsManager: WatchlistTagsManager
    @Environment(\.dismiss) var dismiss
    @State private var newTag = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                    Text("TAG \(ticker)")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                    
                    HStack {
                        TextField("New Tag (e.g. Tech)", text: $newTag)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundStyle(Theme.inkPrimary)
                        Button("Add") {
                            tagsManager.addTag(newTag, to: ticker)
                            newTag = ""
                        }
                        .disabled(newTag.trimmingCharacters(in: .whitespaces).isEmpty)
                        .foregroundStyle(Theme.securityGold)
                    }
                    .padding(Theme.Spacing.card)
                    .banknoteCard()
                    
                    let currentTags = tagsManager.tags[ticker] ?? []
                    if !currentTags.isEmpty {
                        Text("CURRENT TAGS")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                        
                        ForEach(currentTags, id: \.self) { tag in
                            HStack {
                                Text(tag).font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline)).foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                Button(action: { HapticManager.selection(); tagsManager.removeTag(tag, from: ticker) }) {.buttonStyle(EKPressStyle())
                                    Image(systemName: "minus.circle.fill").foregroundStyle(Theme.bearRed)
                                }
                            }
                            .padding(Theme.Spacing.standard)
                            .banknoteCard()
                        }
                    }
                    Spacer()
                }
                .padding(Theme.Spacing.screen)
            }
            .navigationTitle("Tags")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }.buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

// MARK: - Portfolio Risk Card

private struct PortfolioRiskCard: View {
    let riskAnalysis: RiskAnalysis?

    // NOTE: signalEmerald (Theme.bullGreen = "2D5A3D"/"4A8A5D") and
    // signalRuby (Theme.bearRed = "8B3A2A"/"C05540") must maintain >=4.5:1
    // contrast against Theme.canvas ("F5F0E8"/"1C1A14") per WCAG AA.
    var riskColor: Color {
        guard let score = riskAnalysis?.riskScore else { return Theme.securityGold }
        if score <= 4 { return Theme.signalEmerald }
        if score <= 6 { return Theme.securityGold }
        return Theme.signalRuby
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                Text("PORTFOLIO RISK")
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)
                Spacer()
                if let label = riskAnalysis?.riskScoreLabel {
                    Text(label)
                        .font(.caption2)
                        .foregroundStyle(riskColor)
                        .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                        .background(riskColor.opacity(0.15))
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }

            // Risk meter — 10 segments
            if let score = riskAnalysis?.riskScore {
                HStack(spacing: Theme.Spacing.small) {
                    ForEach(1...10, id: \.self) { i in
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(i <= score ? riskColor : Theme.canvasDeep)
                            .frame(height: 8)
                    }
                }
            }

            // Beta
            if let beta = riskAnalysis?.portfolioBeta {
                Text("β \(String(format: "%.2f", beta))")
                    .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .financeTerm("Beta")
            }

            // Concentration warnings
            if let warnings = riskAnalysis?.concentrationRisks, !warnings.isEmpty {
                HStack(spacing: Theme.Spacing.tight) {
                    ForEach(warnings) { w in
                        Text("\(w.ticker) \(String(format: "%.0f", w.pctOfPortfolio))%")
                            .font(.caption2)
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.signalRuby)
                            .cornerRadius(Theme.CornerRadius.small)
                    }
                }
            }

            // Correlation warning
            if let pair = riskAnalysis?.highestCorrelationPair, pair.correlation > 0.7 {
                Text("\(pair.tickerA) ↔ \(pair.tickerB) highly correlated")
                    .font(.caption)
                    .foregroundStyle(Theme.securityGold)
            }

            // Summary
            if let summary = riskAnalysis?.riskSummary {
                Text(summary)
                    .font(.caption.italic())
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding()
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

// MARK: - Red Flags Section

private struct RedFlagsSection: View {
    let redFlags: RedFlagsResponse?
    let onTickerTap: (String) -> Void
    @State private var isExpanded = false

    var body: some View {
        if let rf = redFlags, rf.totalFlags > 0 {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                // Header
                Button(action: { HapticManager.selection(); withAnimation(.easeInOut(duration: 0.25)) { isExpanded.toggle() } }) {.buttonStyle(EKPressStyle())
                    HStack {
                        Text("⚠")
                            .font(.caption)
                        Text("RED FLAGS")
                            .font(Theme.sectionCapsLabel())
                            .tracking(1.5)
                            .foregroundStyle(Theme.signalRuby)
                        Text("\(rf.totalFlags)")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.signalRuby)
                            .clipShape(Capsule())
                        Spacer()
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                .buttonStyle(.plain)

                if isExpanded {
                    ForEach(rf.flags) { flag in
                        Button {
    HapticManager.selection()
                            HapticManager.selection()
                            onTickerTap(flag.ticker)
                        } label: {
                            HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                                Text(flag.severity == "CRITICAL" ? "🔴" : flag.severity == "WARNING" ? "🟡" : "🔵")
                                    .font(.caption)
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    HStack {
                                        Text(flag.ticker)
                                            .font(Theme.monoTabular(size: 12, relativeTo: .caption).weight(.bold))
                                            .foregroundStyle(Theme.inkPrimary)
                                        Text(flag.flagType.replacingOccurrences(of: "_", with: " "))
                                            .font(.caption2)
                                            .foregroundStyle(Theme.inkSecondary)
                                            .tracking(0.5)
                                    }
                                    Text(flag.detail)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .buttonStyle(.plain)
                    }

                    if let summary = rf.summary, !summary.isEmpty {
                        Text(summary)
                            .font(.caption.italic())
                            .foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, Theme.Spacing.small)
                    }
                }
            }
            .padding()
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.signalRuby.opacity(0.3), lineWidth: 0.5))
        }
    }
}

private struct TabNoteButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: { HapticManager.selection();  HapticManager.selection()
            HapticManager.selection()
            action()
        }) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(isSelected ? Theme.inkPrimary : Theme.inkTertiary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .background(isSelected ? Theme.inkSecondary.opacity(0.05) : Color.clear)
        }
        .overlay(
            VStack {
                if isSelected {
                    Spacer()
                    Rectangle().fill(Theme.securityGold).frame(height: 2)
                }
            }
        )
    }
}

/// Screen B holding row — colored allocation dot, ticker, shares, value, ChangeBadge.
/// Lives inside a single shared `.banknoteCard()` (no per-row card).
private struct HoldingNoteRow: View {
    let holding: PortfolioHolding
    var color: Color = Theme.inkSecondary
    var signalWarning: SignalWarning? = nil
    var hideValues: Bool = false

    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            Circle().fill(color).frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(holding.stock.ticker)
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("\(Int(holding.shares)) shares")
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
                if let note = holding.notes, !note.isEmpty {
                    Text(note)
                        .font(Font.custom("Georgia", size: 12, relativeTo: .caption).italic())
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
                if let warning = signalWarning {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption2)
                        Text(warning.signalFlipped ? "SIGNAL CHANGED" : "BEARISH")
                            .font(Theme.officialStampFont(size: 7))
                    }
                    .foregroundStyle(Theme.inkPrimary)
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                    .background(Theme.bearRed.opacity(0.18))
                    .clipShape(Capsule())
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(hideValues ? "₹ ••••" : IndianFormatter.price(holding.currentValue))
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
                    .foregroundStyle(Theme.inkPrimary)
                if !hideValues { ChangeBadge(value: holding.pnlPercent) }
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }
}

/// Shared 6-colour allocation palette (donut segments + holding dots), Screen B.
let allocationPalette: [Color] = [
    Theme.bullGreen,
    Theme.securityGold,
    Theme.bearRed.opacity(0.8),
    Color(hue: 0.58, saturation: 0.5, brightness: 0.6),
    Color(hue: 0.72, saturation: 0.4, brightness: 0.65),
    Theme.inkSecondary
]

/// Screen B — hero value block: label, large price, two pills, brand chip.
private struct PortfolioHeroBlock: View {
    let value: Double
    let totalPnL: Double
    let totalPnLPercent: Double
    let isLoading: Bool
    var hideValues: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("Portfolio · current value")
                        .font(Theme.officialStampFont(size: 9)).tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(hideValues ? "₹ ••••••" : IndianFormatter.price(value))
                        .font(.largeTitle.weight(.bold)).monospaced()
                        .foregroundStyle(Theme.inkPrimary)
                        .contentTransition(.numericText())
                }
                Spacer()
                NiveshBrandChip()
            }
            if !hideValues {
                HStack(spacing: Theme.Spacing.small) {
                    ChangeBadge(value: totalPnLPercent)
                    let up = totalPnL >= 0
                    Text((up ? "+" : "") + IndianFormatter.priceCompact(totalPnL) + " total")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                        .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.18))
                        .clipShape(Capsule())
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .shimmerPlaceholder(isLoading: isLoading)
    }
}

/// Screen B — allocation donut + legend card.
private struct PortfolioAllocationDonutCard: View {
    let holdings: [PortfolioHolding]
    private var total: Double { max(holdings.reduce(0) { $0 + $1.currentValue }, 1) }
    private var sorted: [PortfolioHolding] { holdings.sorted { $0.currentValue > $1.currentValue } }

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            ZStack {
                Canvas { ctx, size in
                    let lineW: CGFloat = 14
                    let radius = min(size.width, size.height) / 2 - lineW / 2
                    let center = CGPoint(x: size.width / 2, y: size.height / 2)
                    var startDeg: Double = -90
                    for (i, h) in sorted.enumerated() {
                        let sweep = (h.currentValue / total) * 360
                        var p = Path()
                        // BUG-10: 1° gap each side for clean segment separation
                        p.addArc(center: center, radius: radius,
                                 startAngle: .degrees(startDeg + 1),
                                 endAngle: .degrees(startDeg + sweep - 1), clockwise: false)
                        ctx.stroke(p, with: .color(allocationPalette[i % allocationPalette.count]),
                                   style: StrokeStyle(lineWidth: lineW, lineCap: .butt))
                        startDeg += sweep
                    }
                }
                .frame(width: UIScreen.main.bounds.width * 0.28, height: UIScreen.main.bounds.width * 0.28)
                VStack(spacing: Theme.Spacing.none) {
                    Text("\(holdings.count)")
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .title3).weight(.bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("STOCKS")
                        .font(Theme.officialStampFont(size: 8)).tracking(1.0)
                        .foregroundStyle(Theme.inkTertiary)
                }
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                ForEach(Array(sorted.prefix(4).enumerated()), id: \.element.id) { i, h in
                    HStack(spacing: Theme.Spacing.small) {
                        Circle().fill(allocationPalette[i % allocationPalette.count]).frame(width: 8, height: 8)
                        Text(h.stock.ticker)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        Text(String(format: "%.1f%%", h.currentValue / total * 100))
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                if holdings.count > 4 {
                    Text("+ \(holdings.count - 4) more")
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct PortfolioHeroNote: View {
    let value: Double
    let totalPnL: Double
    let invested: Double
    let todayPnL: Double
    let count: Int
    let isLoading: Bool

    var body: some View {
        ZStack(alignment: .topLeading) {
            GeometryReader { _ in RupeeWatermark() }

            SecurityThread()

            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("NIVESH")
                            .font(Theme.engravedSerif(size: 14, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Reserve Bank of Intelligence")
                            .font(Theme.serialNumberFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Text("भारतीय निवेश")
                        .font(Theme.hindiFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(.bottom, 8)

                SectionGuillocheDivider()

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("निवेश पोर्टफोलियो")
                        .font(Theme.hindiFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)

                    Text("TOTAL VALUATION")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkSecondary)

                    Text("I PROMISE TO PAY THE BEARER")
                        .font(.caption2.weight(.medium))
                        .tracking(2)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.bottom, 2)

                    PortfolioValueDisplay(target: value, fontSize: 30)

                    HStack(spacing: Theme.Spacing.medium) {
                        Text(totalPnL >= 0 ? "SURPLUS" : "DEFICIT")
                        Text(totalPnL.inrFormatted)
                            .contentTransition(.numericText())
                        Text("(\((invested > 0 ? totalPnL/invested*100 : 0).percentFormatted))")
                            .contentTransition(.numericText())
                    }
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(totalPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                .padding(.top, 4)

                SectionGuillocheDivider()

                HStack {
                    StatNoteBlock(label: "DAILY", value: todayPnL.inrFormatted, color: todayPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                    Spacer()
                    StatNoteBlock(label: "COST", value: invested.shortFormatted, color: Theme.inkPrimary)
                    Spacer()
                    StatNoteBlock(label: "UNITS", value: "\(count)", color: Theme.inkPrimary)
                }
            }
            .padding(.leading, 32)
            .padding(.trailing, 24)
            .padding(.vertical, 20)
        }
        .banknoteCard()
        .clipped()
        .shimmerPlaceholder(isLoading: isLoading)
    }
}

private struct StatNoteBlock: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(Theme.inkSecondary)
            Text(value)
                .contentTransition(.numericText())
                .font(Theme.serialNumberFont(size: 14))
                .foregroundStyle(color)
        }
    }
}

private struct WatchlistRowView: View {
    let item: WatchlistItem
    var tags: [String] = []
    let onRemove: () -> Void
    let onTag: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            // Left sage-green rule (no P&L signal)
            Rectangle()
                .fill(Theme.borderSage.opacity(0.6))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: item.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(item.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(1)
                    HStack {
                        Text(item.ticker)
                            .font(Theme.serialNumberFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                        if !tags.isEmpty {
                            Text(tags.joined(separator: ", "))
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.securityGold)
                        }
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text("₹\(item.currentPrice.inrFormatted)")
                        .contentTransition(.numericText())
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundStyle(Theme.inkPrimary)
                    let changeStr = (item.dayChangePct >= 0 ? "+" : "") + String(format: "%.2f%%", item.dayChangePct)
                    Text(changeStr)
                        .contentTransition(.numericText())
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(item.dayChangePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
        .banknoteCard()
        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
            Button(role: .destructive, action: onRemove) {
                Label("Remove", systemImage: "trash")
            }
            .tint(Theme.bearRed)
        }
        .swipeActions(edge: .leading) {
            Button(action: onTag) {
                Label("Tag", systemImage: "tag")
            }
            .tint(Theme.securityGold)
        }
    }
}

private struct WatchlistSkeletonRow: View {
    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        HStack(spacing: Theme.Spacing.card) {
            Circle()
                .fill(Theme.inkTertiary.opacity(0.1))
                .frame(width: 40, height: 40)
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.15)).frame(width: colW * 0.37, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.1)).frame(width: colW * 0.17, height: 9)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.15)).frame(width: colW * 0.20, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.1)).frame(width: colW * 0.11, height: 9)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, 16)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

private struct AddHoldingSheet: View {
    let viewModel: PortfolioViewModel
    let authManager: AuthManager
    @Environment(\.dismiss) private var dismiss
    
    @State private var searchText = ""
    @State private var selectedEntry: StockEntry? = nil
    @State private var sharesText = ""
    @State private var buyPriceText = ""
    @State private var purchaseDate = Date()
    @State private var notes = ""
    @State private var targetPriceText = ""
    @State private var errorText: String? = nil
    @State private var isAdding = false
    
    private var searchResults: [StockEntry] {
        if searchText.trimmingCharacters(in: .whitespaces).isEmpty { return [] }
        let q = searchText.uppercased()
        return StockDatabase.all.filter {
            $0.ticker.contains(q) || $0.companyName.uppercased().contains(q)
        }
    }
    
    private var shares: Double { Double(sharesText) ?? 0 }
    private var buyPrice: Double { Double(buyPriceText) ?? 0 }
    private var canAdd: Bool { selectedEntry != nil && shares > 0 && buyPrice > 0 && !isAdding }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(spacing: Theme.Spacing.none) {
                    // Stock search
                    VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                        HStack {
                            Image(systemName: "magnifyingglass").foregroundStyle(Theme.inkTertiary)
                            if let entry = selectedEntry {
                                HStack(spacing: Theme.Spacing.tight) {
                                    Text(entry.ticker)
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(entry.companyName)
                                        .font(Theme.serialNumberFont(size: 12))
                                        .foregroundStyle(Theme.inkSecondary)
                                        .lineLimit(1)
                                    Spacer()
                                    Button {
    HapticManager.selection()
                                        selectedEntry = nil
                                        searchText = ""
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                    .accessibilityLabel("Clear selection")
                                }
                            } else {
                                TextField("Search stock…", text: $searchText)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                            }
                        }
                        .padding(Theme.Spacing.standard)
                        .background(Theme.inkPrimary.opacity(0.05))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, 16)
                        
                        if selectedEntry == nil && !searchResults.isEmpty {
                            List(searchResults) { entry in
                                Button {
    HapticManager.selection()
                                    selectedEntry = entry
                                    searchText = entry.ticker
                                } label: {
                                    HStack(spacing: Theme.Spacing.small) {
                                        StockIcon(ticker: entry.ticker, signal: nil)
                                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 13, weight: .bold))
                                                .foregroundStyle(Theme.inkPrimary)
                                            Text(entry.ticker)
                                                .font(Theme.serialNumberFont(size: 10))
                                                .foregroundStyle(Theme.inkSecondary)
                                        }
                                        Spacer()
                                        Image(systemName: "checkmark.circle")
                                            .foregroundStyle(Theme.securityGold)
                                    }
                                    .padding(.vertical, 4)
                                }
                                .listRowBackground(Theme.canvas)
                            }
                            .listStyle(.plain)
                            .frame(maxHeight: 220)
                        }
                    }
                    
                    // Shares & Buy Price inputs
                    VStack(spacing: Theme.Spacing.card) {
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("NUMBER OF SHARES")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("e.g. 100", text: $sharesText)
                                .keyboardType(.numberPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("BUY PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("e.g. 1530.00", text: $buyPriceText)
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("PURCHASE DATE")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            DatePicker("", selection: $purchaseDate, displayedComponents: .date)
                                .labelsHidden()
                                .accentColor(Theme.securityGold)
                                .padding(Theme.Spacing.medium)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .cornerRadius(Theme.CornerRadius.medium)
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("TARGET PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("optional...", text: $targetPriceText)
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("NOTES / INVESTMENT REASON")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("Why did you buy this?", text: $notes)
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        
                        if let err = errorText {
                            Text(err)
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundStyle(Theme.bearRed)
                                .multilineTextAlignment(.center)
                        }
                        
                        Button {
    HapticManager.selection()
                            guard let entry = selectedEntry, let user = authManager.currentUser else { return }
                            // Fix 3.7+3.8: Validate quantity > 0 and buyPrice > 0
                            guard shares > 0 else {
                                errorText = "Number of shares must be greater than zero"
                                return
                            }
                            guard buyPrice > 0 else {
                                errorText = "Buy price cannot be zero"
                                return
                            }
                            // Fix 3.5: Block Western number scales in notes
                            if notes.containsWesternScale {
                                errorText = "Use Indian numbering (Lakhs/Crores) instead of Million/Billion"
                                return
                            }
                            isAdding = true
                            errorText = nil
                            Task {
                                do {
                                    try await viewModel.addHolding(
                                        userId: user.userId,
                                        ticker: entry.ticker,
                                        companyName: entry.companyName,
                                        shares: shares,
                                        buyPrice: buyPrice,
                                        purchaseDate: purchaseDate,
                                        notes: notes,
                                        targetPrice: Double(targetPriceText) ?? 0.0
                                    )
                                    dismiss()
                                } catch {
                                    errorText = error.localizedDescription
                                }
                                isAdding = false
                            }
                        } label: {
                            HStack(spacing: Theme.Spacing.medium) {
                                if isAdding {
                                    ProgressView().tint(.white)
                                }
                                Text(isAdding ? "ADDING…" : "ADD TO PORTFOLIO")
                                    .font(Theme.officialStampFont(size: 11))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(canAdd ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                            .foregroundStyle(.white)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                        }
                        .disabled(!canAdd)
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 24)
                    
                    Spacer()
                }
            }
            .navigationTitle("Add Holding")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") {
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                    }
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(Theme.securityGold)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
    }
}

private struct EditHoldingSheet: View {
        let holding: PortfolioHolding
        let viewModel: PortfolioViewModel
        let authManager: AuthManager
        @Environment(\.dismiss) private var dismiss
        
        @State private var sharesText: String
        @State private var buyPriceText: String
        @State private var errorText: String? = nil
        @State private var isSaving = false
        
        init(holding: PortfolioHolding, viewModel: PortfolioViewModel, authManager: AuthManager) {
            self.holding = holding
            self.viewModel = viewModel
            self.authManager = authManager
            _sharesText = State(initialValue: String(format: "%g", holding.shares))
            _buyPriceText = State(initialValue: String(format: "%.2f", holding.buyPrice))
        }
        
        private var shares: Double { Double(sharesText) ?? 0 }
        private var buyPrice: Double { Double(buyPriceText) ?? 0 }
        private var canSave: Bool { shares > 0 && buyPrice > 0 && !isSaving }
        
        var body: some View {
            NavigationStack {
                ZStack {
                    Theme.canvas.ignoresSafeArea()
                    VStack(spacing: Theme.Spacing.small) {
                        // Read-only stock info
                        HStack(spacing: Theme.Spacing.card) {
                            StockIcon(ticker: holding.stock.ticker, signal: nil)
                            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 15, weight: .bold))
                                    .foregroundStyle(Theme.inkPrimary)
                                Text(holding.stock.ticker)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, 24)
                        
                        VStack(spacing: Theme.Spacing.card) {
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                Text("NUMBER OF SHARES")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("Shares", text: $sharesText)
                                    .keyboardType(.numberPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.standard)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                            
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                Text("BUY PRICE (₹)")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("Buy Price", text: $buyPriceText)
                                    .keyboardType(.decimalPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.standard)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                            
                            if let err = errorText {
                                Text(err)
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(Theme.bearRed)
                                    .multilineTextAlignment(.center)
                            }
                            
                            Button {
    HapticManager.selection()
                                guard let user = authManager.currentUser else { return }
                                isSaving = true
                                errorText = nil
                                Task {
                                    do {
                                        try await viewModel.updateHolding(
                                            userId: user.userId,
                                            ticker: holding.stock.ticker,
                                            shares: shares,
                                            buyPrice: buyPrice
                                        )
                                        dismiss()
                                    } catch {
                                        errorText = error.localizedDescription
                                    }
                                    isSaving = false
                                }
                            } label: {
                                HStack(spacing: Theme.Spacing.medium) {
                                    if isSaving {
                                        ProgressView().tint(.white)
                                    }
                                    Text(isSaving ? "SAVING…" : "SAVE CHANGES")
                                        .font(Theme.officialStampFont(size: 11))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, Theme.Spacing.standard)
                                .background(canSave ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                                .foregroundStyle(.white)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                            }
                            .disabled(!canSave)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        
                        Spacer()
                    }
                }
                .navigationTitle("Edit Holding")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItemGroup(placement: .keyboard) {
                        Spacer()
                        Button("Done") {
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                        }
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(Theme.securityGold)
                    }
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
        }
}

private struct NoteEditorSheet: View {
            let holding: PortfolioHolding
            @Binding var noteText: String
            let onSave: (String) -> Void
            @Environment(\.dismiss) var dismiss
            
            var body: some View {
                NavigationStack {
                    ZStack {
                        Theme.canvas.ignoresSafeArea()
                        VStack(spacing: Theme.Spacing.xSmall) {
                            // Header
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text("अपना नोट / PERSONAL NOTE")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 18, weight: .bold))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 20)
                            
                            // Text editor
                            TextEditor(text: $noteText)
                                .font(Theme.engravedSerif(size: 15))
                                .foregroundStyle(Theme.inkPrimary)
                                .frame(minHeight: 150)
                                .padding(Theme.Spacing.card)
                                .background(Theme.canvasDeep)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSage, lineWidth: 1))
                                .padding(.horizontal, 20)
                            
                            // Character count
                            Text("\(noteText.count)/280 characters")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(noteText.count > 280 ? Theme.bearRed : Theme.inkTertiary)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .padding(.horizontal, 20)
                            
                            Spacer()
                        }
                        .padding(.top, 20)
                    }
                    .navigationTitle("Note")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Save") {
                                onSave(String(noteText.prefix(280)))
                                dismiss()
                            }
                            .disabled(noteText.count > 280)
                        }
                    }
                }
            }
        }
        
        private struct AddWatchlistSheet: View {
            @Binding var searchText: String
            let onAdd: (StockEntry) -> Void
            @Environment(\.dismiss) private var dismiss
            
            private var results: [StockEntry] {
                if searchText.trimmingCharacters(in: .whitespaces).isEmpty { return StockDatabase.all }
                let q = searchText.uppercased()
                return StockDatabase.all.filter {
                    $0.ticker.contains(q) || $0.companyName.uppercased().contains(q) || $0.sector.uppercased().contains(q)
                }
            }
            
            var body: some View {
                NavigationStack {
                    ZStack {
                        Theme.canvas.ignoresSafeArea()
                        
                        VStack(spacing: Theme.Spacing.none) {
                            HStack {
                                Image(systemName: "magnifyingglass")
                                    .foregroundStyle(Theme.inkTertiary)
                                TextField("Search stocks…", text: $searchText)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                            }
                            .padding(Theme.Spacing.standard)
                            .background(Theme.inkPrimary.opacity(0.05))
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, 16)
                            .padding(.bottom, 8)
                            
                            List(results) { entry in
                                Button {
    HapticManager.selection()
                                    onAdd(entry)
                                } label: {
                                    HStack(spacing: Theme.Spacing.small) {
                                        StockIcon(ticker: entry.ticker, signal: nil)
                                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 14, weight: .bold))
                                                .foregroundStyle(Theme.inkPrimary)
                                            HStack(spacing: Theme.Spacing.tight) {
                                                Text(entry.ticker)
                                                    .font(Theme.serialNumberFont(size: 10))
                                                    .foregroundStyle(Theme.inkSecondary)
                                                Text("·")
                                                    .foregroundStyle(Theme.inkTertiary)
                                                Text(entry.sector)
                                                    .font(Theme.serialNumberFont(size: 10))
                                                    .foregroundStyle(Theme.inkTertiary)
                                            }
                                        }
                                        Spacer()
                                        Image(systemName: "plus.circle")
                                            .foregroundStyle(Theme.securityGold)
                                    }
                                    .padding(.vertical, 6)
                                }
                                .listRowBackground(Theme.canvas)
                            }
                            .listStyle(.plain)
                        }
                    }
                    .navigationTitle("Add to Watchlist")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                                .font(Theme.serialNumberFont(size: 13))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
            }
        }
        
        private struct SectorAllocationPieChart: View {
            let holdings: [PortfolioHolding]
            
            private func pseudoSector(for ticker: String) -> String {
                let t = ticker.uppercased()
                if t.contains("BANK") || t.contains("FIN") || t.contains("HDFC") || t.contains("ICICI") { return "Financials" }
                if t.contains("TECH") || t.contains("INFY") || t.contains("TCS") || t.contains("WIPRO") { return "IT" }
                if t.contains("PHARMA") || t.contains("SUN") || t.contains("CIPLA") { return "Healthcare" }
                if t.contains("AUTO") || t.contains("MOTORS") || t.contains("MARUTI") { return "Auto" }
                if t.contains("ENERGY") || t.contains("POW") || t.contains("REL") { return "Energy" }
                return "Others"
            }

            private var sectorGroups: [(sector: String, value: Double, color: Color)] {
                var groups: [String: Double] = [:]
                for h in holdings {
                    let s = pseudoSector(for: h.stock.ticker)
                    groups[s, default: 0] += h.currentValue
                }
                let colors: [Color] = [Theme.bullGreen, Theme.bearRed, Theme.holdAmber, Theme.securityGold, Theme.inkSecondary, Theme.inkPrimary]
                return groups.sorted(by: { $0.value > $1.value }).enumerated().map { index, element in
                    (sector: element.key, value: element.value, color: colors[index % colors.count])
                }
            }

            private var totalValue: Double {
                holdings.reduce(0) { $0 + $1.currentValue }
            }

            var body: some View {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Text("SECTOR ALLOCATION")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkSecondary)
                        
                    if holdings.isEmpty {
                        Text("No holdings")
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundStyle(Theme.inkTertiary)
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else {
                        let data = sectorGroups
                        ZStack {
                            Chart(data, id: \.sector) { item in
                                SectorMark(
                                    angle: .value("Value", item.value),
                                    innerRadius: .ratio(0.55),
                                    angularInset: 1.5
                                )
                                .foregroundStyle(item.color)
                                .annotation(position: .overlay) {
                                    let pct = totalValue > 0 ? (item.value / totalValue) * 100 : 0
                                    if pct > 5 {
                                        VStack(spacing: Theme.Spacing.xSmall) {
                                            Text(item.sector)
                                                .font(Theme.officialStampFont(size: 8))
                                                .foregroundStyle(.white)
                                                .lineLimit(1)
                                            Text(String(format: "%.0f%%", pct))
                                                .font(Theme.serialNumberFont(size: 8))
                                                .foregroundStyle(.white.opacity(0.9))
                                        }
                                    }
                                }
                            }
                            .frame(height: UIScreen.main.bounds.height * 0.30)
                            
                            VStack(spacing: Theme.Spacing.xSmall) {
                                Text("₹")
                                    .font(Theme.engravedSerif(size: 14, weight: .bold))
                                    .foregroundStyle(Theme.inkTertiary)
                                Text(totalValue.inrFormatted)
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                        }
                    }
                }
            }
        }

        // MARK: - Portfolio Charts Carousel
        
        private struct PortfolioChartsCarousel: View {
            let holdings: [PortfolioHolding]
            @State private var page = 0
            @State private var sectorData: [SectorPerformance] = []
            
            var body: some View {
                VStack(spacing: Theme.Spacing.medium) {
                    TabView(selection: $page) {
                        ScrollView {
                            PortfolioAllocationChart(holdings: holdings)
                                .padding(Theme.Spacing.screen)
                        }
                        .banknoteCard()
                        .tag(0)

                        ScrollView {
                            PnLWaterfallChart(holdings: holdings)
                                .padding(Theme.Spacing.screen)
                        }
                        .banknoteCard()
                        .tag(1)

                        ScrollView {
                            SectorHeatmapView(sectors: sectorData)
                                .padding(Theme.Spacing.screen)
                        }
                        .banknoteCard()
                        .tag(2)

                        ScrollView {
                            SectorAllocationPieChart(holdings: holdings)
                                .padding(Theme.Spacing.screen)
                        }
                        .banknoteCard()
                        .tag(3)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .always))
                    .frame(height: UIScreen.main.bounds.height * 0.65)

                    Text("Swipe to explore →")
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(Theme.inkTertiary)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                .onAppear {
                    Task { sectorData = (try? await NetworkManager.shared.getSectorPerformance()) ?? [] }
                }
            }
        }
        
        // MARK: - Portfolio Charts Strip (backend-generated chart PNGs)

        private struct PortfolioChartsStrip: View {
            let userId: Int
            @State private var charts: [ChartItem] = []
            @State private var isLoading = false
            @State private var errorMsg: String? = nil
            @State private var expandedChart: ChartItem? = nil

            var body: some View {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    // Section header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("पोर्टफोलियो चार्ट")
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("PORTFOLIO CHARTS")
                            .font(.caption.weight(.semibold).monospaced())
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary.opacity(0.7))
                    }

                    if isLoading {
                        ScrollView(.horizontal) {
                            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                                ForEach(0..<3, id: \.self) { _ in
                                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                        RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                            .fill(Theme.inkTertiary.opacity(0.08))
                                            .frame(width: UIScreen.main.bounds.width * 0.85, height: UIScreen.main.bounds.height * 0.22)
                                            .overlay(
                                                ProgressView()
                                                    .tint(Theme.securityGold)
                                            )
                                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                            .fill(Theme.inkTertiary.opacity(0.12))
                                            .frame(width: UIScreen.main.bounds.width * 0.55, height: 10)
                                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                            .fill(Theme.inkTertiary.opacity(0.08))
                                            .frame(width: UIScreen.main.bounds.width * 0.40, height: 8)
                                    }
                                    .padding(Theme.Spacing.medium)
                                    .background(Theme.canvasDeep)
                                    .cornerRadius(Theme.CornerRadius.large)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                            .stroke(Theme.borderSage, lineWidth: 0.5)
                                    )
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        .scrollIndicators(.hidden)
                    } else if let err = errorMsg {
                        // Error state with detailed debug info
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            HStack(spacing: Theme.Spacing.medium) {
                                Image(systemName: "chart.bar.xaxis")
                                    .font(.subheadline)
                                    .foregroundStyle(Theme.bearRed.opacity(0.6))
                                Text("Charts unavailable")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            Text("Error: \(err)")
                                .font(.caption2.monospaced())
                                .foregroundStyle(Theme.bearRed.opacity(0.7))
                                .lineLimit(3)
                                .fixedSize(horizontal: false, vertical: true)
                            Button(action: { HapticManager.selection(); fetchCharts() }) {.buttonStyle(EKPressStyle())
                                HStack(spacing: Theme.Spacing.small) {
                                    Image(systemName: "arrow.clockwise")
                                        .font(.caption2)
                                    Text("RETRY")
                                        .font(.caption2.weight(.bold))
                                }
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.standard)
                                .padding(.vertical, Theme.Spacing.tight)
                                .background(Theme.securityGold.opacity(0.08))
                                .cornerRadius(Theme.CornerRadius.tight)
                            }
                            .padding(.top, Theme.Spacing.small)
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    } else if !charts.isEmpty {
                        ScrollView(.horizontal) {
                            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                                ForEach(charts) { chart in
                                    chartCard(chart)
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        .scrollIndicators(.hidden)
                    } else {
                        // Empty state — charts will populate after backend generates them
                        HStack(spacing: Theme.Spacing.medium) {
                            Image(systemName: "chart.bar")
                                .font(.subheadline)
                                .foregroundStyle(Theme.inkTertiary.opacity(0.6))
                            Text("Charts will appear here after portfolio snapshot is generated")
                                .font(.caption)
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                }
                .onAppear { fetchCharts() }
                .sheet(item: $expandedChart) { chart in
                    expandedChartView(chart)
                }
            }

            private func chartCard(_ chart: ChartItem) -> some View {
                let cardWidth = UIScreen.main.bounds.width * 0.85
                let imageHeight = UIScreen.main.bounds.height * 0.22
                return Button(action: { HapticManager.selection();  HapticManager.selection()
                    HapticManager.impact(.light)
                    expandedChart = chart
                }) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        // Chart image
                        AsyncImage(url: URL(string: "\(NetworkManager.shared.baseURL)\(chart.url)")) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: cardWidth, height: imageHeight)
                                    .clipped()
                                    .cornerRadius(Theme.CornerRadius.tight)
                            case .failure(_):
                                Rectangle()
                                    .fill(Theme.inkTertiary.opacity(0.08))
                                    .frame(width: cardWidth, height: imageHeight)
                                    .cornerRadius(Theme.CornerRadius.tight)
                                    .overlay(
                                        Image(systemName: "chart.bar.xaxis")
                                            .font(.title2)
                                            .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                                    )
                            case .empty:
                                Rectangle()
                                    .fill(Theme.inkTertiary.opacity(0.06))
                                    .frame(width: cardWidth, height: imageHeight)
                                    .cornerRadius(Theme.CornerRadius.tight)
                                    .overlay(ProgressView().tint(Theme.securityGold))
                            @unknown default:
                                EmptyView()
                            }
                        }

                        // Title and description
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(chart.title)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Theme.inkPrimary)
                                .lineLimit(1)

                            Text(chart.description)
                                .font(.caption2)
                                .foregroundStyle(Theme.inkTertiary)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.horizontal, Theme.Spacing.small)
                    }
                    .frame(width: cardWidth)
                    .padding(Theme.Spacing.medium)
                    .background(Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.large)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                    )
                }
                .buttonStyle(EKPressStyle())
            }

            private func expandedChartView(_ chart: ChartItem) -> some View {
                NavigationStack {
                    ZStack {
                        Theme.canvas.ignoresSafeArea()

                        VStack(spacing: Theme.Spacing.none) {
                            // Toolbar
                            HStack {
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(chart.title)
                                        .font(.subheadline.weight(.bold))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(chart.description)
                                        .font(.caption)
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                Spacer()
                                Button("Done") { expandedChart = nil }.buttonStyle(EKPressStyle())
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(Theme.securityGold)
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(Theme.canvasDeep)

                            // Full chart image
                            ScrollView([.horizontal, .vertical]) {
                                AsyncImage(url: URL(string: "\(NetworkManager.shared.baseURL)\(chart.url)")) { phase in
                                    switch phase {
                                    case .success(let image):
                                        image
                                            .resizable()
                                            .aspectRatio(contentMode: .fit)
                                    case .failure(_):
                                        VStack(spacing: Theme.Spacing.standard) {
                                            Image(systemName: "exclamationmark.triangle")
                                                .font(.largeTitle)
                                                .foregroundStyle(Theme.holdAmber)
                                            Text("Failed to load chart image")
                                                .font(.footnote)
                                                .foregroundStyle(Theme.inkSecondary)
                                        }
                                        .frame(maxWidth: .infinity, minHeight: 300)
                                    case .empty:
                                        ProgressView()
                                            .frame(maxWidth: .infinity, minHeight: 300)
                                    @unknown default:
                                        EmptyView()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            private func fetchCharts() {
                guard !isLoading else { return }
                isLoading = true
                errorMsg = nil
                Task {
                    do {
                        let resp = try await NetworkManager.shared.fetchPortfolioCharts(userId: userId)
                        await MainActor.run {
                            charts = resp.charts
                            isLoading = false
                        }
                    } catch {
                        await MainActor.run {
                            errorMsg = error.localizedDescription
                            isLoading = false
                        }
                    }
                }
            }
        }

struct PortfolioBriefSheet: View {
    let portfolioValue: Double
    let pnl: Double
    let holdings: [PortfolioHolding]
    @Environment(\.dismiss) var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("PORTFOLIO BRIEF")
                            .font(Theme.officialStampFont(size: 10)).tracking(1.5)
                            .foregroundStyle(Theme.securityGold)
                        Text("Your snapshot")
                            .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer()
                    Button(action: { HapticManager.selection();  HapticManager.selection(); dismiss() }) {.buttonStyle(EKPressStyle())
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2).foregroundStyle(Theme.inkTertiary)
                    }.buttonStyle(EKPressStyle())
                }

                SectionGuillocheDivider()

                // Summary
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("VALUE").font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.priceCompact(portfolioValue))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline)).foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("P&L").font(Theme.officialStampFont(size: 7)).tracking(1.2).foregroundStyle(Theme.inkTertiary)
                        let isUp = pnl >= 0
                        Text((isUp ? "+" : "") + IndianFormatter.priceCompact(abs(pnl)))
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                            .foregroundStyle(isUp ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                .padding(Theme.Spacing.card).banknoteCard()

                SectionGuillocheDivider()

                // Top 3 performers
                Text("TOP PERFORMERS")
                    .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                ForEach(Array(holdings.sorted { $0.pnlPercent > $1.pnlPercent }.prefix(3))) { (h: PortfolioHolding) in
                    HStack {
                        Text(h.stock.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        Text(IndianFormatter.percent(h.pnlPercent))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.bullGreen)
                    }
                    .padding(.vertical, Theme.Spacing.small)
                }

                SectionGuillocheDivider()

                // Bottom 3 performers
                Text("NEEDS ATTENTION")
                    .font(Theme.officialStampFont(size: 9)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                ForEach(Array(holdings.sorted { $0.pnlPercent < $1.pnlPercent }.prefix(3))) { (h: PortfolioHolding) in
                    HStack {
                        Text(h.stock.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        Text(IndianFormatter.percent(h.pnlPercent))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.bearRed)
                    }
                    .padding(.vertical, Theme.Spacing.small)
                }
            }
            .padding(Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

// MARK: - Quick Transaction Sheet

struct QuickTransactionSheet: View {
    @Environment(\.dismiss) var dismiss
    @State private var transactionType: TransactionType = .buy
    @State private var ticker = ""
    @State private var quantity = ""
    @State private var price = ""
    @State private var isSubmitting = false

    enum TransactionType { case buy, sell }

    var body: some View {
        NavigationStack {
            VStack(spacing: Theme.Spacing.large) {
                // BUY / SELL toggle
                HStack(spacing: Theme.Spacing.none) {
                    ForEach([TransactionType.buy, .sell], id: \.self) { type in
                        Button(action: { HapticManager.selection();  HapticManager.selection(); transactionType = type }) {.buttonStyle(EKPressStyle())
                            Text(type == .buy ? "BUY" : "SELL")
                                .font(Theme.officialStampFont(size: 11)).tracking(1.5)
                                .foregroundStyle(transactionType == type ? Theme.canvas : Theme.inkSecondary)
                                .frame(maxWidth: .infinity).padding(.vertical, Theme.Spacing.standard)
                                .background(
                                    transactionType == type
                                        ? (type == .buy ? Theme.bullGreen : Theme.bearRed)
                                        : Theme.canvasDeep
                                )
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                .padding(.horizontal, Theme.screenPadding)

                // Ticker field
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("TICKER SYMBOL")
                        .font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                    TextField("e.g. RELIANCE", text: $ticker)
                        .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                        .textInputAutocapitalization(.characters)
                        .padding(Theme.Spacing.card).banknoteCard()
                }.padding(.horizontal, Theme.screenPadding)

                // Quantity + Price fields
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("QTY").font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                        TextField("0", text: $quantity).keyboardType(.numberPad)
                            .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                            .padding(Theme.Spacing.card).banknoteCard()
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("PRICE ₹").font(Theme.officialStampFont(size: 8)).tracking(1.5).foregroundStyle(Theme.inkTertiary)
                        TextField("0.00", text: $price).keyboardType(.decimalPad)
                            .font(Theme.serialNumberFont(size: 16)).foregroundStyle(Theme.inkPrimary)
                            .padding(Theme.Spacing.card).banknoteCard()
                    }
                }.padding(.horizontal, Theme.screenPadding)

                Spacer()

                // Submit button
                Button(action: { HapticManager.selection(); submitTransaction() }) {.buttonStyle(EKPressStyle())
                    Text(isSubmitting ? "LOGGING..." : "LOG \(transactionType == .buy ? "BUY" : "SELL")")
                        .font(Theme.officialStampFont(size: 11)).tracking(1.5)
                        .foregroundStyle(Theme.canvas).frame(maxWidth: .infinity)
                        .padding(Theme.Spacing.card)
                        .background(transactionType == .buy ? Theme.bullGreen : Theme.bearRed)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }
                .buttonStyle(EKPressStyle())
                .padding(.horizontal, Theme.screenPadding)
                .disabled(ticker.isEmpty || quantity.isEmpty || price.isEmpty || isSubmitting)
            }
            .padding(.top, Theme.Spacing.large)
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Quick Transaction")
            .navigationBarTitleDisplayMode(.inline)
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }

    private func submitTransaction() {
        isSubmitting = true
        HapticManager.impact(.medium)
        // POST to existing transaction endpoint
        Task {
            do {
                // Placeholder: call transaction API here
                try await Task.sleep(nanoseconds: 800_000_000)
                await MainActor.run {
                    HapticManager.success()
                    isSubmitting = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    HapticManager.error()
                    isSubmitting = false
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
