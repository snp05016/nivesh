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
        guard let url = URL(string: "\(baseURL)/api/v1/market/pulse") else {
            os_log(.error, "[Nivesh/Fetch] MarketPulse: invalid URL")
            print("[Nivesh/Fetch] MarketPulse: INVALID URL")
            return nil
        }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] MarketPulse: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] MarketPulse: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(MarketPulseResponse.self, from: data, label: "MarketPulse")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] MarketPulse: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] MarketPulse: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    func fetchMomentum() async -> MomentumResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/momentum") else {
            os_log(.error, "[Nivesh/Fetch] Momentum: invalid URL")
            print("[Nivesh/Fetch] Momentum: INVALID URL")
            return nil
        }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] Momentum: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] Momentum: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(MomentumResponse.self, from: data, label: "Momentum")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] Momentum: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] Momentum: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    func fetchMacroAlternatives() async -> MacroAlternativesResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/macro-alternatives") else {
            os_log(.error, "[Nivesh/Fetch] MacroAlternatives: invalid URL")
            print("[Nivesh/Fetch] MacroAlternatives: INVALID URL")
            return nil
        }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] MacroAlternatives: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] MacroAlternatives: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(MacroAlternativesResponse.self, from: data, label: "MacroAlternatives")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] MacroAlternatives: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] MacroAlternatives: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    func fetchInstitutionalFlow() async -> InstitutionalFlowResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/institutional-flow") else {
            os_log(.error, "[Nivesh/Fetch] InstitutionalFlow: invalid URL")
            print("[Nivesh/Fetch] InstitutionalFlow: INVALID URL")
            return nil
        }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] InstitutionalFlow: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] InstitutionalFlow: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(InstitutionalFlowResponse.self, from: data, label: "InstitutionalFlow")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] InstitutionalFlow: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] InstitutionalFlow: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    func fetchMarketDashboard() async -> MarketDashboardResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/dashboard") else {
            os_log(.error, "[Nivesh/Fetch] MarketDashboard: invalid URL")
            print("[Nivesh/Fetch] MarketDashboard: INVALID URL")
            return nil
        }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] MarketDashboard: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] MarketDashboard: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(MarketDashboardResponse.self, from: data, label: "MarketDashboard")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] MarketDashboard: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] MarketDashboard: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    /// Fetch extended market dashboard with all 5 core sections:
    /// pulse + momentum + live_reporting_sync + yoy_market_health + cap_index_aggregator
    func fetchExtendedMarketDashboard() async -> ExtendedMarketDashboardResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/dashboard-pulse") else {
            os_log(.error, "[Nivesh/Fetch] ExtendedMarketDashboard: invalid URL")
            return nil
        }
        do {
            let (data, response) = try await session.data(for: authRequest(url))
            if let httpResp = response as? HTTPURLResponse, httpResp.statusCode != 200 {
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] ExtendedMarketDashboard: HTTP %{public}d, body: %{public}@", httpResp.statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] ExtendedMarketDashboard: HTTP \(httpResp.statusCode) — body: \(bodyPrefix)")
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
        guard let url = URL(string: "\(baseURL)/api/v1/admin/error-logs?limit=\(limit)") else {
            os_log(.error, "[Nivesh/Fetch] MarketErrorLogs: invalid URL")
            print("[Nivesh/Fetch] MarketErrorLogs: INVALID URL")
            return nil
        }
        let request = authRequest(url)
        do {
            let (data, resp) = try await session.data(for: request)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] MarketErrorLogs: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] MarketErrorLogs: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(MarketErrorLogsResponse.self, from: data, label: "MarketErrorLogs")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] MarketErrorLogs: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] MarketErrorLogs: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    // MARK: - Earnings Calendar & Feed (Extended)

    /// Fetch earnings calendar for a date with 7-day price sparklines per ticker.
    func fetchEarningsCalendar(date: String, ticker: String? = nil) async -> EarningsCalendarDayResponse? {
        var path = "/api/v1/earnings/calendar?date=\(date)"
        if let t = ticker { path += "&ticker=\(t.urlQueryValue)" }
        guard let url = URL(string: "\(baseURL)\(path)") else {
            os_log(.error, "[Nivesh/Fetch] EarningsCalendar: invalid URL")
            print("[Nivesh/Fetch] EarningsCalendar: INVALID URL")
            return nil
        }
        var req = authRequest(url); req.timeoutInterval = 25
        do {
            let (data, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] EarningsCalendar: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] EarningsCalendar: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(EarningsCalendarDayResponse.self, from: data, label: "EarningsCalendar")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] EarningsCalendar: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] EarningsCalendar: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    /// Fetch ranked earnings feed with Latest/Best/Worst categorization.
    /// Timeout is 90s because the backend yfinance fallback queries 12 tickers
    /// sequentially (3 retries each) — this can take 30-60 seconds.
    func fetchRankedEarningsFeed(sort: String = "latest") async -> EarningsFeedResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/earnings/feed?sort=\(sort)") else {
            os_log(.error, "[Nivesh/Fetch] EarningsFeed: invalid URL")
            print("[Nivesh/Fetch] EarningsFeed: INVALID URL — baseURL=\(baseURL), sort=\(sort)")
            return nil
        }
        var req = authRequest(url); req.timeoutInterval = 90
        do {
            let (data, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] EarningsFeed: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] EarningsFeed: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(EarningsFeedResponse.self, from: data, label: "EarningsFeed")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] EarningsFeed: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] EarningsFeed: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    /// Fetch earnings-specific error logs (admin).
    func fetchEarningsErrorLogs(limit: Int = 50) async -> EarningsErrorLogsResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/admin/earnings-errors?limit=\(limit)") else {
            os_log(.error, "[Nivesh/Fetch] EarningsErrorLogs: invalid URL")
            print("[Nivesh/Fetch] EarningsErrorLogs: INVALID URL")
            return nil
        }
        let request = authRequest(url)
        do {
            let (data, resp) = try await session.data(for: request)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                let statusCode = (resp as? HTTPURLResponse)?.statusCode ?? -1
                let bodyPrefix = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                os_log(.error, "[Nivesh/Fetch] EarningsErrorLogs: HTTP %{public}d, body: %{public}@", statusCode, String(bodyPrefix))
                print("[Nivesh/Fetch] EarningsErrorLogs: HTTP \(statusCode) — body: \(bodyPrefix)")
                return nil
            }
            return _diagnosticDecode(EarningsErrorLogsResponse.self, from: data, label: "EarningsErrorLogs")
        } catch {
            let nsErr = error as NSError
            os_log(.error, "[Nivesh/Fetch] EarningsErrorLogs: network error [%{public}@:%{public}ld] — %{public}@",
                   nsErr.domain, nsErr.code, error.localizedDescription)
            print("[Nivesh/Fetch] EarningsErrorLogs: NETWORK ERROR [\(nsErr.domain):\(nsErr.code)] — \(error.localizedDescription)")
            return nil
        }
    }

    // MARK: - Ideas Workspace

    func fetchAdvisors() async -> AdvisorsResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/ideas/advisors") else { return nil }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            return _diagnosticDecode(AdvisorsResponse.self, from: data, label: "Advisors")
        } catch {
            os_log(.error, "[Nivesh/Fetch] Advisors: %{public}@", error.localizedDescription)
            return nil
        }
    }

    func fetchIdeasFeed(limit: Int = 20, sentiment: String = "all") async -> IdeasFeedResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/ideas/feed?limit=\(limit)&sentiment=\(sentiment)") else { return nil }
        do {
            let (data, resp) = try await session.data(for: authRequest(url))
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            return _diagnosticDecode(IdeasFeedResponse.self, from: data, label: "IdeasFeed")
        } catch {
            os_log(.error, "[Nivesh/Fetch] IdeasFeed: %{public}@", error.localizedDescription)
            return nil
        }
    }
}
