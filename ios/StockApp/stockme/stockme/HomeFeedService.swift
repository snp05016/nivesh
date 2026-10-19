import Foundation

/// Thin facade over NetworkManager's shared pipeline (Bearer, correlation id,
/// status check, typed errors).
class HomeFeedService {
    static let shared = HomeFeedService()
    
    private init() {}
    
    func fetchFeed(userId: Int, ticker: String? = nil) async throws -> HomeFeedResponse {
        var endpoint = "/api/v1/home-feed?user_id=\(userId)"
        if let ticker = ticker {
            endpoint += "&ticker=\(ticker.urlQueryValue)"
        }
        return try await NetworkManager.shared._fetchDecode(HomeFeedResponse.self, endpoint: endpoint, timeout: 30)
    }
    
    func fetchValuationHistory(userId: Int, days: Int = 90) async throws -> ValuationHistoryResponse {
        try await NetworkManager.shared.fetchValuationHistory(userId: userId, days: days)
    }
}
