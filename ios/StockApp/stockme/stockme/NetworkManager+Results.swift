import Foundation

// MARK: - Results digest API (see Models/ResultsDigestModels.swift)

extension NetworkManager {

    /// Latest quarterly results digest for a stock. A 404 NO_DIGEST or FEATURE_DISABLED means "show nothing".
    func fetchResultsDigest(symbol: String) async throws -> ResultsDigest {
        let segment = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/"))) ?? symbol
        return try await _fetchDecode(ResultsDigest.self, endpoint: "/api/v1/stocks/\(segment)/results-digest")
    }
}
