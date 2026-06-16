// APIClient.swift — Protocol-based API client (Candidate 4)
import Foundation

// MARK: - Request Types

struct PortfolioAddRequest: Codable {
    let userId: Int
    let ticker: String
    let companyName: String
    let shares: Double
    let buyPrice: Double
    let purchaseDate: Date
    let notes: String
    let targetPrice: Double
}

struct PortfolioUpdateRequest: Codable {
    let userId: Int
    let ticker: String
    let shares: Double
    let buyPrice: Double
}

// MARK: - Domain Protocols

protocol AnalysisAPI {
    func startAnalysis(ticker: String, exchange: String, scanType: String) async throws -> StartJobResponse
    func pollJob(jobId: String) async throws -> JobStatus
    func getActiveJob() async throws -> JobStatus?
    func cancelJob(jobId: String) async throws
    func quickInfo(ticker: String) async throws -> QuickInfo
}

protocol PortfolioAPI {
    func fetchPortfolio(userId: Int) async throws -> [PortfolioHolding]
    func addHolding(request: PortfolioAddRequest) async throws
    func removeHolding(userId: Int, ticker: String) async throws
    func updateHolding(request: PortfolioUpdateRequest) async throws
}

protocol MarketAPI {
    func fetchMarketIndices() async throws -> [LiveMarketIndex]
    func fetchSectorPerformance() async throws -> [SectorPerformance]
    func fetchMomentum() async throws -> MomentumResponse
}

protocol AuthAPI {
    func login(username: String, password: String) async throws -> String // returns token
    func register(username: String, password: String, displayName: String) async throws
}

protocol WatchlistAPI {
    func fetchWatchlist(userId: Int) async throws -> [WatchlistItem]
    func addToWatchlist(userId: Int, ticker: String, exchange: String, companyName: String) async throws
    func removeFromWatchlist(userId: Int, ticker: String) async throws
}

protocol AlertsAPI {
    func fetchAlerts(userId: Int) async throws -> [PriceAlert]
    func addAlert(userId: Int, ticker: String, targetPrice: Double, direction: String) async throws
    func removeAlert(userId: Int, alertId: Int) async throws
}

protocol EarningsAPI {
    func fetchEarningsCalendar(userId: Int) async throws -> [EarningsCalendarItem]
    func fetchEarningsProgress() async throws -> EarningsProgressResponse
}

// MARK: - Unified Protocol

protocol APIClient: AnalysisAPI, PortfolioAPI, MarketAPI, AuthAPI, WatchlistAPI, AlertsAPI, EarningsAPI {
    var baseURL: String { get }
    var authToken: String? { get set }
}
