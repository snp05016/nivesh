import Foundation

class ValuationCalendarService {
    static let shared = ValuationCalendarService()
    private init() {}

    func fetchValuationHistory(userId: Int, days: Int = 90) async throws -> ValuationHistoryResponse {
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/portfolio/valuation-history?user_id=\(userId)&days=\(days)") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        if let token = NetworkManager.shared.authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ValuationHistoryResponse.self, from: data)
    }
}
