import SwiftUI
import Combine

// MARK: - Earnings Dashboard ViewModel

@MainActor
class EarningsDashboardViewModel: ObservableObject {
    @Published var feed: [EarningsResult] = []
    @Published var calendarDayResults: [EarningsCalendarItem] = []
    @Published var calendarSparklines: [String: [Double]] = [:]  // ticker → sparkline
    @Published var postResultMovers: [PostResultMover] = []
    @Published var estimates: [String: EarningsEstimate] = [:]
    @Published var selectedMarketCap: String = "all"
    @Published var selectedSort: String = "latest"
    @Published var selectedCalendarDate: Date = Date()
    @Published var bookmarkedScreeners: Set<String> = []
    @Published var isLoading = false

    /// Backend pre-computed aggregates from /api/v1/market/dashboard-pulse
    @Published var yoyMarketHealth: YoYMarketHealth? = nil
    @Published var capIndexAggregator: [CapIndexGridEntry] = []

    /// Per-section error diagnostics — shown inline when a section fails
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
        feed.isEmpty && postResultMovers.isEmpty
            && (feedError != nil || moversError != nil)
    }

    private var refreshTask: Task<Void, Never>?

    func load() {
        refreshTask?.cancel()
        refreshTask = Task {
            isLoading = true
            feedError = nil; moversError = nil; dashboardError = nil

            // Pre-computed aggregates from dashboard-pulse (yoy_health + cap_grid)
            let dash = await NetworkManager.shared.fetchExtendedMarketDashboard()
            self.yoyMarketHealth = dash?.yoyMarketHealth
            self.capIndexAggregator = dash?.capIndexAggregator ?? []

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
                        self.feedDiagnostic = "No earnings results yet."
                    }
                    self.feedError = nil  // not a fetch error — just no data
                }
            } else {
                self.feedError = "Couldn't load earnings right now. Please try again shortly."
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
        let dateStr = WireDate.dayKey(date)
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

    /// Market-cap chips filter client-side; the feed already carries `marketCap`, so no refetch.
    var capFilteredFeed: [EarningsResult] {
        Self.filter(filteredFeed, marketCap: selectedMarketCap)
    }

    static func filter(_ results: [EarningsResult], marketCap: String) -> [EarningsResult] {
        marketCap == "all" ? results : results.filter { $0.marketCap == marketCap }
    }
}
