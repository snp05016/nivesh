import Foundation

public protocol FundamentalsAPI {
    func fetchFinancials(ticker: String) async throws -> [FinancialMetrics]
    func fetchShareholding(ticker: String) async throws -> [Shareholding]
    func fetchCorporateActions(ticker: String) async throws -> [CorporateActionDTO]
    func fetchValuation(ticker: String) async throws -> ValuationMetrics
    func fetchRiskSignals(ticker: String) async throws -> [RiskSignalDTO]
}

public class FundamentalsService: FundamentalsAPI {
    public static let shared = FundamentalsService()
    
    private let session: URLSession
    
    public init(session: URLSession = .shared) {
        self.session = session
    }
    
    private func fetch<T: Decodable>(endpoint: String) async throws -> T {
        let baseURL = await NetworkManager.shared.baseURL
        guard let url = URL(string: "\(baseURL)/fundamentals\(endpoint)") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        
        // If auth token is needed, we would fetch it from NetworkManager.shared.authToken here.
        // For public endpoints, it might not be needed.
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }
    
    public func fetchFinancials(ticker: String) async throws -> [FinancialMetrics] {
        return try await fetch(endpoint: "/\(ticker)/financials")
    }
    
    public func fetchShareholding(ticker: String) async throws -> [Shareholding] {
        return try await fetch(endpoint: "/\(ticker)/shareholding")
    }
    
    public func fetchCorporateActions(ticker: String) async throws -> [CorporateActionDTO] {
        return try await fetch(endpoint: "/\(ticker)/corporate-actions")
    }
    
    public func fetchValuation(ticker: String) async throws -> ValuationMetrics {
        return try await fetch(endpoint: "/\(ticker)/valuation")
    }
    
    public func fetchRiskSignals(ticker: String) async throws -> [RiskSignalDTO] {
        return try await fetch(endpoint: "/\(ticker)/risk-signals")
    }
}
