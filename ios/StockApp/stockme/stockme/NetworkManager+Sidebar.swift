import Foundation
import OSLog

// MARK: - Diagnostic JSON Decode Logger

/// Wraps JSONDecoder.decode with field-level diagnostic logging.
/// When decoding fails, dumps the raw JSON keys vs expected CodingKeys to console.
private func _diagnosticDecode<T: Decodable>(
    _ type: T.Type, from data: Data, label: String
) -> T? {
    let decoder = JSONDecoder()
    do {
        return try decoder.decode(type, from: data)
    } catch let DecodingError.keyNotFound(key, context) {
        let rawStr = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
        let keys = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]).map { Array($0.keys) } ?? []
        os_log(.error,
               "[Nivesh/Decode] %{public}@: keyNotFound '%{public}@' at %{public}@. Raw keys: %{public}@. JSON prefix: %{public}@",
               label, key.stringValue, context.codingPath.map(\.stringValue).joined(separator: "."),
               keys.joined(separator: ", "), String(rawStr))
        print("[Nivesh/Decode] \(label): MISSING KEY '\(key.stringValue)' — raw keys: \(keys.joined(separator: ", "))")
        print("[Nivesh/Decode] JSON prefix: \(rawStr)")
        return nil
    } catch let DecodingError.typeMismatch(_, context) {
        let rawStr = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
        os_log(.error,
               "[Nivesh/Decode] %{public}@: typeMismatch at %{public}@. JSON prefix: %{public}@",
               label, context.codingPath.map(\.stringValue).joined(separator: "."), String(rawStr))
        print("[Nivesh/Decode] \(label): TYPE MISMATCH at \(context.codingPath.map(\.stringValue).joined(separator: "."))")
        print("[Nivesh/Decode] JSON prefix: \(rawStr)")
        return nil
    } catch let DecodingError.valueNotFound(_, context) {
        let rawStr = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
        os_log(.error,
               "[Nivesh/Decode] %{public}@: valueNotFound at %{public}@. JSON prefix: %{public}@",
               label, context.codingPath.map(\.stringValue).joined(separator: "."), String(rawStr))
        print("[Nivesh/Decode] \(label): NULL VALUE at \(context.codingPath.map(\.stringValue).joined(separator: "."))")
        print("[Nivesh/Decode] JSON prefix: \(rawStr)")
        return nil
    } catch let DecodingError.dataCorrupted(context) {
        let rawStr = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
        os_log(.error,
               "[Nivesh/Decode] %{public}@: dataCorrupted — %{public}@. JSON prefix: %{public}@",
               label, context.debugDescription, String(rawStr))
        print("[Nivesh/Decode] \(label): CORRUPTED DATA — \(context.debugDescription)")
        print("[Nivesh/Decode] JSON prefix: \(rawStr)")
        return nil
    } catch {
        let rawStr = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
        os_log(.error,
               "[Nivesh/Decode] %{public}@: unknown error — %{public}@. JSON prefix: %{public}@",
               label, error.localizedDescription, String(rawStr))
        print("[Nivesh/Decode] \(label): DECODE ERROR — \(error.localizedDescription)")
        print("[Nivesh/Decode] JSON prefix: \(rawStr)")
        return nil
    }
}

extension NetworkManager {

    func fetchMarketPulse() async -> MarketPulseResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/pulse") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return _diagnosticDecode(MarketPulseResponse.self, from: data, label: "MarketPulse")
    }

    func fetchMomentum() async -> MomentumResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/momentum") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return _diagnosticDecode(MomentumResponse.self, from: data, label: "Momentum")
    }

    func fetchMacroAlternatives() async -> MacroAlternativesResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/macro-alternatives") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return _diagnosticDecode(MacroAlternativesResponse.self, from: data, label: "MacroAlternatives")
    }

    func fetchInstitutionalFlow() async -> InstitutionalFlowResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/institutional-flow") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return _diagnosticDecode(InstitutionalFlowResponse.self, from: data, label: "InstitutionalFlow")
    }

    func fetchMarketDashboard() async -> MarketDashboardResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/dashboard") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return _diagnosticDecode(MarketDashboardResponse.self, from: data, label: "MarketDashboard")
    }

    /// Fetch extended market dashboard with all 5 core sections:
    /// pulse + momentum + live_reporting_sync + yoy_market_health + cap_index_aggregator
    func fetchExtendedMarketDashboard() async -> ExtendedMarketDashboardResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/dashboard-pulse") else {
            os_log(.error, "[Nivesh/Fetch] ExtendedMarketDashboard: invalid URL")
            return nil
        }
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            if let httpResp = response as? HTTPURLResponse, httpResp.statusCode != 200 {
                os_log(.error, "[Nivesh/Fetch] ExtendedMarketDashboard: HTTP %{public}d", httpResp.statusCode)
                print("[Nivesh/Fetch] ExtendedMarketDashboard: HTTP \(httpResp.statusCode)")
                return nil
            }
            return _diagnosticDecode(ExtendedMarketDashboardResponse.self, from: data, label: "ExtendedMarketDashboard")
        } catch {
            os_log(.error, "[Nivesh/Fetch] ExtendedMarketDashboard: network error — %{public}@", error.localizedDescription)
            print("[Nivesh/Fetch] ExtendedMarketDashboard: NETWORK ERROR — \(error.localizedDescription)")
            return nil
        }
    }

    /// Fetch admin error logs (requires admin auth token)
    func fetchMarketErrorLogs(limit: Int = 50) async -> MarketErrorLogsResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/admin/error-logs?limit=\(limit)") else { return nil }
        var request = URLRequest(url: url)
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            return _diagnosticDecode(MarketErrorLogsResponse.self, from: data, label: "MarketErrorLogs")
        } catch {
            os_log(.error, "[Nivesh/Fetch] MarketErrorLogs: %{public}@", error.localizedDescription)
            return nil
        }
    }
}
