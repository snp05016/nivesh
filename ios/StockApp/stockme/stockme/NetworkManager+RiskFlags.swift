import Foundation

extension NetworkManager {

    /// At most three risk flags for a stock the user holds. Returns nil on 404 (flags off).
    /// GET /api/v1/stocks/{symbol}/risk-flags
    func fetchRiskFlags(symbol: String) async throws -> RiskFlagsDTO? {
        // .urlPathAllowed keeps '&' so M&M survives.
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        let endpoint = "/api/v1/stocks/\(encoded)/risk-flags"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.timeoutInterval = 10
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        if http.statusCode == 404 { return nil }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.fromHTTP(status: http.statusCode, data: data, endpoint: endpoint)
        }
        do { return try JSONDecoder().decode(RiskFlagsDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}
