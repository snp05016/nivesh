import SwiftUI
import Combine
import UserNotifications

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
            do {
                let dash = try await NetworkManager.shared.fetchExtendedMarketDashboard()
                self.yoyMarketHealth = dash?.yoyMarketHealth
                self.capIndexAggregator = dash?.capIndexAggregator ?? []
            } catch {
                self.dashboardError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription
            }

            // Progress
            do { self.progress = try await NetworkManager.shared.fetchEarningsProgress() }
            catch { self.progressError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription }

            // Feed — use ranked endpoint for diagnostic info
            if let rankedResp = await NetworkManager.shared.fetchRankedEarningsFeed(sort: selectedSort) {
                self.feed = rankedResp.results
                self.feedDataSource = rankedResp.dataSource
                self.feedDiagnostic = rankedResp.diagnostic
                if let err = rankedResp.error {
                    self.feedError = err
                }
                if rankedResp.dataSource == "empty" || rankedResp.results.isEmpty {
                    self.feedError = nil  // not a fetch error — just no data
                }
            } else {
                self.feedError = "Network or decode failure — check server connection"
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
        do {
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
        } catch {
            self.calendarError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription
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

            VStack(spacing: 0) {
                headerBar
                tabBar
                tabContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task { vm.load() }
        .onChange(of: vm.selectedMarketCap) { _ in vm.load() }
        .onChange(of: vm.selectedSort) { _, _ in vm.load() }
    }

    // MARK: Header

    private var headerBar: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("EARNINGS DASHBOARD")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.securityGold)
                if let p = vm.progress {
                    Text("\(p.reported)/\(p.total) results declared")
                        .font(.system(size: 12, weight: .regular))
                        .foregroundColor(Theme.inkSecondary)
                } else if let err = vm.progressError {
                    Text("⚠ \(err.prefix(60))")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundColor(Theme.bearRed)
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
            .frame(width: 100)
            .onChange(of: comparisonMode) { _, val in vm.comparisonMode = val }
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .background(Theme.canvasDeep)
    }

    // MARK: Tab Bar

    private var tabBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 4) {
                ForEach(Array(tabs.enumerated()), id: \.offset) { idx, name in
                    Button(action: { selectedTab = idx }) {
                        Text(name)
                            .font(.system(size: 11, weight: selectedTab == idx ? .bold : .regular))
                            .foregroundColor(selectedTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(
                                selectedTab == idx
                                    ? Theme.securityGold.opacity(0.10)
                                    : Color.clear
                            )
                            .cornerRadius(6)
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
        .background(Theme.canvasDeep)
        .overlay(Divider(), alignment: .bottom)
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
            VStack(spacing: 16) {
                // Full-page error canvas if everything failed
                if vm.isTotalFailure {
                    BanknoteErrorCanvas(
                        title: "Earnings Data Unavailable",
                        detail: [
                            vm.progressError.map { "Progress: \($0)" },
                            vm.feedError.map { "Feed: \($0)" },
                            vm.moversError.map { "Movers: \($0)" },
                        ].compactMap { $0 }.joined(separator: "\n\n"),
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
            .padding(16)
        }
        .background(Theme.canvas)
    }

    private func progressCard(_ p: EarningsProgressResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("LIVE REPORTING SYNC")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)

            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("\(p.reported)")
                    .font(Theme.engravedSerif(size: 36, weight: .bold))
                    .foregroundColor(Theme.inkPrimary)
                Text("/\(p.total)")
                    .font(Theme.engravedSerif(size: 20))
                    .foregroundColor(Theme.inkTertiary)
                Spacer()
                let pct = p.total > 0 ? Double(p.reported) / Double(p.total) : 0
                Text("\(Int(pct * 100))% filed")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(Theme.bullGreen)
            }

            // Progress bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.inkTertiary.opacity(0.15))
                    let pct = p.total > 0 ? CGFloat(p.reported) / CGFloat(p.total) : 0
                    RoundedRectangle(cornerRadius: 3)
                        .fill(LinearGradient(
                            colors: [Theme.bullGreen, Theme.securityGold],
                            startPoint: .leading, endPoint: .trailing))
                        .frame(width: geo.size.width * pct)
                }
            }
            .frame(height: 6)

            Text("companies have declared results against total statutory listed exchange obligations")
                .font(.system(size: 11))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(16)
        .banknoteCard()
    }

    private var progressCardPlaceholder: some View {
        VStack(alignment: .leading, spacing: 10) {
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 14).frame(width: 140)
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 36).frame(width: 180)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.12)).frame(height: 6)
        }
        .padding(16)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var aggregateCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("YoY AGGREGATE MARKET HEALTH")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)

            // Prefer backend pre-computed data, fall back to local feed aggregation
            let revGrowth: Double = vm.yoyMarketHealth?.revenueYoYPct ?? vm.aggregateRevGrowth
            let profitGrowth: Double = vm.yoyMarketHealth?.netProfitYoYPct ?? vm.aggregateProfitGrowth
            let sourceLabel: String = vm.yoyMarketHealth != nil ? "NSE AGGREGATE" : "FEED ESTIMATE"

            HStack(spacing: 0) {
                aggregateMetric(
                    label: "AVG REVENUE GROWTH",
                    value: revGrowth,
                    isLoading: vm.isLoading && vm.yoyMarketHealth == nil && vm.feed.isEmpty
                )
                Divider().frame(height: 40).padding(.horizontal, 16)
                aggregateMetric(
                    label: "AVG NET PROFIT GROWTH",
                    value: profitGrowth,
                    isLoading: vm.isLoading && vm.yoyMarketHealth == nil && vm.feed.isEmpty
                )
            }

            // Source label
            Text(sourceLabel)
                .font(.system(size: 7, weight: .medium, design: .monospaced))
                .foregroundColor(Theme.inkTertiary.opacity(0.5))
        }
        .padding(16)
        .banknoteCard()
    }

    private func aggregateMetric(label: String, value: Double, isLoading: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            if isLoading {
                RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.12)).frame(width: 60, height: 22)
            } else {
                Text(IndianFormatter.delta(value))
                    .font(.system(size: 20, weight: .bold, design: .monospaced))
                    .foregroundColor(value >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // 1.3 Market Cap Index Aggregator — prefers backend grid, falls back to earnings table
    private var marketCapIndexCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("MARKET CAP INDEX AGGREGATOR")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)

            if !vm.capIndexAggregator.isEmpty {
                // Backend pre-computed grid
                capGridTable
            } else if let dashErr = vm.dashboardError, vm.feed.isEmpty {
                // Backend failed + no feed fallback
                MarketSectionErrorRow(sectionLabel: "CAP INDEX GRID", errorMessage: dashErr)
            } else {
                // Fallback: per-company earnings table
                // 1.3 Multi-Tier Index Weight Tabs
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(["all", "nifty50", "large_cap", "mid_cap", "small_cap"], id: \.self) { cap in
                            Button(action: { vm.selectedMarketCap = cap }) {
                                Text(capLabel(cap))
                                    .font(.system(size: 10, weight: vm.selectedMarketCap == cap ? .bold : .regular))
                                    .foregroundColor(vm.selectedMarketCap == cap ? Theme.securityGold : Theme.inkSecondary)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 5)
                                    .background(vm.selectedMarketCap == cap ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                                    .cornerRadius(5)
                                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(Theme.borderSage, lineWidth: 0.5))
                            }
                        }
                    }
                }
                earningsTable
            }
        }
        .padding(16)
        .banknoteCard()
    }

    /// Backend pre-computed cap grid table (from /api/v1/market/dashboard-pulse)
    private var capGridTable: some View {
        VStack(spacing: 0) {
            // Header
            HStack(spacing: 0) {
                Text("BRACKET").tableHeaderStyle().frame(width: 80, alignment: .leading)
                Text("MCAP").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("REVENUE").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PROFIT").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PE").tableHeaderStyle().frame(width: 36, alignment: .trailing)
            }
            .padding(.horizontal, 8).padding(.vertical, 6)
            .background(Theme.canvasDeep)

            Divider().opacity(0.5)

            ForEach(vm.capIndexAggregator) { row in
                HStack(spacing: 0) {
                    Text(row.capBracket.uppercased())
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundColor(row.capBracket == "All" ? Theme.securityGold : Theme.inkPrimary)
                        .frame(width: 80, alignment: .leading)
                    Text(row.avgMarketCapCr)
                        .font(.system(size: 9, design: .monospaced)).foregroundColor(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgRevenueCr)
                        .font(.system(size: 9, design: .monospaced)).foregroundColor(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgNetProfitCr)
                        .font(.system(size: 9, design: .monospaced)).foregroundColor(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgPeRatio.map { String(format: "%.1f", $0) } ?? "—")
                        .font(.system(size: 9, design: .monospaced)).foregroundColor(Theme.inkTertiary)
                        .frame(width: 36, alignment: .trailing)
                }
                .padding(.horizontal, 8).padding(.vertical, 7)
                Divider().opacity(0.25)
            }
        }
        .cornerRadius(6)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderSage, lineWidth: 0.5))
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
        VStack(spacing: 0) {
            // Header row
            HStack(spacing: 0) {
                Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                Text("REVENUE").tableHeaderStyle().frame(width: 90, alignment: .trailing)
                Text("GROSS PROFIT").tableHeaderStyle().frame(width: 90, alignment: .trailing)
                Text("NET PROFIT").tableHeaderStyle().frame(width: 90, alignment: .trailing)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(Theme.canvasDeep)

            Divider().opacity(0.5)

            if vm.feed.isEmpty && vm.isLoading {
                ForEach(0..<4, id: \.self) { _ in
                    tableRowPlaceholder
                    Divider().opacity(0.3)
                }
            } else {
                ForEach(vm.filteredFeed.prefix(10)) { result in
                    earningsTableRow(result)
                    if result.id != vm.filteredFeed.prefix(10).last?.id {
                        Divider().opacity(0.25)
                    }
                }
            }
        }
        .cornerRadius(6)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func earningsTableRow(_ r: EarningsResult) -> some View {
        let mode = vm.comparisonMode
        let revGrowth = r.revenueGrowthPct
        let profitGrowth = r.netProfitGrowthPct
        return HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text(r.ticker)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(Theme.inkPrimary)
                Text(r.isConsolidated ? "Consolidated" : "Standalone")
                    .font(.system(size: 9))
                    .foregroundColor(Theme.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(IndianFormatter.formatLakhsCrores(r.revenue))
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
                .frame(width: 90, alignment: .trailing)

            Text(r.grossProfit != nil ? IndianFormatter.formatLakhsCrores(r.grossProfit!) : "—")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(Theme.inkSecondary)
                .frame(width: 90, alignment: .trailing)

            VStack(alignment: .trailing, spacing: 2) {
                Text(IndianFormatter.formatLakhsCrores(r.netProfit))
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(Theme.inkPrimary)
                Text(IndianFormatter.delta(profitGrowth))
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(profitGrowth >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(width: 90, alignment: .trailing)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 8)
    }

    private var tableRowPlaceholder: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 60, height: 12)
            Spacer()
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 70, height: 12)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 70, height: 12)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 70, height: 12)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 10)
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 1.2 Earnings Calendar View

// MARK: - Mini Sparkline (7-day price context)

struct MiniSparkline: View {
    let data: [Double]
    let color: Color

    var body: some View {
        GeometryReader { geo in
            let minY = data.min() ?? 0
            let maxY = data.max() ?? 1
            let range = max(maxY - minY, 0.01)
            let stepX = geo.size.width / CGFloat(max(data.count - 1, 1))

            Path { path in
                for (i, val) in data.enumerated() {
                    let x = CGFloat(i) * stepX
                    let y = geo.size.height * CGFloat(1 - (val - minY) / range)
                    if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                    else { path.addLine(to: CGPoint(x: x, y: y)) }
                }
            }
            .stroke(color.opacity(0.6), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
        }
    }
}

// MARK: - Calendar View

struct EarningsCalendarView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @EnvironmentObject var authManager: AuthManager
    @State private var alertSetFor: String? = nil

    private let calendar = Calendar.current

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
            VStack(spacing: 16) {
                // 1.2 Horizontal Calendar Day Scroller
                calendarScrollRow
                GuillocheDivider()
                // Results for selected date
                selectedDayResults
            }
            .padding(16)
        }
        .background(Theme.canvas)
    }

    private var calendarScrollRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(calendarDays, id: \.self) { date in
                    Button(action: { vm.selectCalendarDate(date) }) {
                        calendarDayCell(date)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 4)
        }
    }

    private func calendarDayCell(_ date: Date) -> some View {
        let sel = isSelected(date)
        let isToday = calendar.isDateInToday(date)
        let dayStr = apiDate(date)
        let dayResults = vm.calendarDayResults.filter { $0.resultDate == dayStr }
        let count = dayResults.count
        // Extract sparkline from any result that has it
        let sparkData = dayResults.first(where: { !$0.sparkline.isEmpty })?.sparkline ?? []

        return VStack(spacing: 4) {
            Text(monthLabel(date))
                .font(.system(size: 8, weight: .medium, design: .monospaced))
                .foregroundColor(sel ? Theme.securityGold : Theme.inkTertiary)
            Text(dayLabel(date))
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundColor(sel ? Theme.inkPrimary : Theme.inkSecondary)

            // Mini sparkline for dates with price data
            if !sparkData.isEmpty {
                MiniSparkline(data: sparkData, color: sel ? Theme.securityGold : Theme.inkTertiary)
                    .frame(width: 36, height: 16)
            } else if count > 0 {
                Text("\(count)")
                    .font(.system(size: 8, weight: .bold))
                    .foregroundColor(sel ? Theme.securityGold : Theme.inkTertiary)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(sel ? Theme.securityGold.opacity(0.15) : Theme.inkTertiary.opacity(0.08))
                    .cornerRadius(4)
            } else {
                Color.clear.frame(height: 16)
            }
        }
        .frame(width: 60)
        .padding(.vertical, 8)
        .background(sel ? Theme.securityGold.opacity(0.08) : Theme.canvasDeep)
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
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
        return VStack(alignment: .leading, spacing: 12) {

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    // 1.2 count badge in title
                    Text("\(humanDate) — \(count) Earnings")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.inkPrimary)
                    Text("Tap a company row to set an earnings alert")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.inkTertiary)
                }
                Spacer()
            }

            if vm.calendarDayResults.isEmpty {
                Text("No results scheduled for this date.")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 24)
            } else {
                ForEach(vm.calendarDayResults) { result in
                    calendarResultRow(result)
                }
            }
        }
        .padding(16)
        .banknoteCard()
    }

    private func calendarResultRow(_ r: EarningsCalendarItem) -> some View {
        let userId = authManager.currentUser?.userId ?? 0
        return HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(r.ticker)
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                    Text(r.isConsolidated ? "Consol" : "Standalone")
                        .font(.system(size: 9))
                        .foregroundColor(Theme.inkTertiary)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(Theme.inkTertiary.opacity(0.08))
                        .cornerRadius(3)
                    // 7-day price change badge
                    if let chg = r.priceChange7dPct {
                        Text(IndianFormatter.delta(chg))
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(chg >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                Text(r.companyName)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.inkSecondary)
                // Sparkline row
                if !r.sparkline.isEmpty {
                    MiniSparkline(data: r.sparkline, color: (r.priceChange7dPct ?? 0) >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: 20)
                        .padding(.top, 2)
                }
            }
            Spacer()
            // 1.4 Embedded Alert Trigger
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
                HStack(spacing: 4) {
                    Image(systemName: alertSetFor == r.ticker ? "bell.fill" : "bell")
                        .font(.system(size: 11))
                    Text("Alert")
                        .font(.system(size: 10, weight: .medium))
                }
                .foregroundColor(alertSetFor == r.ticker ? Theme.securityGold : Theme.inkSecondary)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(alertSetFor == r.ticker ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                .cornerRadius(6)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderSage, lineWidth: 0.5))
            }
        }
        .padding(.vertical, 8)
        .overlay(Divider(), alignment: .bottom)
    }
}

// MARK: - 2.1 / 2.2 Earnings Feed View

struct EarningsFeedView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        VStack(spacing: 0) {
            // 2.2 Tabbed Performance Sorting Grid
            sortTabBar
            ScrollView {
                LazyVStack(spacing: 10) {
                    if vm.isLoading && vm.feed.isEmpty {
                        ForEach(0..<6, id: \.self) { _ in feedCardPlaceholder }
                    } else if vm.filteredFeed.isEmpty {
                        // Show exact reason — from backend diagnostic or local error
                        VStack(spacing: 12) {
                            if let err = vm.feedError {
                                // Fetch error — network/decode failure
                                BanknoteErrorCanvas(
                                    title: "Feed Fetch Failed",
                                    detail: err,
                                    retryAction: { vm.load() }
                                )
                            } else if let diag = vm.feedDiagnostic {
                                // Backend-provided diagnostic
                                BanknoteErrorCanvas(
                                    title: "No Earnings Data",
                                    detail: diag,
                                    retryAction: { vm.load() }
                                )
                            } else if let src = vm.feedDataSource {
                                BanknoteErrorCanvas(
                                    title: "No Earnings Data",
                                    detail: "Data source: \(src). No results available.\n\n"
                                        + "The backend has no earnings records. "
                                        + "Run an AI analysis on a stock to populate data.",
                                    retryAction: { vm.load() }
                                )
                            } else {
                                BanknoteErrorCanvas(
                                    title: "No Earnings Data",
                                    detail: "Backend returned empty results.\n\n"
                                        + "Likely cause: No stock analyses have been run yet. "
                                        + "The earnings feed reads from the Analysis History database. "
                                        + "Run an AI analysis on a stock first to populate earnings data.\n\n"
                                        + "If analyses exist and this persists, check the backend server logs.",
                                    retryAction: { vm.load() }
                                )
                            }
                        }
                    } else {
                        ForEach(vm.filteredFeed) { result in
                            EarningsResultCard(result: result, comparisonMode: vm.comparisonMode)
                        }
                    }
                }
                .padding(16)
            }
        }
        .background(Theme.canvas)
    }

    private var sortTabBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ForEach([("latest", "Latest Results"), ("best", "Best Performer"), ("worst", "Worst Performer")], id: \.0) { key, label in
                    Button(action: { vm.selectedSort = key }) {
                        Text(label)
                            .font(.system(size: 11, weight: vm.selectedSort == key ? .bold : .regular))
                            .foregroundColor(vm.selectedSort == key ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.vertical, 10)
                            .frame(maxWidth: .infinity)
                            .background(vm.selectedSort == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            // Data source indicator
            if let src = vm.feedDataSource {
                HStack(spacing: 4) {
                    Circle()
                        .fill(src == "database" ? Theme.bullGreen : src == "yfinance_fallback" ? Theme.holdAmber : Theme.bearRed)
                        .frame(width: 5, height: 5)
                    Text("Source: \(src.replacingOccurrences(of: "_", with: " ").uppercased())")
                        .font(.system(size: 8, weight: .medium, design: .monospaced))
                        .foregroundColor(Theme.inkTertiary.opacity(0.6))
                }
                .padding(.vertical, 3)
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Divider(), alignment: .bottom)
    }

    private var feedCardPlaceholder: some View {
        VStack(alignment: .leading, spacing: 8) {
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 100, height: 13)
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 13)
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 160, height: 11)
        }
        .padding(14)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 2.1 / 2.4 Earnings Result Card

struct EarningsResultCard: View {
    let result: EarningsResult
    let comparisonMode: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header row
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(result.ticker)
                            .font(.system(size: 14, weight: .bold, design: .monospaced))
                            .foregroundColor(Theme.inkPrimary)
                        Text(result.isConsolidated ? "CONSOL" : "STANDALONE")
                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                            .tracking(1)
                            .foregroundColor(Theme.inkTertiary)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Theme.inkTertiary.opacity(0.08))
                            .cornerRadius(3)
                    }
                    Text(result.companyName)
                        .font(.system(size: 11))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 3) {
                    Text(IndianFormatter.price(result.ltp))
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                    Text(IndianFormatter.delta(result.changePercent))
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(result.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }

            // Sparkline price context
            if let spark = result.sparkline, !spark.isEmpty {
                HStack(spacing: 8) {
                    MiniSparkline(data: spark, color: result.netProfitGrowthPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: 22)
                    if let chg7d = result.priceChange7dPct {
                        Text("7d: \(IndianFormatter.delta(chg7d))")
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(chg7d >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                .padding(.vertical, 4)
            }

            GuillocheDivider()

            // 2.4 Historical period baseline rows
            HStack(spacing: 0) {
                metricColumn(
                    label: "NET SALES",
                    current: IndianFormatter.formatLakhsCrores(result.revenue),
                    growth: result.revenueGrowthPct
                )
                Divider().frame(height: 44).padding(.horizontal, 8)
                metricColumn(
                    label: "NET PROFIT",
                    current: IndianFormatter.formatLakhsCrores(result.netProfit),
                    growth: result.netProfitGrowthPct
                )
                Divider().frame(height: 44).padding(.horizontal, 8)
                metricColumn(
                    label: "MARGIN",
                    current: String(format: "%.1f%%", result.netProfitMarginPct),
                    growth: nil
                )
            }

            // 2.1 Absolute elapsed timestamp
            if let reportedDate = result.parsedReportedAt {
                Text(IndianFormatter.elapsed(from: reportedDate))
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(14)
        .banknoteCard()
    }

    private func metricColumn(label: String, current: String, growth: Double?) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .tracking(1)
                .foregroundColor(Theme.inkTertiary)
            Text(current)
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
            if let g = growth {
                Text(IndianFormatter.delta(g))
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(g >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - 3.1 / 3.2 / 3.3 Screener View

struct ScreenerView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @State private var results: [ScreenerResult] = []
    @State private var selectedPreset = "profit_growth_25"
    @State private var isLoading = false
    @State private var errorMsg: String? = nil

    let presets: [(key: String, label: String, icon: String)] = [
        ("profit_growth_25",  "Quarterly Profit > 25%",          "chart.line.uptrend.xyaxis"),
        ("sales_growth_25",   "Quarterly Sales > 25%",           "arrow.up.right"),
        ("increasing_margins","Increasing Net Profit Margins",   "chart.bar.fill"),
        ("falling_profits",   "Falling Quarterly Profits",       "arrow.down.right"),
        ("increasing_ii",     "Increasing Institutional Interest","building.columns"),
        ("combined_fii_dii",  "Combined FII+DII Flow Expansion", "arrow.triangle.2.circlepath"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("ALGORITHMIC SCREENERS")
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.inkSecondary)
                    .padding(.horizontal, 16)
                    .padding(.top, 16)

                // Screener Cards
                ForEach(presets, id: \.key) { preset in
                    screenerCard(preset: preset)
                }
                .padding(.horizontal, 16)

                // 3.2 Ownership Variance Grid (if institutional screener selected)
                if selectedPreset == "increasing_ii" || selectedPreset == "combined_fii_dii" {
                    ownershipGrid
                        .padding(.horizontal, 16)
                }

                // Results
                if !results.isEmpty {
                    resultsSection
                        .padding(.horizontal, 16)
                }
            }
            .padding(.bottom, 20)
        }
        .background(Theme.canvas)
    }

    private func screenerCard(preset: (key: String, label: String, icon: String)) -> some View {
        let isSelected = selectedPreset == preset.key
        let isBookmarked = vm.bookmarkedScreeners.contains(preset.key)
        return Button(action: {
            selectedPreset = preset.key
            loadScreener(preset: preset.key)
        }) {
            HStack(spacing: 12) {
                Image(systemName: preset.icon)
                    .font(.system(size: 14))
                    .foregroundColor(isSelected ? Theme.securityGold : Theme.inkSecondary)
                    .frame(width: 24)
                Text(preset.label)
                    .font(.system(size: 13, weight: isSelected ? .semibold : .regular))
                    .foregroundColor(isSelected ? Theme.inkPrimary : Theme.inkSecondary)
                Spacer()
                // 3.3 Star Glyph Persistent Toggle
                Button(action: { vm.toggleScreenerBookmark(preset.key); HapticManager.impact(.light) }) {
                    Image(systemName: isBookmarked ? "star.fill" : "star")
                        .font(.system(size: 13))
                        .foregroundColor(isBookmarked ? Theme.securityGold : Theme.inkTertiary)
                }
                if isSelected {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.inkTertiary)
                }
            }
            .padding(14)
            .background(isSelected ? Theme.securityGold.opacity(0.06) : Theme.canvasDeep)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Theme.securityGold.opacity(0.3) : Theme.borderSage, lineWidth: isSelected ? 1 : 0.5)
            )
        }
        .buttonStyle(EKPressStyle())
    }

    private var ownershipGrid: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("OWNERSHIP VARIANCE GRID")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(2)
                .foregroundColor(Theme.inkSecondary)

            HStack(spacing: 0) {
                Text("TICKER").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                Text("PREV QTR").tableHeaderStyle().frame(width: 70, alignment: .trailing)
                Text("CURR QTR").tableHeaderStyle().frame(width: 70, alignment: .trailing)
                Text("DELTA").tableHeaderStyle().frame(width: 60, alignment: .trailing)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Theme.canvasDeep)
            .cornerRadius(4)

            if results.isEmpty {
                Text("Select screener above to load ownership data")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.inkTertiary)
                    .padding(.vertical, 8)
            } else {
                ForEach(results.prefix(5)) { r in
                    HStack(spacing: 0) {
                        Text(r.ticker)
                            .font(.system(size: 12, weight: .semibold, design: .monospaced))
                            .foregroundColor(Theme.inkPrimary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text("—").font(.system(size: 11)).foregroundColor(Theme.inkTertiary).frame(width: 70, alignment: .trailing)
                        Text("—").font(.system(size: 11)).foregroundColor(Theme.inkTertiary).frame(width: 70, alignment: .trailing)
                        Text("—").font(.system(size: 11)).foregroundColor(Theme.inkTertiary).frame(width: 60, alignment: .trailing)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 8)
                    Divider().opacity(0.3)
                }
            }
        }
        .padding(14)
        .banknoteCard()
    }

    private var resultsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("SCREENER RESULTS")
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text("\(results.count) matches")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
            }

            ForEach(results) { r in
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(r.ticker)
                            .font(.system(size: 13, weight: .bold, design: .monospaced))
                            .foregroundColor(Theme.inkPrimary)
                        if let name = r.companyName {
                            Text(name)
                                .font(.system(size: 11))
                                .foregroundColor(Theme.inkSecondary)
                        }
                    }
                    Spacer()
                    if let reason = r.reason {
                        Text(reason)
                            .font(.system(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                            .multilineTextAlignment(.trailing)
                            .frame(maxWidth: 140, alignment: .trailing)
                    }
                }
                .padding(.vertical, 8)
                if r.id != results.last?.id { Divider().opacity(0.3) }
            }
        }
        .padding(14)
        .banknoteCard()
    }

    private func loadScreener(preset: String) {
        isLoading = true
        Task {
            results = (try? await NetworkManager.shared.fetchScreener(preset: preset)) ?? []
            isLoading = false
        }
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
        VStack(spacing: 0) {
            // 4.3 Pre-Result Sentiment Segmentation Tabs
            expectationFilterBar
            ScrollView {
                LazyVStack(spacing: 12) {
                    if isLoading && estimates.isEmpty {
                        ForEach(0..<4, id: \.self) { _ in variancePlaceholder }
                    } else if filteredEstimates.isEmpty {
                        Text("No variance data available.")
                            .font(.system(size: 13))
                            .foregroundColor(Theme.inkTertiary)
                            .padding(40)
                    } else {
                        ForEach(filteredEstimates) { est in
                            VarianceCard(estimate: est)
                        }
                    }
                }
                .padding(16)
            }
        }
        .background(Theme.canvas)
        .onAppear { loadEstimates() }
    }

    private var expectationFilterBar: some View {
        HStack(spacing: 0) {
            ForEach([("all","All"), ("high","High Expectations"), ("low","Low Expectations")], id: \.0) { key, label in
                Button(action: { expectationFilter = key }) {
                    Text(label)
                        .font(.system(size: 11, weight: expectationFilter == key ? .bold : .regular))
                        .foregroundColor(expectationFilter == key ? Theme.securityGold : Theme.inkTertiary)
                        .padding(.vertical, 10)
                        .frame(maxWidth: .infinity)
                        .background(expectationFilter == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                }
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Divider(), alignment: .bottom)
    }

    private var variancePlaceholder: some View {
        VStack(alignment: .leading, spacing: 8) {
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 100, height: 13)
            RoundedRectangle(cornerRadius: 4).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 60)
        }
        .padding(14).banknoteCard().shimmerPlaceholder(isLoading: true)
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
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(estimate.ticker)
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                    Text(estimate.companyName)
                        .font(.system(size: 11))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
                surpriseChip(pct: estimate.revenueSurprisePct ?? estimate.netProfitSurprisePct)
            }

            // 4.1 Three-column matrix: Revenue, Net Profit, EPS
            HStack(spacing: 0) {
                varianceColumn(label: "REVENUE",
                               estimate: estimate.revenueEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.revenueActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.revenueSurprisePct)
                Divider().frame(height: 50).padding(.horizontal, 6)
                varianceColumn(label: "NET PROFIT",
                               estimate: estimate.netProfitEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.netProfitActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.netProfitSurprisePct)
                Divider().frame(height: 50).padding(.horizontal, 6)
                varianceColumn(label: "EPS",
                               estimate: estimate.epsEstimate.map { String(format: "₹%.2f", $0) },
                               actual: estimate.epsActual.map { String(format: "₹%.2f", $0) },
                               variancePct: nil)
            }
        }
        .padding(14)
        .banknoteCard()
    }

    private func varianceColumn(label: String, estimate: String?, actual: String?, variancePct: Double?) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label)
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .tracking(1)
                .foregroundColor(Theme.inkTertiary)
            if let est = estimate {
                HStack(spacing: 4) {
                    Text("Est:").font(.system(size: 9)).foregroundColor(Theme.inkTertiary)
                    Text(est).font(.system(size: 10, weight: .medium)).foregroundColor(Theme.inkSecondary)
                }
            }
            if let act = actual {
                HStack(spacing: 4) {
                    Text("Act:").font(.system(size: 9)).foregroundColor(Theme.inkTertiary)
                    Text(act).font(.system(size: 10, weight: .semibold)).foregroundColor(Theme.inkPrimary)
                }
            }
            if let pct = variancePct {
                Text(IndianFormatter.delta(pct))
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(pct >= 0 ? Theme.bullGreen : Theme.bearRed)
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
                .font(.system(size: 8, weight: .bold, design: .monospaced))
                .tracking(1)
                .foregroundColor(color)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(color.opacity(0.10))
                .cornerRadius(4)
                .overlay(RoundedRectangle(cornerRadius: 4).stroke(color.opacity(0.3), lineWidth: 0.5))
        )
    }
}

// MARK: - 5. Post-Result Price Action Monitor

struct PostResultMonitorView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("POST-RESULT PRICE SHOCKER MATRIX")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .tracking(2)
                            .foregroundColor(Theme.inkSecondary)
                        Text("Equities experiencing peak volatility after earnings")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                    // 5-second refresh indicator
                    HStack(spacing: 4) {
                        Circle()
                            .fill(Theme.bullGreen)
                            .frame(width: 6, height: 6)
                        Text("5s refresh")
                            .font(.system(size: 9))
                            .foregroundColor(Theme.inkTertiary)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)

                // Table header
                HStack(spacing: 0) {
                    Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                    Text("RESULT DATE").tableHeaderStyle().frame(width: 80, alignment: .trailing)
                    Text("LTP").tableHeaderStyle().frame(width: 80, alignment: .trailing)
                    Text("CHG %").tableHeaderStyle().frame(width: 65, alignment: .trailing)
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
                        .font(.system(size: 12))
                        .foregroundColor(Theme.inkTertiary)
                        .padding(40)
                        .frame(maxWidth: .infinity)
                } else {
                    ForEach(vm.postResultMovers) { mover in
                        postResultRow(mover)
                        Divider().opacity(0.25).padding(.horizontal, 16)
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
        return HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text(m.ticker)
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundColor(Theme.inkPrimary)
                Text(m.companyName)
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(m.resultDate)
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(Theme.inkTertiary)
                .frame(width: 80, alignment: .trailing)

            Text(IndianFormatter.price(m.ltp))
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
                .frame(width: 80, alignment: .trailing)

            HStack(spacing: 4) {
                // Directional Trend Indicator
                Image(systemName: isPos ? "arrow.up" : "arrow.down")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(isPos ? Theme.bullGreen : Theme.bearRed)
                Text(IndianFormatter.delta(m.changePercent))
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .foregroundColor(isPos ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(width: 65, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private var moverRowPlaceholder: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 70, height: 12)
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 110, height: 10)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 60, height: 12)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 55, height: 12).padding(.leading, 8)
            RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 55, height: 12).padding(.leading, 8)
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
            .font(.system(size: 8, weight: .bold, design: .monospaced))
            .tracking(1.2)
            .foregroundColor(Theme.inkTertiary)
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
