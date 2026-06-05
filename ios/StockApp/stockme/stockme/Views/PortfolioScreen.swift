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

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .twoThousand)

                VStack(spacing: 0) {
                    // Content anchored to safe area — fixes left-edge cutoff
                    // Bilingual header
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("निवेश पोर्टफोलियो")
                                .font(Theme.hindiFont(size: 11))
                                .foregroundColor(Theme.inkSecondary)
                            Text("MY PORTFOLIO")
                                .font(Theme.engravedSerif(size: 28, weight: .bold))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        Spacer()
                        HStack(spacing: 12) {
                            Button { showExportOptions = true } label: {
                                Image(systemName: "square.and.arrow.up")
                                    .foregroundColor(Theme.inkSecondary)
                                    .padding(8)
                            }
                            ZStack {
                                Circle().stroke(Theme.borderSage, lineWidth: 0.5).frame(width: 44, height: 44)
                                Text("₹").font(Theme.engravedSerif(size: 18, weight: .bold)).foregroundColor(Theme.inkPrimary)
                            }
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 12)
                    .padding(.bottom, 20)

                    ScrollView {
                        VStack(spacing: Theme.sectionSpacing) {
                            PortfolioHeroNote(
                                value: viewModel.totalValue,
                                totalPnL: viewModel.totalValue - viewModel.investedValue,
                                invested: viewModel.investedValue,
                                todayPnL: viewModel.todayPnL,
                                count: viewModel.holdings.count,
                                isLoading: viewModel.isLoading
                            )
                            .padding(.horizontal, Theme.screenPadding)

                            PortfolioRiskCard(riskAnalysis: riskAnalysis)
                                .padding(.horizontal, Theme.screenPadding)

                            RedFlagsSection(redFlags: redFlags)
                                .padding(.horizontal, Theme.screenPadding)

                            if let user = authManager.currentUser {
                                ValuationCalendarView(userId: user.userId)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            if !viewModel.holdings.isEmpty {
                                PortfolioChartsCarousel(holdings: viewModel.holdings)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            if let user = authManager.currentUser {
                                PortfolioChartsStrip(userId: user.userId)
                                    .padding(.horizontal, Theme.screenPadding)
                            }

                            HStack(spacing: 0) {
                                TabNoteButton(title: "Holdings", isSelected: selectedTab == 0) { selectedTab = 0 }
                                TabNoteButton(title: "Watchlist", isSelected: selectedTab == 1) { selectedTab = 1 }
                                TabNoteButton(title: "Journal", isSelected: selectedTab == 2) { selectedTab = 2 }
                            }
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)

                            if selectedTab == 0 {
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 12) {
                                        ForEach(viewModel.holdings) { holding in
                                            NavigationLink(value: HoldingNavValue(ticker: holding.stock.ticker, userNote: holding.notes, purchaseDateStr: holding.purchaseDate, holding: holding)) {
                                                HoldingNoteRow(holding: holding, signalWarning: signalWarnings[holding.stock.ticker])
                                                    .frame(width: 300)
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
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                }
                            } else if selectedTab == 1 {
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 12) {
                                        ForEach(viewModel.watchlistItems) { item in
                                            NavigationLink(value: item.ticker) {
                                                WatchlistRowView(item: item) {
                                                    guard let user = authManager.currentUser else { return }
                                                    Task { await viewModel.removeFromWatchlist(ticker: item.ticker, userId: user.userId) }
                                                }
                                                .frame(width: 300)
                                            }
                                            .buttonStyle(.plain)
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                }
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
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(Theme.bullGreen)
                            Text("\(addedBannerTicker) added to watchlist")
                                .font(Theme.serialNumberFont(size: 13))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 12)
                        .background(Theme.canvas)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .shadow(color: .black.opacity(0.12), radius: 8, x: 0, y: 4)
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.bullGreen.opacity(0.4), lineWidth: 1))
                        .padding(.top, 60)
                        Spacer()
                    }
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .zIndex(10)
                    .animation(.spring(response: 0.4), value: showAddedBanner)
                }

                // FAB — show "+" on Holdings or Watchlist tab to add
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        Button {
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
                                    .frame(width: 56, height: 56)
                                    .shadow(color: Theme.securityGold.opacity(0.3), radius: 10, x: 0, y: 5)
                                Image(systemName: "plus")
                                    .font(.system(size: 24, weight: .bold))
                                    .foregroundColor(.white)
                            }
                        }
                        .padding(Theme.screenPadding)
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
        .alert("Remove \(deletingTicker)?", isPresented: $showDeleteAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Remove", role: .destructive) {
                if let user = authManager.currentUser {
                    Task {
                        try? await viewModel.removeHolding(ticker: deletingTicker, userId: user.userId)
                    }
                }
            }
        } message: {
            Text("This will permanently remove \(deletingTicker) from your portfolio.")
        }
        .confirmationDialog("Export Portfolio", isPresented: $showExportOptions, titleVisibility: .visible) {
            Button("Export as Excel (.xlsx)") {
                if let user = authManager.currentUser {
                    Task { await exportAsExcel(userId: user.userId) }
                }
            }
            Button("Cancel", role: .cancel) {}
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = exportedFileURL {
                ShareSheet(items: [url])
            }
        }
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

    @ViewBuilder
    private var watchlistTabContent: some View {
        if viewModel.watchlistLoading {
            VStack(spacing: 12) {
                ForEach(0..<3, id: \.self) { _ in
                    WatchlistSkeletonRow()
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        } else if viewModel.watchlistItems.isEmpty {
            VStack(spacing: 20) {
                BanknoteSignalBadge(text: "EMPTY", color: Theme.inkSecondary.opacity(0.4))
                Text("Add stocks to your watchlist to track them here")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundColor(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                Button {
                    addSheetSearchText = ""
                    showAddWatchlistSheet = true
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "plus.circle")
                        Text("ADD STOCK")
                            .font(Theme.officialStampFont(size: 10))
                    }
                    .foregroundColor(Theme.securityGold)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.securityGold, lineWidth: 1))
                }
            }
            .padding(.top, 40)
        } else {
            VStack(spacing: 12) {
                ForEach(viewModel.watchlistItems) { item in
                    NavigationLink(value: item.ticker) {
                        WatchlistRowView(item: item) {
                            guard let user = authManager.currentUser else { return }
                            Task { await viewModel.removeFromWatchlist(ticker: item.ticker, userId: user.userId) }
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

// MARK: - Portfolio Risk Card

private struct PortfolioRiskCard: View {
    let riskAnalysis: RiskAnalysis?

    var riskColor: Color {
        guard let score = riskAnalysis?.riskScore else { return Theme.securityGold }
        if score <= 4 { return Theme.signalEmerald }
        if score <= 6 { return Theme.securityGold }
        return Theme.signalRuby
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("PORTFOLIO RISK")
                    .font(.system(.caption, design: .default).weight(.medium))
                    .tracking(1.5)
                    .foregroundColor(Theme.securityGold)
                Spacer()
                if let label = riskAnalysis?.riskScoreLabel {
                    Text(label)
                        .font(.caption2)
                        .foregroundColor(riskColor)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(riskColor.opacity(0.15))
                        .cornerRadius(4)
                }
            }

            // Risk meter — 10 segments
            if let score = riskAnalysis?.riskScore {
                HStack(spacing: 3) {
                    ForEach(1...10, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 2)
                            .fill(i <= score ? riskColor : Theme.canvasDeep)
                            .frame(height: 8)
                    }
                }
            }

            // Beta
            if let beta = riskAnalysis?.portfolioBeta {
                Text("β \(String(format: "%.2f", beta))")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(Theme.inkSecondary)
            }

            // Concentration warnings
            if let warnings = riskAnalysis?.concentrationRisks, !warnings.isEmpty {
                HStack(spacing: 6) {
                    ForEach(warnings) { w in
                        Text("\(w.ticker) \(String(format: "%.0f", w.pctOfPortfolio))%")
                            .font(.caption2)
                            .foregroundColor(.white)
                            .padding(.horizontal, 5).padding(.vertical, 2)
                            .background(Theme.signalRuby)
                            .cornerRadius(3)
                    }
                }
            }

            // Correlation warning
            if let pair = riskAnalysis?.highestCorrelationPair, pair.correlation > 0.7 {
                Text("\(pair.tickerA) ↔ \(pair.tickerB) highly correlated")
                    .font(.caption)
                    .foregroundColor(Theme.securityGold)
            }

            // Summary
            if let summary = riskAnalysis?.riskSummary {
                Text(summary)
                    .font(.system(size: 12, design: .serif).italic())
                    .foregroundColor(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding()
        .background(Theme.canvasDeep)
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

// MARK: - Red Flags Section

private struct RedFlagsSection: View {
    let redFlags: RedFlagsResponse?
    @State private var isExpanded = false

    var body: some View {
        if let rf = redFlags, rf.totalFlags > 0 {
            VStack(alignment: .leading, spacing: 8) {
                // Header
                Button(action: { withAnimation(.easeInOut(duration: 0.25)) { isExpanded.toggle() } }) {
                    HStack {
                        Text("⚠")
                            .font(.caption)
                        Text("RED FLAGS")
                            .font(.system(.caption, design: .default).weight(.medium))
                            .tracking(1.5)
                            .foregroundColor(Theme.signalRuby)
                        Text("\(rf.totalFlags)")
                            .font(.caption2.weight(.bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Theme.signalRuby)
                            .clipShape(Capsule())
                        Spacer()
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                            .foregroundColor(Theme.inkSecondary)
                    }
                }
                .buttonStyle(.plain)

                if isExpanded {
                    ForEach(rf.flags) { flag in
                        NavigationLink(value: flag.ticker) {
                            HStack(alignment: .top, spacing: 8) {
                                Text(flag.severity == "CRITICAL" ? "🔴" : flag.severity == "WARNING" ? "🟡" : "🔵")
                                    .font(.caption)
                                VStack(alignment: .leading, spacing: 2) {
                                    HStack {
                                        Text(flag.ticker)
                                            .font(.system(.caption, design: .monospaced).weight(.bold))
                                            .foregroundColor(Theme.inkPrimary)
                                        Text(flag.flagType.replacingOccurrences(of: "_", with: " "))
                                            .font(.caption2)
                                            .foregroundColor(Theme.inkSecondary)
                                            .tracking(0.5)
                                    }
                                    Text(flag.detail)
                                        .font(.caption2)
                                        .foregroundColor(Theme.inkSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.system(size: 9))
                                    .foregroundColor(Theme.inkTertiary)
                            }
                        }
                        .buttonStyle(.plain)
                    }

                    if let summary = rf.summary, !summary.isEmpty {
                        Text(summary)
                            .font(.system(size: 11, design: .serif).italic())
                            .foregroundColor(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 4)
                    }
                }
            }
            .padding()
            .background(Theme.canvasDeep)
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.signalRuby.opacity(0.3), lineWidth: 0.5))
        }
    }
}

private struct TabNoteButton: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: {
            HapticManager.selection()
            action()
        }) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundColor(isSelected ? Theme.inkPrimary : Theme.inkTertiary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
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

private struct HoldingNoteRow: View {
    let holding: PortfolioHolding
    var signalWarning: SignalWarning? = nil

    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(holding.pnl >= 0 ? Theme.bullGreen.opacity(0.3) : Theme.bearRed.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, 12)

            HStack(spacing: 16) {
                StockIcon(ticker: holding.stock.ticker, signal: holding.pnl >= 0 ? .bullish : .bearish)

                VStack(alignment: .leading, spacing: 2) {
                    Text(holding.stock.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    Text("\(Int(holding.shares)) SHARES • AVG ₹\(holding.buyPrice.inrFormatted)")
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)
                    if let note = holding.notes, !note.isEmpty {
                        Text(note)
                            .font(Font.custom("Georgia", size: 12).italic())
                            .foregroundColor(Theme.inkSecondary)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                    if let warning = signalWarning {
                        HStack(spacing: 4) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 9))
                            Text(warning.signalFlipped ? "SIGNAL CHANGED" : "BEARISH")
                                .font(Theme.officialStampFont(size: 7))
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Theme.bearRed)
                        .clipShape(Capsule())
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 2) {
                    Text(holding.currentValue.inrFormatted)
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundColor(Theme.inkPrimary)
                    Text(holding.pnl.inrFormatted)
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundColor(holding.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }
            .padding(.vertical, 14)
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
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

            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text("NIVESH")
                            .font(Theme.engravedSerif(size: 14, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                        Text("Reserve Bank of Intelligence")
                            .font(Theme.serialNumberFont(size: 8))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                    Text("भारतीय निवेश")
                        .font(Theme.hindiFont(size: 11))
                        .foregroundColor(Theme.inkSecondary)
                }
                .padding(.bottom, 8)

                GuillocheDivider()

                VStack(alignment: .leading, spacing: 4) {
                    Text("निवेश पोर्टफोलियो")
                        .font(Theme.hindiFont(size: 11))
                        .foregroundColor(Theme.inkSecondary)

                    Text("TOTAL VALUATION")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)

                    Text("I PROMISE TO PAY THE BEARER")
                        .font(.system(size: 8, weight: .medium))
                        .tracking(2)
                        .foregroundColor(Theme.inkTertiary)
                        .padding(.bottom, 2)

                    PortfolioValueDisplay(target: value, fontSize: 30)

                    HStack(spacing: 8) {
                        Text(totalPnL >= 0 ? "SURPLUS" : "DEFICIT")
                        Text(totalPnL.inrFormatted)
                        Text("(\((invested > 0 ? totalPnL/invested*100 : 0).percentFormatted))")
                    }
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundColor(totalPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                .padding(.top, 4)

                GuillocheDivider()

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
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .foregroundColor(Theme.inkSecondary)
            Text(value)
                .font(Theme.serialNumberFont(size: 14))
                .foregroundColor(color)
        }
    }
}

private struct WatchlistRowView: View {
    let item: WatchlistItem
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            // Left sage-green rule (no P&L signal)
            Rectangle()
                .fill(Theme.borderSage.opacity(0.6))
                .frame(width: 1)
                .padding(.vertical, 12)

            HStack(spacing: 16) {
                StockIcon(ticker: item.ticker, signal: nil)

                VStack(alignment: .leading, spacing: 2) {
                    Text(item.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(1)
                    Text(item.ticker)
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 2) {
                    Text("₹\(item.currentPrice.inrFormatted)")
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundColor(Theme.inkPrimary)
                    let changeStr = (item.dayChangePct >= 0 ? "+" : "") + String(format: "%.2f%%", item.dayChangePct)
                    Text(changeStr)
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundColor(item.dayChangePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }
            .padding(.vertical, 14)
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
    }
}

private struct WatchlistSkeletonRow: View {
    var body: some View {
        HStack(spacing: 16) {
            Circle()
                .fill(Theme.inkTertiary.opacity(0.1))
                .frame(width: 40, height: 40)
            VStack(alignment: .leading, spacing: 6) {
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.15)).frame(width: 130, height: 12)
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.1)).frame(width: 60, height: 9)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 6) {
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.15)).frame(width: 70, height: 12)
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.1)).frame(width: 40, height: 9)
            }
        }
        .padding(.vertical, 14)
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
                VStack(spacing: 0) {
                    // Stock search
                    VStack(alignment: .leading, spacing: 0) {
                        HStack {
                            Image(systemName: "magnifyingglass").foregroundColor(Theme.inkTertiary)
                            if let entry = selectedEntry {
                                HStack(spacing: 6) {
                                    Text(entry.ticker)
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundColor(Theme.inkPrimary)
                                    Text(entry.companyName)
                                        .font(Theme.serialNumberFont(size: 12))
                                        .foregroundColor(Theme.inkSecondary)
                                        .lineLimit(1)
                                    Spacer()
                                    Button {
                                        selectedEntry = nil
                                        searchText = ""
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .foregroundColor(Theme.inkTertiary)
                                    }
                                }
                            } else {
                                TextField("Search stock…", text: $searchText)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundColor(Theme.inkPrimary)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                            }
                        }
                        .padding(12)
                        .background(Theme.inkPrimary.opacity(0.05))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, 16)
                        
                        if selectedEntry == nil && !searchResults.isEmpty {
                            List(searchResults) { entry in
                                Button {
                                    selectedEntry = entry
                                    searchText = entry.ticker
                                } label: {
                                    HStack(spacing: 14) {
                                        StockIcon(ticker: entry.ticker, signal: nil)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 13, weight: .bold))
                                                .foregroundColor(Theme.inkPrimary)
                                            Text(entry.ticker)
                                                .font(Theme.serialNumberFont(size: 10))
                                                .foregroundColor(Theme.inkSecondary)
                                        }
                                        Spacer()
                                        Image(systemName: "checkmark.circle")
                                            .foregroundColor(Theme.securityGold)
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
                    VStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("NUMBER OF SHARES")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            TextField("e.g. 100", text: $sharesText)
                                .keyboardType(.numberPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(12)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        
                        VStack(alignment: .leading, spacing: 6) {
                            Text("BUY PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            TextField("e.g. 1530.00", text: $buyPriceText)
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(12)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text("PURCHASE DATE")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            DatePicker("", selection: $purchaseDate, displayedComponents: .date)
                                .labelsHidden()
                                .accentColor(Theme.securityGold)
                                .padding(8)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .cornerRadius(8)
                        }
                        
                        VStack(alignment: .leading, spacing: 6) {
                            Text("TARGET PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            TextField("optional...", text: $targetPriceText)
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(12)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        
                        VStack(alignment: .leading, spacing: 6) {
                            Text("NOTES / INVESTMENT REASON")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            TextField("Why did you buy this?", text: $notes)
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(12)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        
                        if let err = errorText {
                            Text(err)
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundColor(Theme.bearRed)
                                .multilineTextAlignment(.center)
                        }
                        
                        Button {
                            guard let entry = selectedEntry, let user = authManager.currentUser else { return }
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
                            HStack(spacing: 8) {
                                if isAdding {
                                    ProgressView().tint(.white)
                                }
                                Text(isAdding ? "ADDING…" : "ADD TO PORTFOLIO")
                                    .font(Theme.officialStampFont(size: 11))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(canAdd ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                            .foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
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
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.securityGold)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundColor(Theme.inkSecondary)
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
                    VStack(spacing: 24) {
                        // Read-only stock info
                        HStack(spacing: 16) {
                            StockIcon(ticker: holding.stock.ticker, signal: nil)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 15, weight: .bold))
                                    .foregroundColor(Theme.inkPrimary)
                                Text(holding.stock.ticker)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundColor(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, 24)
                        
                        VStack(spacing: 16) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("NUMBER OF SHARES")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                                TextField("Shares", text: $sharesText)
                                    .keyboardType(.numberPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundColor(Theme.inkPrimary)
                                    .padding(12)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                            
                            VStack(alignment: .leading, spacing: 6) {
                                Text("BUY PRICE (₹)")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                                TextField("Buy Price", text: $buyPriceText)
                                    .keyboardType(.decimalPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundColor(Theme.inkPrimary)
                                    .padding(12)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                            
                            if let err = errorText {
                                Text(err)
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundColor(Theme.bearRed)
                                    .multilineTextAlignment(.center)
                            }
                            
                            Button {
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
                                HStack(spacing: 8) {
                                    if isSaving {
                                        ProgressView().tint(.white)
                                    }
                                    Text(isSaving ? "SAVING…" : "SAVE CHANGES")
                                        .font(Theme.officialStampFont(size: 11))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(canSave ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                                .foregroundColor(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
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
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.securityGold)
                    }
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundColor(Theme.inkSecondary)
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
                        VStack(spacing: 20) {
                            // Header
                            VStack(alignment: .leading, spacing: 4) {
                                Text("अपना नोट / PERSONAL NOTE")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 18, weight: .bold))
                                    .foregroundColor(Theme.inkPrimary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 20)
                            
                            // Text editor
                            TextEditor(text: $noteText)
                                .font(Theme.engravedSerif(size: 15))
                                .foregroundColor(Theme.inkPrimary)
                                .frame(minHeight: 150)
                                .padding(16)
                                .background(Theme.canvasDeep)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.borderSage, lineWidth: 1))
                                .padding(.horizontal, 20)
                            
                            // Character count
                            Text("\(noteText.count)/280 characters")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundColor(noteText.count > 280 ? Theme.bearRed : Theme.inkTertiary)
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
                            Button("Cancel") { dismiss() }
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
                        
                        VStack(spacing: 0) {
                            HStack {
                                Image(systemName: "magnifyingglass")
                                    .foregroundColor(Theme.inkTertiary)
                                TextField("Search stocks…", text: $searchText)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundColor(Theme.inkPrimary)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                            }
                            .padding(12)
                            .background(Theme.inkPrimary.opacity(0.05))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, 16)
                            .padding(.bottom, 8)
                            
                            List(results) { entry in
                                Button {
                                    onAdd(entry)
                                } label: {
                                    HStack(spacing: 14) {
                                        StockIcon(ticker: entry.ticker, signal: nil)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 14, weight: .bold))
                                                .foregroundColor(Theme.inkPrimary)
                                            HStack(spacing: 6) {
                                                Text(entry.ticker)
                                                    .font(Theme.serialNumberFont(size: 10))
                                                    .foregroundColor(Theme.inkSecondary)
                                                Text("·")
                                                    .foregroundColor(Theme.inkTertiary)
                                                Text(entry.sector)
                                                    .font(Theme.serialNumberFont(size: 10))
                                                    .foregroundColor(Theme.inkTertiary)
                                            }
                                        }
                                        Spacer()
                                        Image(systemName: "plus.circle")
                                            .foregroundColor(Theme.securityGold)
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
                            Button("Cancel") { dismiss() }
                                .font(Theme.serialNumberFont(size: 13))
                                .foregroundColor(Theme.inkSecondary)
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
                VStack(spacing: 8) {
                    TabView(selection: $page) {
                        ScrollView {
                            PortfolioAllocationChart(holdings: holdings)
                                .padding(20)
                        }
                        .banknoteCard()
                        .tag(0)
                        
                        ScrollView {
                            PnLWaterfallChart(holdings: holdings)
                                .padding(20)
                        }
                        .banknoteCard()
                        .tag(1)
                        
                        ScrollView {
                            SectorHeatmapView(sectors: sectorData)
                                .padding(20)
                        }
                        .banknoteCard()
                        .tag(2)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .always))
                    .frame(height: 480)
                    
                    Text("Swipe to explore →")
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundColor(Theme.inkTertiary)
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
                VStack(alignment: .leading, spacing: 12) {
                    // Section header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("पोर्टफोलियो चार्ट")
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        Text("PORTFOLIO CHARTS")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(Theme.inkPrimary.opacity(0.7))
                    }

                    if isLoading {
                        HStack(spacing: 12) {
                            ForEach(0..<3, id: \.self) { _ in
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(Theme.inkTertiary.opacity(0.08))
                                    .frame(width: 200, height: 160)
                            }
                        }
                        .shimmerPlaceholder(isLoading: true)
                    } else if let err = errorMsg {
                        // Compact error state
                        HStack(spacing: 8) {
                            Image(systemName: "chart.bar.xaxis")
                                .font(.system(size: 14))
                                .foregroundColor(Theme.inkTertiary)
                            Text("Charts unavailable")
                                .font(.system(size: 11))
                                .foregroundColor(Theme.inkTertiary)
                        }
                        .padding(.vertical, 12)
                    } else if !charts.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 12) {
                                ForEach(charts) { chart in
                                    chartCard(chart)
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        .frame(height: 240)
                    } else {
                        // Empty state — charts will populate after backend generates them
                        HStack(spacing: 8) {
                            Image(systemName: "chart.bar")
                                .font(.system(size: 14))
                                .foregroundColor(Theme.inkTertiary.opacity(0.6))
                            Text("Charts will appear here after portfolio snapshot is generated")
                                .font(.system(size: 11))
                                .foregroundColor(Theme.inkTertiary)
                        }
                        .padding(.vertical, 12)
                    }
                }
                .onAppear { fetchCharts() }
                .sheet(item: $expandedChart) { chart in
                    expandedChartView(chart)
                }
            }

            private func chartCard(_ chart: ChartItem) -> some View {
                Button(action: {
                    HapticManager.impact(.light)
                    expandedChart = chart
                }) {
                    VStack(alignment: .leading, spacing: 6) {
                        // Chart image
                        AsyncImage(url: URL(string: chart.url)) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 200, height: 130)
                                    .clipped()
                                    .cornerRadius(6)
                            case .failure(_):
                                Rectangle()
                                    .fill(Theme.inkTertiary.opacity(0.08))
                                    .frame(width: 200, height: 130)
                                    .cornerRadius(6)
                                    .overlay(
                                        Image(systemName: "chart.bar.xaxis")
                                            .font(.system(size: 24))
                                            .foregroundColor(Theme.inkTertiary.opacity(0.4))
                                    )
                            case .empty:
                                Rectangle()
                                    .fill(Theme.inkTertiary.opacity(0.06))
                                    .frame(width: 200, height: 130)
                                    .cornerRadius(6)
                                    .overlay(ProgressView().tint(Theme.securityGold))
                            @unknown default:
                                EmptyView()
                            }
                        }

                        // Title and description
                        VStack(alignment: .leading, spacing: 2) {
                            Text(chart.title)
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundColor(Theme.inkPrimary)
                                .lineLimit(1)

                            Text(chart.description)
                                .font(.system(size: 9))
                                .foregroundColor(Theme.inkTertiary)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.horizontal, 4)
                    }
                    .frame(width: 200)
                    .padding(8)
                    .background(Theme.canvasDeep)
                    .cornerRadius(10)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                    )
                }
                .buttonStyle(EKPressStyle())
            }

            private func expandedChartView(_ chart: ChartItem) -> some View {
                NavigationStack {
                    ZStack {
                        Theme.canvas.ignoresSafeArea()

                        VStack(spacing: 0) {
                            // Toolbar
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(chart.title)
                                        .font(.system(size: 14, weight: .bold))
                                        .foregroundColor(Theme.inkPrimary)
                                    Text(chart.description)
                                        .font(.system(size: 11))
                                        .foregroundColor(Theme.inkSecondary)
                                }
                                Spacer()
                                Button("Done") { expandedChart = nil }
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Theme.securityGold)
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .background(Theme.canvasDeep)

                            // Full chart image
                            ScrollView([.horizontal, .vertical]) {
                                AsyncImage(url: URL(string: chart.url)) { phase in
                                    switch phase {
                                    case .success(let image):
                                        image
                                            .resizable()
                                            .aspectRatio(contentMode: .fit)
                                    case .failure(_):
                                        VStack(spacing: 12) {
                                            Image(systemName: "exclamationmark.triangle")
                                                .font(.system(size: 32))
                                                .foregroundColor(Theme.holdAmber)
                                            Text("Failed to load chart image")
                                                .font(.system(size: 13))
                                                .foregroundColor(Theme.inkSecondary)
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

        struct ShareSheet: UIViewControllerRepresentable {
            let items: [Any]
            func makeUIViewController(context: Context) -> UIActivityViewController {
                UIActivityViewController(activityItems: items, applicationActivities: nil)
            }
            func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
        }
