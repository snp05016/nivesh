import Foundation

/// GET /api/v1/features body: `{"flags": {key: Bool}, "version": 1}` (no auth).
nonisolated struct FeatureFlagsResponse: Decodable {
    let flags: [String: Bool]
}

extension NetworkManager {
    func fetchFeatureFlags() async throws -> FeatureFlagsResponse {
        try await _fetchDecode(FeatureFlagsResponse.self, endpoint: "/api/v1/features", timeout: 10)
    }
}
