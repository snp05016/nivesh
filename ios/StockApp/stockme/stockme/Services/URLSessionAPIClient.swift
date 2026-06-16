// URLSessionAPIClient.swift — Concrete API client using URLSession (Candidate 4)
import Foundation

final class URLSessionAPIClient: APIClient {
    var baseURL: String
    var authToken: String?
    var session: URLSession

    init(baseURL: String = "http://192.168.1.122:8000", authToken: String? = nil) {
        self.baseURL = baseURL
        self.authToken = authToken
        self.session = URLSession.shared
    }

    // Returns the existing NetworkManager.shared for backward compatibility
    static var shared: URLSessionAPIClient {
        let client = URLSessionAPIClient()
        client.authToken = NetworkManager.shared.authToken
        return client
    }

    // MARK: - Private Helpers

    private func makeURL(_ path: String, queryItems: [URLQueryItem] = []) -> URL? {
        guard var components = URLComponents(string: "\(baseURL)\(path)") else { return nil }
        if !queryItems.isEmpty { components.queryItems = queryItems }
        return components.url
    }

    private func authHeader() -> [String: String] {
        guard let token = authToken else { return [:] }
        return ["Authorization": "Bearer \(token)"]
    }

    // MARK: - Auth

    func login(username: String, password: String) async throws -> String {
        let response = try await NetworkManager.shared.login(username: username, password: password)
        return response.token
    }

    func register(username: String, password: String, displayName: String) async throws {
        let _ = try await NetworkManager.shared.register(username: username, password: password, displayName: displayName)
    }

    // MARK: - Analysis

    func startAnalysis(ticker: String, exchange: String, scanType: String) async throws -> StartJobResponse {
        return try await NetworkManager.shared.startAnalysisJob(ticker: ticker, exchange: exchange, userId: nil, scanType: scanType)
    }

    func pollJob(jobId: String) async throws -> JobStatus {
        return try await NetworkManager.shared.pollJob(jobId: jobId, userId: nil)
    }

    func getActiveJob() async throws -> JobStatus? {
        return try await NetworkManager.shared.getActiveJob(userId: 0)
    }

    func cancelJob(jobId: String) async throws {
        try await NetworkManager.shared.cancelJob(jobId: jobId, userId: nil)
    }

    func quickInfo(ticker: String) async throws -> QuickInfo {
        guard let result = await NetworkManager.shared.quickInfo(ticker: ticker) else {
            throw NetworkError.invalidResponse
        }
        return result
    }

    // MARK: - Portfolio

    func fetchPortfolio(userId: Int) async throws -> [PortfolioHolding] {
        return try await NetworkManager.shared.getPortfolio(userId: userId)
    }

    func addHolding(request: PortfolioAddRequest) async throws {
        let _ = try await NetworkManager.shared.addHolding(
            userId: request.userId,
            ticker: request.ticker,
            companyName: request.companyName,
            shares: request.shares,
            buyPrice: request.buyPrice,
            purchaseDate: request.purchaseDate,
            notes: request.notes,
            targetPrice: request.targetPrice
        )
    }

    func removeHolding(userId: Int, ticker: String) async throws {
        try await NetworkManager.shared.removeHolding(userId: userId, ticker: ticker)
    }

    func updateHolding(request: PortfolioUpdateRequest) async throws {
        try await NetworkManager.shared.updateHolding(
            userId: request.userId,
            ticker: request.ticker,
            shares: request.shares,
            buyPrice: request.buyPrice
        )
    }

    // MARK: - Market

    func fetchMarketIndices() async throws -> [LiveMarketIndex] {
        let response = try await NetworkManager.shared.getMarketIndices()
        return response.indices
    }

    func fetchSectorPerformance() async throws -> [SectorPerformance] {
        return try await NetworkManager.shared.getSectorPerformance()
    }

    func fetchMomentum() async throws -> MomentumResponse {
        guard let result = await NetworkManager.shared.fetchMomentum() else {
            throw NetworkError.invalidResponse
        }
        return result
    }

    // MARK: - Watchlist

    func fetchWatchlist(userId: Int) async throws -> [WatchlistItem] {
        return try await NetworkManager.shared.getWatchlist(userId: userId)
    }

    func addToWatchlist(userId: Int, ticker: String, exchange: String, companyName: String) async throws {
        let _ = try await NetworkManager.shared.addToWatchlist(userId: userId, ticker: ticker, exchange: exchange, companyName: companyName)
    }

    func removeFromWatchlist(userId: Int, ticker: String) async throws {
        try await NetworkManager.shared.removeFromWatchlist(userId: userId, ticker: ticker)
    }

    // MARK: - Alerts

    func fetchAlerts(userId: Int) async throws -> [PriceAlert] {
        return try await NetworkManager.shared.getAlerts(userId: userId)
    }

    func addAlert(userId: Int, ticker: String, targetPrice: Double, direction: String) async throws {
        let _ = try await NetworkManager.shared.addAlert(userId: userId, ticker: ticker, targetPrice: targetPrice, direction: direction, companyName: ticker)
    }

    func removeAlert(userId: Int, alertId: Int) async throws {
        try await NetworkManager.shared.removeAlert(userId: userId, alertId: alertId)
    }

    // MARK: - Earnings

    func fetchEarningsCalendar(userId: Int) async throws -> [EarningsCalendarItem] {
        let today = ISO8601DateFormatter().string(from: Date()).prefix(10)
        let results = try await NetworkManager.shared.fetchEarningsCalendarDay(date: String(today))
        return results.map { r in
            EarningsCalendarItem(ticker: r.ticker, companyName: r.companyName, earningsDate: "", estimate: nil, actual: nil, surprise: nil, surprisePct: nil)
        }
    }

    func fetchEarningsProgress() async throws -> EarningsProgressResponse {
        return try await NetworkManager.shared.fetchEarningsProgress()
    }
}
