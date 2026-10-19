import Foundation

// MARK: - Corporate actions API (see Models/CorporateActionModels.swift)

extension NetworkManager {

    func fetchCorporateActions() async throws -> [CorporateActionItem] {
        let list = try await _fetchDecode(CorporateActionList.self, endpoint: "/api/v1/portfolio/corporate-actions")
        return list.items
    }

    /// POST .../{id}/apply, /dismiss or /undo. Non-2xx throws `fetchFailed` carrying the status and the body prefix.
    func mutateCorporateAction(id: Int, action: CorporateActionMutation) async throws -> CorporateActionMutationResponse {
        let endpoint = "/api/v1/portfolio/corporate-actions/\(id)/\(action.rawValue)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            if error is CancellationError || (error as? URLError)?.code == .cancelled { throw error }
            throw NetworkError.fetchFailed(endpoint: endpoint, status: -1, body: "Network error: \(error.localizedDescription)")
        }
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(body))
        }
        do {
            return try JSONDecoder().decode(CorporateActionMutationResponse.self, from: data)
        } catch {
            throw NetworkError.decodingError("\(endpoint): \(error)")
        }
    }
}
