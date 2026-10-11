import Foundation

// MARK: - Session management (AUTH-13)
//
// backend/routers/auth.py: both calls bump users.token_version server-side, so
// every token issued before (on every device, this one included) stops working.
// Callers sign the user out locally afterwards.

private struct ChangePasswordBody: Encodable {
    let currentPassword: String
    let newPassword: String

    enum CodingKeys: String, CodingKey {
        case currentPassword = "current_password"
        case newPassword = "new_password"
    }
}

extension NetworkManager {

    /// POST /api/v1/auth/change-password. A wrong current password or a weak new
    /// one throws NetworkError.serverError(400, detail) with the server's message.
    func changePassword(current: String, new: String) async throws {
        let body = try JSONEncoder().encode(ChangePasswordBody(currentPassword: current, newPassword: new))
        try await postAuth("/api/v1/auth/change-password", body: body)
    }

    /// POST /api/v1/auth/logout: revokes every session of the signed-in user.
    func logoutAllSessions() async throws {
        try await postAuth("/api/v1/auth/logout", body: nil)
    }

    private func postAuth(_ endpoint: String, body: Data?) async throws {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        let (data, response) = try await session.data(for: request)
        try NetworkError.ensureOK(data: data, response: response)
    }
}
