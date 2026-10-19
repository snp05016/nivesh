import Foundation

extension NetworkManager {
    /// GET /api/v1/me/holdings/{ticker} (identity from the token). 404 NOT_HELD when no open
    /// holding; 404 FEATURE_DISABLED when money_holding_detail is off on the server.
    func fetchHoldingDetail(ticker: String) async throws -> HoldingDetailResponse {
        try await _fetchDecode(HoldingDetailResponse.self,
                               endpoint: "/api/v1/me/holdings/\(ticker.urlQueryValue)", timeout: 20)
    }

    /// GET /portfolio/benchmark (FIX ARCH-02 checks user_id against the token). The Nifty
    /// history fetch can be slow on a cold cache, hence the longer timeout.
    func fetchPortfolioReturn(userId: Int) async throws -> PortfolioReturnDTO {
        try await _fetchDecode(PortfolioReturnDTO.self, endpoint: "/portfolio/benchmark?user_id=\(userId)", timeout: 30)
    }
}
