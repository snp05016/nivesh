import Foundation

// Market screens that used to build requests inline (ARCH-15). All go through
// `_fetchDecode`, so they carry the Bearer token and throw typed errors.
extension NetworkManager {

    func fetchTopMovers() async throws -> TopMoversResponse {
        try await _fetchDecode(TopMoversResponse.self, endpoint: "/api/v1/market/top-movers", timeout: 30)
    }

    /// Same endpoint as `fetchExtendedMarketDashboard`, decoded as the shape TechnicalMomentumView renders.
    func fetchDashboardPulse() async throws -> MarketDashboardResponse {
        try await _fetchDecode(MarketDashboardResponse.self, endpoint: "/api/v1/market/dashboard-pulse", timeout: 20)
    }

    func fetchMarketAnomalies(limit: Int = 20) async throws -> [MarketAnomaly] {
        try await _fetchDecode([MarketAnomaly].self, endpoint: "/api/v1/market/anomalies?limit=\(limit)", timeout: 60)
    }

    func fetchEarningsSurprises() async throws -> [EarningsSurprise] {
        try await _fetchDecode([EarningsSurprise].self,
                               endpoint: "/api/v1/earnings/surprises?period=current_quarter", timeout: 60)
    }

    /// `date` is yyyy-MM-dd.
    func fetchEarningsSurpriseCalendar(date: String) async throws -> EarningsCalendarResponse {
        try await _fetchDecode(EarningsCalendarResponse.self,
                               endpoint: "/api/v1/earnings/calendar?date=\(date.urlQueryValue)", timeout: 60)
    }
}
