import Foundation

// Tool screens (Copilot, Correlation, Strategy Lab, Stress Test, live analysis
// stream) that used to build requests inline (ARCH-15). Every request starts
// from `authRequest`, so the Bearer token and app-version headers are attached.
extension NetworkManager {

    /// Authenticated request on `session`. Returns the raw body and HTTP response for
    /// callers that render status-specific diagnostics; transport errors (URLError)
    /// propagate unchanged.
    func _send(_ path: String, method: String = "GET", json body: [String: Any]? = nil,
               headers: [String: String] = [:],
               timeout: TimeInterval = 30) async throws -> (Data, HTTPURLResponse) {
        guard let url = URL(string: "\(baseURL)\(path)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        for (field, value) in headers { req.setValue(value, forHTTPHeaderField: field) }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        return (data, http)
    }

    /// `_send`, then `NetworkError.ensureOK` (401/402 typed, else serverError with the
    /// FastAPI `detail`), then decode.
    func _sendDecode<T: Decodable>(_ type: T.Type, _ path: String, method: String = "GET",
                                   json body: [String: Any]? = nil,
                                   timeout: TimeInterval = 30) async throws -> T {
        let (data, http) = try await _send(path, method: method, json: body, timeout: timeout)
        try NetworkError.ensureOK(data: data, response: http)
        do { return try JSONDecoder().decode(type, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    func copilotChat(_ body: [String: Any]) async throws -> CopilotResponse {
        try await _sendDecode(CopilotResponse.self, "/api/v1/copilot/chat", method: "POST", json: body)
    }

    /// Raw response: NLScreenerScreen renders status-specific diagnostics. `correlationId`
    /// replaces the one authRequest generates so the ID shown on screen matches the server log.
    func nlScreenerSearch(query: String, correlationId: String) async throws -> (Data, HTTPURLResponse) {
        try await _send("/api/v1/screener/natural-language", method: "POST", json: ["query": query],
                        headers: ["X-Correlation-ID": correlationId], timeout: 120)
    }

    func fetchPortfolioCorrelation() async throws -> CorrelationResponse {
        try await _sendDecode(CorrelationResponse.self, "/portfolio/correlation?portfolio_id=holdings", timeout: 90)
    }

    func runStrategyBacktest(ticker: String, strategyId: String, years: Int) async throws -> StrategyBacktestResult {
        try await _sendDecode(StrategyBacktestResult.self, "/analysis/backtest", method: "POST",
                              json: ["ticker": ticker, "strategy_id": strategyId, "years": years])
    }

    /// Raw response: StressTestScreen shows status/body in its diagnostic card.
    func startStressTest(scenarios: [String]) async throws -> (Data, HTTPURLResponse) {
        try await _send("/api/v1/portfolio/stress-test", method: "POST",
                        json: ["portfolio_id": "holdings", "scenarios": scenarios])
    }

    func pollStressTest(jobId: String) async throws -> (Data, HTTPURLResponse) {
        try await _send("/api/v1/portfolio/stress-test/\(jobId.urlQueryValue)")
    }

    /// SSE agent stream for DialecticProgressView. Uses URLSession.shared on purpose:
    /// `session` caps a whole transfer at 120 s (timeoutIntervalForResource), which
    /// would cut long analysis streams. Auth still comes from `authRequest`.
    func dashboardStreamBytes(userId: Int, ticker: String) async throws -> URLSession.AsyncBytes {
        let path = "/api/v1/dashboard/stream?user_id=\(userId)&ticker=\(ticker.urlQueryValue)"
        guard let url = URL(string: "\(baseURL)\(path)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 120
        let (bytes, response) = try await URLSession.shared.bytes(for: req)
        // An error body is JSON, not SSE: fail here instead of streaming nothing.
        AuthAwareSession.check(req, response)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            bytes.task.cancel()
            throw NetworkError.fromHTTP(status: http.statusCode, data: Data(), endpoint: path)
        }
        return bytes
    }
}
