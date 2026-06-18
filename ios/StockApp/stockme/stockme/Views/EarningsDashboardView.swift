import SwiftUI
import Combine
import UserNotifications
import EventKit

// MARK: - Earnings Dashboard ViewModel

@MainActor
class EarningsDashboardViewModel: ObservableObject {
    @Published var progress: EarningsProgressResponse? = nil
    @Published var feed: [EarningsResult] = []
    @Published var calendarDayResults: [EarningsCalendarItem] = []
    @Published var calendarSparklines: [String: [Double]] = [:]  // ticker → sparkline
    @Published var postResultMovers: [PostResultMover] = []
    @Published var estimates: [String: EarningsEstimate] = [:]
    @Published var selectedMarketCap: String = "all"
    @Published var selectedSort: String = "latest"
    @Published var comparisonMode: String = "yoy"
    @Published var selectedCalendarDate: Date = Date()
    @Published var bookmarkedScreeners: Set<String> = []
    @Published var isLoading = false

    /// Backend pre-computed aggregates from /api/v1/market/dashboard-pulse
    @Published var yoyMarketHealth: YoYMarketHealth? = nil
    @Published var capIndexAggregator: [CapIndexGridEntry] = []

    /// Per-section error diagnostics — shown inline when a section fails
    @Published var progressError: String? = nil
    @Published var feedError: String? = nil
    @Published var calendarError: String? = nil
    @Published var moversError: String? = nil
    @Published var alertError: String? = nil
    @Published var dashboardError: String? = nil
    @Published var feedDataSource: String? = nil
    @Published var feedDiagnostic: String? = nil

    /// Diagnostic contexts — attached to every error for full telemetry
    private func trackError(_ message: String, endpoint: String, classification: String = "INFRASTRUCTURE_EXCEPTION") {
        let diag = ErrorDiagnostic(endpoint: endpoint, swiftFile: "EarningsDashboardView.swift", classification: classification)
        GlobalErrorDiagnoser.shared.track(message, diagnostic: diag)
    }

    /// True if ALL sections failed — triggers full-page error canvas
    var isTotalFailure: Bool {
        progress == nil && feed.isEmpty && postResultMovers.isEmpty
            && (progressError != nil || feedError != nil || moversError != nil)
    }

    private var refreshTask: Task<Void, Never>?

    func load() {
        refreshTask?.cancel()
        refreshTask = Task {
            isLoading = true
            progressError = nil; feedError = nil; moversError = nil; dashboardError = nil

            // Pre-computed aggregates from dashboard-pulse (yoy_health + cap_grid)
            let dash = await NetworkManager.shared.fetchExtendedMarketDashboard()
            self.yoyMarketHealth = dash?.yoyMarketHealth
            self.capIndexAggregator = dash?.capIndexAggregator ?? []

            // Progress
            do { self.progress = try await NetworkManager.shared.fetchEarningsProgress() }
            catch { self.progressError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription }

            // Feed — use ranked endpoint for diagnostic info
            if let rankedResp = await NetworkManager.shared.fetchRankedEarningsFeed(sort: selectedSort) {
                self.feed = rankedResp.results
                self.feedDataSource = rankedResp.dataSource ?? "unknown"
                self.feedDiagnostic = rankedResp.diagnostic
                if let err = rankedResp.error {
                    self.feedError = err
                }
                if (rankedResp.dataSource ?? "") == "empty" || rankedResp.results.isEmpty {
                    if rankedResp.diagnostic == nil && rankedResp.error == nil {
                        // Old server — no diagnostic fields. Explain the situation.
                        self.feedDiagnostic = "Server returned empty results without diagnostic info. The server may be running an older version without the yfinance fallback. Redeploy the backend to get real earnings data."
                    }
                    self.feedError = nil  // not a fetch error — just no data
                }
            } else {
                self.feedError = "Feed endpoint unreachable or JSON decode failed. Check: (1) Is the server running? (2) Is the backend URL correct in Settings? (3) Check iOS console for details."
            }

            // Movers
            do { self.postResultMovers = try await NetworkManager.shared.fetchPostResultMovers() }
            catch { self.moversError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription }

            await loadCalendarDay(date: selectedCalendarDate)
            isLoading = false
        }
    }

    func loadCalendarDay(date: Date) async {
        calendarError = nil
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        let dateStr = f.string(from: date)
        // Use enhanced endpoint with sparkline price data
        if let calResp = await NetworkManager.shared.fetchEarningsCalendar(date: dateStr) {
            self.calendarDayResults = calResp.results
            // Build sparkline lookup: ticker → sparkline array
            var sparkMap: [String: [Double]] = [:]
            for item in calResp.results {
                if !item.sparkline.isEmpty {
                    sparkMap[item.ticker] = item.sparkline
                }
            }
            self.calendarSparklines = sparkMap
            if let err = calResp.error {
                self.calendarError = err
            }
        } else {
            self.calendarDayResults = []
        }
    }

    func setAlert(ticker: String, date: String, userId: Int) async {
        alertError = nil
        do {
            try await NetworkManager.shared.setEarningsAlert(userId: userId, ticker: ticker, date: date)
        } catch {
            self.alertError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription
        }
    }

    func selectCalendarDate(_ date: Date) {
        selectedCalendarDate = date
        Task { await loadCalendarDay(date: date) }
    }

    func toggleScreenerBookmark(_ key: String) {
        if bookmarkedScreeners.contains(key) {
            bookmarkedScreeners.remove(key)
        } else {
            bookmarkedScreeners.insert(key)
        }
    }

    var filteredFeed: [EarningsResult] {
        switch selectedSort {
        case "best":
            return feed.sorted { $0.netProfitGrowthPct > $1.netProfitGrowthPct }
        case "worst":
            return feed.sorted { $0.netProfitGrowthPct < $1.netProfitGrowthPct }
        default:
            return feed
        }
    }

    var aggregateRevGrowth: Double {
        guard !feed.isEmpty else { return 0 }
        let vals = feed.map { $0.revenueGrowthPct }
        return vals.reduce(0, +) / Double(vals.count)
    }

    var aggregateProfitGrowth: Double {
        guard !feed.isEmpty else { return 0 }
        let vals = feed.map { $0.netProfitGrowthPct }
        return vals.reduce(0, +) / Double(vals.count)
    }
}

// MARK: - Main Earnings Dashboard

struct EarningsDashboardView: View {
    @StateObject private var vm = EarningsDashboardViewModel()
    @EnvironmentObject var authManager: AuthManager
    @State private var selectedTab: Int = 0  // 0=Progress, 1=Calendar, 2=Feed, 3=Screeners, 4=Variance, 5=PostResult
    @AppStorage("earningsComparisonMode") private var comparisonMode = "yoy"

    let tabs = ["Progress", "Calendar", "Feed", "Screeners", "Variance", "Post-Result"]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: Theme.Spacing.none) {
                headerBar
                tabBar
                tabContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxHeight: .infinity, alignment: .top)
        }
        .task { vm.load() }
        .onChange(of: vm.selectedMarketCap) { _, _ in vm.load() }
        .onChange(of: vm.selectedSort) { _, _ in vm.load() }
    }

    // MARK: Header

    private var headerBar: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("EARNINGS DASHBOARD")
                    .font(.caption.weight(.bold).monospaced())
                    .tracking(2)
                    .foregroundStyle(Theme.securityGold)
                if let p = vm.progress {
                    Text("\(p.reported)/\(p.total) results declared")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkSecondary)
                } else if let err = vm.progressError {
                    Text("⚠ \(err.prefix(60))")
                        .font(.caption.weight(.medium).monospaced())
                        .foregroundStyle(Theme.bearRed)
                        .lineLimit(1)
                }
            }
            Spacer()
            // QoQ / YoY global toggle (2.3 / 1.3 requirement)
            Picker("Mode", selection: $comparisonMode) {
                Text("YoY").tag("yoy")
                Text("QoQ").tag("qoq")
            }
            .pickerStyle(.segmented)
            .frame(minWidth: 100)
            .onChange(of: comparisonMode) { _, val in vm.comparisonMode = val }
        }
        .padding(.horizontal, 16)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.medium)
        .background(Theme.canvasDeep)
    }

    // MARK: Tab Bar

    private var tabBar: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.small) {
                ForEach(Array(tabs.enumerated()), id: \.offset) { idx, name in
                    Button(action: { selectedTab = idx }) {
                        Text(name)
                            .font(.caption.weight(selectedTab == idx ? .bold : .regular))
                            .foregroundStyle(selectedTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(
                                selectedTab == idx
                                    ? Theme.securityGold.opacity(0.10)
                                    : Color.clear
                            )
                            .cornerRadius(Theme.CornerRadius.tight)
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.tight)
        }
        .scrollIndicators(.hidden)
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    // MARK: Tab Content

    @ViewBuilder
    private var tabContent: some View {
        switch selectedTab {
        case 0: EarningsProgressView(vm: vm)
        case 1: EarningsCalendarView(vm: vm)
        case 2: EarningsFeedView(vm: vm)
        case 3: ScreenerView(vm: vm)
        case 4: VarianceTrackerView(vm: vm)
        case 5: PostResultMonitorView(vm: vm)
        default: EmptyView()
        }
    }
}

// MARK: - 1.1 Earnings Progress View

struct EarningsProgressView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                // Full-page error if everything failed
                if vm.isTotalFailure {
                    ErrorDiagnoserView(
                        error: [
                            vm.progressError.map { "Progress: \($0)" },
                            vm.feedError.map { "Feed: \($0)" },
                            vm.moversError.map { "Movers: \($0)" },
                        ].compactMap { $0 }.joined(separator: "\n\n"),
                        context: ErrorDiagnostic(endpoint: "/api/v1/market/dashboard-pulse", classification: "INFRASTRUCTURE_EXCEPTION"),
                        retryAction: { vm.load() }
                    )
                }

                // Live Reporting Sync Ratio
                if let p = vm.progress {
                    progressCard(p)
                } else if let err = vm.progressError {
                    MarketSectionErrorRow(sectionLabel: "LIVE REPORTING SYNC", errorMessage: err)
                } else {
                    progressCardPlaceholder
                }

                // YoY Aggregate Indicators
                if vm.feedError != nil && vm.feed.isEmpty {
                    MarketSectionErrorRow(sectionLabel: "YoY AGGREGATE INDICATORS", errorMessage: vm.feedError!)
                } else {
                    aggregateCard
                }

                // 1.3 Market Cap Index Aggregator
                marketCapIndexCard
            }
            .padding(Theme.Spacing.card)
        }
        .background(Theme.canvas)
    }

    private func progressCard(_ p: EarningsProgressResponse) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("LIVE REPORTING SYNC")
                .font(.caption2.weight(.bold).monospaced())
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.tight) {
                Text("\(p.reported)")
                    .font(Theme.engravedSerif(size: 36, weight: .bold, relativeTo: .largeTitle))
                    .foregroundStyle(Theme.inkPrimary)
                Text("/\(p.total)")
                    .font(Theme.engravedSerif(size: 20, relativeTo: .title3))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                let pct = p.total > 0 ? Double(p.reported) / Double(p.total) : 0
                Text("\(Int(pct * 100))% filed")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(Theme.bullGreen)
            }

            // Progress bar
            let w = UIScreen.main.bounds.width
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.15))
                let pct = p.total > 0 ? CGFloat(p.reported) / CGFloat(p.total) : 0
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(LinearGradient(
                        colors: [Theme.bullGreen, Theme.securityGold],
                        startPoint: .leading, endPoint: .trailing))
                    .frame(width: w * pct)
            }
            .frame(height: 6)

            Text("companies have declared results against total statutory listed exchange obligations")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private var progressCardPlaceholder: some View {
        let w = UIScreen.main.bounds.width
        return VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 14).frame(width: w * 0.35)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 36).frame(width: w * 0.45)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 6)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var aggregateCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("YoY AGGREGATE MARKET HEALTH")
                .font(.caption2.weight(.bold).monospaced())
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            // Prefer backend pre-computed data, fall back to local feed aggregation
            let revGrowth: Double = vm.yoyMarketHealth?.revenueYoYPct ?? vm.aggregateRevGrowth
            let profitGrowth: Double = vm.yoyMarketHealth?.netProfitYoYPct ?? vm.aggregateProfitGrowth
            let sourceLabel: String = vm.yoyMarketHealth != nil ? "NSE AGGREGATE" : "FEED ESTIMATE"

            HStack(spacing: Theme.Spacing.none) {
                aggregateMetric(
                    label: "AVG REVENUE GROWTH",
                    value: revGrowth,
                    isLoading: vm.isLoading && vm.yoyMarketHealth == nil && vm.feed.isEmpty
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 40).padding(.horizontal, Theme.Spacing.card)
                aggregateMetric(
                    label: "AVG NET PROFIT GROWTH",
                    value: profitGrowth,
                    isLoading: vm.isLoading && vm.yoyMarketHealth == nil && vm.feed.isEmpty
                )
            }

            // Source label
            Text(sourceLabel)
                .font(.caption2.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func aggregateMetric(label: String, value: Double, isLoading: Bool) -> some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
            if isLoading {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.12)).frame(width: colW * 0.17, height: 22)
            } else {
                Text(IndianFormatter.delta(value))
                    .font(.title3.weight(.bold).monospaced())
                    .foregroundStyle(value >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // 1.3 Market Cap Index Aggregator — prefers backend grid, falls back to earnings table
    private var marketCapIndexCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("MARKET CAP INDEX AGGREGATOR")
                .font(.caption2.weight(.bold).monospaced())
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            if !vm.capIndexAggregator.isEmpty {
                // Backend pre-computed grid
                capGridTable
            } else if let dashErr = vm.dashboardError, vm.feed.isEmpty {
                // Backend failed + no feed fallback
                MarketSectionErrorRow(sectionLabel: "CAP INDEX GRID", errorMessage: dashErr)
            } else {
                // Fallback: per-company earnings table
                // 1.3 Multi-Tier Index Weight Tabs
                ScrollView(.horizontal) {
                    HStack(spacing: Theme.Spacing.tight) {
                        ForEach(["all", "nifty50", "large_cap", "mid_cap", "small_cap"], id: \.self) { cap in
                            Button(action: { vm.selectedMarketCap = cap }) {
                                Text(capLabel(cap))
                                    .font(.caption.weight(vm.selectedMarketCap == cap ? .bold : .regular))
                                    .foregroundStyle(vm.selectedMarketCap == cap ? Theme.securityGold : Theme.inkSecondary)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 5)
                                    .background(vm.selectedMarketCap == cap ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                                    .cornerRadius(Theme.CornerRadius.tight)
                                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                            }
                        }
                    }
                }
                .scrollIndicators(.hidden)
                earningsTable
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// Backend pre-computed cap grid table (from /api/v1/market/dashboard-pulse)
    private var capGridTable: some View {
        let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2  // available content width
        return VStack(spacing: Theme.Spacing.none) {
            // Header
            HStack(spacing: Theme.Spacing.none) {
                Text("BRACKET").tableHeaderStyle().frame(width: colW * 0.20, alignment: .leading)
                Text("MCAP").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("REVENUE").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PROFIT").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PE").tableHeaderStyle().frame(width: colW * 0.10, alignment: .trailing)
            }
            .padding(.horizontal, 8).padding(.vertical, 6)
            .background(Theme.canvasDeep)

            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

            ForEach(vm.capIndexAggregator) { row in
                HStack(spacing: Theme.Spacing.none) {
                    Text(row.capBracket.uppercased())
                        .font(.caption2.weight(.bold).monospaced())
                        .foregroundStyle(row.capBracket == "All" ? Theme.securityGold : Theme.inkPrimary)
                        .frame(width: colW * 0.20, alignment: .leading)
                    Text(row.avgMarketCapCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgRevenueCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgNetProfitCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgPeRatio.map { String(format: "%.1f", $0) } ?? "—")
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkTertiary)
                        .frame(width: colW * 0.10, alignment: .trailing)
                }
                .padding(.horizontal, 8).padding(.vertical, 7)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            }
        }
        .cornerRadius(Theme.CornerRadius.tight)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func capLabel(_ cap: String) -> String {
        switch cap {
        case "nifty50": return "Nifty 50"
        case "large_cap": return "Large Cap"
        case "mid_cap": return "Mid Cap"
        case "small_cap": return "Small Cap"
        default: return "All"
        }
    }

    private var earningsTable: some View {
        let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2
        return VStack(spacing: Theme.Spacing.none) {
            // Header row
            HStack(spacing: Theme.Spacing.none) {
                Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                Text("REVENUE").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
                Text("GROSS PROFIT").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
                Text("NET PROFIT").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(Theme.canvasDeep)

            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

            if vm.feed.isEmpty && vm.isLoading {
                ForEach(0..<4, id: \.self) { _ in
                    tableRowPlaceholder
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                }
            } else {
                ForEach(vm.filteredFeed.prefix(10)) { result in
                    earningsTableRow(result, tableWidth: colW)
                    if result.id != vm.filteredFeed.prefix(10).last?.id {
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                    }
                }
            }
        }
        .cornerRadius(Theme.CornerRadius.tight)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func earningsTableRow(_ r: EarningsResult, tableWidth: CGFloat) -> some View {
        let profitGrowth = r.netProfitGrowthPct
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(r.ticker)
                    .font(.caption.weight(.semibold).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(r.isConsolidated ? "Consolidated" : "Standalone")
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(IndianFormatter.formatLakhsCrores(r.revenue))
                .font(.caption.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkPrimary)
                .frame(minWidth: tableWidth * 0.22, alignment: .trailing)

            Text(r.grossProfit != nil ? IndianFormatter.formatLakhsCrores(r.grossProfit!) : "—")
                .font(.caption.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkSecondary)
                .frame(minWidth: tableWidth * 0.22, alignment: .trailing)

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(IndianFormatter.formatLakhsCrores(r.netProfit))
                    .font(.caption.weight(.medium).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(IndianFormatter.delta(profitGrowth))
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(profitGrowth >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(minWidth: tableWidth * 0.22, alignment: .trailing)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 8)
    }

    private var tableRowPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.17, height: 12)
            Spacer()
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, Theme.Spacing.medium)
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 1.2 Earnings Calendar View

// MARK: - Mini Sparkline (7-day price context)

struct MiniSparkline: View {
    let data: [Double]
    let color: Color

    var body: some View {
        let sparkW: CGFloat = 36
        let sparkH: CGFloat = 16
        let minY = data.min() ?? 0
        let maxY = data.max() ?? 1
        let range = max(maxY - minY, 0.01)
        let stepX = sparkW / CGFloat(max(data.count - 1, 1))

        Path { path in
            for (i, val) in data.enumerated() {
                let x = CGFloat(i) * stepX
                let y = sparkH * CGFloat(1 - (val - minY) / range)
                if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                else { path.addLine(to: CGPoint(x: x, y: y)) }
            }
        }
        .stroke(color.opacity(0.6), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
    }
}

// MARK: - Calendar View

struct EarningsCalendarView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @EnvironmentObject var authManager: AuthManager
    @State private var alertSetFor: String? = nil

    private let calendar = Calendar.current
    
    private func addEventToCalendar(title: String, dateStr: String) {
        let eventStore = EKEventStore()
        
        let completion: EKEventStoreRequestAccessCompletionHandler = { (granted, error) in
            if granted && error == nil {
                let event = EKEvent(eventStore: eventStore)
                event.title = title
                
                let df = DateFormatter()
                df.dateFormat = "yyyy-MM-dd"
                if let date = df.date(from: dateStr) {
                    event.startDate = date
                    event.endDate = date.addingTimeInterval(60 * 60)
                    event.notes = "Earnings report"
                    event.calendar = eventStore.defaultCalendarForNewEvents
                    
                    do {
                        try eventStore.save(event, span: .thisEvent)
                        DispatchQueue.main.async {
                            HapticManager.notification(.success)
                        }
                    } catch {
                        DispatchQueue.main.async {
                            HapticManager.notification(.error)
                        }
                    }
                }
            }
        }
        
        if #available(iOS 17.0, *) {
            eventStore.requestWriteOnlyAccessToEvents(completion: completion)
        } else {
            eventStore.requestAccess(to: .event, completion: completion)
        }
    }

    // Generate 14 days window centred on today
    private var calendarDays: [Date] {
        let today = Date()
        return (-3...10).compactMap { offset in
            calendar.date(byAdding: .day, value: offset, to: today)
        }
    }

    private func dayLabel(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "dd"
        return f.string(from: date)
    }
    private func monthLabel(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "MMM"
        return f.string(from: date).uppercased()
    }
    private func apiDate(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }
    private func isSelected(_ date: Date) -> Bool {
        calendar.isDate(date, inSameDayAs: vm.selectedCalendarDate)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                // 1.2 Horizontal Calendar Day Scroller
                calendarScrollRow
                SectionDivider()
                // Results for selected date
                selectedDayResults
            }
            .padding(Theme.Spacing.card)
        }
        .background(Theme.canvas)
    }

    private var calendarScrollRow: some View {
        let cellW = UIScreen.main.bounds.width / 5.5
        return ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.medium) {
                ForEach(calendarDays, id: \.self) { date in
                    Button(action: { vm.selectCalendarDate(date) }) {
                        calendarDayCell(date)
                    }
                    .buttonStyle(EKPressStyle())
                    .frame(width: cellW)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.small)
        }
        .scrollIndicators(.hidden)
    }

    private func calendarDayCell(_ date: Date) -> some View {
        let sel = isSelected(date)
        let dayStr = apiDate(date)
        let dayResults = vm.calendarDayResults.filter { $0.resultDate == dayStr }
        let count = dayResults.count
        // Extract sparkline from any result that has it
        let sparkData = dayResults.first(where: { !$0.sparkline.isEmpty })?.sparkline ?? []

        return VStack(spacing: Theme.Spacing.small) {
            Text(monthLabel(date))
                .font(.caption2.weight(.medium).monospaced())
                .foregroundStyle(sel ? Theme.securityGold : Theme.inkTertiary)
            Text(dayLabel(date))
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundStyle(sel ? Theme.inkPrimary : Theme.inkSecondary)

            // Mini sparkline for dates with price data
            if !sparkData.isEmpty {
                MiniSparkline(data: sparkData, color: sel ? Theme.securityGold : Theme.inkTertiary)
                    .frame(width: 36, height: 16)
            } else if count > 0 {
                Text("\(count)")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(sel ? Theme.securityGold : Theme.inkTertiary)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(sel ? Theme.securityGold.opacity(0.15) : Theme.inkTertiary.opacity(0.08))
                    .cornerRadius(Theme.CornerRadius.small)
            } else {
                Color.clear.frame(height: 16)
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
        .background(sel ? Theme.securityGold.opacity(0.08) : Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(sel ? Theme.securityGold.opacity(0.4) : Theme.borderSage, lineWidth: sel ? 1 : 0.5)
        )
    }

    // 1.2 Earnings Count Volume Badge on day header
    private var selectedDayResults: some View {
        let humanDate: String = {
            let df = DateFormatter()
            df.dateFormat = "dd MMM"
            return df.string(from: vm.selectedCalendarDate)
        }()
        let count = vm.calendarDayResults.count
        return VStack(alignment: .leading, spacing: Theme.Spacing.standard) {

            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    // 1.2 count badge in title
                    Text("\(humanDate) — \(count) Earnings")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("Tap a company row to set an earnings alert")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                }
                Spacer()
            }

            if vm.calendarDayResults.isEmpty {
                Text("No results scheduled for this date.")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 24)
            } else {
                ForEach(vm.calendarDayResults) { result in
                    calendarResultRow(result)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func calendarResultRow(_ r: EarningsCalendarItem) -> some View {
        let userId = authManager.currentUser?.userId ?? 0
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                HStack(spacing: Theme.Spacing.tight) {
                    Text(r.ticker)
                        .font(.footnote.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(r.isConsolidated ? "Consol" : "Standalone")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(Theme.inkTertiary.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.small)
                    // 7-day price change badge
                    if let chg = r.priceChange7dPct {
                        Text(IndianFormatter.delta(chg))
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(chg >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                Text(r.companyName)
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
                // Sparkline row
                if !r.sparkline.isEmpty {
                    MiniSparkline(data: r.sparkline, color: (r.priceChange7dPct ?? 0) >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: UIScreen.main.bounds.height * 0.024)
                        .padding(.top, 2)
                }
            }
            Spacer()
            // 1.4 Embedded Alert Trigger
            VStack(spacing: Theme.Spacing.small) {
                Button(action: {
                    Task {
                        do {
                            try await NetworkManager.shared.setEarningsAlert(userId: userId, ticker: r.ticker, date: r.resultDate)
                            alertSetFor = r.ticker
                            HapticManager.notification(.success)
                        } catch {
                            vm.alertError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription
                            HapticManager.notification(.error)
                        }
                    }
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: alertSetFor == r.ticker ? "bell.fill" : "bell")
                            .font(.caption)
                        Text("Alert")
                            .font(.caption.weight(.medium))
                    }
                    .frame(width: colW * 0.17)
                    .foregroundStyle(alertSetFor == r.ticker ? Theme.securityGold : Theme.inkSecondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(alertSetFor == r.ticker ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.tight)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                }
                
                Button(action: {
                    addEventToCalendar(title: "\(r.ticker) Earnings", dateStr: r.resultDate)
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "calendar.badge.plus")
                            .font(.caption)
                        Text("iCal")
                            .font(.caption.weight(.medium))
                    }
                    .frame(width: colW * 0.17)
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.tight)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                }
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }
}

// MARK: - 2.1 / 2.2 Earnings Feed View

struct EarningsFeedView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            // 2.2 Tabbed Performance Sorting Grid
            sortTabBar
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.standard) {
                    if vm.isLoading && vm.feed.isEmpty {
                        ForEach(0..<6, id: \.self) { _ in feedCardPlaceholder }
                    } else if vm.filteredFeed.isEmpty {
                        // Universal diagnostic error display
                        ErrorDiagnoserView(
                            error: vm.feedError ?? vm.feedDiagnostic
                                ?? (vm.feedDataSource != nil
                                    ? "Data source: \(vm.feedDataSource!). No results available.\n\nThe backend has no earnings records. Run an AI analysis on a stock to populate data."
                                    : "Backend returned empty results.\n\nLikely cause: No stock analyses have been run yet. The earnings feed reads from the Analysis History database. Run an AI analysis on a stock first to populate earnings data."),
                            context: ErrorDiagnostic(
                                endpoint: "/api/v1/earnings/feed",
                                classification: vm.feedError != nil ? "INFRASTRUCTURE_EXCEPTION" : "DATA_EMPTY"
                            ),
                            retryAction: { vm.load() }
                        )
                    } else {
                        ForEach(vm.filteredFeed) { result in
                            EarningsResultCard(result: result, comparisonMode: vm.comparisonMode)
                        }
                    }
                }
                .padding(Theme.Spacing.card)
            }
        }
        .background(Theme.canvas)
    }

    private var sortTabBar: some View {
        VStack(spacing: Theme.Spacing.none) {
            HStack(spacing: Theme.Spacing.none) {
                ForEach([("latest", "Latest Results"), ("best", "Best Performer"), ("worst", "Worst Performer")], id: \.0) { key, label in
                    Button(action: { vm.selectedSort = key }) {
                        Text(label)
                            .font(.caption.weight(vm.selectedSort == key ? .bold : .regular))
                            .foregroundStyle(vm.selectedSort == key ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.vertical, Theme.Spacing.medium)
                            .frame(maxWidth: .infinity)
                            .background(vm.selectedSort == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            // Data source indicator
            if let src = vm.feedDataSource {
                HStack(spacing: Theme.Spacing.small) {
                    Circle()
                        .fill(src == "database" ? Theme.bullGreen : src == "yfinance_fallback" ? Theme.holdAmber : Theme.bearRed)
                        .frame(width: 5, height: 5)
                    Text("Source: \(src.replacingOccurrences(of: "_", with: " ").uppercased())")
                        .font(.caption2.weight(.medium).monospaced())
                        .foregroundStyle(Theme.inkTertiary.opacity(0.6))
                }
                .padding(.vertical, 3)
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    private var feedCardPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.28, height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.45, height: 11)
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 2.1 / 2.4 Earnings Result Card

struct EarningsResultCard: View {
    let result: EarningsResult
    let comparisonMode: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header row
            HStack(spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(result.ticker)
                            .font(.subheadline.weight(.bold).monospaced())
                            .foregroundStyle(Theme.inkPrimary)
                        Text(result.isConsolidated ? "CONSOL" : "STANDALONE")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(1)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Theme.inkTertiary.opacity(0.08))
                            .cornerRadius(Theme.CornerRadius.small)
                    }
                    Text(result.companyName)
                        .font(.caption)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                    Text(IndianFormatter.price(result.ltp))
                        .font(.footnote.weight(.semibold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(IndianFormatter.delta(result.changePercent))
                        .font(.caption.weight(.bold))
                        .foregroundStyle(result.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }

            // Sparkline price context
            if let spark = result.sparkline, !spark.isEmpty {
                HStack(spacing: Theme.Spacing.medium) {
                    MiniSparkline(data: spark, color: result.netProfitGrowthPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: UIScreen.main.bounds.height * 0.026)
                    if let chg7d = result.priceChange7dPct {
                        Text("7d: \(IndianFormatter.delta(chg7d))")
                            .font(.caption2.weight(.medium).monospaced())
                            .foregroundStyle(chg7d >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                .padding(.vertical, 4)
            }

            SectionDivider()

            // 2.4 Historical period baseline rows
            HStack(spacing: Theme.Spacing.none) {
                metricColumn(
                    label: "NET SALES",
                    current: IndianFormatter.formatLakhsCrores(result.revenue),
                    growth: result.revenueGrowthPct
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 44).padding(.horizontal, Theme.Spacing.medium)
                metricColumn(
                    label: "NET PROFIT",
                    current: IndianFormatter.formatLakhsCrores(result.netProfit),
                    growth: result.netProfitGrowthPct
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 44).padding(.horizontal, Theme.Spacing.medium)
                metricColumn(
                    label: "MARGIN",
                    current: String(format: "%.1f%%", result.netProfitMarginPct),
                    growth: nil
                )
            }

            // 2.1 Absolute elapsed timestamp
            if let reportedDate = result.parsedReportedAt {
                Text(IndianFormatter.elapsed(from: reportedDate))
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }

    private func metricColumn(label: String, current: String, growth: Double?) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1)
                .foregroundStyle(Theme.inkTertiary)
            Text(current)
                .font(.footnote.weight(.semibold).monospaced())
                .foregroundStyle(Theme.inkPrimary)
            if let g = growth {
                Text(IndianFormatter.delta(g))
                    .font(.caption.weight(.bold))
                    .foregroundStyle(g >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - 3.1 / 3.2 / 3.3 Screener View

struct ScreenerPreset: Identifiable {
    let id: String
    let title: String
    let icon: String
    let description: String
    /// Filter function: returns matching EarningsResult items (nil = filter not available locally)
    let filter: (([EarningsResult]) -> [EarningsResult])?
    /// Backend preset key for server-side screening (used when filter is nil)
    let backendPreset: String?
}

fileprivate let screenerPresets: [ScreenerPreset] = [
    ScreenerPreset(
        id: "piotroski",
        title: "Piotroski High Score",
        icon: "checklist",
        description: "Stocks with strong fundamentals based on Piotroski F-Score criteria",
        filter: nil,
        backendPreset: "quality_value"
    ),
    ScreenerPreset(
        id: "breakout",
        title: "Breakout Candidates",
        icon: "arrow.up.forward",
        description: "Stocks showing price breakouts above key resistance levels",
        filter: { feed in feed.filter { $0.changePercent > 5.0 } },
        backendPreset: nil
    ),
    ScreenerPreset(
        id: "oversold",
        title: "Oversold (RSI < 30)",
        icon: "arrow.down.heart",
        description: "Stocks in oversold territory with potential for mean reversion",
        filter: nil,
        backendPreset: "institutional_capitulation"
    ),
    ScreenerPreset(
        id: "golden_cross",
        title: "Golden Cross",
        icon: "arrow.triangle.swap",
        description: "50-day MA crossing above 200-day MA — classic bullish signal",
        filter: nil,
        backendPreset: "earnings_pioneers"
    ),
    ScreenerPreset(
        id: "high_momentum",
        title: "High Momentum",
        icon: "speedometer",
        description: "Stocks with strong upward price and earnings momentum",
        filter: { feed in feed.filter { $0.changePercent > 3.0 || $0.netProfitGrowthPct > 25.0 } },
        backendPreset: nil
    ),
    ScreenerPreset(
        id: "value_picks",
        title: "Value Picks (Low PE)",
        icon: "tag",
        description: "Undervalued stocks trading at low price-to-earnings multiples",
        filter: nil,
        backendPreset: "turnaround"
    ),
]

struct ScreenerView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @State private var selectedPreset: String? = nil
    @State private var filteredResults: [EarningsResult] = []
    @State private var screenerBackendResults: [ScreenerResult] = []
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("स्क्रीनर सूची")
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("STOCK SCREENERS")
                            .font(.caption.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)

                    // Info hint
                    if vm.feed.isEmpty && !vm.isLoading {
                        emptyStateMessage
                            .padding(.horizontal, 16)
                    }

                    // Screener preset cards — banknote aesthetic grid
                    LazyVGrid(
                        columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.standard), count: 2),
                        spacing: Theme.Spacing.standard
                    ) {
                        ForEach(screenerPresets) { preset in
                            screenerPresetCard(preset)
                        }
                    }
                    .padding(.horizontal, 16)

                    // Filtered results section
                    if let selected = selectedPreset, !filteredResults.isEmpty {
                        screenerResultsSection(presetId: selected)
                            .padding(.horizontal, 16)
                    } else if let selected = selectedPreset, !screenerBackendResults.isEmpty {
                        screenerBackendResultsSection(presetId: selected)
                            .padding(.horizontal, 16)
                    } else if selectedPreset != nil && filteredResults.isEmpty && screenerBackendResults.isEmpty && !isLoading {
                        noResultsForPreset
                            .padding(.horizontal, 16)
                    }
                }
                .padding(.bottom, 20)
            }
            .background(Theme.canvas)
            .navigationDestination(for: String.self) { ticker in
                AnalysisScreen(ticker: ticker)
            }
        }
    }

    // MARK: - Empty State (no feed data at all)

    private var emptyStateMessage: some View {
        VStack(spacing: Theme.Spacing.card) {
            Spacer().frame(height: 20)
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.largeTitle.weight(.light))
                .foregroundStyle(Theme.securityGold.opacity(0.6))

            VStack(spacing: Theme.Spacing.tight) {
                Text("SCREENER FEED STATUS")
                    .font(.caption.weight(.bold).monospaced())
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkPrimary)

                // Feed diagnostics
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    ScreenDiagRow(label: "Feed items", value: "\(vm.feed.count)")
                    ScreenDiagRow(label: "Dashboard error", value: vm.dashboardError ?? "none")
                    ScreenDiagRow(label: "Cap index rows", value: "\(vm.capIndexAggregator.count)")
                    ScreenDiagRow(label: "Backend endpoint", value: "/api/v1/screener?preset=<id>", color: Theme.securityGold)
                }
                .padding(Theme.Spacing.standard)
                .background(Theme.canvasDeep)
                .cornerRadius(Theme.CornerRadius.medium)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .stroke(Theme.borderSage, lineWidth: 0.5)
                )

                Text("No earnings feed data available. Screeners require backend data for Piotroski F-Scores, RSI, Golden Cross signals, and PE ratios. Analyze stocks via the Analysis tab or use Search → Screener for live backend presets.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 20)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.large)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .stroke(Theme.borderSage, lineWidth: 0.5)
        )
    }

    // MARK: - No Results for Selected Preset

    private var noResultsForPreset: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionDivider()
                .padding(.horizontal, 16)

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.subheadline)
                        .foregroundStyle(Theme.holdAmber)
                    Text("LOCAL FILTER UNAVAILABLE")
                        .font(.caption.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                }

                if let presetId = selectedPreset,
                   let preset = screenerPresets.first(where: { $0.id == presetId }) {

                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        ScreenDiagRow(label: "Selected preset", value: preset.title)
                        ScreenDiagRow(label: "Preset ID", value: preset.id)
                        ScreenDiagRow(label: "Has local filter", value: preset.filter != nil ? "YES" : "NO — requires backend")
                        ScreenDiagRow(label: "Missing data",
                            value: missingDataForPreset(preset.id),
                            color: Theme.bearRed)
                        ScreenDiagRow(label: "Backend call",
                            value: "/api/v1/screener?preset=\(preset.id)",
                            color: Theme.securityGold)
                        ScreenDiagRow(label: "Feed available", value: "\(vm.feed.count) items")
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.medium)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                    )

                    Text("This preset needs server-side computation. Use Search tab → Screener for live backend results, or run analyses on individual stocks to populate local feed data.")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.borderSage, lineWidth: 0.5)
            )
        }
    }

    private func missingDataForPreset(_ id: String) -> String {
        switch id {
        case "piotroski":    return "Piotroski F-Score (needs balance sheet + cash flow + income)"
        case "oversold":     return "RSI-14 calculation (needs 14 days OHLCV history)"
        case "golden_cross": return "50-day + 200-day MA (needs 200 days OHLCV history)"
        case "value_picks":  return "PE ratio + sector average (needs yfinance fundamentals)"
        default:             return "Unknown"
        }
    }

    // MARK: - Diagnostic Row

    private struct ScreenDiagRow: View {
        let label: String
        let value: String
        var color: Color = Theme.inkSecondary

        var body: some View {
            let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
            HStack(alignment: .top, spacing: Theme.Spacing.tight) {
                Text(label)
                    .font(.caption2.weight(.semibold).monospaced())
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(width: colW * 0.28, alignment: .leading)
                Text(value)
                    .font(.caption2.monospaced())
                    .foregroundStyle(color)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: - Preset Card

    private func screenerPresetCard(_ preset: ScreenerPreset) -> some View {
        let isSelected = selectedPreset == preset.id
        let isBookmarked = vm.bookmarkedScreeners.contains(preset.id)

        // Compute match count: use local filter if available, else indicate backend
        let matchCount: String = {
            if let filter = preset.filter {
                let matches = filter(vm.feed)
                return "\(matches.count)"
            }
            if preset.backendPreset != nil {
                return "LIVE"
            }
            return "—"
        }()

        return Button(action: {
            HapticManager.selection()
            if isSelected {
                selectedPreset = nil
                filteredResults = []
                screenerBackendResults = []
                return
            }
            selectedPreset = preset.id
            filteredResults = []
            screenerBackendResults = []
            isLoading = true

            if let filter = preset.filter {
                filteredResults = filter(vm.feed)
                isLoading = false
            } else if let backendKey = preset.backendPreset {
                Task {
                    let results = (try? await NetworkManager.shared.fetchScreener(preset: backendKey)) ?? []
                    screenerBackendResults = results
                    isLoading = false
                }
            } else {
                isLoading = false
            }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                // Icon + Bookmark row
                HStack {
                        ZStack {
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                .fill(Theme.securityGold.opacity(0.12))
                                .frame(width: Theme.Spacing.xLarge, height: Theme.Spacing.xLarge)
                            Image(systemName: preset.icon)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(isSelected ? Theme.securityGold : Theme.inkSecondary)
                        }

                        Spacer()

                        // Bookmark toggle
                        Button(action: {
                            vm.toggleScreenerBookmark(preset.id)
                            HapticManager.impact(.light)
                        }) {
                            Image(systemName: isBookmarked ? "star.fill" : "star")
                                .font(.footnote)
                                .foregroundStyle(isBookmarked ? Theme.securityGold : Theme.inkTertiary.opacity(0.5))
                        }

                        // Match count badge
                        Text(matchCount)
                            .font(.caption.weight(.bold).monospaced())
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(Theme.securityGold.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.medium)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                    .stroke(Theme.securityGold.opacity(0.2), lineWidth: 0.5)
                            )
                    }

                    // Title
                    Text(preset.title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isSelected ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.85))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    // Description
                    Text(preset.description)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer(minLength: 0)
            }
            .padding(Theme.Spacing.standard)
            .frame(minHeight: UIScreen.main.bounds.width * 0.9, alignment: .topLeading)
            .background(isSelected ? Theme.securityGold.opacity(0.06) : Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.large)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(
                        isSelected ? Theme.securityGold.opacity(0.4) : Theme.borderSage,
                        lineWidth: isSelected ? 1.0 : 0.5
                    )
            )
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Results Section

    private func screenerResultsSection(presetId: String) -> some View {
        guard let preset = screenerPresets.first(where: { $0.id == presetId }) else {
            return AnyView(EmptyView())
        }

        return AnyView(
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                SectionDivider()

                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SCREENER RESULTS")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text(preset.title)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    Text("\(filteredResults.count) matches")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.tight)
                }

                let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2
                VStack(spacing: Theme.Spacing.none) {
                        // Table header
                        HStack(spacing: Theme.Spacing.none) {
                            Text("TICKER").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                            Text("LTP").tableHeaderStyle().frame(minWidth: colW * 0.18, alignment: .trailing)
                            Text("CHG%").tableHeaderStyle().frame(minWidth: colW * 0.14, alignment: .trailing)
                            Text("PROFIT GR%").tableHeaderStyle().frame(minWidth: colW * 0.18, alignment: .trailing)
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.small)

                        ForEach(Array(filteredResults.prefix(15).enumerated()), id: \.offset) { idx, r in
                            HStack(spacing: Theme.Spacing.none) {
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(r.ticker)
                                        .font(.footnote.weight(.bold).monospaced())
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(r.companyName)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.inkTertiary)
                                        .lineLimit(1)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)

                                Text(IndianFormatter.price(r.ltp))
                                    .font(.caption.monospaced())
                                    .foregroundStyle(Theme.inkPrimary)
                                    .frame(minWidth: colW * 0.18, alignment: .trailing)

                                Text(IndianFormatter.delta(r.changePercent))
                                    .font(.caption.weight(.bold).monospaced())
                                    .foregroundStyle(r.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    .frame(minWidth: colW * 0.14, alignment: .trailing)

                                Text(IndianFormatter.delta(r.netProfitGrowthPct))
                                    .font(.caption.weight(.bold).monospaced())
                                    .foregroundStyle(r.netProfitGrowthPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    .frame(minWidth: colW * 0.18, alignment: .trailing)
                            }
                            .padding(.horizontal, 10)
                            .padding(.vertical, 8)

                            if idx < min(filteredResults.count, 15) - 1 {
                                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                            }
                        }
            }
            .padding(.vertical, 4)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.borderSage, lineWidth: 0.5)
            )
        }
    )
    }

    // MARK: - Backend Results Section

    private func screenerBackendResultsSection(presetId: String) -> some View {
        guard let preset = screenerPresets.first(where: { $0.id == presetId }) else {
            return AnyView(EmptyView())
        }
        return AnyView(
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                SectionDivider()

                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SCREENER RESULTS")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text(preset.title)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    Text("\(screenerBackendResults.count) matches")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.tight)
                }

                ForEach(Array(screenerBackendResults.enumerated()), id: \.element.id) { idx, result in
                    NavigationLink(value: result.ticker) {
                        screenerBackendResultRow(result: result)
                    }
                    .ekPressHaptic()
                    .staggerAppear(delay: Double(idx) * 0.05)
                }
            }
        )
    }

    private func screenerBackendResultRow(result: ScreenerResult) -> some View {
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(Theme.securityGold.opacity(0.4))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: result.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(result.ticker.uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    if let company = result.companyName {
                        Text(company)
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(1)
                    }
                    if let reason = result.reason {
                        Text(reason)
                            .font(.caption2)
                            .foregroundStyle(Theme.inkTertiary)
                            .lineLimit(1)
                    }
                }
                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    if let conf = result.confidencePct {
                        Text("\(conf)%")
                            .font(Theme.serialNumberFont(size: 11))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.securityGold)
                    }
                    if let fs = result.fScore {
                        Text("F:\(fs)/9")
                            .font(Theme.serialNumberFont(size: 10))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.bullGreen)
                    }
                    if let pe = result.peRatio {
                        Text("PE:\(String(format: "%.1f", pe))")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    if let pg = result.profitGrowthPct {
                        Text("+\(String(format: "%.0f", pg))%")
                            .font(Theme.serialNumberFont(size: 10))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.bullGreen)
                    }
                    if let r = result.rsi {
                        Text("RSI:\(String(format: "%.0f", r))")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.bearRed)
                    }
                }
                Image(systemName: "arrow.right")
                    .foregroundStyle(Theme.inkSecondary.opacity(0.3))
                    .font(.footnote.weight(.bold))
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .glassCard()
        .banknoteCard()
    }
}

// MARK: - 4.1 / 4.2 / 4.3 Variance Tracker View

struct VarianceTrackerView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @State private var estimates: [EarningsEstimate] = []
    @State private var expectationFilter: String = "all"  // all | high | low
    @State private var isLoading = false

    var filteredEstimates: [EarningsEstimate] {
        switch expectationFilter {
        case "high":
            return estimates.filter { ($0.revenueSurprisePct ?? 0) > 5 }
        case "low":
            return estimates.filter { ($0.revenueSurprisePct ?? 0) < -5 }
        default:
            return estimates
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            // 4.3 Pre-Result Sentiment Segmentation Tabs
            expectationFilterBar
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.standard) {
                    if isLoading && estimates.isEmpty {
                        ForEach(0..<4, id: \.self) { _ in variancePlaceholder }
                    } else if filteredEstimates.isEmpty {
                        Text("No variance data available.")
                            .font(.footnote)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(Theme.Spacing.xLarge)
                    } else {
                        ForEach(filteredEstimates) { est in
                            VarianceCard(estimate: est)
                        }
                    }
                }
                .padding(Theme.Spacing.card)
            }
        }
        .background(Theme.canvas)
        .onAppear { loadEstimates() }
    }

    private var expectationFilterBar: some View {
        HStack(spacing: Theme.Spacing.none) {
            ForEach([("all","All"), ("high","High Expectations"), ("low","Low Expectations")], id: \.0) { key, label in
                Button(action: { expectationFilter = key }) {
                    Text(label)
                        .font(.caption.weight(expectationFilter == key ? .bold : .regular))
                        .foregroundStyle(expectationFilter == key ? Theme.securityGold : Theme.inkTertiary)
                        .padding(.vertical, Theme.Spacing.medium)
                        .frame(maxWidth: .infinity)
                        .background(expectationFilter == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                }
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    private var variancePlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.28, height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 60)
        }
        .padding(Theme.Spacing.standard).banknoteCard().shimmerPlaceholder(isLoading: true)
    }

    private func loadEstimates() {
        isLoading = true
        Task {
            // Load estimates for top 20 from current feed
            var loaded: [EarningsEstimate] = []
            for ticker in vm.filteredFeed.prefix(20).map({ $0.ticker }) {
                if let est = try? await NetworkManager.shared.fetchEarningsEstimates(ticker: ticker) {
                    loaded.append(est)
                }
            }
            estimates = loaded
            isLoading = false
        }
    }
}

// MARK: - 4.1 / 4.2 Variance Card

struct VarianceCard: View {
    let estimate: EarningsEstimate

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(estimate.ticker)
                        .font(.subheadline.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(estimate.companyName)
                        .font(.caption)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                surpriseChip(pct: estimate.revenueSurprisePct ?? estimate.netProfitSurprisePct)
            }

            // 4.1 Three-column matrix: Revenue, Net Profit, EPS
            HStack(spacing: Theme.Spacing.none) {
                varianceColumn(label: "REVENUE",
                               estimate: estimate.revenueEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.revenueActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.revenueSurprisePct)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 50).padding(.horizontal, Theme.Spacing.tight)
                varianceColumn(label: "NET PROFIT",
                               estimate: estimate.netProfitEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.netProfitActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.netProfitSurprisePct)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 50).padding(.horizontal, Theme.Spacing.tight)
                varianceColumn(label: "EPS",
                               estimate: estimate.epsEstimate.map { String(format: "₹%.2f", $0) },
                               actual: estimate.epsActual.map { String(format: "₹%.2f", $0) },
                               variancePct: nil)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }

    private func varianceColumn(label: String, estimate: String?, actual: String?, variancePct: Double?) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1)
                .foregroundStyle(Theme.inkTertiary)
            if let est = estimate {
                HStack(spacing: Theme.Spacing.small) {
                    Text("Est:").font(.caption2).foregroundStyle(Theme.inkTertiary)
                    Text(est).font(.caption.weight(.medium)).foregroundStyle(Theme.inkSecondary)
                }
            }
            if let act = actual {
                HStack(spacing: Theme.Spacing.small) {
                    Text("Act:").font(.caption2).foregroundStyle(Theme.inkTertiary)
                    Text(act).font(.caption.weight(.semibold)).foregroundStyle(Theme.inkPrimary)
                }
            }
            if let pct = variancePct {
                Text(IndianFormatter.delta(pct))
                    .font(.caption.weight(.bold))
                    .foregroundStyle(pct >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // 4.2 Semantic Color-Coded State Chips
    private func surpriseChip(pct: Double?) -> some View {
        guard let pct = pct else {
            return AnyView(EmptyView())
        }
        let beats = pct >= 0
        let label = beats ? "BEATS EXPECTATIONS" : "MISSED EXPECTATIONS"
        let color: Color = beats ? Theme.bullGreen : Theme.bearRed
        return AnyView(
            Text(label)
                .font(.caption2.weight(.bold).monospaced())
                .tracking(1)
                .foregroundStyle(color)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(color.opacity(0.10))
                .cornerRadius(Theme.CornerRadius.small)
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(color.opacity(0.3), lineWidth: 0.5))
        )
    }
}

// MARK: - 5. Post-Result Price Action Monitor

struct PostResultMonitorView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("POST-RESULT PRICE SHOCKER MATRIX")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("Equities experiencing peak volatility after earnings")
                            .font(.caption)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    // 5-second refresh indicator
                    HStack(spacing: Theme.Spacing.small) {
                        Circle()
                            .fill(Theme.bullGreen)
                            .frame(width: 6, height: 6)
                        Text("5s refresh")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)

                // Table header
                let headerW = UIScreen.main.bounds.width
                HStack(spacing: Theme.Spacing.none) {
                    Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                    Text("RESULT DATE").tableHeaderStyle().frame(minWidth: headerW * 0.20, alignment: .trailing)
                    Text("LTP").tableHeaderStyle().frame(minWidth: headerW * 0.20, alignment: .trailing)
                    Text("CHG %").tableHeaderStyle().frame(minWidth: headerW * 0.16, alignment: .trailing)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Theme.canvasDeep)

                if vm.isLoading && vm.postResultMovers.isEmpty {
                    ForEach(0..<5, id: \.self) { _ in
                        moverRowPlaceholder
                    }
                } else if vm.postResultMovers.isEmpty {
                    Text("No significant post-result movers currently.")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(Theme.Spacing.xLarge)
                        .frame(maxWidth: .infinity)
                } else {
                    ForEach(vm.postResultMovers) { mover in
                        postResultRow(mover)
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5).padding(.horizontal, 16)
                    }
                }
            }
            .padding(.bottom, 20)
        }
        .background(Theme.canvas)
        // 5-second throttle loop during market hours
        .onAppear { startVolatilityThrottle() }
        .onDisappear { stopVolatilityThrottle() }
    }

    @State private var throttleTask: Task<Void, Never>? = nil

    private func startVolatilityThrottle() {
        throttleTask?.cancel()
        throttleTask = Task {
            while !Task.isCancelled {
                let hour = Calendar.current.component(.hour, from: Date())
                // Active market hours: 9:15 AM – 3:30 PM IST
                if hour >= 9 && hour < 16 {
                    let movers = (try? await NetworkManager.shared.fetchPostResultMovers()) ?? []
                    if !Task.isCancelled { vm.postResultMovers = movers }
                }
                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
            }
        }
    }

    private func stopVolatilityThrottle() {
        throttleTask?.cancel()
        throttleTask = nil
    }

    private func postResultRow(_ m: PostResultMover) -> some View {
        let isPos = m.changePercent >= 0
        let rowW = UIScreen.main.bounds.width
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(m.ticker)
                    .font(.footnote.weight(.bold).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(m.companyName)
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(m.resultDate)
                .font(.caption.monospaced())
                .foregroundStyle(Theme.inkTertiary)
                .frame(minWidth: rowW * 0.20, alignment: .trailing)

            Text(IndianFormatter.price(m.ltp))
                .font(.footnote.weight(.semibold).monospaced())
                .foregroundStyle(Theme.inkPrimary)
                .frame(minWidth: rowW * 0.20, alignment: .trailing)

            HStack(spacing: Theme.Spacing.small) {
                // Directional Trend Indicator
                Image(systemName: isPos ? "arrow.up" : "arrow.down")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
                Text(IndianFormatter.delta(m.changePercent))
                    .font(.caption.weight(.bold).monospaced())
                    .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(minWidth: rowW * 0.16, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, Theme.Spacing.medium)
    }

    private var moverRowPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.31, height: 10)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.17, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.15, height: 12).padding(.leading, 8)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.15, height: 12).padding(.leading, 8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - Helper: Table Header Text Style

private extension Text {
    func tableHeaderStyle() -> some View {
        self
            .font(.caption2.weight(.bold).monospaced())
            .tracking(1.2)
            .foregroundStyle(Theme.inkTertiary)
    }
}

// MARK: - SwiftUI Previews (Section 15)

#Preview("Earnings Dashboard") {
    EarningsDashboardView()
        .environmentObject(AuthManager())
}

#Preview("Variance Card") {
    VarianceCard(estimate: EarningsEstimate(
        ticker: "RELIANCE",
        companyName: "Reliance Industries Ltd",
        revenueEstimate: 250000,
        revenueActual: 265000,
        netProfitEstimate: 18000,
        netProfitActual: 19500,
        epsEstimate: 28.5,
        epsActual: 30.2
    ))
    .padding()
    .background(Theme.canvas)
}

#Preview("Post Result Row") {
    PostResultMonitorView(vm: EarningsDashboardViewModel())
        .environmentObject(AuthManager())
}
