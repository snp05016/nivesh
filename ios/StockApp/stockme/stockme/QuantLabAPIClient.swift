import Foundation

// MARK: - Quant Lab API

extension NetworkManager {

    // MARK: - ML Signal

    func fetchMLSignal(symbol: String) async throws -> MLSignalResponse {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        return try await _fetchDecode(
            MLSignalResponse.self,
            endpoint: "/api/v1/stocks/\(encoded)/ml-signal",
            timeout: 15
        )
    }

    // MARK: - Calibration

    func fetchCalibration(horizon: String = "30d") async throws -> CalibrationResponse {
        return try await _fetchDecode(
            CalibrationResponse.self,
            endpoint: "/api/v1/predictions/calibration?horizon=\(horizon)",
            timeout: 15
        )
    }

    // MARK: - Pillar Attribution

    func fetchPillarAttribution(horizon: String = "30d") async throws -> PillarAttributionResponse {
        return try await _fetchDecode(
            PillarAttributionResponse.self,
            endpoint: "/api/v1/predictions/pillar-attribution?horizon=\(horizon)",
            timeout: 15
        )
    }

    // MARK: - Model Versions

    func fetchModelVersions(horizon: String = "30d") async throws -> ModelVersionsResponse {
        return try await _fetchDecode(
            ModelVersionsResponse.self,
            endpoint: "/api/v1/predictions/model-versions?horizon=\(horizon)",
            timeout: 15
        )
    }

    // MARK: - Alpha Validation (Backtest)

    func fetchAlphaValidation() async throws -> BacktestResult {
        let endpoint = "/api/v1/backtests/alpha-validation"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(BacktestParams())

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(body))
        }
        do {
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            return try decoder.decode(BacktestResult.self, from: data)
        } catch {
            throw NetworkError.decodingError(error.localizedDescription)
        }
    }

    // MARK: - Strategy Sweep

    func fetchStrategySweep() async throws -> StrategySweepResponse {
        return try await _fetchDecode(
            StrategySweepResponse.self,
            endpoint: "/api/v1/backtests/strategy-sweep",
            timeout: 20
        )
    }

    // MARK: - Regime Breakdown (Backtest)

    func fetchRegimeBreakdown() async throws -> RegimeBreakdownResponse {
        let endpoint = "/api/v1/backtests/regime-breakdown"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(BacktestParams())

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(body))
        }
        do {
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            return try decoder.decode(RegimeBreakdownResponse.self, from: data)
        } catch {
            throw NetworkError.decodingError(error.localizedDescription)
        }
    }

    // MARK: - Cost Sensitivity

    func fetchCostSensitivity() async throws -> CostSensitivityResponse {
        return try await _fetchDecode(
            CostSensitivityResponse.self,
            endpoint: "/api/v1/backtests/cost-sensitivity",
            timeout: 20
        )
    }
}
