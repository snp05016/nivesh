import Foundation

// Optional-returning fetches for sidebar/market screens. All go through
// `_fetchDecode` (Bearer, correlation id, status check, typed and tracked errors);
// these callers render a nil as their own empty/error state.
extension NetworkManager {

    func fetchMomentum() async -> MomentumResponse? {
        try? await _fetchDecode(MomentumResponse.self, endpoint: "/api/v1/market/momentum", timeout: 30)
    }

    func fetchMarketDashboard() async -> MarketDashboardResponse? {
        try? await _fetchDecode(MarketDashboardResponse.self, endpoint: "/api/v1/market/dashboard", timeout: 30)
    }

    /// Fetch extended market dashboard with all 5 core sections:
    /// pulse + momentum + live_reporting_sync + yoy_market_health + cap_index_aggregator
    func fetchExtendedMarketDashboard() async -> ExtendedMarketDashboardResponse? {
        try? await _fetchDecode(ExtendedMarketDashboardResponse.self, endpoint: "/api/v1/market/dashboard-pulse", timeout: 30)
    }

    // MARK: - Earnings Calendar & Feed (Extended)

    /// Fetch earnings calendar for a date with 7-day price sparklines per ticker.
    func fetchEarningsCalendar(date: String, ticker: String? = nil) async -> EarningsCalendarDayResponse? {
        var path = "/api/v1/earnings/calendar?date=\(date.urlQueryValue)"
        if let t = ticker { path += "&ticker=\(t.urlQueryValue)" }
        return try? await _fetchDecode(EarningsCalendarDayResponse.self, endpoint: path, timeout: 25)
    }

    /// Fetch ranked earnings feed with Latest/Best/Worst categorization.
    /// Timeout is 90s because the backend yfinance fallback queries 12 tickers
    /// sequentially (3 retries each) — this can take 30-60 seconds.
    func fetchRankedEarningsFeed(sort: String = "latest") async -> EarningsFeedResponse? {
        try? await _fetchDecode(EarningsFeedResponse.self, endpoint: "/api/v1/earnings/feed?sort=\(sort.urlQueryValue)", timeout: 90)
    }

    // MARK: - Ideas Workspace

    func fetchAdvisors() async -> AdvisorsResponse? {
        try? await _fetchDecode(AdvisorsResponse.self, endpoint: "/api/v1/ideas/advisors", timeout: 30)
    }

    func fetchIdeasFeed(limit: Int = 20, sentiment: String = "all") async -> IdeasFeedResponse? {
        try? await _fetchDecode(IdeasFeedResponse.self,
                                endpoint: "/api/v1/ideas/feed?limit=\(limit)&sentiment=\(sentiment.urlQueryValue)", timeout: 30)
    }
}
