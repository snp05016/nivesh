import Foundation

class HomeFeedService {
    static let shared = HomeFeedService()
    
    private init() {}
    
    func fetchFeed(userId: Int, ticker: String? = nil) async throws -> HomeFeedResponse {
        var urlString = "\(NetworkManager.shared.baseURL)/api/v1/home-feed?user_id=\(userId)"
        if let ticker = ticker {
            urlString += "&ticker=\(ticker.urlQueryValue)"
        }
        
        guard let url = URL(string: urlString) else {
            throw NetworkError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.timeoutInterval = 30
        if let token = NetworkManager.shared.authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
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

        var request = URLRequest(url: url)
        if let token = NetworkManager.shared.authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NetworkError.invalidResponse
        }

        return try JSONDecoder().decode(ValuationHistoryResponse.self, from: data)
    }
}
