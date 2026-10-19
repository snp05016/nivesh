import Foundation

// MARK: - Platform: client flags, analytics events, data export
//
// GET  /api/v1/flags                  (backend/routers/flags.py, token optional)
// POST /api/v1/events                 (backend/routers/events.py, Bearer required)
// GET  /api/v1/compliance/my-data     (backend/routers/compliance.py, Bearer required, never flag-gated)

/// GET /api/v1/flags body: `{"flags": {key: Bool}, "analytics_retention_days": Int}`.
/// Unknown flag keys are kept; a missing `analytics_retention_days` decodes as nil.
nonisolated struct ClientFlagsResponse: Decodable, Equatable {
    let flags: [String: Bool]
    let analyticsRetentionDays: Int?

    enum CodingKeys: String, CodingKey {
        case flags
        case analyticsRetentionDays = "analytics_retention_days"
    }

    init(flags: [String: Bool], analyticsRetentionDays: Int? = nil) {
        self.flags = flags
        self.analyticsRetentionDays = analyticsRetentionDays
    }
}

/// POST /api/v1/events body.
nonisolated private struct EventsBatchBody: Encodable {
    let events: [QueuedEvent]
    let appVersion: String?
    let platform: String

    enum CodingKeys: String, CodingKey {
        case events
        case appVersion = "app_version"
        case platform
    }
}

extension NetworkManager {

    /// Sends the Bearer token when one exists: the server computes `analytics_consented` per caller.
    func fetchClientFlags() async throws -> ClientFlagsResponse {
        try await _fetchDecode(ClientFlagsResponse.self, endpoint: "/api/v1/flags", timeout: 10)
    }

    /// POST /api/v1/events. 202 (or 200) carries `{accepted, rejected, reason}`.
    func postEvents(_ events: [QueuedEvent]) async throws -> EventsAck {
        let endpoint = "/api/v1/events"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        request.httpBody = try JSONEncoder().encode(EventsBatchBody(events: events, appVersion: version, platform: "ios"))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard http.statusCode == 202 || http.statusCode == 200 else {
            throw NetworkError.serverError(http.statusCode, nil)
        }
        do { return try JSONDecoder().decode(EventsAck.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// GET /api/v1/compliance/my-data: writes the JSON export to a protected temporary file
    /// (the previous export file is removed first) and returns its URL.
    func downloadMyData() async throws -> URL {
        let endpoint = "/api/v1/compliance/my-data"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 60
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, nil)
        }
        let directory = FileManager.default.temporaryDirectory
        if let old = try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil) {
            for file in old where file.lastPathComponent.hasPrefix("nivesh-my-data-") {
                try? FileManager.default.removeItem(at: file)
            }
        }
        let file = directory.appendingPathComponent("nivesh-my-data-\(NetworkManager.istDateString()).json")
        try data.write(to: file, options: [.atomic, .completeFileProtection])
        return file
    }
}
