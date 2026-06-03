import Foundation

class HomeFeedService {
    static let shared = HomeFeedService()
    
    private init() {}
    
    func fetchFeed(userId: Int, ticker: String? = nil) async throws -> HomeFeedResponse {
        var urlString = "\(NetworkManager.shared.baseURL)/api/v1/home-feed?user_id=\(userId)"
        if let ticker = ticker {
            urlString += "&ticker=\(ticker)"
        }
        
        guard let url = URL(string: urlString) else {
            throw NetworkError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NetworkError.invalidResponse
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(HomeFeedResponse.self, from: data)
    }
    
    func fetchValuationHistory(userId: Int, days: Int = 90) async throws -> ValuationHistoryResponse {
        let urlString = "\(NetworkManager.shared.baseURL)/api/v1/portfolio/valuation-history?user_id=\(userId)&days=\(days)"
        
        guard let url = URL(string: urlString) else {
            throw NetworkError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NetworkError.invalidResponse
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(ValuationHistoryResponse.self, from: data)
    }
}
