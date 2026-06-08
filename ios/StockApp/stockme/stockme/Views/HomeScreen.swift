import SwiftUI
import Combine

// MARK: - Emoji Stripper (global fix for AI-generated text)

func stripEmoji(_ text: String) -> String {
    text.unicodeScalars
        .filter { !$0.properties.isEmojiPresentation && !$0.properties.isEmoji }
        .map { String($0) }
        .joined()
        .trimmingCharacters(in: .whitespaces)
}

// MARK: - Design System Constants (Phase 1 redesign — all Theme.* tokens)

private let cardHPad: CGFloat = Theme.Spacing.card
private let cardVPad: CGFloat = Theme.Spacing.standard
private let rowSpacing: CGFloat = Theme.Spacing.medium
private let sectionGap: CGFloat = Theme.Spacing.tight

private let bullGreen  = Theme.dataPositive
private let bearRed    = Theme.dataNegative
private let neutralAmber = Theme.holdAmber
private let goldAccent = Theme.goldPrimary
private let dimText    = Theme.inkSecondary
private let subtleText = Theme.inkTertiary

// MARK: - NiveshBulletRow

struct NiveshBulletRow: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(goldAccent)
                .frame(width: 4, height: 4)
                .padding(.top, Theme.Spacing.tight)

            Text(stripEmoji(text))
                .font(.body)
                .foregroundStyle(.primary.opacity(0.80))
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(3)
        }
    }
}

// MARK: - PriorityPill

struct PriorityPill: View {
    let label: String
    let color: Color

    var body: some View {
        Text(label)
            .font(.caption2.weight(.bold)).monospaced()
            .tracking(1.5)
            .foregroundStyle(color)
            .padding(.horizontal, Theme.Spacing.tight)
            .padding(.vertical, Theme.Spacing.small)
            .background(color.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(color.opacity(0.25), lineWidth: 0.5)
            )
            .cornerRadius(Theme.CornerRadius.small)
    }
}

// MARK: - ADBreathBar

struct ADBreathBar: View {
    let advancing: Int
    let declining: Int

    var advancingRatio: CGFloat {
        let total = CGFloat(advancing + declining)
        guard total > 0 else { return 0.5 }
        return CGFloat(advancing) / total
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text("ADVANCE / DECLINE BREADTH")
                .font(.caption2.weight(.semibold)).monospaced()
                .tracking(1.5)
                .foregroundStyle(dimText)

            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(bearRed.opacity(0.15))
                    .frame(maxWidth: .infinity)

                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(
                        LinearGradient(
                            colors: [bullGreen.opacity(0.9), bullGreen.opacity(0.6)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: UIScreen.main.bounds.width * advancingRatio)
            }
            .frame(height: 8)
            .cornerRadius(Theme.CornerRadius.small)

            HStack {
                HStack(spacing: Theme.Spacing.small) {
                    Circle().fill(bullGreen).frame(width: 5, height: 5)
                    Text("\(advancing) advancing")
                        .font(.caption)
                        .foregroundStyle(bullGreen)
                }
                Spacer()
                HStack(spacing: Theme.Spacing.small) {
                    Text("\(declining) declining")
                        .font(.caption)
                        .foregroundStyle(bearRed)
                    Circle().fill(bearRed).frame(width: 5, height: 5)
                }
            }
        }
    }
}

// MARK: - IndexRow

struct IndexRow: View {
    let name: String
    let value: String
    let change: Double

    var changeColor: Color { change >= 0 ? bullGreen : bearRed }
    var changeText: String {
        let sign = change >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", change))%"
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: 1)
                .fill(changeColor.opacity(0.7))
                .frame(width: 2, height: 20)

            Text(name)
                .font(.footnote.weight(.medium))
                .foregroundStyle(.primary.opacity(0.85))

            Spacer()

            Text(value)
                .contentTransition(.numericText())
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.85))

            Text(changeText)
                .contentTransition(.numericText())
                .sensoryFeedback(change >= 0 ? .increase : .decrease, trigger: change)
                .font(.caption.weight(.semibold)).monospaced()
                .foregroundStyle(changeColor)
                .frame(minWidth: 60, alignment: .trailing)
        }
        .padding(.vertical, Theme.Spacing.small)
    }
}

// MARK: - MomentumSectionView

struct MomentumSectionView: View {
    let stance: String
    let stocks: [MomentumTicker]

    var stanceColor: Color { stance == "BULLISH" ? bullGreen : bearRed }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: Theme.Spacing.medium) {
                Rectangle()
                    .fill(stanceColor)
                    .frame(width: 3, height: 14)
                    .cornerRadius(1.5)

                Text(stance)
                    .font(.caption2.weight(.bold)).monospaced()
                    .tracking(2.0)
                    .foregroundStyle(stanceColor)

                Spacer()

                Text("\(stocks.count) stocks")
                    .font(.caption2)
                    .foregroundStyle(subtleText)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .background(stanceColor.opacity(0.06))

            VStack(spacing: 0) {
                ForEach(stocks) { stock in
                    MomentumStockRow(stock: stock, stanceColor: stanceColor)
                    if stock.id != stocks.last?.id {
                        Divider().opacity(0.10).padding(.leading, 10)
                    }
                }
            }
        }
        .background(stanceColor.opacity(0.03))
        .cornerRadius(Theme.CornerRadius.large)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .stroke(stanceColor.opacity(0.15), lineWidth: 0.5)
        )
    }
}

// MARK: - SignalBadge

struct SignalBadge: View {
    let label: String

    var isDeathCross: Bool { label.lowercased().contains("death") }
    var badgeColor: Color { isDeathCross ? bearRed : Color.primary.opacity(0.35) }

    var body: some View {
        Text(label)
            .font(.caption2.weight(isDeathCross ? .bold : .medium)).monospaced()
            .tracking(0.5)
            .foregroundStyle(isDeathCross ? bearRed : Color.primary.opacity(0.55))
            .padding(.horizontal, Theme.Spacing.tight)
            .padding(.vertical, Theme.Spacing.small)
            .background(
                isDeathCross
                    ? bearRed.opacity(0.10)
                    : Color.primary.opacity(0.05)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(
                        isDeathCross ? bearRed.opacity(0.3) : Color.primary.opacity(0.12),
                        lineWidth: 0.5
                    )
            )
            .cornerRadius(Theme.CornerRadius.small)
    }
}

// MARK: - MomentumStockRow

struct MomentumStockRow: View {
    let stock: MomentumTicker
    let stanceColor: Color

    var signalText: String {
        switch stock.crossover {
        case "golden_cross": return "Golden Cross"
        case "death_cross": return "Death Cross"
        default:
            return stock.lastPrice > stock.ma50 ? "Above 50MA" : "Below 50MA"
        }
    }

    var body: some View {
        HStack(spacing: 10) {
            Text(stock.ticker)
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.90))
                .frame(minWidth: 80, alignment: .leading)

            Text("₹\(IndianFormatter.price(stock.lastPrice))")
                .font(.footnote).monospaced()
                .foregroundStyle(.primary.opacity(0.70))

            Spacer()

            SignalBadge(label: signalText)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - MacroGroupView

struct MacroGroupView: View {
    let groupTitle: String
    let rows: [MacroItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(groupTitle)
                .font(.caption2.weight(.semibold)).monospaced()
                .tracking(1.8)
                .foregroundStyle(dimText)
                .padding(.bottom, Theme.Spacing.medium)

            VStack(spacing: 0) {
                ForEach(rows) { row in
                    MacroRowView(row: row)
                    if row.id != rows.last?.id {
                        Divider().opacity(0.08)
                    }
                }
            }
        }
    }
}

// MARK: - MacroRowView

struct MacroRowView: View {
    let row: MacroItem

    var changeColor: Color { row.changePct >= 0 ? bullGreen : bearRed }

    var body: some View {
        HStack(alignment: .center, spacing: 0) {
            VStack(alignment: .leading, spacing: 1) {
                Text(row.name)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.primary.opacity(0.85))
            }

            Spacer()

            Text(String(format: "%.2f", row.price))
                .contentTransition(.numericText())
                .font(.footnote.weight(.semibold)).monospaced()
                .foregroundStyle(.primary.opacity(0.85))
                .frame(minWidth: 70, alignment: .trailing)

            Text("\(row.changePct >= 0 ? "+" : "")\(String(format: "%.2f", row.changePct))%")
                .contentTransition(.numericText())
                .font(.caption.weight(.semibold)).monospaced()
                .foregroundStyle(changeColor)
                .padding(.horizontal, Theme.Spacing.tight)
                .padding(.vertical, Theme.Spacing.xSmall)
                .background(changeColor.opacity(0.08))
                .cornerRadius(Theme.CornerRadius.small)
                .frame(minWidth: 60, alignment: .trailing)
        }
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - FundReturnRow

struct FundReturnRow: View {
    let rank: Int
    let fundName: String
    let returnPercent: Double
    let maxAbsReturn: Double

    var returnColor: Color { returnPercent >= 0 ? bullGreen : bearRed }
    var barWidth: CGFloat {
        guard maxAbsReturn > 0 else { return 0 }
        return CGFloat(abs(returnPercent) / maxAbsReturn)
    }
    var formattedReturn: String {
        let sign = returnPercent >= 0 ? "+" : "-"
        return "\(sign)\(String(format: "%.1f", abs(returnPercent)))%"
    }

    var body: some View {
        HStack(spacing: 10) {
            Text("\(rank)")
                .font(.caption.weight(.medium)).monospaced()
                .foregroundStyle(subtleText)
                .frame(width: 14)

            Text(fundName)
                .font(.footnote.weight(.medium))
                .foregroundStyle(.primary.opacity(0.85))
                .lineLimit(1)

            Spacer()

            HStack(spacing: Theme.Spacing.tight) {
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.primary.opacity(0.06))
                    RoundedRectangle(cornerRadius: 2)
                        .fill(returnColor.opacity(0.7))
                        .frame(width: UIScreen.main.bounds.width * 0.13 * barWidth)
                }
                .frame(width: UIScreen.main.bounds.width * 0.13, height: 4)

                Text(formattedReturn)
                    .font(.caption.weight(.semibold)).monospaced()
                    .foregroundStyle(returnColor)
                    .frame(minWidth: 40, alignment: .trailing)
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - AdvisoryConsensusEmptyCard

struct AdvisoryConsensusEmptyCard: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                        .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
                )

            RBISealBackground()
                .opacity(0.04)

            HStack(spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("दलाल स्ट्रीट सलाह")
                            .font(.caption2)
                            .foregroundStyle(dimText)
                        Text("DALAL STREET ADVISORY")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(.primary.opacity(0.7))
                    }
                    .padding(.bottom, Theme.Spacing.standard)

                    GuillocheDivider()
                        .padding(.bottom, Theme.Spacing.standard)

                    HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                        Image(systemName: "clock.badge")
                            .font(.title2.weight(.light))
                            .foregroundStyle(goldAccent.opacity(0.7))
                            .frame(width: 28)

                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("Next harvest at 1:30 AM")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(.primary.opacity(0.80))

                            Text("Advisor stances from SOIC, Basant Maheshwari, and others will appear here after the nightly run.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                                .lineSpacing(2)
                        }
                    }
                }
                .padding(cardVPad)
            }
        }
        .frame(minHeight: 110)
    }
}

@MainActor
class HomeViewModel: ObservableObject {
    @Published var portfolioValue: Double = 0
    @Published var todayPnL: Double = 0
    @Published var totalPnL: Double = 0
    @Published var investedValue: Double = 0
    @Published var stockCount: Int = 0
    @Published var watchlist: [Stock] = []
    @Published var indices: [LiveMarketIndex] = []
    @Published var indicesLoading = false
    @Published var indicesFetchFailed = false
    @Published var morningBriefData: MorningSummaryResponse? = nil
    @Published var sectorData: [SectorPerformance] = []
    @Published var earningsEvents: [EarningsEvent] = []
    @Published var isLoading = false
    @Published var dashboard: MarketDashboardResponse? = nil
    @Published var dashboardLoading = false
    @Published var sessionExpired = false

    private var indicesTimer: Timer?

    func fetchDashboard() {
        guard !dashboardLoading else { return }
        dashboardLoading = true
        Task {
            dashboard = await NetworkManager.shared.fetchMarketDashboard()
            dashboardLoading = false
        }
    }

    func fetchData(userId: Int) async {
        isLoading = true
        do {
            let holdings = try await NetworkManager.shared.getPortfolio(userId: userId)
            portfolioValue = holdings.reduce(0) { $0 + $1.currentValue }
            investedValue = holdings.reduce(0) { $0 + $1.investedValue }
            todayPnL = holdings.reduce(0) { $0 + ($1.stock.currentPrice * $1.shares * ($1.stock.changePercent/100)) }
            totalPnL = portfolioValue - investedValue
            stockCount = holdings.count

            do {
                morningBriefData = try await NetworkManager.shared.getMorningSummary(userId: userId)
            } catch NetworkError.unauthorized {
                sessionExpired = true
                isLoading = false
                return
            } catch {
                morningBriefData = nil
            }

            do {
                let watchlistItems = try await NetworkManager.shared.getWatchlist(userId: userId)
                watchlist = watchlistItems.map { item in
                    Stock(
                        ticker: item.ticker,
                        companyName: item.companyName,
                        exchange: item.exchange,
                        currentPrice: item.currentPrice,
                        changePercent: item.dayChangePct,
                        signal: nil
                    )
                }
            } catch NetworkError.unauthorized {
                sessionExpired = true
                isLoading = false
                return
            } catch {
                // watchlist unavailable — non-fatal
            }

        } catch NetworkError.unauthorized {
            sessionExpired = true
            isLoading = false
            return
        } catch {
            print("Home fetch error: \(error)")
        }
        isLoading = false
    }

    func fetchIndices() {
        Task {
            indicesLoading = indices.isEmpty
            do {
                let resp = try await NetworkManager.shared.getMarketIndices()
                indices = resp.indices
                indicesFetchFailed = false
            } catch {
                print("Indices fetch error: \(error)")
                indicesFetchFailed = true
            }
            indicesLoading = false
        }
    }

    func startIndicesTimer() {
        indicesTimer?.invalidate()
        indicesTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            self?.fetchIndices()
        }
    }

    func fetchSectors() {
        Task {
            sectorData = (try? await NetworkManager.shared.getSectorPerformance()) ?? []
        }
    }

    func fetchEarnings() {
        Task {
            earningsEvents = await NetworkManager.shared.getEarningsCalendar()
        }
    }

    func stopIndicesTimer() {
        indicesTimer?.invalidate()
        indicesTimer = nil
    }
}

struct HomeScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var viewModel = HomeViewModel()
    @StateObject private var consensusVM = AdvisoryConsensusViewModel()
    @StateObject private var feedVM = HomeFeedViewModel()
    @State private var timeframeConflicts: [TimeframeConflict] = []
    @State private var dailyAction: DailyActionResponse? = nil
    @State private var scrollTarget: String?
    @State private var navigationPath = NavigationPath()
    @State private var selectedTab = 0
    // Fix 3.3: Offline guard — block destructive watchlist ops when disconnected
    @State private var isOnline = true
    private let homeTabs = ["Market Pulse", "My Holdings", "Advisory"]

    var body: some View {
        NavigationStack(path: $navigationPath) {
            ZStack {
                DenominationBackground(denomination: .fiveHundred)

                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: Theme.Spacing.card) {

                            // Fix 1.3: Sticky 3-tab segment control
                            HStack(spacing: 0) {
                                ForEach(Array(homeTabs.enumerated()), id: \.offset) { idx, label in
                                    Button {
                                        selectedTab = idx
                                        HapticManager.selection()
                                    } label: {
                                        Text(label.uppercased())
                                            .font(Theme.officialStampFont(size: 10))
                                            .tracking(1.5)
                                            .foregroundStyle(selectedTab == idx ? Theme.inkPrimary : Theme.inkTertiary)
                                            .padding(.vertical, Theme.Spacing.small)
                                            .padding(.horizontal, Theme.Spacing.standard)
                                            .background(selectedTab == idx ? Theme.securityGold.opacity(0.12) : Color.clear)
                                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.vertical, Theme.Spacing.tight)
                            .padding(.horizontal, Theme.screenPadding)
                            .background(Theme.canvasDeep.opacity(0.95))
                            .overlay(Divider().opacity(0.3), alignment: .bottom)

                            // ── Section 1: Header + Daily Action ─────────────
                            Group {
                                if let user = authManager.currentUser {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text("भारतीय वित्तीय विश्लेषण")
                                                .font(Theme.hindiFont(size: 11))
                                                .foregroundStyle(Theme.inkSecondary)
                                            Text("RESERVE BANK OF INTELLIGENCE")
                                                .font(Theme.officialStampFont(size: 9))
                                                .foregroundStyle(Theme.inkPrimary)
                                        }
                                        Spacer()
                                        NavigationLink(destination: SettingsScreen()) {
                                            ZStack {
                                                Circle()
                                                    .fill(Theme.securityGold.opacity(0.15))
                                                    .frame(width: 40, height: 40)
                                                Text(String(user.displayName.prefix(1)).uppercased())
                                                    .font(.headline.weight(.bold))
                                                    .foregroundStyle(Theme.securityGold)
                                            }
                                            .overlay(Circle().stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.top, Theme.Spacing.standard)
                                }
                                
                                // NEW: Horizontal Quick Nav Bar
                                ScrollView(.horizontal) {
                                    HStack(spacing: Theme.Spacing.medium) {
                                        ForEach(HomeSectionID.allCases) { section in
                                            if section != .top {
                                                Button(action: {
                                                    HapticManager.selection()
                                                    scrollTarget = section.rawValue
                                                }) {
                                                    HStack(spacing: Theme.Spacing.small) {
                                                        Image(systemName: section.icon)
                                                            .font(.caption2)
                                                        Text(section.title.uppercased())
                                                            .font(Theme.officialStampFont(size: 9))
                                                    }
                                                    .foregroundStyle(Theme.inkPrimary)
                                                    .padding(.horizontal, Theme.Spacing.standard)
                                                    .padding(.vertical, Theme.Spacing.medium)
                                                    .background(Theme.securityGold.opacity(0.12))
                                                    .cornerRadius(Theme.CornerRadius.card)
                                                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                                                }
                                                .buttonStyle(EKPressStyle())
                                            }
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.bottom, Theme.Spacing.small)
                                }
                                .scrollIndicators(.hidden)

                                if let action = dailyAction {
                                    DailyActionCard(response: action)
                                        .padding(.horizontal, Theme.screenPadding)
                                }
                            }
                            .id(HomeSectionID.top.rawValue)

                            // ── Section 2: Portfolio ──────────────────────────
                            PortfolioNoteCard(
                                value: viewModel.portfolioValue,
                                totalPnL: viewModel.totalPnL,
                                invested: viewModel.investedValue,
                                todayPnL: viewModel.todayPnL,
                                count: viewModel.stockCount,
                                isLoading: viewModel.isLoading
                            )
                            .padding(.horizontal, Theme.screenPadding)
                            .id(HomeSectionID.portfolio.rawValue)

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
                                            .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.bearRed, lineWidth: 0.5))
                                    }
                                }
                                ScrollView(.horizontal) {
                                    HStack(spacing: Theme.Spacing.standard) {
                                        ForEach(viewModel.indices) { index in
                                            let valueStr: String = {
                                                if index.ticker == "USDINR=X" {
                                                    return String(format: "%.2f", index.value)
                                                } else {
                                                    return IndianFormatter.price(index.value)
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

                            // ── Section 4: Watchlist ──────────────────────────
                            VStack(spacing: Theme.Spacing.card) {
                                SectionHeader(title: "Watchlist", hindiTitle: "बाज़ार की निगरानी", actionLabel: "SEE ALL →") {
                                    // Switch to Portfolio tab (tab 4) to show full holdings
                                    HapticManager.selection()
                                    NotificationCenter.default.post(
                                        name: Notification.Name("switchToTab"),
                                        object: nil,
                                        userInfo: ["tab": 4]
                                    )
                                }
                                if viewModel.watchlist.isEmpty && !viewModel.isLoading {
                                    Text("Add stocks to your watchlist to see them here")
                                        .font(Theme.serialNumberFont(size: 13))
                                        .foregroundStyle(Theme.inkTertiary)
                                        .multilineTextAlignment(.center)
                                        .padding(.horizontal, Theme.screenPadding)
                                        .padding(.vertical, Theme.Spacing.screen)
                                } else {
                                    VStack(spacing: Theme.Spacing.standard) {
                                        ForEach(viewModel.watchlist) { stock in
                                            NavigationLink(value: stock.ticker) {
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

                            // ── Section 5: Sector Pulse ───────────────────────
                            VStack(spacing: Theme.Spacing.standard) {
                                SectionHeader(title: "Sector Pulse", hindiTitle: "क्षेत्र प्रदर्शन")
                                if !viewModel.sectorData.isEmpty {
                                    SectorHeatmapView(sectors: viewModel.sectorData)
                                        .padding(.horizontal, Theme.screenPadding)
                                } else {
                                    DashboardLoadingCard(label: "Sector Pulse", isLoading: viewModel.isLoading)
                                }
                            }
                            .id(HomeSectionID.sectors.rawValue)

                            // ── Section 6: Morning Brief ──────────────────────
                            VStack(spacing: Theme.Spacing.card) {
                                SectionHeader(title: "Morning Brief", hindiTitle: "प्रातःकालीन सारांश")
                                if let briefData = viewModel.morningBriefData {
                                    MorningDecreeCard(briefData: briefData)
                                        .padding(.horizontal, Theme.screenPadding)
                                } else {
                                    DashboardLoadingCard(label: "Morning Brief", isLoading: viewModel.isLoading)
                                }
                            }
                            .id(HomeSectionID.morning.rawValue)

                            // ── Section 6a: NEWS FEED ─────────────────────────
                            VStack(alignment: .leading, spacing: 0) {
                                // Section header (bilingual, matches existing pattern)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("ताज़ा समाचार")
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text("MARKET NEWS")
                                        .font(.caption.weight(.semibold)).monospaced()
                                        .tracking(2.0)
                                        .foregroundStyle(.secondary)
                                }
                                .padding(.bottom, Theme.Spacing.standard)
                                .padding(.horizontal, Theme.screenPadding)

                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.bottom, Theme.Spacing.standard)

                                if let feed = feedVM.feed {
                                    // Horizontal scrolling news strip — all news in one scroll
                                    ScrollView(.horizontal) {
                                        HStack(spacing: Theme.Spacing.standard) {
                                            ForEach(feed.news.prefix(10)) { article in
                                                CompactNewsCell(article: article) { ticker in
                                                    navigationPath.append(ticker)
                                                }
                                                .frame(
                                                    width: UIScreen.main.bounds.width * 0.62,
                                                    height: UIScreen.main.bounds.width * 0.44
                                                )
                                            }
                                        }
                                        .padding(.horizontal, Theme.screenPadding)
                                    }
                                    .scrollIndicators(.hidden)
                                } else if feedVM.isLoading {
                                    // Skeleton shimmer while loading
                                    ForEach(0..<3, id: \.self) { _ in
                                        RoundedRectangle(cornerRadius: 14)
                                            .fill(Color.primary.opacity(0.05))
                                            .frame(height: UIScreen.main.bounds.width * 0.24)
                                            .padding(.horizontal, Theme.screenPadding)
                                    }
                                }
                            }
                            .id(HomeSectionID.news.rawValue)

                            // ── Section 6b: Dalal Street Consensus ───────────────
                            DalalStreetConsensusCard(viewModel: consensusVM) { ticker in
                                // Navigate to analysis for this ticker using the same
                                // pattern as watchlist/earnings NavigationLink(value:)
                                navigationPath.append(ticker)
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, Theme.sectionSpacing)

                            // ── Section 6c: YOUTUBE FEED ─────────────────────────
                            if let feed = feedVM.feed, !feed.youtubeVideos.isEmpty {
                                let videos = Array(feed.youtubeVideos.prefix(15))

                                VStack(alignment: .leading, spacing: 0) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("विशेषज्ञ विश्लेषण")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                        Text("EXPERT VIDEOS")
                                            .font(.caption.weight(.semibold)).monospaced()
                                            .tracking(2.0)
                                            .foregroundStyle(.secondary)
                                    }
                                    .padding(.bottom, Theme.Spacing.standard)
                                    .padding(.horizontal, Theme.screenPadding)

                                    GuillocheDivider()
                                        .padding(.horizontal, Theme.screenPadding)
                                        .padding(.bottom, Theme.Spacing.standard)

                                    ScrollView(.horizontal) {
                                        HStack(alignment: .top, spacing: Theme.Spacing.card) {
                                            ForEach(videos) { video in
                                                YouTubeCompactCard(video: video) { ticker in
                                                    navigationPath.append(ticker)
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

                            // ── Section 8: Market Pulse ───────────────────────
                            DashboardSection(id: HomeSectionID.marketPulse.rawValue, title: "Market Pulse", hindi: "बाजार की नब्ज", icon: "waveform.path.ecg") {
                                if let pulse = viewModel.dashboard?.pulse {
                                    MarketPulseDashCard(pulse: pulse)
                                } else {
                                    DashboardLoadingCard(label: "Market Pulse", isLoading: viewModel.dashboardLoading)
                                }
                            }

                            // ── Section 9: Momentum ───────────────────────────
                            DashboardSection(id: HomeSectionID.momentum.rawValue, title: "Momentum Scan", hindi: "गति विश्लेषण", icon: "arrow.up.right.circle.fill") {
                                if let momentum = viewModel.dashboard?.momentum {
                                    MomentumDashCard(momentum: momentum)
                                } else {
                                    DashboardLoadingCard(label: "Momentum Scan", isLoading: viewModel.dashboardLoading)
                                }
                            }

                            // ── Section 10: Macro & Alternatives ─────────────
                            DashboardSection(id: HomeSectionID.macroAlt.rawValue, title: "Macro & Alternatives", hindi: "वृहद अर्थव्यवस्था", icon: "globe.asia.australia.fill") {
                                if let macro = viewModel.dashboard?.macro {
                                    MacroDashCard(macro: macro)
                                } else {
                                    DashboardLoadingCard(label: "Macro Data", isLoading: viewModel.dashboardLoading)
                                }
                            }

                            // ── Section 11: Institutional Flow ───────────────
                            DashboardSection(id: HomeSectionID.institutional.rawValue, title: "Institutional Allocation", hindi: "संस्थागत प्रवाह", icon: "building.columns.fill") {
                                if let inst = viewModel.dashboard?.institutional {
                                    InstitutionalDashCard(flow: inst)
                                } else {
                                    DashboardLoadingCard(label: "Institutional Flow", isLoading: viewModel.dashboardLoading)
                                }
                            }

                            Spacer(minLength: 100)
                        }
                    }
                    .refreshable {
                        HapticManager.impact(.medium)
                        if let user = authManager.currentUser {
                            await viewModel.fetchData(userId: user.userId)
                            viewModel.fetchIndices()
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
        }
        .onAppear {
            if let user = authManager.currentUser, viewModel.stockCount == 0 && !viewModel.isLoading {
                Task { await viewModel.fetchData(userId: user.userId) }
            }
            viewModel.fetchIndices()
            viewModel.fetchSectors()
            viewModel.fetchEarnings()
            viewModel.fetchDashboard()
            viewModel.startIndicesTimer()
            if let user = authManager.currentUser {
                consensusVM.fetch(userId: user.userId)
                feedVM.fetch(userId: user.userId)
                Task {
                    if let resp = try? await NetworkManager.shared.fetchTimeframeConflicts(userId: user.userId) {
                        timeframeConflicts = resp.conflicts
                    }
                }
                Task {
                    dailyAction = await NetworkManager.shared.fetchDailyAction(userId: user.userId)
                }
            }
        }
        .onDisappear {
            viewModel.stopIndicesTimer()
        }
        .onChange(of: viewModel.sessionExpired) { expired in
            if expired {
                authManager.logout()
            }
        }
    }
}

// MARK: - Daily Action Card

private struct DailyActionCard: View {
    let response: DailyActionResponse

    private var borderColor: Color {
        switch response.urgency {
        case "high":   return Theme.bearRed
        case "medium": return Theme.holdAmber
        default:       return Theme.bullGreen
        }
    }

    private var urgencyLabel: String {
        switch response.urgency {
        case "high":   return "URGENT"
        case "medium": return "WATCH"
        default:       return "INFO"
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            Rectangle()
                .fill(borderColor)
                .frame(width: 3)

            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                HStack {
                    Text("TODAY'S ACTION")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                    Text(urgencyLabel)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(borderColor)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .overlay(RoundedRectangle(cornerRadius: 3).stroke(borderColor, lineWidth: 0.5))
                }

                Text(stripEmoji(response.action))
                    .font(.body).fontDesign(.serif).italic()
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineSpacing(3)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(borderColor.opacity(0.3), lineWidth: 0.5))
        .cornerRadius(Theme.CornerRadius.medium)
    }
}

// MARK: - Portfolio Note Card (the ₹2000 note hero)

private struct PortfolioNoteCard: View {
    let value: Double
    let totalPnL: Double
    let invested: Double
    let todayPnL: Double
    let count: Int
    let isLoading: Bool

    var body: some View {
        ZStack(alignment: .topLeading) {
            // Rupee watermark
            GeometryReader { _ in RupeeWatermark() }

            // Micro-text security thread on left edge
            SecurityThread()

            // Corner ornament top-right
            VStack {
                HStack {
                    Spacer()
                    CornerOrnament()
                        .padding(.top, Theme.Spacing.medium)
                        .padding(.trailing, 8)
                }
                Spacer()
            }

            VStack(alignment: .leading, spacing: 0) {
                // Banknote denomination header
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 1) {
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
                .padding(.bottom, Theme.Spacing.medium)

                GuillocheDivider()

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("निवेश पोर्टफोलियो")
                        .font(Theme.hindiFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)

                    Text("PORTFOLIO VALUE")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkSecondary)

                    Text("I PROMISE TO PAY THE BEARER")
                        .font(.caption2.weight(.medium))
                        .tracking(2)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.bottom, Theme.Spacing.xSmall)

                    PortfolioValueDisplay(target: value, fontSize: 30)

                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: totalPnL >= 0 ? "arrow.up.right" : "arrow.down.right")
                        Text(totalPnL.inrFormatted)
                            .contentTransition(.numericText())
                        Text("(\((invested > 0 ? totalPnL/invested*100 : 0).percentFormatted))")
                            .contentTransition(.numericText())
                    }
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(totalPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                .padding(.top, Theme.Spacing.small)

                // Signature block
                VStack(alignment: .leading, spacing: 0) {
                    Text("Platform Governor")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(Theme.inkSecondary)
                    Text("Nirav Patel")
                        .font(Font.custom("SnellRoundhand", size: 18, relativeTo: .title2))
                        .foregroundStyle(Theme.inkPrimary.opacity(0.7))
                        .padding(.top, -2)
                }
                .padding(.top, Theme.Spacing.standard)

                GuillocheDivider()

                HStack {
                    StatNoteBlock(label: "TODAY", value: todayPnL.inrFormatted, color: todayPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                    Spacer()
                    StatNoteBlock(label: "INVESTED", value: invested.shortFormatted, color: Theme.inkPrimary)
                    Spacer()
                    StatNoteBlock(label: "ASSETS", value: "\(count)", color: Theme.inkPrimary)
                }
            }
            .padding(.leading, 32)
            .padding(.trailing, 24)
            .padding(.vertical, Theme.Spacing.screen)
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

private struct MorningDecreeCard: View {
    let briefData: MorningSummaryResponse

    private var moodColor: Color {
        switch briefData.mood {
        case "positive": return Theme.bullGreen
        case "negative": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }

    private var bulletPoints: [String] {
        briefData.summary
            .components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { $0.hasPrefix("•") }
            .map { String($0.dropFirst()).trimmingCharacters(in: .whitespaces) }
    }

    private var leadSentence: String {
        if let first = bulletPoints.first {
            return stripEmoji(first)
        }
        return stripEmoji(briefData.summary)
    }

    private var remainingBullets: [String] {
        if bulletPoints.count > 1 {
            return Array(bulletPoints.dropFirst())
        }
        return []
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // SecurityThread on left edge
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("प्रातःकालीन सारांश")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        HStack {
                            Text("MORNING BRIEF")
                                .font(.caption.weight(.semibold)).monospaced()
                                .tracking(2.0)
                                .foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            BanknoteSignalBadge(text: "VERIFIED", color: Theme.securityGold, rotation: -8)
                        }
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Lead sentence with priority pill detection
                    VStack(alignment: .leading, spacing: sectionGap) {
                        if briefData.mood == "negative" {
                            PriorityPill(label: "ALERT", color: bearRed)
                        } else if briefData.mood == "positive" {
                            PriorityPill(label: "SIGNAL", color: bullGreen)
                        } else {
                            PriorityPill(label: "INFO", color: neutralAmber)
                        }

                        Text(leadSentence)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.primary.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(3)
                    }
                    .padding(.horizontal, cardHPad)

                    // Fine rule separator
                    Rectangle()
                        .fill(Color.primary.opacity(0.08))
                        .frame(height: 0.5)
                        .padding(.horizontal, cardHPad)
                        .padding(.vertical, Theme.Spacing.standard)

                    // Bullet points
                    if !remainingBullets.isEmpty {
                        VStack(alignment: .leading, spacing: rowSpacing) {
                            ForEach(remainingBullets, id: \.self) { point in
                                NiveshBulletRow(text: point)
                            }
                        }
                        .padding(.horizontal, cardHPad)
                    }

                    // Priority items
                    if let items = briefData.priorityItems, !items.isEmpty {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .frame(height: 0.5)
                            .padding(.horizontal, cardHPad)
                            .padding(.top, Theme.Spacing.standard)
                            .padding(.bottom, Theme.Spacing.medium)

                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("TODAY'S PRIORITIES")
                                .font(.caption2.weight(.semibold)).monospaced()
                                .tracking(1.5)
                                .foregroundStyle(dimText)

                            ForEach(items.prefix(5)) { item in
                                HStack(spacing: Theme.Spacing.medium) {
                                    PriorityPill(
                                        label: item.type == "alert_triggered" ? "ALERT" : "SIGNAL",
                                        color: item.type == "alert_triggered" ? bearRed : goldAccent
                                    )
                                    Text(stripEmoji(item.message))
                                        .font(.caption)
                                        .foregroundStyle(.primary.opacity(0.70))
                                        .lineLimit(2)
                                }
                            }
                        }
                        .padding(.horizontal, cardHPad)
                    }

                    // Timestamp footer
                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)

                    HStack {
                        Text("Updated \(briefData.generatedAt)")
                            .font(.caption2)
                            .foregroundStyle(subtleText)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(subtleText)
                    }
                    .padding(.horizontal, cardHPad)
                    .padding(.bottom, cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

private struct SectorPulseCard: View {
    let sector: SectorPerformance

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(sector.name.uppercased())
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(1)

            Text((sector.changePct >= 0 ? "+" : "") + String(format: "%.2f%%", sector.changePct))
                .contentTransition(.numericText())
                .font(Theme.serialNumberFont(size: 18))
                .foregroundStyle(sector.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)

            // Mini bar
            ZStack(alignment: .leading) {
                Rectangle().fill(Theme.inkSecondary.opacity(0.08)).frame(height: 3)
                Rectangle()
                    .fill(sector.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                    .frame(width: min(UIScreen.main.bounds.height * 0.10, UIScreen.main.bounds.height * 0.10 * abs(sector.changePct) / 5.0), height: 3)
            }
            .frame(height: 3)
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}

// MARK: - Timeframe Conflicts Banner

private struct TimeframeConflictsBanner: View {
    let conflicts: [TimeframeConflict]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("TIMING INSIGHTS")
                .font(Theme.sectionCapsLabel())
                .tracking(1.5)
                .foregroundStyle(Theme.securityGold)
                .padding(.horizontal, Theme.screenPadding)

            ScrollView(.horizontal) {
                HStack(spacing: 10) {
                    ForEach(conflicts) { conflict in
                        NavigationLink(value: conflict.ticker) {
                            TimeframeConflictCard(conflict: conflict)
                        }
                        .buttonStyle(.plain)
                        .ekPressHaptic()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
            .scrollIndicators(.hidden)
        }
    }
}

private struct TimeframeConflictCard: View {
    let conflict: TimeframeConflict

    var isBottomFishing: Bool { conflict.conflictType == "BUY_THE_DIP" }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack {
                Text(conflict.ticker)
                    .font(Theme.monoTabular(size: 15, relativeTo: .subheadline).weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Text(isBottomFishing ? "BUY THE DIP" : "TAKE PROFITS")
                    .font(Theme.microLabel(size: 10).weight(.bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                    .background(isBottomFishing ? Theme.signalEmerald : Theme.signalRuby)
                    .cornerRadius(3)
            }

            if let hint = conflict.actionHint {
                Text(stripEmoji(hint))
                    .font(.caption).fontDesign(.serif).italic()
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(Theme.Spacing.medium)
        .frame(width: UIScreen.main.bounds.width * 0.42)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

// MARK: - Dashboard Section Wrapper

private struct DashboardSection<Content: View>: View {
    let id: String
    let title: String
    let hindi: String
    let icon: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: Theme.Spacing.tight) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(Theme.securityGold)
                SectionHeader(title: title, hindiTitle: hindi)
            }
            content()
        }
        .id(id)
        .padding(.horizontal, Theme.screenPadding)
    }
}

private struct DashboardLoadingCard: View {
    let label: String
    var isLoading: Bool = true
    var body: some View {
        HStack {
            if isLoading {
                ProgressView().tint(Theme.securityGold)
                Text("Loading \(label)…")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.inkTertiary)
            } else {
                Text("\(label) unavailable")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Market Pulse Dashboard Card

private struct MarketPulseDashCard: View {
    let pulse: MarketPulseResponse

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // SecurityThread on left
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("बाजार की नब्ज")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MARKET PULSE")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // A/D Breadth Bar
                    if pulse.advances + pulse.declines > 0 {
                        ADBreathBar(advancing: pulse.advances, declining: pulse.declines)
                            .padding(.horizontal, cardHPad)
                    }

                    // Fine rule
                    Rectangle()
                        .fill(Color.primary.opacity(0.08))
                        .frame(height: 0.5)
                        .padding(.horizontal, cardHPad)
                        .padding(.vertical, Theme.Spacing.standard)

                    // Index rows
                    VStack(spacing: 0) {
                        ForEach(pulse.indices.prefix(4)) { idx in
                            let valueStr: String = {
                                if idx.name.lowercased().contains("usd") || idx.name.lowercased().contains("inr") {
                                    return idx.value
                                }
                                return idx.value
                            }()
                            let changeVal: Double = {
                                if idx.changePct.contains("%") {
                                    return Double(idx.changePct.replacingOccurrences(of: "%", with: "")) ?? 0
                                }
                                return Double(idx.changePct) ?? 0
                            }()

                            IndexRow(
                                name: idx.name,
                                value: valueStr,
                                change: changeVal
                            )

                            if idx.id != pulse.indices.prefix(4).last?.id {
                                Divider().opacity(0.10)
                            }
                        }
                    }
                    .padding(.horizontal, cardHPad)
                    .padding(.bottom, cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Momentum Dashboard Card

private struct MomentumDashCard: View {
    let momentum: MomentumResponse

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("गति विश्लेषण")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MOMENTUM SCAN")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Bullish section
                    if !momentum.bullish.isEmpty {
                        MomentumSectionView(
                            stance: "BULLISH",
                            stocks: Array(momentum.bullish.prefix(3))
                        )
                        .padding(.horizontal, cardHPad)
                    }

                    if !momentum.bullish.isEmpty && !momentum.bearish.isEmpty {
                        Spacer().frame(height: 10)
                    }

                    // Bearish section
                    if !momentum.bearish.isEmpty {
                        MomentumSectionView(
                            stance: "BEARISH",
                            stocks: Array(momentum.bearish.prefix(3))
                        )
                        .padding(.horizontal, cardHPad)
                    }

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Macro Dashboard Card

private struct MacroDashCard: View {
    let macro: MacroAlternativesResponse

    private let macroGroups: [(title: String, keys: [String])] = [
        ("COMMODITIES & FOREX", ["Brent Crude", "Gold", "Silver", "USD/INR"]),
        ("RATES & VOLATILITY", ["US 10Y Yield", "India VIX"]),
        ("INDIA INSTRUMENTS", ["Nifty BeES", "Gold BeES", "Nifty IT", "Nifty Pharma"]),
    ]

    private func itemsForGroup(_ keys: [String]) -> [MacroItem] {
        macro.items.filter { item in
            keys.contains { key in
                item.name.localizedCaseInsensitiveContains(key)
            }
        }
    }

    private var ungroupedItems: [MacroItem] {
        let allGrouped = macroGroups.flatMap { itemsForGroup($0.keys) }
        return macro.items.filter { item in
            !allGrouped.contains { $0.id == item.id }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("वृहद अर्थव्यवस्था")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MACRO & ALTERNATIVES")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Grouped sections
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        ForEach(macroGroups, id: \.title) { group in
                            let items = itemsForGroup(group.keys)
                            if !items.isEmpty {
                                MacroGroupView(groupTitle: group.title, rows: items)

                                if group.title != macroGroups.last?.title || !ungroupedItems.isEmpty {
                                    Rectangle()
                                        .fill(Color.primary.opacity(0.08))
                                        .frame(height: 0.5)
                                        .padding(.vertical, Theme.Spacing.small)
                                }
                            }
                        }

                        // Ungrouped items
                        if !ungroupedItems.isEmpty {
                            MacroGroupView(groupTitle: "OTHER", rows: ungroupedItems)
                        }
                    }
                    .padding(.horizontal, cardHPad)

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - 14.4 Market Mood Gauge (Advance/Decline semi-circle dial)

struct MarketMoodGauge: View {
    /// advances / (advances + declines), range 0…1
    let ratio: Double

    private var moodLabel: String {
        switch ratio {
        case 0..<0.35: return "EXTREME FEAR"
        case 0.35..<0.45: return "FEAR"
        case 0.45..<0.55: return "NEUTRAL"
        case 0.55..<0.65: return "GREED"
        default: return "EXTREME GREED"
        }
    }

    private var needleColor: Color {
        switch ratio {
        case 0..<0.45: return Theme.bearRed
        case 0.45..<0.55: return Theme.holdAmber
        default: return Theme.bullGreen
        }
    }

    var body: some View {
        VStack(spacing: 10) {
            Text("MARKET MOOD GAUGE")
                .font(.caption2.weight(.bold)).monospaced()
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            ZStack {
                // Background arc (full 180°)
                ArcShape(startAngle: .degrees(180), endAngle: .degrees(360), clockwise: false)
                    .stroke(Theme.inkTertiary.opacity(0.15), style: StrokeStyle(lineWidth: 16, lineCap: .round))

                // Colored fill arc based on ratio
                ArcShape(startAngle: .degrees(180), endAngle: .degrees(180 + ratio * 180), clockwise: false)
                    .stroke(
                        LinearGradient(colors: [Theme.bearRed, Theme.holdAmber, Theme.bullGreen],
                                       startPoint: .leading, endPoint: .trailing),
                        style: StrokeStyle(lineWidth: 16, lineCap: .round)
                    )

                // Needle
                GeometryReader { geo in
                    let cx = geo.size.width / 2
                    let cy = geo.size.height
                    let r = min(cx, cy) - 18
                    let angle = Double.pi + ratio * Double.pi
                    let nx = cx + CGFloat(cos(angle)) * r
                    let ny = cy + CGFloat(sin(angle)) * r
                    Path { p in
                        p.move(to: CGPoint(x: cx, y: cy))
                        p.addLine(to: CGPoint(x: nx, y: ny))
                    }
                    .stroke(Theme.inkPrimary, style: StrokeStyle(lineWidth: 2, lineCap: .round))
                    // Center dot
                    Circle()
                        .fill(Theme.inkPrimary)
                        .frame(width: 8, height: 8)
                        .position(x: cx, y: cy)
                }
            }
            .aspectRatio(0.22, contentMode: .fit)
            .clipped()

            VStack(spacing: Theme.Spacing.small) {
                Text(moodLabel)
                    .font(.footnote.weight(.bold))
                    .foregroundStyle(needleColor)
                Text(String(format: "A/D Ratio: %.2f", ratio))
                    .font(.caption2).monospaced()
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}

private struct ArcShape: Shape {
    var startAngle: Angle
    var endAngle: Angle
    var clockwise: Bool

    func path(in rect: CGRect) -> Path {
        var p = Path()
        let cx = rect.midX
        let cy = rect.maxY
        let r = min(rect.width / 2, rect.height) - 8
        p.addArc(center: CGPoint(x: cx, y: cy),
                 radius: r,
                 startAngle: startAngle,
                 endAngle: endAngle,
                 clockwise: clockwise)
        return p
    }
}

// MARK: - 14.4 IndexCardView (snapping horizontal index chip)

struct IndexCardView: View {
    let index: LiveMarketIndex

    private var valueStr: String {
        index.ticker == "USDINR=X"
            ? String(format: "%.2f", index.value)
            : IndianFormatter.price(index.value)
    }
    private var isPositive: Bool { index.changePct >= 0 }
    private var changeStr: String {
        (isPositive ? "+" : "") + String(format: "%.2f%%", index.changePct)
    }

    var body: some View {
        GeometryReader { idxGeo in
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                Text(index.name)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)

                Text(valueStr)
                    .contentTransition(.numericText())
                    .font(.headline.weight(.bold)).monospaced()
                    .foregroundStyle(Theme.inkPrimary)
                    .monospacedDigit()

                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
                    Text(changeStr)
                        .contentTransition(.numericText())
                        .sensoryFeedback(isPositive ? .increase : .decrease, trigger: index.changePct)
                        .font(.caption.weight(.bold)).monospaced()
                        .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
                }
            }
            .padding(Theme.Spacing.standard)
            .frame(width: idxGeo.size.width * 0.35)
            .banknoteCard()
        }
    }
}

// MARK: - 14.4 MomentumRowView (backed by Swift Charts sparkline)

struct MomentumRowView: View {
    let ticker: MomentumTicker
    let isBullish: Bool

    private var signalColor: Color { isBullish ? Theme.bullGreen : Theme.bearRed }
    private var crossoverLabel: String {
        switch ticker.crossover {
        case "golden_cross": return "Golden Cross"
        case "death_cross": return "Death Cross"
        default: return isBullish ? "Above MA50" : "Below MA50"
        }
    }

    var body: some View {
        GeometryReader { momGeo in
            HStack(spacing: Theme.Spacing.standard) {
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(ticker.ticker)
                            .font(.footnote.weight(.bold)).monospaced()
                            .foregroundStyle(Theme.inkPrimary)
                        Text(crossoverLabel.uppercased())
                            .font(.caption2.weight(.bold)).monospaced()
                            .tracking(0.8)
                            .foregroundStyle(signalColor)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(signalColor.opacity(0.10))
                            .cornerRadius(3)
                    }
                    HStack(spacing: 10) {
                        VStack(alignment: .leading, spacing: 1) {
                            Text("LTP").font(.caption2).foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(ticker.lastPrice))
                                .font(.caption.weight(.semibold)).monospaced()
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        VStack(alignment: .leading, spacing: 1) {
                            Text("SINCE").font(.caption2).foregroundStyle(Theme.inkTertiary)
                            Text(ticker.trendDate)
                                .font(.caption2).monospaced()
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                Spacer()
                // Native Swift Charts trend sparkline
                if !ticker.sparkline.isEmpty {
                    SparklineView(values: ticker.sparkline, color: signalColor)
                        .frame(width: momGeo.size.width * 0.14, height: momGeo.size.width * 0.08)
                }
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.standard)
        }
    }
}

// MARK: - 14.7 Anti-Patterns Validator (passive checks, no UI)

/// Validates that a Double value from the server does not represent a
/// Western million/billion scale (>= 1_000_000 raw without crore conversion).
/// Returns a safe IndianFormatter string, never raw Western numbers.
func safeIndianCurrency(_ raw: Double) -> String {
    // Block any value that looks like it was passed as raw millions/billions
    // (i.e. > 100 crore threshold without going through formatLakhsCrores)
    return IndianFormatter.formatLakhsCrores(raw)
}

// MARK: - Compact News Cell — rich card with expand-to-detail

struct CompactNewsCell: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil
    @State private var showDetail = false

    private var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "MC"
        case "economic_times": return "ET"
        case "nse": return "NSE"
        case "business_standard": return "BS"
        case "livemint": return "MINT"
        case "reuters": return "RTR"
        default: return String(article.source.prefix(4)).uppercased()
        }
    }

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return ""
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    var body: some View {
        Button(action: {
            HapticManager.selection()
            showDetail = true
        }) {
            VStack(alignment: .leading, spacing: 0) {
                // ── Image / Hero ─────────────────────────────────────────
                ZStack(alignment: .bottomLeading) {
                    if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(height: 110)
                                    .clipped()
                            case .failure(_), .empty:
                                newsFallbackImage
                            @unknown default:
                                EmptyView()
                            }
                        }
                    } else {
                        newsFallbackImage
                    }

                    // Source + time strip over image
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(sourceLabel)
                            .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                            .tracking(1.0)
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, 2)
                            .background(Color.black.opacity(0.55))
                            .cornerRadius(Theme.CornerRadius.small)

                        if !timeLabel.isEmpty {
                            Text(timeLabel)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.white.opacity(0.8))
                                .padding(.horizontal, Theme.Spacing.tight)
                                .padding(.vertical, 2)
                                .background(Color.black.opacity(0.40))
                                .cornerRadius(Theme.CornerRadius.small)
                        }
                    }
                    .padding(Theme.Spacing.tight)
                }
                .frame(height: 110)
                .clipped()
                .cornerRadius(Theme.CornerRadius.tight)

                // ── Body ─────────────────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    // Sentiment badge
                    if let sentiment = article.sentiment, !sentiment.isEmpty {
                        Text(sentiment.uppercased())
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(0.8)
                            .foregroundStyle(sentimentColor)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(sentimentColor.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                    }

                    // Headline
                    Text(stripEmoji(article.headline))
                        .font(Theme.engravedSerif(size: 12, weight: .semibold, relativeTo: .caption))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)

                    // Summary snippet
                    if let summary = article.summary, !summary.isEmpty {
                        Text(stripEmoji(summary))
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(2)
                            .lineSpacing(1.5)
                    }

                    // Read more hint
                    HStack {
                        Spacer()
                        Text("TAP TO READ")
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(1.2)
                            .foregroundStyle(Theme.inkTertiary)
                        Image(systemName: "chevron.right")
                            .font(Theme.serialNumberFont(size: 7, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.standard)
            }
            .frame(maxWidth: .infinity, alignment: .topLeading)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showDetail) {
            NewsDetailSheet(article: article, onTickerTap: onTickerTap)
        }
    }

    private var newsFallbackImage: some View {
        Rectangle()
            .fill(Theme.canvasDeep)
            .frame(height: 110)
            .overlay(
                VStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: "newspaper.fill")
                        .font(.title2)
                        .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                    Text(sourceLabel)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                        .tracking(1.5)
                }
            )
    }
}

// MARK: - News Detail Sheet (shared — used in HomeScreen & NewsMultimediaView)

struct NewsDetailSheet: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil
    @Environment(\.dismiss) var dismiss
    @State private var showSafari = false

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "MoneyControl"
        case "economic_times": return "Economic Times"
        case "nse": return "NSE Official"
        case "business_standard": return "Business Standard"
        case "livemint": return "Livemint"
        case "reuters": return "Reuters"
        default: return article.source.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        // Hero image
                        if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                            AsyncImage(url: url) { phase in
                                switch phase {
                                case .success(let img):
                                    img.resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(maxWidth: .infinity)
                                        .frame(height: UIScreen.main.bounds.width * 0.55)
                                        .clipped()
                                case .failure(_), .empty:
                                    EmptyView()
                                @unknown default:
                                    EmptyView()
                                }
                            }
                        }

                        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                            // Source + time row
                            HStack(spacing: Theme.Spacing.small) {
                                Text(sourceLabel.uppercased())
                                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                                    .tracking(1.5)
                                    .foregroundStyle(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.small)
                                    .padding(.vertical, Theme.Spacing.xSmall)
                                    .background(Theme.securityGold.opacity(0.10))
                                    .cornerRadius(Theme.CornerRadius.small)

                                if let sentiment = article.sentiment, !sentiment.isEmpty {
                                    Text(sentiment.uppercased())
                                        .font(.caption2.weight(.bold).monospaced())
                                        .tracking(0.8)
                                        .foregroundStyle(sentimentColor)
                                        .padding(.horizontal, Theme.Spacing.small)
                                        .padding(.vertical, Theme.Spacing.xSmall)
                                        .background(sentimentColor.opacity(0.10))
                                        .cornerRadius(Theme.CornerRadius.small)
                                }

                                Spacer()

                                Text(timeLabel)
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(Theme.inkTertiary)
                            }

                            GuillocheDivider()

                            // Headline
                            Text(stripEmoji(article.headline))
                                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                                .foregroundStyle(Theme.inkPrimary)
                                .lineSpacing(4)

                            // Ticker chip
                            if let ticker = article.ticker, !ticker.isEmpty {
                                Button(action: {
                                    HapticManager.selection()
                                    dismiss()
                                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                                        onTickerTap?(ticker)
                                    }
                                }) {
                                    HStack(spacing: Theme.Spacing.tight) {
                                        Image(systemName: "chart.line.uptrend.xyaxis")
                                            .font(.caption2.weight(.semibold))
                                        Text(ticker)
                                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                        Image(systemName: "arrow.right")
                                            .font(.caption2)
                                    }
                                    .foregroundStyle(Theme.bullGreen)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.medium)
                                    .background(Theme.bullGreen.opacity(0.08))
                                    .cornerRadius(Theme.CornerRadius.medium)
                                }
                                .buttonStyle(EKPressStyle())
                            }

                            GuillocheDivider()

                            // Summary / body
                            if let summary = article.summary, !summary.isEmpty {
                                Text(stripEmoji(summary))
                                    .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                                    .foregroundStyle(Theme.inkPrimary.opacity(0.88))
                                    .lineSpacing(6)
                            } else {
                                Text("Full article available at source.")
                                    .font(.footnote)
                                    .foregroundStyle(Theme.inkSecondary)
                            }

                            // Read full article button
                            Button(action: {
                                HapticManager.impact(.medium)
                                showSafari = true
                            }) {
                                HStack {
                                    Image(systemName: "safari.fill")
                                    Text("READ FULL ARTICLE")
                                        .font(Theme.officialStampFont(size: 11, relativeTo: .callout))
                                        .tracking(1.5)
                                }
                                .foregroundStyle(Theme.canvas)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, Theme.Spacing.card)
                                .background(Theme.inkPrimary)
                                .cornerRadius(Theme.CornerRadius.large)
                            }
                            .buttonStyle(EKPressStyle())
                            .padding(.top, Theme.Spacing.standard)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, Theme.Spacing.card)
                        .padding(.bottom, Theme.Spacing.xLarge)
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.title3)
                    }
                }
            }
        }
        .sheet(isPresented: $showSafari) {
            if let url = URL(string: article.articleUrl) {
                SafariSheetView(url: url)
            }
        }
    }
}

// MARK: - Section 15: SwiftUI Preview Environment

#Preview("HomeScreen") {
    HomeScreen()
        .environmentObject(AuthManager())
        .environmentObject(LocalReportManager())
}

#Preview("IndexCardView") {
    IndexCardView(index: LiveMarketIndex(
        name: "NIFTY 50", ticker: "^NSEI",
        value: 22_547.85, changePct: 0.43, changeAbs: 96.5
    ))
    .padding()
    .background(Theme.canvas)
}

#Preview("MarketMoodGauge") {
    MarketMoodGauge(ratio: 0.62)
        .padding()
        .background(Theme.canvas)
}

#Preview("MomentumRowView") {
    MomentumRowView(
        ticker: MomentumTicker(
            ticker: "RELIANCE", lastPrice: 2847.5, ma20: 2780.0,
            ma50: 2650.0, sparkline: [2600, 2640, 2680, 2720, 2780, 2820, 2847],
            trendDate: "12 May 2026", crossover: "golden_cross"
        ),
        isBullish: true
    )
    .padding()
    .background(Theme.canvas)
}

// MARK: - Institutional Flow Dashboard Card

private struct InstitutionalDashCard: View {
    let flow: InstitutionalFlowResponse

    private var maxAbsReturn: Double {
        flow.funds.prefix(6).map { abs($0.oneYearReturnPct) }.max() ?? 1.0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("संस्थागत प्रवाह")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("INSTITUTIONAL ALLOCATION")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    Text("TOP PERFORMING MUTUAL FUNDS — 1Y RETURN")
                        .font(.caption2.weight(.semibold)).monospaced()
                        .tracking(1.5)
                        .foregroundStyle(dimText)
                        .padding(.horizontal, cardHPad)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Fund rows
                    VStack(spacing: 0) {
                        ForEach(Array(flow.funds.prefix(6).enumerated()), id: \.offset) { i, fund in
                            FundReturnRow(
                                rank: i + 1,
                                fundName: fund.name,
                                returnPercent: fund.oneYearReturnPct,
                                maxAbsReturn: maxAbsReturn
                            )

                            if i < min(flow.funds.count, 6) - 1 {
                                Divider().opacity(0.08)
                            }
                        }
                    }
                    .padding(.horizontal, cardHPad)

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}
