import Foundation

// MARK: - User preferences (backend/routers/preferences.py, auth'd)
//
// GET/PUT /api/v1/preferences. `alerts_enabled` is the server-side push switch:
// the price-alert poller and the APNs delivery helpers skip pushes when it is false.

struct UserPreferencesDTO: Codable {
    let alertsEnabled: Bool?

    enum CodingKeys: String, CodingKey {
        case alertsEnabled = "alerts_enabled"
    }
}

extension NetworkManager {

    func fetchPreferences() async throws -> UserPreferencesDTO {
        try await _fetchDecode(UserPreferencesDTO.self, endpoint: "/api/v1/preferences")
    }

    /// Persists the push master switch server-side. Throws on any non-2xx.
    func updateAlertsEnabled(_ enabled: Bool) async throws {
        let endpoint = "/api/v1/preferences"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "PUT"
        request.timeoutInterval = 15
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(UserPreferencesDTO(alertsEnabled: enabled))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw NetworkError.fromHTTP(status: status, data: data, endpoint: endpoint)
        }
    }
}
