import Foundation

extension NetworkManager {
    /// GET /api/v1/me/portfolio/xray (identity from the token). 404 FEATURE_DISABLED while money_xray is off.
    func fetchXRay() async throws -> XRayResponse {
        try await _fetchDecode(XRayResponse.self, endpoint: "/api/v1/me/portfolio/xray", timeout: 30)
    }

    /// GET /api/v1/me/portfolio/crisis-replay?scenario=covid_2020. 503 REPLAY_UNAVAILABLE when the
    /// engine cannot answer; 404 FEATURE_DISABLED while money_crisis_replay is off.
    func fetchCrisisReplay() async throws -> CrisisReplayResponse {
        try await _fetchDecode(CrisisReplayResponse.self,
                               endpoint: "/api/v1/me/portfolio/crisis-replay?scenario=covid_2020", timeout: 30)
    }
}
