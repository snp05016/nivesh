import Foundation

extension NetworkManager {
    /// GET /api/v1/me/tax/capital-gains?fy=2025-26. 404 FEATURE_DISABLED while money_tax_report is off;
    /// 422 INVALID_FY for a bad label.
    func fetchCapitalGains(fy: String) async throws -> CapitalGainsReport {
        try await _fetchDecode(CapitalGainsReport.self, endpoint: "/api/v1/me/tax/capital-gains?fy=\(fy.urlQueryValue)", timeout: 60)
    }

    /// Downloads the CSV to `nivesh_capital_gains_FY<fy>.csv` in the temporary directory, with file
    /// protection on. The caller deletes it when done.
    func downloadCapitalGainsCSV(fy: String) async throws -> URL {
        let endpoint = "/api/v1/me/tax/capital-gains.csv?fy=\(fy.urlQueryValue)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 60
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            if error is CancellationError || (error as? URLError)?.code == .cancelled { throw error }
            throw NetworkError.connectionFailed
        }
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.fromHTTP(status: http.statusCode, data: data, endpoint: endpoint)
        }
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("nivesh_capital_gains_FY\(fy).csv")
        try data.write(to: file, options: [.atomic, .completeFileProtection])
        return file
    }
}
