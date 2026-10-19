import Foundation

// MARK: - My account (backend/routers/account.py, auth'd)

extension NetworkManager {

    /// PATCH /api/v1/me/profile (GH-692). Returns the display name the server
    /// stored (trimmed). Throws on any non-2xx.
    func updateProfile(displayName: String) async throws -> String {
        struct Body: Codable {
            let displayName: String
            enum CodingKeys: String, CodingKey { case displayName = "display_name" }
        }
        let endpoint = "/api/v1/me/profile"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "PATCH"
        request.timeoutInterval = 15
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Body(displayName: displayName))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw NetworkError.fromHTTP(status: status, data: data, endpoint: endpoint)
        }
        return try JSONDecoder().decode(Body.self, from: data).displayName
    }
}
