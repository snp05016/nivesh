import Foundation

// MARK: - Stock report (Research Engine, /api/v1/research)
//
// Spec 9.1 / 10.2. Every request goes through `authRequest(_:)` (Bearer + correlation
// headers) plus `X-Nivesh-Client`, and uses the session's default URLCache policy so
// the server's ETag / Cache-Control revalidation works without app code. Expected
// "no report" answers come back as `ResearchFetchResult` cases; anything else throws
// a `NetworkError` whose user copy never shows endpoints or bodies.

/// Outcome of a stock report request, mapped from the HTTP status and error `code`.
enum ResearchFetchResult {
    case report(ResearchReport)
    /// 404 NOT_COVERED: no stored report; `computeAvailable` allows POST .../compute.
    case notCovered(computeAvailable: Bool)
    /// 404 UNKNOWN_SYMBOL (or 422 invalid symbol): not an NSE equity.
    case unknownSymbol
    /// 401: no or expired session.
    case signedOut
    /// 404 RESEARCH_DISABLED, shadow-mode 403, or a backend without the route.
    case disabled
}

extension NetworkManager {

    /// The only decoder for research payloads: a plain JSONDecoder. The models carry
    /// explicit snake_case CodingKeys, so no key conversion may be configured here.
    nonisolated static func researchDecoder() -> JSONDecoder {
        JSONDecoder()
    }

    /// GET /api/v1/research/stocks/{symbol}
    func fetchResearchReport(symbol: String) async throws -> ResearchFetchResult {
        let path = try researchPathSymbol(symbol)
        let endpoint = "/api/v1/research/stocks/\(path)"
        let (data, status) = try await researchCall(endpoint, method: "GET", timeout: 20)
        return try mapResearchResponse(data: data, status: status, endpoint: endpoint)
    }

    /// POST /api/v1/research/stocks/{symbol}/compute: synchronous on-demand report for a
    /// symbol outside the nightly set (server budget 15 s, so 20 s here).
    func computeResearchReport(symbol: String) async throws -> ResearchFetchResult {
        let path = try researchPathSymbol(symbol)
        let endpoint = "/api/v1/research/stocks/\(path)/compute"
        let (data, status) = try await researchCall(endpoint, method: "POST", timeout: 20)
        if status == 422 {
            throw NetworkError.serverError(422, "This stock does not have enough trading history for a report yet.")
        }
        return try mapResearchResponse(data: data, status: status, endpoint: endpoint)
    }

    /// GET /api/v1/research/model-card (summary: tier text per horizon, data period,
    /// universe, limitations).
    func fetchResearchModelCard() async throws -> ResearchModelCard {
        let endpoint = "/api/v1/research/model-card"
        let (data, status) = try await researchCall(endpoint, method: "GET", timeout: 20)
        guard (200...299).contains(status) else { throw researchFailure(endpoint, status, data) }
        return try decodeResearch(ResearchModelCard.self, from: data)
    }

    // MARK: - Helpers

    /// Upper-cased with any .NS/.BO suffix removed (the server normalises the same way),
    /// then percent-encoded for the path.
    private func researchPathSymbol(_ raw: String) throws -> String {
        var symbol = raw.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        for suffix in [".NS", ".BO"] where symbol.hasSuffix(suffix) {
            symbol.removeLast(suffix.count)
        }
        var allowed = CharacterSet.urlPathAllowed
        allowed.remove(charactersIn: "/")
        guard !symbol.isEmpty,
              let encoded = symbol.addingPercentEncoding(withAllowedCharacters: allowed) else {
            throw NetworkError.invalidURL
        }
        return encoded
    }

    private func researchCall(_ endpoint: String, method: String, timeout: TimeInterval) async throws -> (Data, Int) {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = method
        request.timeoutInterval = timeout
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(Self.niveshClientHeader, forHTTPHeaderField: "X-Nivesh-Client")
        let result: (Data, URLResponse)
        do {
            result = try await session.data(for: request)
        } catch let error as URLError where error.code != .cancelled {
            throw NetworkError.connectionFailed
        }
        guard let http = result.1 as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        return (result.0, http.statusCode)
    }

    /// "ios/<CFBundleShortVersionString>(<CFBundleVersion>)" (spec 9.4).
    private static var niveshClientHeader: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "0"
        let build = info?["CFBundleVersion"] as? String ?? "0"
        return "ios/\(version)(\(build))"
    }

    private func mapResearchResponse(data: Data, status: Int, endpoint: String) throws -> ResearchFetchResult {
        switch status {
        case 200...299:
            return .report(try decodeResearch(ResearchReport.self, from: data))
        case 401:
            return .signedOut
        case 403:
            return .disabled
        case 404:
            let body = researchErrorBody(data)
            switch body.code {
            case "NOT_COVERED": return .notCovered(computeAvailable: body.computeAvailable)
            case "UNKNOWN_SYMBOL": return .unknownSymbol
            default: return .disabled   // RESEARCH_DISABLED, or the route is not deployed yet
            }
        case 422:
            return .unknownSymbol
        default:
            throw researchFailure(endpoint, status, data)
        }
    }

    /// Reads `code` / `compute_available` from a top-level error object or from
    /// FastAPI's `{"detail": {...}}` wrapper.
    private func researchErrorBody(_ data: Data) -> (code: String?, computeAvailable: Bool) {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return (nil, false)
        }
        let payload = (obj["code"] == nil ? obj["detail"] as? [String: Any] : nil) ?? obj
        return (payload["code"] as? String, payload["compute_available"] as? Bool ?? false)
    }

    private func researchFailure(_ endpoint: String, _ status: Int, _ data: Data) -> NetworkError {
        let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
        return NetworkError.fetchFailed(endpoint: endpoint, status: status, body: String(body))
    }

    private func decodeResearch<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do { return try Self.researchDecoder().decode(T.self, from: data) }
        catch { throw NetworkError.decodingError(String(describing: error)) }
    }
}
