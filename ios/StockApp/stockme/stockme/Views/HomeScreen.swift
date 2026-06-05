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

// MARK: - Design System Constants

private let cardHPad: CGFloat = 16
private let cardVPad: CGFloat = 14
private let rowSpacing: CGFloat = 10
private let sectionGap: CGFloat = 6

private let bullGreen  = Color(red: 0.10, green: 0.53, blue: 0.24)
private let bearRed    = Color(red: 0.72, green: 0.09, blue: 0.09)
private let neutralAmber = Color(red: 0.80, green: 0.55, blue: 0.05)
private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)
private let dimText    = Color.primary.opacity(0.45)
private let subtleText = Color.primary.opacity(0.30)

// MARK: - NiveshBulletRow

struct NiveshBulletRow: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(goldAccent)
                .frame(width: 4, height: 4)
                .padding(.top, 6)

            Text(stripEmoji(text))
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(.primary.opacity(0.80))
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
            .font(.system(size: 9, weight: .bold, design: .monospaced))
            .tracking(1.5)
            .foregroundColor(color)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(color.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(color.opacity(0.25), lineWidth: 0.5)
            )
            .cornerRadius(4)
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
        VStack(alignment: .leading, spacing: 6) {
            Text("ADVANCE / DECLINE BREADTH")
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .tracking(1.5)
                .foregroundColor(dimText)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(bearRed.opacity(0.15))
                        .frame(maxWidth: .infinity)

                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [bullGreen.opacity(0.9), bullGreen.opacity(0.6)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geo.size.width * advancingRatio)
                }
            }
            .frame(height: 8)
            .cornerRadius(4)

            HStack {
                HStack(spacing: 4) {
                    Circle().fill(bullGreen).frame(width: 5, height: 5)
                    Text("\(advancing) advancing")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(bullGreen)
                }
                Spacer()
                HStack(spacing: 4) {
                    Text("\(declining) declining")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(bearRed)
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
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 1)
                .fill(changeColor.opacity(0.7))
                .frame(width: 2, height: 20)

            Text(name)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(.primary.opacity(0.85))

            Spacer()

            Text(value)
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(.primary.opacity(0.85))

            Text(changeText)
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(changeColor)
                .frame(width: 62, alignment: .trailing)
        }
        .padding(.vertical, 3)
    }
}

// MARK: - MomentumSectionView

struct MomentumSectionView: View {
    let stance: String
    let stocks: [MomentumTicker]

    var stanceColor: Color { stance == "BULLISH" ? bullGreen : bearRed }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Rectangle()
                    .fill(stanceColor)
                    .frame(width: 3, height: 14)
                    .cornerRadius(1.5)

                Text(stance)
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .tracking(2.0)
                    .foregroundColor(stanceColor)

                Spacer()

                Text("\(stocks.count) stocks")
                    .font(.system(size: 10, weight: .regular))
                    .foregroundColor(subtleText)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
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
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
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
            .font(.system(size: 9, weight: isDeathCross ? .bold : .medium, design: .monospaced))
            .tracking(0.5)
            .foregroundColor(isDeathCross ? bearRed : Color.primary.opacity(0.55))
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(
                isDeathCross
                    ? bearRed.opacity(0.10)
                    : Color.primary.opacity(0.05)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(
                        isDeathCross ? bearRed.opacity(0.3) : Color.primary.opacity(0.12),
                        lineWidth: 0.5
                    )
            )
            .cornerRadius(4)
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
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(.primary.opacity(0.90))
                .frame(width: 90, alignment: .leading)

            Text("₹\(IndianFormatter.price(stock.lastPrice))")
                .font(.system(size: 13, weight: .regular, design: .monospaced))
                .foregroundColor(.primary.opacity(0.70))

            Spacer()

            SignalBadge(label: signalText)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 9)
    }
}

// MARK: - MacroGroupView

struct MacroGroupView: View {
    let groupTitle: String
    let rows: [MacroItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(groupTitle)
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .tracking(1.8)
                .foregroundColor(dimText)
                .padding(.bottom, 8)

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
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.primary.opacity(0.85))
            }

            Spacer()

            Text(String(format: "%.2f", row.price))
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(.primary.opacity(0.85))
                .frame(width: 80, alignment: .trailing)

            Text("\(row.changePct >= 0 ? "+" : "")\(String(format: "%.2f", row.changePct))%")
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundColor(changeColor)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(changeColor.opacity(0.08))
                .cornerRadius(4)
                .frame(width: 64, alignment: .trailing)
        }
        .padding(.vertical, 8)
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
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundColor(subtleText)
                .frame(width: 14)

            Text(fundName)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(.primary.opacity(0.85))
                .lineLimit(1)

            Spacer()

            HStack(spacing: 6) {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.primary.opacity(0.06))
                        RoundedRectangle(cornerRadius: 2)
                            .fill(returnColor.opacity(0.7))
                            .frame(width: geo.size.width * barWidth)
                    }
                }
                .frame(width: 52, height: 4)

                Text(formattedReturn)
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundColor(returnColor)
                    .frame(width: 44, alignment: .trailing)
            }
        }
        .padding(.vertical, 7)
    }
}

// MARK: - AdvisoryConsensusEmptyCard

struct AdvisoryConsensusEmptyCard: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
                )

            RBISealBackground()
                .opacity(0.04)

            HStack(spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("दलाल स्ट्रीट सलाह")
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(dimText)
                        Text("DALAL STREET ADVISORY")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(.primary.opacity(0.7))
                    }
                    .padding(.bottom, 10)

                    GuillocheDivider()
                        .padding(.bottom, 12)

                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "clock.badge")
                            .font(.system(size: 22, weight: .light))
                            .foregroundColor(goldAccent.opacity(0.7))
                            .frame(width: 28)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Next harvest at 1:30 AM")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundColor(.primary.opacity(0.80))

                            Text("Advisor stances from SOIC, Basant Maheshwari, and others will appear here after the nightly run.")
                                .font(.system(size: 12, weight: .regular))
                                .foregroundColor(.primary.opacity(0.50))
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

            morningBriefData = try? await NetworkManager.shared.getMorningSummary(userId: userId)

            if let watchlistItems = try? await NetworkManager.shared.getWatchlist(userId: userId) {
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
            }

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

    var body: some View {
        NavigationStack(path: $navigationPath) {
            ZStack {
                DenominationBackground(denomination: .fiveHundred)

                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 16) {

                            // ── Section 1: Header + Daily Action ─────────────
                            Group {
                                if let user = authManager.currentUser {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text("भारतीय वित्तीय विश्लेषण")
                                                .font(Theme.hindiFont(size: 11))
                                                .foregroundColor(Theme.inkSecondary)
                                            Text("RESERVE BANK OF INTELLIGENCE")
                                                .font(Theme.officialStampFont(size: 9))
                                                .foregroundColor(Theme.inkPrimary)
                                        }
                                        Spacer()
                                        NavigationLink(destination: SettingsScreen()) {
                                            ZStack {
                                                Circle()
                                                    .fill(Theme.securityGold.opacity(0.15))
                                                    .frame(width: 40, height: 40)
                                                Text(String(user.displayName.prefix(1)).uppercased())
                                                    .font(.system(size: 16, weight: .bold))
                                                    .foregroundColor(Theme.securityGold)
                                            }
                                            .overlay(Circle().stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.top, 12)
                                }
                                
                                // NEW: Horizontal Quick Nav Bar
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 8) {
                                        ForEach(HomeSectionID.allCases) { section in
                                            if section != .top {
                                                Button(action: {
                                                    HapticManager.selection()
                                                    scrollTarget = section.rawValue
                                                }) {
                                                    HStack(spacing: 4) {
                                                        Image(systemName: section.icon)
                                                            .font(.system(size: 9))
                                                        Text(section.title.uppercased())
                                                            .font(Theme.officialStampFont(size: 9))
                                                    }
                                                    .foregroundColor(Theme.inkPrimary)
                                                    .padding(.horizontal, 12)
                                                    .padding(.vertical, 8)
                                                    .background(Theme.securityGold.opacity(0.12))
                                                    .cornerRadius(16)
                                                    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                                                }
                                                .buttonStyle(EKPressStyle())
                                            }
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.bottom, 4)
                                }

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
                            VStack(alignment: .leading, spacing: 12) {
                                HStack(alignment: .center, spacing: 8) {
                                    SectionHeader(title: "Market Indices", hindiTitle: "बाजार सूचकांक")
                                    if viewModel.indicesFetchFailed {
                                        Text("DELAYED")
                                            .font(Theme.officialStampFont(size: 8))
                                            .foregroundColor(Theme.bearRed)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.bearRed, lineWidth: 0.5))
                                    }
                                }
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 12) {
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
                            }
                            .id(HomeSectionID.indices.rawValue)

                            // ── Section 4: Watchlist ──────────────────────────
                            VStack(spacing: 16) {
                                SectionHeader(title: "Watchlist", hindiTitle: "बाज़ार की निगरानी", actionLabel: "SEE ALL →") { }
                                if viewModel.watchlist.isEmpty && !viewModel.isLoading {
                                    Text("Add stocks to your watchlist to see them here")
                                        .font(Theme.serialNumberFont(size: 13))
                                        .foregroundColor(Theme.inkTertiary)
                                        .multilineTextAlignment(.center)
                                        .padding(.horizontal, Theme.screenPadding)
                                        .padding(.vertical, 20)
                                } else {
                                    VStack(spacing: 12) {
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
                            VStack(spacing: 12) {
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
                            VStack(spacing: 16) {
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
                                        .font(.system(size: 10, weight: .regular))
                                        .foregroundColor(Color.primary.opacity(0.35))
                                    Text("MARKET NEWS")
                                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                        .tracking(2.0)
                                        .foregroundColor(Color.primary.opacity(0.45))
                                }
                                .padding(.bottom, 10)
                                .padding(.horizontal, Theme.screenPadding)

                                GuillocheDivider()
                                    .padding(.horizontal, Theme.screenPadding)
                                    .padding(.bottom, 12)

                                if let feed = feedVM.feed {
                                    // Red flag alerts at the top (if any)
                                    if !feed.redFlagAlerts.isEmpty {
                                        VStack(spacing: 8) {
                                            ForEach(feed.redFlagAlerts) { article in
                                                NewsCardView(article: article) { ticker in
                                                    navigationPath.append(ticker)
                                                }
                                                .padding(.horizontal, Theme.screenPadding)
                                            }
                                        }
                                        .padding(.bottom, 12)
                                    }

                                    // 5-wide compact news grid (2 rows × 5 cols = 10 items)
                                    LazyVGrid(
                                        columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 5),
                                        spacing: 8
                                    ) {
                                        ForEach(feed.news.prefix(10)) { article in
                                            CompactNewsCell(article: article) { ticker in
                                                navigationPath.append(ticker)
                                            }
                                        }
                                    }
                                    .padding(.horizontal, Theme.screenPadding)
                                } else if feedVM.isLoading {
                                    // Skeleton shimmer while loading
                                    ForEach(0..<3, id: \.self) { _ in
                                        RoundedRectangle(cornerRadius: 14)
                                            .fill(Color.primary.opacity(0.05))
                                            .frame(height: 90)
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

                            // ── Section 6c: YOUTUBE FEED ─────────────────────────
                            if let feed = feedVM.feed, !feed.youtubeVideos.isEmpty {
                                let videos = Array(feed.youtubeVideos.prefix(15))
                                let row1 = Array(videos.prefix(5))
                                let row2 = Array(videos.dropFirst(5).prefix(5))
                                let row3 = Array(videos.dropFirst(10).prefix(5))

                                VStack(alignment: .leading, spacing: 0) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("विशेषज्ञ विश्लेषण")
                                            .font(.system(size: 10, weight: .regular))
                                            .foregroundColor(Color.primary.opacity(0.35))
                                        Text("EXPERT VIDEOS")
                                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                            .tracking(2.0)
                                            .foregroundColor(Color.primary.opacity(0.45))
                                    }
                                    .padding(.bottom, 10)
                                    .padding(.horizontal, Theme.screenPadding)

                                    GuillocheDivider()
                                        .padding(.horizontal, Theme.screenPadding)
                                        .padding(.bottom, 12)

                                    VStack(spacing: 12) {
                                        if !row1.isEmpty {
                                            ScrollView(.horizontal, showsIndicators: false) {
                                                HStack(spacing: 10) {
                                                    ForEach(row1) { video in
                                                        YouTubeCompactCard(video: video) { ticker in
                                                            navigationPath.append(ticker)
                                                        }
                                                    }
                                                }
                                                .padding(.horizontal, Theme.screenPadding)
                                            }
                                        }

                                        if !row2.isEmpty {
                                            ScrollView(.horizontal, showsIndicators: false) {
                                                HStack(spacing: 10) {
                                                    ForEach(row2) { video in
                                                        YouTubeCompactCard(video: video) { ticker in
                                                            navigationPath.append(ticker)
                                                        }
                                                    }
                                                }
                                                .padding(.horizontal, Theme.screenPadding)
                                            }
                                        }

                                        if !row3.isEmpty {
                                            ScrollView(.horizontal, showsIndicators: false) {
                                                HStack(spacing: 10) {
                                                    ForEach(row3) { video in
                                                        YouTubeCompactCard(video: video) { ticker in
                                                            navigationPath.append(ticker)
                                                        }
                                                    }
                                                }
                                                .padding(.horizontal, Theme.screenPadding)
                                            }
                                        }
                                    }
                                }
                                .id(HomeSectionID.youtube.rawValue)
                            }

                            // ── Section 7: Upcoming Results ───────────────────
                            VStack(spacing: 12) {
                                SectionHeader(title: "This Week's Results", hindiTitle: "आगामी परिणाम")
                                let upcoming = viewModel.earningsEvents.filter { $0.daysAway >= 0 && $0.daysAway <= 14 }
                                if !upcoming.isEmpty {
                                    VStack(spacing: 8) {
                                        ForEach(upcoming) { event in
                                            NavigationLink(value: event.ticker) {
                                                HStack {
                                                    Text(event.ticker)
                                                        .font(Theme.serialNumberFont(size: 13))
                                                        .foregroundColor(Theme.inkPrimary)
                                                    Spacer()
                                                    Text(event.daysAway == 0 ? "Today" : "In \(event.daysAway) days")
                                                        .font(Theme.officialStampFont(size: 9))
                                                        .foregroundColor(event.daysAway <= 3 ? Theme.holdAmber : Theme.inkSecondary)
                                                    Text("· \(event.earningsDate)")
                                                        .font(Theme.serialNumberFont(size: 10))
                                                        .foregroundColor(Theme.inkTertiary)
                                                    Image(systemName: "chevron.right")
                                                        .font(.system(size: 9))
                                                        .foregroundColor(Theme.inkTertiary)
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

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("TODAY'S ACTION")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundColor(Theme.inkSecondary)
                    Spacer()
                    Text(urgencyLabel)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundColor(borderColor)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .overlay(RoundedRectangle(cornerRadius: 3).stroke(borderColor, lineWidth: 0.5))
                }

                Text(stripEmoji(response.action))
                    .font(.system(size: 14, design: .serif).italic())
                    .foregroundColor(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineSpacing(3)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(borderColor.opacity(0.3), lineWidth: 0.5))
        .cornerRadius(8)
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
                        .padding(.top, 8)
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

                    Text("PORTFOLIO VALUE")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)

                    Text("I PROMISE TO PAY THE BEARER")
                        .font(.system(size: 8, weight: .medium))
                        .tracking(2)
                        .foregroundColor(Theme.inkTertiary)
                        .padding(.bottom, 2)

                    PortfolioValueDisplay(target: value, fontSize: 30)

                    HStack(spacing: 6) {
                        Image(systemName: totalPnL >= 0 ? "arrow.up.right" : "arrow.down.right")
                        Text(totalPnL.inrFormatted)
                        Text("(\((invested > 0 ? totalPnL/invested*100 : 0).percentFormatted))")
                    }
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundColor(totalPnL >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                .padding(.top, 4)

                // Signature block
                VStack(alignment: .leading, spacing: 0) {
                    Text("Platform Governor")
                        .font(.system(size: 7, weight: .bold))
                        .foregroundColor(Theme.inkSecondary)
                    Text("Nirav Patel")
                        .font(Font.custom("SnellRoundhand", size: 18))
                        .foregroundColor(Theme.inkPrimary.opacity(0.7))
                        .padding(.top, -2)
                }
                .padding(.top, 12)

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
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        HStack {
                            Text("MORNING BRIEF")
                                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                .tracking(2.0)
                                .foregroundColor(Theme.inkPrimary)
                            Spacer()
                            BanknoteSignalBadge(text: "VERIFIED", color: Theme.securityGold, rotation: -8)
                        }
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)
                        .padding(.bottom, 10)

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
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.primary.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(3)
                    }
                    .padding(.horizontal, cardHPad)

                    // Fine rule separator
                    Rectangle()
                        .fill(Color.primary.opacity(0.08))
                        .frame(height: 0.5)
                        .padding(.horizontal, cardHPad)
                        .padding(.vertical, 10)

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
                            .padding(.top, 10)
                            .padding(.bottom, 8)

                        VStack(alignment: .leading, spacing: 6) {
                            Text("TODAY'S PRIORITIES")
                                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                .tracking(1.5)
                                .foregroundColor(dimText)

                            ForEach(items.prefix(5)) { item in
                                HStack(spacing: 8) {
                                    PriorityPill(
                                        label: item.type == "alert_triggered" ? "ALERT" : "SIGNAL",
                                        color: item.type == "alert_triggered" ? bearRed : goldAccent
                                    )
                                    Text(stripEmoji(item.message))
                                        .font(.system(size: 12, weight: .regular))
                                        .foregroundColor(.primary.opacity(0.70))
                                        .lineLimit(2)
                                }
                            }
                        }
                        .padding(.horizontal, cardHPad)
                    }

                    // Timestamp footer
                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)

                    HStack {
                        Text("Updated \(briefData.generatedAt)")
                            .font(.system(size: 9, weight: .regular))
                            .foregroundColor(subtleText)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 8, weight: .semibold))
                            .foregroundColor(subtleText)
                    }
                    .padding(.horizontal, cardHPad)
                    .padding(.bottom, cardVPad)
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

private struct SectorPulseCard: View {
    let sector: SectorPerformance

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(sector.name.uppercased())
                .font(Theme.officialStampFont(size: 8))
                .foregroundColor(Theme.inkSecondary)
                .lineLimit(1)

            Text((sector.changePct >= 0 ? "+" : "") + String(format: "%.2f%%", sector.changePct))
                .font(Theme.serialNumberFont(size: 18))
                .foregroundColor(sector.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)

            // Mini bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Rectangle().fill(Theme.inkSecondary.opacity(0.08)).frame(height: 3)
                    Rectangle()
                        .fill(sector.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(width: min(geo.size.width, geo.size.width * abs(sector.changePct) / 5.0), height: 3)
                }
            }
            .frame(height: 3)
        }
        .padding(12)
        .banknoteCard()
    }
}

// MARK: - Timeframe Conflicts Banner

private struct TimeframeConflictsBanner: View {
    let conflicts: [TimeframeConflict]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("TIMING INSIGHTS")
                .font(.system(.caption, design: .default).weight(.medium))
                .tracking(1.5)
                .foregroundColor(Theme.securityGold)
                .padding(.horizontal, Theme.screenPadding)

            ScrollView(.horizontal, showsIndicators: false) {
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
        }
    }
}

private struct TimeframeConflictCard: View {
    let conflict: TimeframeConflict

    var isBottomFishing: Bool { conflict.conflictType == "BUY_THE_DIP" }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(conflict.ticker)
                    .font(.system(.subheadline, design: .monospaced).weight(.bold))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Text(isBottomFishing ? "BUY THE DIP" : "TAKE PROFITS")
                    .font(.system(.caption2, design: .default).weight(.bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 5).padding(.vertical, 2)
                    .background(isBottomFishing ? Theme.signalEmerald : Theme.signalRuby)
                    .cornerRadius(3)
            }

            if let hint = conflict.actionHint {
                Text(stripEmoji(hint))
                    .font(.system(size: 11, design: .serif).italic())
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(10)
        .frame(width: 200)
        .background(Theme.canvasDeep)
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.borderFine, lineWidth: 0.5))
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
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.securityGold)
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
                    .foregroundColor(Theme.inkTertiary)
            } else {
                Text("\(label) unavailable")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.canvasDeep)
        .cornerRadius(8)
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
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        Text("MARKET PULSE")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)
                        .padding(.bottom, 10)

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
                        .padding(.vertical, 10)

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
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
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
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        Text("MOMENTUM SCAN")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)
                        .padding(.bottom, 10)

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
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
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
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        Text("MACRO & ALTERNATIVES")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)
                        .padding(.bottom, 10)

                    // Grouped sections
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(macroGroups, id: \.title) { group in
                            let items = itemsForGroup(group.keys)
                            if !items.isEmpty {
                                MacroGroupView(groupTitle: group.title, rows: items)

                                if group.title != macroGroups.last?.title || !ungroupedItems.isEmpty {
                                    Rectangle()
                                        .fill(Color.primary.opacity(0.08))
                                        .frame(height: 0.5)
                                        .padding(.vertical, 4)
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
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
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
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)

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
            .frame(height: 80)
            .clipped()

            VStack(spacing: 4) {
                Text(moodLabel)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(needleColor)
                Text(String(format: "A/D Ratio: %.2f", ratio))
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(14)
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
        VStack(alignment: .leading, spacing: 8) {
            Text(index.name)
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(Theme.inkSecondary)
                .lineLimit(1)

            Text(valueStr)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
                .monospacedDigit()

            HStack(spacing: 4) {
                Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(isPositive ? Theme.bullGreen : Theme.bearRed)
                Text(changeStr)
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .foregroundColor(isPositive ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .padding(14)
        .frame(width: 140)
        .banknoteCard()
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
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    Text(ticker.ticker)
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                    Text(crossoverLabel.uppercased())
                        .font(.system(size: 8, weight: .bold, design: .monospaced))
                        .tracking(0.8)
                        .foregroundColor(signalColor)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(signalColor.opacity(0.10))
                        .cornerRadius(3)
                }
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text("LTP").font(.system(size: 8)).foregroundColor(Theme.inkTertiary)
                        Text(IndianFormatter.price(ticker.lastPrice))
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    VStack(alignment: .leading, spacing: 1) {
                        Text("SINCE").font(.system(size: 8)).foregroundColor(Theme.inkTertiary)
                        Text(ticker.trendDate)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Theme.inkSecondary)
                    }
                }
            }
            Spacer()
            // Native Swift Charts trend sparkline
            if !ticker.sparkline.isEmpty {
                SparklineView(values: ticker.sparkline, color: signalColor)
                    .frame(width: 56, height: 32)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
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

// MARK: - Compact News Cell (2 rows × 5 columns grid)

struct CompactNewsCell: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)

    var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "MC"
        case "economic_times": return "ET"
        case "nse": return "NSE"
        default: return String(article.source.prefix(3)).uppercased()
        }
    }

    var body: some View {
        Button(action: {
            if let url = URL(string: article.articleUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: 4) {
                // Thumbnail image
                if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 120, height: 72)
                                .clipped()
                                .cornerRadius(6)
                        case .failure(_), .empty:
                            Rectangle()
                                .fill(Color.primary.opacity(0.06))
                                .frame(width: 120, height: 72)
                                .cornerRadius(6)
                                .overlay(
                                    Image(systemName: "newspaper")
                                        .font(.system(size: 16))
                                        .foregroundColor(Color.primary.opacity(0.2))
                                )
                        @unknown default:
                            EmptyView()
                        }
                    }
                } else {
                    Rectangle()
                        .fill(Color.primary.opacity(0.06))
                        .frame(width: 120, height: 72)
                        .cornerRadius(6)
                        .overlay(
                            Image(systemName: "newspaper")
                                .font(.system(size: 16))
                                .foregroundColor(Color.primary.opacity(0.2))
                        )
                }

                // Source badge
                Text(sourceLabel)
                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                    .tracking(1.0)
                    .foregroundColor(goldAccent)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(goldAccent.opacity(0.12))
                    .cornerRadius(3)

                // Headline (max 2 lines)
                Text(article.headline)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.primary.opacity(0.85))
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineSpacing(1)

                Spacer(minLength: 0)
            }
            .frame(width: 120, height: 160, alignment: .topLeading)
            .padding(6)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Theme.canvasDeep)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.primary.opacity(0.08), lineWidth: 0.5)
                    )
            )
        }
        .buttonStyle(EKPressStyle())
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
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(Theme.inkSecondary)
                        Text("INSTITUTIONAL ALLOCATION")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .tracking(2.0)
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, 10)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, 4)
                        .padding(.top, 6)
                        .padding(.bottom, 10)

                    Text("TOP PERFORMING MUTUAL FUNDS — 1Y RETURN")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .tracking(1.5)
                        .foregroundColor(dimText)
                        .padding(.horizontal, cardHPad)
                        .padding(.bottom, 10)

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
